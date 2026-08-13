"""Controlled vocabularies shared across the engine and API.

Every enum here corresponds to a controlled identifier list defined in the
methodology documents. Using free-form strings anywhere these enums apply
would allow silent typos or undocumented units to slip into a calculation,
which CALCULATION_ENGINE_GUIDELINES.md section 5.2 explicitly forbids.
"""

from __future__ import annotations

from enum import Enum


class Frequency(str, Enum):
    """Supported observation frequencies (ENGINE guidelines section 6.1)."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


# Lag (in native periods) used for a year-over-year comparison at each
# frequency, per ENGINE guidelines section 7.1 (k=12 monthly, k=4 quarterly,
# k=1 annual). Daily/weekly are not covered by the YoY formula in the docs;
# callers must choose an explicit horizon for those frequencies.
YOY_LAG_BY_FREQUENCY: dict[Frequency, int] = {
    Frequency.MONTHLY: 12,
    Frequency.QUARTERLY: 4,
    Frequency.ANNUAL: 1,
}

# Number of periods per year, used for annualization exponents (ENGINE
# guidelines section 7.3): m=12 monthly, m=4 quarterly.
PERIODS_PER_YEAR: dict[Frequency, int] = {
    Frequency.MONTHLY: 12,
    Frequency.QUARTERLY: 4,
    Frequency.ANNUAL: 1,
}


class Unit(str, Enum):
    """Controlled unit identifiers (ENGINE guidelines section 5.1)."""

    INDEX = "index"
    PERCENT_YOY = "percent_yoy"
    PERCENT_MOM = "percent_mom"
    PERCENT_ANNUALIZED = "percent_annualized"
    CURRENCY = "currency"
    CURRENCY_PER_UNIT = "currency_per_unit"
    LOCAL_CURRENCY = "local_currency"
    PERSONS = "persons"
    HOUSEHOLDS = "households"
    RATIO = "ratio"
    SHARE_PERCENT = "share_percent"
    STANDARD_DEVIATION_SCORE = "standard_deviation_score"


class Confidence(str, Enum):
    """Suggested confidence levels (ENGINE guidelines section 14.1)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Coverage(str, Enum):
    """Coverage labels (ENGINE guidelines section 10.2)."""

    FULL = "full"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class ValidationStatus(str, Enum):
    """Normalized-observation validation status (ENGINE guidelines section 4)."""

    VALIDATED = "validated"
    PENDING = "pending"
    REJECTED = "rejected"
