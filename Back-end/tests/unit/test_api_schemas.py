import pytest

from app.api.schemas import (
    SchemaError,
    get_float,
    get_mapping,
    get_str,
    normalize_string_sequence,
    parse_observation,
    parse_observation_series,
    parse_period_field,
    require,
)
from app.models.enums import Frequency

VALID_OBS = {
    "provider": "bls",
    "source_series_id": "CUUR0000SA0",
    "indicator_id": "headline_consumer_inflation",
    "geography": "USA",
    "frequency": "monthly",
    "unit": "index",
    "observation_period": "2026-06",
    "value": 321.5,
    "retrieved_at": "2026-08-02T12:00:00Z",
    "validation_status": "validated",
}


class TestRequire:
    def test_present_returns_value(self):
        assert require({"a": 1}, "a") == 1

    def test_missing_raises(self):
        with pytest.raises(SchemaError):
            require({}, "a")

    def test_none_value_raises(self):
        with pytest.raises(SchemaError):
            require({"a": None}, "a")


class TestGetFloat:
    def test_present(self):
        assert get_float({"a": 3.2}, "a") == 3.2

    def test_int_coerced_to_float(self):
        assert get_float({"a": 3}, "a") == 3.0

    def test_missing_required_raises(self):
        with pytest.raises(SchemaError):
            get_float({}, "a")

    def test_missing_optional_returns_default(self):
        assert get_float({}, "a", required=False, default=5.0) == 5.0

    def test_missing_optional_no_default_returns_none(self):
        assert get_float({}, "a", required=False) is None

    def test_bool_rejected(self):
        with pytest.raises(SchemaError):
            get_float({"a": True}, "a")

    def test_string_rejected(self):
        with pytest.raises(SchemaError):
            get_float({"a": "3.2"}, "a")


class TestGetStr:
    def test_present(self):
        assert get_str({"a": "x"}, "a") == "x"

    def test_missing_required_raises(self):
        with pytest.raises(SchemaError):
            get_str({}, "a")

    def test_missing_optional_returns_default(self):
        assert get_str({}, "a", required=False, default="d") == "d"

    def test_non_string_rejected(self):
        with pytest.raises(SchemaError):
            get_str({"a": 5}, "a")


class TestGetMapping:
    def test_present(self):
        assert get_mapping({"a": {"x": 1, "y": 2}}, "a") == {"x": 1.0, "y": 2.0}

    def test_missing_required_raises(self):
        with pytest.raises(SchemaError):
            get_mapping({}, "a")

    def test_missing_optional_returns_none(self):
        assert get_mapping({}, "a", required=False) is None

    def test_non_dict_rejected(self):
        with pytest.raises(SchemaError):
            get_mapping({"a": [1, 2]}, "a")

    def test_non_numeric_value_rejected(self):
        with pytest.raises(SchemaError):
            get_mapping({"a": {"x": "not a number"}}, "a")

    def test_bool_value_rejected(self):
        with pytest.raises(SchemaError):
            get_mapping({"a": {"x": True}}, "a")


class TestParsePeriodField:
    def test_valid(self):
        p = parse_period_field({"period": "2026-06"}, "period", Frequency.MONTHLY)
        assert p.raw == "2026-06"

    def test_invalid_format_raises_schema_error(self):
        with pytest.raises(SchemaError):
            parse_period_field({"period": "not-a-period"}, "period", Frequency.MONTHLY)


class TestParseObservation:
    def test_valid(self):
        obs = parse_observation(VALID_OBS)
        assert obs.value == 321.5

    def test_not_a_mapping_raises(self):
        with pytest.raises(SchemaError):
            parse_observation("not a dict")

    def test_missing_field_raises(self):
        bad = dict(VALID_OBS)
        del bad["provider"]
        with pytest.raises(SchemaError):
            parse_observation(bad)

    def test_invalid_frequency_enum_raises(self):
        bad = dict(VALID_OBS, frequency="fortnightly")
        with pytest.raises(SchemaError):
            parse_observation(bad)

    def test_invalid_unit_enum_raises(self):
        bad = dict(VALID_OBS, unit="bushels")
        with pytest.raises(SchemaError):
            parse_observation(bad)

    def test_optional_confidence_parsed(self):
        obs = parse_observation(dict(VALID_OBS, confidence="high"))
        assert obs.confidence.value == "high"

    def test_optional_coverage_status_parsed(self):
        obs = parse_observation(dict(VALID_OBS, coverage_status="partial"))
        assert obs.coverage_status.value == "partial"

    def test_invalid_confidence_raises(self):
        with pytest.raises(SchemaError):
            parse_observation(dict(VALID_OBS, confidence="super_high"))

    def test_underlying_construction_error_wrapped_as_schema_error(self):
        # A well-shaped but invalid numeric value is a domain error (HTTP 422).
        bad = dict(VALID_OBS, value=float("nan"))
        from app.engines.shared.errors import DataQualityError
        with pytest.raises(DataQualityError):
            parse_observation(bad)


class TestParseObservationSeries:
    def test_valid(self):
        series = parse_observation_series([VALID_OBS])
        assert len(series) == 1

    def test_not_a_list_raises(self):
        with pytest.raises(SchemaError):
            parse_observation_series({"not": "a list"})

    def test_empty_list_raises(self):
        with pytest.raises(SchemaError):
            parse_observation_series([])

    def test_duplicate_periods_raises_schema_error(self):
        with pytest.raises(SchemaError):
            parse_observation_series([VALID_OBS, VALID_OBS])


class TestNormalizeStringSequence:
    def test_none_returns_empty_tuple(self):
        assert normalize_string_sequence(None) == ()

    def test_empty_string_returns_empty_tuple(self):
        assert normalize_string_sequence("") == ()
        assert normalize_string_sequence("   ") == ()

    def test_single_string_wrapped_as_single_element_tuple(self):
        assert normalize_string_sequence("food") == ("food",)
        assert normalize_string_sequence("  food  ") == ("food",)

    def test_sequence_of_strings_returns_clean_tuple(self):
        assert normalize_string_sequence(["food", "energy"]) == ("food", "energy")
        assert normalize_string_sequence(("food", "energy")) == ("food", "energy")

    def test_sequence_filters_empty_and_whitespace(self):
        assert normalize_string_sequence(["food", "", "  ", None, "energy"]) == ("food", "energy")

    def test_other_types_return_empty_tuple(self):
        assert normalize_string_sequence(123) == ()
        assert normalize_string_sequence({}) == ()

