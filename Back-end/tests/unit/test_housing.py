import pytest

from app.engines.country import housing
from app.engines.shared.errors import DataQualityError
from app.models.enums import Coverage

CALCULATED_AT = "2026-08-02T12:00:00Z"


class TestSubComponentsNeverAveraged:
    def test_top_level_value_is_always_none(self):
        result = housing.calculate(
            rent_index_current=110.0, rent_index_prior_year=100.0,
            house_price_index_current=130.0, house_price_index_prior_year=100.0,
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert result.value is None
        assert result.unit is None

    def test_rent_and_house_price_computed_independently(self):
        result = housing.calculate(
            rent_index_current=104.0, rent_index_prior_year=100.0,
            house_price_index_current=106.8, house_price_index_prior_year=100.0,
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        rent = next(c for c in result.components if c.key == "rent_inflation")
        house = next(c for c in result.components if c.key == "house_price_inflation")
        assert rent.value == pytest.approx(4.0)
        assert house.value == pytest.approx(6.8)


class TestMortgagePayment:
    def test_matches_manual_annuity_formula(self):
        assumptions = housing.MortgageAssumptions(term_years=30, loan_to_value=0.8, payment_frequency="monthly")
        result = housing.calculate(
            rent_index_current=100.0, rent_index_prior_year=100.0,
            house_price_index_current=100.0, house_price_index_prior_year=100.0,
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            property_price_current=420000.0, property_price_prior_year=400000.0,
            mortgage_rate_current=0.065, mortgage_rate_prior_year=0.06,
            mortgage_assumptions=assumptions,
        )
        n = 30 * 12
        loan_t = 0.8 * 420000.0
        loan_t12 = 0.8 * 400000.0
        r_t = 0.065 / 12
        r_t12 = 0.06 / 12
        pmt_t = loan_t * (r_t * (1 + r_t) ** n) / ((1 + r_t) ** n - 1)
        pmt_t12 = loan_t12 * (r_t12 * (1 + r_t12) ** n) / ((1 + r_t12) ** n - 1)
        expected = (pmt_t / pmt_t12 - 1) * 100
        mortgage = next(c for c in result.components if c.key == "mortgage_payment_inflation")
        assert mortgage.value == pytest.approx(expected)
        assert result.metadata["mortgage_assumptions"]["term_years"] == 30

    def test_zero_rate_uses_linear_limit(self):
        assumptions = housing.MortgageAssumptions(term_years=10, loan_to_value=1.0, payment_frequency="monthly")
        result = housing.calculate(
            rent_index_current=100.0, rent_index_prior_year=100.0,
            house_price_index_current=100.0, house_price_index_prior_year=100.0,
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            property_price_current=120000.0, property_price_prior_year=120000.0,
            mortgage_rate_current=0.0, mortgage_rate_prior_year=0.0,
            mortgage_assumptions=assumptions,
        )
        mortgage = next(c for c in result.components if c.key == "mortgage_payment_inflation")
        assert mortgage.value == pytest.approx(0.0)

    def test_missing_mortgage_inputs_marks_unavailable_not_whole_result(self):
        result = housing.calculate(
            rent_index_current=104.0, rent_index_prior_year=100.0,
            house_price_index_current=106.0, house_price_index_prior_year=100.0,
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        mortgage = next(c for c in result.components if c.key == "mortgage_payment_inflation")
        assert mortgage.value is None
        rent = next(c for c in result.components if c.key == "rent_inflation")
        assert rent.value is not None
        assert result.coverage == Coverage.PARTIAL
        assert any("mortgage_payment_inflation unavailable" in w for w in result.warnings)

    def test_unsupported_payment_frequency_raises(self):
        with pytest.raises(DataQualityError):
            housing.MortgageAssumptions(term_years=30, loan_to_value=0.8, payment_frequency="weekly").periods_per_year()

    @pytest.mark.parametrize("bad_rate", [-0.01, 1.5, 6.5])
    def test_out_of_bounds_mortgage_rate_ratio_raises(self, bad_rate):
        assumptions = housing.MortgageAssumptions(term_years=30, loan_to_value=0.8, payment_frequency="monthly")
        with pytest.raises(DataQualityError):
            housing.calculate(
                rent_index_current=100.0, rent_index_prior_year=100.0,
                house_price_index_current=100.0, house_price_index_prior_year=100.0,
                geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
                property_price_current=420000.0, property_price_prior_year=400000.0,
                mortgage_rate_current=bad_rate, mortgage_rate_prior_year=0.06,
                mortgage_assumptions=assumptions,
            )


class TestHousingBurden:
    def test_matches_manual_formula(self):
        result = housing.calculate(
            rent_index_current=100.0, rent_index_prior_year=100.0,
            house_price_index_current=100.0, house_price_index_prior_year=100.0,
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            monthly_housing_cost=1500.0, monthly_disposable_income=5000.0,
        )
        burden = next(c for c in result.components if c.key == "housing_burden_percent")
        assert burden.value == pytest.approx(30.0)

    def test_zero_disposable_income_raises(self):
        with pytest.raises(DataQualityError):
            housing.calculate(
                rent_index_current=100.0, rent_index_prior_year=100.0,
                house_price_index_current=100.0, house_price_index_prior_year=100.0,
                geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
                monthly_housing_cost=1500.0, monthly_disposable_income=0.0,
            )


class TestHousingPressureScore:
    def test_score_marked_as_score_not_rate(self):
        assumptions = housing.MortgageAssumptions(term_years=30, loan_to_value=0.8)
        weights = housing.HousingPressureWeights(rent=0.4, mortgage=0.4, burden=0.2)
        windows = {
            "rent": [2.0, 3.0, 4.0, 5.0, 6.0],
            "mortgage": [5.0, 8.0, 10.0, 12.0, 15.0],
            "burden": [25.0, 28.0, 30.0, 32.0, 35.0],
        }
        result = housing.calculate(
            rent_index_current=104.0, rent_index_prior_year=100.0,
            house_price_index_current=106.0, house_price_index_prior_year=100.0,
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            property_price_current=420000.0, property_price_prior_year=400000.0,
            mortgage_rate_current=0.065, mortgage_rate_prior_year=0.06,
            mortgage_assumptions=assumptions,
            monthly_housing_cost=1500.0, monthly_disposable_income=5000.0,
            pressure_score_weights=weights,
            standardization_windows=windows,
        )
        hps = next(c for c in result.components if c.key == "housing_pressure_score")
        assert hps.is_score is True
        assert hps.unit.value == "standard_deviation_score"

    def test_score_absent_without_windows(self):
        result = housing.calculate(
            rent_index_current=104.0, rent_index_prior_year=100.0,
            house_price_index_current=106.0, house_price_index_prior_year=100.0,
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert not any(c.key == "housing_pressure_score" for c in result.components)


class TestEdgeCases:
    def test_flat_house_prices_zero_inflation(self):
        result = housing.calculate(
            rent_index_current=100.0, rent_index_prior_year=100.0,
            house_price_index_current=100.0, house_price_index_prior_year=100.0,
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        house = next(c for c in result.components if c.key == "house_price_inflation")
        assert house.value == pytest.approx(0.0)

    def test_falling_house_prices_negative(self):
        result = housing.calculate(
            rent_index_current=100.0, rent_index_prior_year=100.0,
            house_price_index_current=90.0, house_price_index_prior_year=100.0,
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        house = next(c for c in result.components if c.key == "house_price_inflation")
        assert house.value < 0
