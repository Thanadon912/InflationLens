import pytest

from app.engines.shared.errors import (
    FrequencyMismatchError,
    InsufficientHistoryError,
    InvalidWeightError,
    MissingRequiredInputError,
    PeriodAlignmentError,
    UnitMismatchError,
)
from app.engines.shared.periods import parse_period
from app.engines.shared.validation import (
    require_lagged_observation,
    require_observation_at,
    validate_frequency,
    validate_period_alignment,
    validate_positive_index,
    validate_unit,
    validate_weights,
)
from app.models.enums import Frequency, Unit, ValidationStatus
from app.models.observation import Observation
from app.models.series import ObservationSeries


def make_obs(period: str, value: float, frequency=Frequency.MONTHLY, unit=Unit.INDEX):
    return Observation(
        provider="bls",
        source_series_id="CUUR0000SA0",
        indicator_id="headline_consumer_inflation",
        geography="USA",
        frequency=frequency,
        unit=unit,
        observation_period=period,
        value=value,
        retrieved_at="2026-08-02T12:00:00Z",
        validation_status=ValidationStatus.VALIDATED,
    )


class TestValidateUnit:
    def test_accepted_unit_passes(self):
        validate_unit(Unit.INDEX, [Unit.INDEX], indicator_id="x")

    def test_rejected_unit_raises(self):
        with pytest.raises(UnitMismatchError) as exc_info:
            validate_unit(Unit.PERCENT_YOY, [Unit.INDEX], indicator_id="headline_consumer_inflation")
        assert exc_info.value.details["expected"] == "index"
        assert exc_info.value.details["received"] == "percent_yoy"


class TestValidateFrequency:
    def test_match_passes(self):
        validate_frequency(Frequency.MONTHLY, Frequency.MONTHLY, indicator_id="x")

    def test_mismatch_raises(self):
        with pytest.raises(FrequencyMismatchError):
            validate_frequency(Frequency.QUARTERLY, Frequency.MONTHLY, indicator_id="x")


class TestValidatePeriodAlignment:
    def test_same_period_passes(self):
        a = parse_period("2026-06", Frequency.MONTHLY)
        b = parse_period("2026-06", Frequency.MONTHLY)
        validate_period_alignment(a, b, context="test")

    def test_different_period_raises(self):
        a = parse_period("2026-06", Frequency.MONTHLY)
        b = parse_period("2026-Q1", Frequency.QUARTERLY)
        with pytest.raises(PeriodAlignmentError):
            validate_period_alignment(a, b, context="test")

    def test_same_frequency_different_value_raises(self):
        a = parse_period("2026-06", Frequency.MONTHLY)
        b = parse_period("2026-05", Frequency.MONTHLY)
        with pytest.raises(PeriodAlignmentError):
            validate_period_alignment(a, b, context="money vs gdp")


class TestValidateWeights:
    def test_valid_mapping_passes(self):
        validate_weights({"a": 0.5, "b": 0.5})

    def test_valid_list_passes(self):
        validate_weights([0.3, 0.3, 0.4])

    def test_empty_raises(self):
        with pytest.raises(InvalidWeightError):
            validate_weights({})

    def test_negative_weight_raises(self):
        with pytest.raises(InvalidWeightError):
            validate_weights({"a": 1.5, "b": -0.5})

    def test_sum_not_one_raises(self):
        with pytest.raises(InvalidWeightError):
            validate_weights({"a": 0.5, "b": 0.6})

    def test_within_tolerance_passes(self):
        validate_weights({"a": 0.5, "b": 0.5 + 1e-9})


class TestValidatePositiveIndex:
    def test_positive_passes(self):
        validate_positive_index(100.0, context="cpi")

    def test_zero_raises(self):
        from app.engines.shared.errors import DataQualityError

        with pytest.raises(DataQualityError):
            validate_positive_index(0.0, context="cpi")

    def test_negative_raises(self):
        from app.engines.shared.errors import DataQualityError

        with pytest.raises(DataQualityError):
            validate_positive_index(-5.0, context="cpi")


class TestRequireObservationAt:
    def test_present_returns_observation(self):
        series = ObservationSeries([make_obs("2026-06", 100.0)])
        period = parse_period("2026-06", Frequency.MONTHLY)
        obs = require_observation_at(series, period, context="test")
        assert obs.value == 100.0

    def test_missing_raises(self):
        series = ObservationSeries([make_obs("2026-06", 100.0)])
        period = parse_period("2026-07", Frequency.MONTHLY)
        with pytest.raises(MissingRequiredInputError):
            require_observation_at(series, period, context="test")


class TestRequireLaggedObservation:
    def test_sufficient_history_returns_observation(self):
        series = ObservationSeries(
            [make_obs("2025-06", 95.0), make_obs("2026-06", 100.0)]
        )
        reference = parse_period("2026-06", Frequency.MONTHLY)
        obs = require_lagged_observation(series, reference, 12, context="yoy")
        assert obs.value == 95.0

    def test_insufficient_history_raises(self):
        series = ObservationSeries([make_obs("2026-06", 100.0)])
        reference = parse_period("2026-06", Frequency.MONTHLY)
        with pytest.raises(InsufficientHistoryError):
            require_lagged_observation(series, reference, 12, context="yoy")
