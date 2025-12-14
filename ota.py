# ===== ota.py =====
import urequests
import os
import time
import machine

# ================= CONFIG =================
BASE_URL = "https://raw.githubusercontent.com/YOUR_GITHUB/YOUR_REPO/main/"

VERSION_FILE = "version.txt"
MANIFEST_FILE = "manifest.json"

UPDATE_DIR = "Update"
LAST_CHECK_FILE = "last_ota_check.txt"

# Change this later without touching main.py
UPDATE_INTERVAL = 7 * 24 * 60 * 60   # 1 week
# =========================================


# ---------- File helpers ----------
def _read(path, default=""):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except:
        return default

def _write(path, data):
    with open(path, "w") as f:
        f.write(data)

def _now():
    try:
        return time.time()
    except:
        return 0


# ---------- Timing ----------
def _should_check():
    try:
        last = int(_read(LAST_CHECK_FILE, "0"))
    except:
        return True
    return (_now() - last) >= UPDATE_INTERVAL

def _mark_checked():
    _write(LAST_CHECK_FILE, str(_now()))


# ---------- Version ----------
def _local_version():
    return _read(VERSION_FILE, "0.0.0")

def _remote_version():
    r = urequests.get(BASE_URL + VERSION_FILE, timeout=5)
    v = r.text.strip()
    r.close()
    return v


# ---------- OTA helpers ----------
def _ensure_update_dir():
    if UPDATE_DIR not in os.listdir():
        os.mkdir(UPDATE_DIR)

def _download_file(rel_path):
    url = BASE_URL + rel_path
    local_path = UPDATE_DIR + "/" + rel_path

    # Ensure subdirectories exist
    parts = local_path.split("/")[:-1]
    path = ""
    for p in parts:
        path = p if not path else path + "/" + p
        if path and path not in os.listdir("/" if "/" not in path else path.rsplit("/", 1)[0]):
            try:
                os.mkdir(path)
            except:
                pass

    r = urequests.get(url, timeout=10)
    with open(local_path, "w") as f:
        f.write(r.text)
    r.close()


def _load_manifest():
    r = urequests.get(BASE_URL + MANIFEST_FILE, timeout=5)
    data = r.json()
    r.close()
    return data.get("files", [])


def _apply_update(files):
    for file in files:
        src = UPDATE_DIR + "/" + file
        if src not in _walk_files(UPDATE_DIR):
            raise Exception("Missing file: " + file)

        if file in os.listdir():
            os.remove(file)

        os.rename(src, file)


def _walk_files(root):
    found = []
    for entry in os.listdir(root):
        path = root + "/" + entry
        try:
            os.listdir(path)
            found.extend(_walk_files(path))
        except:
            found.append(path)
    return found


# ---------- OTA core ----------
def _perform_update():
    print("OTA: Checking versions")

    remote = _remote_version()
    local = _local_version()

    if remote == local:
        print("OTA: Already up to date")
        return False

    print("OTA: New version", remote)

    files = _load_manifest()
    _ensure_update_dir()

    # Download all files first
    for file in files:
        print("OTA: Downloading", file)
        _download_file(file)

    # Replace files only after successful download
    print("OTA: Applying update")
    _apply_update(files)

    _write(VERSION_FILE, remote)

    print("OTA: Update complete, rebooting")
    time.sleep(1)
    machine.reset()


# ---------- Public API ----------
def maybe_check(force=False):
    """
    Called by main.py
    force=True  -> always check
    force=False -> interval-based
    """
    try:
        if not force and not _should_check():
            return

        _mark_checked()
        _perform_update()

    except Exception as e:
        print("OTA failed:", e)
