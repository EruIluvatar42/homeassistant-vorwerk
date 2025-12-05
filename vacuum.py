"""Support for Neato Connected Vacuums."""
from __future__ import annotations

import logging
from typing import Any

from pybotvac import Robot
from pybotvac.exceptions import NeatoRobotException
import voluptuous as vol

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.components.vacuum.const import VacuumActivity
from homeassistant.const import ATTR_MODE
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from propcache import cached_property
from . import VorwerkState
from .const import (
    ATTR_CATEGORY,
    ATTR_NAVIGATION,
    ATTR_ZONE,
    VORWERK_DOMAIN,
    VORWERK_ROBOT_API,
    VORWERK_ROBOT_COORDINATOR,
    VORWERK_ROBOTS,
)

_LOGGER = logging.getLogger(__name__)

STATE_TO_ACTIVITY: dict[str, VacuumActivity] = {
    "cleaning": VacuumActivity.CLEANING,
    "docked": VacuumActivity.DOCKED,
    "idle": VacuumActivity.IDLE,
    "paused": VacuumActivity.PAUSED,
    "returning": VacuumActivity.RETURNING,
    "error": VacuumActivity.ERROR,
}


SUPPORT_VORWERK = (
    VacuumEntityFeature.BATTERY
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.START
    | VacuumEntityFeature.CLEAN_SPOT
    | VacuumEntityFeature.STATE
    | VacuumEntityFeature.LOCATE
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Vorwerk vacuum with config entry."""

    _LOGGER.debug("Adding vorwerk vacuums")
    async_add_entities(
        [
            VorwerkConnectedVacuum(
                robot[VORWERK_ROBOT_API], robot[VORWERK_ROBOT_COORDINATOR]
            )
            for robot in hass.data[VORWERK_DOMAIN][entry.entry_id][VORWERK_ROBOTS]
        ],
        True,
    )

    platform = entity_platform.current_platform.get()
    assert platform is not None

    platform.async_register_entity_service(
        "custom_cleaning",
        {
            vol.Optional(ATTR_MODE, default=2): cv.positive_int,
            vol.Optional(ATTR_NAVIGATION, default=1): cv.positive_int,
            vol.Optional(ATTR_CATEGORY, default=4): cv.positive_int,
            vol.Optional(ATTR_ZONE): cv.string,
        },
        "vorwerk_custom_cleaning",
    )


class VorwerkConnectedVacuum(CoordinatorEntity, StateVacuumEntity):
    """Representation of a Vorwerk Connected Vacuum."""

    def __init__(
        self, robot_state: VorwerkState, coordinator: DataUpdateCoordinator[Any]
    ) -> None:
        """Initialize the Vorwerk Connected Vacuum."""
        super().__init__(coordinator)
        self.robot: Robot = robot_state.robot
        self._state: VorwerkState = robot_state

        self._name = f"{self.robot.name}"
        self._robot_serial = self.robot.serial
        self._robot_boundaries: list = []

    @cached_property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @cached_property
    def supported_features(self) -> VacuumEntityFeature:
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_VORWERK

    @cached_property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum cleaner."""
        return int(self._state.battery_level) if self._state.battery_level else None

    @cached_property
    def available(self) -> bool:
        """Return if the robot is available."""
        return self._state.available

    @cached_property
    def icon(self) -> str:
        """Return specific icon."""
        return "mdi:robot-vacuum-variant"

    @cached_property
    def activity(self) -> VacuumActivity | None:
        """Return the current activity using the VacuumActivity enum."""
        if not self._state or not self._state.state:
            return None
        return STATE_TO_ACTIVITY.get(self._state.state)

    @property
    def state(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        activity = self.activity
        return activity.value if activity else None

    @cached_property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._robot_serial

    @cached_property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the vacuum cleaner."""
        data: dict[str, Any] = {}

        if self._state.status is not None:
            data["status"] = self._state.status

        return data

    @cached_property
    def device_info(self) -> DeviceInfo:
        """Device info for robot."""
        return self._state.device_info

    def start(self) -> None:
        """Start cleaning or resume cleaning."""
        if not self._state:
            return
        try:
            if self._state.state == 'idle' or self._state.state == 'docked':
                self.robot.start_cleaning()
            elif self._state.state == 'paused':
                self.robot.resume_cleaning()
        except NeatoRobotException as ex:
            _LOGGER.error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    def pause(self) -> None:
        """Pause the vacuum."""
        try:
            self.robot.pause_cleaning()
        except NeatoRobotException as ex:
            _LOGGER.error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    def return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        try:
            if self._state.state == 'cleaning':
                self.robot.pause_cleaning()
            self.robot.send_to_base()
        except NeatoRobotException as ex:
            _LOGGER.error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    def stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        try:
            self.robot.stop_cleaning()
        except NeatoRobotException as ex:
            _LOGGER.error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    def locate(self, **kwargs: Any) -> None:
        """Locate the robot by making it emit a sound."""
        try:
            self.robot.locate()
        except NeatoRobotException as ex:
            _LOGGER.error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    def clean_spot(self, **kwargs: Any) -> None:
        """Run a spot cleaning starting from the base."""
        try:
            self.robot.start_spot_cleaning()
        except NeatoRobotException as ex:
            _LOGGER.error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    def vorwerk_custom_cleaning(
        self, mode: int, navigation: int, category: str, zone: str | None = None
    ) -> None:
        """Zone cleaning service call."""
        boundary_id = None
        if zone is not None:
            for boundary in self._robot_boundaries:
                if zone in boundary["name"]:
                    boundary_id = boundary["id"]
            if boundary_id is None:
                _LOGGER.error(
                    "Zone '%s' was not found for the robot '%s'", zone, self.entity_id
                )
                return
            _LOGGER.info("Start cleaning zone '%s' with robot %s", zone, self.entity_id)

        try:
            self.robot.start_cleaning(mode, navigation, category, boundary_id)
        except NeatoRobotException as ex:
            _LOGGER.error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    async def async_start(self) -> None:
        await self.hass.async_add_executor_job(self.start)

    async def async_stop(self, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(self.stop, **kwargs)

    async def async_pause(self, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(self.pause, **kwargs)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(self.return_to_base, **kwargs)

    async def async_clean_spot(self, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(self.clean_spot, **kwargs)

    async def async_locate(self, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(self.locate, **kwargs)

    async def async_send_command(self, command: str, params: dict[str, Any] | list[Any] | None = None, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(self.send_command, command, params)
