"""Renders a saved project with FL Studio's command line exporter.

FL opens a separate instance, exports and closes. With FL already open the
command hands over to it, exits with code 0 and writes nothing, so this refuses
to run in that case.
"""

import glob
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class RenderError(Exception):
    pass


def find_fl():
    configured = os.environ.get("FL_STUDIO_EXE")
    if configured:
        return Path(configured)
    found = sorted(glob.glob(r"C:\Program Files\Image-Line\FL Studio*\FL64.exe"))
    if not found:
        raise RenderError("FL64.exe not found, set FL_STUDIO_EXE")
    return Path(found[-1])


def fl_is_running():
    listing = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq FL64.exe", "/NH"], check=False, capture_output=True, text=True
    )
    return "FL64.exe" in listing.stdout


def command(fl, project, output):
    """Build the arguments. FL reads the output path from the /R switch itself."""
    return [str(fl), f"/R{output}", "/Ewav", f"/O{output.parent}", str(project)]


def render(project, output, timeout=300, running=fl_is_running, run=subprocess.run):
    """Render project to output and return the size of the WAV.

    Works on a copy, so FL can't touch the project file. Only what was saved
    to disk is rendered.
    """
    project = Path(project)
    output = Path(output)
    if not project.is_file():
        raise RenderError(f"{project} doesn't exist")
    if running():
        raise RenderError("FL Studio is open. The command line render only works with it closed")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        copy = work / "render.flp"
        shutil.copy2(project, copy)
        rendered = work / "render.wav"
        try:
            done = run(command(find_fl(), copy, rendered), check=False, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise RenderError(f"FL didn't finish within {timeout} s") from exc
        if done.returncode != 0:
            raise RenderError(f"FL exited with code {done.returncode}")
        if not rendered.is_file() or rendered.stat().st_size < 1000:
            raise RenderError("FL exited without writing a WAV")
        shutil.move(rendered, output)
    return output.stat().st_size
