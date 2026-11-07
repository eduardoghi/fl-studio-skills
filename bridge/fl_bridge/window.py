"""Drives FL Studio's interface with window messages, so it works behind other windows.

Nothing here moves the mouse or takes the keyboard focus. Clicks and keys are posted to FL's own windows, and the
modifiers of a shortcut are set in FL's input state alone, so the real keyboard stays free. FL still opens menus and
dialogs above other programs and raises its main window while it works, so actions run inside a shield that makes
those windows invisible and lets clicks pass through them. See `_shielded`.

Everything was observed on FL Studio 26.1.4. Dragging doesn't work this way, because FL starts the drag and never
drops.
"""

import contextlib
import ctypes
import os
import struct
import sys
import tempfile
import threading
import time
import uuid
import zlib
from ctypes import wintypes
from pathlib import Path, PureWindowsPath

WM_SETTEXT = 0x000C
WM_CLOSE = 0x0010
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MOUSEWHEEL = 0x020A
BM_CLICK = 0x00F5
MK_LBUTTON = 1
MK_RBUTTON = 2
WHEEL_DELTA = 120

VK_RETURN = 0x0D
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_ESCAPE = 0x1B
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_LCONTROL = 0xA2
VK_LMENU = 0xA4
MENU_KEYS = {
    "down": VK_DOWN,
    "up": VK_UP,
    "left": VK_LEFT,
    "right": VK_RIGHT,
    "enter": VK_RETURN,
    "escape": VK_ESCAPE,
}

CLASS_MAIN = "TFruityLoopsMainForm"
CLASS_APPLICATION = "TApplication"  # A hidden 0x0 window that owns FL's forms.
CLASS_MAIN_PANELS = ("TEventEditForm", "TStepSeqForm", "TFXForm")
CLASS_FL_MENU = "TQuickPopupMenuWindow"
CLASS_NATIVE_MENU = "#32768"
CLASS_DIALOG = "#32770"
CLASS_RENDER = "TWAVRenderForm"
CLASS_FLIP_TOOL = "TPRFlipForm"
PLUGIN_MENU_SIZE = (247, 271)  # The browser's menu for a plugin. Folders and other rows open different ones.
FILE_MENU = (38, 25)  # FILE in the menu bar of the main window.
FILE_MENU_EXPORT_DOWNS = 11  # Down presses from the top of FILE to Export, with the disabled row skipped.
EXPORT_MENU_SIZE = (179, 358)  # The Export submenu. Import, one row above, opens a submenu of another size.
RENDER_FORM_SIZE = (433, 611)
RENDER_START = (385, 587)  # Measured on the form above.
RENDER_CLOSE = (419, 14)
FILE_NAME_FIELD = 1001
DIALOG_OK = 1
DIALOG_CANCEL = 2
PW_RENDERFULLCONTENT = 2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020  # Leaves the window out of hit testing, so clicks reach whatever is below.
WS_EX_LAYERED = 0x00080000
GHOST_STYLE = WS_EX_LAYERED | WS_EX_TRANSPARENT
LWA_ALPHA = 2
EVENT_OBJECT_CREATE = 0x8000
EVENT_OBJECT_SHOW = 0x8002
WINEVENT_OUTOFCONTEXT = 0
OBJID_WINDOW = 0
GA_ROOT = 2
PM_REMOVE = 1
RDW_REPAINT = 0x0001 | 0x0004 | 0x0080 | 0x0400  # Invalidate, erase, all children, frame.
FL_PROCESSES = ("fl64.exe", "fl.exe")
KEY_GAP_S = 0.05
SHIELD_JOIN_S = 15.0  # The hook thread only stops between messages, and FL can hold one for seconds.
POLL_S = 0.1


class WindowError(Exception):
    pass


def is_fl(image_path):
    return PureWindowsPath(image_path).name.lower() in FL_PROCESSES


def click_param(x, y):
    """Pack client coordinates for a mouse message. Negative values keep their 16 bit form."""
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


