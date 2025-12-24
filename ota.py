import urequests as requests
import ujson
import os
import time
import ubinascii
import hashlib

CONFIG_FILE = "config.json"
UPDATE_DIR = "UPDATE"
OLD_DIR = "OLD"

# ------------------------
# Utility helpers
# ------------------------

def ensure_dir(path):
    try:
        os.mkdir(path)
    except OSError:
        pass

def load_config():
    with open(CONFIG_FILE) as f:
        return ujson.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        ujson.dump(cfg, f)

def fetch_json(url):
    r = requests.get(url)
    data = r.json()
    r.close()
    return data

def fetch_file(url, dest):
    r = requests.get(url)
    with open(dest, "wb") as f:
        f.write(r.content)
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

# ------------------------
# OTA logic
# ------------------------

def ota_update():
    cfg = load_config()
    repo = cfg["github_repo_url"]
    local_version = cfg.get("version", "0.0.0")

    print("[OTA] Current version:", local_version)

    # Fetch remote config.json
    remote_cfg = fetch_json(repo + "config.json")
    remote_version = remote_cfg.get("version")

    if remote_version == local_version:
        print("[OTA] Already up to date")
        return

    print("[OTA] New version available:", remote_version)

    # Fetch file list
    file_list = fetch_json(repo + "file_list.json").get("files", [])
    if not file_list:
        print("[OTA] No files listed for update")
        return

    ensure_dir(UPDATE_DIR)
    ensure_dir(OLD_DIR)

    # ------------------------
    # Step 1: Download & verify hashes
    # ------------------------
    for entry in file_list:
        path = entry["path"]
        expected_hash = entry["sha256"]

        update_path = f"{UPDATE_DIR}/{path}"
        dir_path = "/".join(update_path.split("/")[:-1])
        if dir_path:
            ensure_dir(dir_path)

        print("[OTA] Downloading", path)
        fetch_file(repo + path, update_path)

        actual_hash = sha256_file(update_path)
        if actual_hash != expected_hash:
            print("[OTA] Hash mismatch:", path)
            raise Exception("Download verification failed")

    # ------------------------
    # Step 2: Backup current files
    # ------------------------
    for entry in file_list:
        path = entry["path"]
        if path in os.listdir():
            ensure_dir("/".join((OLD_DIR + "/" + path).split("/")[:-1]))
            os.rename(path, OLD_DIR + "/" + path)

    # ------------------------
    # Step 3: Replace files
    # ------------------------
    for entry in file_list:
        path = entry["path"]
        os.rename(UPDATE_DIR + "/" + path, path)

    # ------------------------
    # Step 4: Final verification
    # ------------------------
    for entry in file_list:
        if not path_exists(entry["path"]):
            raise Exception("Post-update verification failed")

    # ------------------------
    # Step 5: Update local version
    # ------------------------
    print("[OTA] Update successful →", remote_version)
    
    cfg["version"] = remote_version
    cfg["pending_reboot"] = True
    save_config(cfg)

    print("[OTA] Update applied, reboot required")

def path_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False
    
# Update Files
def safe_ota():
    try:
        ota_update()
    except Exception as e:
        print("[OTA] FAILED:", e)
        try:
            cfg = load_config()
            repo = cfg["github_repo_url"]
            file_list = fetch_json(repo + "file_list.json").get("files", [])
            rollback(file_list)
        except Exception as re:
            print("[OTA] Rollback failed:", re)


def rollback(file_list):
    print("[OTA] Rolling back updated files")

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


