"""Proof of concept 11. Which projects make the separate render process end with exit code 0xC000000D.

Each case is built through the bridge in a new tab (one track, four notes, 4 s rendered as 32-bit float), saved and
rendered with `reaper -newinst -renderproject`. Cases that load a plugin are also opened in a new REAPER process and
closed without rendering, to tell a failure of the render from a failure at exit. The Application log is read for
the process id of every run, but Windows didn't record every crash, so a missing record proves nothing.

Usage: uv run python poc/p11_exit_matrix.py <folder> <kontakt state.b64> [--fx-delay S] [case ...]
"""

import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

from mps import audio, reaper, render, state

folder, kontakt_state = Path(sys.argv[1]), Path(sys.argv[2])
rest = sys.argv[3:]
fx_delay = 0.0
if rest[:1] == ["--fx-delay"]:
    fx_delay, rest = float(rest[1]), rest[2:]
only = set(rest)
folder.mkdir(parents=True, exist_ok=True)

# name, plugins added in order (name for fx.add), whether notes are written, and a state to write into the first one
CASES = [
    ("empty_project", [], False, None),
    ("js_tone", ["JS:Tone Generator"], False, None),
    ("reasynth", ["VSTi:ReaSynth"], True, None),
    ("valhalla_effect", ["JS:Tone Generator", "VST3:ValhallaVintageVerb"], False, None),
    ("kontakt_empty", ["VST3i:Kontakt 8"], True, None),
    ("kontakt_evolution", ["VST3i:Kontakt 8"], True, kontakt_state),
    ("ample_sc_vst3", ["VST3i:Ample Guitar SC"], True, None),
    ("ezbass_vst3", ["VST3i:EZbass"], True, None),
    ("ezbass_vst2", ["VSTi:EZbass"], True, None),
    ("omnisphere", ["VST3i:Omnisphere"], True, None),
]


def call(cmd, args=None, timeout=120):
    r = reaper.call(cmd, args or {}, timeout=timeout)
    if r["status"] != reaper.OK:
        raise RuntimeError(f"{cmd}: {json.dumps(r)[:300]}")
    return r["result"]


def build(name, plugins, notes, chunk_file):
    rpp = folder / f"{name}.rpp"
    call("project.new_tab")
    call("project.set_tempo", {"bpm": 120, "srate": 44100})
    if plugins or notes:
        tr = call("track.add", {"name": name})
        added = [call("fx.add", {"track": tr["guid"], "name": p}) for p in plugins]
        if chunk_file:
            call(
                "fx.restore_fresh",
                {
                    "track": tr["guid"],
                    "fx": added[0]["guid"],
                    "chunk": chunk_file.read_text("ascii"),
                    "name": plugins[0],
                },
                timeout=180,
            )
            state.settle(tr["guid"], 0)
        if notes:
            item = call("item.add_midi", {"track": tr["guid"], "start_qn": 0, "end_qn": 8})
            ns = [{"start_qn": k, "end_qn": k + 0.9, "chan": 0, "pitch": 52 + 5 * k, "vel": 100} for k in range(4)]
            call("midi.write", {"item": item["guid"], "notes": ns, "replace": True})
    call(
        "render.configure",
        {
            "format": "wav32f",
            "directory": str(folder),
            "pattern": name,
            "start": 0,
            "end": 4,
            "srate": 44100,
            "channels": 2,
            "fx_delay": fx_delay,
        },
    )
    call("project.save", {"path": str(rpp)})
    call("project.close_tab", {"path": str(rpp)})
    return rpp


def crashes(pid, since):
    """Application Error events Windows recorded for this process id since the given time."""
    ps = (
        "Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000; StartTime=[datetime]'" + since + "'} "
        "-ErrorAction SilentlyContinue | ForEach-Object { $_.Message }"
    )
    # no matching event isn't an error, Windows doesn't record every crash (docs/render-standard.md)
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False, capture_output=True, text=True)
    out = out.stdout
    tag = f"0x{pid:x}".lower()
    found = []
    for msg in out.split("Faulting application name")[1:]:
        if f"faulting process id: {tag}" in msg.lower():
            module = msg.split("Faulting module name: ")[1].split(",")[0] if "Faulting module name: " in msg else "?"
            code = msg.split("Exception code: ")[1].split()[0] if "Exception code: " in msg else "?"
            found.append({"module": module, "code": code})
    return found


user32 = ctypes.windll.user32


def main_window(pid):
    found = []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit(h, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(owner))
        b = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(h, b, 64)
        if owner.value == pid and b.value == "REAPERwnd":
            found.append(h)
        return True

    user32.EnumWindows(proc(visit), 0)
    return found[0] if found else None


def open_and_close(rpp, wait=20):
    """Open the project in a new REAPER process, wait, close its main window and return the exit code."""
    exe = render.reaper_exe()
    p = subprocess.Popen([str(exe), "-newinst", "-nosplash", str(rpp)], env={**os.environ, "MPS_ROLE": "render"})
    time.sleep(wait)
    h = main_window(p.pid)
    if h is None:
        p.kill()
        return {"error": "main window not found", "pid": p.pid}
    user32.PostMessageW(h, 0x0010, 0, 0)  # WM_CLOSE
    try:
        code = p.wait(60)
    except subprocess.TimeoutExpired:
        p.kill()
        return {"error": "didn't exit after WM_CLOSE (a dialog?)", "pid": p.pid}
    return {"pid": p.pid, "returncode_hex": f"0x{code & 0xFFFFFFFF:08X}"}


results = []
since = time.strftime("%Y-%m-%d %H:%M:%S")
for name, plugins, notes, chunk in CASES:
    if only and name not in only:
        continue
    row = {"case": name, "plugins": plugins}
    try:
        rpp = build(name, plugins, notes, chunk)
    except RuntimeError as e:
        row["error"] = str(e)
        results.append(row)
        print(json.dumps(row), flush=True)
        continue
    for run in (1, 2):
        wav = folder / f"{name}.wav"
        if wav.exists():
            wav.unlink()
        res = render.render_project(rpp, timeout=300)
        check = audio.check(wav, seconds=4, samplerate=44100, channels=2, subtype="FLOAT")
        row[f"render_{run}"] = {
            "returncode_hex": res.get("returncode_hex"),
            "error": res.get("error"),
            "file_ok": check["ok"],
            "failures": check.get("failures"),
            "pid": res.get("pid"),
        }
    if plugins:
        row["open_close"] = open_and_close(rpp)
    results.append(row)
    print(json.dumps(row), flush=True)

# Windows writes the crash records a few seconds after the process ends
time.sleep(10)
for row in results:
    for key in ("render_1", "render_2", "open_close"):
        if row.get(key, {}).get("pid"):
            row[key]["crashes"] = crashes(row[key]["pid"], since)
    print(json.dumps({k: row.get(k) for k in ("case", "render_1", "open_close")}), flush=True)
(folder / f"p11_results_delay{fx_delay:g}.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
