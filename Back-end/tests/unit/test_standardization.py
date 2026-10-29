import pytest

from app.engines.shared.errors import DataQualityError
from app.engines.shared.standardization import (
    composite_score,
    diffusion_z_score,
    historical_mean_std,
    z_score,
)


class TestZScore:
    def test_at_mean_is_zero(self):
        assert z_score(5.0, 5.0, 2.0) == pytest.approx(0.0)

    def test_one_sigma_above(self):
        assert z_score(7.0, 5.0, 2.0) == pytest.approx(1.0)

    def test_one_sigma_below(self):
        assert z_score(3.0, 5.0, 2.0) == pytest.approx(-1.0)

    def test_zero_sigma_raises(self):
        with pytest.raises(DataQualityError):
            z_score(5.0, 5.0, 0.0)


class TestHistoricalMeanStd:
    def test_matches_sample_statistics(self):
        window = [1.0, 2.0, 3.0, 4.0, 5.0]
        mu, sigma = historical_mean_std(window)
        assert mu == pytest.approx(3.0)
        assert sigma == pytest.approx(1.5811388300841898)


class TestCompositeScore:
    def test_weighted_sum(self):
        z_values = {"rent": 1.0, "mortgage": 2.0, "burden": -1.0}
        weights = {"rent": 0.4, "mortgage": 0.4, "burden": 0.2}
        result = composite_score(z_values, weights)
        assert result == pytest.approx(0.4 * 1.0 + 0.4 * 2.0 + 0.2 * -1.0)

    def test_weights_not_summing_to_one_raises(self):
        from app.engines.shared.errors import InvalidWeightError

        with pytest.raises(InvalidWeightError):
            composite_score({"a": 1.0}, {"a": 0.5})

    def test_mismatched_keys_raises(self):
        with pytest.raises(DataQualityError):
            composite_score({"a": 1.0}, {"b": 1.0})


class TestDiffusionZScore:
    @pytest.mark.parametrize("share,expected", [(0.0, -2.0), (50.0, 0.0), (75.0, 1.0), (100.0, 2.0)])
    def test_maps_percentage_bounds_to_sigma_scale(self, share, expected):
        assert diffusion_z_score(share) == pytest.approx(expected)

    @pytest.mark.parametrize("bad_share", [-0.1, 100.1])
    def test_out_of_bounds_share_raises(self, bad_share):
        with pytest.raises(DataQualityError):
            diffusion_z_score(bad_share)
