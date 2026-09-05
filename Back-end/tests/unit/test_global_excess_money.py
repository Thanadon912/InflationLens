import pytest

from app.engines.global_ import excess_money as gem
from app.engines.shared.errors import InvalidWeightError, MissingRequiredInputError, UnsupportedMethodError

CALCULATED_AT = "2026-08-02T12:00:00Z"


class TestAggregateFirst:
    def test_matches_manual_subtraction(self):
        result = gem.calculate(
            method="aggregate_first",
            all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT,
            global_money_expansion_percent=7.0, global_real_gdp_growth_percent=2.5,
        )
        assert result.value == pytest.approx(4.5)
        assert result.metadata["selected_method"] == "aggregate_first"

    def test_missing_inputs_raises(self):
        with pytest.raises(MissingRequiredInputError):
            gem.calculate(method="aggregate_first", all_geographies=(), period="p", calculated_at=CALCULATED_AT)


class TestCountryFirst:
    def test_matches_manual_weighted_sum(self):
        result = gem.calculate(
            method="country_first",
            all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT,
            country_money_growth={"USA": 7.0, "EA": 5.0},
            country_real_gdp_growth={"USA": 2.0, "EA": 1.0},
            country_weights={"USA": 0.5, "EA": 0.5},
        )
        expected = 0.5 * (7.0 - 2.0) + 0.5 * (5.0 - 1.0)
        assert result.value == pytest.approx(expected)

    def test_missing_inputs_raises(self):
        with pytest.raises(MissingRequiredInputError):
            gem.calculate(method="country_first", all_geographies=(), period="p", calculated_at=CALCULATED_AT)

    def test_unsupported_method_raises(self):
        with pytest.raises(UnsupportedMethodError):
            gem.calculate(method="nonsense", all_geographies=(), period="p", calculated_at=CALCULATED_AT)


class TestVelocityAdjusted:
    def test_global_velocity_adjusted_pressure_present(self):
        result = gem.calculate(
            method="aggregate_first",
            all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT,
            global_money_expansion_percent=7.0, global_real_gdp_growth_percent=2.5,
            country_velocity_adjusted_mp={"USA": 3.0, "EA": 2.0},
            country_weights={"USA": 0.5, "EA": 0.5},
        )
        gmp = next(c for c in result.components if c.key == "global_velocity_adjusted_pressure")
        assert gmp.value == pytest.approx(2.5)


class TestWeightBasisConsistency:
    def test_mismatched_weight_basis_warns(self):
        result = gem.calculate(
            method="aggregate_first",
            all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT,
            global_money_expansion_percent=7.0, global_real_gdp_growth_percent=2.5,
            money_weight_basis="gdp_ppp", gdp_weight_basis="consumption_ppp",
        )
        assert any("weight basis" in w for w in result.warnings)

    def test_matching_weight_basis_no_warning(self):
        result = gem.calculate(
            method="aggregate_first",
            all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT,
            global_money_expansion_percent=7.0, global_real_gdp_growth_percent=2.5,
            money_weight_basis="gdp_ppp", gdp_weight_basis="gdp_ppp",
        )
        assert result.warnings == ()


class TestInvalidWeights:
    def test_negative_country_weight_raises(self):
        with pytest.raises(InvalidWeightError):
            gem.calculate(
                method="country_first",
                all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT,
                country_money_growth={"USA": 7.0, "EA": 5.0},
                country_real_gdp_growth={"USA": 2.0, "EA": 1.0},
                country_weights={"USA": 1.2, "EA": -0.2},
            )

    def test_partial_coverage_across_country_first_inputs_raises(self):
        # Regression-documenting: country_weights covering a country absent
        # from country_money_growth/country_real_gdp_growth is not
        # renormalized over the intersection today, so the surviving
        # weights (which no longer sum to 1) are rejected outright rather
        # than silently averaged over a smaller set.
        with pytest.raises(InvalidWeightError):
            gem.calculate(
                method="country_first",
                all_geographies=("USA", "EA", "JPN"), period="p", calculated_at=CALCULATED_AT,
                country_money_growth={"USA": 7.0, "EA": 5.0},
                country_real_gdp_growth={"USA": 2.0, "EA": 1.0},
                country_weights={"USA": 0.5, "EA": 0.3, "JPN": 0.2},
            )

    def test_velocity_adjusted_component_with_bad_weights_raises(self):
        with pytest.raises(InvalidWeightError):
            gem.calculate(
                method="aggregate_first",
                all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT,
                global_money_expansion_percent=7.0, global_real_gdp_growth_percent=2.5,
                country_velocity_adjusted_mp={"USA": 3.0, "EA": 2.0},
                country_weights={"USA": 0.9, "EA": 0.9},
            )
