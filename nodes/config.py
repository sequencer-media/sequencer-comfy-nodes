"""
Sequencer ComfyUI Nodes — Configuration

Handles API key loading from config file or environment variable.
"""

import os
import json

# ─── Firebase Project Config (public, not secret) ───
FIREBASE_PROJECT_ID = "smoothieeditor"
FIRESTORE_BASE_URL = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents"

# ─── V3 Generation Endpoint ───
V3_ENDPOINT = "https://generate-unified-task-v3-649436726272.us-central1.run.app"

# ─── Workspace Manager Endpoint ───
WORKSPACE_ENDPOINT = "https://workspace-manager-649436726272.us-central1.run.app"

# ─── Config File Path ───
CONFIG_DIR = os.path.expanduser("~/.sequencer")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def get_api_key() -> str:
    """
    Load the Sequencer API key from:
      1. Environment variable SEQUENCER_API_KEY
      2. Config file ~/.sequencer/config.json
    
    Returns empty string if not configured.
    """
    # 1. Check environment variable
    env_key = os.environ.get("SEQUENCER_API_KEY", "").strip()
    if env_key:
        return env_key
    
    # 2. Check config file
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
            key = config.get("api_key", "").strip()
            if key:
                return key
        except (json.JSONDecodeError, IOError) as e:
            print(f"[Sequencer] Warning: Could not read config file: {e}")
    
    return ""


def get_workspace_id() -> str:
    """
    Load the workspace ID from config.
    If not set, the node will attempt to auto-detect the user's default workspace.
    """
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
            return config.get("workspace_id", "").strip()
        except (json.JSONDecodeError, IOError):
            pass
    
    return os.environ.get("SEQUENCER_WORKSPACE_ID", "").strip()


def save_config(api_key: str, workspace_id: str = ""):
    """Save API key and workspace ID to the config file."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    
    config = {}
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    if api_key:
        config["api_key"] = api_key
    if workspace_id:
        config["workspace_id"] = workspace_id
    
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    
    # Set restrictive permissions on the config file (Unix only)
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass
