class CmeeDeviceScannerConfigData():
    def __init__(self, username, password, loginUrl, alarmDataUrl, deviceDataUrl, logoutUrl, verifySSL):
        """Initialize"""
        self._username = username
        self._password = password
        self._loginUrl = loginUrl
        self._alarmDataUrl = alarmDataUrl
        self._deviceDataUrl = deviceDataUrl
        self._logoutUrl = logoutUrl
        self._verifySSL = verifySSL
