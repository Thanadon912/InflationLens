import pytest

from app.engines.global_ import producer_pressure as gpp
from app.engines.shared.errors import InvalidWeightError
from app.models.enums import Coverage

CALCULATED_AT = "2026-08-02T12:00:00Z"


def base_kwargs(**overrides):
    defaults = dict(
        country_ppi_rates={"USA": 5.0, "EA": 3.0},
        gdp_ppp_weights={"USA": 0.5, "EA": 0.5},
        country_import_rates={"USA": 6.0, "EA": 4.0},
        import_share_weights={"USA": 0.6, "EA": 0.4},
        commodity_rates={"oil": 10.0, "metals": 2.0},
        commodity_weights={"oil": 0.7, "metals": 0.3},
        all_geographies=("USA", "EA"),
        period="2026-06",
        calculated_at=CALCULATED_AT,
    )
    defaults.update(overrides)
    return defaults


class TestComponents:
    def test_value_and_unit_always_none(self):
        result = gpp.calculate(**base_kwargs())
        assert result.value is None
        assert result.unit is None

    def test_ppi_component_matches_manual(self):
        result = gpp.calculate(**base_kwargs())
        ppi = next(c for c in result.components if c.key == "ppi_component")
        assert ppi.value == pytest.approx(0.5 * 5.0 + 0.5 * 3.0)

    def test_import_component_matches_manual(self):
        result = gpp.calculate(**base_kwargs())
        imp = next(c for c in result.components if c.key == "import_component")
        assert imp.value == pytest.approx(0.6 * 6.0 + 0.4 * 4.0)

    def test_commodity_component_matches_manual(self):
        result = gpp.calculate(**base_kwargs())
        commodity = next(c for c in result.components if c.key == "commodity_component")
        assert commodity.value == pytest.approx(0.7 * 10.0 + 0.3 * 2.0)

    def test_logistics_missing_marks_partial(self):
        result = gpp.calculate(**base_kwargs())
        assert result.coverage == Coverage.PARTIAL
        assert not any(c.key == "logistics_component" for c in result.components)

    def test_logistics_present_when_freight_given(self):
        result = gpp.calculate(**base_kwargs(freight_index_current=120.0, freight_index_prior_year=100.0))
        logistics = next(c for c in result.components if c.key == "logistics_component")
        assert logistics.value == pytest.approx(20.0)
        assert result.coverage == Coverage.FULL


class TestCompositeScore:
    def test_composite_is_marked_as_score(self):
        windows = {
            "ppi": [1.0, 2.0, 3.0, 4.0, 5.0],
            "import": [2.0, 3.0, 4.0, 5.0, 6.0],
            "commodity": [3.0, 5.0, 7.0, 9.0, 11.0],
            "logistics": [5.0, 10.0, 15.0, 20.0, 25.0],
        }
        weights = {"ppi": 0.3, "import": 0.25, "commodity": 0.25, "logistics": 0.2}
        result = gpp.calculate(
            **base_kwargs(
                freight_index_current=120.0,
                freight_index_prior_year=100.0,
                composite_weights=weights,
                standardization_windows=windows,
            )
        )
        score = next(c for c in result.components if c.key == "composite_pressure_score")
        assert score.is_score is True
        assert score.unit.value == "standard_deviation_score"

    def test_no_composite_without_logistics(self):
        weights = {"ppi": 0.3, "import": 0.25, "commodity": 0.25, "logistics": 0.2}
        windows = {"ppi": [1.0, 2.0, 3.0]}
        result = gpp.calculate(**base_kwargs(composite_weights=weights, standardization_windows=windows))
        assert not any(c.key == "composite_pressure_score" for c in result.components)


class TestInvalidWeights:
    def test_ppi_weights_not_summing_to_one_raises(self):
        with pytest.raises(InvalidWeightError):
            gpp.calculate(**base_kwargs(gdp_ppp_weights={"USA": 0.5, "EA": 0.9}))

    def test_commodity_weight_key_mismatch_raises(self):
        with pytest.raises(InvalidWeightError):
            gpp.calculate(**base_kwargs(commodity_weights={"oil": 0.7, "gas": 0.3}))

    def test_negative_import_share_weight_raises(self):
        with pytest.raises(InvalidWeightError):
            gpp.calculate(**base_kwargs(import_share_weights={"USA": 1.2, "EA": -0.2}))


class TestCompositeScoreDegradesGracefully:
    def test_insufficient_standardization_window_omits_score_with_warning(self):
        # A window with fewer than 2 historical values can't produce a
        # z-score; the composite must degrade to a warning, never raise
        # past the calculate() boundary.
        windows = {
            "ppi": [1.0],  # too short
            "import": [2.0, 3.0, 4.0],
            "commodity": [3.0, 5.0, 7.0],
            "logistics": [5.0, 10.0, 15.0],
        }
        weights = {"ppi": 0.3, "import": 0.25, "commodity": 0.25, "logistics": 0.2}
        result = gpp.calculate(
            **base_kwargs(
                freight_index_current=120.0, freight_index_prior_year=100.0,
                composite_weights=weights, standardization_windows=windows,
            )
        )
        assert not any(c.key == "composite_pressure_score" for c in result.components)
        assert any("composite_pressure_score unavailable" in w for w in result.warnings)
