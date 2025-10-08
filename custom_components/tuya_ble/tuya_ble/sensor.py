"""Tuya BLE sensor platform - for battery and temperature monitoring."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .devices import TuyaBLEData, TuyaBLEEntity, get_device_product_info

_LOGGER = logging.getLogger(__name__)
_PLATFORM = Platform.SENSOR

@dataclass
class TuyaBLESensorEntityDescription(SensorEntityDescription):
    """Describes Tuya BLE sensor entity."""
    dp_id: int | None = None

SENSOR_DESCRIPTIONS: dict[str, TuyaBLESensorEntityDescription] = {
    "battery_percentage": TuyaBLESensorEntityDescription(
        key="battery_percentage",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "temperature": TuyaBLESensorEntityDescription(
        key="temperature", 
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tuya BLE sensors."""
    data: TuyaBLEData = hass.data[DOMAIN][entry.entry_id]
    
    # Check if this device supports sensor platform
    product_info = data.product
    if not product_info or not hasattr(product_info, 'datapoints'):
        return
        
    sensor_datapoints = product_info.datapoints.get(Platform.SENSOR)
    if not sensor_datapoints:
        return
        
    entities: list[TuyaBLESensor] = []
    
    # Add battery sensor if configured
    if isinstance(sensor_datapoints, list):
        for sensor_config in sensor_datapoints:
            if "battery_percentage" in sensor_config:
                entities.append(
                    TuyaBLESensor(
                        hass,
                        data.coordinator,
                        data.device,
                        data.product,
                        SENSOR_DESCRIPTIONS["battery_percentage"],
                        sensor_config["battery_percentage"]
                    )
                )
            if "temperature" in sensor_config:
                entities.append(
                    TuyaBLESensor(
                        hass,
                        data.coordinator,
                        data.device,
                        data.product,
                        SENSOR_DESCRIPTIONS["temperature"],
                        sensor_config["temperature"]
                    )
                )
    elif isinstance(sensor_datapoints, dict):
        if "battery_percentage" in sensor_datapoints:
            entities.append(
                TuyaBLESensor(
                    hass,
                    data.coordinator,
                    data.device,
                    data.product,
                    SENSOR_DESCRIPTIONS["battery_percentage"],
                    sensor_datapoints["battery_percentage"]
                )
            )
        if "temperature" in sensor_datapoints:
            entities.append(
                TuyaBLESensor(
                    hass,
                    data.coordinator,
                    data.device,
                    data.product,
                    SENSOR_DESCRIPTIONS["temperature"],
                    sensor_datapoints["temperature"]
                )
            )

    async_add_entities(entities)

class TuyaBLESensor(TuyaBLEEntity, SensorEntity):
    """Tuya BLE sensor."""

    _PLATFORM = _PLATFORM

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator,
        device,
        product,
        description: TuyaBLESensorEntityDescription,
        dp_id: int,
    ) -> None:
        """Initialize sensor."""
        super().__init__(hass, coordinator, device, product)
        self.entity_description = description
        self._dp_id = dp_id
        self._attr_unique_id = f"{device.device_id}_{description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        datapoint = self._device.datapoints.get(self._dp_id)
        if datapoint:
            self._attr_native_value = datapoint.value
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._dp_id in self._device.datapoints and super().available
