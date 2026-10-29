import pytest

from app.engines.global_ import housing_assets as gha
from app.models.enums import Coverage

CALCULATED_AT = "2026-08-02T12:00:00Z"


def base_kwargs(**overrides):
    defaults = dict(
        country_house_price_current={"USA": 110.0, "EA": 105.0},
        country_house_price_prior={"USA": 100.0, "EA": 100.0},
        housing_weights={"USA": 0.6, "EA": 0.4},
        country_rent_rates={"USA": 4.0, "EA": 3.0},
        consumption_ppp_weights={"USA": 0.5, "EA": 0.5},
        all_geographies=("USA", "EA"),
        period="2026-Q2",
        calculated_at=CALCULATED_AT,
    )
    defaults.update(overrides)
    return defaults


class TestSeparationFromConsumerInflation:
    def test_value_and_unit_always_none(self):
        result = gha.calculate(**base_kwargs())
        assert result.value is None
        assert result.unit is None

    def test_house_and_rent_are_distinct_components(self):
        result = gha.calculate(**base_kwargs())
        house = next(c for c in result.components if c.key == "house_price")
        rent = next(c for c in result.components if c.key == "rent")
        assert house.value != pytest.approx(rent.value)

    def test_house_price_matches_manual_weighted_mean(self):
        result = gha.calculate(**base_kwargs())
        house = next(c for c in result.components if c.key == "house_price")
        usa_infl = (110.0 / 100.0 - 1) * 100
        ea_infl = (105.0 / 100.0 - 1) * 100
        expected = 0.6 * usa_infl + 0.4 * ea_infl
        assert house.value == pytest.approx(expected)

    def test_partial_country_coverage_renormalizes_secondary_weights(self):
        result = gha.calculate(
            **base_kwargs(
                country_house_price_current={"USA": 110.0},
                country_house_price_prior={"USA": 100.0},
                housing_weights={"USA": 0.6, "EA": 0.4},
                country_rent_rates={"USA": 4.0},
                consumption_ppp_weights={"USA": 0.5, "EA": 0.5},
            )
        )
        house = next(c for c in result.components if c.key == "house_price")
        rent = next(c for c in result.components if c.key == "rent")
        assert house.value == pytest.approx(10.0)
        assert rent.value == pytest.approx(4.0)


class TestOptionalComponents:
    def test_equity_present_when_given(self):
        result = gha.calculate(**base_kwargs(equity_index_current=1200.0, equity_index_prior_year=1000.0))
        equity = next(c for c in result.components if c.key == "equity")
        assert equity.value == pytest.approx(20.0)

    def test_equity_absent_marks_partial(self):
        result = gha.calculate(**base_kwargs())
        assert result.coverage == Coverage.PARTIAL
        assert not any(c.key == "equity" for c in result.components)

    def test_gold_and_bitcoin_per_currency(self):
        result = gha.calculate(
            **base_kwargs(
                asset_prices_current={"gold": {"USD": 2200.0, "EUR": 2000.0}, "bitcoin": {"USD": 65000.0}},
                asset_prices_prior_year={"gold": {"USD": 2000.0, "EUR": 1900.0}, "bitcoin": {"USD": 50000.0}},
            )
        )
        gold_usd = next(c for c in result.components if c.key == "gold_USD")
        assert gold_usd.value == pytest.approx(10.0)
        btc_usd = next(c for c in result.components if c.key == "bitcoin_USD")
        assert btc_usd.value == pytest.approx(30.0)

    def test_asset_income_ratio(self):
        result = gha.calculate(
            **base_kwargs(
                asset_price_index_current=220.0, asset_price_index_prior_year=200.0,
                income_index_current=110.0, income_index_prior_year=105.0,
            )
        )
        ratio = next(c for c in result.components if c.key == "asset_income_ratio")
        assert ratio.value == pytest.approx(2.0)
        growth = next(c for c in result.components if c.key == "asset_income_ratio_growth_approx")
        asset_g = (220.0 / 200.0 - 1) * 100
        income_g = (110.0 / 105.0 - 1) * 100
        assert growth.value == pytest.approx(asset_g - income_g)


class TestZeroIncomeIndex:
    def test_zero_income_index_current_marks_partial_not_zero_division(self):
        result = gha.calculate(
            **base_kwargs(
                asset_price_index_current=220.0, asset_price_index_prior_year=200.0,
                income_index_current=0.0, income_index_prior_year=105.0,
            )
        )
        assert not any(c.key == "asset_income_ratio" for c in result.components)
        assert any("asset_income_ratio unavailable" in w for w in result.warnings)
