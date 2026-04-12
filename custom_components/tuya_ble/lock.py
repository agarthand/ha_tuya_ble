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
        if motor_state := self._device.datapoints.get_or_create(
            DPCode.LOCK_MOTOR_STATE, TuyaBLEDataPointType.DT_BOOL, False
        ):
            return not motor_state.value
        return None

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        self._debug_log_lock_dp_state("before_lock")
        if manual_lock := self._device.datapoints.get_or_create(
            DPCode.MANUAL_LOCK, TuyaBLEDataPointType.DT_BOOL, True
        ):
            _LOGGER.warning(
                "%s: hs21i377 lock command [lock]: dpid=%s, created_type=%s, value=%s",
                self._device.address,
                manual_lock.id,
                manual_lock.type.name,
                True,
            )
            try:
                await manual_lock.set_value(True)
            except Exception:
                _LOGGER.exception(
                    "%s: hs21i377 lock command [lock] failed", self._device.address
                )
                self._debug_log_lock_dp_state("lock_exception")
                raise
        self._debug_log_lock_dp_state("after_lock")

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        self._debug_log_lock_dp_state("before_unlock")
        if manual_lock := self._device.datapoints.get_or_create(
            DPCode.MANUAL_LOCK, TuyaBLEDataPointType.DT_BOOL, False
        ):
            _LOGGER.warning(
                "%s: hs21i377 lock command [unlock]: dpid=%s, created_type=%s, value=%s",
                self._device.address,
                manual_lock.id,
                manual_lock.type.name,
                False,
            )
            try:
                await manual_lock.set_value(False)
            except Exception:
                _LOGGER.exception(
                    "%s: hs21i377 lock command [unlock] failed", self._device.address
                )
                self._debug_log_lock_dp_state("unlock_exception")
                raise
        self._debug_log_lock_dp_state("after_unlock")

    async def async_open(self, **kwargs: Any) -> None:
        """Open the covering."""
        self._debug_log_lock_dp_state("before_open")
        if manual_lock := self._device.datapoints.get_or_create(
            DPCode.MANUAL_LOCK, TuyaBLEDataPointType.DT_BOOL, False
        ):
            _LOGGER.warning(
                "%s: hs21i377 lock command [open]: dpid=%s, created_type=%s, value=%s",
                self._device.address,
                manual_lock.id,
                manual_lock.type.name,
                False,
            )
            try:
                await manual_lock.set_value(False)
            except Exception:
                _LOGGER.exception(
                    "%s: hs21i377 lock command [open] failed", self._device.address
                )
                self._debug_log_lock_dp_state("open_exception")
                raise
        self._debug_log_lock_dp_state("after_open")