def key_param(scan_code, alt, released):
    """Build the lParam of a key message, with the bits Windows would set for a real key."""
    value = 1 | (scan_code << 16)
    if alt:
        value |= 0x20000000
    if released:
        value |= 0xC0000000
    return value


def wheel_param(notches):
    """Build the wParam of a wheel message. The high word is a signed distance, negative scrolls down."""
    return ((notches * WHEEL_DELTA) & 0xFFFF) << 16


def key_message(alt, released):
    if alt:
        return WM_SYSKEYUP if released else WM_SYSKEYDOWN
    return WM_KEYUP if released else WM_KEYDOWN


def menu_key(name):
    if name not in MENU_KEYS:
        raise WindowError(f"unknown menu key {name!r}, use one of {', '.join(MENU_KEYS)}")
    return MENU_KEYS[name]


def ghosted(style):
    """Return an extended style that, with alpha 0, makes a window invisible and lets clicks pass through it."""
    return style | GHOST_STYLE


def is_ghost(style):
    return style & GHOST_STYLE == GHOST_STYLE


def unghosted(style):
    """Drop the ghost bits from a style whose original is unknown. FL's own windows had neither bit."""
    return style & ~GHOST_STYLE


def centered(outer, inner):
    """Return the top left that centers an inner (width, height) on an outer (left, top, width, height)."""
    left, top, width, height = outer
    return left + (width - inner[0]) // 2, top + (height - inner[1]) // 2


def scaled(point, size, reference=RENDER_FORM_SIZE):
    """Move a point measured from the bottom right of a form, since FL can draw the form at another scale."""
    return size[0] - (reference[0] - point[0]), size[1] - (reference[1] - point[1])


def crop(pixels, width, height, region):
    """Cut a (x, y, width, height) region out of top-down BGRA rows, limited to the image."""
    x, y, w, h = region
    x, y = max(x, 0), max(y, 0)
    w, h = min(w, width - x), min(h, height - y)
    if w <= 0 or h <= 0:
        raise WindowError(f"the region {region} is outside the {width}x{height} image")
    rows = [pixels[(y + row) * width * 4 + x * 4 : (y + row) * width * 4 + (x + w) * 4] for row in range(h)]
    return b"".join(rows), w, h


def encode_png(pixels, width, height):
    """Encode top-down BGRA rows as an RGB PNG, which keeps image libraries out of the dependencies."""
    rgb = bytearray(width * height * 3)
    rgb[0::3] = pixels[2::4]
    rgb[1::3] = pixels[1::4]
    rgb[2::3] = pixels[0::4]
    stride = width * 3
    raw = b"".join(b"\0" + bytes(rgb[row * stride : (row + 1) * stride]) for row in range(height))

    def chunk(name, body):
        return struct.pack(">I", len(body)) + name + body + struct.pack(">I", zlib.crc32(name + body))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")


class _BitmapInfo(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
        ("bmiColors", wintypes.DWORD * 3),
    ]


_api_cache = None
_WINEVENTPROC = (
    ctypes.WINFUNCTYPE(
        None,
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.HWND,
        wintypes.LONG,
        wintypes.LONG,
        wintypes.DWORD,
        wintypes.DWORD,
    )
    if sys.platform == "win32"
    else None
)


