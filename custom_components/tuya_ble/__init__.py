"""The Tuya BLE integration."""
from __future__ import annotations

import logging

from bleak_retry_connector import (
    BLEAK_RETRY_EXCEPTIONS as BLEAK_EXCEPTIONS,
    BleakNotFoundError,
    get_device,
)

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import ADDRESS, BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .tuya_ble import TuyaBLEDevice

from .cloud import HASSTuyaBLEDeviceManager
from .const import DOMAIN
from .devices import TuyaBLECoordinator, TuyaBLEData, get_device_product_info

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.TEXT,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tuya BLE from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), True
    ) or await get_device(address)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Tuya BLE device with address {address}"
        )
    
    manager = HASSTuyaBLEDeviceManager(hass, entry.options.copy())
    device = TuyaBLEDevice(manager, ble_device)
    
    # Add error handling for device initialization
    try:
        await device.initialize()
    except BLEAK_EXCEPTIONS as ex:
        _LOGGER.error(
            "Failed to initialize Tuya BLE device %s: %s. "
            "Device may be out of range, battery low, or experiencing interference. "
            "Integration will retry on next restart.",
            address,
            ex,
            exc_info=True,
        )
        raise ConfigEntryNotReady(
            f"Could not initialize Tuya BLE device with address {address}: {ex}"
        ) from ex
    except BleakNotFoundError as ex:
        _LOGGER.error(
            "Tuya BLE device %s not found after connection attempts. "
            "Device may be out of range or powered off. "
            "Integration will retry on next restart.",
            address,
            exc_info=True,
        )
        raise ConfigEntryNotReady(
            f"Tuya BLE device with address {address} not found: {ex}"
        ) from ex
    except Exception as ex:
        _LOGGER.error(
            "Unexpected error initializing Tuya BLE device %s: %s. "
            "Integration will retry on next restart.",
            address,
            ex,
            exc_info=True,
        )
        raise ConfigEntryNotReady(
            f"Unexpected error with Tuya BLE device {address}: {ex}"
        ) from ex
    
    product_info = get_device_product_info(device)
    coordinator = TuyaBLECoordinator(hass, device)

    # Schedule device update as background task instead of blocking setup
    # This prevents timeout issues from crashing the integration
    async def _async_initial_update() -> None:
        """Perform initial device update."""
        try:
            await device.update()
        except BLEAK_EXCEPTIONS as ex:
            _LOGGER.warning(
                "Initial update failed for Tuya BLE device %s: %s. "
                "Device may be temporarily unavailable. Will retry.",
                address,
                ex,
            )
        except Exception as ex:
            _LOGGER.warning(
                "Unexpected error during initial update for device %s: %s",
                address,
                ex,
                exc_info=True,
            )
    
    hass.async_create_task(_async_initial_update())

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        device.set_ble_device_and_advertisement_data(
            service_info.device, service_info.advertisement
        )

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble,
            BluetoothCallbackMatcher({ADDRESS: address}),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = TuyaBLEData(
        entry.title,
        device,
        product_info,
        manager,
        coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _async_stop(event: Event) -> None:
        """Close the connection."""
        await device.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    data: TuyaBLEData = hass.data[DOMAIN][entry.entry_id]
    if entry.title != data.title:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data: TuyaBLEData = hass.data[DOMAIN].pop(entry.entry_id)
        await data.device.stop()

    return unload_ok
