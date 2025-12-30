# wifi_utils.py

import network
import time
from wifi_encryption import decrypt
from wifi_storage import load_wifi_credentials

CONFIG_FILE = "wifi_config.bin"

# ---- Wi-Fi global state ----
WIFI_STATE = {
    "connected": False,        # association + IP
    "internet_ok": False,      # DNS/TCP confirmed
    "healthy": False,          # latched good state
    "failures": 0,             # consecutive failures
    "last_ok": 0               # time of last success
}

MAX_FAILURES_BEFORE_REBOOT = 5

def note_network_failure():
    WIFI_STATE["failures"] += 1
    print("[WIFI] Failure count:", WIFI_STATE["failures"])

    if WIFI_STATE["failures"] >= MAX_FAILURES_BEFORE_REBOOT:
        print("[WIFI] Too many failures — rebooting")
        time.sleep(1)
        import machine
        machine.reset()


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
    
def ensure_wifi():
    """
    Ensure Wi-Fi is connected and internet-capable.
    Latches healthy state once confirmed.
    """
    global WIFI_STATE
    wlan = network.WLAN(network.STA_IF)

    if WIFI_STATE["healthy"]:
        return True  # 🔒 trust latched state

    wlan.active(True)

    ssid, password = load_wifi_credentials()
    if not ssid:
        return False

    if not wlan.isconnected():
        wlan.connect(ssid, password)
        start = time.time()
        while not wlan.isconnected():
            if time.time() - start > 20:
                WIFI_STATE["failures"] += 1
                return False
            time.sleep(1)

    # Now test actual internet
    if has_internet():
        WIFI_STATE.update({
            "connected": True,
            "internet_ok": True,
            "healthy": True,      # 🔒 latch
            "failures": 0,
            "last_ok": time.time()
        })
        print("[WIFI] Connection healthy")
        return True

    WIFI_STATE["failures"] += 1
    return False


def is_connected():
    """Return True if Wi-Fi is connected and active."""
    wlan = network.WLAN(network.STA_IF)
    return wlan.active() and wlan.isconnected()
