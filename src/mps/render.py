"""Render a saved REAPER project in a separate REAPER process.

`reaper -newinst -renderproject project.rpp` starts a new instance, renders with the render settings saved in the
project and exits, leaving the instance in use alone. The environment variable MPS_ROLE=render keeps the bridge from
starting in that instance.

A missing plugin or another load error makes the render instance show a dialog and wait. While the process runs, its
dialogs are checked every half second, and the first one found (other than the render progress window) is reported
with its text and the process ended, so a failure takes seconds instead of the whole timeout.

The render process exited with code 0xC000000D after every render of a Kontakt project in the tests, with complete
files, so the exit code is reported but the files decide whether the render worked.
"""

import os
import subprocess
import time
from pathlib import Path

from mps import windows


def reaper_exe() -> Path:
    env = os.environ.get("MPS_REAPER_EXE")
    return Path(env) if env else Path(r"C:\Program Files\REAPER (x64)\reaper.exe")


def render_project(project: str | Path, *, timeout: float = 600.0) -> dict:
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
        # the progress window of the render is a dialog too, and must not count as a failure
        found = [d for d in windows.dialogs(pid=proc.pid) if not d["title"].startswith("Rendering to file")]
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
