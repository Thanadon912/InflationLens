"""Z-scores and composite pressure scores.

CALCULATION_ENGINE_GUIDELINES.md section 19 and COUNTRY/GLOBAL guidelines
sections 16/19 all define the same two-step construction: standardize a
value against a historical window, then take a weighted sum of z-scores.
The result is a *score*, not an inflation rate (ENGINE guidelines section
19 prohibits presenting a composite as an objectively true rate), which is
why every score-producing engine function must set
``Component.is_score=True`` and ``unit=Unit.STANDARD_DEVIATION_SCORE`` on
its output (enforced by ``Component.__post_init__``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.engines.shared.aggregation import sample_mean, sample_std
from app.engines.shared.errors import DataQualityError
from app.engines.shared.validation import DEFAULT_WEIGHT_TOLERANCE, validate_weights


def historical_mean_std(window: Sequence[float]) -> tuple[float, float]:
    """Return (mu, sigma) for a documented historical standardization
    window, using the sample standard deviation (divide by n-1), matching
    GLOBAL guidelines section 12.4's dispersion convention.
    """

    return sample_mean(window), sample_std(window)


def z_score(x: float, mu: float, sigma: float) -> float:
    """z = (x - mu) / sigma (ENGINE guidelines section 7.8)."""

    if sigma == 0:
        raise DataQualityError("z_score: sigma (standard deviation) must not be zero")
    return (x - mu) / sigma


def composite_score(
    z_values: Mapping[str, float],
    weights: Mapping[str, float],
    *,
    tolerance: float = DEFAULT_WEIGHT_TOLERANCE,
) -> float:
    """Score = sum_i w_i z_i, subject to sum_i w_i = 1.

    ENGINE guidelines section 19.2 / COUNTRY guidelines section 16.2 /
    GLOBAL guidelines section 16.2.
    """

    keys = set(z_values)
    if keys != set(weights):
        raise DataQualityError(
            "composite_score: z_values and weights must cover the same components",
            only_in_z_values=sorted(keys - set(weights)),
            only_in_weights=sorted(set(weights) - keys),
        )
    validate_weights(weights, tolerance=tolerance, context="composite_score")
    return sum(z_values[k] * weights[k] for k in z_values)
