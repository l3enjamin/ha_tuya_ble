# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2024-12-05

### Changed - Internal Architecture Improvements

#### Phase 2.1: Runtime Data Migration
- **Breaking internal change**: Migrated all platform components from `hass.data[DOMAIN]` to `entry.runtime_data`
- Introduced type-safe `TuyaBLEConfigEntry = ConfigEntry[TuyaBLEData]` pattern
- Updated all 10 platform files:
  - `__init__.py` - Core entry point with runtime_data setup
  - `sensor.py`
  - `binary_sensor.py`
  - `button.py`
  - `climate.py`
  - `cover.py` 
  - `switch.py`
  - `number.py`
  - `select.py`
  - `text.py`
  - `light.py`
- Improved type safety and follows HA 2024.x best practices
- Standardized task creation using `hass.async_create_task()` throughout codebase

#### Phase 2.2: Documentation Updates
- Added CHANGELOG.md for tracking changes
- Updated manifest.json to version 0.3.0
- Added developer notes to README.md

### Technical Details

This is a pure internal refactoring with no user-facing changes. The integration functionality remains identical, but the code structure is now:
- More maintainable
- Better typed
- Aligned with Home Assistant's modern architecture patterns
- Prepared for future HA core changes

### Migration Notes for Developers

If you're maintaining a fork or contributing:

**Old pattern:**
```python
from .const import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data: TuyaBLEData = hass.data[DOMAIN][entry.entry_id]
```

**New pattern:**
```python
from . import TuyaBLEConfigEntry

async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaBLEConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data: TuyaBLEData = entry.runtime_data
```

## [0.2.0] - Previous Release

(Previous changes not documented)
