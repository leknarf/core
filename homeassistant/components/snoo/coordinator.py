"""Support for Snoo Coordinators."""

import logging
from typing import override

from python_snoo.containers import SnooData, SnooDevice
from python_snoo.snoo import Snoo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .weaning import WEANING_DEVICES_OPTION, WeaningController

type SnooConfigEntry = ConfigEntry[dict[str, SnooCoordinator]]

_LOGGER = logging.getLogger(__name__)


class SnooCoordinator(DataUpdateCoordinator[SnooData]):
    """Snoo coordinator."""

    config_entry: SnooConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SnooConfigEntry,
        device: SnooDevice,
        snoo: Snoo,
    ) -> None:
        """Set up Snoo Coordinator."""
        super().__init__(
            hass,
            name=device.name,
            config_entry=entry,
            logger=_LOGGER,
        )
        self.device_unique_id = device.serialNumber
        self.device = device
        self.sensor_data_set: bool = False
        self.snoo = snoo
        self.weaning = WeaningController(
            snoo,
            device,
            hass.async_create_task,
            enabled=device.serialNumber
            in entry.options.get(WEANING_DEVICES_OPTION, []),
        )

    @callback
    @override
    def async_set_updated_data(self, data: SnooData) -> None:
        """Publish native data and apply optional baseline automation."""
        super().async_set_updated_data(data)
        self.weaning.update(data)

    async def async_set_weaning_enabled(self, enabled: bool) -> None:
        """Persist the per-device switch state and update the controller."""
        devices = set(self.config_entry.options.get(WEANING_DEVICES_OPTION, []))
        if enabled:
            devices.add(self.device_unique_id)
        else:
            devices.discard(self.device_unique_id)
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options={
                **self.config_entry.options,
                WEANING_DEVICES_OPTION: sorted(devices),
            },
        )
        try:
            await self.weaning.set_enabled(enabled)
        finally:
            self.async_update_listeners()

    async def setup(self) -> None:
        """Perform setup needed on every coordintaor creation."""
        self.snoo.start_subscribe(self.device, self.async_set_updated_data)
        # After we subscribe - get the status so that we have something to start with.
        # We only need to do this once. The device will auto update otherwise.
        await self.snoo.get_status(self.device)
