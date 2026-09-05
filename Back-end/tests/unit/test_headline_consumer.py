import pytest

from app.engines.country import headline_consumer as hc
from app.engines.shared.errors import (
    DataQualityError,
    FrequencyMismatchError,
    InsufficientHistoryError,
    UnitMismatchError,
)
from app.engines.shared.periods import parse_period
from app.models.enums import Confidence, Coverage, Frequency, Unit, ValidationStatus
from app.models.observation import Observation
from app.models.series import ObservationSeries

CALCULATED_AT = "2026-08-02T12:00:00Z"


def make_obs(period, value, **overrides):
    defaults = dict(
        provider="bls",
        source_series_id="CUUR0000SA0",
        indicator_id=hc.INDICATOR_ID,
        geography="USA",
        frequency=Frequency.MONTHLY,
        unit=Unit.INDEX,
        observation_period=period,
        value=value,
        retrieved_at=CALCULATED_AT,
        validation_status=ValidationStatus.VALIDATED,
    )
    defaults.update(overrides)
    return Observation(**defaults)


def monthly_series(base=300.0, months=16, monthly_growth=0.003, start="2025-03"):
    """Build a series of `months` consecutive monthly observations."""

    year, month = (int(x) for x in start.split("-"))
    obs = []
    value = base
    for i in range(months):
        m = ((month - 1 + i) % 12) + 1
        y = year + (month - 1 + i) // 12
        obs.append(make_obs(f"{y:04d}-{m:02d}", round(value, 6)))
        value *= 1 + monthly_growth
    return ObservationSeries(obs)


class TestNormalCalculation:
    def test_yoy_matches_manual_formula(self):
        series = monthly_series()
        period = parse_period("2026-06", Frequency.MONTHLY)
        result = hc.calculate(series, period, calculated_at=CALCULATED_AT)
        current = series.get_at(period).value
        prior = series.get_at(parse_period("2025-06", Frequency.MONTHLY)).value
        expected = (current / prior - 1) * 100
        assert result.value == pytest.approx(expected)
        assert result.unit == Unit.PERCENT_YOY
        assert result.indicator_id == hc.INDICATOR_ID
        assert result.geography == "USA"
        assert result.coverage == Coverage.FULL

    def test_result_has_all_13_required_fields(self):
        series = monthly_series()
        period = parse_period("2026-06", Frequency.MONTHLY)
        result = hc.calculate(series, period, calculated_at=CALCULATED_AT)
        d = result.to_dict()
        for field in [
            "indicator_id", "geography", "period", "value", "unit", "method",
            "methodology_version", "input_series", "coverage", "confidence",
            "is_estimated", "warnings", "calculated_at",
        ]:
            assert field in d

    def test_momentum_components_present(self):
        series = monthly_series()
        period = parse_period("2026-06", Frequency.MONTHLY)
        result = hc.calculate(series, period, calculated_at=CALCULATED_AT)
        keys = {c.key for c in result.components}
        assert "mom" in keys
        assert "three_month_annualized" in keys
        assert "six_month_annualized" in keys
        six_m = next(c for c in result.components if c.key == "six_month_annualized")
        assert six_m.value is not None
        assert six_m.unit == Unit.PERCENT_ANNUALIZED

    def test_provenance_recorded(self):
        series = monthly_series()
        period = parse_period("2026-06", Frequency.MONTHLY)
        result = hc.calculate(series, period, calculated_at=CALCULATED_AT)
        assert len(result.input_series) == 1
        assert result.input_series[0].provider == "bls"


class TestZeroGrowth:
    def test_flat_series_yields_zero_yoy(self):
        obs = [make_obs(f"2025-{m:02d}", 100.0) for m in range(1, 13)]
        obs += [make_obs(f"2026-{m:02d}", 100.0) for m in range(1, 7)]
        series = ObservationSeries(obs)
        period = parse_period("2026-06", Frequency.MONTHLY)
        result = hc.calculate(series, period, calculated_at=CALCULATED_AT)
        assert result.value == pytest.approx(0.0)


class TestDeflation:
    def test_negative_growth(self):
        series = monthly_series(monthly_growth=-0.002)
        period = parse_period("2026-06", Frequency.MONTHLY)
        result = hc.calculate(series, period, calculated_at=CALCULATED_AT)
        assert result.value < 0


class TestExtremeInflation:
    def test_hyperinflation_case(self):
        series = monthly_series(monthly_growth=0.30)  # ~30% monthly
        period = parse_period("2026-06", Frequency.MONTHLY)
        result = hc.calculate(series, period, calculated_at=CALCULATED_AT)
        assert result.value > 1000


