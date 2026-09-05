import pytest

from app.engines.country import excess_money as em
from app.engines.shared.errors import PeriodAlignmentError
from app.engines.shared.periods import parse_period
from app.models.enums import Coverage, Frequency

CALCULATED_AT = "2026-08-02T12:00:00Z"


class TestSimpleEMG:
    def test_matches_manual_formula(self):
        q = parse_period("2026-Q2", Frequency.QUARTERLY)
        result = em.calculate(
            money_growth_percent=8.0, real_output_growth_percent=3.0,
            money_period=q, real_output_period=q,
            geography="USA", period="2026-Q2", calculated_at=CALCULATED_AT,
        )
        assert result.value == pytest.approx(5.0)

    def test_negative_emg_when_output_outpaces_money(self):
        q = parse_period("2026-Q2", Frequency.QUARTERLY)
        result = em.calculate(
            money_growth_percent=2.0, real_output_growth_percent=5.0,
            money_period=q, real_output_period=q,
            geography="USA", period="2026-Q2", calculated_at=CALCULATED_AT,
        )
        assert result.value < 0

    def test_zero_emg(self):
        q = parse_period("2026-Q2", Frequency.QUARTERLY)
        result = em.calculate(
            money_growth_percent=3.0, real_output_growth_percent=3.0,
            money_period=q, real_output_period=q,
            geography="USA", period="2026-Q2", calculated_at=CALCULATED_AT,
        )
        assert result.value == pytest.approx(0.0)

    def test_mismatched_periods_raise(self):
        monthly = parse_period("2026-06", Frequency.MONTHLY)
        quarterly = parse_period("2026-Q1", Frequency.QUARTERLY)
        with pytest.raises(PeriodAlignmentError):
            em.calculate(
                money_growth_percent=8.0, real_output_growth_percent=3.0,
                money_period=monthly, real_output_period=quarterly,
                geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            )

    def test_different_quarters_same_frequency_raise(self):
        q1 = parse_period("2026-Q1", Frequency.QUARTERLY)
        q2 = parse_period("2026-Q2", Frequency.QUARTERLY)
        with pytest.raises(PeriodAlignmentError):
            em.calculate(
                money_growth_percent=8.0, real_output_growth_percent=3.0,
                money_period=q1, real_output_period=q2,
                geography="USA", period="2026-Q1", calculated_at=CALCULATED_AT,
            )


class TestVelocityAdjusted:
    def test_matches_manual_formula(self):
        q = parse_period("2026-Q2", Frequency.QUARTERLY)
        result = em.calculate(
            money_growth_percent=8.0, real_output_growth_percent=3.0,
            money_period=q, real_output_period=q,
            geography="USA", period="2026-Q2", calculated_at=CALCULATED_AT,
            nominal_gdp_current=26000.0, nominal_gdp_prior=24500.0,
            money_current=21500.0, money_prior=20000.0,
        )
        v_current = 26000.0 / 21500.0
        v_prior = 24500.0 / 20000.0
        g_v = (v_current / v_prior - 1) * 100
        expected_mp = 8.0 + g_v - 3.0
        mp = next(c for c in result.components if c.key == "velocity_adjusted_monetary_pressure")
        assert mp.value == pytest.approx(expected_mp)
        assert result.coverage == Coverage.FULL

    def test_missing_velocity_inputs_marks_partial(self):
        q = parse_period("2026-Q2", Frequency.QUARTERLY)
        result = em.calculate(
            money_growth_percent=8.0, real_output_growth_percent=3.0,
            money_period=q, real_output_period=q,
            geography="USA", period="2026-Q2", calculated_at=CALCULATED_AT,
        )
        assert result.coverage == Coverage.PARTIAL
        assert not any(c.key == "velocity_adjusted_monetary_pressure" for c in result.components)

    def test_zero_money_current_is_engine_error_not_zero_division(self):
        q = parse_period("2026-Q2", Frequency.QUARTERLY)
        result = em.calculate(
            money_growth_percent=8.0, real_output_growth_percent=3.0,
            money_period=q, real_output_period=q,
            geography="USA", period="2026-Q2", calculated_at=CALCULATED_AT,
            nominal_gdp_current=26000.0, nominal_gdp_prior=24500.0,
            money_current=0.0, money_prior=20000.0,
        )
        # Must degrade to a warning like the missing-inputs case, never raise
        # a bare ZeroDivisionError past the engine boundary.
        assert not any(c.key == "velocity_adjusted_monetary_pressure" for c in result.components)
        assert any("velocity_adjusted_monetary_pressure unavailable" in w for w in result.warnings)

    def test_zero_money_prior_is_engine_error_not_zero_division(self):
        q = parse_period("2026-Q2", Frequency.QUARTERLY)
        result = em.calculate(
            money_growth_percent=8.0, real_output_growth_percent=3.0,
            money_period=q, real_output_period=q,
            geography="USA", period="2026-Q2", calculated_at=CALCULATED_AT,
            nominal_gdp_current=26000.0, nominal_gdp_prior=24500.0,
            money_current=21500.0, money_prior=0.0,
        )
        assert not any(c.key == "velocity_adjusted_monetary_pressure" for c in result.components)
        assert any("velocity_adjusted_monetary_pressure unavailable" in w for w in result.warnings)
