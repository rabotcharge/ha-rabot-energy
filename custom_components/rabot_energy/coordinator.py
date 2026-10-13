"""Coordinator: fetches the price preview and parses it into slots."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from ._lib import (
    RabotApiError,
    RabotAuthError,
    RabotConnectionError,
    RabotContractNotFoundError,
    RabotEnergyApi,
    RabotRateLimitError,
)
from .const import CONF_CONTRACT_ID, DOMAIN, LOGGER, UPDATE_INTERVAL
from .prices import PriceSlot, parse_slots

type RabotConfigEntry = ConfigEntry[RabotCoordinator]


class RabotCoordinator(DataUpdateCoordinator[list[PriceSlot]]):
    """Poll the price preview for one contract."""

    config_entry: RabotConfigEntry

    def __init__(self, hass: HomeAssistant, entry: RabotConfigEntry, api: RabotEnergyApi) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self._api = api
        self.contract_id: str = entry.data[CONF_CONTRACT_ID]

    async def _async_update_data(self) -> list[PriceSlot]:
        """Fetch and parse the preview."""
        try:
            preview = await self._api.async_get_price_preview(self.contract_id)
            return parse_slots(preview)
        except RabotAuthError as err:
            raise ConfigEntryAuthFailed("The Rabot token was rejected") from err
        except RabotContractNotFoundError as err:
            raise UpdateFailed("The Rabot contract was not found") from err
        except RabotRateLimitError as err:
            raise UpdateFailed("Rabot rate limit reached, will retry later") from err
        except (RabotConnectionError, RabotApiError) as err:
            raise UpdateFailed(f"Error talking to Rabot: {err}") from err
        except (KeyError, TypeError, ValueError) as err:
            raise UpdateFailed(f"Unexpected price data from Rabot: {err!r}") from err
