"""Coverage for app/api/contracts.py -- the strict normalized-observation
contract every calculation endpoint enforces. This module had no dedicated
test file: it is the strictest gatekeeper in the system (356 lines of pure
validation), and several of its raise branches were previously reachable
only by reading the code, not by any test."""

import pytest

from app.api import contracts as c
from app.api.schemas import SchemaError
from app.engines.shared.errors import (
    CoverageThresholdError,
    FrequencyMismatchError,
    PeriodAlignmentError,
    UnitMismatchError,
)
from app.models.enums import Unit


def obs(
    role,
    value,
    period="2026-06",
    *,
    geography="USA",
    unit="percent_yoy",
    frequency="monthly",
    component_id=None,
    indicator_id=None,
    status="validated",
):
    return {
        "provider": "official-test",
        "source_series_id": f"SERIES:{role}:{component_id or geography}",
        "indicator_id": indicator_id or role,
        "geography": geography,
        "frequency": frequency,
        "unit": unit,
        "observation_period": period,
        "value": value,
        "retrieved_at": "2026-08-01T00:00:00Z",
        "validation_status": status,
        **({"component_id": component_id} if component_id else {}),
    }


def emg_body(**overrides):
    body = {
        "period": "2026-06",
        "inputs": {
            "money_growth_percent": [obs("money_growth_percent", 8.0)],
            "real_output_growth_percent": [obs("real_output_growth_percent", 3.0)],
        },
    }
    body.update(overrides)
    return body


def coverage_obs(role, value, *, geography, target_period="2026-06"):
    prior_year = str(int(target_period[:4]) - 1)
    unit = "persons" if role == "population_by_geo" else "local_currency"
    return obs(role, value, prior_year, geography=geography, unit=unit, frequency="annual", component_id=geography)


def median_body(*, weights, rates_geos, universe):
    inputs = {
        "country_rates": [
            obs("country_rates", 5.0, "2026-06", geography=g, unit="percent_yoy", frequency="monthly", component_id=g, indicator_id="headline_consumer_inflation")
            for g in rates_geos
        ],
        "country_weights": [obs("country_weights", w, "2025", geography=g, unit="ratio", frequency="annual", component_id=g) for g, w in weights.items()],
        "population_by_geo": [coverage_obs("population_by_geo", 100.0, geography=g) for g in universe],
        "gdp_ppp_by_geo": [coverage_obs("gdp_ppp_by_geo", 100.0, geography=g) for g in universe],
        "consumption_ppp_by_geo": [coverage_obs("consumption_ppp_by_geo", 100.0, geography=g) for g in universe],
    }
    return {"period": "2026-06", "inputs": inputs, "universe": universe}


def global_sync_body(**overrides):
    body = {
        "period": "2026-06",
        "inputs": {
            "country_rates_current": [
                obs("country_rates_current", 5.0, "2026-06", geography="USA", unit="percent_yoy", frequency="monthly", component_id="USA", indicator_id="headline_consumer_inflation"),
                obs("country_rates_current", 3.0, "2026-06", geography="EA", unit="percent_yoy", frequency="monthly", component_id="EA", indicator_id="headline_consumer_inflation"),
            ],
            "population_by_geo": [coverage_obs("population_by_geo", 300.0, geography="USA"), coverage_obs("population_by_geo", 340.0, geography="EA")],
            "gdp_ppp_by_geo": [coverage_obs("gdp_ppp_by_geo", 25000.0, geography="USA"), coverage_obs("gdp_ppp_by_geo", 17000.0, geography="EA")],
            "consumption_ppp_by_geo": [coverage_obs("consumption_ppp_by_geo", 20000.0, geography="USA"), coverage_obs("consumption_ppp_by_geo", 14000.0, geography="EA")],
        },
        "universe": ["USA", "EA"],
    }
    body.update(overrides)
    return body


class TestBodyShape:
    def test_non_dict_body_rejected(self):
        with pytest.raises(SchemaError):
            c.normalize_request("excess_money_growth", [1, 2], global_scope=False)

    def test_missing_period_rejected(self):
        with pytest.raises(SchemaError):
            c.normalize_request("excess_money_growth", {"inputs": {}}, global_scope=False)

    def test_empty_period_rejected(self):
        with pytest.raises(SchemaError):
            c.normalize_request("excess_money_growth", {"period": "", "inputs": {}}, global_scope=False)

    def test_non_string_period_rejected(self):
        with pytest.raises(SchemaError):
            c.normalize_request("excess_money_growth", {"period": 202606, "inputs": {}}, global_scope=False)

    def test_inputs_not_object_rejected(self):
        with pytest.raises(SchemaError):
            c.normalize_request("excess_money_growth", {"period": "2026-06", "inputs": [1]}, global_scope=False)


