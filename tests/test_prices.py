"""Tests for the pure price logic (no Home Assistant needed)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

_PATH = Path(__file__).parents[1] / "custom_components" / "rabot_energy" / "prices.py"
_spec = importlib.util.spec_from_file_location("rabot_prices", _PATH)
assert _spec and _spec.loader
prices = importlib.util.module_from_spec(_spec)
sys.modules["rabot_prices"] = prices  # dataclasses need the module registered
_spec.loader.exec_module(prices)


def _record(moment: str, gross_cent: float) -> SimpleNamespace:
    return SimpleNamespace(moment=moment, price_gross_in_cent_per_kwh=gross_cent)


def _preview(*records: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(records=list(records))


def at(hour: int, minute: int = 0, second: int = 0) -> datetime:
    """A moment on 12 Oct 2026 in UTC."""
    return datetime(2026, 10, 12, hour, minute, second, tzinfo=UTC)


# hourly, deliberately out of order; the API sends UTC with milliseconds
PREVIEW = _preview(
    _record("2026-10-12T09:00:00.000Z", 27.5),
    _record("2026-10-12T08:00:00.000Z", 30.0),
    _record("2026-10-12T10:00:00.000Z", 24.0),
)


def test_parse_sorts_converts_units_and_derives_ends() -> None:
    slots = prices.parse_slots(PREVIEW)
    assert [s.start for s in slots] == [at(8), at(9), at(10)]
    assert [s.end for s in slots] == [at(9), at(10), at(11)]  # last copies the spacing
    assert slots[0].gross == pytest.approx(0.30)  # 30.0 ct/kWh -> 0.30 EUR/kWh


def test_parse_handles_fractional_seconds() -> None:
    slots = prices.parse_slots(_preview(_record("2026-10-12T10:28:00.269Z", 20.0)))
    assert slots[0].start == datetime(2026, 10, 12, 10, 28, 0, 269000, tzinfo=UTC)
    assert slots[0].end - slots[0].start == prices.FALLBACK_SLOT_LENGTH  # single record


def test_parse_quarter_hour_spacing_is_kept() -> None:
    slots = prices.parse_slots(
        _preview(
            _record("2026-10-12T10:00:00Z", 20.0),
            _record("2026-10-12T10:15:00Z", 21.0),
            _record("2026-10-12T10:30:00Z", 22.0),
        )
    )
    assert slots[-1].end - slots[-1].start == timedelta(minutes=15)


def test_parse_empty_preview() -> None:
    assert prices.parse_slots(_preview()) == []


def test_parse_time_without_zone_is_utc() -> None:
    """The service sends "2026-10-13 07:30" without a zone; it is read as UTC."""
    slots = prices.parse_slots(
        _preview(_record("2026-10-12 10:00", 20.0), _record("2026-10-12 10:15", 21.0))
    )
    assert slots[0].start == at(10)
    assert slots[0].end == at(10, 15)


def test_parse_keeps_an_explicit_offset() -> None:
    slots = prices.parse_slots(_preview(_record("2026-10-12T12:00:00+02:00", 20.0)))
    assert slots[0].start == at(10)


def test_parse_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        prices.parse_slots(_preview(_record("yesterday", 20.0)))


def test_current_slot_boundaries() -> None:
    slots = prices.parse_slots(PREVIEW)
    assert prices.current_slot(slots, at(8)).gross == pytest.approx(0.30)
    assert prices.current_slot(slots, at(8, 59, 59)).gross == pytest.approx(0.30)
    # the end is exclusive: 09:00 belongs to the next slot
    assert prices.current_slot(slots, at(9)).gross == pytest.approx(0.275)
    assert prices.current_slot(slots, at(7, 59)) is None
    assert prices.current_slot(slots, at(11)) is None


def test_current_slot_compares_across_time_zones() -> None:
    slots = prices.parse_slots(PREVIEW)
    # 10:30 at +02:00 is 08:30 UTC
    local = datetime(2026, 10, 12, 10, 30, tzinfo=timezone(timedelta(hours=2)))
    assert prices.current_slot(slots, local).gross == pytest.approx(0.30)


def test_next_slot() -> None:
    slots = prices.parse_slots(PREVIEW)
    assert prices.next_slot(slots, at(8, 30)).gross == pytest.approx(0.275)
    assert prices.next_slot(slots, at(10, 30)) is None


def test_lowest_and_highest_ignore_past_slots() -> None:
    slots = prices.parse_slots(PREVIEW)
    assert prices.lowest_slot(slots, at(8, 30)).gross == pytest.approx(0.24)
    assert prices.highest_slot(slots, at(8, 30)).gross == pytest.approx(0.30)
    # at 09:30 the 0.30 slot is over, so the highest is the 0.275 slot
    assert prices.highest_slot(slots, at(9, 30)).gross == pytest.approx(0.275)


def test_extremes_empty_when_everything_is_past() -> None:
    slots = prices.parse_slots(PREVIEW)
    late = datetime(2026, 10, 13, tzinfo=UTC)
    assert prices.lowest_slot(slots, late) is None
    assert prices.highest_slot(slots, late) is None


def test_dst_change_day_has_no_ambiguity_because_moments_are_utc() -> None:
    """On 25 Oct 2026 clocks go back; UTC moments keep every slot exactly one hour."""
    slots = prices.parse_slots(
        _preview(
            _record("2026-10-24T22:00:00Z", 20.0),  # 00:00 CEST
            _record("2026-10-24T23:00:00Z", 21.0),  # 01:00 CEST
            _record("2026-10-25T00:00:00Z", 22.0),  # 02:00 CEST
            _record("2026-10-25T01:00:00Z", 23.0),  # 02:00 CET (second 02:xx hour)
        )
    )
    assert {s.end - s.start for s in slots} == {timedelta(hours=1)}
    now = datetime(2026, 10, 25, 1, 30, tzinfo=UTC)
    assert prices.current_slot(slots, now).gross == pytest.approx(0.23)
