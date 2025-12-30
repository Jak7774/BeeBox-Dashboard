import os
import json
import hashlib

# ----------------------
# Config
# ----------------------
PROJECT_FOLDER = "."              # Root of repo
OUTPUT_FILE = "file_list.json"
CONFIG_FILE = "config.json"

IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "OLD",
    "UPDATE"
}

IGNORE_FILES = {
    OUTPUT_FILE,
    CONFIG_FILE,
    "Create_FileList.py",
    "secret_config.json",
    "README.md",
}

# ----------------------
# Hash helpers
# ----------------------
def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def sha256_config_canonical(path):
    """
    Must match MicroPython OTA logic exactly
    """
    with open(path, "r") as f:
        data = json.load(f)

    # Remove runtime-only keys
    for k in ["setup_complete", "last_sensor_mode", "pending_reboot"]:
        data.pop(k, None)

    # Sort keys deterministically
    ordered = {k: data[k] for k in sorted(data)}

    # No separators, no indent (match ujson behaviour closely)
    canonical = json.dumps(ordered)

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

# ----------------------
# Load version
# ----------------------
with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

if "version" not in config:
    raise RuntimeError("config.json must contain a 'version' field")

version = config["version"]

print(f"[BUILD] Generating file_list.json for version {version}")

# ----------------------
# Walk project & hash files
# ----------------------
files_manifest = []

for root, dirs, files in os.walk(PROJECT_FOLDER):
    # Remove ignored directories in-place
    dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

    for filename in files:
        if filename in IGNORE_FILES:
            continue

        abs_path = os.path.join(root, filename)

        # Skip non-files (just in case)
        if not os.path.isfile(abs_path):
            continue

        rel_path = os.path.relpath(abs_path, PROJECT_FOLDER)
        rel_path = rel_path.replace("\\", "/")  # Windows safety

        if rel_path == CONFIG_FILE:
            sha = sha256_config_canonical(abs_path)
        else:
            sha = sha256_file(abs_path)

        files_manifest.append({
            "path": rel_path,
            "sha256": sha
        })

# Sort for deterministic output
files_manifest.sort(key=lambda x: x["path"])

# ----------------------
# Write file_list.json
# ----------------------
with open(OUTPUT_FILE, "w", newline="\n") as f:
    json.dump(
        {
            "version": version,
            "files": files_manifest
        },
        f,
        indent=2
    )

print(f"[BUILD] {OUTPUT_FILE} written")
print(f"[BUILD] Total files: {len(files_manifest)}")