class TestRequiredAndUnknownRoles:
    def test_missing_required_role_lists_it(self):
        body = {"period": "2026-06", "inputs": {"money_growth_percent": [obs("money_growth_percent", 8.0)]}}
        with pytest.raises(SchemaError) as exc_info:
            c.normalize_request("excess_money_growth", body, global_scope=False)
        assert exc_info.value.details["missing_roles"] == ["real_output_growth_percent"]

    def test_unknown_input_role_rejected(self):
        body = emg_body()
        body["inputs"]["mystery_role"] = [obs("mystery_role", 1.0)]
        with pytest.raises(SchemaError) as exc_info:
            c.normalize_request("excess_money_growth", body, global_scope=False)
        assert exc_info.value.details["roles"] == ["mystery_role"]

    def test_empty_observation_array_rejected(self):
        body = emg_body()
        body["inputs"]["money_growth_percent"] = []
        with pytest.raises(SchemaError):
            c.normalize_request("excess_money_growth", body, global_scope=False)

    def test_non_list_observation_role_rejected(self):
        body = emg_body()
        body["inputs"]["money_growth_percent"] = "not-a-list"
        with pytest.raises(SchemaError):
            c.normalize_request("excess_money_growth", body, global_scope=False)


class TestOptions:
    def test_options_not_object_rejected(self):
        body = emg_body(options=[1, 2])
        with pytest.raises(SchemaError):
            c.normalize_request("excess_money_growth", body, global_scope=False)

    def test_unknown_option_rejected(self):
        body = emg_body(options={"bogus_option": True})
        with pytest.raises(SchemaError) as exc_info:
            c.normalize_request("excess_money_growth", body, global_scope=False)
        assert exc_info.value.details["options"] == ["bogus_option"]


class TestScalarRoleCardinality:
    def test_scalar_role_with_two_observations_rejected(self):
        body = emg_body()
        body["inputs"]["money_growth_percent"] = [
            obs("money_growth_percent", 8.0),
            obs("money_growth_percent", 9.0, "2026-07"),
        ]
        with pytest.raises(SchemaError):
            c.normalize_request("excess_money_growth", body, global_scope=False)


class TestMappingRoles:
    def test_duplicate_mapping_key_rejected(self):
        body = {
            "period": "2026-06",
            "inputs": {
                "category_rates": [
                    obs("category_rates", 4.0, component_id="food"),
                    obs("category_rates", 5.0, component_id="food"),
                ],
            },
        }
        with pytest.raises(SchemaError):
            c.normalize_request("essential_cost_inflation", body, global_scope=False)


class TestWrongIndicatorRole:
    def test_role_with_wrong_source_indicator_id_rejected(self):
        body = global_sync_body()
        body["inputs"]["country_rates_current"][0]["indicator_id"] = "broad_money_expansion"
        with pytest.raises(SchemaError) as exc_info:
            c.normalize_request("global_inflation_synchronization", body, global_scope=True)
        assert exc_info.value.details["expected_indicator_id"] == "headline_consumer_inflation"


class TestUnitAndFrequency:
    def test_wrong_unit_is_unit_mismatch(self):
        body = emg_body()
        body["inputs"]["money_growth_percent"] = [obs("money_growth_percent", 8.0, unit="index")]
        with pytest.raises(UnitMismatchError):
            c.normalize_request("excess_money_growth", body, global_scope=False)

    def test_mixed_frequencies_in_one_role_rejected(self):
        body = emg_body()
        body["inputs"]["money_growth_percent"] = [
            obs("money_growth_percent", 8.0, frequency="monthly"),
            obs("money_growth_percent", 8.5, "2026-Q2", frequency="quarterly"),
        ]
        with pytest.raises(FrequencyMismatchError):
            c.normalize_request("excess_money_growth", body, global_scope=False)

    def test_mixed_periods_without_alignment_policy_rejected(self):
        body = emg_body()
        body["inputs"]["money_growth_percent"] = [
            obs("money_growth_percent", 8.0, "2026-06"),
            obs("money_growth_percent", 8.1, "2026-07"),
        ]
        with pytest.raises(SchemaError):
            c.normalize_request("excess_money_growth", body, global_scope=False)

    def test_frequency_not_accepted_by_indicator_rejected(self):
        # underlying_inflation only accepts MONTHLY.
        body = {
            "period": "2026-Q2",
            "inputs": {
                "component_rates": [obs("component_rates", 4.0, "2026-Q2", geography="USA", frequency="quarterly", component_id="core")],
                "component_weights": [obs("component_weights", 1.0, "2025", geography="USA", unit="ratio", frequency="annual", component_id="core")],
            },
        }
        with pytest.raises(FrequencyMismatchError):
            c.normalize_request("underlying_inflation", body, global_scope=False)


