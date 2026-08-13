"""Pure aggregation and dispersion formulas.

Direct translations of CALCULATION_ENGINE_GUIDELINES.md section 7.5-7.8,
COUNTRY_INFLATION_METHODS.md section 3.5-3.7 and 5.3-5.4, and
GLOBAL_INFLATION_METHODS.md section 3.2-3.4, 6.2-6.3, and 12.4-12.5.

Values and weights are passed as ``Mapping[str, float]`` keyed by component
or country identifier rather than parallel lists. This makes the "must not
depend on input order" property (ENGINE guidelines section 15.2) trivially
true by construction — dict iteration order never participates in sorting
or summation order in a way that changes the floating-point result*, and
every function that needs "the smallest/first" value sorts explicitly by
value, never by key order.

(*) Summation order can, in principle, change floating-point rounding at
the last bit. The property tests assert equality within a numerical
tolerance, not bit-for-bit equality, which is what the methodology
documents mean by "must not depend on order."
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from decimal import Decimal

from app.engines.shared.errors import DataQualityError, InvalidWeightError
from app.engines.shared.validation import DEFAULT_WEIGHT_TOLERANCE, validate_weights


def _check_matching_keys(values: Mapping[str, float], weights: Mapping[str, float], *, context: str) -> None:
    value_keys, weight_keys = set(values), set(weights)
    if value_keys != weight_keys:
        raise InvalidWeightError(
            f"{context}: values and weights must cover the same keys",
            context=context,
            only_in_values=sorted(value_keys - weight_keys),
            only_in_weights=sorted(weight_keys - value_keys),
        )


def weighted_arithmetic_mean(
    values: Mapping[str, float],
    weights: Mapping[str, float],
    *,
    tolerance: float = DEFAULT_WEIGHT_TOLERANCE,
) -> float:
    """A = sum_i w_i x_i, subject to sum_i w_i = 1.

    ENGINE guidelines section 7.5 / COUNTRY section 3.5 / GLOBAL section
    3.2.
    """

    _check_matching_keys(values, weights, context="weighted_arithmetic_mean")
    validate_weights(weights, tolerance=tolerance, context="weighted_arithmetic_mean")
    # Decimal protects weight normalization/aggregation from binary-float
    # drift; the public numeric contract remains float at this boundary.
    return float(sum(Decimal(str(values[k])) * Decimal(str(weights[k])) for k in sorted(values)))


def weighted_geometric_mean_rates(
    rates_percent: Mapping[str, float],
    weights: Mapping[str, float],
    *,
    tolerance: float = DEFAULT_WEIGHT_TOLERANCE,
) -> float:
    """G = [prod_i (1 + x_i)^{w_i}] - 1, expressed in percent.

    ENGINE guidelines section 7.6. ``rates_percent`` are rates in percent
    (e.g. 3.2 for 3.2%); internally converted to decimals as the docs
    require ("Rates must be expressed as decimals inside the product.").
    """

    _check_matching_keys(rates_percent, weights, context="weighted_geometric_mean_rates")
    validate_weights(weights, tolerance=tolerance, context="weighted_geometric_mean_rates")
    product = 1.0
    for k, rate in rates_percent.items():
        base = 1 + rate / 100
        if base <= 0:
            raise DataQualityError(
                f"weighted_geometric_mean_rates: rate for {k!r} implies a non-positive "
                f"base (1 + rate/100 = {base})",
                component=k,
                rate=rate,
            )
        product *= base ** weights[k]
    return (product - 1) * 100


def weighted_geometric_price_relative(
    price_relatives: Mapping[str, float],
    weights: Mapping[str, float],
    *,
    tolerance: float = DEFAULT_WEIGHT_TOLERANCE,
) -> float:
    """G_t = prod_i (P_{i,t} / P_{i,0})^{w_i}.

    COUNTRY guidelines section 3.6 / GLOBAL guidelines section 3.3. Unlike
    :func:`weighted_geometric_mean_rates`, inputs here are price *relatives*
    (ratios such as 1.032), not growth rates, and the result is also a
    relative — the caller converts to a percent rate with
    ``(result - 1) * 100`` if needed (as GLOBAL guidelines section 3.3
    does explicitly for global period inflation).
    """

    _check_matching_keys(price_relatives, weights, context="weighted_geometric_price_relative")
    validate_weights(weights, tolerance=tolerance, context="weighted_geometric_price_relative")
    product = 1.0
    for k, relative in price_relatives.items():
        if relative <= 0:
            raise DataQualityError(
                f"weighted_geometric_price_relative: price relative for {k!r} must be "
                f"positive, got {relative}",
                component=k,
                relative=relative,
            )
        product *= relative ** weights[k]
    return product


def _sorted_by_value(values: Mapping[str, float]) -> list[tuple[str, float]]:
    return sorted(values.items(), key=lambda kv: kv[1])


def weighted_median(
    values: Mapping[str, float],
    weights: Mapping[str, float],
    *,
    tolerance: float = DEFAULT_WEIGHT_TOLERANCE,
) -> float:
    """The weighted median: sort ascending, return the first value m such
    that cumulative weight up to and including m is >= 0.5 and cumulative
    weight strictly before m is < 0.5.

    COUNTRY guidelines section 5.3 / GLOBAL guidelines section 6.3. This
    picks an existing data point; it never averages two values, which
    distinguishes it from :func:`unweighted_median`'s even-count handling.
    """

    _check_matching_keys(values, weights, context="weighted_median")
    validate_weights(weights, tolerance=tolerance, context="weighted_median")
    ordered = _sorted_by_value(values)
    cumulative = 0.0
    for key, value in ordered:
        cumulative_before = cumulative
        cumulative += weights[key]
        if cumulative >= 0.5 - 1e-12 and cumulative_before < 0.5 - 1e-12:
            return value
    # Floating point rounding could leave the last observation just under
    # 0.5 cumulative; the total is guaranteed ~1 by validate_weights, so
    # the last observation is always a safe fallback.
    return ordered[-1][1]


def unweighted_median(values: Sequence[float]) -> float:
    """The classical median: for even counts, the average of the two
    middle values; for odd counts, the single middle value.

    GLOBAL guidelines section 6.2.
    """

    if not values:
        raise DataQualityError("unweighted_median requires at least one value")
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def percentile(values: Sequence[float], p: float, *, method: str = "linear") -> float:
    """The p-th percentile (0 <= p <= 100) using linear interpolation
    between closest ranks (the "type 7" / Excel PERCENTILE.INC method).

    The methodology documents (GLOBAL guidelines section 6.5, 12.5) require
    25th/75th percentiles but do not specify an interpolation method;
    linear interpolation is the documented deviation recorded in
    Back-end/README.md.
    """

    if method != "linear":
        raise DataQualityError(f"Unsupported percentile method {method!r}")
    if not values:
        raise DataQualityError("percentile requires at least one value")
    if not 0 <= p <= 100:
        raise DataQualityError(f"percentile p must be within [0, 100], got {p}")
    ordered = sorted(values)
    n = len(ordered)
    if n == 1:
        return ordered[0]
    rank = (p / 100) * (n - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    fraction = rank - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def interquartile_range(values: Sequence[float]) -> float:
    """IQR = Q75 - Q25 (GLOBAL guidelines section 12.5)."""

    return percentile(values, 75) - percentile(values, 25)


def sample_mean(values: Sequence[float]) -> float:
    """Unweighted arithmetic mean (GLOBAL guidelines section 12.4)."""

    if not values:
        raise DataQualityError("sample_mean requires at least one value")
    return sum(values) / len(values)


def sample_std(values: Sequence[float]) -> float:
    """Sample standard deviation with Bessel's correction (divide by C-1).

    GLOBAL guidelines section 12.4: ``Dispersion_t = sqrt(sum((pi_c -
    mean)^2) / (C_t - 1))``.
    """

    n = len(values)
    if n < 2:
        raise DataQualityError(
            "sample_std requires at least two values (denominator is C - 1)", count=n
        )
    mean = sample_mean(values)
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return math.sqrt(variance)


def trimmed_mean(
    values: Mapping[str, float],
    weights: Mapping[str, float],
    *,
    alpha: float,
    beta: float,
    boundary_handling: str = "exclude_whole",
    tolerance: float = DEFAULT_WEIGHT_TOLERANCE,
) -> tuple[float, tuple[str, ...]]:
    """The weighted trimmed mean: sort ascending, drop the bottom alpha and
    top beta cumulative-weight mass, then take the weighted mean of what
    remains: sum_{i in R} w_i x_i / sum_{i in R} w_i.

    COUNTRY guidelines section 5.4. The docs do not specify how to handle
    a component whose weight straddles the alpha/(1-beta) boundary; this
    implementation supports two documented, deterministic policies
    (recorded as a deliberate deviation in Back-end/README.md):

    - ``"exclude_whole"`` (default): a component is retained only if its
      cumulative weight *before* it is already >= alpha and still <
      1 - beta. Straddling components are dropped entirely.
    - ``"clip"``: a component's weight is clipped to the portion that
      falls inside [alpha, 1 - beta] (Cleveland-Fed-style partial
      trimming), so a straddling component contributes partially.

    Returns ``(trimmed_mean_value, retained_keys)``.
    """

    if not 0 <= alpha < 1 or not 0 <= beta < 1 or alpha + beta >= 1:
        raise DataQualityError(
            f"trimmed_mean requires 0 <= alpha, beta and alpha + beta < 1, got "
            f"alpha={alpha}, beta={beta}"
        )
    _check_matching_keys(values, weights, context="trimmed_mean")
    validate_weights(weights, tolerance=tolerance, context="trimmed_mean")
    ordered = _sorted_by_value(values)
    upper_bound = 1 - beta

    retained_keys: list[str] = []
    retained_weight = 0.0
    weighted_sum = 0.0
    cumulative = 0.0

    for key, value in ordered:
        cum_before = cumulative
        w = weights[key]
        cum_after = cumulative + w
        cumulative = cum_after

        if boundary_handling == "exclude_whole":
            if cum_before >= alpha - 1e-12 and cum_before < upper_bound - 1e-12:
                retained_keys.append(key)
                retained_weight += w
                weighted_sum += w * value
        elif boundary_handling == "clip":
            overlap = min(cum_after, upper_bound) - max(cum_before, alpha)
            if overlap > 0:
                retained_keys.append(key)
                retained_weight += overlap
                weighted_sum += overlap * value
        else:
            raise DataQualityError(f"Unsupported trimmed_mean boundary_handling {boundary_handling!r}")

    if retained_weight <= 0:
        raise DataQualityError(
            "trimmed_mean: alpha/beta trimmed away all components",
            alpha=alpha,
            beta=beta,
        )
    return weighted_sum / retained_weight, tuple(retained_keys)


def laspeyres_price_index(
    prices_current: Mapping[str, float],
    prices_base: Mapping[str, float],
    quantities_base: Mapping[str, float],
) -> float:
    """A fixed-basket (Laspeyres) price index:

    Index_t = sum_i P_{i,t} Q_{i,0} / sum_i P_{i,0} Q_{i,0} * 100.

    This single formula is used twice in the methodology documents with
    identical structure: COUNTRY_INFLATION_METHODS.md section 7.3 (Fixed-
    Lifestyle Inflation) and section 6.5 (Essential Cost Inflation's
    price-level version) -- factored here so both engine modules share one
    tested implementation instead of two copies.
    """

    keys = set(prices_current) & set(prices_base) & set(quantities_base)
    all_keys = set(prices_current) | set(prices_base) | set(quantities_base)
    if not keys or keys != all_keys:
        raise DataQualityError(
            "laspeyres_price_index: prices_current, prices_base, and quantities_base "
            "must all cover exactly the same items",
            missing_or_mismatched=sorted(all_keys - keys),
        )
    numerator = sum(prices_current[k] * quantities_base[k] for k in keys)
    denominator = sum(prices_base[k] * quantities_base[k] for k in keys)
    if denominator <= 0:
        raise DataQualityError(
            f"laspeyres_price_index: base-period basket value must be positive, got {denominator}"
        )
    return (numerator / denominator) * 100


def chain_step(previous_level: float, period_relative: float) -> float:
    """GPI_t = GPI_{t-1} * R^G_t, one step of the chain-linked index
    (GLOBAL guidelines section 3.4)."""

    if period_relative <= 0:
        raise DataQualityError(
            f"chain_step: period relative must be positive, got {period_relative}"
        )
    return float(Decimal(str(previous_level)) * Decimal(str(period_relative)))


def chain_linked_index(period_relatives: Sequence[float], *, base: float = 100.0) -> list[float]:
    """Build a full chain-linked index series: GPI_0 = base, GPI_t =
    GPI_{t-1} * R^G_t for each relative in ``period_relatives``.

    Returns a list of length ``len(period_relatives) + 1`` starting with
    ``base``.
    """

    levels = [base]
    for relative in period_relatives:
        levels.append(chain_step(levels[-1], relative))
    return levels
