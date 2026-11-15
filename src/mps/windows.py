"""Find and answer standard Windows dialogs of a process, without moving the mouse.

A modal dialog stops REAPER's script loop, so the bridge stops answering. These helpers list the dialogs of the
REAPER process with their buttons, and press a button by its text.
"""

import ctypes
import subprocess
from ctypes import wintypes

user32 = ctypes.windll.user32
ENUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
BM_CLICK = 0x00F5


def _text(h) -> str:
    n = user32.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(h, b, n + 1)
    return b.value


def _class(h) -> str:
    b = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, b, 256)
    return b.value


def pids(image: str = "reaper.exe") -> set[int]:
    out = subprocess.run(
        ["tasklist", "/fo", "csv", "/nh", "/fi", f"IMAGENAME eq {image}"], capture_output=True, text=True, check=False
    ).stdout
    return {int(line.split(",")[1].strip('"')) for line in out.splitlines() if line.count(",") >= 2}


def dialogs(image: str = "reaper.exe", pid: int | None = None) -> list[dict]:
    """Visible #32770 dialogs of the process (or of one process id), with the text of their labels and buttons."""
    owners = {pid} if pid else pids(image)
    found = []

    @ENUM
    def top(h, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value in owners and user32.IsWindowVisible(h) and _class(h) == "#32770":
            found.append(h)
        return True

    user32.EnumWindows(top, 0)
    result = []
    for h in found:
        kids = []

        @ENUM
        def child(c, _, kids=kids):
            kids.append({"class": _class(c), "text": _text(c), "hwnd": c})
            return True

        user32.EnumChildWindows(h, child, 0)
        result.append(
            {
                "hwnd": h,
                "title": _text(h),
                "labels": [k["text"] for k in kids if k["class"] == "Static" and k["text"]],
                "buttons": [k["text"] for k in kids if k["class"] == "Button" and k["text"]],
                "texts": [k["text"] for k in kids if k["class"] == "Edit" and k["text"]],
                "_kids": kids,
            }
        )
    return result


def find(title_part: str, image: str = "reaper.exe") -> list[int]:
    """Visible top-level windows of the process whose title contains title_part."""
    owners = pids(image)
    found = []

    @ENUM
    def top(h, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value in owners and user32.IsWindowVisible(h) and title_part.lower() in _text(h).lower():
            found.append(h)
        return True

    user32.EnumWindows(top, 0)
    return found


def rect(h) -> tuple[int, int, int, int]:
    r = wintypes.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def capture(h, path) -> tuple[int, int]:
    """Save the window as a PNG through PrintWindow, so it works behind other windows. Returns its size."""
    import struct
    import zlib

    gdi = ctypes.windll.gdi32
    _, _, w, hgt = rect(h)
    hdc = user32.GetWindowDC(h)
    mem = gdi.CreateCompatibleDC(hdc)
    bmp = gdi.CreateCompatibleBitmap(hdc, w, hgt)
    gdi.SelectObject(mem, bmp)
    user32.PrintWindow(h, mem, 2)  # PW_RENDERFULLCONTENT, needed for windows drawn with DirectX or Qt

    class BITMAPINFOHEADER(ctypes.Structure):
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
        ]

    bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -hgt, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * hgt * 4)
    gdi.GetDIBits(mem, bmp, 0, hgt, buf, ctypes.byref(bi), 0)
    gdi.DeleteObject(bmp)
    gdi.DeleteDC(mem)
    user32.ReleaseDC(h, hdc)
    raw = bytearray()
    data = buf.raw
    for y in range(hgt):
        row = data[y * w * 4 : (y + 1) * w * 4]
        raw.append(0)
        rgb = bytearray(w * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = row[2::4], row[1::4], row[0::4]
        raw += rgb

    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, hgt, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return w, hgt


def _deepest(h, sx, sy):
    pt = wintypes.POINT(sx, sy)
    while True:
        local = wintypes.POINT(pt.x, pt.y)
        user32.ScreenToClient(h, ctypes.byref(local))
        child = user32.ChildWindowFromPointEx(h, local, 1 | 4)  # skip invisible and transparent children
        if not child or child == h:
            return h, local.x, local.y
        h = child


def click(h, x, y, button="left"):
    """Post a click at (x, y) of the window (its own coordinates, as in a capture), to the innermost child there."""
    import time

    left, top, _, _ = rect(h)
    target, cx, cy = _deepest(h, left + x, top + y)
    lp = (cy << 16) | (cx & 0xFFFF)
    down, up, held = (0x0201, 0x0202, 1) if button == "left" else (0x0204, 0x0205, 2)
    user32.PostMessageW(target, 0x0200, 0, lp)
    time.sleep(0.05)
    user32.PostMessageW(target, down, held, lp)
    time.sleep(0.05)
    user32.PostMessageW(target, up, 0, lp)
    return _class(target)


def bring_to_front(h):
    """Make the window the foreground one, which Windows only allows after this process sends input."""
    import time

    kernel32 = ctypes.windll.kernel32
    front = user32.GetForegroundWindow()
    theirs = user32.GetWindowThreadProcessId(front, None)
    ours = kernel32.GetCurrentThreadId()
    attached = theirs and theirs != ours and user32.AttachThreadInput(ours, theirs, True)
    try:
        user32.keybd_event(0x12, 0, 0, 0)  # an Alt press lets this process change the foreground window
        user32.keybd_event(0x12, 0, 2, 0)
        user32.SetForegroundWindow(h)
    finally:
        if attached:
            user32.AttachThreadInput(ours, theirs, False)
    time.sleep(0.3)


def real_drag(h, x0, y0, x1, y1, steps=20):
    """Press the real mouse at (x0, y0) of the window, move to (x1, y1), release, then put the pointer back."""
    import time

    bring_to_front(h)
    saved = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(saved))
    left, top, _, _ = rect(h)
    user32.SetCursorPos(left + x0, top + y0)
    time.sleep(0.15)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    for k in range(1, steps + 1):
        user32.SetCursorPos(left + x0 + (x1 - x0) * k // steps, top + y0 + (y1 - y0) * k // steps)
        time.sleep(0.02)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.2)
    user32.SetCursorPos(saved.x, saved.y)