class TestWeightAndCoverageRoleAlignment:
    def test_weight_role_wrong_frequency_rejected(self):
        body = median_body(weights={"USA": 1.0}, rates_geos=["USA"], universe=["USA"])
        body["inputs"]["country_weights"][0]["frequency"] = "monthly"
        body["inputs"]["country_weights"][0]["observation_period"] = "2026-06"
        with pytest.raises(FrequencyMismatchError):
            c.normalize_request("median_country_inflation", body, global_scope=True, structurally_dominant_weight=0.5)

    def test_weight_role_wrong_period_rejected(self):
        body = median_body(weights={"USA": 1.0}, rates_geos=["USA"], universe=["USA"])
        body["inputs"]["country_weights"][0]["observation_period"] = "2024"  # not the prior year of 2026-06
        with pytest.raises(PeriodAlignmentError):
            c.normalize_request("median_country_inflation", body, global_scope=True, structurally_dominant_weight=0.5)

    def test_malformed_non_year_target_period_raises_schema_error_not_value_error(self):
        body = median_body(weights={"USA": 1.0}, rates_geos=["USA"], universe=["USA"])
        body["period"] = "abcd"
        with pytest.raises(SchemaError):
            c.normalize_request("median_country_inflation", body, global_scope=True, structurally_dominant_weight=0.5)

    def test_country_money_growth_and_secondary_weights_are_normalized(self):
        body = {
            "period": "2026-Q2",
            "universe": ["USA", "EA"],
            "inputs": {
                "global_money_expansion_percent": [obs("global_money_expansion_percent", 7.0, "2026-Q2", geography="GLOBAL", frequency="quarterly")],
                "global_real_gdp_growth_percent": [obs("global_real_gdp_growth_percent", 2.5, "2026-Q2", geography="GLOBAL", frequency="quarterly")],
                "country_money_growth": [
                    obs("country_money_growth", 7.0, "2026-Q2", geography="USA", frequency="quarterly", component_id="USA", indicator_id="broad_money_expansion"),
                ],
                "country_real_gdp_growth": [
                    obs("country_real_gdp_growth", 2.0, "2026-Q2", geography="USA", frequency="quarterly", component_id="USA"),
                ],
                "country_weights": [
                    obs("country_weights", 0.9, "2025", geography="USA", unit="ratio", frequency="annual", component_id="USA"),
                    obs("country_weights", 0.1, "2025", geography="EA", unit="ratio", frequency="annual", component_id="EA"),
                ],
                "population_by_geo": [coverage_obs("population_by_geo", 90.0, geography="USA"), coverage_obs("population_by_geo", 10.0, geography="EA")],
                "gdp_ppp_by_geo": [coverage_obs("gdp_ppp_by_geo", 90.0, geography="USA"), coverage_obs("gdp_ppp_by_geo", 10.0, geography="EA")],
                "consumption_ppp_by_geo": [coverage_obs("consumption_ppp_by_geo", 90.0, geography="USA"), coverage_obs("consumption_ppp_by_geo", 10.0, geography="EA")],
            },
        }
        normalized = c.normalize_request("global_excess_money_growth", body, global_scope=True, structurally_dominant_weight=0.2)
        assert normalized.legacy["country_weights"] == pytest.approx({"USA": 1.0})


class TestCpiSeriesPeriod:
    def test_missing_requested_period_rejected(self):
        body = {
            "period": "2026-06",
            "inputs": {
                "all_items_cpi_index": [
                    obs("all_items_cpi_index", 300.0, "2025-06", unit="index"),
                    obs("all_items_cpi_index", 310.0, "2025-07", unit="index"),
                ],
            },
        }
        with pytest.raises(SchemaError):
            c.normalize_request("headline_consumer_inflation", body, global_scope=False)


