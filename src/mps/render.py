"""Render a saved REAPER project in a separate REAPER process.

`reaper -newinst -renderproject project.rpp` starts a new instance, renders with the render settings saved in the
project and exits, leaving the instance in use alone. The environment variable MPS_ROLE=render keeps the bridge from
starting in that instance.

A missing plugin or another load error makes the render instance show a dialog and wait. While the process runs, its
dialogs are checked every half second, and the first one found (other than the render progress window) is reported
with its text and the process ended, so a failure takes seconds instead of the whole timeout.

The render process exited with code 0xC000000D after every render of a Kontakt project in the tests, with complete
files. The cause isn't known, so `mps render` doesn't count such a render as a normal one. It reports `files_ok` and
`abnormal_exit` separately and `ok` only when the files check out and the process exited with 0.
"""

import os
import subprocess
import time
from pathlib import Path

# The render standard for anything measured or compared (docs/render-standard.md). Float keeps peaks above 0 dBFS,
# and dither, normalization and the other postprocessing would change the samples between versions.
STANDARD = {"format": "wav32f", "srate": 44100, "channels": 2, "speed": 0, "project_srate": 44100}
NO_POSTPROCESSING = 4 << 16  # RENDER_NORMALIZE flag that disables normalize, limit, fades, trim and pad
DITHER_ON = 1 | 2  # RENDER_DITHER flags for dither and noise shaping on the master mix


def deviations(settings: dict) -> list[str]:
    """How a project's saved render settings (from rpp.render_settings) differ from the standard."""
    out = [f"{k} is {settings.get(k)!r}, the standard is {v!r}" for k, v in STANDARD.items() if settings.get(k) != v]
    norm = settings.get("normalize") or 0
    if norm and not norm & NO_POSTPROCESSING:
        out.append(f"render postprocessing is on (RENDER_NORMALIZE {norm})")
    if (settings.get("dither") or 0) & DITHER_ON:
        out.append(f"dither is on (RENDER_DITHER {settings.get('dither')})")
    if settings.get("bounds") != 0:
        out.append(f"bounds are {settings.get('bounds')!r}, the standard is explicit start and end (0)")
    return out


def targets(settings: dict) -> list[Path]:
    """The file a project's saved settings render to, when it can be told without REAPER.

    The bridge sets a directory and a plain name, which REAPER saves joined in RENDER_FILE. A pattern with wildcards
    (such as $project) only REAPER expands, so it gives nothing here and the caller's --expect list has to name it.
    """
    file, pattern = settings.get("file") or "", settings.get("pattern") or ""
    ext = {"wav16": ".wav", "wav24": ".wav", "wav32f": ".wav"}.get(settings.get("format") or "")
    if not file or not ext:
        return []
    if not pattern:
        p = Path(file)
        return [p if p.suffix.lower() == ext else p.with_name(p.name + ext)]
    if any(c in pattern for c in "$*?"):
        return []
    return [Path(file) / (pattern + ext)]


def expected_seconds(settings: dict) -> float | None:
    """The length a render with explicit bounds should have, with its tail when the tail applies to them."""
    if settings.get("bounds") != 0 or settings.get("start") is None or settings.get("end") is None:
        return None
    tail = settings.get("tail_ms", 0) / 1000 if settings.get("tail_flag", 0) & 1 else 0.0
    return settings["end"] - settings["start"] + tail


# Dialogs a normal render shows, which must not count as failures. The render's progress window, and the countdown
# REAPER shows when a project asks to wait for FX to load samples before rendering (RENDER_DELAY).
PROGRESS_DIALOGS = ("Rendering to file", "Render Queue Delay")


def reaper_exe() -> Path:
    env = os.environ.get("MPS_REAPER_EXE")
    return Path(env) if env else Path(r"C:\Program Files\REAPER (x64)\reaper.exe")


def render_project(project: str | Path, *, timeout: float = 600.0) -> dict:
    # imported here because it loads Windows libraries, while the rest of the package also runs on Linux in CI
    from mps import windows

    project = Path(project)
    if not project.is_file():
        return {"ok": False, "error": f"project not found: {project}"}
    cmd = [str(reaper_exe()), "-newinst", "-nosplash", "-renderproject", str(project)]
    env = {**os.environ, "MPS_ROLE": "render"}
    start = time.time()
    proc = subprocess.Popen(cmd, env=env)
    while proc.poll() is None:
        if time.time() - start > timeout:
            proc.kill()
            return {
                "ok": False,
                "error": f"render process still running after {timeout:.0f} s, killed",
                "started": start,
            }
        found = [d for d in windows.dialogs(pid=proc.pid) if not d["title"].startswith(PROGRESS_DIALOGS)]
        if found:
            d = found[0]
            proc.kill()
            return {
                "ok": False,
                "error": "the render instance opened a dialog and was ended",
                "dialog": {"title": d["title"], "labels": d["labels"], "buttons": d["buttons"]},
                "started": start,
            }
        time.sleep(0.5)
    code = proc.returncode
    return {
        "ok": True,
        "returncode": code,
        "returncode_hex": f"0x{code & 0xFFFFFFFF:08X}",
        "seconds": round(time.time() - start, 2),
        "started": start,
    }
