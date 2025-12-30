# ===== ota.py =====
import urequests as requests
import ujson
import os
import ubinascii
import hashlib

CONFIG_FILE = "config.json"
UPDATE_DIR = "UPDATE"
OLD_DIR = "OLD"

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

def clear_folder(folder):
    """Remove all files and subfolders in a folder"""
    if not path_exists(folder):
        return
    for root, dirs, files in walk(folder):
        for name in files:
            try:
                os.remove(root + "/" + name)
            except:
                pass
        for d in dirs:	
            subfolder = root + "/" + d
            clear_folder(subfolder)  # recursively clear subfolders
            try:
                os.rmdir(subfolder)   # remove the empty subfolder
            except:
                pass

# -----------------------------
# Config helpers
# -----------------------------

def load_config():
    with open(CONFIG_FILE) as f:
        return ujson.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        ujson.dump(cfg, f)

def merge_remote_config_stage():
    """
    Fetch remote config but stage it in UPDATE/config.json
    instead of merging immediately into live config.
    """
    cfg = load_config()
    repo = cfg["github_repo_url"]
    remote = fetch_json(repo + "config.json")

    # Save staged config to UPDATE folder
    staged_path = UPDATE_DIR + "/config.json"
    ensure_dir(UPDATE_DIR)
    with open(staged_path, "w") as f:
        ujson.dump(remote, f)

    return staged_path, cfg.get("version"), remote.get("version")

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
    folder = "/".join(dest.split("/")[:-1])
    ensure_dir(folder)
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
    
    # Clear staging folders to prevent partial downloads
    ensure_dir(UPDATE_DIR)
    ensure_dir(OLD_DIR)
    clear_folder(UPDATE_DIR)
    clear_folder(OLD_DIR)

    # Merge config but **do not overwrite local version yet**
    staged_config_path, local_version, remote_version = merge_remote_config_stage()

    print("[OTA] Current version:", local_version)
    
    manifest = fetch_json(repo + "file_list.json")
    files = manifest.get("files", [])

    if not remote_version or not files:
        raise RuntimeError("Invalid file_list.json")

    # Stage config-only update without touching firmware files
    if remote_version == local_version:
        if config_changed:
            print("[OTA] Config updated (no firmware change)")
        else:
            print("[OTA] Already up to date")
        return False

    print("[OTA] New firmware version available:", remote_version)

    for entry in files:
        path = entry["path"]
        expected = entry["sha256"]

        dst = path
        tmp = UPDATE_DIR + "/" + path

        # Skip unchanged files
        if path_exists(path) and sha256_file(path) == expected:
            print("[OTA] Skipping unchanged:", path)
            continue

        print("[OTA] Downloading:", path)
        fetch_file(repo + path, tmp)

        actual = sha256_file(tmp)
        if actual != expected:
            raise RuntimeError("Hash mismatch: " + path)

    print("[OTA] All required files downloaded and verified")

    # ---- Stage reboot ----
    cfg["pending_reboot"] = True
    save_config(cfg)
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
    cfg = load_config()
    if not cfg.get("pending_reboot"):
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
            
    # Apply staged config
    staged_cfg_path = UPDATE_DIR + "/config.json"
    if path_exists(staged_cfg_path):
        try:
            staged_cfg = ujson.load(open(staged_cfg_path))
            cfg = load_config()
            for key, value in staged_cfg.items():
                if key not in RUNTIME_CONFIG_KEYS:
                    cfg[key] = value
            cfg["pending_reboot"] = False
            save_config(cfg)
            print("[OTA] Config updated after firmware apply - Pending Reboot = FALSE")
        except Exception as e:
            print("[OTA] Failed to apply staged config:", e)
            
    # Cleanup    
    clear_folder(UPDATE_DIR)
    print("[OTA] Update applied successfully")


