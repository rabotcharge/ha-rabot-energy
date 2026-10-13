"""Data models.

They mirror the API response (GET .../energy-prices/average?contractId=...) and do no
conversion: the moment stays a string (for example "2026-10-13 07:30") and prices stay
in cent per kWh, exactly as sent. Time zones, slot lengths and unit changes are the
integration's job.
"""

from __future__ import annotations

from typing import Any


def _value(raw: dict[str, Any], key: str) -> float | None:
    """Return raw[key]["value"] as a float, or None when the key is missing."""
    item = raw.get(key)
    if item is None:
        return None
    return float(item["value"])


class PriceRecord:
    """One price at one moment."""

    def __init__(self, raw_data: dict[str, Any]) -> None:
        """Wrap the raw JSON object of one record."""
        self.raw_data = raw_data

    @property
    def moment(self) -> str:
        """Return the moment the price starts to apply, as sent (a string)."""
        return str(self.raw_data["moment"])

    @property
    def price_gross_in_cent_per_kwh(self) -> float:
        """Return the gross price in cent per kWh."""
        return float(self.raw_data["priceGross_inCentPerKwh"]["value"])

    @property
    def price_net_in_cent_per_kwh(self) -> float | None:
        """Return the net price in cent per kWh, if sent."""
        return _value(self.raw_data, "priceNet_inCentPerKwh")


class PricePreview:
    """The price preview for one contract (up to 72 hours)."""

    def __init__(self, raw_data: dict[str, Any]) -> None:
        """Wrap the raw JSON object of the response."""
        self.raw_data = raw_data

    @property
    def records(self) -> list[PriceRecord]:
        """Return all records in the order the API sent them."""
        return [PriceRecord(item) for item in self.raw_data["records"]]

    @property
    def is_contract_data(self) -> bool | None:
        """Return the API's isContractData flag, if sent."""
        value = self.raw_data.get("isContractData")
        return None if value is None else bool(value)

    @property
    def price_cap_duration_in_months(self) -> int | None:
        """Return the price cap duration in months, if the response has a price cap."""
        cap = self.raw_data.get("priceCap")
        if not cap or cap.get("priceCapDuration_InMonths") is None:
            return None
        return int(cap["priceCapDuration_InMonths"])

    @property
    def max_effective_working_price_in_cent_per_kwh_gross(self) -> float | None:
        """Return the gross price cap in cent per kWh, if the response has one."""
        cap = self.raw_data.get("priceCap")
        if not cap:
            return None
        return _value(cap, "maxEffectiveWorkingPrice_InCentPerKwh_Gross")

    @property
    def base_provider_working_price_in_cent_per_kwh_gross(self) -> float | None:
        """Return the base provider working price (gross, cent per kWh), if sent."""
        return _value(self.raw_data, "baseProviderWorkingPriceGross_inCentPerKwh")
