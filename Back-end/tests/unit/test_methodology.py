import pytest

from app.models.methodology import InputProvenance, MethodologyVersion


class TestInputProvenance:
    def test_to_dict(self):
        p = InputProvenance(provider="bls", series_id="CUUR0000SA0")
        assert p.to_dict() == {"provider": "bls", "series_id": "CUUR0000SA0"}


class TestMethodologyVersion:
    def test_parses_semver(self):
        v = MethodologyVersion.parse("1.2.3")
        assert (v.major, v.minor, v.patch) == (1, 2, 3)
        assert str(v) == "1.2.3"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            MethodologyVersion.parse("1.2")
        with pytest.raises(ValueError):
            MethodologyVersion.parse("v1.2.3")

    def test_ordering(self):
        assert MethodologyVersion.parse("1.0.0") < MethodologyVersion.parse("1.0.1")
        assert MethodologyVersion.parse("1.0.0") < MethodologyVersion.parse("1.1.0")
        assert MethodologyVersion.parse("1.9.9") < MethodologyVersion.parse("2.0.0")

    def test_equality(self):
        assert MethodologyVersion.parse("1.0.0") == MethodologyVersion.parse("1.0.0")
