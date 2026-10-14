"""Strict, normalized request contract for every calculation endpoint.

The public API never forwards anonymous numbers to an engine.  Each input
role contains one or more normalized observations, and this module performs
the mechanical conversion to the argument names used by the pure engines.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.api.schemas import SchemaError, parse_observation
from app.engines.shared.periods import parse_period
from app.engines.shared.errors import FrequencyMismatchError, PeriodAlignmentError, UnitMismatchError
from app.engines.shared.quality import build_provenance, derive_confidence
from app.engines.shared.coverage import renormalize_weights
from app.engines.shared.errors import CoverageThresholdError
from app.engines.shared.validation import validate_weights
from app.models.enums import Confidence, Frequency, Unit
from app.models.methodology import InputProvenance
from app.models.observation import Observation


# Public input roles. Required roles deliberately mirror the smallest set
# needed to produce each indicator's documented primary output.
REQUIRED_ROLES: dict[str, tuple[str, ...]] = {
    "headline_consumer_inflation": ("all_items_cpi_index",),
    "underlying_inflation": ("component_rates", "component_weights"),
    "essential_cost_inflation": ("category_rates",),
    "fixed_lifestyle_inflation": ("prices_current", "prices_prior_year", "prices_base", "quantities_base"),
    "housing_inflation": ("rent_index_current", "rent_index_prior_year", "house_price_index_current", "house_price_index_prior_year"),
    "broad_money_expansion": ("money_current", "money_prior_year"),
    "excess_money_growth": ("money_growth_percent", "real_output_growth_percent"),
    "producer_import_inflation": ("ppi_current", "ppi_prior_year", "import_price_current", "import_price_prior_year", "energy_inflation_percent", "commodity_inflation_percent"),
    "economy_wide_inflation": ("nominal_gdp_current", "real_gdp_current", "nominal_gdp_prior_year", "real_gdp_prior_year"),
    "purchasing_power_squeeze": ("nominal_wage_growth_percent", "headline_inflation_percent", "essential_inflation_percent"),
    "global_consumer_inflation": ("country_headline_rates", "country_weights"),
    "median_country_inflation": ("country_rates",),
    "global_essential_inflation": ("country_essential_rates", "consumption_ppp_weights"),
    "global_monetary_expansion": ("country_money_growth_rates", "gdp_ppp_weights"),
    "global_excess_money_growth": ("global_money_expansion_percent", "global_real_gdp_growth_percent"),
    "global_producer_pressure": ("country_ppi_rates", "gdp_ppp_weights", "country_import_rates", "import_share_weights", "commodity_rates", "commodity_weights"),
    "global_housing_asset_inflation": ("country_house_price_current", "country_house_price_prior", "housing_weights", "country_rent_rates", "consumption_ppp_weights"),
    "global_inflation_synchronization": ("country_rates_current",),
}

MAPPING_ROLES = {
    "component_rates", "component_weights", "category_rates", "prices_current",
    "prices_prior_year", "prices_base", "quantities_base", "package_sizes_current",
    "package_sizes_base", "country_headline_rates",
    "quality_adjusted_prices_current",
    "country_weights", "country_price_relatives", "country_rates", "population_by_geo",
    "gdp_ppp_by_geo", "consumption_ppp_by_geo", "country_essential_rates",
    "consumption_ppp_weights", "population_weights", "country_money_growth_rates",
    "gdp_ppp_weights", "country_money_growth", "country_real_gdp_growth",
    "country_velocity_adjusted_mp", "country_ppi_rates", "country_import_rates",
    "import_share_weights", "commodity_rates", "commodity_weights",
    "country_house_price_current", "country_house_price_prior", "housing_weights",
    "country_rent_rates", "country_rates_current", "country_rates_prior",
}

OPTIONAL_ROLES: dict[str, set[str]] = {
    "underlying_inflation": {"official_core_value"},
    "fixed_lifestyle_inflation": {"package_sizes_current", "package_sizes_base", "quality_adjusted_prices_current"},
    "housing_inflation": {"property_price_current", "property_price_prior_year", "mortgage_rate_current", "mortgage_rate_prior_year", "monthly_housing_cost", "monthly_disposable_income"},
    "broad_money_expansion": {"population_current", "population_prior_year", "real_gdp_current", "real_gdp_prior_year"},
    "excess_money_growth": {"nominal_gdp_current", "nominal_gdp_prior", "money_current", "money_prior"},
    "producer_import_inflation": {"foreign_price_growth_percent", "exchange_rate_growth_percent"},
    "economy_wide_inflation": {"nominal_domestic_demand_current", "real_domestic_demand_current", "nominal_domestic_demand_prior_year", "real_domestic_demand_prior_year"},
    "purchasing_power_squeeze": {"disposable_income_growth_percent"},
    "global_consumer_inflation": {"country_price_relatives", "global_index_previous_period", "global_index_prior_year", "population_by_geo", "gdp_ppp_by_geo", "consumption_ppp_by_geo"},
    "median_country_inflation": {"country_weights", "population_by_geo", "gdp_ppp_by_geo", "consumption_ppp_by_geo"},
    "global_essential_inflation": {"population_weights", "population_by_geo", "gdp_ppp_by_geo", "consumption_ppp_by_geo"},
    "global_monetary_expansion": {"consumption_ppp_weights", "population_by_geo", "gdp_ppp_by_geo", "consumption_ppp_by_geo"},
    "global_excess_money_growth": {"country_money_growth", "country_real_gdp_growth", "country_weights", "country_velocity_adjusted_mp", "population_by_geo", "gdp_ppp_by_geo", "consumption_ppp_by_geo"},
    "global_producer_pressure": {"freight_index_current", "freight_index_prior_year", "population_by_geo", "gdp_ppp_by_geo", "consumption_ppp_by_geo"},
    "global_housing_asset_inflation": {"equity_index_current", "equity_index_prior_year", "asset_price_index_current", "asset_price_index_prior_year", "income_index_current", "income_index_prior_year", "population_by_geo", "gdp_ppp_by_geo", "consumption_ppp_by_geo"},
    "global_inflation_synchronization": {"country_rates_prior", "population_weights", "population_by_geo", "gdp_ppp_by_geo", "consumption_ppp_by_geo"},
}

WEIGHT_ROLES = {role for role in MAPPING_ROLES if "weight" in role}
RATE_ROLES = {
    role for roles in REQUIRED_ROLES.values() for role in roles
    if "rate" in role or "growth" in role or "inflation_percent" in role
} | {
    "country_rates_prior", "country_velocity_adjusted_mp", "energy_inflation_percent",
    "commodity_inflation_percent", "foreign_price_growth_percent",
    "exchange_rate_growth_percent", "disposable_income_growth_percent",
    "global_money_expansion_percent", "official_core_value",
}
INDEX_ROLES = {role for roles in REQUIRED_ROLES.values() for role in roles if "index" in role or "ppi_" in role}

OPTION_KEYS: dict[str, set[str]] = {
    "fixed_lifestyle_inflation": {"replacements"},
    "housing_inflation": {"standardization_windows"},
    "producer_import_inflation": {"upp_standardization_window"},
    "global_producer_pressure": {"standardization_windows"},
    "global_housing_asset_inflation": {"asset_prices_current", "asset_prices_prior_year"},
    "global_inflation_synchronization": {"threshold_percent", "dispersion_standardization_window"},
}

ACCEPTED_FREQUENCIES = {
    "headline_consumer_inflation": {Frequency.MONTHLY, Frequency.QUARTERLY, Frequency.ANNUAL},
    "underlying_inflation": {Frequency.MONTHLY},
    "essential_cost_inflation": {Frequency.MONTHLY},
    "fixed_lifestyle_inflation": {Frequency.MONTHLY},
    "housing_inflation": {Frequency.MONTHLY, Frequency.QUARTERLY},
    "broad_money_expansion": {Frequency.MONTHLY, Frequency.QUARTERLY},
    "excess_money_growth": {Frequency.MONTHLY, Frequency.QUARTERLY, Frequency.ANNUAL},
    "producer_import_inflation": {Frequency.MONTHLY},
    "economy_wide_inflation": {Frequency.QUARTERLY, Frequency.ANNUAL},
    "purchasing_power_squeeze": {Frequency.MONTHLY, Frequency.QUARTERLY, Frequency.ANNUAL},
    "global_consumer_inflation": {Frequency.MONTHLY, Frequency.QUARTERLY},
    "median_country_inflation": {Frequency.MONTHLY, Frequency.QUARTERLY},
    "global_essential_inflation": {Frequency.MONTHLY},
    "global_monetary_expansion": {Frequency.MONTHLY, Frequency.QUARTERLY},
    "global_excess_money_growth": {Frequency.QUARTERLY, Frequency.ANNUAL},
    "global_producer_pressure": {Frequency.MONTHLY},
    "global_housing_asset_inflation": {Frequency.QUARTERLY},
    "global_inflation_synchronization": {Frequency.MONTHLY},
}

COVERAGE_MEASURE_ROLES = {"population_by_geo", "gdp_ppp_by_geo", "consumption_ppp_by_geo"}
EXPECTED_INDICATOR_IDS = {
    "country_headline_rates": "headline_consumer_inflation",
    "country_rates": "headline_consumer_inflation",
    "country_rates_current": "headline_consumer_inflation",
    "country_rates_prior": "headline_consumer_inflation",
    "country_essential_rates": "essential_cost_inflation",
    "country_money_growth_rates": "broad_money_expansion",
    "country_money_growth": "broad_money_expansion",
}


@dataclass(frozen=True)
class NormalizedPayload:
    legacy: dict[str, Any]
    observations: tuple[Observation, ...]
    input_series: tuple[InputProvenance, ...]
    confidence: Confidence
    original_weights: Mapping[str, float] | None = None
    adjusted_weights: Mapping[str, float] | None = None


PRIMARY_WEIGHT_PAIR = {
    "global_consumer_inflation": ("country_weights", "country_headline_rates"),
    "median_country_inflation": ("country_weights", "country_rates"),
    "global_essential_inflation": ("consumption_ppp_weights", "country_essential_rates"),
    "global_monetary_expansion": ("gdp_ppp_weights", "country_money_growth_rates"),
    "global_excess_money_growth": ("country_weights", "country_money_growth"),
    "global_producer_pressure": ("gdp_ppp_weights", "country_ppi_rates"),
    "global_housing_asset_inflation": ("housing_weights", "country_house_price_current"),
    "global_inflation_synchronization": ("population_weights", "country_rates_current"),
}


def normalize_request(
    indicator_id: str,
    body: Mapping[str, Any],
    *,
    global_scope: bool = False,
    structurally_dominant_weight: float | None = None,
) -> NormalizedPayload:
    if not isinstance(body, Mapping):
        raise SchemaError("Request body must be a JSON object")
    period = body.get("period")
    if not isinstance(period, str) or not period:
        raise SchemaError("Field 'period' must be a non-empty string", field="period")
    inputs = body.get("inputs")
    if not isinstance(inputs, Mapping):
        raise SchemaError("Field 'inputs' must be an object of normalized-observation arrays", field="inputs")

    required_roles = set(REQUIRED_ROLES[indicator_id])
    original_weights = adjusted_weights = None
    if global_scope:
        required_roles.update({"population_by_geo", "gdp_ppp_by_geo", "consumption_ppp_by_geo"})
    missing = [role for role in sorted(required_roles) if role not in inputs]
    if missing:
        raise SchemaError("Missing required input roles", missing_roles=missing)
    unknown_roles = set(inputs) - set(REQUIRED_ROLES[indicator_id]) - OPTIONAL_ROLES.get(indicator_id, set())
    if unknown_roles:
        raise SchemaError("Unsupported input roles for indicator", roles=sorted(unknown_roles))

    options = body.get("options", {})
    if not isinstance(options, Mapping):
        raise SchemaError("Field 'options' must be an object", field="options")
    unknown_options = set(options) - OPTION_KEYS.get(indicator_id, set())
    if unknown_options:
        raise SchemaError("Unsupported options for indicator", options=sorted(unknown_options))

    legacy: dict[str, Any] = {"period": period, **options}
    all_observations: list[Observation] = []
    for role, raw_items in inputs.items():
        if not isinstance(role, str) or not isinstance(raw_items, list) or not raw_items:
            raise SchemaError("Each input role must be a non-empty observation array", role=role)
        observations = [parse_observation(raw) for raw in raw_items]
        _validate_role(indicator_id, role, observations, period)
        all_observations.extend(observations)
        if indicator_id == "headline_consumer_inflation" and role == "all_items_cpi_index":
            legacy["observations"] = raw_items
        elif role in MAPPING_ROLES:
            legacy[role] = _as_mapping(role, observations)
        elif len(observations) == 1:
            legacy[role] = observations[0].value
        else:
            raise SchemaError("Scalar input role must contain exactly one observation", role=role)

    pair = PRIMARY_WEIGHT_PAIR.get(indicator_id)
    if pair and pair[0] in legacy and pair[1] in legacy:
        weight_role, value_role = pair
        original_weights = dict(legacy[weight_role])
        validate_weights(original_weights, context=f"{indicator_id}.{weight_role}")
        available = set(legacy[value_role])
        missing_weight = sum(value for key, value in original_weights.items() if key not in available)
        if structurally_dominant_weight is None:
            raise SchemaError("Global missing-weight policy is not configured")
        if missing_weight >= structurally_dominant_weight:
            raise CoverageThresholdError(
                f"{indicator_id}: missing geographies are structurally dominant",
                missing_weight=missing_weight,
            )
        adjusted_weights = renormalize_weights(original_weights, available)
        legacy[weight_role] = adjusted_weights

    if global_scope:
        universe = body.get("universe")
        if not isinstance(universe, list) or not universe or not all(isinstance(g, str) and g for g in universe):
            raise SchemaError("Global requests require a non-empty string array 'universe'", field="universe")
        legacy["all_geographies"] = universe

    # Excess-money periods come from the two validated rate observations.
    if indicator_id == "excess_money_growth":
        money_obs = _one(inputs, "money_growth_percent")
        output_obs = _one(inputs, "real_output_growth_percent")
        legacy.update({
            "money_period": money_obs.observation_period,
            "money_frequency": money_obs.frequency.value,
            "real_output_period": output_obs.observation_period,
            "real_output_frequency": output_obs.frequency.value,
        })

    obs_tuple = tuple(all_observations)
    return NormalizedPayload(
        legacy=legacy,
        observations=obs_tuple,
        input_series=build_provenance(*obs_tuple),
        confidence=derive_confidence(*obs_tuple),
        original_weights=original_weights,
        adjusted_weights=adjusted_weights,
    )


def _one(inputs: Mapping[str, Any], role: str) -> Observation:
    raw = inputs[role]
    if len(raw) != 1:
        raise SchemaError("Scalar input role must contain exactly one observation", role=role)
    return parse_observation(raw[0])


def _as_mapping(role: str, observations: list[Observation]) -> dict[str, float]:
    result: dict[str, float] = {}
    for obs in observations:
        key = obs.component_id or obs.geography
        if key in result:
            raise SchemaError("Duplicate mapping key in input role", role=role, key=key)
        result[key] = obs.value
    return result


def _validate_role(indicator_id: str, role: str, observations: list[Observation], target_period: str) -> None:
    expected_indicator = EXPECTED_INDICATOR_IDS.get(role)
    if expected_indicator and any(obs.indicator_id != expected_indicator for obs in observations):
        raise SchemaError(
            "Input role contains observations from the wrong normalized indicator",
            role=role,
            expected_indicator_id=expected_indicator,
            received=sorted({obs.indicator_id for obs in observations}),
        )
    accepted = _accepted_units(role)
    bad = [obs.unit.value for obs in observations if obs.unit not in accepted]
    if bad:
        raise UnitMismatchError(expected=", ".join(sorted(u.value for u in accepted)), received=", ".join(bad), indicator=role)

    frequencies = {obs.frequency for obs in observations}
    if len(frequencies) != 1:
        raise FrequencyMismatchError(expected="one declared frequency", received=", ".join(sorted(f.value for f in frequencies)), indicator=role)
    periods = {obs.observation_period for obs in observations}
    if len(periods) != 1 and role != "all_items_cpi_index":
        raise SchemaError("Input role mixes periods without an alignment policy", role=role)

    if role in WEIGHT_ROLES or role in COVERAGE_MEASURE_ROLES:
        if frequencies != {Frequency.ANNUAL}:
            raise FrequencyMismatchError(expected="annual lagged measure", received=", ".join(sorted(f.value for f in frequencies)), indicator=role)
        expected_period = str(int(target_period[:4]) - 1)
        if periods != {expected_period}:
            raise PeriodAlignmentError("Global weights and coverage measures must use the previous annual period", role=role, expected=expected_period, received=sorted(periods))
        return

    if role == "all_items_cpi_index":
        if target_period not in periods:
            raise SchemaError("CPI series does not include the requested period", role=role, expected=target_period)
        return

    if not frequencies.issubset(ACCEPTED_FREQUENCIES[indicator_id]):
        raise FrequencyMismatchError(expected=", ".join(sorted(f.value for f in ACCEPTED_FREQUENCIES[indicator_id])), received=", ".join(sorted(f.value for f in frequencies)), indicator=indicator_id)

    # Current/rate roles refer to the requested economic period. Historical
    # comparison, base-basket and lagged-weight roles disclose their own lag.
    historical = role.endswith(("_prior", "_prior_year", "_base", "_previous_period"))
    if not historical and next(iter(periods)) != target_period:
        raise PeriodAlignmentError("Input role period does not match requested period", role=role, expected=target_period, received=next(iter(periods)))
    # Parse both to reject malformed periods even for roles whose lag is
    # intentionally preserved rather than silently aligned.
    freq = next(iter(frequencies))
    actual = parse_period(next(iter(periods)), freq)
    if role.endswith(("_prior", "_prior_year")):
        from app.engines.shared.periods import yoy_lag
        expected = parse_period(target_period, freq).shift(-yoy_lag(freq))
        if actual.sort_key != expected.sort_key:
            raise PeriodAlignmentError("Historical input is not at the documented year-over-year lag", role=role, expected=expected.raw, received=actual.raw)
    elif role.endswith("_previous_period"):
        expected = parse_period(target_period, freq).shift(-1)
        if actual.sort_key != expected.sort_key:
            raise PeriodAlignmentError("Historical input is not at the previous native period", role=role, expected=expected.raw, received=actual.raw)


def _accepted_units(role: str) -> set[Unit]:
    if role in WEIGHT_ROLES:
        return {Unit.RATIO, Unit.SHARE_PERCENT}
    if role in RATE_ROLES:
        return {Unit.PERCENT_YOY}
    if "population" in role:
        return {Unit.PERSONS}
    if "quantit" in role or "package_size" in role or "price_relative" in role or role == "mortgage_rate_current" or role == "mortgage_rate_prior_year":
        return {Unit.RATIO}
    if role in INDEX_ROLES or "index" in role or "price" in role:
        return {Unit.INDEX, Unit.CURRENCY, Unit.LOCAL_CURRENCY, Unit.CURRENCY_PER_UNIT}
    if any(token in role for token in ("money", "gdp", "income", "cost", "wage", "demand", "consumption_ppp")):
        return {Unit.CURRENCY, Unit.LOCAL_CURRENCY}
    # Every public role is classified above. Raising here makes additions
    # fail closed until their documented unit policy is declared.
    raise SchemaError("Input role has no declared unit policy", role=role)


def contract_metadata(indicator_id: str) -> dict[str, object]:
    roles = sorted(set(REQUIRED_ROLES[indicator_id]) | OPTIONAL_ROLES.get(indicator_id, set()))
    return {
        "contract_version": "2.0.0",
        "required_roles": list(REQUIRED_ROLES[indicator_id]),
        "optional_roles": sorted(OPTIONAL_ROLES.get(indicator_id, set())),
        "allowed_options": sorted(OPTION_KEYS.get(indicator_id, set())),
        "accepted_frequencies": sorted(f.value for f in ACCEPTED_FREQUENCIES[indicator_id]),
        "role_units": {role: sorted(unit.value for unit in _accepted_units(role)) for role in roles},
        "global_weight_period_policy": "previous_annual_period",
    }
