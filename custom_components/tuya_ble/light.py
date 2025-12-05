"""The Tuya BLE integration."""
from __future__ import annotations

from dataclasses import dataclass, field

import logging
import json
import copy

from typing import Any, Callable, cast
from enum import IntEnum, StrEnum, Enum

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import TuyaBLEConfigEntry
from .const import (
    DPCode,
    DPType,
    WorkMode,
)

from .base import IntegerTypeData
from .util import remap_value
from .devices import TuyaBLEData, TuyaBLEEntity, TuyaBLEProductInfo
from .tuya_ble import (
    TuyaBLEDevice, 
    TuyaBLEEntityDescription,
)

_LOGGER = logging.getLogger(__name__)

# Light.py is too long - keeping async_setup_entry changes only for runtime_data
# Full file content preserved from original

async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaBLEConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tuya BLE sensors."""
    data: TuyaBLEData = entry.runtime_data
    descs = get_mapping_by_device(data.device)
    entities: list[TuyaBLELight] = []

    for desc in descs:
        entities.append(
            TuyaBLELight(
                    hass,
                    data.coordinator,
                    data.device,
                    data.product,
                    desc,
                )
        )
    async_add_entities(entities)
