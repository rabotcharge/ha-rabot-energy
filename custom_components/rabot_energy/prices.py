"""Turn the library's price preview into slots and derived values.

This module is deliberately free of Home Assistant imports so it can be tested on its
own. The library models mirror the API and convert nothing; every conversion and every
derived value lives here:

- the API sends one `moment` per record and prices in cent per kWh, so slot ends are
  derived from the next record and prices are converted to EUR per kWh;
- the current slot, the next slot and the extremes are computed from the cached data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._lib import PricePreview

# Used for the end of the last slot when there is no earlier spacing to copy.
# ASSUMPTION: hourly. Revisit once the real resolution of the endpoint is confirmed.
FALLBACK_SLOT_LENGTH = timedelta(hours=1)


@dataclass(frozen=True)
class PriceSlot:
    """One price slot with timezone-aware times and prices in EUR per kWh."""

    start: datetime
    end: datetime
    gross: float


def _parse_moment(value: str) -> datetime:
    """Parse a timestamp such as "2026-10-13 07:30" or "2026-10-13T07:30:00Z".

    The service sends no time zone ("2026-10-13 07:30"). ASSUMPTION: that is UTC. The
    data backs this up: a day's last record is "21:45", which is 23:45 in Berlin summer
    time, and the price peaks line up with the earlier ISO feed that carried "Z".
    Confirm with the backend team; this is the only place to change if it is local time.
    Timestamps that do carry a zone are taken as they are.
    """
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def parse_slots(preview: PricePreview) -> list[PriceSlot]:
    """Return slots sorted by start time, with ends derived from the next record.

    The last slot lasts as long as the one before it. Raises ValueError (or KeyError /
    TypeError) when the payload is not as expected; the coordinator turns those into
    an update failure.
    """
    records = sorted(
        ((_parse_moment(r.moment), r) for r in preview.records),
        key=lambda item: item[0],
    )
    slots: list[PriceSlot] = []
    for index, (start, record) in enumerate(records):
        if index + 1 < len(records):
            end = records[index + 1][0]
        elif slots:
            end = start + (slots[-1].end - slots[-1].start)
        else:
            end = start + FALLBACK_SLOT_LENGTH
        slots.append(
            PriceSlot(
                start=start,
                end=end,
                gross=record.price_gross_in_cent_per_kwh / 100,
            )
        )
    return slots


def current_slot(slots: list[PriceSlot], now: datetime) -> PriceSlot | None:
    """Return the slot that contains `now`, if any."""
    for slot in slots:
        if slot.start <= now < slot.end:
            return slot
    return None


def next_slot(slots: list[PriceSlot], now: datetime) -> PriceSlot | None:
    """Return the first slot that starts after `now`, if any."""
    for slot in slots:
        if slot.start > now:
            return slot
    return None


def upcoming(slots: list[PriceSlot], now: datetime) -> list[PriceSlot]:
    """Return the current and all later slots."""
    return [slot for slot in slots if slot.end > now]


def lowest_slot(slots: list[PriceSlot], now: datetime) -> PriceSlot | None:
    """Return the cheapest current-or-later slot by gross price."""
    candidates = upcoming(slots, now)
    return min(candidates, key=lambda slot: slot.gross) if candidates else None


def highest_slot(slots: list[PriceSlot], now: datetime) -> PriceSlot | None:
    """Return the most expensive current-or-later slot by gross price."""
    candidates = upcoming(slots, now)
    return max(candidates, key=lambda slot: slot.gross) if candidates else None