class TestMissingHistory:
    def test_insufficient_yoy_history_raises(self):
        obs = [make_obs(f"2026-{m:02d}", 300.0 + m) for m in range(1, 7)]
        series = ObservationSeries(obs)
        period = parse_period("2026-06", Frequency.MONTHLY)
        with pytest.raises(InsufficientHistoryError):
            hc.calculate(series, period, calculated_at=CALCULATED_AT)

    def test_current_period_missing_raises(self):
        series = monthly_series()
        missing_period = parse_period("2027-01", Frequency.MONTHLY)
        with pytest.raises(Exception):
            hc.calculate(series, missing_period, calculated_at=CALCULATED_AT)

    def test_momentum_unavailable_when_three_month_history_missing(self):
        # Only current, prior-month (for MoM), and prior-year (for YoY)
        # exist; prior-3-months (needed for the annualized momentum view)
        # is deliberately absent.
        obs = [
            make_obs("2025-01", 300.0),  # YoY lag (12 months back)
            make_obs("2025-12", 308.0),  # MoM lag (1 month back)
            make_obs("2026-01", 310.0),  # current
        ]
        series = ObservationSeries(obs)
        period = parse_period("2026-01", Frequency.MONTHLY)
        result = hc.calculate(series, period, calculated_at=CALCULATED_AT)
        mom = next(c for c in result.components if c.key == "mom")
        assert mom.value is not None
        three_m = next(c for c in result.components if c.key == "three_month_annualized")
        assert three_m.value is None
        assert any("three_month_annualized unavailable" in w for w in result.warnings)
        six_m = next(c for c in result.components if c.key == "six_month_annualized")
        assert six_m.value is None
        assert any("six_month_annualized unavailable" in w for w in result.warnings)


class TestInvalidUnit:
    def test_percent_yoy_input_rejected(self):
        obs = [make_obs(f"2025-{m:02d}", 3.0, unit=Unit.PERCENT_YOY) for m in range(1, 13)]
        obs += [make_obs(f"2026-{m:02d}", 3.0, unit=Unit.PERCENT_YOY) for m in range(1, 7)]
        series = ObservationSeries(obs)
        period = parse_period("2026-06", Frequency.MONTHLY)
        with pytest.raises(UnitMismatchError):
            hc.calculate(series, period, calculated_at=CALCULATED_AT)


class TestInvalidFrequency:
    def test_weekly_frequency_rejected(self):
        obs = [
            make_obs(f"2026-W{w:02d}", 100.0 + w, frequency=Frequency.WEEKLY)
            for w in range(1, 10)
        ]
        series = ObservationSeries(obs)
        period = parse_period("2026-W05", Frequency.WEEKLY)
        with pytest.raises(FrequencyMismatchError):
            hc.calculate(series, period, calculated_at=CALCULATED_AT)


class TestZeroOrNegativeIndex:
    def test_zero_index_current_raises(self):
        obs = [make_obs(f"2025-{m:02d}", 300.0) for m in range(1, 13)]
        obs.append(make_obs("2026-01", 0.0))
        series = ObservationSeries(obs)
        period = parse_period("2026-01", Frequency.MONTHLY)
        with pytest.raises(DataQualityError):
            hc.calculate(series, period, calculated_at=CALCULATED_AT)

    def test_negative_index_prior_raises(self):
        obs = [make_obs(f"2025-{m:02d}", -50.0) for m in range(1, 13)]
        obs.append(make_obs("2026-01", 300.0))
        series = ObservationSeries(obs)
        period = parse_period("2026-01", Frequency.MONTHLY)
        with pytest.raises(DataQualityError):
            hc.calculate(series, period, calculated_at=CALCULATED_AT)


class TestPartialCoverageAndConfidence:
    def test_estimated_observation_lowers_confidence(self):
        obs = [make_obs(f"2025-{m:02d}", 300.0) for m in range(1, 13)]
        obs.append(make_obs("2026-01", 310.0, is_estimated=True))
        series = ObservationSeries(obs)
        period = parse_period("2026-01", Frequency.MONTHLY)
        result = hc.calculate(series, period, calculated_at=CALCULATED_AT)
        assert result.confidence == Confidence.LOW
        assert result.is_estimated is True

    def test_gap_in_series_is_disclosed_as_warning(self):
        # Gap at 2025-06 does not coincide with any period required to
        # compute 2026-08 (current, -1, -3, -12), so calculation still
        # succeeds, but the gap must still be disclosed as a warning.
        obs = [make_obs(f"2025-{m:02d}", 300.0) for m in range(1, 13) if m != 6]
        obs += [make_obs(f"2026-{m:02d}", 305.0 + m) for m in range(1, 9)]
        series = ObservationSeries(obs)
        period = parse_period("2026-08", Frequency.MONTHLY)
        result = hc.calculate(series, period, calculated_at=CALCULATED_AT)
        assert any("gaps" in w for w in result.warnings)


class TestQuarterlyFrequency:
    def test_quarterly_yoy_uses_lag_4(self):
        obs = [
            make_obs(f"{y}-Q{q}", value, frequency=Frequency.QUARTERLY)
            for y, value in [(2024, 100.0), (2025, 103.0)]
            for q in range(1, 5)
        ]
        series = ObservationSeries(obs)
        period = parse_period("2025-Q1", Frequency.QUARTERLY)
        result = hc.calculate(series, period, calculated_at=CALCULATED_AT)
        assert result.value == pytest.approx(3.0)
        # three/six-month annualized momentum is monthly-only, must be absent
        assert not any(c.key == "three_month_annualized" for c in result.components)
        assert not any(c.key == "six_month_annualized" for c in result.components)
