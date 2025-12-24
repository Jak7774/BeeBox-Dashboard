# wifi_storage.py
import os
import struct
from wifi_encryption import encrypt, decrypt

CONFIG_FILE = "wifi_config.bin"
MAGIC = b"WCFG"   # sanity check

def save_wifi_credentials(ssid: str, password: str):
    ssid_enc = encrypt(ssid)
    pass_enc = encrypt(password)

    with open("wifi_config.tmp", "wb") as f:
        f.write(MAGIC)
        f.write(struct.pack(">H", len(ssid_enc)))
        f.write(ssid_enc)
        f.write(struct.pack(">H", len(pass_enc)))
        f.write(pass_enc)

    os.rename("wifi_config.tmp", CONFIG_FILE)


def load_wifi_credentials():
    try:
        with open(CONFIG_FILE, "rb") as f:
            if f.read(4) != MAGIC:
                raise ValueError("Invalid Wi-Fi config")

            ssid_len = struct.unpack(">H", f.read(2))[0]
            ssid = decrypt(f.read(ssid_len))

            pass_len = struct.unpack(">H", f.read(2))[0]
            password = decrypt(f.read(pass_len))

        return ssid, password

    except Exception as e:
        print("Wi-Fi config load failed:", e)
        return None, None


def wipe_wifi_credentials():
    try:
        os.remove(CONFIG_FILE)
    except:
        pass
