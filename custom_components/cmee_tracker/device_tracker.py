
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

__version__ = '0.0.7'

_LOGGER = logging.getLogger(__name__)

CONF_USERNAME = 'username'
CONF_PASSWORD = 'password'
CONF_LOGIN_URL = 'login_url'
CONF_DEVICE_DATA_URL = 'device_data_url'
CONF_ALARM_DATA_URL = 'alarm_data_url'
CONF_LOGOUT_URL = 'logout_url'
CONF_NAME = 'name'
CONF_FORCE_INTERVAL = 'force_interval'

DEFAULT_CONF_LOGIN_URL = 'https://cmee.online/doLogin.action?glanguage=en&userinfo.username={0}&userinfo.userpass={1}'
DEFAULT_CONF_ALARM_DATA_URL = 'https://cmee.online/getAlarmList.action?glanguage=en&rptquery.querytype=1&usermd5={0}&rptquery.starttime={1}'
DEFAULT_CONF_DEVICE_DATA_URL = 'https://cmee.online/getActiveListOfPager.action?usermd5={0}'
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
    vol.Optional(CONF_ALARM_DATA_URL, default=DEFAULT_CONF_ALARM_DATA_URL): cv.string,
    vol.Optional(CONF_DEVICE_DATA_URL, default=DEFAULT_CONF_DEVICE_DATA_URL): cv.string,
    vol.Optional(CONF_LOGOUT_URL, default=DEFAULT_CONF_LOGOUT_URL): cv.string,
    vol.Optional(CONF_FORCE_INTERVAL, default=DEFAULT_CONF_FORCE_INTERVAL): cv.boolean
})

async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    _LOGGER.debug("Scanner setup started")
    interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    loginUrl = config.get(CONF_LOGIN_URL)
    alarmDataUrl = config.get(CONF_ALARM_DATA_URL)
    deviceDataUrl = config.get(CONF_DEVICE_DATA_URL)
    logoutUrl = config.get(CONF_LOGOUT_URL)
    forceInterval = config.get(CONF_FORCE_INTERVAL)
    name = config.get(CONF_NAME)

    configData = CmeeDeviceScannerConfigData(
        username,
        password,
        loginUrl,
        alarmDataUrl,
        deviceDataUrl,
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
        _LOGGER.debug("Requesting CMEE Data")
        try:
            with requests.Session() as session:
                usermd5 = self.perform_login(session)
                self.perform_fetch_alarm_data(session, usermd5)
                self.perform_fetch_device_data(session, usermd5)
                self.perform_logout(session)
        except Exception as e:
            _LOGGER.error("Failed fetch data", e)

    def perform_login(self, session):
        loginUrl = self.configData._loginUrl.format(self.configData._username, self.configData._password)
        #_LOGGER.debug("CMEE Login URL: " + loginUrl)
        loginRequest = session.get(loginUrl) 
        #_LOGGER.debug("CMEE Login Data retrieved: " + loginRequest.text)
        if loginRequest.text is not None:
            jsonData = json.loads(loginRequest.text)
            return self.parse_login_find_usermd5(jsonData)

        return ""

    def perform_fetch_device_data(self, session, usermd5):
        deviceDataUrl = self.configData._deviceDataUrl.format(usermd5)
        #_LOGGER.debug("CMEE Device Data URL: " + deviceDataUrl)
        deviceDataRequest = session.get(deviceDataUrl)
        _LOGGER.debug("CMEE Device Data retrieved: " + deviceDataRequest.text)
        if deviceDataRequest.text is not None:
            jsonData = json.loads(deviceDataRequest.text)
            self.parse_data(jsonData)

    def perform_fetch_alarm_data(self, session, usermd5):
        ts = datetime.datetime.now(pytz.utc)
        dt = ts + datetime.timedelta(hours=6)
        st = dt_util.as_local(dt)
        starttime = datetime.datetime.strftime(st, "%Y-%m-%d %H:%M:%S")
        alarmDataUrl = self.configData._alarmDataUrl.format(usermd5, starttime)
        #_LOGGER.debug("CMEE Alarm Data URL: " + alarmDataUrl)
        alarmDataRequest = session.get(alarmDataUrl)
        _LOGGER.debug("CMEE Alarm Data retrieved: " + alarmDataRequest.text)

    def perform_logout(self, session):
        logoutUrl = self.configData._logoutUrl
        _LOGGER.debug("CMEE Logout URL: " + logoutUrl)
        logoutRequest = session.get(logoutUrl)
    
    def parse_login_find_usermd5(self, jsonData):
        try:
            if jsonData["usermd5"] is not None:
                return jsonData["usermd5"]
            else:
                return ""
        except Exception as e:
            return ""

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
    def __init__(self, username, password, loginUrl, alarmDataUrl, deviceDataUrl, logoutUrl):
        """Initialize"""
        self._username = username
        self._password = password
        self._loginUrl = loginUrl
        self._alarmDataUrl = alarmDataUrl
        self._deviceDataUrl = deviceDataUrl
        self._logoutUrl = logoutUrl
