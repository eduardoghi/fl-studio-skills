"""Presses Ctrl+Alt+Y, FL Studio's shortcut for running the last piano roll script.

FL has no API to start a piano roll script. Keystrokes go to the active window,
so nothing is sent unless that window belongs to FL.
"""

import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import PureWindowsPath

VK_CONTROL = 0x11
VK_MENU = 0x12
VK_Y = 0x59
KEYEVENTF_KEYUP = 2
QUERY_LIMITED = 0x1000
FL_PROCESSES = ("fl64.exe", "fl.exe")


class HotkeyError(Exception):
    pass


def is_fl(image_path):
    return PureWindowsPath(image_path).name.lower() in FL_PROCESSES


def key_sequence():
    """Return (virtual key, released) pairs, pressing the modifiers first."""
    keys = (VK_CONTROL, VK_MENU, VK_Y)
    return [(key, False) for key in keys] + [(key, True) for key in reversed(keys)]


def _process_image(user32, kernel32, window):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(window, ctypes.byref(pid))
    process = kernel32.OpenProcess(QUERY_LIMITED, False, pid.value)
    if not process:
        return ""
    try:
        size = wintypes.DWORD(1024)
        name = ctypes.create_unicode_buffer(size.value)
        ok = kernel32.QueryFullProcessImageNameW(process, 0, name, ctypes.byref(size))
        return name.value if ok else ""
    finally:
        kernel32.CloseHandle(process)


def _main_window(user32, kernel32):
    found = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit(window, _):
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(window, title, 256)
        if (
            user32.IsWindowVisible(window)
            and "FL Studio" in title.value
            and is_fl(_process_image(user32, kernel32, window))
        ):
            found.append(window)
            return False
        return True

    user32.EnumWindows(callback_type(visit), 0)
    return found[0] if found else None


def run_last_script():
    if sys.platform != "win32":
        raise HotkeyError("the hotkey only supports Windows")
    user32 = ctypes.WinDLL("user32")
    kernel32 = ctypes.WinDLL("kernel32")
    user32.GetForegroundWindow.restype = wintypes.HWND
    window = _main_window(user32, kernel32)
    if window is None:
        raise HotkeyError("FL Studio's window wasn't found")
    user32.SetForegroundWindow(window)
    time.sleep(0.25)
    if not is_fl(_process_image(user32, kernel32, user32.GetForegroundWindow())):
        raise HotkeyError("FL Studio isn't the active window, so no key was sent")
    for key, released in key_sequence():
        user32.keybd_event(key, 0, KEYEVENTF_KEYUP if released else 0, 0)
