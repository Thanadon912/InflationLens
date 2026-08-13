"""Global Indicator 6 -- Global Producer Pressure.

GLOBAL_INFLATION_METHODS.md section 10 / CALCULATION_ENGINE_GUIDELINES.md
section 9.6.

Question answered: how strong are upstream inflation pressures across
producers, trade, commodities, energy, and logistics? GLOBAL guidelines
section 10.6: "This is a pressure score, not an inflation rate." Because
no single component is inherently the "headline" measure here and the
composite is explicitly a standardized score rather than a rate,
``value``/``unit`` are always ``None`` -- every number, including the
optional composite score, lives in ``components`` (mirroring how
:mod:`app.engines.country.housing` and
:mod:`app.engines.country.economy_wide` handle indicators with no single
defensible headline number).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.engines.shared.aggregation import weighted_arithmetic_mean
from app.engines.shared.coverage import build_coverage_report
from app.engines.shared.errors import DataQualityError
from app.engines.shared.growth import year_over_year
from app.engines.shared.standardization import composite_score, historical_mean_std, z_score
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance

INDICATOR_ID = "global_producer_pressure"
METHODOLOGY_VERSION = "1.0.0"


def calculate(
    *,
    country_ppi_rates: Mapping[str, float],
    gdp_ppp_weights: Mapping[str, float],
    country_import_rates: Mapping[str, float],
    import_share_weights: Mapping[str, float],
    commodity_rates: Mapping[str, float],
    commodity_weights: Mapping[str, float],
    all_geographies: tuple[str, ...],
    period: str,
    calculated_at: str,
    freight_index_current: float | None = None,
    freight_index_prior_year: float | None = None,
    composite_weights: Mapping[str, float] | None = None,
    standardization_windows: Mapping[str, Sequence[float]] | None = None,
    population_by_geo: Mapping[str, float] | None = None,
    gdp_ppp_by_geo: Mapping[str, float] | None = None,
    consumption_ppp_by_geo: Mapping[str, float] | None = None,
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    ppi_component = weighted_arithmetic_mean(country_ppi_rates, gdp_ppp_weights)
    import_component = weighted_arithmetic_mean(country_import_rates, import_share_weights)
    commodity_component = weighted_arithmetic_mean(commodity_rates, commodity_weights)

    components = [
        Component(key="ppi_component", label="Global PPI Component", value=ppi_component, unit=Unit.PERCENT_YOY),
        Component(key="import_component", label="Global Import-Price Component", value=import_component, unit=Unit.PERCENT_YOY),
        Component(
            key="commodity_component", label="Global Commodity Component", value=commodity_component, unit=Unit.PERCENT_YOY
        ),
    ]

    warnings: list[str] = []
    logistics_component = None
    if freight_index_current is not None and freight_index_prior_year is not None:
        logistics_component = year_over_year(freight_index_current, freight_index_prior_year)
        components.append(
            Component(key="logistics_component", label="Global Logistics Component", value=logistics_component, unit=Unit.PERCENT_YOY)
        )
    else:
        warnings.append(f"{INDICATOR_ID}: logistics_component unavailable (missing freight index data)")

    if composite_weights and standardization_windows and logistics_component is not None:
        try:
            raw = {
                "ppi": ppi_component,
                "import": import_component,
                "commodity": commodity_component,
                "logistics": logistics_component,
            }
            z_values = {
                key: _z(value, standardization_windows[key]) for key, value in raw.items() if key in standardization_windows
            }
            weights = {k: composite_weights[k] for k in z_values if k in composite_weights}
            if set(z_values) == set(weights):
                score = composite_score(z_values, weights)
                components.append(
                    Component(
                        key="composite_pressure_score",
                        label="Global Producer Pressure Score",
                        value=score,
                        unit=Unit.STANDARD_DEVIATION_SCORE,
                        is_score=True,
                    )
                )
        except DataQualityError as exc:
            warnings.append(f"composite_pressure_score unavailable: {exc.message}")

    coverage_report = build_coverage_report(
        all_geographies=all_geographies,
        included_geographies=set(country_ppi_rates) | set(country_import_rates),
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
        method="producer_pressure_components",
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
        metadata={"interpretation": "leading pressure indicator; pass-through to consumer prices is not automatic"},
    )


def _z(value: float, window: Sequence[float]) -> float:
    if len(window) < 2:
        raise DataQualityError("standardization window requires at least 2 historical values")
    mu, sigma = historical_mean_std(window)
    return z_score(value, mu, sigma)
