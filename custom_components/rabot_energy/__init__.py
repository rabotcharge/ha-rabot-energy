"""The Rabot Energy integration."""

from __future__ import annotations

from homeassistant.const import CONF_API_TOKEN, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ._lib import Auth, RabotEnergyApi
from .const import CONF_CONTRACT_NUMBER, LEGACY_HOST
from .coordinator import RabotConfigEntry, RabotCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: RabotConfigEntry) -> bool:
    """Set up Rabot Energy from a config entry."""
    auth = Auth(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data.get(CONF_API_TOKEN) or None,
    )
    coordinator = RabotCoordinator(hass, entry, RabotEnergyApi(auth))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RabotConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: RabotConfigEntry) -> bool:
    """Migrate older entries (1: no server address, 2: setting called contract_id)."""
    if entry.version == 1:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_HOST: LEGACY_HOST}, version=2
        )
    if entry.version == 2:
        # The service now identifies a contract by its number. An old value (a contract ID)
        # is kept so the entry still loads; it must be replaced by re-adding the entry.
        data = dict(entry.data)
        if "contract_id" in data:
            data[CONF_CONTRACT_NUMBER] = data.pop("contract_id")
        hass.config_entries.async_update_entry(entry, data=data, version=3)
    return True
