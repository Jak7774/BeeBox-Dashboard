import os
import json
import hashlib
import requests

# ----------------------
# Config
# ----------------------
PROJECT_FOLDER = "."              # Local repo folder
OUTPUT_FILE = "file_list.json"    # File list to generate
CONFIG_FILE = "config.json"       # Config file containing version
IGNORE = ["OLD", "UPDATE", ".git", "__pycache__"]
GITHUB_FILE_LIST_URL = "https://raw.githubusercontent.com/jak7774/BeeBox-Dashboard/main/file_list.json"

# ----------------------
# Helper functions
# ----------------------
def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def sha256_config_canonical(path):
    with open(path, "r") as f:
        data = json.load(f)

    for k in ["setup_complete", "last_sensor_mode", "pending_reboot"]:
        data.pop(k, None)

    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()

def fetch_github_json(url):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("Could not fetch from GitHub:", e)
    return {"files": []}

# ----------------------
# 1. Load local version from config.json
# ----------------------
with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

local_version = config.get("version", "0.0.0")

# ----------------------
# 2. Scan local files & compute hashes (skip directories)
# ----------------------
local_files = {}
for root, dirs, files in os.walk(PROJECT_FOLDER):
    # Remove ignored directories
    dirs[:] = [d for d in dirs if d not in IGNORE]
    for file in files:
        # Skip ignored files
        if file in IGNORE:
            continue
        abs_path = os.path.join(root, file)
        # Ensure it's a file, not a directory
        if not os.path.isfile(abs_path):
            continue
        # Relative path with forward slashes
        rel_path = os.path.relpath(abs_path, PROJECT_FOLDER).replace("\\", "/")
        
        if rel_path == "config.json":
            local_files[rel_path] = sha256_config_canonical(abs_path)
        else:
            local_files[rel_path] = sha256_file(abs_path)


# ----------------------
# 3. Fetch previous file_list.json from GitHub
# ----------------------
github_file_list = fetch_github_json(GITHUB_FILE_LIST_URL)
github_hashes = {f["path"]: f.get("sha256", "") for f in github_file_list.get("files", [])}

# ----------------------
# 4. Determine changed files
# ----------------------
files_to_update = []
for path, hash_val in local_files.items():
    if github_hashes.get(path) != hash_val:
        files_to_update.append({"path": path, "sha256": hash_val})

# ----------------------
# 5. Update version in config.json if needed
# ----------------------
if files_to_update:
    major, minor, patch = map(int, local_version.split("."))
    patch += 1
    new_version = f"{major}.{minor}.{patch}"

    # Save new version
    config["version"] = new_version
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

    print(f"Version updated: {local_version} → {new_version}")
else:
    print("No changes detected. Version stays the same.")

# ----------------------
# 6. Write new file_list.json (only files)
# ----------------------
with open(OUTPUT_FILE, "w") as f:
    json.dump({"files": files_to_update}, f, indent=4)

print(f"{OUTPUT_FILE} created with {len(files_to_update)} changed files.")
if not files_to_update:
    print("No files need to be updated in OTA.")
