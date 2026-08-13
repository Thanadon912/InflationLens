import pytest

from app.engines.shared.errors import SeriesDefinitionError
from app.engines.shared.periods import parse_period
from app.models.enums import Frequency, Unit, ValidationStatus
from app.models.observation import Observation
from app.models.series import ObservationSeries


def make_obs(period: str, value: float, **overrides):
    defaults = dict(
        provider="bls",
        source_series_id="CUUR0000SA0",
        indicator_id="headline_consumer_inflation",
        geography="USA",
        frequency=Frequency.MONTHLY,
        unit=Unit.INDEX,
        observation_period=period,
        value=value,
        retrieved_at="2026-08-02T12:00:00Z",
        validation_status=ValidationStatus.VALIDATED,
    )
    defaults.update(overrides)
    return Observation(**defaults)


class TestConstruction:
    def test_sorts_by_period(self):
        series = ObservationSeries(
            [make_obs("2026-03", 3.0), make_obs("2026-01", 1.0), make_obs("2026-02", 2.0)]
        )
        assert series.periods() == ["2026-01", "2026-02", "2026-03"]

    def test_empty_raises(self):
        with pytest.raises(SeriesDefinitionError):
            ObservationSeries([])

    def test_duplicate_period_raises(self):
        with pytest.raises(SeriesDefinitionError):
            ObservationSeries([make_obs("2026-01", 1.0), make_obs("2026-01", 2.0)])

    def test_mixed_indicator_raises(self):
        with pytest.raises(SeriesDefinitionError):
            ObservationSeries(
                [make_obs("2026-01", 1.0), make_obs("2026-02", 2.0, indicator_id="other")]
            )

    def test_mixed_geography_raises(self):
        with pytest.raises(SeriesDefinitionError):
            ObservationSeries(
                [make_obs("2026-01", 1.0), make_obs("2026-02", 2.0, geography="EA")]
            )

    def test_mixed_frequency_raises(self):
        with pytest.raises(SeriesDefinitionError):
            ObservationSeries(
                [
                    make_obs("2026-01", 1.0),
                    make_obs("2026-Q1", 2.0, frequency=Frequency.QUARTERLY),
                ]
            )

    def test_mixed_unit_raises(self):
        with pytest.raises(SeriesDefinitionError):
            ObservationSeries(
                [make_obs("2026-01", 1.0), make_obs("2026-02", 2.0, unit=Unit.PERCENT_YOY)]
            )


class TestAccess:
    def test_latest_and_earliest(self):
        series = ObservationSeries(
            [make_obs("2026-01", 1.0), make_obs("2026-03", 3.0), make_obs("2026-02", 2.0)]
        )
        assert series.latest.observation_period == "2026-03"
        assert series.earliest.observation_period == "2026-01"

    def test_len_and_iter(self):
        series = ObservationSeries([make_obs("2026-01", 1.0), make_obs("2026-02", 2.0)])
        assert len(series) == 2
        assert [o.value for o in series] == [1.0, 2.0]

    def test_get_at_present(self):
        series = ObservationSeries([make_obs("2026-06", 100.0)])
        period = parse_period("2026-06", Frequency.MONTHLY)
        assert series.get_at(period).value == 100.0

    def test_get_at_missing_returns_none(self):
        series = ObservationSeries([make_obs("2026-06", 100.0)])
        period = parse_period("2026-07", Frequency.MONTHLY)
        assert series.get_at(period) is None

    def test_get_lagged(self):
        series = ObservationSeries([make_obs("2025-06", 95.0), make_obs("2026-06", 100.0)])
        reference = parse_period("2026-06", Frequency.MONTHLY)
        assert series.get_lagged(reference, 12).value == 95.0

    def test_get_lagged_insufficient_history_returns_none(self):
        series = ObservationSeries([make_obs("2026-06", 100.0)])
        reference = parse_period("2026-06", Frequency.MONTHLY)
        assert series.get_lagged(reference, 12) is None


class TestGaps:
    def test_no_gaps_for_continuous_series(self):
        series = ObservationSeries(
            [make_obs("2026-01", 1.0), make_obs("2026-02", 2.0), make_obs("2026-03", 3.0)]
        )
        assert series.gaps() == []
        assert series.has_gaps() is False

    def test_detects_single_gap(self):
        series = ObservationSeries([make_obs("2026-01", 1.0), make_obs("2026-03", 3.0)])
        gaps = series.gaps()
        assert len(gaps) == 1
        assert gaps[0].raw == "2026-02"
        assert series.has_gaps() is True

    def test_detects_multiple_gaps(self):
        series = ObservationSeries([make_obs("2026-01", 1.0), make_obs("2026-05", 5.0)])
        gaps = [g.raw for g in series.gaps()]
        assert gaps == ["2026-02", "2026-03", "2026-04"]

    def test_two_adjacent_observations_no_gap(self):
        series = ObservationSeries([make_obs("2026-01", 1.0), make_obs("2026-02", 2.0)])
        assert series.gaps() == []

    def test_single_observation_no_gap(self):
        series = ObservationSeries([make_obs("2026-01", 1.0)])
        assert series.gaps() == []
