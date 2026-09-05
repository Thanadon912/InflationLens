import pytest

from app.engines.global_ import synchronization as gs
from app.engines.shared.errors import DataQualityError
from app.models.enums import Coverage

CALCULATED_AT = "2026-08-02T12:00:00Z"


class TestShareAboveThreshold:
    def test_matches_manual_count(self):
        rates = {"A": 1.0, "B": 3.0, "C": 5.0, "D": 6.0}
        result = gs.calculate(country_rates_current=rates, threshold_percent=4.0, all_geographies=("A", "B", "C", "D"), period="p", calculated_at=CALCULATED_AT)
        assert result.value == pytest.approx(50.0)  # C and D above 4.0

    def test_all_below_threshold(self):
        rates = {"A": 1.0, "B": 2.0}
        result = gs.calculate(country_rates_current=rates, threshold_percent=10.0, all_geographies=("A", "B"), period="p", calculated_at=CALCULATED_AT)
        assert result.value == pytest.approx(0.0)

    def test_all_above_threshold(self):
        rates = {"A": 5.0, "B": 6.0}
        result = gs.calculate(country_rates_current=rates, threshold_percent=1.0, all_geographies=("A", "B"), period="p", calculated_at=CALCULATED_AT)
        assert result.value == pytest.approx(100.0)


class TestDispersionAndCount:
    def test_country_count_and_mean(self):
        rates = {"A": 2.0, "B": 4.0, "C": 6.0}
        result = gs.calculate(country_rates_current=rates, threshold_percent=3.0, all_geographies=("A", "B", "C"), period="p", calculated_at=CALCULATED_AT)
        count = next(c for c in result.components if c.key == "country_count")
        mean = next(c for c in result.components if c.key == "mean")
        assert count.value == pytest.approx(3.0)
        assert mean.value == pytest.approx(4.0)

    def test_dispersion_matches_bessel_corrected_std(self):
        rates = {"A": 2.0, "B": 4.0, "C": 6.0, "D": 8.0}
        result = gs.calculate(country_rates_current=rates, threshold_percent=3.0, all_geographies=("A", "B", "C", "D"), period="p", calculated_at=CALCULATED_AT)
        mean = sum(rates.values()) / len(rates)
        expected = (sum((v - mean) ** 2 for v in rates.values()) / (len(rates) - 1)) ** 0.5
        dispersion = next(c for c in result.components if c.key == "dispersion")
        assert dispersion.value == pytest.approx(expected)

    def test_iqr_present(self):
        rates = {"A": 1.0, "B": 2.0, "C": 3.0, "D": 4.0}
        result = gs.calculate(country_rates_current=rates, threshold_percent=2.0, all_geographies=("A", "B", "C", "D"), period="p", calculated_at=CALCULATED_AT)
        iqr = next(c for c in result.components if c.key == "iqr")
        assert iqr.value >= 0


class TestShareAccelerating:
    def test_matches_manual_computation(self):
        current = {"A": 5.0, "B": 3.0, "C": 6.0}
        prior = {"A": 4.0, "B": 4.0, "C": 5.0}
        result = gs.calculate(
            country_rates_current=current, country_rates_prior=prior,
            threshold_percent=10.0, all_geographies=("A", "B", "C"), period="p", calculated_at=CALCULATED_AT,
        )
        accel = next(c for c in result.components if c.key == "share_accelerating")
        assert accel.value == pytest.approx(2 / 3 * 100)  # A and C accelerated

    def test_absent_without_prior_marks_partial(self):
        result = gs.calculate(country_rates_current={"A": 1.0}, threshold_percent=0.0, all_geographies=("A",), period="p", calculated_at=CALCULATED_AT)
        assert result.coverage == Coverage.PARTIAL
        assert not any(c.key == "share_accelerating" for c in result.components)

    def test_no_overlap_between_current_and_prior_omits_component(self):
        # country_rates_prior is supplied (truthy) but shares no country
        # with country_rates_current -- today this silently omits
        # share_accelerating without a warning, unlike the analogous
        # population_weights overlap check. Pinning current behavior.
        result = gs.calculate(country_rates_current={"A": 5.0}, country_rates_prior={"Z": 4.0}, threshold_percent=0.0, all_geographies=("A",), period="p", calculated_at=CALCULATED_AT)
        assert not any(c.key == "share_accelerating" for c in result.components)


