# wifi_utils.py

import network
import time
import wifi_config  # import your config with SSID and PASSWORD

def connect_to_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(wifi_config.WIFI_SSID, wifi_config.WIFI_PASSWORD)
    
    while not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        time.sleep(1)
    
    print("Connected! IP address:", wlan.ifconfig()[0])
    
def is_connected():
    """Return True if Wi-Fi is connected and active."""
    wlan = network.WLAN(network.STA_IF)
    return wlan.active() and wlan.isconnected()

