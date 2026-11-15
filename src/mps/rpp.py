"""Read the render settings and the plugins of a saved REAPER project, for the record of a render.

Projects are built and changed through the bridge, never by writing this text. Reading it is how a render records
what the separate render process actually loaded. How each line maps to a setting was checked against the values
the bridge set and read back (REAPER 7.86, see docs/render-standard.md).
"""

import re
from pathlib import Path

TOKEN = re.compile(r'"[^"]*"|\'[^\']*\'|`[^`]*`|\S+')
# RENDER_FORMAT values the bridge writes, by name (the same table as RENDER_FORMATS in reaper/mps_bridge.lua)
FORMATS = {"ZXZhdxAAAQ==": "wav16", "ZXZhdxgAAQ==": "wav24", "ZXZhdyAAAQ==": "wav32f"}
# RENDER_1X values whose meaning was seen in the render dialog
SPEEDS = {0: "offline, full speed"}
PLUGIN_TAGS = ("VST", "JS", "CLAP", "AU", "DX", "LV2")


def tokens(line: str) -> list[str]:
    return [t[1:-1] if t[0] in "\"'`" and len(t) > 1 else t for t in TOKEN.findall(line)]


def _num(s: str) -> float:
    v = float(s)
    return int(v) if v.is_integer() else v


def render_settings(text: str) -> dict:
    lines = text.splitlines()
    top: dict[str, list[str]] = {}
    for i, line in enumerate(lines):
        # project-level lines are indented by two spaces, deeper ones belong to tracks and items
        if not line.startswith("  ") or line.startswith("   "):
            continue
        t = tokens(line.strip())
        if not t:
            continue
        key = t[0]
        if key == "<RENDER_CFG":
            # the base64 follows on the same line or on the next ones until ">"
            body = t[1:]
            j = i + 1
            while not body and j < len(lines) and lines[j].strip() != ">":
                body = tokens(lines[j].strip())
                j += 1
            top[key] = body
        elif key.startswith(("RENDER_", "SAMPLERATE")) and key not in top:
            top[key] = t[1:]

    def field(key, idx, default=None):
        v = top.get(key)
        return _num(v[idx]) if v and len(v) > idx else default

    cfg = (top.get("<RENDER_CFG") or [""])[0]
    speed = field("RENDER_1X", 0)
    return {
        "file": (top.get("RENDER_FILE") or [""])[0],
        "pattern": (top.get("RENDER_PATTERN") or [""])[0],
        "format": FORMATS.get(cfg, cfg or None),
        "channels": field("RENDER_FMT", 1),
        "srate": field("RENDER_FMT", 2),
        "speed": speed,
        "speed_label": SPEEDS.get(int(speed), "not mapped") if speed is not None else None,
        "bounds": field("RENDER_RANGE", 0),
        "start": field("RENDER_RANGE", 1),
        "end": field("RENDER_RANGE", 2),
        "tail_flag": field("RENDER_RANGE", 3, 0),
        "tail_ms": field("RENDER_RANGE", 4, 0),
        "settings": field("RENDER_STEMS", 0, 0),
        "fx_delay": field("RENDER_QDELAY", 0, 0),
        "dither": field("RENDER_DITHER", 0, 0),
        "normalize": field("RENDER_NORMALIZE", 0, 0),
        "resample": top.get("RENDER_RESAMPLE"),
        "project_srate": field("SAMPLERATE", 0),
    }


def plugins(text: str) -> list[dict]:
    """Every plugin in the project, in file order, with the name and the binary's file name the project names."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("<"):
            continue
        t = tokens(s)
        tag = t[0][1:]
        if tag not in PLUGIN_TAGS or len(t) < 2:
            continue
        if tag == "JS":
            out.append({"type": "JS", "name": t[1], "file": None})
        else:
            out.append({"type": tag, "name": t[1], "file": t[2] if len(t) > 2 else None})
    return out


def read(path: str | Path) -> tuple[dict, list[dict]]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return render_settings(text), plugins(text)
