"""Country-indicator request handlers.

One handler per country indicator, registered in :data:`HANDLERS`. Each
handler parses its JSON request body (see ``app.api.schemas``), pulls
externalized policy (weights, thresholds, mortgage assumptions, method
preferences) from the geography's country profile YAML
(``app.config.loader.load_country_profile``), and delegates the actual
math to the matching ``app.engines.country.*`` module. This file contains
no formulas -- only request wiring.
"""

from __future__ import annotations

from collections.abc import Callable

from app.api.schemas import SchemaError, get_float, get_mapping, get_str, parse_observation_series, parse_period_field, require
from app.api.util import now_iso
from app.engines.country import (
    broad_money,
    economy_wide,
    essential_cost,
    excess_money,
    fixed_lifestyle,
    headline_consumer,
    housing,
    producer_import,
    purchasing_power,
    underlying
)
from app.engines.shared.periods import parse_period
from app.models.enums import Frequency
from app.models.indicator_result import IndicatorResult

Handler = Callable[[str, dict, dict], IndicatorResult]


def _handle_headline_consumer(geo: str, body: dict) -> IndicatorResult:
    series = parse_observation_series(require(body, "observations"))
    if series.geography != geo:
        raise SchemaError(f"observations geography {series.geography!r} does not match path geography {geo!r}")
    period = parse_period_field(body, "period", series.frequency)
    return headline_consumer.calculate(series, period, calculated_at=now_iso())


def _handle_underlying(geo: str, body: dict, profile: dict) -> IndicatorResult:
    cfg_raw = profile["underlying"]
    trim = cfg_raw.get("trim_mean", cfg_raw.get("trimmed_mean", {}))
    config = underlying.UnderlyingConfig(
        preferred_method=cfg_raw["preferred_method"],
        fallback_methods=tuple(cfg_raw.get("fallback_methods", ())),
        trim_alpha=trim.get("alpha", 0.1),
        trim_beta=trim.get("beta", 0.1),
        excluded_categories=tuple(cfg_raw.get("core_exclusion", {}).get("excluded_categories", ())),
        trim_boundary_handling=trim.get("boundary_handling", "exclude_whole"),
    )
    return underlying.calculate(
        component_rates=get_mapping(body, "component_rates"),
        component_weights=get_mapping(body, "component_weights"),
        config=config,
        geography=geo,
        period=get_str(body, "period"),
        calculated_at=now_iso(),
        official_core_value=get_float(body, "official_core_value", required=False),
    )


def _handle_essential_cost(geo: str, body: dict, profile: dict) -> IndicatorResult:
    basket = profile["essential_basket"]
    config = essential_cost.EssentialBasketConfig(
        version=basket["version"],
        methodology=basket["methodology"],
        categories=basket["categories"],
        min_coverage_percent=float(basket.get("min_coverage_percent", 80.0)),
        structurally_dominant_weight=float(basket["structurally_dominant_weight"]),
    )
    return essential_cost.calculate_from_rates(
        get_mapping(body, "category_rates"),
        config,
        geography=geo,
        period=get_str(body, "period"),
        calculated_at=now_iso(),
    )


def _handle_fixed_lifestyle(geo: str, body: dict, profile: dict) -> IndicatorResult:
    fl_cfg = profile["fixed_lifestyle"]
    config = fixed_lifestyle.FixedLifestyleConfig(basket_version=fl_cfg["basket_version"])
    replacements_raw = body.get("replacements") or {}
    replacements = {
        item: fixed_lifestyle.ItemReplacement(item_id=item, replacement_level=info["replacement_level"], note=info.get("note", ""))
        for item, info in replacements_raw.items()
    }
    return fixed_lifestyle.calculate(
        prices_current=get_mapping(body, "prices_current"),
        prices_prior_year=get_mapping(body, "prices_prior_year"),
        prices_base=get_mapping(body, "prices_base"),
        quantities_base=get_mapping(body, "quantities_base"),
        config=config,
        geography=geo,
        period=get_str(body, "period"),
        calculated_at=now_iso(),
        package_sizes_current=get_mapping(body, "package_sizes_current", required=False),
        package_sizes_base=get_mapping(body, "package_sizes_base", required=False),
        replacements=replacements or None,
        quality_adjustment_factors=get_mapping(body, "quality_adjustment_factors", required=False),
        quality_adjusted_prices_current=get_mapping(body, "quality_adjusted_prices_current", required=False),
    )


def _handle_housing(geo: str, body: dict, profile: dict) -> IndicatorResult:
    h_cfg = profile["housing"]
    mortgage_assumptions = housing.MortgageAssumptions(
        term_years=int(h_cfg["mortgage_term_years"]),
        loan_to_value=float(h_cfg["loan_to_value"]),
        payment_frequency=h_cfg.get("payment_frequency", "monthly"),
    )
    weights_raw = h_cfg.get("pressure_score_weights")
    pressure_weights = (
        housing.HousingPressureWeights(rent=weights_raw["rent"], mortgage=weights_raw["mortgage"], burden=weights_raw["burden"])
        if weights_raw
        else None
    )
    standardization_windows = body.get("standardization_windows")

    return housing.calculate(
        rent_index_current=get_float(body, "rent_index_current"),
        rent_index_prior_year=get_float(body, "rent_index_prior_year"),
        house_price_index_current=get_float(body, "house_price_index_current"),
        house_price_index_prior_year=get_float(body, "house_price_index_prior_year"),
        geography=geo,
        period=get_str(body, "period"),
        calculated_at=now_iso(),
        property_price_current=get_float(body, "property_price_current", required=False),
        property_price_prior_year=get_float(body, "property_price_prior_year", required=False),
        mortgage_rate_current=get_float(body, "mortgage_rate_current", required=False),
        mortgage_rate_prior_year=get_float(body, "mortgage_rate_prior_year", required=False),
        mortgage_assumptions=mortgage_assumptions,
        monthly_housing_cost=get_float(body, "monthly_housing_cost", required=False),
        monthly_disposable_income=get_float(body, "monthly_disposable_income", required=False),
        pressure_score_weights=pressure_weights,
        standardization_windows=standardization_windows,
    )


