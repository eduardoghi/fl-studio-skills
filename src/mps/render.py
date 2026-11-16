"""Render a saved REAPER project in a separate REAPER process.

By default a new process opens the project with reaper/mps_render.lua, which renders with the settings saved in the
project, waits a few seconds and quits through REAPER's Quit action. `reaper -newinst -renderproject` (mode
"renderproject") renders and exits at once, which with Kontakt loaded ended every process with exit code 0xC000000D
although the files were complete. Waiting before quitting avoided it (docs/render-standard.md). The environment
variable MPS_ROLE=render keeps the bridge from starting in the render process.

A missing plugin or another load error makes the render process show a dialog and wait. While the process runs, its
dialogs are checked every half second, and the first one that isn't part of a normal render is reported with its text
and the process ended, so a failure takes seconds instead of the whole timeout.

A process that ends with any other exit code than 0 isn't counted as a normal render, even with complete files.
`mps render` reports `files_ok` and `abnormal_exit` separately.
"""

import json
import os
import subprocess
import time
from pathlib import Path

# The render standard for anything measured or compared (docs/render-standard.md). Float keeps peaks above 0 dBFS,
# and dither, normalization and the other postprocessing would change the samples between versions.
STANDARD = {"format": "wav32f", "srate": 44100, "channels": 2, "speed": 0, "project_srate": 44100}
NO_POSTPROCESSING = 4 << 16  # RENDER_NORMALIZE flag that disables normalize, limit, fades, trim and pad
DITHER_ON = 1 | 2  # RENDER_DITHER flags for dither and noise shaping on the master mix
INSTRUMENT_PREFIXES = ("VSTi:", "VST3i:", "CLAPi:", "AUi:", "DXi:")


def deviations(settings: dict, plugins: list[dict] = ()) -> list[str]:
    """How a project's saved render settings and plugins (from rpp.read) differ from the standard."""
    out = [f"{k} is {settings.get(k)!r}, the standard is {v!r}" for k, v in STANDARD.items() if settings.get(k) != v]
    norm = settings.get("normalize") or 0
    if norm and not norm & NO_POSTPROCESSING:
        out.append(f"render postprocessing is on (RENDER_NORMALIZE {norm})")
    if (settings.get("dither") or 0) & DITHER_ON:
        out.append(f"dither is on (RENDER_DITHER {settings.get('dither')})")
    # Ample Guitar and EZbass rendered silence when the render started before they had loaded their samples
    loaders = [p["name"] for p in plugins if p["name"].startswith(INSTRUMENT_PREFIXES) and "(Cockos)" not in p["name"]]
    if loaders and not settings.get("fx_delay"):
        out.append(f"instruments that load samples ({', '.join(loaders)}) render without fx_delay")
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


# Dialogs a normal render shows, which must not count as failures. The render's progress window, the countdown
# REAPER shows when a project asks to wait for FX to load samples before rendering (RENDER_DELAY), and the progress of
# building peak files for audio items whose files are new (as a DI rendered just before re-amping it).
PROGRESS_DIALOGS = ("Rendering to file", "Render Queue Delay", "Building Peaks")


def reaper_exe() -> Path:
    env = os.environ.get("MPS_REAPER_EXE")
    return Path(env) if env else Path(r"C:\Program Files\REAPER (x64)\reaper.exe")


RENDER_SCRIPT = Path(__file__).resolve().parents[2] / "reaper" / "mps_render.lua"
WM_SETTEXT = 0x000C


def _answer_delay(windows, d: dict, fx_delay: float) -> bool:
    """In a process started with a script, a project with RENDER_DELAY asks for the delay with an empty field and OK.
    Fill in the project's own delay and confirm, so the wait is the one the project asks for."""
    edit = next((k["hwnd"] for k in d["_kids"] if k["class"] == "Edit"), None)
    if edit is None or "OK" not in d["buttons"]:
        return False
    windows.user32.SendMessageW(edit, WM_SETTEXT, 0, f"{fx_delay:g}")
    return windows.press(d, "OK")


def render_project(
    project: str | Path,
    *,
    timeout: float = 600.0,
    mode: str = "script",
    settle: float = 3.0,
    fx_delay: float = 0.0,
) -> dict:
    # imported here because it loads Windows libraries, while the rest of the package also runs on Linux in CI
    from mps import windows

    project = Path(project)
    if not project.is_file():
        return {"ok": False, "error": f"project not found: {project}"}
    if mode == "script":
        cmd = [str(reaper_exe()), "-newinst", "-nosplash", str(project), str(RENDER_SCRIPT)]
    elif mode == "renderproject":
        cmd = [str(reaper_exe()), "-newinst", "-nosplash", "-renderproject", str(project)]
    else:
        return {"ok": False, "error": f"unknown render mode {mode!r}"}
    # what the render script saw when it rendered (its tempo above all), written next to the project
    log = project.with_name(project.name + ".mps-render.json")
    log.unlink(missing_ok=True)
    env = {
        **os.environ,
        "MPS_ROLE": "render",
        "MPS_RENDER_SETTLE": f"{settle:g}",
        "MPS_RENDER_PROJECT": str(project.resolve()),
        "MPS_RENDER_LOG": str(log),
    }
    start = time.time()
    proc = subprocess.Popen(cmd, env=env)
    answered = False
    base = {"mode": mode, "started": start, "pid": proc.pid}
    while proc.poll() is None:
        if time.time() - start > timeout:
            proc.kill()
            return {"ok": False, "error": f"render process still running after {timeout:.0f} s, killed", **base}
        found = []
        for d in windows.dialogs(pid=proc.pid):
            if d["title"].startswith("Render Queue Delay") and "OK" in d["buttons"]:
                if not answered:
                    answered = _answer_delay(windows, d, fx_delay)
                continue
            if not d["title"].startswith(PROGRESS_DIALOGS):
                found.append(d)
        if found:
            d = found[0]
            proc.kill()
            return {
                "ok": False,
                "error": "the render process opened a dialog and was ended",
                "dialog": {"title": d["title"], "labels": d["labels"], "buttons": d["buttons"]},
                **base,
            }
        time.sleep(0.5)
    code = proc.returncode
    seen = None
    if mode == "script":
        try:
            seen = json.loads(log.read_text(encoding="utf-8", errors="replace"))
        except (FileNotFoundError, json.JSONDecodeError):
            seen = {"error": "the render script left no record"}
        log.unlink(missing_ok=True)
    return {
        "ok": True,
        "returncode": code,
        "returncode_hex": f"0x{code & 0xFFFFFFFF:08X}",
        "seconds": round(time.time() - start, 2),
        "seen": seen,
        **base,
    }
