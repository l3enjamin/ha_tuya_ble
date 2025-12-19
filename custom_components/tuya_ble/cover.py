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
            if battery_dp:
                datapoint = self._device.datapoints[battery_dp]
                if datapoint:
                    attributes["battery_percentage"] = datapoint.value
                    
            # Work state (DP7) - learning status, not movement!
            if 7: # Always check if defined
                datapoint = self._device.datapoints[7]
                if datapoint:
                    # 0=standby, 1=learning, 2=success, 3=fail
                    attributes["work_state"] = datapoint.value
                
            # Fault status (DP12)
            if 12:
                datapoint = self._device.datapoints[12]
                if datapoint:
                    val = datapoint.value
                    if isinstance(val, bytes):
                        attributes["fault_code"] = int.from_bytes(val, 'big')
                    else:
                        attributes["fault_code"] = val
                    
            # Temperature (DP103) - scaled by 10
            if 103:
                datapoint = self._device.datapoints[103]
                if datapoint:
                    attributes["temperature"] = datapoint.value
                    
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
            if cover_position_dp:
                datapoint = self._device.datapoints[cover_position_dp]
                if datapoint and datapoint.value is not None:
                    # Tuya: 0=open, 100=closed
                    # HA: 0=closed, 100=open
                    # So we need to invert!
                    try:
                        tuya_position = int(datapoint.value)
                        self._attr_current_cover_position = 100 - tuya_position
                        
                        # Update closed state
                        if self._attr_current_cover_position == 0:
                            self._attr_is_closed = True
                        elif self._attr_current_cover_position > 0:
                            self._attr_is_closed = False
                    except ValueError:
                        pass
            
            # Get control state from DP1 (control enum)
            # Note: DP1 shows LAST command sent, not necessarily current movement!
            cover_state_dp = self.get_tuya_datapoint("state")
            if cover_state_dp:
                datapoint = self._device.datapoints[cover_state_dp]
                if datapoint and datapoint.value is not None:
                    # Reset movement flags first
                    self._attr_is_opening = False
                    self._attr_is_closing = False
                    
                    # Only set movement flags if not at target position
                    # Enum values depend on device, assuming 0=Open, 1=Stop, 2=Close
                    # Need to verify enum mapping from logs.
                    # Log says: "range":["open","stop","close","continue"]
                    # If SDK maps these to int: open=0, stop=1, close=2? Usually.
                    # Let's assume standard Tuya Enum mapping or use string if raw?
                    # TuyaBLEDataPointType.DT_ENUM stores value as int.
                    
                    try:
                        val = int(datapoint.value)
                        match val:
                            case 0:  # OPEN
                                if self._attr_current_cover_position != 100:
                                    self._attr_is_opening = True
                            case 1:  # STOP
                                pass  # Movement stopped
                            case 2:  # CLOSE
                                if self._attr_current_cover_position != 0:
                                    self._attr_is_closing = True
                    except ValueError:
                        pass

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
            datapoint = self._device.datapoints.get_or_create(
                cover_state_dp,
                TuyaBLEDataPointType.DT_ENUM,
                command.value
            )
            await datapoint.set_value(command.value)
            
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
                    pass
            
            self.async_write_ha_state()
                
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
            datapoint = self._device.datapoints.get_or_create(
                position_set_dp,
                TuyaBLEDataPointType.DT_VALUE,
                tuya_position
            )
            await datapoint.set_value(tuya_position)
            
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
    """Set up the Tuya BLE Cover."""
    data: TuyaBLEData = entry.runtime_data
    manager = data.manager
    product = data.product
    device = data.device

    # Look for cover platform config
    # In this repo, datapoints are dict[Platform, ...]
    if not product or not product.datapoints or Platform.COVER not in product.datapoints:
        return
        
    # We found config for cover, create entity
    cover = TuyaBLECover(hass, data.coordinator, device, product)
    async_add_entities([cover])
