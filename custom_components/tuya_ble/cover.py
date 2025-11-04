"""The Tuya BLE Cover integration."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from enum import IntEnum
from typing import Any

from homeassistant.components.cover import (
    CoverEntityFeature,
    CoverEntity,
    CoverDeviceClass,
    ATTR_POSITION
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .devices import TuyaBLEData, TuyaBLEEntity, TuyaBLEProductInfo
from .tuya_ble import TuyaBLEDataPointType, TuyaBLEDevice

_LOGGER = logging.getLogger(__name__)
_PLATFORM = Platform.COVER

class TuyaCoverState(IntEnum):
    """Tuya Cover State Enum"""
    OPEN = 0
    STOP = 1
    CLOSE = 2

class TuyaBLECover(TuyaBLEEntity, CoverEntity):
    """Representation of a Tuya BLE Cover."""

    _PLATFORM = _PLATFORM

    _attr_is_closed = False
    _attr_is_opening = False
    _attr_is_closing = False
    _attr_current_cover_position = 0

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
        device: TuyaBLEDevice,
        product: TuyaBLEProductInfo,
    ) -> None:
        # FIX #1: Add the missing EntityDescription parameter
        description = EntityDescription(key="cover", name="Cover")
        super().__init__(hass, coordinator, device, product, description)

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Return the supported features of the device."""
        return self.platform_config.get("supported_features")

    @property
    def device_class(self) -> CoverDeviceClass:
        """Return device class."""
        return CoverDeviceClass.CURTAIN

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes including battery."""
        attributes = {}
        
        # Add battery percentage if available
        battery_dp = self.get_tuya_datapoint("battery_percentage")
        if battery_dp and battery_dp in self._device.datapoints:
            battery_datapoint = self._device.datapoints[battery_dp]
            if battery_datapoint:
                attributes["battery_percentage"] = battery_datapoint.value
                
        # Add work state if available (DP7)
        if 7 in self._device.datapoints:
            work_state_dp = self._device.datapoints[7]
            if work_state_dp:
                attributes["work_state"] = work_state_dp.value
            
        # Add fault status if available (DP12)
        if 12 in self._device.datapoints:
            fault_dp = self._device.datapoints[12]
            if fault_dp:
                attributes["fault_code"] = fault_dp.value
                
        # Add temperature if available (DP103)
        if 103 in self._device.datapoints:
            temp_dp = self._device.datapoints[103]
            if temp_dp:
                attributes["temperature"] = temp_dp.value
            
        return attributes if attributes else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # FIX #2: Fixed the problematic __dict__() call
        _LOGGER.debug(
            "Updated data for %s: datapoints=%s",
            self._device.name,
            list(self._device.datapoints.keys())  # Safe way to show datapoints
        )
        cover_state_dp = self.get_tuya_datapoint("state")
        cover_position_dp = self.get_tuya_datapoint("current_position")
        
        if cover_state_dp:
            datapoint = self._device.datapoints[cover_state_dp]
            if datapoint:
                self._attr_is_opening = False
                self._attr_is_closing = False
                match datapoint.value:
                    case 0:
                        self._attr_is_opening = True
                    case 1:
                        pass # motor has stopped
                    case 2:
                        self._attr_is_closing = True

        if cover_position_dp:
            datapoint = self._device.datapoints[cover_position_dp]
            if datapoint:
                self._attr_current_cover_position = 100 - int(datapoint.value) # reverse position
                if self._attr_current_cover_position == 0:
                    self._attr_is_closed = True
                    self._attr_is_closing = False
                else:
                    self._attr_is_closed = False

                if self._attr_current_cover_position == 100:
                    self._attr_is_closed = False
                    self._attr_is_opening = False

        self.async_write_ha_state()

    def _update_ha_state_for_cover(self, state: TuyaCoverState) -> None:
        """Update the state of the cover based on the current request or response from device."""
        self._attr_is_closing = False
        self._attr_is_opening = False
        self._attr_is_closed = False
        if self._attr_current_cover_position == 0:
            self._attr_is_closed = True
        if state == TuyaCoverState.OPEN and self._attr_current_cover_position != 100:
            self._attr_is_opening = True
        if state == TuyaCoverState.CLOSE and self._attr_current_cover_position != 0:
            self._attr_is_closing = True
        self.async_write_ha_state()

    def _update_cover_state_without_validation(self, state: TuyaCoverState) -> None:
        cover_state_dp = self.get_tuya_datapoint("state")
        if cover_state_dp:
            if cover_state_dp != 0:
                datapoint = self._device.datapoints.get_or_create(
                    cover_state_dp,
                    TuyaBLEDataPointType.DT_VALUE,
                    state.value,
                )
                if datapoint:
                    self._hass.create_task(datapoint.set_value(state.value))

    async def _validate_data_update_from_device_and_reconnect_if_needed(
        self,
        sleep_ms: int = 1000,
        time_now: datetime | None = None,
    ) -> None:
        time_now = time_now or datetime.now(timezone.utc)
        await asyncio.sleep(sleep_ms / 1000.0)
        if self._device.is_paired and (
            not self._device.last_data_received
            or self._device.last_data_received < time_now
        ):
            _LOGGER.warning(
                "No data received from device (cover) %s within %dms, manually requesting status update",
                self._device.name,
                sleep_ms,
            )
            await self._device.update()

    def _update_ha_state_for_cover_state(self, state: TuyaCoverState) -> None:
        # sometimes the device does not update DP 1 so force the current state
        self._attr_is_closed = False
        self._attr_is_closing = False
        self._attr_is_opening = False

        if self._attr_current_cover_position == 0:
            self._attr_is_closed = True

        if state == TuyaCoverState.OPEN and self._attr_current_cover_position != 100:
            self._attr_is_opening = True
        elif state == TuyaCoverState.CLOSE and self._attr_current_cover_position != 0:
            self._attr_is_closing = True
        self.async_write_ha_state()

    async def _update_cover_state(self, state: TuyaCoverState) -> None:
        """Change state from open, close and stop action."""
        cover_state_dp = self.get_tuya_datapoint("state")
        cover_position_dp = self.get_tuya_datapoint("current_position")
        if cover_state_dp:
            # In some circumstances (presumably due to a communication error in between where packets were lost)
            # It can be the case that the device does not update the state of the cover and does not accept new commands.
            # This is why a timer is here to verify that the state is updated and to manually request the status update
            # if no new data has come in within 1 second as it points to a communication error (as happened in tests with
            # the kcy0x4pi product).
            datapoint = self._device.datapoints.get_or_create(
                cover_state_dp,
                TuyaBLEDataPointType.DT_VALUE,
                state.value
            )
            if datapoint:
                self._hass.add_job(
                    self._validate_data_update_from_device_and_reconnect_if_needed(
                        time_now=datetime.now(timezone.utc)
                    )
                )
                self._update_cover_state_without_validation(state)
                self._update_ha_state_for_cover_state(state)
                return

        if cover_position_dp:
            new_pos = self._attr_current_cover_position # this will be overriden anyway
            if state == TuyaCoverState.CLOSE:
                await self.async_set_cover_position(position=0)
                new_pos = 0
            if state == TuyaCoverState.OPEN:
                await self.async_set_cover_position(position=100)
                new_pos = 100
            if state == TuyaCoverState.STOP:
                return
            if self._attr_current_cover_position != new_pos:
                self._update_ha_state_for_cover(state)

    async def async_open_cover(self, **kwargs) -> None:
        """Open a cover."""
        await self._update_cover_state(TuyaCoverState.OPEN)

    async def async_stop_cover(self, **kwargs: logging.Any) -> None:
        """Stop a cover."""
        await self._update_cover_state(TuyaCoverState.STOP)

    async def async_close_cover(self, **kwargs) -> None:
        """Close a cover."""
        await self._update_cover_state(TuyaCoverState.CLOSE)

    async def async_set_cover_position(self, **kwargs: logging.Any) -> None:
        """Set cover position."""
        position = 100 - kwargs[ATTR_POSITION]
        if self.get_tuya_datapoint("position_set"):
            datapoint = self._device.datapoints.get_or_create(
                self.get_tuya_datapoint("position_set"),
                TuyaBLEDataPointType.DT_VALUE,
                position
            )
            if datapoint:
                self._hass.create_task(datapoint.set_value(position))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tuya BLE covers."""
    data: TuyaBLEData = hass.data[DOMAIN][entry.entry_id]
    
