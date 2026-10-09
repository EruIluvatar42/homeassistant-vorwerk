"""Support for Vorwerk sensors."""
from __future__ import annotations

import logging
from typing import Any

from pybotvac.robot import Robot
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import VorwerkState
from .const import (
    VORWERK_DOMAIN,
    VORWERK_ROBOT_API,
    VORWERK_ROBOT_COORDINATOR,
    VORWERK_ROBOTS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Vorwerk sensor using config entry."""
    _LOGGER.debug("Adding sensors for vorwerk robots")
    async_add_entities(
        [
            VorwerkSensor(robot[VORWERK_ROBOT_API], robot[VORWERK_ROBOT_COORDINATOR])
            for robot in hass.data[VORWERK_DOMAIN][entry.entry_id][VORWERK_ROBOTS]
        ],
        True,
    )


class VorwerkSensor(CoordinatorEntity, SensorEntity): # type: ignore
    """Vorwerk battery sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, robot_state: VorwerkState, coordinator: DataUpdateCoordinator[Any]
    ) -> None:
        """Initialize Vorwerk sensor."""
        super().__init__(coordinator)
        self.robot: Robot = robot_state.robot
        self._state: VorwerkState = robot_state
        self._attr_name = f"{self.robot.name} Battery"
        self._attr_unique_id = self.robot.serial
        self._attr_device_info = self._state.device_info
        self._refresh_state()

    def _refresh_state(self) -> None:
        """Refresh cached values from the robot state."""
        level = self._state.battery_level
        self._attr_native_value = int(level) if level is not None else None
        self._attr_available = bool(
            self._state.available and self.coordinator.last_update_success
        )

    def _handle_coordinator_update(self) -> None:
        """Update state from coordinator data."""
        self._refresh_state()
        super()._handle_coordinator_update()