class TestPopulationWeighted:
    def test_matches_manual_weighted_share(self):
        rates = {"A": 5.0, "B": 1.0}
        weights = {"A": 0.8, "B": 0.2}
        result = gs.calculate(country_rates_current=rates, threshold_percent=3.0, all_geographies=("A", "B"), period="p", calculated_at=CALCULATED_AT, population_weights=weights)
        pop_share = next(c for c in result.components if c.key == "share_above_pop_weighted")
        assert pop_share.value == pytest.approx(80.0)

    def test_weights_not_summing_to_one_are_renormalized_not_taken_literally(self):
        # Regression: population_weights summing to 1.8 must never yield a
        # share above 100%. The share is defined over the covered subset
        # of country_rates_current, renormalized, not the raw weights.
        rates = {"USA": 5.0, "EA": 3.0}  # only USA is above the threshold
        weights = {"USA": 0.9, "EA": 0.9}
        result = gs.calculate(country_rates_current=rates, threshold_percent=4.0, all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT, population_weights=weights)
        pop_share = next(c for c in result.components if c.key == "share_above_pop_weighted")
        assert pop_share.value == pytest.approx(50.0)
        assert 0.0 <= pop_share.value <= 100.0

    def test_partial_weight_coverage_renormalizes_over_covered_countries_and_warns(self):
        rates = {"USA": 5.0, "EA": 3.0, "JPN": 1.0}  # only USA is above the threshold
        weights = {"USA": 0.5, "EA": 0.5}  # JPN has no population weight
        result = gs.calculate(country_rates_current=rates, threshold_percent=4.0, all_geographies=("USA", "EA", "JPN"), period="p", calculated_at=CALCULATED_AT, population_weights=weights)
        pop_share = next(c for c in result.components if c.key == "share_above_pop_weighted")
        assert pop_share.value == pytest.approx(50.0)
        assert any("share_above_pop_weighted" in w for w in result.warnings)

    def test_no_overlap_between_rates_and_population_weights_warns_not_omits_silently(self):
        rates = {"USA": 5.0, "EA": 3.0}
        weights = {"JPN": 1.0}  # no country in common with rates
        result = gs.calculate(country_rates_current=rates, threshold_percent=4.0, all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT, population_weights=weights)
        assert not any(c.key == "share_above_pop_weighted" for c in result.components)
        assert any("no overlap" in w for w in result.warnings)


class TestCommonFactorModelAlwaysUnavailable:
    def test_present_and_unavailable(self):
        result = gs.calculate(country_rates_current={"A": 1.0}, threshold_percent=0.0, all_geographies=("A",), period="p", calculated_at=CALCULATED_AT)
        cfm = next(c for c in result.components if c.key == "common_factor_model")
        assert cfm.value is None
        assert cfm.is_score is True


class TestSynchronizationScore:
    def test_present_when_all_inputs_given(self):
        current = {"A": 5.0, "B": 3.0, "C": 6.0, "D": 2.0}
        prior = {"A": 4.0, "B": 4.0, "C": 5.0, "D": 3.0}
        weights = {"share_accelerating": 0.4, "share_above_threshold": 0.4, "dispersion": 0.2}
        window = [1.0, 1.5, 2.0, 2.5, 3.0]
        result = gs.calculate(
            country_rates_current=current, country_rates_prior=prior,
            threshold_percent=3.0, all_geographies=("A", "B", "C", "D"), period="p", calculated_at=CALCULATED_AT,
            composite_weights=weights, dispersion_standardization_window=window,
        )
        score = next(c for c in result.components if c.key == "synchronization_score")
        assert score.is_score is True
        assert score.unit.value == "standard_deviation_score"
        # Doc formula subtracts dispersion. With the window below, z of
        # current dispersion is negative, so subtracting it raises the score.
        import statistics
        dispersion = statistics.stdev(current.values())
        z_dispersion = (dispersion - statistics.mean(window)) / statistics.stdev(window)
        expected = 0.4 * 50.0 + 0.4 * 50.0 - 0.2 * z_dispersion
        assert score.value == pytest.approx(expected)

    def test_absent_without_composite_weights(self):
        current = {"A": 5.0, "B": 3.0}
        prior = {"A": 4.0, "B": 4.0}
        result = gs.calculate(country_rates_current=current, country_rates_prior=prior, threshold_percent=3.0, all_geographies=("A", "B"), period="p", calculated_at=CALCULATED_AT)
        assert not any(c.key == "synchronization_score" for c in result.components)


class TestEmptyInput:
    def test_empty_country_rates_raises(self):
        with pytest.raises(DataQualityError):
            gs.calculate(country_rates_current={}, threshold_percent=2.0, all_geographies=(), period="p", calculated_at=CALCULATED_AT)


class TestSynchronizationScoreDegradesGracefully:
    def test_insufficient_dispersion_window_omits_score_with_warning(self):
        current = {"A": 5.0, "B": 3.0, "C": 6.0, "D": 2.0}
        prior = {"A": 4.0, "B": 4.0, "C": 5.0, "D": 3.0}
        weights = {"share_accelerating": 0.4, "share_above_threshold": 0.4, "dispersion": 0.2}
        result = gs.calculate(
            country_rates_current=current, country_rates_prior=prior,
            threshold_percent=3.0, all_geographies=("A", "B", "C", "D"), period="p", calculated_at=CALCULATED_AT,
            composite_weights=weights, dispersion_standardization_window=[1.0],  # too short
        )
        assert not any(c.key == "synchronization_score" for c in result.components)
        assert any("synchronization_score unavailable" in w for w in result.warnings)
