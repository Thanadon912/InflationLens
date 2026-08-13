"""Global-indicator request handlers.

Mirrors ``app.api.country``: one handler per global indicator, registered
in :data:`HANDLERS`. Policy defaults (weight method label, coverage
thresholds, composite weights) come from ``app.config.loader.load_global_weights``;
actual per-country weight *values* are supplied in the request body, since
they are live data this phase does not fetch itself (see
``app/config/global_weights.yaml`` for why).
"""

from __future__ import annotations

from collections.abc import Callable

from app.api.schemas import get_float, get_mapping, get_str, require
from app.api.util import now_iso
from app.engines.global_ import (
    consumer,
    essential,
    excess_money,
    housing_assets,
    median_country,
    monetary,
    producer_pressure,
    synchronization,
)
from app.models.indicator_result import IndicatorResult

Handler = Callable[[dict, dict], IndicatorResult]


def _all_geographies(body: dict) -> tuple[str, ...]:
    geos = require(body, "all_geographies")
    if not isinstance(geos, list) or not all(isinstance(g, str) for g in geos):
        from app.api.schemas import SchemaError

        raise SchemaError("all_geographies must be an array of geography codes")
    return tuple(geos)


def _handle_consumer(body: dict, global_cfg: dict) -> IndicatorResult:
    return consumer.calculate(
        country_headline_rates=get_mapping(body, "country_headline_rates"),
        country_weights=get_mapping(body, "country_weights"),
        all_geographies=_all_geographies(body),
        period=get_str(body, "period"),
        calculated_at=now_iso(),
        weight_method=get_str(body, "weight_method", required=False, default=global_cfg["default_weight_method"]),
        country_price_relatives=get_mapping(body, "country_price_relatives", required=False),
        global_index_previous_period=get_float(body, "global_index_previous_period", required=False),
        global_index_prior_year=get_float(body, "global_index_prior_year", required=False),
        population_by_geo=get_mapping(body, "population_by_geo", required=False),
        gdp_ppp_by_geo=get_mapping(body, "gdp_ppp_by_geo", required=False),
        consumption_ppp_by_geo=get_mapping(body, "consumption_ppp_by_geo", required=False),
    )


def _handle_median_country(body: dict, global_cfg: dict) -> IndicatorResult:
    return median_country.calculate(
        country_rates=get_mapping(body, "country_rates"),
        all_geographies=_all_geographies(body),
        period=get_str(body, "period"),
        calculated_at=now_iso(),
        country_weights=get_mapping(body, "country_weights", required=False),
        population_by_geo=get_mapping(body, "population_by_geo", required=False),
        gdp_ppp_by_geo=get_mapping(body, "gdp_ppp_by_geo", required=False),
        consumption_ppp_by_geo=get_mapping(body, "consumption_ppp_by_geo", required=False),
    )


def _handle_essential(body: dict, global_cfg: dict) -> IndicatorResult:
    return essential.calculate(
        country_essential_rates=get_mapping(body, "country_essential_rates"),
        consumption_ppp_weights=get_mapping(body, "consumption_ppp_weights"),
        all_geographies=_all_geographies(body),
        period=get_str(body, "period"),
        calculated_at=now_iso(),
        population_weights=get_mapping(body, "population_weights", required=False),
        population_by_geo=get_mapping(body, "population_by_geo", required=False),
        gdp_ppp_by_geo=get_mapping(body, "gdp_ppp_by_geo", required=False),
        consumption_ppp_by_geo=get_mapping(body, "consumption_ppp_by_geo", required=False),
    )


def _handle_monetary(body: dict, global_cfg: dict) -> IndicatorResult:
    return monetary.calculate(
        country_money_growth_rates=get_mapping(body, "country_money_growth_rates"),
        gdp_ppp_weights=get_mapping(body, "gdp_ppp_weights"),
        all_geographies=_all_geographies(body),
        period=get_str(body, "period"),
        calculated_at=now_iso(),
        consumption_ppp_weights=get_mapping(body, "consumption_ppp_weights", required=False),
        population_by_geo=get_mapping(body, "population_by_geo", required=False),
        gdp_ppp_by_geo=get_mapping(body, "gdp_ppp_by_geo", required=False),
        consumption_ppp_by_geo=get_mapping(body, "consumption_ppp_by_geo", required=False),
    )


def _handle_excess_money(body: dict, global_cfg: dict) -> IndicatorResult:
    method = get_str(body, "method", required=False, default=global_cfg["excess_money_growth"]["default_method"])
    return excess_money.calculate(
        method=method,
        all_geographies=_all_geographies(body),
        period=get_str(body, "period"),
        calculated_at=now_iso(),
        global_money_expansion_percent=get_float(body, "global_money_expansion_percent", required=False),
        global_real_gdp_growth_percent=get_float(body, "global_real_gdp_growth_percent", required=False),
        country_money_growth=get_mapping(body, "country_money_growth", required=False),
        country_real_gdp_growth=get_mapping(body, "country_real_gdp_growth", required=False),
        country_weights=get_mapping(body, "country_weights", required=False),
        country_velocity_adjusted_mp=get_mapping(body, "country_velocity_adjusted_mp", required=False),
        money_weight_basis=get_str(body, "money_weight_basis", required=False),
        gdp_weight_basis=get_str(body, "gdp_weight_basis", required=False),
        population_by_geo=get_mapping(body, "population_by_geo", required=False),
        gdp_ppp_by_geo=get_mapping(body, "gdp_ppp_by_geo", required=False),
        consumption_ppp_by_geo=get_mapping(body, "consumption_ppp_by_geo", required=False),
    )