def _api():
    """Load the Windows libraries once, with the types that keep 64 bit handles intact."""
    global _api_cache
    if _api_cache is not None:
        return _api_cache
    if sys.platform != "win32":
        raise WindowError("driving FL's windows only supports Windows")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32")
    kernel32 = ctypes.WinDLL("kernel32")
    user32.SetProcessDPIAware()  # Otherwise coordinates and captures are scaled on a high DPI screen.
    hwnd = wintypes.HWND
    user32.GetForegroundWindow.restype = hwnd
    user32.GetDC.restype = wintypes.HDC
    user32.GetDC.argtypes = [hwnd]
    user32.ReleaseDC.argtypes = [hwnd, wintypes.HDC]
    user32.PostMessageW.argtypes = [hwnd, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.argtypes = [hwnd, wintypes.UINT, wintypes.WPARAM, wintypes.LPCWSTR]
    user32.SendMessageW.restype = ctypes.c_ssize_t
    user32.RealChildWindowFromPoint.argtypes = [hwnd, wintypes.POINT]
    user32.RealChildWindowFromPoint.restype = hwnd
    user32.PrintWindow.argtypes = [hwnd, wintypes.HDC, wintypes.UINT]
    user32.SetWindowPos.argtypes = [
        hwnd,
        hwnd,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.GetWindowThreadProcessId.argtypes = [hwnd, ctypes.POINTER(wintypes.DWORD)]
    user32.GetClassNameW.argtypes = [hwnd, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.argtypes = [hwnd, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowRect.argtypes = [hwnd, ctypes.POINTER(wintypes.RECT)]
    user32.ScreenToClient.argtypes = [hwnd, ctypes.POINTER(wintypes.POINT)]
    user32.IsWindowVisible.argtypes = [hwnd]
    user32.IsIconic.argtypes = [hwnd]
    user32.GetDlgCtrlID.argtypes = [hwnd]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.GetDIBits.argtypes = [
        wintypes.HDC,
        wintypes.HBITMAP,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.c_void_p,
        ctypes.POINTER(_BitmapInfo),
        wintypes.UINT,
    ]
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.GetWindowLongPtrW.argtypes = [hwnd, ctypes.c_int]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = [hwnd, ctypes.c_int, ctypes.c_ssize_t]
    user32.SetLayeredWindowAttributes.argtypes = [hwnd, wintypes.DWORD, wintypes.BYTE, wintypes.DWORD]
    user32.GetAncestor.restype = hwnd
    user32.GetAncestor.argtypes = [hwnd, wintypes.UINT]
    user32.IsWindow.argtypes = [hwnd]
    user32.RedrawWindow.argtypes = [hwnd, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
    user32.SetWinEventHook.restype = wintypes.HANDLE
    user32.SetWinEventHook.argtypes = [
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HMODULE,
        _WINEVENTPROC,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
    user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), hwnd, wintypes.UINT, wintypes.UINT, wintypes.UINT]
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    _api_cache = (user32, gdi32, kernel32)
    return _api_cache


def _text(window):
    user32, _, _ = _api()
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(window, buffer, 256)
    return buffer.value


def _class(window):
    user32, _, _ = _api()
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(window, buffer, 256)
    return buffer.value


def _rect(window):
    user32, _, _ = _api()
    rect = wintypes.RECT()
    user32.GetWindowRect(window, ctypes.byref(rect))
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def _process_id(window):
    user32, _, _ = _api()
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(window, ctypes.byref(pid))
    return pid.value


def _process_image(pid):
    _, _, kernel32 = _api()
    process = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not process:
        return ""
    try:
        size = wintypes.DWORD(1024)
        name = ctypes.create_unicode_buffer(size.value)
        ok = kernel32.QueryFullProcessImageNameW(process, 0, name, ctypes.byref(size))
        return name.value if ok else ""
    finally:
        kernel32.CloseHandle(process)


def _top_windows():
    """Return top-level visible windows from the front to the back."""
    user32, _, _ = _api()
    found = []
    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit(window, _):
        if user32.IsWindowVisible(window):
            found.append(window)
        return True

    user32.EnumWindows(callback(visit), 0)
    return found


def _children(parent):
    user32, _, _ = _api()
    found = []
    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit(window, _):
        found.append(window)
        return True

    user32.EnumChildWindows(parent, callback(visit), 0)
    return found


def main_window():
    """Return FL's main window. The title is `FL Studio 2026` alone when no project is open."""
    for window in _top_windows():
        if "FL Studio" in _text(window) and is_fl(_process_image(_process_id(window))):
            return window
    raise WindowError("FL Studio's window wasn't found")


def _fl_windows(main, classes):
    """Return FL's top-level windows of the given classes, from the front to the back."""
    pid = _process_id(main)
    return [w for w in _top_windows() if _process_id(w) == pid and _class(w) in classes]


def open_menus(main=None):
    return _fl_windows(main or main_window(), (CLASS_FL_MENU, CLASS_NATIVE_MENU))


def _require_visible(main):
    user32, _, _ = _api()
    if user32.IsIconic(main):
        raise WindowError(
            "FL is minimized, so its panels can't be captured or clicked. Restore it behind other windows"
        )


def _process_windows(pid):
    """Return every top-level window of a process, hidden ones included."""
    user32, _, _ = _api()
    found = []
    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit(window, _):
        if _process_id(window) == pid:
            found.append(window)
        return True

    user32.EnumWindows(callback(visit), 0)
    return found


def _repaint(window):
    user32, _, _ = _api()
    user32.RedrawWindow(window, None, None, RDW_REPAINT)


class _Shield:
    """Hide FL's main window and every window FL opens while an action runs.

    FL opens menus and dialogs above other programs, and raises its main window while exporting even without taking
    the focus. Pushing it back down the window order lost to the save dialog, which raised it 33 times in 80 ms, so
    the windows are made invisible instead, with alpha 0 and click-through, which works from another process. Posted
    keys and clicks still reach them, and PrintWindow still captures them.

    New windows are caught by a WinEvent hook. The events arrive after the window is already visible, 0 to 16 ms
    later for menus and up to about 150 ms for the save dialog, and no flash was seen in testing.
    """

    def __init__(self, main):
        self.main = main
        self.pid = _process_id(main)
        self.styles = {}
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.thread = None

    def _ghost(self, window):
        user32, _, _ = _api()
        if window in self.styles:
            return
        style = user32.GetWindowLongPtrW(window, GWL_EXSTYLE)
        self.styles[window] = style
        user32.SetWindowLongPtrW(window, GWL_EXSTYLE, ghosted(style))
        user32.SetLayeredWindowAttributes(window, 0, 0, LWA_ALPHA)

    def _on_event(self, hook, event, window, id_object, id_child, thread, when):
        user32, _, _ = _api()
        if id_object != OBJID_WINDOW or not window or user32.GetAncestor(window, GA_ROOT) != window:
            return
        if _class(window) not in (CLASS_MAIN, CLASS_APPLICATION):
            self._ghost(window)

    def _listen(self):
        user32, _, _ = _api()
        callback = _WINEVENTPROC(self._on_event)
        hooks = [
            user32.SetWinEventHook(event, event, None, callback, self.pid, 0, WINEVENT_OUTOFCONTEXT)
            for event in (EVENT_OBJECT_CREATE, EVENT_OBJECT_SHOW)
        ]
        self.ready.set()
        message = wintypes.MSG()
        try:
            # Out of context events are delivered through this thread's message queue.
            while not self.stop.is_set():
                while user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
                    user32.TranslateMessage(ctypes.byref(message))
                    user32.DispatchMessageW(ctypes.byref(message))
                time.sleep(0.002)
        finally:
            for hook in hooks:
                user32.UnhookWinEvent(hook)

    def __enter__(self):
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()
        self.ready.wait(2)
        self._ghost(self.main)
        return self

    def __exit__(self, *_):
        user32, _, _ = _api()
        self.stop.set()
        # While FL is busy, loading a plugin for example, the hook can still be adding windows to self.styles, and
        # iterating it then raised "dictionary changed size during iteration".
        self.thread.join(SHIELD_JOIN_S)
        # FL rises while hidden and would show up above the window in use, as it did over a game. Its dialogs are
        # closed by now, so putting it back below that window holds.
        front = user32.GetForegroundWindow()
        order = _top_windows()
        visible = front in order and self.main in order
        if front and _process_id(front) != self.pid and visible and order.index(self.main) < order.index(front):
            user32.SetWindowPos(self.main, front, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
        # A menu left open waits for the next fl_menu_keys, so it stays invisible. It closes when chosen or escaped,
        # and FL makes a new window for the next one. Dialogs come back, so a stuck one can be seen.
        menus = set(open_menus(self.main))
        for window, style in list(self.styles.items()):
            if window not in menus and user32.IsWindow(window):
                user32.SetWindowLongPtrW(window, GWL_EXSTYLE, style)
                _repaint(window)
        # A window ghosted after the copy above, or by a hook that outlived the join, would stay invisible.
        for window in _process_windows(self.pid):
            style = user32.GetWindowLongPtrW(window, GWL_EXSTYLE)
            if window not in menus and window not in self.styles and is_ghost(style):
                user32.SetWindowLongPtrW(window, GWL_EXSTYLE, unghosted(style))
                _repaint(window)


_shield_depth = 0


@contextlib.contextmanager
def _shielded():
    """Run an action inside a `_Shield`, unless one is already active or FL has the focus.

    With FL in the foreground the person is using it, so nothing is hidden.
    """
    global _shield_depth
    user32, _, _ = _api()
    main = main_window()
    front = user32.GetForegroundWindow()
    if _shield_depth or (front and _process_id(front) == _process_id(main)):
        _shield_depth += 1
        try:
            yield
        finally:
            _shield_depth -= 1
        return
    _shield_depth += 1
    try:
        with _Shield(main):
            yield
    finally:
        _shield_depth -= 1


def reveal():
    """Close FL's menus and make its windows visible and clickable again, for when a shielded action stopped halfway.

    A process that died inside the shield leaves FL invisible, and its original styles died with it. FL's own windows
    had neither ghost bit, so both are dropped.
    """
    user32, _, _ = _api()
    main = main_window()
    closed = 0
    while open_menus(main) and closed < 5:
        _press(open_menus(main)[0], VK_ESCAPE)
        time.sleep(0.25)
        closed += 1
    shown = []
    for window in _process_windows(_process_id(main)):
        style = user32.GetWindowLongPtrW(window, GWL_EXSTYLE)
        if is_ghost(style):
            user32.SetWindowLongPtrW(window, GWL_EXSTYLE, unghosted(style))
            _repaint(window)
            shown.append(_class(window))
    return {"menus_closed": closed, "windows_shown": shown}


def _deepest(root, screen_x, screen_y):
    """Find the innermost window at a screen point, since FL's panels ignore clicks sent to their parents."""
    user32, _, _ = _api()
    target = root
    while True:
        point = wintypes.POINT(screen_x, screen_y)
        user32.ScreenToClient(target, ctypes.byref(point))
        child = user32.RealChildWindowFromPoint(target, point)
        if not child or child == target:
            return target, point.x, point.y
        target = child


def _post(window, message, wparam=0, lparam=0):
    user32, _, _ = _api()
    if not user32.PostMessageW(window, message, wparam, lparam):
        raise WindowError(f"could not post to window {window}, error {ctypes.get_last_error()}")


def _post_click(root, screen_x, screen_y, button="left"):
    if button not in ("left", "right"):
        raise WindowError("button must be left or right")
    target, x, y = _deepest(root, screen_x, screen_y)
    down, up, held = (
        (WM_LBUTTONDOWN, WM_LBUTTONUP, MK_LBUTTON) if button == "left" else (WM_RBUTTONDOWN, WM_RBUTTONUP, MK_RBUTTON)
    )
    param = click_param(x, y)
    _post(target, WM_MOUSEMOVE, 0, param)
    time.sleep(KEY_GAP_S)
    _post(target, down, held, param)
    time.sleep(KEY_GAP_S)
    _post(target, up, 0, param)
    return target


@_shielded()
def click(x, y, button="left"):
    """Click at a point relative to the main window, the same coordinates as a capture."""
    main = main_window()
    _require_visible(main)
    left, top, width, height = _rect(main)
    if not (0 <= x < width and 0 <= y < height):
        raise WindowError(f"({x}, {y}) is outside FL's {width}x{height} window")
    target = _post_click(main, left + x, top + y, button)
    time.sleep(0.3)
    return {"window": _class(target), "menus": len(open_menus(main))}


def scroll(x, y, notches):
    """Turn the wheel over a point. Negative notches scroll down. The message carries screen coordinates."""
    main = main_window()
    _require_visible(main)
    left, top, _, _ = _rect(main)
    target, _, _ = _deepest(main, left + x, top + y)
    step = -1 if notches < 0 else 1
    for _ in range(abs(notches)):
        _post(target, WM_MOUSEWHEEL, wheel_param(step), click_param(left + x, top + y))
        time.sleep(KEY_GAP_S)
    return {"window": _class(target)}


def _press(window, key, alt=False):
    user32, _, _ = _api()
    scan = user32.MapVirtualKeyW(key, 0)
    _post(window, key_message(alt, False), key, key_param(scan, alt, False))
    time.sleep(KEY_GAP_S)
    # Unchecked, because escape and enter can close a menu before its key is released.
    user32.PostMessageW(window, key_message(alt, True), key, key_param(scan, alt, True))


@_shielded()
def menu_keys(keys):
    """Send keys to the open menu. Clicking a menu item closes the menu without choosing it, keys do choose it."""
    codes = [menu_key(name) for name in keys]
    main = main_window()
    for name, code in zip(keys, codes):
        menus = open_menus(main)
        if not menus:
            raise WindowError(f"no menu is open for {name!r}")
        _press(menus[0], code)
        time.sleep(0.25 if name in ("right", "left", "enter", "escape") else KEY_GAP_S)
    return {"menus": len(open_menus(main))}


@contextlib.contextmanager
def _modifiers_held(main, ctrl, alt):
    """Hold modifiers in FL's input state only.

    FL reads Ctrl and Alt from the state of its own thread, so posting them as keys does nothing. Attaching to that
    thread makes SetKeyboardState reach it, and the keyboard the user is typing on isn't touched.
    """
    user32, _, kernel32 = _api()
    theirs = user32.GetWindowThreadProcessId(main, None)
    ours = kernel32.GetCurrentThreadId()
    if not user32.AttachThreadInput(ours, theirs, True):
        raise WindowError(f"could not attach to FL's input, error {ctypes.get_last_error()}")
    saved = (ctypes.c_ubyte * 256)()
    try:
        user32.GetKeyboardState(saved)
        state = (ctypes.c_ubyte * 256)(*saved)
        if ctrl:
            state[VK_CONTROL] = state[VK_LCONTROL] = 0x80
        if alt:
            state[VK_MENU] = state[VK_LMENU] = 0x80
        user32.SetKeyboardState(state)
        yield
    finally:
        user32.SetKeyboardState(saved)
        user32.AttachThreadInput(ours, theirs, False)


def _panels(main):
    """Return the visible panels, piano roll first. Shortcuts only worked when sent to a panel."""
    user32, _, _ = _api()
    panels = [w for w in _children(main) if _class(w) in CLASS_MAIN_PANELS and user32.IsWindowVisible(w)]
    return sorted(panels, key=lambda w: not _text(w).startswith("Piano roll"))


def _shortcut(window, main, key, ctrl=False, alt=False):
    with _modifiers_held(main, ctrl, alt):
        _press(window, key, alt=alt)
        time.sleep(0.4)  # FL reads the modifiers when it handles the message, so they stay held until then.


@_shielded()
def run_last_script():
    """Press Ctrl+Alt+Y on the piano roll, which repeats the last piano roll script."""
    main = main_window()
    panels = [w for w in _panels(main) if _text(w).startswith("Piano roll")]
    if not panels:
        raise WindowError("the piano roll isn't open")
    _shortcut(panels[0], main, ord("Y"), ctrl=True, alt=True)
    # Without Ctrl the key reads as Alt+Y, which opens the flip tool instead of running the script.
    flip_tools = _fl_windows(main, (CLASS_FLIP_TOOL,))
    for tool in flip_tools:
        _post(tool, WM_CLOSE)
    if flip_tools:
        raise WindowError("FL read the shortcut as Alt+Y and opened the flip tool, which was closed. Try again")


def capture(folder=None, region=None):
    """Save PNGs of the main window and any open menu, and return where each one is.

    region is (x, y, width, height) in the main window. It works behind other windows, not while minimized.
    """
    main = main_window()
    _require_visible(main)
    folder = Path(folder) if folder else Path(tempfile.gettempdir()) / "fl-bridge"
    folder.mkdir(parents=True, exist_ok=True)
    shots = []
    for position, window in enumerate([main, *open_menus(main)]):
        name = "main" if window == main else f"menu-{position}"
        left, top, width, height = _rect(window)
        pixels = _grab(window, width, height)
        if window == main and region:
            pixels, width, height = crop(pixels, width, height, region)
        path = folder / f"{name}.png"
        path.write_bytes(encode_png(pixels, width, height))
        shots.append({"window": name, "path": str(path), "x": left, "y": top, "width": width, "height": height})
    return shots


def _grab(window, width, height):
    user32, gdi32, _ = _api()
    screen = user32.GetDC(None)
    memory = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, width, height)
    previous = gdi32.SelectObject(memory, bitmap)
    try:
        if not user32.PrintWindow(window, memory, PW_RENDERFULLCONTENT):
            raise WindowError("PrintWindow refused to draw FL's window")
        info = _BitmapInfo()
        info.biSize = 40
        info.biWidth = width
        info.biHeight = -height  # Negative means rows come top-down.
        info.biPlanes = 1
        info.biBitCount = 32
        buffer = ctypes.create_string_buffer(width * height * 4)
        if not gdi32.GetDIBits(memory, bitmap, 0, height, buffer, ctypes.byref(info), 0):
            raise WindowError("could not read the capture")
        return buffer.raw
    finally:
        gdi32.SelectObject(memory, previous)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory)
        user32.ReleaseDC(None, screen)


def _wait(condition, timeout, message):
    deadline = time.monotonic() + timeout
    while True:
        value = condition()
        if value:
            return value
        if time.monotonic() >= deadline:
            raise WindowError(message)
        time.sleep(POLL_S)


@_shielded()
def load_plugin(x, y, channel_count, timeout=30):
    """Open the plugin at a browser row in a new channel, through the row's menu.

    A plugin's menu has a known size, so another kind of row is refused before anything is chosen. Dropping a plugin
    from the browser doesn't work by messages.
    """
    main = main_window()
    _require_visible(main)
    # The menu of the previous load can still be closing, so only a menu that stays open is refused.
    _wait(lambda: not open_menus(main), 3, "a menu is already open. Close it with fl_menu_keys(['escape'])")
    before = channel_count()
    left, top, _, _ = _rect(main)
    _post_click(main, left + x, top + y, "right")
    menus = _wait(lambda: open_menus(main), 3, "no menu opened at that point")
    size = _rect(menus[0])[2:]
    if size != PLUGIN_MENU_SIZE:
        menu_keys(["escape"])
        raise WindowError(f"the menu at that point is {size}, not a plugin's {PLUGIN_MENU_SIZE}. Check the row")
    menu_keys(["down", "down", "enter"])  # The second item is Open in new channel.
    _wait(lambda: channel_count() > before, timeout, "FL didn't create the channel")
    return before


def _dialog(main):
    found = _fl_windows(main, (CLASS_DIALOG,))
    return found[0] if found else None


def _render_form(main):
    found = _fl_windows(main, (CLASS_RENDER,))
    return found[0] if found else None


def _dialog_child(dialog, class_name, control):
    user32, _, _ = _api()
    for child in _children(dialog):
        if _class(child) == class_name and user32.GetDlgCtrlID(child) == control:
            return child
    raise WindowError(f"the dialog has no {class_name} {control}")


def _cancel_dialog(dialog):
    _post(_dialog_child(dialog, "Button", DIALOG_CANCEL), BM_CLICK)


def _close_render_form(form):
    _post_click(form, *_form_point(form, RENDER_CLOSE))


def _center_on_main(window, main):
    """Move a dialog over FL, since FL opens the render dialog at the center of the monitor."""
    user32, _, _ = _api()
    _, _, width, height = _rect(window)
    x, y = centered(_rect(main), (width, height))
    user32.SetWindowPos(window, None, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)


def _form_point(form, point):
    left, top, width, height = _rect(form)
    x, y = scaled(point, (width, height))
    return left + x, top + y


def _export_menu_open(main):
    menus = open_menus(main)
    return len(menus) == 2 and _rect(menus[0])[2:] == EXPORT_MENU_SIZE


def _open_export_dialog(main):
    """Choose FILE > Export > Wave file with keys.

    Ctrl+R opened the same dialog, but holding Ctrl means attaching to FL's input, and FL then came in front of the
    window with the focus. A row above Export can become enabled, so a wrong submenu gets one more try a row lower.
    """
    left, top, _, _ = _rect(main)
    _post_click(main, left + FILE_MENU[0], top + FILE_MENU[1])
    _wait(lambda: open_menus(main), 3, "the FILE menu didn't open")
    time.sleep(0.3)
    menu_keys(["down"] * FILE_MENU_EXPORT_DOWNS + ["right"])
    time.sleep(0.3)
    if not _export_menu_open(main):
        menu_keys(["left", "down", "right"])
        time.sleep(0.3)
    if not _export_menu_open(main):
        while open_menus(main):
            menu_keys(["escape"])
            time.sleep(0.25)
        raise WindowError("FILE > Export wasn't where it was measured. Check the FILE menu with fl_capture")
    menu_keys(["enter"])  # Wave file is the first row and the submenu opens with it highlighted.
    return _wait(lambda: _dialog(main), 5, "Wave file didn't open the save dialog")


def _settled_size(path, seconds=1.0):
    """Return the file's size once it stops growing, or 0 while FL may still be writing."""
    if not path.is_file():
        return 0
    size = path.stat().st_size
    time.sleep(seconds)
    return size if size > 0 and path.is_file() and path.stat().st_size == size else 0


@_shielded()
def export_wav(output, overwrite=False, timeout=300):
    """Export the open project to a WAV with FL open, and return the file's size.

    Goes through a temporary name in the same folder, so the save dialog never asks about replacing a file. Uses
    Start, because Render minimized restores FL at the end and that took the focus. The dialog keeps the mode FL
    chose, so song mode exports the arrangement and pattern mode exports the pattern.
    """
    output = Path(output)
    if not output.is_absolute():
        raise WindowError("output must be an absolute path")
    if output.exists() and not overwrite:
        raise WindowError(f"{output} already exists")
    main = main_window()
    # A menu chosen a moment ago can still be closing, so this only refuses one that stays open.
    _wait(
        lambda: not (open_menus(main) or _dialog(main) or _render_form(main)),
        3,
        "a menu or dialog is already open in FL. Close it first",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".fl-bridge-export-{uuid.uuid4().hex[:8]}.wav")
    user32, _, _ = _api()
    dialog = _open_export_dialog(main)
    try:
        field = _dialog_child(dialog, "Edit", FILE_NAME_FIELD)
        user32.SendMessageW(field, WM_SETTEXT, 0, str(temporary))
        time.sleep(0.2)
        _post(_dialog_child(dialog, "Button", DIALOG_OK), BM_CLICK)
        form = _wait(lambda: _render_form(main), 5, "the render dialog didn't open")
        _center_on_main(form, main)
    except WindowError:
        still_open = _dialog(main)
        if still_open:
            _cancel_dialog(still_open)
        raise
    time.sleep(0.5)
    if temporary.stem not in _text(form):
        _close_render_form(form)
        raise WindowError(f"FL didn't take the file name. The dialog reads {_text(form)!r}")
    _post_click(form, *_form_point(form, RENDER_START))
    try:
        _wait(lambda: not _render_form(main) and _settled_size(temporary), timeout, f"FL didn't finish in {timeout} s")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output.stat().st_size
