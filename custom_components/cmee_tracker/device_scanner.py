import datetime
import pytz
import logging
import asyncio
import voluptuous as vol
import requests
import json;
from homeassistant.util import slugify
from homeassistant.helpers.entity import Entity
from homeassistant.components.device_tracker import (
    DeviceScanner,
)
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.dt as dt_util

from .data_service import CmeeDeviceDataService

_LOGGER = logging.getLogger(__name__)

class CmeeDeviceScanner(DeviceScanner):
    def __init__(self, hass, async_see, configData):
        """Initialize the scanner."""
        self.hass = hass
        self.configData = configData
        self.async_see = async_see
        self.dataService = CmeeDeviceDataService(configData)

    async def async_start(self, hass, interval, force):
        """Perform a first update and start polling at the given interval."""
        await self.async_update_info()
        if force is False:
            interval = max(interval, MIN_SCAN_INTERVAL)
        _LOGGER.debug("Starting scanner: interval=" + str(interval))
        async_track_time_interval(hass, self.async_update_info, interval)

    async def async_see_sensor(self, device):
        _LOGGER.debug("See device called")
        result = await self.async_see(**device)
        return result


    async def async_update_info(self, now=None):
        devices = await self.hass.async_add_executor_job(self.dataService.fetch_data)
        '''devices = await self.dataService.fetch_data()'''
        if devices is not None:
            sensors = []
            for device in devices:
                sensors.append(self.async_see_sensor(device))
            await asyncio.wait(sensors)
        else:
            _LOGGER.error("No devices found!")
