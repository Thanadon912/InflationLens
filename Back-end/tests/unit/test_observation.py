import math

import pytest

from app.engines.shared.errors import DataQualityError, SeriesDefinitionError
from app.models.enums import Frequency, Unit, ValidationStatus
from app.models.observation import Observation


def make_obs(**overrides):
    defaults = dict(
        provider="bls",
        source_series_id="CUUR0000SA0",
        indicator_id="headline_consumer_inflation",
        geography="USA",
        frequency=Frequency.MONTHLY,
        unit=Unit.INDEX,
        observation_period="2026-06",
        value=321.5,
        retrieved_at="2026-08-02T12:00:00Z",
        validation_status=ValidationStatus.VALIDATED,
    )
    defaults.update(overrides)
    return Observation(**defaults)


class TestObservationConstruction:
    def test_valid_observation_constructs(self):
        obs = make_obs()
        assert obs.value == 321.5
        assert obs.period.raw == "2026-06"

    def test_optional_fields_default(self):
        obs = make_obs()
        assert obs.publication_date is None
        assert obs.is_estimated is False
        assert obs.is_revised is False
        assert obs.confidence is None

    def test_is_frozen(self):
        obs = make_obs()
        with pytest.raises(Exception):
            obs.value = 999.0

    def test_non_finite_value_raises(self):
        with pytest.raises(DataQualityError):
            make_obs(value=math.nan)
        with pytest.raises(DataQualityError):
            make_obs(value=math.inf)

    def test_non_numeric_value_raises(self):
        with pytest.raises(DataQualityError):
            make_obs(value="not a number")

    def test_bool_value_raises(self):
        # bool is a subclass of int in Python; must be explicitly rejected
        with pytest.raises(DataQualityError):
            make_obs(value=True)

    def test_empty_provider_raises(self):
        with pytest.raises(SeriesDefinitionError):
            make_obs(provider="")

    def test_empty_series_id_raises(self):
        with pytest.raises(SeriesDefinitionError):
            make_obs(source_series_id="")

    def test_empty_geography_raises(self):
        with pytest.raises(SeriesDefinitionError):
            make_obs(geography="")

    def test_malformed_period_raises(self):
        with pytest.raises(SeriesDefinitionError):
            make_obs(observation_period="not-a-period")

    def test_period_frequency_mismatch_raises(self):
        with pytest.raises(SeriesDefinitionError):
            make_obs(observation_period="2026-Q1", frequency=Frequency.MONTHLY)

    def test_negative_value_allowed_at_observation_level(self):
        # Index positivity is a validation-layer concern (see
        # validate_positive_index), not a universal observation-level
        # constraint, since e.g. a growth-rate observation can be negative.
        obs = make_obs(unit=Unit.PERCENT_YOY, value=-3.2)
        assert obs.value == -3.2

    def test_zero_value_allowed_at_observation_level(self):
        obs = make_obs(unit=Unit.PERCENT_YOY, value=0.0)
        assert obs.value == 0.0
