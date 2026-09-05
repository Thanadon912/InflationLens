"""Regression: the Flask app must never serialize NaN/Infinity as bare
JSON literals -- valid Python, but JavaScript's JSON.parse() (every
browser, including this project's own frontend) rejects them outright.
Component/IndicatorResult already reject non-finite values at
construction (a 422); this covers the response paths in app/api/data.py
that build plain dicts outside that model layer."""

import math

import pytest

from app import create_app


@pytest.fixture()
def app():
    return create_app()


class TestStrictJSONProvider:
    def test_finite_values_serialize_normally(self, app):
        assert app.json.dumps({"v": 3.2}) == '{"v": 3.2}'

    def test_infinity_raises_instead_of_serializing_bare_literal(self, app):
        with pytest.raises(ValueError):
            app.json.dumps({"v": math.inf})

    def test_negative_infinity_raises(self, app):
        with pytest.raises(ValueError):
            app.json.dumps({"v": -math.inf})

    def test_nan_raises(self, app):
        with pytest.raises(ValueError):
            app.json.dumps({"v": math.nan})
