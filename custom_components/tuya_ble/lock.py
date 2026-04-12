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

    def _debug_log_lock_dp_state(self, context: str) -> None:
        """Log relevant datapoints for hs21i377 lock debugging."""
        if self._device.product_id != "hs21i377":
            return

        debug_datapoints: list[tuple[str, int | None, TuyaBLEDataPointType | None]] = [
            ("manual_lock", self.find_dpid(DPCode.MANUAL_LOCK), None),
            ("lock_motor_state", self.find_dpid(DPCode.LOCK_MOTOR_STATE), None),
            ("dp_40", 40, None),
            ("dp_46", 46, None),
            ("dp_47", 47, None),
            ("dp_71", 71, None),
            ("dp_20", 20, None),
            ("dp_69", 69, None),
        ]

        state_parts: list[str] = []
        for name, dp_id, expected_type in debug_datapoints:
            if dp_id is None:
                state_parts.append(f"{name}=missing")
                continue
            datapoint = self._device.datapoints[dp_id]
            if datapoint is None:
                state_parts.append(f"{name}(id={dp_id})=unseen")
                continue
            value = datapoint.value
            if isinstance(value, bytes):
                value_repr = value.hex()
            else:
                value_repr = repr(value)
            state_parts.append(
                f"{name}(id={dp_id}, type={datapoint.type.name})={value_repr}"
            )

        _LOGGER.warning(
            "%s: hs21i377 lock debug [%s]: %s",
            self._device.address,
            context,
            "; ".join(state_parts),
        )

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
        self._debug_log_lock_dp_state(f"before_{context}")
        manual_lock_dp_id = self.find_dpid(DPCode.MANUAL_LOCK)
        if manual_lock_dp_id is None:
            _LOGGER.warning(
                "%s: hs21i377 lock command [%s] skipped: manual_lock dp not found",
                self._device.address,
                context,
            )
            return

        if manual_lock := self._device.datapoints.get_or_create(
            manual_lock_dp_id, TuyaBLEDataPointType.DT_BOOL, value
        ):
            _LOGGER.warning(
                "%s: hs21i377 lock command [%s]: dpid=%s, created_type=%s, value=%s",
                self._device.address,
                context,
                manual_lock.id,
                manual_lock.type.name,
                value,
            )
            try:
                await manual_lock.set_value(value)
            except Exception:
                _LOGGER.exception(
                    "%s: hs21i377 lock command [%s] failed",
                    self._device.address,
                    context,
                )
                self._debug_log_lock_dp_state(f"{context}_exception")
                raise
        self._debug_log_lock_dp_state(f"after_{context}")

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self._write_manual_lock(True, "lock")

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        await self._write_manual_lock(False, "unlock")

    async def async_open(self, **kwargs: Any) -> None:
        """Open the covering."""
        await self._write_manual_lock(False, "open")
