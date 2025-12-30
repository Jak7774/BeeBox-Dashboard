# ===== ota.py =====
import urequests as requests
import ujson
import os
import ubinascii
import hashlib

CONFIG_FILE = "config.json"
UPDATE_DIR = "UPDATE"
OLD_DIR = "OLD"
OTA_FLAG = "OTA_PENDING"

RUNTIME_CONFIG_KEYS = {
    "setup_complete",
    "last_sensor_mode",
    "pending_reboot"
}

# -------------------------------------------------
# Utility helpers
# -------------------------------------------------

def walk(path):
    """MicroPython-compatible os.walk()"""
    try:
        names = os.listdir(path)
    except OSError:
        return

    dirs = []
    files = []

    for name in names:
        full = path + "/" + name
        try:
            mode = os.stat(full)[0]
        except OSError:
            continue

        if mode & 0x4000:
            dirs.append(name)
        else:
            files.append(name)

    yield path, dirs, files

    for d in dirs:
        for x in walk(path + "/" + d):
            yield x

def ensure_dir(path):
    parts = path.split("/")
    current = ""
    for p in parts:
        if not p:
            continue
        current = current + p + "/"
        try:
            os.mkdir(current)
        except OSError:
            pass

def path_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def load_config():
    with open(CONFIG_FILE) as f:
        return ujson.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        ujson.dump(cfg, f)

# -------------------------------------------------
# Hash helpers
# -------------------------------------------------

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(512)
            if not chunk:
                break
            h.update(chunk)
    return ubinascii.hexlify(h.digest()).decode()

def sha256_json_canonical(path):
    with open(path, "r") as f:
        data = ujson.load(f)

    for k in RUNTIME_CONFIG_KEYS:
        data.pop(k, None)

    ordered = {k: data[k] for k in sorted(data)}
    canonical = ujson.dumps(ordered)

    h = hashlib.sha256(bytes(canonical, "utf-8"))
    return ubinascii.hexlify(h.digest()).decode()

# -------------------------------------------------
# Network helpers
# -------------------------------------------------

def fetch_json(url):
    r = requests.get(url)
    try:
        if r.status_code != 200:
            raise RuntimeError("HTTP %d" % r.status_code)
        return ujson.loads(r.text)
    finally:
        r.close()

def fetch_file(url, dest):
    ensure_dir("/".join(dest.split("/")[:-1]))
    r = requests.get(url)
    if r.status_code != 200:
        raise RuntimeError("HTTP %d" % r.status_code)
    with open(dest, "wb") as f:
        f.write(r.content)
    r.close()

# -------------------------------------------------
# Step 1: Download & verify update
# -------------------------------------------------

def download_and_verify_update():
    cfg = load_config()
    repo = cfg["github_repo_url"]
    local_version = cfg.get("version", "0.0.0")

    print("[OTA] Current version:", local_version)

    manifest = fetch_json(repo + "file_list.json")
    remote_version = manifest.get("version")
    files = manifest.get("files", [])

    if not remote_version or not files:
        raise RuntimeError("Invalid file_list.json")

    if remote_version == local_version:
        print("[OTA] Already up to date")
        return False

    print("[OTA] New version available:", remote_version)

    ensure_dir(UPDATE_DIR)
    ensure_dir(OLD_DIR)

    for entry in files:
        path = entry["path"]
        expected = entry["sha256"]

        dst = path
        tmp = UPDATE_DIR + "/" + path

        # Skip unchanged files
        if path_exists(dst):
            if path == CONFIG_FILE:
                current_hash = sha256_json_canonical(dst)
            else:
                current_hash = sha256_file(dst)

            if current_hash == expected:
                print("[OTA] Skipping unchanged:", path)
                continue

        print("[OTA] Downloading:", path)
        fetch_file(repo + path, tmp)

        # Verify downloaded file
        if path == CONFIG_FILE:
            actual = sha256_json_canonical(tmp)
        else:
            actual = sha256_file(tmp)

        if actual != expected:
            raise RuntimeError("Hash mismatch: " + path)

    print("[OTA] All required files downloaded and verified")

    # Signal apply at boot
    cfg["pending_reboot"] = True
    save_config(cfg)

    with open(OTA_FLAG, "w") as f:
        f.write("1")

    return True

# -------------------------------------------------
# Safe OTA trigger (called during runtime)
# -------------------------------------------------

def safe_ota():
    try:
        updated = download_and_verify_update()
        if updated:
            print("[OTA] Update staged; reboot deferred to main loop")
        else:
            print("[OTA] No update required")
    except Exception as e:
        print("[OTA] FAILED:", e)

# -------------------------------------------------
# Step 2: Apply update at boot
# -------------------------------------------------

def apply_update():
    if not path_exists(OTA_FLAG):
        return

    print("[OTA] Applying update at boot")

    if not path_exists(UPDATE_DIR):
        print("[OTA] UPDATE directory missing")
        return

    ensure_dir(OLD_DIR)

    for root, dirs, files in walk(UPDATE_DIR):
        for name in files:
            src = root + "/" + name
            dst = src.replace(UPDATE_DIR + "/", "")

            ensure_dir("/".join(dst.split("/")[:-1]))

            # Backup existing file
            if path_exists(dst):
                backup = OLD_DIR + "/" + dst
                ensure_dir("/".join(backup.split("/")[:-1]))
                try:
                    os.rename(dst, backup)
                    print("[OTA] Backed up:", dst)
                except:
                    print("[OTA] Backup failed:", dst)

            os.rename(src, dst)
            print("[OTA] Updated:", dst)

    # Cleanup
    try:
        os.remove(OTA_FLAG)
    except:
        pass

    try:
        os.rmdir(UPDATE_DIR)
    except:
        pass

    print("[OTA] Update applied successfully")

