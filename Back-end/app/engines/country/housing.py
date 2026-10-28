"""Indicator 5 -- Housing Inflation.

COUNTRY_INFLATION_METHODS.md section 8 / CALCULATION_ENGINE_GUIDELINES.md
section 8.5.

Question answered: how much is the cost of obtaining and maintaining
housing increasing? Renters, existing fixed-rate borrowers, new buyers,
and outright homeowners experience different inflation, so this indicator
never collapses its sub-results into one number by default (COUNTRY
guidelines section 8.7: "Do not average these into one inflation rate.").
``value``/``unit`` are therefore always ``None``; every number lives in
``components``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.engines.shared.errors import DataQualityError
from app.engines.shared.growth import year_over_year
from app.engines.shared.quality import derive_confidence
from app.engines.shared.standardization import composite_score, historical_mean_std, z_score
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance
from app.models.observation import Observation

INDICATOR_ID = "housing_inflation"
METHODOLOGY_VERSION = "1.0.1"

_PAYMENT_PERIODS_PER_YEAR = {"monthly": 12, "quarterly": 4, "annual": 1}


@dataclass(frozen=True)
class MortgageAssumptions:
    """Externalized mortgage assumptions (COUNTRY guidelines section 8.5;
    ENGINE guidelines section 8.5: "Assumptions must be returned in result
    metadata.")."""

    term_years: int
    loan_to_value: float
    payment_frequency: str = "monthly"

    def periods_per_year(self) -> int:
        try:
            return _PAYMENT_PERIODS_PER_YEAR[self.payment_frequency]
        except KeyError as exc:
            raise DataQualityError(
                f"Unsupported payment_frequency {self.payment_frequency!r}"
            ) from exc


@dataclass(frozen=True)
class HousingPressureWeights:
    rent: float
    mortgage: float
    burden: float


def _mortgage_payment(loan_amount: float, periodic_rate: float, n_periods: int) -> float:
    """PMT_t = L_t * r_t(1+r_t)^N / [(1+r_t)^N - 1] (COUNTRY guidelines
    section 8.5). At r=0 the formula's limit is the simple L/N
    straight-line amortization, computed explicitly to avoid 0/0."""

    if loan_amount <= 0:
        raise DataQualityError(f"Loan amount must be positive, got {loan_amount}")
    if n_periods <= 0:
        raise DataQualityError(f"Number of payment periods must be positive, got {n_periods}")
    if periodic_rate == 0:
        return loan_amount / n_periods
    if periodic_rate < 0:
        raise DataQualityError(f"Periodic mortgage rate cannot be negative, got {periodic_rate}")
    factor = (1 + periodic_rate) ** n_periods
    return loan_amount * (periodic_rate * factor) / (factor - 1)


def calculate(
    *,
    rent_index_current: float,
    rent_index_prior_year: float,
    house_price_index_current: float,
    house_price_index_prior_year: float,
    geography: str,
    period: str,
    calculated_at: str,
    property_price_current: float | None = None,
    property_price_prior_year: float | None = None,
    mortgage_rate_current: float | None = None,
    mortgage_rate_prior_year: float | None = None,
    mortgage_assumptions: MortgageAssumptions | None = None,
    monthly_housing_cost: float | None = None,
    monthly_disposable_income: float | None = None,
    pressure_score_weights: HousingPressureWeights | None = None,
    standardization_windows: Mapping[str, Sequence[float]] | None = None,
    source_observations: tuple[Observation, ...] = (),
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    warnings: list[str] = []
    metadata: dict[str, object] = {}

    rent_inflation = year_over_year(rent_index_current, rent_index_prior_year)
    house_price_inflation = year_over_year(house_price_index_current, house_price_index_prior_year)

    mortgage_payment_inflation = None
    if all(
        v is not None
        for v in (property_price_current, property_price_prior_year,
                  mortgage_rate_current, mortgage_rate_prior_year, mortgage_assumptions)
    ):
        n_periods = mortgage_assumptions.term_years * mortgage_assumptions.periods_per_year()
        loan_current = mortgage_assumptions.loan_to_value * property_price_current
        loan_prior = mortgage_assumptions.loan_to_value * property_price_prior_year
        rate_current = mortgage_rate_current / mortgage_assumptions.periods_per_year()
        rate_prior = mortgage_rate_prior_year / mortgage_assumptions.periods_per_year()
        pmt_current = _mortgage_payment(loan_current, rate_current, n_periods)
        pmt_prior = _mortgage_payment(loan_prior, rate_prior, n_periods)
        mortgage_payment_inflation = year_over_year(pmt_current, pmt_prior)
        metadata["mortgage_assumptions"] = {
            "term_years": mortgage_assumptions.term_years,
            "loan_to_value": mortgage_assumptions.loan_to_value,
            "payment_frequency": mortgage_assumptions.payment_frequency,
            "representative_property_price": property_price_current,
            "representative_mortgage_rate": mortgage_rate_current,
        }
    else:
        warnings.append(f"{INDICATOR_ID}: mortgage_payment_inflation unavailable (missing mortgage inputs)")

    housing_burden_percent = None
    if monthly_housing_cost is not None and monthly_disposable_income is not None:
        if monthly_disposable_income <= 0:
            raise DataQualityError("monthly_disposable_income must be positive")
        housing_burden_percent = (monthly_housing_cost / monthly_disposable_income) * 100
    else:
        warnings.append(f"{INDICATOR_ID}: housing_burden_percent unavailable (missing income/cost inputs)")

    components = [
        Component(key="rent_inflation", label="Rent Inflation", value=rent_inflation, unit=Unit.PERCENT_YOY),
        Component(
            key="house_price_inflation", label="House-Price Inflation", value=house_price_inflation, unit=Unit.PERCENT_YOY
        ),
        Component(
            key="mortgage_payment_inflation",
            label="Mortgage-Payment Inflation",
            value=mortgage_payment_inflation,
            unit=Unit.PERCENT_YOY,
        ),
        Component(
            key="housing_burden_percent",
            label="Housing Burden",
            value=housing_burden_percent,
            unit=Unit.SHARE_PERCENT,
        ),
    ]

    # Optional Housing Pressure Score composite (COUNTRY guidelines
    # section 8.7): a standardized *score*, never presented as a rate.
    if (
        pressure_score_weights is not None
        and standardization_windows is not None
        and mortgage_payment_inflation is not None
        and housing_burden_percent is not None
    ):
        try:
            z_values = {
                "rent": _z(rent_inflation, standardization_windows.get("rent", ())),
                "mortgage": _z(mortgage_payment_inflation, standardization_windows.get("mortgage", ())),
                "burden": _z(housing_burden_percent, standardization_windows.get("burden", ())),
            }
            weights = {
                "rent": pressure_score_weights.rent,
                "mortgage": pressure_score_weights.mortgage,
                "burden": pressure_score_weights.burden,
            }
            hps = composite_score(z_values, weights)
            components.append(
                Component(
                    key="housing_pressure_score",
                    label="Housing Pressure Score",
                    value=hps,
                    unit=Unit.STANDARD_DEVIATION_SCORE,
                    is_score=True,
                )
            )
        except DataQualityError as exc:
            warnings.append(f"housing_pressure_score unavailable: {exc.message}")

    confidence = derive_confidence(*source_observations) if source_observations else Confidence.HIGH
    is_estimated = any(o.is_estimated for o in source_observations)
    any_unavailable = mortgage_payment_inflation is None or housing_burden_percent is None

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography=geography,
        period=period,
        value=None,
        unit=None,
        method="housing_multi_component",
        methodology_version=methodology_version,
        input_series=input_series,
        coverage=Coverage.PARTIAL if any_unavailable else Coverage.FULL,
        confidence=confidence,
        is_estimated=is_estimated,
        warnings=tuple(warnings),
        calculated_at=calculated_at,
        components=tuple(components),
        config_version=config_version,
        metadata=metadata,
    )


def _z(value: float, window: Sequence[float]) -> float:
    if len(window) < 2:
        raise DataQualityError("standardization window requires at least 2 historical values")
    mu, sigma = historical_mean_std(window)
    return z_score(value, mu, sigma)
