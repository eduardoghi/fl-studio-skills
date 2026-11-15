"""Facts an experiment record needs to be reproduced or audited later."""

import ctypes
import hashlib
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_version(path: str | Path) -> str | None:
    """The version resource of a Windows binary (a plugin's .vst3 or .dll), or None if it has none."""
    ver = ctypes.windll.version
    size = ver.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return None
    buf = ctypes.create_string_buffer(size)
    if not ver.GetFileVersionInfoW(str(path), 0, size, buf):
        return None
    ptr, length = ctypes.c_void_p(), ctypes.c_uint()
    if not ver.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(length)):
        return None
    fixed = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_uint32 * 13)).contents
    ms, ls = fixed[2], fixed[3]
    return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"


def plugin_binary(ident: str) -> Path | None:
    """The binary inside a VST3 bundle named by REAPER's fx_ident ("path.vst3<id..."), when it can be found."""
    path = Path(ident.split("<")[0])
    if path.is_file():
        return path
    inner = path / "Contents" / "x86_64-win" / path.name
    return inner if inner.is_file() else None
