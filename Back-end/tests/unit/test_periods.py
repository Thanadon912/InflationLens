import pytest

from app.engines.shared.errors import SeriesDefinitionError, UnsupportedMethodError
from app.engines.shared.periods import parse_period, periods_per_year, yoy_lag
from app.models.enums import Frequency


class TestParsePeriod:
    def test_monthly(self):
        p = parse_period("2026-06", Frequency.MONTHLY)
        assert p.raw == "2026-06"
        assert p.frequency == Frequency.MONTHLY

    def test_quarterly(self):
        p = parse_period("2026-Q2", Frequency.QUARTERLY)
        assert p.raw == "2026-Q2"

    def test_annual(self):
        p = parse_period("2026", Frequency.ANNUAL)
        assert p.raw == "2026"

    def test_daily(self):
        p = parse_period("2026-06-15", Frequency.DAILY)
        assert p.raw == "2026-06-15"

    def test_weekly(self):
        p = parse_period("2026-W24", Frequency.WEEKLY)
        assert p.raw == "2026-W24"

    @pytest.mark.parametrize(
        "raw,freq",
        [
            ("2026/06", Frequency.MONTHLY),
            ("2026-13", Frequency.MONTHLY),
            ("2026-Q5", Frequency.QUARTERLY),
            ("2026-Q0", Frequency.QUARTERLY),
            ("26", Frequency.ANNUAL),
            ("2026-02-30", Frequency.DAILY),  # invalid calendar date
            ("2026-W99", Frequency.WEEKLY),
        ],
    )
    def test_invalid_formats_raise(self, raw, freq):
        with pytest.raises(SeriesDefinitionError):
            parse_period(raw, freq)


class TestOrderingAndShift:
    def test_monthly_ordering(self):
        a = parse_period("2026-01", Frequency.MONTHLY)
        b = parse_period("2026-02", Frequency.MONTHLY)
        assert a < b

    def test_monthly_shift_forward_across_year(self):
        p = parse_period("2026-11", Frequency.MONTHLY)
        assert p.shift(3).raw == "2027-02"

    def test_monthly_shift_backward_across_year(self):
        p = parse_period("2026-02", Frequency.MONTHLY)
        assert p.shift(-3).raw == "2025-11"

    def test_monthly_shift_yoy_lag(self):
        p = parse_period("2026-06", Frequency.MONTHLY)
        assert p.shift(-12).raw == "2025-06"

    def test_quarterly_shift(self):
        p = parse_period("2026-Q1", Frequency.QUARTERLY)
        assert p.shift(-4).raw == "2025-Q1"
        assert p.shift(1).raw == "2026-Q2"

    def test_quarterly_shift_across_year_boundary(self):
        p = parse_period("2026-Q1", Frequency.QUARTERLY)
        assert p.shift(-1).raw == "2025-Q4"

    def test_annual_shift(self):
        p = parse_period("2026", Frequency.ANNUAL)
        assert p.shift(-1).raw == "2025"

    def test_daily_shift(self):
        p = parse_period("2026-01-01", Frequency.DAILY)
        assert p.shift(-1).raw == "2025-12-31"

    def test_weekly_shift(self):
        p = parse_period("2026-W01", Frequency.WEEKLY)
        shifted = p.shift(1)
        assert shifted.frequency == Frequency.WEEKLY

    def test_shift_is_pure_and_returns_new_object(self):
        p = parse_period("2026-06", Frequency.MONTHLY)
        p2 = p.shift(1)
        assert p.raw == "2026-06"
        assert p2.raw == "2026-07"
        assert p is not p2


class TestYoyLagAndPeriodsPerYear:
    def test_monthly_lag_is_12(self):
        assert yoy_lag(Frequency.MONTHLY) == 12

    def test_quarterly_lag_is_4(self):
        assert yoy_lag(Frequency.QUARTERLY) == 4

    def test_annual_lag_is_1(self):
        assert yoy_lag(Frequency.ANNUAL) == 1

    @pytest.mark.parametrize("freq", [Frequency.DAILY, Frequency.WEEKLY])
    def test_undocumented_lag_raises(self, freq):
        with pytest.raises(UnsupportedMethodError):
            yoy_lag(freq)

    def test_periods_per_year_monthly(self):
        assert periods_per_year(Frequency.MONTHLY) == 12

    def test_periods_per_year_quarterly(self):
        assert periods_per_year(Frequency.QUARTERLY) == 4
