
import datetime
import pytz
import logging
import asyncio
import voluptuous as vol
import requests
import async_timeout
import json;
from homeassistant.util import slugify
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
    SOURCE_TYPE_GPS,
    CONF_SCAN_INTERVAL, 
)
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.dt as dt_util

__version__ = '0.0.6'

_LOGGER = logging.getLogger(__name__)

CONF_USERNAME = 'username'
CONF_PASSWORD = 'password'
CONF_LOGIN_URL = 'login_url'
CONF_DATA_URL = 'data_url'
CONF_LOGOUT_URL = 'logout_url'
CONF_NAME = 'name'
CONF_FORCE_INTERVAL = 'force_interval'

DEFAULT_CONF_LOGIN_URL = 'https://cmee.online/doLogin.action?userinfo.username={0}&userinfo.userpass={1}'
DEFAULT_CONF_DATA_URL = 'https://cmee.online/getActiveListOfPager.action'
DEFAULT_CONF_LOGOUT_URL = 'https://cmee.online/logout.action'
DEFAULT_CONF_NAME = 'cmee_tracker'
DEFAULT_CONF_FORCE_INTERVAL = False

DEFAULT_SCAN_INTERVAL = datetime.timedelta(seconds=300)
MIN_SCAN_INTERVAL = datetime.timedelta(seconds=180)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,   
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_CONF_NAME): cv.string,
    vol.Optional(CONF_LOGIN_URL, default=DEFAULT_CONF_LOGIN_URL): cv.string,
    vol.Optional(CONF_DATA_URL, default=DEFAULT_CONF_DATA_URL): cv.string,
    vol.Optional(CONF_LOGOUT_URL, default=DEFAULT_CONF_LOGOUT_URL): cv.string,
    vol.Optional(CONF_FORCE_INTERVAL, default=DEFAULT_CONF_FORCE_INTERVAL): cv.boolean
})

async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    _LOGGER.debug("Scanner setup started")
    interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    loginUrl = config.get(CONF_LOGIN_URL)
    dataUrl = config.get(CONF_DATA_URL)
    logoutUrl = config.get(CONF_LOGOUT_URL)
    forceInterval = config.get(CONF_FORCE_INTERVAL)
    name = config.get(CONF_NAME)

    configData = CmeeDeviceScannerConfigData(
        username,
        password,
        loginUrl,
        dataUrl,
        logoutUrl)
    scanner = CmeeDeviceScanner(hass, async_see, configData)
    await scanner.async_start(hass, interval, forceInterval)
    _LOGGER.debug("Scanner initialized")
    return True


class CmeeDeviceScanner(DeviceScanner):
    def __init__(self, hass, async_see, configData):
        """Initialize the scanner."""
        self.hass = hass
        self.configData = configData
        self.async_see = async_see
        self.devices = None

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
        await self.fetch_data()
        if self.devices is not None:
            sensors = []
            for device in self.devices:
                sensors.append(self.async_see_sensor(device))
            await asyncio.wait(sensors)

    async def fetch_data(self):
        loginUrl = self.configData._loginUrl.format(self.configData._username, self.configData._password)
        dataUrl = self.configData._dataUrl
        logoutUrl = self.configData._logoutUrl
        _LOGGER.debug("Requesting CMEE Data")
        try:
            with requests.Session() as session:
                loginRequest = session.get(loginUrl) 
                dataRequest = session.get(dataUrl)
                logoutRequest = session.get(logoutUrl)
                _LOGGER.debug("CMEE Data retrieved: " + dataRequest.text)
                if dataRequest.text is not None:
                    jsonData = json.loads(dataRequest.text)
                    self.parse_data(jsonData)
        except Exception as e:
            _LOGGER.error("Failed fetch data", e)

    def parse_data(self, jsonData):
        if len(jsonData["rows"]) > 0:
            self.devices = []
            for row in jsonData["rows"]:
                rowMetadata = json.loads("{" + row["ov"] + "}")
                item = {
                    "host_name": row["obn"] + " " + row["hn"].upper() + " Watch", 
                    "dev_id": "cmee_{}".format(slugify(row["mid"])),
                    "gps": [row["lt"], row["lo"]],
                    "gps_accuracy": rowMetadata["gps"],
                    "battery": rowMetadata["batt"],
                    "source_type": SOURCE_TYPE_GPS,
                    "icon": "mdi:watch",
                    "attributes": {
                        "last_updated": dt_util.as_local(datetime.datetime.now(pytz.utc)),
                        "watch_id": row["mid"],
                        "watch_sid": row["sid"],
                        "watch_status": self.parse_status(row),
                        "watch_location": self.parse_location(rowMetadata),
                        "watch_positioning_time": self.parse_data_date(row["gt"], 16),
                        "watch_reception_time": self.parse_data_date(row["rt"], 8),
                    },
                }
                self.devices.append(item)

    def parse_status(self, row):
        try:
            if "tt" in row:
                if row["tt"] is 0:
                    return "Offline"
                elif row["tt"] is 1:
                    return "Online"
                else:
                    return "Unknown"                
            else:
                return "Unknown"
        except Exception as e:
            return "Unknown"

    def parse_location(self, rowMetadata):
        try:
            if "inrn" in rowMetadata and "inrn1" in rowMetadata:
                return rowMetadata["inrn"] + " | " + rowMetadata["inrn1"]
            elif "outrn" in rowMetadata and "outrn1" in rowMetadata:
                return rowMetadata["outrn"] + " | " + rowMetadata["outrn1"]
            else:
                return "Unknown"
        except Exception as e:
            return "Unknown"

    def parse_data_date(self, dateStr, offset):
        try:
            tmpDatetime = datetime.datetime.strptime(dateStr, "%Y-%m-%d %H:%M:%S")
            dt = tmpDatetime - datetime.timedelta(hours=offset)
            return dt_util.as_local(dt)
        except Exception as e:
            _LOGGER.error("Failed fetch data", e)
            return dateStr

class CmeeDeviceScannerConfigData():
    def __init__(self, username, password, loginUrl, dataUrl, logoutUrl):
        """Initialize"""
        self._username = username
        self._password = password
        self._loginUrl = loginUrl
        self._dataUrl = dataUrl
        self._logoutUrl = logoutUrl