def _handle_broad_money(geo: str, body: dict, profile: dict) -> IndicatorResult:
    return broad_money.calculate(
        money_current=get_float(body, "money_current"),
        money_prior_year=get_float(body, "money_prior_year"),
        aggregate_name=profile["money"]["preferred_aggregate"],
        geography=geo,
        period=get_str(body, "period"),
        calculated_at=now_iso(),
        population_current=get_float(body, "population_current", required=False),
        population_prior_year=get_float(body, "population_prior_year", required=False),
        real_gdp_current=get_float(body, "real_gdp_current", required=False),
        real_gdp_prior_year=get_float(body, "real_gdp_prior_year", required=False),
    )


def _handle_excess_money(geo: str, body: dict, profile: dict) -> IndicatorResult:
    money_freq = Frequency(get_str(body, "money_frequency", required=False, default="quarterly"))
    output_freq = Frequency(get_str(body, "real_output_frequency", required=False, default="quarterly"))
    money_period = parse_period(get_str(body, "money_period"), money_freq)
    real_output_period = parse_period(get_str(body, "real_output_period"), output_freq)
    return excess_money.calculate(
        money_growth_percent=get_float(body, "money_growth_percent"),
        real_output_growth_percent=get_float(body, "real_output_growth_percent"),
        money_period=money_period,
        real_output_period=real_output_period,
        geography=geo,
        period=get_str(body, "period"),
        calculated_at=now_iso(),
        nominal_gdp_current=get_float(body, "nominal_gdp_current", required=False),
        nominal_gdp_prior=get_float(body, "nominal_gdp_prior", required=False),
        money_current=get_float(body, "money_current", required=False),
        money_prior=get_float(body, "money_prior", required=False),
    )


def _handle_producer_import(geo: str, body: dict, profile: dict) -> IndicatorResult:
    config = producer_import.ProducerImportConfig(component_weights=profile["producer_import"]["component_weights"])
    return producer_import.calculate(
        ppi_current=get_float(body, "ppi_current"),
        ppi_prior_year=get_float(body, "ppi_prior_year"),
        import_price_current=get_float(body, "import_price_current"),
        import_price_prior_year=get_float(body, "import_price_prior_year"),
        energy_inflation_percent=get_float(body, "energy_inflation_percent"),
        commodity_inflation_percent=get_float(body, "commodity_inflation_percent"),
        config=config,
        geography=geo,
        period=get_str(body, "period"),
        calculated_at=now_iso(),
        foreign_price_growth_percent=get_float(body, "foreign_price_growth_percent", required=False),
        exchange_rate_growth_percent=get_float(body, "exchange_rate_growth_percent", required=False),
        upp_standardization_window=body.get("upp_standardization_window"),
    )


def _handle_economy_wide(geo: str, body: dict, profile: dict) -> IndicatorResult:
    return economy_wide.calculate(
        nominal_gdp_current=get_float(body, "nominal_gdp_current"),
        real_gdp_current=get_float(body, "real_gdp_current"),
        nominal_gdp_prior_year=get_float(body, "nominal_gdp_prior_year"),
        real_gdp_prior_year=get_float(body, "real_gdp_prior_year"),
        geography=geo,
        period=get_str(body, "period"),
        calculated_at=now_iso(),
        nominal_domestic_demand_current=get_float(body, "nominal_domestic_demand_current", required=False),
        real_domestic_demand_current=get_float(body, "real_domestic_demand_current", required=False),
        nominal_domestic_demand_prior_year=get_float(body, "nominal_domestic_demand_prior_year", required=False),
        real_domestic_demand_prior_year=get_float(body, "real_domestic_demand_prior_year", required=False),
    )


def _handle_purchasing_power(geo: str, body: dict, profile: dict) -> IndicatorResult:
    pp_cfg = profile["purchasing_power"]
    return purchasing_power.calculate(
        nominal_wage_growth_percent=get_float(body, "nominal_wage_growth_percent"),
        headline_inflation_percent=get_float(body, "headline_inflation_percent"),
        essential_inflation_percent=get_float(body, "essential_inflation_percent"),
        wage_measure=pp_cfg["wage_measure"],
        income_definition=pp_cfg["income_definition"],
        geography=geo,
        period=get_str(body, "period"),
        calculated_at=now_iso(),
        disposable_income_growth_percent=get_float(body, "disposable_income_growth_percent", required=False),
    )


HANDLERS: dict[str, Handler] = {
    headline_consumer.INDICATOR_ID: _handle_headline_consumer,
    underlying.INDICATOR_ID: _handle_underlying,
    essential_cost.INDICATOR_ID: _handle_essential_cost,
    fixed_lifestyle.INDICATOR_ID: _handle_fixed_lifestyle,
    housing.INDICATOR_ID: _handle_housing,
    broad_money.INDICATOR_ID: _handle_broad_money,
    excess_money.INDICATOR_ID: _handle_excess_money,
    producer_import.INDICATOR_ID: _handle_producer_import,
    economy_wide.INDICATOR_ID: _handle_economy_wide,
    purchasing_power.INDICATOR_ID: _handle_purchasing_power,
}
