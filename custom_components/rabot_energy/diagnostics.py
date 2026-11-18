"""Diagnostics for a Rabot Energy config entry."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from .const import CONF_CONTRACT_NUMBER
from .coordinator import RabotConfigEntry

TO_REDACT = {CONF_API_TOKEN, CONF_CONTRACT_NUMBER}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RabotConfigEntry
) -> dict[str, Any]:
    """Return the entry settings (redacted) and a summary of the cached prices."""
    coordinator = entry.runtime_data
    data = coordinator.data
    slots = data.slots if data else []
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "slot_count": len(slots),
        "first_slot": slots[0].start.isoformat() if slots else None,
        "last_slot_end": slots[-1].end.isoformat() if slots else None,
        "base_provider_gross": data.base_provider_gross if data else None,
        "price_cap_gross": data.price_cap_gross if data else None,
        "price_cap_duration_months": data.price_cap_duration_months if data else None,
    }
