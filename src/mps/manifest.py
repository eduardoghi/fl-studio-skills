"""Facts an experiment record needs to be reproduced or audited later."""

import ctypes
import hashlib
import os
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
    if os.name != "nt" or not Path(path).is_file():
        return None
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


# Folders searched for a plugin binary named in a project, when MPS_PLUGIN_PATHS (separated by ;) isn't set.
# These are the Windows defaults for VST3 and VST2. A project names only the file, as "Kontakt 8 Portable.vst3".
PLUGIN_ROOTS = (
    r"C:\Program Files\Common Files\VST3",
    r"C:\Program Files\Common Files\VST2",
    r"C:\Program Files\VSTPlugins",
    r"C:\Program Files\Steinberg\VSTPlugins",
    r"C:\Program Files\Common Files\Steinberg\VST2",
)


def find_plugin(file_name: str, roots: list[str] | None = None) -> Path | None:
    """The plugin file or VST3 bundle a project names, searched by name under the plugin folders."""
    if roots is None:
        env = os.environ.get("MPS_PLUGIN_PATHS")
        roots = env.split(";") if env else list(PLUGIN_ROOTS)
    want = file_name.lower()
    for root in roots:
        # follows links, since a plugin folder can be a link to where the plugin really is (Kontakt Portable here)
        for folder, dirs, files in os.walk(root, followlinks=True):
            for name in dirs + files:
                if name.lower() == want:
                    return Path(folder) / name
    return None


def plugin_version(file_name: str) -> dict:
    """Where a plugin named in a project is installed and the version its binary declares."""
    found = find_plugin(file_name)
    binary = plugin_binary(str(found)) if found else None
    return {"path": str(binary) if binary else None, "version": file_version(binary) if binary else None}


def plugin_binary(ident: str) -> Path | None:
    """The binary inside a VST3 bundle named by REAPER's fx_ident ("path.vst3<id..."), when it can be found."""
    path = Path(ident.split("<")[0])
    if path.is_file():
        return path
    inner = path / "Contents" / "x86_64-win" / path.name
    return inner if inner.is_file() else None
