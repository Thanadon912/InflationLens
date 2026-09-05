"""Global Indicator 7 -- Global Housing and Asset Inflation.

GLOBAL_INFLATION_METHODS.md section 11 / CALCULATION_ENGINE_GUIDELINES.md
section 9.7.

Question answered: how quickly are major stores of wealth and access-to-
ownership costs rising globally? GLOBAL guidelines section 11.2 requires
housing and financial assets to remain separate from consumer inflation;
``value``/``unit`` are always ``None`` so every asset class is reported
on its own, uncombined.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.engines.shared.aggregation import weighted_arithmetic_mean
from app.engines.shared.coverage import build_coverage_report
from app.engines.shared.errors import EngineError
from app.engines.shared.growth import year_over_year
from app.engines.shared.validation import validate_positive_index
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance

INDICATOR_ID = "global_housing_asset_inflation"
METHODOLOGY_VERSION = "1.0.1"


def calculate(
    *,
    country_house_price_current: Mapping[str, float],
    country_house_price_prior: Mapping[str, float],
    housing_weights: Mapping[str, float],
    country_rent_rates: Mapping[str, float],
    consumption_ppp_weights: Mapping[str, float],
    all_geographies: tuple[str, ...],
    period: str,
    calculated_at: str,
    equity_index_current: float | None = None,
    equity_index_prior_year: float | None = None,
    asset_prices_current: Mapping[str, Mapping[str, float]] | None = None,
    asset_prices_prior_year: Mapping[str, Mapping[str, float]] | None = None,
    asset_price_index_current: float | None = None,
    asset_price_index_prior_year: float | None = None,
    income_index_current: float | None = None,
    income_index_prior_year: float | None = None,
    population_by_geo: Mapping[str, float] | None = None,
    gdp_ppp_by_geo: Mapping[str, float] | None = None,
    consumption_ppp_by_geo: Mapping[str, float] | None = None,
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    """``country_house_price_current``/``_prior`` are per-country HPI
    levels at ``t`` and ``t-4`` (quarterly lag, GLOBAL guidelines section
    11.3); country house-price inflation is computed here before global
    aggregation with ``housing_weights``.
    """

    country_house_inflation = {
        c: year_over_year(country_house_price_current[c], country_house_price_prior[c])
        for c in set(country_house_price_current) & set(country_house_price_prior)
    }
    global_house_price = weighted_arithmetic_mean(
        country_house_inflation, {c: housing_weights[c] for c in country_house_inflation}
    )
    global_rent = weighted_arithmetic_mean(country_rent_rates, consumption_ppp_weights)

    components = [
        Component(key="house_price", label="Global House-Price Inflation", value=global_house_price, unit=Unit.PERCENT_YOY),
        Component(key="rent", label="Global Rent Inflation", value=global_rent, unit=Unit.PERCENT_YOY),
    ]
    warnings: list[str] = []

    if equity_index_current is not None and equity_index_prior_year is not None:
        components.append(
            Component(
                key="equity",
                label="Global Equity Inflation",
                value=year_over_year(equity_index_current, equity_index_prior_year),
                unit=Unit.PERCENT_YOY,
            )
        )
    else:
        warnings.append(f"{INDICATOR_ID}: equity unavailable (missing global equity index)")

    if asset_prices_current and asset_prices_prior_year:
        for asset_name, current_by_currency in asset_prices_current.items():
            prior_by_currency = asset_prices_prior_year.get(asset_name, {})
            for currency, current_price in current_by_currency.items():
                if currency not in prior_by_currency:
                    continue
                components.append(
                    Component(
                        key=f"{asset_name}_{currency}",
                        label=f"{asset_name.title()} Price Inflation ({currency})",
                        value=year_over_year(current_price, prior_by_currency[currency]),
                        unit=Unit.PERCENT_YOY,
                    )
                )
    else:
        warnings.append(f"{INDICATOR_ID}: gold/bitcoin returns unavailable (missing multi-currency asset prices)")

    if all(
        v is not None
        for v in (asset_price_index_current, asset_price_index_prior_year, income_index_current, income_index_prior_year)
    ):
        try:
            validate_positive_index(income_index_current, context=f"{INDICATOR_ID}.income_index_current")
            ratio_current = asset_price_index_current / income_index_current
            asset_growth = year_over_year(asset_price_index_current, asset_price_index_prior_year)
            income_growth = year_over_year(income_index_current, income_index_prior_year)
            components.append(
                Component(key="asset_income_ratio", label="Asset-to-Income Ratio", value=ratio_current, unit=Unit.RATIO)
            )
            components.append(
                Component(
                    key="asset_income_ratio_growth_approx",
                    label="Asset-to-Income Ratio Growth (approx)",
                    value=asset_growth - income_growth,
                    unit=Unit.PERCENT_YOY,
                )
            )
        except EngineError as exc:
            warnings.append(f"asset_income_ratio unavailable: {exc.message}")
    else:
        warnings.append(f"{INDICATOR_ID}: asset_income_ratio unavailable (missing asset/income index data)")

    coverage_report = build_coverage_report(
        all_geographies=all_geographies,
        included_geographies=set(country_house_inflation) | set(country_rent_rates),
        population_by_geo=population_by_geo,
        gdp_ppp_by_geo=gdp_ppp_by_geo,
        consumption_ppp_by_geo=consumption_ppp_by_geo,
    )

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography="GLOBAL",
        period=period,
        value=None,
        unit=None,
        method="housing_and_asset_multi_component",
        methodology_version=methodology_version,
        input_series=input_series,
        coverage=Coverage.FULL if not warnings else Coverage.PARTIAL,
        confidence=Confidence.HIGH,
        is_estimated=False,
        warnings=tuple(warnings),
        calculated_at=calculated_at,
        components=tuple(components),
        coverage_report=coverage_report,
        config_version=config_version,
        metadata={"note": "asset returns are kept separate from consumer inflation"},
    )
