from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import (
    LockEntity,
    LockEntityFeature,
    LockEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DPCode
from .devices import (
    TuyaBLEData,
    TuyaBLEEntity,
    TuyaBLEProductInfo,
    TuyaBLECoordinator,
    get_device_product_info,
)
from .tuya_ble import TuyaBLEDataPointType, TuyaBLEDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tuya BLE sensors."""
    data: TuyaBLEData = hass.data[DOMAIN][entry.entry_id]
    product = get_device_product_info(data.device)
    if product and product.lock:
        async_add_entities([TuyaBLELock(hass, data.coordinator, data.device, product)])


class TuyaBLELock(TuyaBLEEntity, LockEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TuyaBLECoordinator,
        device: TuyaBLEDevice,
        product: TuyaBLEProductInfo,
    ) -> None:
        super().__init__(
            hass,
            coordinator,
            device,
            product,
            LockEntityDescription(key="lock", name=product.name),
        )
        self._attr_supported_features = LockEntityFeature.OPEN


    @property
    def is_locked(self) -> bool | None:
        """Return true if lock is locked."""
        motor_state_dp_id = self.find_dpid(DPCode.LOCK_MOTOR_STATE)
        if motor_state_dp_id is None:
            return None
        if motor_state := self._device.datapoints.get_or_create(
            motor_state_dp_id, TuyaBLEDataPointType.DT_BOOL, False
        ):
            return not motor_state.value
        return None

    async def _write_manual_lock(self, value: bool, context: str) -> None:
        """Write manual lock using the resolved numeric datapoint id."""
        manual_lock_dp_id = self.find_dpid(DPCode.MANUAL_LOCK)
        if manual_lock_dp_id is None:
            return

        if manual_lock := self._device.datapoints.get_or_create(
            manual_lock_dp_id, TuyaBLEDataPointType.DT_BOOL, value
        ):
            await manual_lock.set_value(value)

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self._write_manual_lock(True, "lock")

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        await self._write_manual_lock(False, "unlock")

    async def async_open(self, **kwargs: Any) -> None:
        """Open the covering."""
        await self._write_manual_lock(False, "open")
