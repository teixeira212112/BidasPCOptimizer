"""
state_manager.py – Persistent JSON state for Bidas PC Optimizer
Stores original registry values, service startup types, and removed Appx packages.
The state.json is saved in an "appdata" folder next to the executable (portable mode).
"""

import os
import sys
import json
import re
import winreg
import subprocess
from pathlib import Path
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────────────
# Base directory detection (portable: next to .exe)
# ──────────────────────────────────────────────────────────────────────────────
def _get_base_dir():
    """Return the directory where the executable/script is located."""
    if getattr(sys, 'frozen', False):
        # PyInstaller bundle: use the directory of the .exe
        return Path(sys.executable).parent
    else:
        # Development mode: use the project root (scripts/ is one level down)
        return Path(__file__).parent.parent

# State directory: appdata folder inside the program's base directory
STATE_DIR = _get_base_dir() / "appdata"
STATE_FILE = STATE_DIR / "state.json"

# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────
def _ensure_dir():
    STATE_DIR.mkdir(parents=True, exist_ok=True)

def _load_state():
    _ensure_dir()
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def _save_state(state):
    _ensure_dir()
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def _hidden_startupinfo():
    """STARTUPINFO that suppresses any console window on Windows."""
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    return si

# ──────────────────────────────────────────────────────────────────────────────
# Power scheme utilities
# ──────────────────────────────────────────────────────────────────────────────
def powercfg_list():
    """Return dict {guid_lower: name} of all existing power schemes."""
    result = subprocess.run(
        ["powercfg", "/list"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        startupinfo=_hidden_startupinfo(),
        creationflags=0x08000000,  # CREATE_NO_WINDOW
    )
    output = result.stdout
    schemes = {}
    for line in output.splitlines():
        # Example: "Guid: 381b4222-f694-41f0-9685-ff5bb260df2e  (Equilibrado)"
        match = re.search(r"Guid:\s*([a-f0-9\-]+)\s*\((.+)\)", line, re.I)
        if match:
            guid, name = match.groups()
            schemes[guid.lower()] = name.strip()
    return schemes

# ──────────────────────────────────────────────────────────────────────────────
# Registry backup / restore
# ──────────────────────────────────────────────────────────────────────────────
def backup_reg_value(key_hive, subkey, value_name, reg_type=None):
    """
    Save current registry value before changing it.
    key_hive: integer from winreg (e.g. winreg.HKEY_CURRENT_USER)
    Returns the original value (or None if key didn't exist).
    """
    state = _load_state()
    hive_name = {
        winreg.HKEY_CLASSES_ROOT: "HKCR",
        winreg.HKEY_CURRENT_USER: "HKCU",
        winreg.HKEY_LOCAL_MACHINE: "HKLM",
        winreg.HKEY_USERS: "HKU",
        winreg.HKEY_CURRENT_CONFIG: "HKCC"
    }.get(key_hive, str(key_hive))
    path = f"{hive_name}:{subkey}\\{value_name}"
    
    if path in state.get("registry", {}):
        return state["registry"][path].get("original_value")

    try:
        with winreg.OpenKey(key_hive, subkey, 0, winreg.KEY_READ) as k:
            value, reg_type = winreg.QueryValueEx(k, value_name)
            if isinstance(value, bytes):
                value = value.decode('utf-8', errors='replace')
            elif not isinstance(value, (int, str)):
                value = str(value)
        exists = True
    except (FileNotFoundError, WindowsError):
        value = None
        exists = False

    if "registry" not in state:
        state["registry"] = {}
    state["registry"][path] = {
        "original_value": value,
        "original_type": reg_type,
        "existed": exists,
        "backup_time": datetime.now().isoformat()
    }
    _save_state(state)
    return value

def restore_reg_value(key_hive, subkey, value_name):
    """
    Restore previously backed up registry value and remove from state.
    Returns True if restored/deleted, False if no backup.
    """
    state = _load_state()
    hive_name = {
        winreg.HKEY_CLASSES_ROOT: "HKCR",
        winreg.HKEY_CURRENT_USER: "HKCU",
        winreg.HKEY_LOCAL_MACHINE: "HKLM",
        winreg.HKEY_USERS: "HKU",
        winreg.HKEY_CURRENT_CONFIG: "HKCC"
    }.get(key_hive, str(key_hive))
    path = f"{hive_name}:{subkey}\\{value_name}"
    
    backup = state.get("registry", {}).get(path)
    if not backup:
        return False

    original = backup["original_value"]
    reg_type = backup.get("original_type")
    if not isinstance(reg_type, int):
        reg_type = winreg.REG_SZ
    existed = backup.get("existed", True)

    # If the key originally existed and we have a value, restore it
    if existed and original is not None:
        try:
            with winreg.OpenKey(key_hive, subkey, 0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, value_name, 0, reg_type, original)
        except:
            pass
    elif existed and original is None:
        # Value existed but was None? Should not happen; delete it just in case
        try:
            with winreg.OpenKey(key_hive, subkey, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, value_name)
        except:
            pass
    else:
        # The key originally did NOT exist: try to delete the value
        try:
            with winreg.OpenKey(key_hive, subkey, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, value_name)
        except:
            pass

    del state["registry"][path]
    if not state["registry"]:
        del state["registry"]
    _save_state(state)
    return True

# ──────────────────────────────────────────────────────────────────────────────
# Service backup / restore
# ──────────────────────────────────────────────────────────────────────────────
def backup_service(service_name, original_start_type=None):
    """Store original start type of a service."""
    state = _load_state()
    if "services" not in state:
        state["services"] = {}

    if service_name in state["services"]:
        return

    if original_start_type is None:
        try:
            out = subprocess.run(
                ["sc", "qc", service_name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
                startupinfo=_hidden_startupinfo(), creationflags=0x08000000,
            )
            for line in out.stdout.splitlines():
                if "START_TYPE" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        original_start_type = parts[1]
                        break
        except:
            original_start_type = "3"   # manual / unknown fallback

    state["services"][service_name] = {
        "original_start": original_start_type,
        "backup_time": datetime.now().isoformat()
    }
    _save_state(state)

def restore_service(service_name):
    """Restore service to its original start type. Returns True if restored."""
    state = _load_state()
    if not state.get("services", {}).get(service_name):
        return False

    orig = state["services"][service_name]["original_start"]
    try:
        subprocess.run(
            ["sc", "config", service_name, f"start={orig}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            startupinfo=_hidden_startupinfo(), creationflags=0x08000000,
        )
    except:
        pass
    del state["services"][service_name]
    if not state["services"]:
        del state["services"]
    _save_state(state)
    return True

# ──────────────────────────────────────────────────────────────────────────────
# Appx package removal registry (for possible revert)
# ──────────────────────────────────────────────────────────────────────────────
def backup_appx_package(package_fullname):
    """Register that an Appx package was removed."""
    state = _load_state()
    if "appx_removed" not in state:
        state["appx_removed"] = []
    if package_fullname not in state["appx_removed"]:
        state["appx_removed"].append(package_fullname)
    _save_state(state)

# ──────────────────────────────────────────────────────────────────────────────
# Global getters / utilities
# ──────────────────────────────────────────────────────────────────────────────
def get_all_backups():
    """Return full state dictionary."""
    return _load_state()

def clear_backup(category=None):
    """Clear all or specific category (registry, services, appx_removed)."""
    if category:
        state = _load_state()
        if category in state:
            del state[category]
        _save_state(state)
    else:
        if STATE_FILE.exists():
            STATE_FILE.unlink()

# ──────────────────────────────────────────────────────────────────────────────
# Custom value storage (for temporary data, e.g. created power scheme GUID)
# ──────────────────────────────────────────────────────────────────────────────
def save_custom(key: str, value):
    """Save an arbitrary custom key/value pair in state.json (not a backup)."""
    state = _load_state()
    if "custom" not in state:
        state["custom"] = {}
    state["custom"][key] = value
    _save_state(state)

def get_custom(key: str):
    """Retrieve a custom value by key."""
    state = _load_state()
    return state.get("custom", {}).get(key)

def clear_custom(key: str):
    """Remove a custom key/value pair."""
    state = _load_state()
    if "custom" in state and key in state["custom"]:
        del state["custom"][key]
        _save_state(state)