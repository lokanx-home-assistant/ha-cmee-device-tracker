# ha-cmee-device-tracker

Home Assistant device tracker for CMEE waches.

### Usage

    - platform: cmee
      username: <username>
      password: <password>
  
Data is fetched from https://cmee.online/ every 300 second (5 minutes).

It is possible to change the data fetch interval by specifying interval_seconds. 
Since fetching data is draining battery on the CMEE device a minimum value of 180 seconds (3rd minute) is used.

    - platform: cmee
      username: <username>
      password: <password>
      interval_seconds: 180
