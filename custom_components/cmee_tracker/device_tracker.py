
import datetime
import pytz
import logging
import voluptuous as vol
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
from .config_data import CmeeDeviceScannerConfigData
from .device_scanner import CmeeDeviceScanner

__version__ = '0.0.9'

_LOGGER = logging.getLogger(__name__)

CONF_USERNAME = 'username'
CONF_PASSWORD = 'password'
CONF_LOGIN_URL = 'login_url'
CONF_DEVICE_DATA_URL = 'device_data_url'
CONF_ALARM_DATA_URL = 'alarm_data_url'
CONF_LOGOUT_URL = 'logout_url'
CONF_NAME = 'name'
CONF_FORCE_INTERVAL = 'force_interval'
CONF_VERIFY_SSL = 'verify_ssl'

DEFAULT_CONF_LOGIN_URL = 'https://cmee.online/doLogin.action?glanguage=en&userinfo.username={0}&userinfo.userpass={1}'
DEFAULT_CONF_ALARM_DATA_URL = 'https://cmee.online/getAlarmList.action?glanguage=en&rptquery.querytype=1&usermd5={0}&rptquery.starttime={1}'
DEFAULT_CONF_DEVICE_DATA_URL = 'https://cmee.online/getActiveListOfPager.action?usermd5={0}'
DEFAULT_CONF_LOGOUT_URL = 'https://cmee.online/logout.action'
DEFAULT_CONF_NAME = 'cmee_tracker'
DEFAULT_CONF_FORCE_INTERVAL = False
DEFAULT_CONF_VERIFY_SSL = True

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
    vol.Optional(CONF_FORCE_INTERVAL, default=DEFAULT_CONF_FORCE_INTERVAL): cv.boolean,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_CONF_VERIFY_SSL): cv.boolean
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
    verifySSL = config.get(CONF_VERIFY_SSL)

    configData = CmeeDeviceScannerConfigData(
        username,
        password,
        loginUrl,
        alarmDataUrl,
        deviceDataUrl,
        logoutUrl,
        verifySSL)
    scanner = CmeeDeviceScanner(hass, async_see, configData)
    await scanner.async_start(hass, interval, forceInterval)
    _LOGGER.debug("Scanner initialized")
    return True


