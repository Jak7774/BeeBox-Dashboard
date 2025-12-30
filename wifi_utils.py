# wifi_utils.py

import network
import time
from wifi_encryption import decrypt
from wifi_storage import load_wifi_credentials

CONFIG_FILE = "wifi_config.bin"

def has_internet(timeout=3):
    try:
        import socket
        s = socket.socket()
        s.settimeout(timeout)
        s.connect(("8.8.8.8", 53))
        s.close()
        return True
    except:
        return False

def _load_wifi_credentials():
    """Load and decrypt Wi-Fi credentials.
    Returns:
        (ssid, password) or (None, None) if not found or invalid
    """
    try:
        with open(CONFIG_FILE, "rb") as f:
            ssid = decrypt(f.readline().strip())
            password = decrypt(f.readline().strip())
        return ssid, password
    except Exception as e:
        print("Wi-Fi config load failed:", e)
        return None, None

def connect_to_wifi(timeout=20):
    """Connect to Wi-Fi using saved credentials.
    Mesh-safe: does NOT depend on scan results.
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    ssid, password = load_wifi_credentials()
    if not ssid:
        print("No Wi-Fi credentials found")
        return False

    if wlan.isconnected():
        if has_internet():
            print("Wi-Fi already connected and internet OK")
            return True
        else:
            print("Wi-Fi connected but internet broken — resetting")
            wlan.disconnect()
            wlan.active(False)
            time.sleep(1)
            wlan.active(True)


    print("Connecting to Wi-Fi:", ssid)

    # Optional scan (diagnostics only)
    try:
        nets = wlan.scan()
        print("Scan found:", [n[0].decode() for n in nets])
    except Exception as e:
        print("Wi-Fi scan skipped:", e)

    # Direct connect (works even if scan fails)
    wlan.connect(ssid, password)

    start = time.time()
    while not wlan.isconnected():
        if time.time() - start > timeout:
            print("Wi-Fi connection timeout")
            return False
        time.sleep(1)

    print("Connected! IP:", wlan.ifconfig()[0])
    return True


def is_connected():
    """Return True if Wi-Fi is connected and active."""
    wlan = network.WLAN(network.STA_IF)
    return wlan.active() and wlan.isconnected()

