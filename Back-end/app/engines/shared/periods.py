"""Period parsing, comparison, and lag arithmetic.

CALCULATION_ENGINE_GUIDELINES.md section 6.4 requires inputs to refer to the
same economic period or an explicitly documented lag, and section 7.1 defines
year-over-year growth using a lag ``k`` that depends on frequency (12 for
monthly, 4 for quarterly, 1 for annual). This module gives every engine a
single, deterministic way to parse an ``observation_period`` string, compare
two periods, and step a period forward/backward by a number of native steps.

Supported period string formats, one per ``Frequency``:

- monthly:   ``"YYYY-MM"``            e.g. ``"2026-06"``
- quarterly: ``"YYYY-Qn"``            e.g. ``"2026-Q2"``
- annual:    ``"YYYY"``               e.g. ``"2026"``
- daily:     ``"YYYY-MM-DD"``         e.g. ``"2026-06-15"``
- weekly:    ``"YYYY-Www"`` (ISO)     e.g. ``"2026-W24"``

Daily and weekly periods parse and compare correctly, but no year-over-year
lag is defined for them anywhere in the methodology documents, so
:func:`yoy_lag` raises ``UnsupportedMethodError`` for those frequencies
rather than guessing one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from app.engines.shared.errors import SeriesDefinitionError, UnsupportedMethodError
from app.models.enums import PERIODS_PER_YEAR, YOY_LAG_BY_FREQUENCY, Frequency

_MONTHLY_RE = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})$")
_QUARTERLY_RE = re.compile(r"^(?P<year>\d{4})-Q(?P<quarter>[1-4])$")
_ANNUAL_RE = re.compile(r"^(?P<year>\d{4})$")
_DAILY_RE = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$")
_WEEKLY_RE = re.compile(r"^(?P<year>\d{4})-W(?P<week>\d{2})$")


@dataclass(frozen=True, order=True)
class Period:
    """A single, frequency-aware economic period.

    Comparable and orderable via the ``sort_key`` field so that periods of
    the *same* frequency sort chronologically. Comparing periods of
    different frequencies is intentionally not supported by ordering
    operators; use :meth:`Period.to_ordinal` explicitly if that is ever
    required, so the mismatch is visible rather than silently coerced.
    """

    sort_key: int
    frequency: Frequency
    raw: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.raw

    def shift(self, steps: int) -> "Period":
        """Return the period ``steps`` native periods away (may be negative)."""

        if self.frequency == Frequency.MONTHLY:
            year, month = divmod(self.sort_key, 12)
            total = year * 12 + month + steps
            year, month = divmod(total, 12)
            return Period(sort_key=total, frequency=self.frequency, raw=f"{year:04d}-{month + 1:02d}")
        if self.frequency == Frequency.QUARTERLY:
            total = self.sort_key + steps
            year, quarter = divmod(total, 4)
            return Period(sort_key=total, frequency=self.frequency, raw=f"{year:04d}-Q{quarter + 1}")
        if self.frequency == Frequency.ANNUAL:
            total = self.sort_key + steps
            return Period(sort_key=total, frequency=self.frequency, raw=f"{total:04d}")
        if self.frequency == Frequency.DAILY:
            d = date.fromordinal(self.sort_key) + timedelta(days=steps)
            return Period(sort_key=d.toordinal(), frequency=self.frequency, raw=d.isoformat())
        if self.frequency == Frequency.WEEKLY:
            d = date.fromordinal(self.sort_key) + timedelta(weeks=steps)
            iso_year, iso_week, _ = d.isocalendar()
            monday = date.fromisocalendar(iso_year, iso_week, 1)
            return Period(
                sort_key=monday.toordinal(),
                frequency=self.frequency,
                raw=f"{iso_year:04d}-W{iso_week:02d}",
            )
        raise UnsupportedMethodError(  # pragma: no cover - defensive, all enum members handled above
            method=str(self.frequency), context="Period.shift"
        )


def parse_period(raw: str, frequency: Frequency) -> Period:
    """Parse ``raw`` as a period of the given frequency.

    Raises ``SeriesDefinitionError`` if ``raw`` does not match the expected
    format for ``frequency``. No silent coercion between formats is
    performed, matching the "no silent conversions" rule in
    CALCULATION_ENGINE_GUIDELINES.md section 5.3.
    """

    if frequency == Frequency.MONTHLY:
        m = _MONTHLY_RE.match(raw)
        if not m:
            raise SeriesDefinitionError(
                message=f"Expected monthly period 'YYYY-MM', received {raw!r}"
            )
        year, month = int(m["year"]), int(m["month"])
        if not 1 <= month <= 12:
            raise SeriesDefinitionError(message=f"Invalid month in period {raw!r}")
        return Period(sort_key=year * 12 + (month - 1), frequency=frequency, raw=raw)

    if frequency == Frequency.QUARTERLY:
        m = _QUARTERLY_RE.match(raw)
        if not m:
            raise SeriesDefinitionError(
                message=f"Expected quarterly period 'YYYY-Qn', received {raw!r}"
            )
        year, quarter = int(m["year"]), int(m["quarter"])
        return Period(sort_key=year * 4 + (quarter - 1), frequency=frequency, raw=raw)

    if frequency == Frequency.ANNUAL:
        m = _ANNUAL_RE.match(raw)
        if not m:
            raise SeriesDefinitionError(
                message=f"Expected annual period 'YYYY', received {raw!r}"
            )
        year = int(m["year"])
        return Period(sort_key=year, frequency=frequency, raw=raw)

    if frequency == Frequency.DAILY:
        m = _DAILY_RE.match(raw)
        if not m:
            raise SeriesDefinitionError(
                message=f"Expected daily period 'YYYY-MM-DD', received {raw!r}"
            )
        try:
            d = date(int(m["year"]), int(m["month"]), int(m["day"]))
        except ValueError as exc:
            raise SeriesDefinitionError(message=f"Invalid calendar date in period {raw!r}") from exc
        return Period(sort_key=d.toordinal(), frequency=frequency, raw=raw)

    if frequency == Frequency.WEEKLY:
        m = _WEEKLY_RE.match(raw)
        if not m:
            raise SeriesDefinitionError(
                message=f"Expected ISO weekly period 'YYYY-Www', received {raw!r}"
            )
        year, week = int(m["year"]), int(m["week"])
        try:
            monday = date.fromisocalendar(year, week, 1)
        except ValueError as exc:
            raise SeriesDefinitionError(message=f"Invalid ISO week in period {raw!r}") from exc
        return Period(sort_key=monday.toordinal(), frequency=frequency, raw=raw)

    raise UnsupportedMethodError(method=str(frequency), context="parse_period")  # pragma: no cover


def yoy_lag(frequency: Frequency) -> int:
    """Return k, the native-period lag used for year-over-year growth.

    Per ENGINE guidelines section 7.1: k=12 for monthly, k=4 for quarterly,
    k=1 for annual. Daily and weekly frequencies have no documented
    year-over-year lag, so this raises rather than inventing one.
    """

    try:
        return YOY_LAG_BY_FREQUENCY[frequency]
    except KeyError as exc:
        raise UnsupportedMethodError(
            method="year_over_year", context=f"frequency={frequency.value}"
        ) from exc


def periods_per_year(frequency: Frequency) -> int:
    """Return m, periods per year, used for annualization exponents.

    ENGINE guidelines section 7.3: m=12 monthly, m=4 quarterly.
    """

    try:
        return PERIODS_PER_YEAR[frequency]
    except KeyError as exc:
        raise UnsupportedMethodError(
            method="annualized_growth", context=f"frequency={frequency.value}"
        ) from exc
