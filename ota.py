import urequests as requests
import ujson
import os
import time
import shutil

# --- Configurable globals ---
CONFIG_FILE = "config.json"
UPDATE_FOLDER = "UPDATE"
OLD_FOLDER = "OLD"

# --- Load config ---
with open(CONFIG_FILE) as f:
    config = ujson.load(f)

GITHUB_URL = config.get("github_repo_url")
LOCAL_VERSION = config.get("version")
CHECK_INTERVAL_HOURS = config.get("check_interval_hours", 24)

# --- Helper functions ---
def fetch_text(url):
    try:
        r = requests.get(url)
        if r.status_code == 200:
            return r.text
    except Exception as e:
        print("Fetch failed:", e)
    return None

def fetch_json(url):
    text = fetch_text(url)
    if text:
        try:
            return ujson.loads(text)
        except Exception as e:
            print("JSON parse failed:", e)
    return None

def download_file(file_name):
    url = GITHUB_URL + file_name
    dest_path = f"{UPDATE_FOLDER}/{file_name}"
    try:
        content = fetch_text(url)
        if content is not None:
            # Ensure directory exists
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "w") as f:
                f.write(content)
            return True
    except Exception as e:
        print("Download failed:", file_name, e)
    return False

def backup_files(file_list):
    os.makedirs(OLD_FOLDER, exist_ok=True)
    for f in file_list:
        if os.path.exists(f):
            os.makedirs(os.path.dirname(f"{OLD_FOLDER}/{f}"), exist_ok=True)
            shutil.copy(f, f"{OLD_FOLDER}/{f}")

def replace_files(file_list):
    for f in file_list:
        src = f"{UPDATE_FOLDER}/{f}"
        if os.path.exists(src):
            shutil.copy(src, f)
        else:
            print("Missing update file:", f)
            return False
    return True

def verify_files(file_list):
    for f in file_list:
        if not os.path.exists(f):
            print("Verification failed:", f)
            return False
    return True

# --- Main OTA process ---
def ota_update():
    global LOCAL_VERSION
    print("Checking for updates...")
    
    latest_version = fetch_text(GITHUB_URL + "version.txt")
    if not latest_version or latest_version.strip() == LOCAL_VERSION:
        print("Already up-to-date.")
        return
    
    latest_version = latest_version.strip()
    print(f"New version found: {latest_version}")
    
    file_list_json = fetch_json(GITHUB_URL + "file_list.json")
    if not file_list_json or "files" not in file_list_json:
        print("Failed to fetch file list")
        return
    
    files_to_update = file_list_json["files"]

    # Step 1: Download to UPDATE folder
    os.makedirs(UPDATE_FOLDER, exist_ok=True)
    for f in files_to_update:
        if not download_file(f):
            print("Download failed, will retry later")
            return
    
    # Step 2: Backup existing files
    backup_files(files_to_update)
    
    # Step 3: Replace files
    if not replace_files(files_to_update):
        print("Update failed, restoring OLD files")
        replace_files([f"{OLD_FOLDER}/{f}" for f in files_to_update])
        return
    
    # Step 4: Verify
    if verify_files(files_to_update):
        print("Update successful!")
        # Update local version
        config["version"] = latest_version
        with open(CONFIG_FILE, "w") as f:
            ujson.dump(config, f)
    else:
        print("Verification failed, restoring OLD files")
        replace_files([f"{OLD_FOLDER}/{f}" for f in files_to_update])

# --- Periodic check ---
while True:
    ota_update()
    print(f"Next check in {CHECK_INTERVAL_HOURS} hours...")
    time.sleep(CHECK_INTERVAL_HOURS * 3600)
