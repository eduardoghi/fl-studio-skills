"""Finds the folders that FL Studio lets its scripts use."""

import os
from pathlib import Path


def documents_dir():
    """Return the real Documents folder, which OneDrive often moves away from the home folder."""
    try:
        import winreg

        key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
            return Path(os.path.expandvars(winreg.QueryValueEx(handle, "Personal")[0]))
    except (ImportError, OSError):
        return Path.home() / "Documents"


def settings_dir():
    return documents_dir() / "Image-Line" / "FL Studio" / "Settings"


def device_dir():
    """Return the mailbox folder. A script can only open files in its own folder."""
    return Path(os.environ.get("FL_BRIDGE_DIR") or settings_dir() / "Hardware" / "ClaudeBridge")


def piano_roll_dir():
    return Path(os.environ.get("FL_BRIDGE_PIANO_ROLL_DIR") or settings_dir() / "Piano roll scripts")
