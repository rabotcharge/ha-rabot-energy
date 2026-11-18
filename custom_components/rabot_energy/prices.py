"""Turn the library's price preview into slots and derived values.

This module is deliberately free of Home Assistant imports so it can be tested on its
own. The library models mirror the API and convert nothing; every conversion and every
derived value lives here:

- the API sends one `moment` per record (quarter-hourly) and prices in cent per kWh, so
  slot ends are derived from the next record and prices are converted to EUR per kWh;
- the current slot, the next slot and the extremes are computed from the cached data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._lib import PricePreview

# Used for the end of the last slot when there is no earlier record to copy the spacing
# from. The API sends quarter-hourly records.
FALLBACK_SLOT_LENGTH = timedelta(minutes=15)


@dataclass(frozen=True)
class PriceSlot:
    """One price slot with timezone-aware times and prices in EUR per kWh."""

    start: datetime
    end: datetime
    gross: float


@dataclass(frozen=True)
class PriceData:
    """Everything the sensors need from one API response, in EUR per kWh."""

    slots: list[PriceSlot]
    base_provider_gross: float | None = None
    price_cap_gross: float | None = None
    price_cap_duration_months: int | None = None


def _parse_moment(value: str) -> datetime:
    """Parse an ISO 8601 date-time such as "2026-10-13T07:30:00Z".

    Timestamps that carry a zone are taken as they are. Older responses sent no zone
    ("2026-10-13 07:30"); those are read as UTC, which the data backs up (a day's last
    record is "21:45", which is 23:45 in Berlin summer time).
    """
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _eur(cent: float | None) -> float | None:
    """Convert cent to EUR, keeping None."""
    return None if cent is None else cent / 100


def parse_slots(preview: PricePreview) -> list[PriceSlot]:
    """Return slots sorted by start time, with ends derived from the next record.

    Records without a price are skipped, but their moment still ends the slot before,
    so a missing price leaves a gap instead of stretching the previous slot. The last
    slot lasts as long as the spacing before it. Raises ValueError (or KeyError /
    TypeError) when the payload is not as expected; the coordinator turns those into
    an update failure.
    """
    records = sorted(
        ((_parse_moment(r.moment), r.price_gross_in_cent_per_kwh) for r in preview.records),
        key=lambda item: item[0],
    )
    slots: list[PriceSlot] = []
    for index, (start, gross_cent) in enumerate(records):
        if gross_cent is None:
            continue
        if index + 1 < len(records):
            end = records[index + 1][0]
        elif index > 0:
            end = start + (start - records[index - 1][0])
        else:
            end = start + FALLBACK_SLOT_LENGTH
        slots.append(PriceSlot(start=start, end=end, gross=gross_cent / 100))
    return slots


def parse_preview(preview: PricePreview) -> PriceData:
    """Return the slots plus the contract-level prices of one response."""
    return PriceData(
        slots=parse_slots(preview),
        base_provider_gross=_eur(preview.base_provider_working_price_in_cent_per_kwh_gross),
        price_cap_gross=_eur(preview.max_effective_working_price_in_cent_per_kwh_gross),
        price_cap_duration_months=preview.price_cap_duration_in_months,
    )


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
