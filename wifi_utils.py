# wifi_utils.py

import network
import time
from wifi_encryption import decrypt
from wifi_storage import load_wifi_credentials

CONFIG_FILE = "wifi_config.bin"

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
    """Connect to Wi-Fi using credentials, choosing the strongest 2.4 GHz AP if multiple exist."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    ssid, password = load_wifi_credentials()
    if not ssid:
        print("No Wi-Fi credentials found")
        return False

    print("Scanning for nearby networks...")
    networks = wlan.scan()  # returns list of tuples (ssid, bssid, channel, RSSI, security, hidden)
    
    # Filter networks with matching SSID
    candidates = [n for n in networks if n[0].decode() == ssid and n[2] <= 14]  # channels 1-14 = 2.4 GHz
    if not candidates:
        print(f"No 2.4 GHz AP found for SSID '{ssid}'")
        return False

    # Pick the strongest signal
    best = max(candidates, key=lambda x: x[3])  # x[3] = RSSI
    print(f"Connecting to SSID '{ssid}' on channel {best[2]} with signal {best[3]} dBm")

    wlan.connect(ssid, password)

    start = time.time()
    while not wlan.isconnected():
        if time.time() - start > timeout:
            print("Wi-Fi connection timeout")
            return False
        print("Connecting to Wi-Fi...")
        time.sleep(1)

    print("Connected! IP:", wlan.ifconfig()[0])
    return True

def is_connected():
    """Return True if Wi-Fi is connected and active."""
    wlan = network.WLAN(network.STA_IF)
    return wlan.active() and wlan.isconnected()
