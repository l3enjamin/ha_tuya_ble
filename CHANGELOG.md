# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog],
and this project adheres to [Semantic Versioning].

## [0.2.0] - 2025-10-08 (l3enjamin fork)

### Added

- **Home Assistant 2025.7 compatibility**: Fixed import issues that broke the integration in HA 2025.7
- **Curtain motor support**: Added support for curtain motors and blind controllers (category_id 'cl')
  - Blind Controller (product_ids '4pbr8eig', 'qqdxfdht')
  - Curtain Controller (product_id 'kcy0xpi')
- **Cover platform**: New Cover platform for curtain/blind control with features:
  - Open, Close, Stop commands
  - Position control (0-100%)
  - Current position feedback
  - Opening/closing state indicators
- **Enhanced device database**: Extended TuyaBLEProductInfo to support platform-specific datapoint configurations
- **Platform configuration support**: Added platform_config property to TuyaBLEEntity for platform-specific settings

### Changed

- Updated devices.py to include datapoints configuration for curtain motors
- Enhanced TuyaBLEEntity with get_tuya_datapoint method for easier datapoint access
- Added Platform.COVER to supported platforms list

### Technical Notes

This fork integrates:
- The 2025.7 compatibility fixes from [airy10/ha_tuya_ble](https://github.com/airy10/ha_tuya_ble)
- The curtain motor support from [pantherale0/ha_tuya_ble](https://github.com/pantherale0/ha_tuya_ble) preview branch

## [0.1.0] - 2023-04-22

- Initial release


## [0.1.1] - 2023-04-26

### Added

- Added new product_id for Fingerbot Plus (#1)

### Fixed

- Fixed problem in options flow.

### Changed

- Updated strings.json


## [0.1.2] - 2023-04-26

### Changed

- Changed a way to obtain device credentials from Tuya IOT cloud, possible fix to (#2)

## [0.1.4] - 2023-04-30

### Added

- Added support of CUBETOUCH 1s, thanks @damiano75
- Added new product_ids for Fingerbot.
- Added new product_ids for Fingerbot Plus.
- First attempt to support Smart Lock device.

### Fixed

- Fixed possible disconnect of BLE device.

## [0.1.5] - 2023-06-01

### Added

- Added new product_ids for Fingerbot.
- Added event "fingerbot_button_pressed" which is fired on Fingerbot Plus touch button press.
- First attempt to add support of climate entity.

## [0.1.6] - 2023-06-01

### Added

- Added new product_ids for Fingerbot and Fingerbot Plus.

### Changed

- Updated sources to conform Python 3.11

## [0.1.7] - 2023-06-01

### Added

- Added new product_ids.
- Added full support of BLE TRV provided by @forabi
- Added support of programming mode for Fingerbot Plus, thanks @redphx for information.

### Changed

- Improved connection stability.

## [0.1.8] - 2023-07-09

### Added

- Added support of 'Irrigation computer', thanks to @SanMiggel.
- Added new product_ids for Smart locks, thanks to @drewpo28.

### Changed

- Connection to the device is postponed now. Previously some out of range device might prevents HA from fully booting.
- Improved connection stability.