def _handle_producer_pressure(body: dict, global_cfg: dict) -> IndicatorResult:
    return producer_pressure.calculate(
        country_ppi_rates=get_mapping(body, "country_ppi_rates"),
        gdp_ppp_weights=get_mapping(body, "gdp_ppp_weights"),
        country_import_rates=get_mapping(body, "country_import_rates"),
        import_share_weights=get_mapping(body, "import_share_weights"),
        commodity_rates=get_mapping(body, "commodity_rates"),
        commodity_weights=get_mapping(body, "commodity_weights"),
        all_geographies=_all_geographies(body),
        period=get_str(body, "period"),
        calculated_at=now_iso(),
        freight_index_current=get_float(body, "freight_index_current", required=False),
        freight_index_prior_year=get_float(body, "freight_index_prior_year", required=False),
        composite_weights=get_mapping(body, "composite_weights", required=False)
        or global_cfg["producer_pressure"]["composite_weights"],
        standardization_windows=body.get("standardization_windows"),
        population_by_geo=get_mapping(body, "population_by_geo", required=False),
        gdp_ppp_by_geo=get_mapping(body, "gdp_ppp_by_geo", required=False),
        consumption_ppp_by_geo=get_mapping(body, "consumption_ppp_by_geo", required=False),
    )


def _handle_housing_assets(body: dict, global_cfg: dict) -> IndicatorResult:
    return housing_assets.calculate(
        country_house_price_current=get_mapping(body, "country_house_price_current"),
        country_house_price_prior=get_mapping(body, "country_house_price_prior"),
        housing_weights=get_mapping(body, "housing_weights"),
        country_rent_rates=get_mapping(body, "country_rent_rates"),
        consumption_ppp_weights=get_mapping(body, "consumption_ppp_weights"),
        all_geographies=_all_geographies(body),
        period=get_str(body, "period"),
        calculated_at=now_iso(),
        equity_index_current=get_float(body, "equity_index_current", required=False),
        equity_index_prior_year=get_float(body, "equity_index_prior_year", required=False),
        asset_prices_current=body.get("asset_prices_current"),
        asset_prices_prior_year=body.get("asset_prices_prior_year"),
        asset_price_index_current=get_float(body, "asset_price_index_current", required=False),
        asset_price_index_prior_year=get_float(body, "asset_price_index_prior_year", required=False),
        income_index_current=get_float(body, "income_index_current", required=False),
        income_index_prior_year=get_float(body, "income_index_prior_year", required=False),
        population_by_geo=get_mapping(body, "population_by_geo", required=False),
        gdp_ppp_by_geo=get_mapping(body, "gdp_ppp_by_geo", required=False),
        consumption_ppp_by_geo=get_mapping(body, "consumption_ppp_by_geo", required=False),
    )


def _handle_synchronization(body: dict, global_cfg: dict) -> IndicatorResult:
    sync_cfg = global_cfg["synchronization"]
    return synchronization.calculate(
        country_rates_current=get_mapping(body, "country_rates_current"),
        threshold_percent=get_float(body, "threshold_percent", required=False, default=sync_cfg["default_threshold_percent"]),
        all_geographies=_all_geographies(body),
        period=get_str(body, "period"),
        calculated_at=now_iso(),
        country_rates_prior=get_mapping(body, "country_rates_prior", required=False),
        population_weights=get_mapping(body, "population_weights", required=False),
        composite_weights=get_mapping(body, "composite_weights", required=False) or sync_cfg["composite_weights"],
        dispersion_standardization_window=body.get("dispersion_standardization_window"),
        population_by_geo=get_mapping(body, "population_by_geo", required=False),
        gdp_ppp_by_geo=get_mapping(body, "gdp_ppp_by_geo", required=False),
        consumption_ppp_by_geo=get_mapping(body, "consumption_ppp_by_geo", required=False),
    )


HANDLERS: dict[str, Handler] = {
    consumer.INDICATOR_ID: _handle_consumer,
    median_country.INDICATOR_ID: _handle_median_country,
    essential.INDICATOR_ID: _handle_essential,
    monetary.INDICATOR_ID: _handle_monetary,
    excess_money.INDICATOR_ID: _handle_excess_money,
    producer_pressure.INDICATOR_ID: _handle_producer_pressure,
    housing_assets.INDICATOR_ID: _handle_housing_assets,
    synchronization.INDICATOR_ID: _handle_synchronization,
}
