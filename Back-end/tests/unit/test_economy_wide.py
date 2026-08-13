import pytest

from app.engines.country import economy_wide as ew
from app.engines.shared.errors import DataQualityError
from app.models.enums import Coverage

CALCULATED_AT = "2026-08-02T12:00:00Z"


class TestGdpDeflator:
    def test_matches_manual_formula(self):
        assert ew.gdp_deflator(2600.0, 2500.0) == pytest.approx((2600.0 / 2500.0) * 100)

    def test_zero_real_gdp_raises(self):
        with pytest.raises(DataQualityError):
            ew.gdp_deflator(2600.0, 0.0)

    def test_negative_real_gdp_raises(self):
        with pytest.raises(DataQualityError):
            ew.gdp_deflator(2600.0, -100.0)


class TestCalculate:
    def test_value_and_unit_always_none(self):
        result = ew.calculate(
            nominal_gdp_current=26000.0, real_gdp_current=25000.0,
            nominal_gdp_prior_year=24500.0, real_gdp_prior_year=24000.0,
            geography="USA", period="2026-Q2", calculated_at=CALCULATED_AT,
        )
        assert result.value is None
        assert result.unit is None

    def test_gdp_deflator_component_matches_manual_computation(self):
        result = ew.calculate(
            nominal_gdp_current=26000.0, real_gdp_current=25000.0,
            nominal_gdp_prior_year=24500.0, real_gdp_prior_year=24000.0,
            geography="USA", period="2026-Q2", calculated_at=CALCULATED_AT,
        )
        deflator_t = (26000.0 / 25000.0) * 100
        deflator_t4 = (24500.0 / 24000.0) * 100
        expected = (deflator_t / deflator_t4 - 1) * 100
        comp = next(c for c in result.components if c.key == "gdp_deflator_inflation")
        assert comp.value == pytest.approx(expected)

    def test_both_deflators_present_and_not_averaged(self):
        result = ew.calculate(
            nominal_gdp_current=26000.0, real_gdp_current=25000.0,
            nominal_gdp_prior_year=24500.0, real_gdp_prior_year=24000.0,
            geography="USA", period="2026-Q2", calculated_at=CALCULATED_AT,
            nominal_domestic_demand_current=27000.0, real_domestic_demand_current=25500.0,
            nominal_domestic_demand_prior_year=25500.0, real_domestic_demand_prior_year=24800.0,
        )
        gdp = next(c for c in result.components if c.key == "gdp_deflator_inflation")
        dd = next(c for c in result.components if c.key == "domestic_demand_deflator_inflation")
        assert gdp.value != pytest.approx(dd.value)
        assert result.coverage == Coverage.FULL

    def test_missing_dd_data_marks_partial(self):
        result = ew.calculate(
            nominal_gdp_current=26000.0, real_gdp_current=25000.0,
            nominal_gdp_prior_year=24500.0, real_gdp_prior_year=24000.0,
            geography="USA", period="2026-Q2", calculated_at=CALCULATED_AT,
        )
        assert result.coverage == Coverage.PARTIAL
        assert not any(c.key == "domestic_demand_deflator_inflation" for c in result.components)

    def test_zero_growth(self):
        result = ew.calculate(
            nominal_gdp_current=25000.0, real_gdp_current=25000.0,
            nominal_gdp_prior_year=25000.0, real_gdp_prior_year=25000.0,
            geography="USA", period="2026-Q2", calculated_at=CALCULATED_AT,
        )
        gdp = next(c for c in result.components if c.key == "gdp_deflator_inflation")
        assert gdp.value == pytest.approx(0.0)

    def test_deflation_case(self):
        result = ew.calculate(
            nominal_gdp_current=24000.0, real_gdp_current=25000.0,
            nominal_gdp_prior_year=25000.0, real_gdp_prior_year=24000.0,
            geography="USA", period="2026-Q2", calculated_at=CALCULATED_AT,
        )
        gdp = next(c for c in result.components if c.key == "gdp_deflator_inflation")
        assert gdp.value < 0
