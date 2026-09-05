"""Coverage for app/engines/shared/quality.py -- confidence derivation and
provenance collection shared by every engine module. This module had no
direct tests: every engine only exercised it incidentally, so a dedup or
confidence-ranking bug here would silently affect every single response's
``confidence`` and ``input_series`` fields without any test catching it."""

import pytest

from app.engines.shared.periods import parse_period
from app.engines.shared.quality import any_estimated, build_provenance, derive_confidence, gap_warnings
from app.models.enums import Confidence, Coverage, Frequency, Unit, ValidationStatus
from app.models.observation import Observation
from app.models.series import ObservationSeries


def make_obs(period: str, value: float = 100.0, **overrides):
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


class TestDeriveConfidence:
    def test_no_observations_is_low(self):
        assert derive_confidence() == Confidence.LOW

    def test_all_validated_no_estimate_no_explicit_confidence_is_high(self):
        obs = (make_obs("2026-01"), make_obs("2026-02"))
        assert derive_confidence(*obs) == Confidence.HIGH

    def test_any_estimated_caps_at_low_even_with_explicit_high(self):
        obs = (
            make_obs("2026-01", is_estimated=True, confidence=Confidence.HIGH),
            make_obs("2026-02", confidence=Confidence.HIGH),
        )
        assert derive_confidence(*obs) == Confidence.LOW

    def test_any_partial_coverage_caps_at_medium(self):
        obs = (
            make_obs("2026-01", coverage_status=Coverage.PARTIAL),
            make_obs("2026-02", confidence=Confidence.HIGH),
        )
        assert derive_confidence(*obs) == Confidence.MEDIUM

    def test_estimated_outranks_partial_coverage(self):
        # Both caps apply; LOW (estimated) must win over MEDIUM (partial).
        obs = (make_obs("2026-01", is_estimated=True, coverage_status=Coverage.PARTIAL),)
        assert derive_confidence(*obs) == Confidence.LOW

    def test_lowest_explicit_confidence_wins(self):
        obs = (
            make_obs("2026-01", confidence=Confidence.HIGH),
            make_obs("2026-02", confidence=Confidence.MEDIUM),
            make_obs("2026-03", confidence=Confidence.HIGH),
        )
        assert derive_confidence(*obs) == Confidence.MEDIUM

    def test_mix_of_explicit_and_absent_confidence_uses_only_explicit(self):
        # One observation with no explicit confidence must not silently
        # count as HIGH and out-vote a genuinely lower explicit value from
        # another, nor must it be treated as missing data.
        obs = (
            make_obs("2026-01", confidence=Confidence.LOW),
            make_obs("2026-02"),  # no explicit confidence
        )
        assert derive_confidence(*obs) == Confidence.LOW


class TestAnyEstimated:
    def test_false_when_none_estimated(self):
        assert any_estimated(make_obs("2026-01"), make_obs("2026-02")) is False

    def test_true_when_one_estimated(self):
        assert any_estimated(make_obs("2026-01"), make_obs("2026-02", is_estimated=True)) is True

    def test_false_for_no_observations(self):
        assert any_estimated() is False


class TestBuildProvenance:
    def test_single_observation(self):
        result = build_provenance(make_obs("2026-01", provider="bls", source_series_id="CUUR0000SA0"))
        assert len(result) == 1
        assert result[0].provider == "bls"
        assert result[0].series_id == "CUUR0000SA0"

    def test_deduplicates_identical_provider_series_vintage(self):
        # Two observations pulled from the same series/vintage (e.g. one
        # role reusing another role's underlying data point) must collapse
        # to one provenance entry, not double-count the source.
        a = make_obs("2026-01", provider="bls", source_series_id="CUUR0000SA0", data_vintage="2026-08-01")
        b = make_obs("2026-02", provider="bls", source_series_id="CUUR0000SA0", data_vintage="2026-08-01")
        result = build_provenance(a, b)
        assert len(result) == 1

    def test_different_data_vintage_is_not_deduplicated(self):
        # A revision (new data_vintage) of the same series is a distinct,
        # traceable provenance entry -- not silently merged with the
        # earlier vintage.
        a = make_obs("2026-01", provider="bls", source_series_id="CUUR0000SA0", data_vintage="2026-07-01")
        b = make_obs("2026-02", provider="bls", source_series_id="CUUR0000SA0", data_vintage="2026-08-01")
        result = build_provenance(a, b)
        assert len(result) == 2

    def test_different_provider_is_not_deduplicated(self):
        a = make_obs("2026-01", provider="bls", source_series_id="X")
        b = make_obs("2026-02", provider="fred", source_series_id="X")
        result = build_provenance(a, b)
        assert len(result) == 2

    def test_order_is_preserved_first_occurrence_wins(self):
        a = make_obs("2026-01", provider="bls", source_series_id="A")
        b = make_obs("2026-02", provider="fred", source_series_id="B")
        c = make_obs("2026-03", provider="bls", source_series_id="A")  # dup of a
        result = build_provenance(a, b, c)
        assert [p.series_id for p in result] == ["A", "B"]

    def test_no_observations_returns_empty_tuple(self):
        assert build_provenance() == ()


class TestGapWarnings:
    def test_no_gaps_returns_empty_list(self):
        series = ObservationSeries([make_obs("2026-01"), make_obs("2026-02"), make_obs("2026-03")])
        assert gap_warnings(series, context="test") == []

    def test_gap_produces_one_warning_naming_the_missing_periods(self):
        series = ObservationSeries([make_obs("2026-01"), make_obs("2026-04")])
        warnings = gap_warnings(series, context="headline_consumer_inflation")
        assert len(warnings) == 1
        assert "headline_consumer_inflation" in warnings[0]
        assert "2026-02" in warnings[0]
        assert "2026-03" in warnings[0]
