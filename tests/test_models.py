"""Tests for the library models and the conversion of a full response (no Home Assistant)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).parents[1] / "custom_components" / "rabot_energy"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses need the module registered
    spec.loader.exec_module(module)
    return module


models = _load("rabot_models", _ROOT / "_lib" / "models.py")
prices = _load("rabot_prices_for_models", _ROOT / "prices.py")

# Shape of GetAverageEnergyPricesResponse from the service spec.
RESPONSE = {
    "records": [
        {"moment": "2026-10-12 10:00", "priceGross_inCentPerKwh": {"value": 27.5}},
        {"moment": "2026-10-12 10:15", "priceGross_inCentPerKwh": None},
        {"moment": "2026-10-12 10:30", "priceGross_inCentPerKwh": {"value": 30}},
    ],
    "baseProviderWorkingPriceGross_inCentPerKwh": {"value": 35.1},
    "priceCap": {
        "durationMonths": 12,
        "maxEffectiveWorkingPriceGross_inCentPerKwh": {"value": 40.0},
    },
    "contractNumber": "1000123456",
}


def test_record_price_is_nullable() -> None:
    records = models.PricePreview(RESPONSE).records
    assert [r.price_gross_in_cent_per_kwh for r in records] == [27.5, None, 30.0]
    assert records[0].moment == "2026-10-12 10:00"


def test_record_price_with_null_value() -> None:
    record = models.PriceRecord({"moment": "x", "priceGross_inCentPerKwh": {"value": None}})
    assert record.price_gross_in_cent_per_kwh is None


def test_price_cap_uses_the_new_keys() -> None:
    preview = models.PricePreview(RESPONSE)
    assert preview.price_cap_duration_in_months == 12
    assert preview.max_effective_working_price_in_cent_per_kwh_gross == pytest.approx(40.0)
    assert preview.base_provider_working_price_in_cent_per_kwh_gross == pytest.approx(35.1)


def test_old_price_cap_keys_are_ignored() -> None:
    preview = models.PricePreview(
        {
            "records": [],
            "priceCap": {
                "priceCapDuration_InMonths": 12,
                "maxEffectiveWorkingPrice_InCentPerKwh_Gross": {"value": 40.0},
            },
        }
    )
    assert preview.price_cap_duration_in_months is None
    assert preview.max_effective_working_price_in_cent_per_kwh_gross is None


def test_nullable_top_level_fields() -> None:
    preview = models.PricePreview(
        {"records": [], "priceCap": None, "baseProviderWorkingPriceGross_inCentPerKwh": None}
    )
    assert preview.price_cap_duration_in_months is None
    assert preview.max_effective_working_price_in_cent_per_kwh_gross is None
    assert preview.base_provider_working_price_in_cent_per_kwh_gross is None


def test_is_contract_data_was_removed() -> None:
    assert not hasattr(models.PricePreview, "is_contract_data")


def test_parse_preview_converts_everything_to_eur() -> None:
    data = prices.parse_preview(models.PricePreview(RESPONSE))
    assert [s.start for s in data.slots] == [
        datetime(2026, 10, 12, 10, 0, tzinfo=UTC),
        datetime(2026, 10, 12, 10, 30, tzinfo=UTC),
    ]
    assert data.slots[0].gross == pytest.approx(0.275)
    assert data.base_provider_gross == pytest.approx(0.351)
    assert data.price_cap_gross == pytest.approx(0.40)
    assert data.price_cap_duration_months == 12


def test_parse_preview_without_cap() -> None:
    data = prices.parse_preview(models.PricePreview({"records": [], "priceCap": None}))
    assert data.slots == []
    assert data.price_cap_gross is None
    assert data.price_cap_duration_months is None
    assert data.base_provider_gross is None


def test_contract_number_from_response() -> None:
    assert models.PricePreview(RESPONSE).contract_number == "1000123456"
    # null from older service releases
    assert models.PricePreview({"records": [], "contractNumber": None}).contract_number is None
    assert models.PricePreview({"records": []}).contract_number is None


def test_backend_fixture_parses_as_utc() -> None:
    """The exact 200 fixture of the service: UTC moment without a zone, null extras."""
    fixture = {
        "records": [{"moment": "2026-11-10 13:00", "priceGross_inCentPerKwh": {"value": 31.25}}],
        "baseProviderWorkingPriceGross_inCentPerKwh": None,
        "priceCap": None,
        "contractNumber": "1000123456",
    }
    data = prices.parse_preview(models.PricePreview(fixture))
    assert data.slots[0].start == datetime(2026, 11, 10, 13, 0, tzinfo=UTC)
    assert data.slots[0].end == datetime(2026, 11, 10, 13, 15, tzinfo=UTC)
    assert data.slots[0].gross == pytest.approx(0.3125)
    assert data.base_provider_gross is None
    assert data.price_cap_gross is None
