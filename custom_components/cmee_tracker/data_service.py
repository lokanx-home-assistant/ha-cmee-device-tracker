import datetime
import pytz
import logging
import requests
import json;
from homeassistant.components.device_tracker import (
    SOURCE_TYPE_GPS,
)
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

class CmeeDeviceDataService():
    def __init__(self, configData):
        self.configData = configData
        self.devices = None

    async def fetch_data(self):
        _LOGGER.debug("Requesting CMEE Data")
        try:
            with requests.Session() as session:
                session.verify = self.configData._verifySSL
                usermd5 = await self.perform_login(session)
                await self.perform_fetch_alarm_data(session, usermd5)
                await self.perform_fetch_device_data(session, usermd5)
                await self.perform_logout(session)
        except Exception as e:
            _LOGGER.error("Failed fetch data", e)

    async def perform_login(self, session):
        loginUrl =  self.configData._loginUrl.format(self.configData._username, self.configData._password)
        #_LOGGER.debug("CMEE Login URL: " + loginUrl)
        loginRequest = session.get(loginUrl) 
        #_LOGGER.debug("CMEE Login Data retrieved: " + loginRequest.text)
        if loginRequest.text is not None:
            jsonData = json.loads(loginRequest.text)
            return self.parse_login_find_usermd5(jsonData)

        return ""

    async def perform_fetch_device_data(self, session, usermd5):
        deviceDataUrl = self.configData._deviceDataUrl.format(usermd5)
        #_LOGGER.debug("CMEE Device Data URL: " + deviceDataUrl)
        deviceDataRequest = session.get(deviceDataUrl)
        _LOGGER.debug("CMEE Device Data retrieved: " + deviceDataRequest.text)
        if deviceDataRequest.text is not None:
            jsonData = json.loads(deviceDataRequest.text)
            self.parse_data(jsonData)

    async def perform_fetch_alarm_data(self, session, usermd5):
        ts = datetime.datetime.now(pytz.utc)
        dt = ts + datetime.timedelta(hours=6)
        st = dt_util.as_local(dt)
        starttime = datetime.datetime.strftime(st, "%Y-%m-%d %H:%M:%S")
        alarmDataUrl = self.configData._alarmDataUrl.format(usermd5, starttime)
        #_LOGGER.debug("CMEE Alarm Data URL: " + alarmDataUrl)
        alarmDataRequest = session.get(alarmDataUrl)
        _LOGGER.debug("CMEE Alarm Data retrieved: " + alarmDataRequest.text)

    async def perform_logout(self, session):
        logoutUrl =  self.configData._logoutUrl
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
    