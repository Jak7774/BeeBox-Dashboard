# ===== ota.py =====
import urequests as requests
import ujson
import os
import utime
import ubinascii
import hashlib
import machine

CONFIG_FILE = "config.json"
UPDATE_DIR = "UPDATE"
OLD_DIR = "OLD"
OTA_FLAG = "OTA_PENDING"

RUNTIME_CONFIG_KEYS = {
    "setup_complete",
    "last_sensor_mode",
    "pending_reboot"
}

# ------------------------
# Utility helpers
# ------------------------

def ensure_dir(path):
    parts = path.split("/")
    current = ""
    for p in parts:
        if not p:
            continue
        current += p + "/"
        try:
            os.mkdir(current)
        except OSError:
            pass

def load_config():
    with open(CONFIG_FILE) as f:
        return ujson.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        ujson.dump(cfg, f)

def fetch_file(url, dest):
    # Ensure parent directories exist
    dir_path = "/".join(dest.split("/")[:-1])
    if dir_path:
        ensure_dir(dir_path)

    r = requests.get(url)
    if r.status_code != 200:
        raise Exception("Failed to fetch %s (HTTP %d)" % (url, r.status_code))

    with open(dest, "wb") as f:
        f.write(r.content)
    r.close()

def fetch_json(url):
    r = requests.get(url)
    try:
        if r.status_code != 200:
            raise Exception("HTTP %d" % r.status_code)
        return ujson.loads(r.text)
    finally:
        r.close()

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
    """
    Hash JSON after removing runtime-only keys
    and serializing deterministically.
    """
    with open(path, "r") as f:
        data = ujson.load(f)

    for k in RUNTIME_CONFIG_KEYS:
        data.pop(k, None)

    # Canonical JSON: sorted keys, no whitespace
    canonical = ujson.dumps(data, sort_keys=True)
    h = hashlib.sha256(bytes(canonical, "utf-8"))
    return ubinascii.hexlify(h.digest()).decode()

def path_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

# ------------------------
# Step 1: Download & verify update
# ------------------------

def download_and_verify_update():
    """
    Download all files to UPDATE_DIR and verify hashes.
    Returns True if update available and downloaded.
    """
    cfg = load_config()
    repo = cfg["github_repo_url"]
    local_version = cfg.get("version", "0.0.0")

    print("[OTA] Current version:", local_version)

    remote_cfg = fetch_json(repo + "config.json")
    remote_version = remote_cfg.get("version")

    if remote_version == local_version:
        print("[OTA] Already up to date")
        return False

    print("[OTA] New version available:", remote_version)

    file_list = fetch_json(repo + "file_list.json").get("files", [])
    if not file_list:
        print("[OTA] No files listed for update")
        return False

    ensure_dir(UPDATE_DIR)
    ensure_dir(OLD_DIR)

    for entry in file_list:
        path = entry["path"]
        expected_hash = entry["sha256"]

        update_path = f"{UPDATE_DIR}/{path}"
        dir_path = "/".join(update_path.split("/")[:-1])
        if dir_path:
            ensure_dir(dir_path)

        print("[OTA] Downloading", path)
        fetch_file(repo + path, update_path)

        if path == "config.json":
            actual_hash = sha256_json_canonical(update_path)
        else:
            actual_hash = sha256_file(update_path)
            
        if actual_hash != expected_hash:
            print("[OTA] Hash mismatch:", path)
            raise Exception("Download verification failed")

    print("[OTA] All files downloaded and verified")
    return True

# ------------------------
# Step 2: Safe trigger OTA
# ------------------------

def safe_ota():
    try:
        updated = download_and_verify_update()
        if not updated:
            print("[OTA] No update needed")
            return

        # Signal main loop to reboot safely
        cfg = load_config()
        cfg["pending_reboot"] = True
        save_config(cfg)

        print("[OTA] Update ready. Reboot will occur via main loop.")

    except Exception as e:
        print("[OTA] FAILED:", e)

# ------------------------
# Step 3: Apply update at boot
# ------------------------

def apply_update():
    """
    Called at boot if OTA_PENDING exists.
    Moves files from UPDATE_DIR to root, backs up old files.
    """
    print("[OTA] Applying update at boot...")

    ensure_dir(OLD_DIR)

    for root, dirs, files in os.walk(UPDATE_DIR):
        for name in files:
            src = root + "/" + name
            dst = src.replace(UPDATE_DIR + "/", "")

            # Backup existing file
            dst_dir = "/".join(dst.split("/")[:-1])
            if dst_dir:
                ensure_dir(dst_dir)

            if path_exists(dst):
                backup_path = OLD_DIR + "/" + dst
                backup_dir = "/".join(backup_path.split("/")[:-1])
                if backup_dir:
                    ensure_dir(backup_dir)
                try:
                    os.rename(dst, backup_path)
                    print("[OTA] Backed up:", dst)
                except:
                    print("[OTA] Backup failed:", dst)

            # Move new file
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

    # Update version in config
    cfg = load_config()
    remote_cfg = fetch_json(cfg["github_repo_url"] + "config.json")

    # Preserve runtime-only keys
    for k in RUNTIME_CONFIG_KEYS:
        if k in cfg:
            remote_cfg[k] = cfg[k]

    # Always keep version from remote
    cfg = remote_cfg

    # Request reboot via main
    cfg["pending_reboot"] = True
    save_config(cfg)
    print("[OTA] Update applied successfully; reboot deferred to main")

# ------------------------
# Rollback
# ------------------------

def rollback(file_list):
    print("[OTA] Rolling back updated files...")
    for entry in file_list:
        path = entry["path"]
        old_path = OLD_DIR + "/" + path
        if path_exists(old_path):
            try:
                if path_exists(path):
                    os.remove(path)
                os.rename(old_path, path)
                print("[OTA] Restored:", path)
            except Exception as e:
                print("[OTA] Restore failed:", path, e)