class TestCurrentAndHistoricalPeriodAlignment:
    def test_current_role_at_wrong_period_rejected(self):
        body = emg_body()
        body["inputs"]["money_growth_percent"] = [obs("money_growth_percent", 8.0, "2026-05")]
        with pytest.raises(PeriodAlignmentError):
            c.normalize_request("excess_money_growth", body, global_scope=False)

    def test_prior_year_role_not_at_documented_lag_rejected(self):
        body = {
            "period": "2026-06",
            "inputs": {
                "money_current": [obs("money_current", 110.0, "2026-06", unit="local_currency")],
                "money_prior_year": [obs("money_prior_year", 100.0, "2026-01", unit="local_currency")],  # wrong lag
            },
        }
        with pytest.raises(PeriodAlignmentError):
            c.normalize_request("broad_money_expansion", body, global_scope=False)

    def test_previous_period_role_not_at_lag_one_rejected(self):
        body = {
            "period": "2026-06",
            "inputs": {
                "country_headline_rates": [obs("country_headline_rates", 5.0, "2026-06", geography="USA", frequency="monthly", component_id="USA", indicator_id="headline_consumer_inflation")],
                "country_weights": [obs("country_weights", 1.0, "2025", geography="USA", unit="ratio", frequency="annual", component_id="USA")],
                "global_index_previous_period": [obs("global_index_previous_period", 118.0, "2026-04", unit="index")],  # should be 2026-05
                "population_by_geo": [coverage_obs("population_by_geo", 100.0, geography="USA")],
                "gdp_ppp_by_geo": [coverage_obs("gdp_ppp_by_geo", 100.0, geography="USA")],
                "consumption_ppp_by_geo": [coverage_obs("consumption_ppp_by_geo", 100.0, geography="USA")],
            },
            "universe": ["USA"],
        }
        with pytest.raises(PeriodAlignmentError):
            c.normalize_request("global_consumer_inflation", body, global_scope=True, structurally_dominant_weight=0.5)


class TestGlobalUniverse:
    def test_missing_universe_rejected(self):
        body = global_sync_body()
        del body["universe"]
        with pytest.raises(SchemaError):
            c.normalize_request("global_inflation_synchronization", body, global_scope=True)

    def test_empty_universe_rejected(self):
        body = global_sync_body(universe=[])
        with pytest.raises(SchemaError):
            c.normalize_request("global_inflation_synchronization", body, global_scope=True)

    def test_non_string_universe_entries_rejected(self):
        body = global_sync_body(universe=["USA", 42])
        with pytest.raises(SchemaError):
            c.normalize_request("global_inflation_synchronization", body, global_scope=True)


class TestPrimaryWeightCoverage:
    def test_full_coverage_keeps_original_weights(self):
        body = median_body(weights={"USA": 0.6, "EA": 0.4}, rates_geos=["USA", "EA"], universe=["USA", "EA"])
        result = c.normalize_request("median_country_inflation", body, global_scope=True, structurally_dominant_weight=0.5)
        assert result.adjusted_weights == pytest.approx({"USA": 0.6, "EA": 0.4})

    def test_partial_coverage_below_threshold_renormalizes(self):
        body = median_body(weights={"USA": 0.6, "EA": 0.4}, rates_geos=["USA"], universe=["USA", "EA"])
        result = c.normalize_request("median_country_inflation", body, global_scope=True, structurally_dominant_weight=0.5)
        assert result.original_weights == pytest.approx({"USA": 0.6, "EA": 0.4})
        assert result.adjusted_weights == pytest.approx({"USA": 1.0})

    def test_missing_weight_at_or_above_dominant_threshold_raises_coverage_error(self):
        body = median_body(weights={"USA": 0.6, "EA": 0.4}, rates_geos=["USA"], universe=["USA", "EA"])
        with pytest.raises(CoverageThresholdError):
            c.normalize_request("median_country_inflation", body, global_scope=True, structurally_dominant_weight=0.3)

    def test_unconfigured_missing_weight_policy_rejected(self):
        body = median_body(weights={"USA": 0.6, "EA": 0.4}, rates_geos=["USA", "EA"], universe=["USA", "EA"])
        with pytest.raises(SchemaError):
            c.normalize_request("median_country_inflation", body, global_scope=True, structurally_dominant_weight=None)


class TestAcceptedUnitsFailsClosed:
    def test_unclassified_role_raises_instead_of_defaulting(self):
        # Every role the public contract declares is classified in
        # _accepted_units; this pins the fail-closed behavior for any
        # future role that is added to REQUIRED_ROLES/OPTIONAL_ROLES
        # without a matching branch there.
        with pytest.raises(SchemaError):
            c._accepted_units("totally_unclassified_role")


class TestContractMetadata:
    @pytest.mark.parametrize("indicator_id", list(c.REQUIRED_ROLES))
    def test_every_indicator_produces_metadata_without_raising(self, indicator_id):
        metadata = c.contract_metadata(indicator_id)
        assert metadata["required_roles"] == list(c.REQUIRED_ROLES[indicator_id])
        assert set(metadata["role_units"]) == set(metadata["required_roles"]) | set(metadata["optional_roles"])

    def test_accepted_frequencies_are_sorted_strings(self):
        metadata = c.contract_metadata("excess_money_growth")
        assert metadata["accepted_frequencies"] == sorted(metadata["accepted_frequencies"])
        assert all(isinstance(f, str) for f in metadata["accepted_frequencies"])
