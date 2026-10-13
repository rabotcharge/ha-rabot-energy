"""Price sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import RabotConfigEntry, RabotCoordinator
from .prices import (
    PriceSlot,
    current_slot,
    highest_slot,
    lowest_slot,
    next_slot,
)

PARALLEL_UPDATES = 0

# ASSUMPTION: prices are in EUR. Revisit when the API states the currency explicitly.
PRICE_UNIT = f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"


@dataclass(frozen=True, kw_only=True)
class RabotSensorDescription(SensorEntityDescription):
    """Describe a price sensor."""

    slot_fn: Callable[[list[PriceSlot], datetime], PriceSlot | None]
    net: bool = False
    with_period: bool = False
    with_prices: bool = False


SENSORS: tuple[RabotSensorDescription, ...] = (
    RabotSensorDescription(
        key="current_price",
        translation_key="current_price",
        slot_fn=current_slot,
        with_prices=True,
    ),
    RabotSensorDescription(
        key="current_price_net", translation_key="current_price_net", slot_fn=current_slot, net=True
    ),
    RabotSensorDescription(key="next_price", translation_key="next_price", slot_fn=next_slot),
    RabotSensorDescription(
        key="lowest_price", translation_key="lowest_price", slot_fn=lowest_slot, with_period=True
    ),
    RabotSensorDescription(
        key="highest_price", translation_key="highest_price", slot_fn=highest_slot, with_period=True
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RabotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the price sensors."""
    coordinator = entry.runtime_data
    async_add_entities(RabotPriceSensor(coordinator, description) for description in SENSORS)


class RabotPriceSensor(CoordinatorEntity[RabotCoordinator], SensorEntity):
    """A price derived from the cached preview."""

    entity_description: RabotSensorDescription
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PRICE_UNIT
    _attr_suggested_display_precision = 4
    # The full price list is large and only useful live (charts), so keep it out of the database.
    _unrecorded_attributes = frozenset({"prices"})

    def __init__(self, coordinator: RabotCoordinator, description: RabotSensorDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.contract_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.contract_number)},
            name=f"Rabot {coordinator.contract_number}",
            manufacturer="Rabot Energy",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Re-evaluate at every quarter hour from cached data, without calling the API."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._handle_slot_boundary, minute=range(0, 60, 15), second=0
            )
        )

    @callback
    def _handle_slot_boundary(self, _now: datetime) -> None:
        """Write the state again; the slot may have changed."""
        self.async_write_ha_state()

    def _slot(self) -> PriceSlot | None:
        """Return the slot this sensor reports, based on the current time."""
        return self.entity_description.slot_fn(self.coordinator.data, dt_util.utcnow())

    @property
    def native_value(self) -> float | None:
        """Return the price of the selected slot."""
        slot = self._slot()
        if slot is None:
            return None
        return slot.net if self.entity_description.net else slot.gross

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the slot period (lowest/highest) or the full price list (current price)."""
        description = self.entity_description
        if description.with_prices:
            return {
                "prices": [
                    {
                        "start": slot.start.isoformat(),
                        "end": slot.end.isoformat(),
                        "price": slot.gross,
                    }
                    for slot in self.coordinator.data
                ]
            }
        if not description.with_period:
            return None
        slot = self._slot()
        if slot is None:
            return None
        return {"start": slot.start.isoformat(), "end": slot.end.isoformat()}