def real_click(h, x, y, double=False):
    """Click with the real mouse at (x, y) of the window, then put the pointer back.

    Brings the window to the front and moves the person's pointer, so use it only when no API, MIDI, preset or saved
    state can do the job. Qt windows such as Kontakt's ignored posted clicks on their menus inside REAPER.
    """
    import time

    bring_to_front(h)
    saved = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(saved))
    left, top, _, _ = rect(h)
    user32.SetCursorPos(left + x, top + y)
    time.sleep(0.15)
    for _ in range(2 if double else 1):
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
        time.sleep(0.08)
    time.sleep(0.2)
    user32.SetCursorPos(saved.x, saved.y)


def real_wheel(h, x, y, notches):
    """Turn the real mouse wheel over (x, y) of the window (negative scrolls down), then put the pointer back."""
    import time

    bring_to_front(h)
    saved = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(saved))
    left, top, _, _ = rect(h)
    user32.SetCursorPos(left + x, top + y)
    time.sleep(0.15)
    step = 1 if notches > 0 else -1
    for _ in range(abs(notches)):
        user32.mouse_event(0x0800, 0, 0, ctypes.c_ulong(120 * step & 0xFFFFFFFF).value, 0)
        time.sleep(0.06)
    time.sleep(0.2)
    user32.SetCursorPos(saved.x, saved.y)


def fill_file_dialog(dialog: dict, path: str) -> bool:
    """Type a path in a standard open or save dialog and confirm it."""
    edit = None
    for k in dialog["_kids"]:
        if k["class"] == "Edit" and user32.GetDlgCtrlID(user32.GetParent(k["hwnd"])) == 1148:
            edit = k["hwnd"]
    if edit is None:
        edit = next(
            (k["hwnd"] for k in dialog["_kids"] if k["class"] == "Edit" and user32.GetDlgCtrlID(k["hwnd"]) == 1001),
            None,
        )
    if edit is None:
        return False
    user32.SendMessageW(edit, 0x000C, 0, ctypes.create_unicode_buffer(path))  # WM_SETTEXT
    ok = next(
        (k["hwnd"] for k in dialog["_kids"] if k["class"] == "Button" and user32.GetDlgCtrlID(k["hwnd"]) == 1), None
    )
    if ok is None:
        return False
    user32.SendMessageW(ok, BM_CLICK, 0, 0)
    return True


def press(dialog: dict, button_text: str) -> bool:
    for k in dialog["_kids"]:
        if k["class"] == "Button" and k["text"].replace("&", "").lower() == button_text.replace("&", "").lower():
            user32.SendMessageW(k["hwnd"], BM_CLICK, 0, 0)
            return True
    return False
