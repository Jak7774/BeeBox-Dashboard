# secure_store.py
from ucryptolib import aes
import machine
import hashlib
import json

CONFIG_FILE = "secret_config.json"
_cached_key = None

def _load_device_phrase():
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
            return cfg["device_phrase"].encode("utf-8")
    except:
        raise RuntimeError("Device hash missing from config.json")

def derive_key():
    global _cached_key
    if _cached_key:
        return _cached_key

    uid = machine.unique_id()
    phrase = _load_device_phrase()

    h = hashlib.sha256(uid + phrase).digest()
    _cached_key = h[:16]  # AES-128
    return _cached_key

def pad(data):
    while len(data) % 16:
        data += b'\x00'
    return data

def encrypt(text):
    key = derive_key()
    cipher = aes(key, 1)
    return cipher.encrypt(pad(text.encode()))

def decrypt(data):
    key = derive_key()
    cipher = aes(key, 1)
    return cipher.decrypt(data).rstrip(b'\x00').decode()
