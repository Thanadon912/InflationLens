import pytest

from app.engines.shared.errors import (
    CoverageThresholdError,
    DataQualityError,
    EngineError,
    FrequencyMismatchError,
    InsufficientHistoryError,
    InvalidWeightError,
    MissingRequiredInputError,
    PeriodAlignmentError,
    SeriesDefinitionError,
    UnitMismatchError,
    UnsupportedMethodError,
)

ALL_ERRORS = [
    UnitMismatchError,
    FrequencyMismatchError,
    PeriodAlignmentError,
    InsufficientHistoryError,
    InvalidWeightError,
    CoverageThresholdError,
    MissingRequiredInputError,
    UnsupportedMethodError,
    SeriesDefinitionError,
    DataQualityError,
]


def test_all_ten_errors_exist_and_are_engine_errors():
    assert len(ALL_ERRORS) == 10
    for cls in ALL_ERRORS:
        assert issubclass(cls, EngineError)
        assert issubclass(cls, Exception)


def test_each_error_has_a_unique_stable_code():
    codes = {cls.code for cls in ALL_ERRORS}
    assert len(codes) == len(ALL_ERRORS)


def test_unit_mismatch_error_structured_payload():
    err = UnitMismatchError(expected="index", received="percent_yoy", indicator="headline_consumer_inflation")
    d = err.to_dict()
    assert d["code"] == "UNIT_MISMATCH"
    assert d["details"]["expected"] == "index"
    assert d["details"]["received"] == "percent_yoy"
    assert d["details"]["indicator"] == "headline_consumer_inflation"
    assert "index" in str(err)


def test_frequency_mismatch_error_structured_payload():
    err = FrequencyMismatchError(expected="monthly", received="quarterly", indicator="x")
    assert err.to_dict()["code"] == "FREQUENCY_MISMATCH"


def test_unsupported_method_error_message_includes_context():
    err = UnsupportedMethodError(method="model_based", context="not implemented in v1")
    assert "model_based" in str(err)
    assert "not implemented in v1" in str(err)


@pytest.mark.parametrize("cls", ALL_ERRORS)
def test_generic_construction_and_to_dict_roundtrip(cls):
    if cls in (UnitMismatchError, FrequencyMismatchError):
        err = cls(expected="a", received="b", indicator="c")
    elif cls is UnsupportedMethodError:
        err = cls(method="m")
    else:
        err = cls("message text", foo="bar")
    d = err.to_dict()
    assert set(d.keys()) == {"code", "message", "details"}
    assert d["code"] == cls.code


def test_engine_error_never_returns_zero_as_a_value():
    # Domain rule check: EngineError itself carries no numeric "value"
    # attribute that could accidentally be read as a calculation result.
    err = DataQualityError("bad data")
    assert not hasattr(err, "value")
