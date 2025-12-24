# ===== settings_config.py =====
import json
import os

SETTINGS_FILE = "settings.json"

# Default configuration values
DEFAULT_SETTINGS = {
    "autoscroll": True,           # Automatically scroll through hives
    "update_period": 300,         # Background update period (seconds)
    "brightness": 100,            # LCD backlight brightness (0–100%)
    "units": "C",                 # 'C' or 'F' for temperature
    "wifi_auto_reconnect": True   # Attempt Wi-Fi reconnect automatically
}

def load_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            loaded = json.load(f)
    except OSError:
        # File missing or filesystem temporarily unavailable
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    except ValueError:
        # Corrupt JSON
        print("Settings JSON corrupted, resetting to defaults")
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

    # Merge defaults (for upgrades)
    for key, val in DEFAULT_SETTINGS.items():
        if key not in loaded:
            loaded[key] = val

    return loaded



def save_settings(settings):
    """Write settings to JSON file."""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)
    except Exception as e:
        print("Error saving settings:", e)

def get_setting(key):
    """Convenience getter (returns default if missing)."""
    settings = load_settings()
    return settings.get(key, DEFAULT_SETTINGS.get(key))

def set_setting(key, value):
    s = load_settings()
    s[key] = value
    save_settings(s)
