"""The Tuya BLE Cover integration."""
from __future__ import annotations

import logging
from enum import IntEnum
from typing import Any

from homeassistant.components.cover import (
    CoverEntityFeature,
    CoverEntity,
    CoverDeviceClass,
    ATTR_POSITION
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import TuyaBLEConfigEntry
from .devices import TuyaBLEData, TuyaBLEEntity, TuyaBLEProductInfo
from .tuya_ble import TuyaBLEDataPointType, TuyaBLEDevice

_LOGGER = logging.getLogger(__name__)
_PLATFORM = Platform.COVER


class TuyaCoverCommand(IntEnum):
    """Tuya Cover Control Commands (DP1)."""
    OPEN = 0
    STOP = 1
    CLOSE = 2


class TuyaBLECover(TuyaBLEEntity, CoverEntity):
    """Representation of a Tuya BLE Cover."""

    _PLATFORM = _PLATFORM

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
        device: TuyaBLEDevice,
        product: TuyaBLEProductInfo,
    ) -> None:
        """Initialize the cover."""
        description = EntityDescription(key="cover", name="Cover")
        super().__init__(hass, coordinator, device, product, description)
        
        # Initialize state attributes
        self._attr_is_closed = None
        self._attr_is_opening = False
        self._attr_is_closing = False
        self._attr_current_cover_position = None

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Return the supported features of the device."""
        features = self.platform_config.get("supported_features")
        if features:
            return features
        # Default features if not specified
        return (
            CoverEntityFeature.OPEN 
            | CoverEntityFeature.CLOSE 
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    @property
    def device_class(self) -> CoverDeviceClass:
        """Return device class."""
        return CoverDeviceClass.CURTAIN

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self._device or not hasattr(self._device, 'datapoints'):
            return None
            
        attributes = {}
        
        try:
            # Battery percentage (DP13)
            battery_dp = self.get_tuya_datapoint("battery_percentage")
            if battery_dp and battery_dp in self._device.datapoints:
                battery_datapoint = self._device.datapoints[battery_dp]
                if battery_datapoint:
                    attributes["battery_percentage"] = battery_datapoint.value
                    
            # Work state (DP7) - learning status, not movement!
            if 7 in self._device.datapoints:
                work_state_dp = self._device.datapoints[7]
                if work_state_dp:
                    # 0=standby, 1=learning, 2=success, 3=fail
                    attributes["work_state"] = work_state_dp.value
                
            # Fault status (DP12)
            if 12 in self._device.datapoints:
                fault_dp = self._device.datapoints[12]
                if fault_dp:
                    attributes["fault_code"] = fault_dp.value
                    
            # Temperature (DP103) - scaled by 10
            if 103 in self._device.datapoints:
                temp_dp = self._device.datapoints[103]
                if temp_dp:
                    attributes["temperature"] = temp_dp.value / 10.0
                    
        except Exception as ex:
            _LOGGER.debug(
                "Error getting extra attributes for %s: %s",
                self._device.name if self._device else "unknown",
                ex,
            )
            
        return attributes if attributes else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self._device or not hasattr(self._device, 'datapoints'):
            return
            
        try:
            # Get current position from DP3 (percent_state)
            cover_position_dp = self.get_tuya_datapoint("current_position")
            if cover_position_dp and cover_position_dp in self._device.datapoints:
                datapoint = self._device.datapoints[cover_position_dp]
                if datapoint and datapoint.value is not None:
                    # Tuya: 0=open, 100=closed
                    # HA: 0=closed, 100=open
                    # So we need to invert!
                    tuya_position = int(datapoint.value)
                    self._attr_current_cover_position = 100 - tuya_position
                    
                    # Update closed state
                    if self._attr_current_cover_position == 0:
                        self._attr_is_closed = True
                    elif self._attr_current_cover_position > 0:
                        self._attr_is_closed = False
            
            # Get control state from DP1 (control enum)
            # Note: DP1 shows LAST command sent, not necessarily current movement!
            cover_state_dp = self.get_tuya_datapoint("state")
            if cover_state_dp and cover_state_dp in self._device.datapoints:
                datapoint = self._device.datapoints[cover_state_dp]
                if datapoint and datapoint.value is not None:
                    # Reset movement flags first
                    self._attr_is_opening = False
                    self._attr_is_closing = False
                    
                    # Only set movement flags if not at target position
                    match datapoint.value:
                        case 0:  # OPEN command
                            if self._attr_current_cover_position != 100:
                                self._attr_is_opening = True
                        case 1:  # STOP command
                            pass  # Movement stopped
                        case 2:  # CLOSE command
                            if self._attr_current_cover_position != 0:
                                self._attr_is_closing = True

            # Write state to HA
            self.async_write_ha_state()
            
        except Exception as ex:
            _LOGGER.warning(
                "Error updating cover state for %s: %s",
                self._device.name if self._device else "unknown",
                ex,
            )

    async def _send_control_command(self, command: TuyaCoverCommand) -> None:
        """Send control command to DP1 (enum type)."""
        if not self._device:
            _LOGGER.warning("Cannot send command - device not available")
            return
            
        cover_state_dp = self.get_tuya_datapoint("state")
        if not cover_state_dp:
            _LOGGER.warning("No state datapoint configured")
            return
        
        try:
            # DP1 is DT_ENUM type! Not DT_VALUE!
            success = await self.send_dp_value_async(
                None,  # dpcode (we use dpid directly)
                TuyaBLEDataPointType.DT_ENUM,
                command.value
            )
            
            if success:
                # Optimistically update local state
                self._attr_is_opening = False
                self._attr_is_closing = False
                
                match command:
                    case TuyaCoverCommand.OPEN:
                        if self._attr_current_cover_position != 100:
                            self._attr_is_opening = True
                    case TuyaCoverCommand.CLOSE:
                        if self._attr_current_cover_position != 0:
                            self._attr_is_closing = True
                    case TuyaCoverCommand.STOP:
                        pass  # Stop clears movement flags
                
                self.async_write_ha_state()
            else:
                _LOGGER.warning(
                    "Failed to send control command %s",
                    command.name
                )
                
        except Exception as ex:
            _LOGGER.error(
                "Error sending control command %s: %s",
                command.name,
                ex,
            )

    async def async_open_cover(self, **kwargs) -> None:
        """Open the cover."""
        await self._send_control_command(TuyaCoverCommand.OPEN)

    async def async_close_cover(self, **kwargs) -> None:
        """Close the cover."""
        await self._send_control_command(TuyaCoverCommand.CLOSE)

    async def async_stop_cover(self, **kwargs) -> None:
        """Stop the cover."""
        await self._send_control_command(TuyaCoverCommand.STOP)

    async def async_set_cover_position(self, **kwargs) -> None:
        """Set cover position using DP2 (percent_control)."""
        if not self._device:
            _LOGGER.warning("Cannot set position - device not available")
            return
            
        # Get HA position (0=closed, 100=open)
        ha_position = kwargs.get(ATTR_POSITION)
        if ha_position is None:
            _LOGGER.warning("No position provided")
            return
        
        # Convert to Tuya position (0=open, 100=closed)
        tuya_position = 100 - int(ha_position)
        
        position_set_dp = self.get_tuya_datapoint("position_set")
        if not position_set_dp:
            _LOGGER.warning("No position_set datapoint configured")
            return
        
        try:
            # DP2 is DT_VALUE type (0-100)
            success = await self.send_dp_value_async(
                None,  # dpcode (we use dpid directly)
                TuyaBLEDataPointType.DT_VALUE,
                tuya_position
            )
            
            if success:
                # Optimistically update position
                self._attr_current_cover_position = ha_position
                
                # Set movement flags
                self._attr_is_opening = False
                self._attr_is_closing = False
                if ha_position > (self._attr_current_cover_position or 0):
                    self._attr_is_opening = True
                elif ha_position < (self._attr_current_cover_position or 0):
                    self._attr_is_closing = True
                
                # Update closed state
                if ha_position == 0:
                    self._attr_is_closed = True
                else:
                    self._attr_is_closed = False
                    
                self.async_write_ha_state()
            else:
                _LOGGER.warning(
                    "Failed to set cover position to %d%%",
                    ha_position
                )
                
        except Exception as ex:
            _LOGGER.error(
                "Error setting cover position to %d%%: %s",
                ha_position,
                ex,
            )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaBLEConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tuya BLE covers."""
    data: TuyaBLEData = entry.runtime_data
    
    if not data.device or not data.product:
        _LOGGER.error(
            "Cannot setup cover - device or product data not available"
        )
        return
    
    # Check if this device supports cover platform
    if (
        data.product.datapoints
        and Platform.COVER in data.product.datapoints
    ):
        try:
            async_add_entities([
                TuyaBLECover(
                    hass,
                    data.coordinator,
                    data.device,
                    data.product,
                )
            ])
            _LOGGER.info(
                "Added cover entity for device: %s",
                data.device.name if data.device else "unknown"
            )
        except Exception as ex:
            _LOGGER.error(
                "Error setting up cover entity: %s",
                ex,
                exc_info=True,
            )
    else:
        _LOGGER.debug(
            "Device %s does not have cover platform configuration",
            data.device.name if data.device else "unknown"
        )
