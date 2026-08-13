"""A homogeneous, ordered collection of observations for one logical series.

``ObservationSeries`` enforces the invariants the methodology documents
assume are already true before a formula runs: one geography, one
indicator, one frequency, one unit, no duplicate periods, and periods
sorted chronologically. It also implements the disclosure half of
CALCULATION_ENGINE_GUIDELINES.md section 8.1 ("periods must be continuous
or gaps disclosed") via :meth:`ObservationSeries.gaps`.

It deliberately does *not* compute growth rates itself — that stays in
``app.engines.shared.growth`` so the pure math can be tested and reused
independently of how observations are stored.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from app.engines.shared.errors import SeriesDefinitionError
from app.engines.shared.periods import Period
from app.models.enums import Frequency, Unit
from app.models.observation import Observation


class ObservationSeries:
    """An immutable, period-sorted, de-duplicated series of observations."""

    def __init__(self, observations: Sequence[Observation]):
        if not observations:
            raise SeriesDefinitionError("ObservationSeries requires at least one observation")

        first = observations[0]
        for obs in observations:
            if obs.indicator_id != first.indicator_id:
                raise SeriesDefinitionError(
                    "ObservationSeries mixes indicator_id values",
                    indicator_ids={obs.indicator_id, first.indicator_id},
                )
            if obs.geography != first.geography:
                raise SeriesDefinitionError(
                    "ObservationSeries mixes geography values",
                    geographies={obs.geography, first.geography},
                )
            if obs.frequency != first.frequency:
                raise SeriesDefinitionError(
                    "ObservationSeries mixes frequency values",
                    frequencies={obs.frequency.value, first.frequency.value},
                    indicator=first.indicator_id,
                )
            if obs.unit != first.unit:
                raise SeriesDefinitionError(
                    "ObservationSeries mixes unit values",
                    units={obs.unit.value, first.unit.value},
                    indicator=first.indicator_id,
                )

        ordered = sorted(observations, key=lambda o: o.period.sort_key)
        seen: dict[int, Observation] = {}
        for obs in ordered:
            key = obs.period.sort_key
            if key in seen:
                raise SeriesDefinitionError(
                    "ObservationSeries has duplicate observation_period",
                    period=obs.observation_period,
                    indicator=first.indicator_id,
                    geography=first.geography,
                )
            seen[key] = obs

        self._observations: tuple[Observation, ...] = tuple(ordered)
        self._by_sort_key: dict[int, Observation] = seen

    # -- identity -----------------------------------------------------
    @property
    def indicator_id(self) -> str:
        return self._observations[0].indicator_id

    @property
    def geography(self) -> str:
        return self._observations[0].geography

    @property
    def frequency(self) -> Frequency:
        return self._observations[0].frequency

    @property
    def unit(self) -> Unit:
        return self._observations[0].unit

    # -- access ---------------------------------------------------------
    def __len__(self) -> int:
        return len(self._observations)

    def __iter__(self) -> Iterator[Observation]:
        return iter(self._observations)

    @property
    def latest(self) -> Observation:
        return self._observations[-1]

    @property
    def earliest(self) -> Observation:
        return self._observations[0]

    def get_at(self, period: Period) -> Observation | None:
        """Return the observation at exactly ``period``, or ``None``."""

        return self._by_sort_key.get(period.sort_key)

    def get_lagged(self, reference: Period, lag: int) -> Observation | None:
        """Return the observation ``lag`` native periods before ``reference``."""

        return self.get_at(reference.shift(-lag))

    def periods(self) -> list[str]:
        return [obs.observation_period for obs in self._observations]

    # -- quality ----------------------------------------------------------
    def gaps(self) -> list[Period]:
        """Return the list of periods missing between the earliest and
        latest observation (exclusive of ends already present).

        An empty list means the series is continuous, satisfying the
        "periods must be continuous" half of ENGINE guidelines section
        8.1; a non-empty list is what "gaps disclosed" refers to.
        """

        missing: list[Period] = []
        start = self.earliest.period
        end = self.latest.period
        cursor = start
        while cursor.sort_key < end.sort_key:
            cursor = cursor.shift(1)
            if cursor.sort_key not in self._by_sort_key and cursor.sort_key != end.sort_key:
                missing.append(cursor)
        return missing

    def has_gaps(self) -> bool:
        return bool(self.gaps())
