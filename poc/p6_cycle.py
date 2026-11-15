"""Proof of concept 6. Render after restoring a state, after changing it, and after restoring it again, and compare
each render with a render of the original state.

Uses the project open in the current tab, whose render settings were set by p3_channels.py. Every step saves the
project under a new name and renders it in a separate REAPER process. A restore deletes the plugin, adds it again
and writes the saved state into the new instance (writing it into the running instance didn't take, see the notes).

Usage: uv run python poc/p6_cycle.py <track guid> <plugin name> <state.b64> <param index> <changed value 0..1>
       <baseline.wav> <folder> <layout.json from p3_channels.py>
"""

import json
import sys
import time
from pathlib import Path

from mps import audio, reaper, render

track, name, state_file, param, value, baseline, folder, layout_file = (
    sys.argv[1],
    sys.argv[2],
    Path(sys.argv[3]),
    int(sys.argv[4]),
    float(sys.argv[5]),
    sys.argv[6],
    Path(sys.argv[7]),
    Path(sys.argv[8]),
)
state = state_file.read_text("ascii")


def ok(res):
    if res["status"] != reaper.OK:
        raise SystemExit(json.dumps(res, indent=1))
    return res["result"]


def text():
    rows = ok(reaper.call("fx.params", {"track": track, "fx": 0}, timeout=60))["params"]
    return next(r for r in rows if r["index"] == param)["text"]


def settle(want=None, limit=60):
    start, last = time.monotonic(), None
    while time.monotonic() - start < limit:
        t = text()
        if t and t == last and (want is None or t == want):
            return t, round(time.monotonic() - start, 1)
        last = t
        time.sleep(1)
    raise SystemExit(f"parameter never settled (last text {last!r})")


def fresh_restore():
    ok(reaper.call("fx.delete", {"track": track, "fx": 0}))
    ok(reaper.call("fx.add", {"track": track, "name": name, "position": 0}, timeout=60))
    ok(reaper.call("fx.state_set", {"track": track, "fx": 0, "chunk": state}, timeout=120))
    return settle()


layout = json.loads(layout_file.read_text(encoding="utf-8"))
r = layout["render"]
seconds = r["end"] - r["start"]


def save_render(label):
    target = folder / f"{label}.wav"
    if target.exists():
        target.unlink()
    ok(
        reaper.call(
            "render.configure",
            {
                "directory": str(folder),
                "pattern": label,
                "format": "wav24",
                "start": r["start"],
                "end": r["end"],
                "srate": int(r["srate"]),
                "channels": int(r["channels"]),
            },
        )
    )
    project = folder / f"{label}.rpp"
    ok(reaper.call("project.save", {"path": str(project)}, timeout=60))
    res = render.render_project(project, timeout=300)
    check = audio.check(target, seconds=seconds, samplerate=int(r["srate"]), channels=int(r["channels"]))
    cmp = audio.compare(baseline, target) if check["ok"] else {}
    return {
        "label": label,
        "render_returncode": res.get("returncode"),
        "file_ok": check["ok"],
        "failures": check.get("failures"),
        "identical_to_baseline": cmp.get("identical"),
        "residual_db": cmp.get("residual_db"),
        "correlation": cmp.get("correlation"),
    }


steps = []
t, s = settle()
steps.append({"step": "restored into a fresh instance", "param": t, **save_render("p6_restored1")})
ok(reaper.call("fx.set_param", {"track": track, "fx": 0, "param": param, "value": value}))
t, s = settle(limit=20)
steps.append({"step": f"parameter {param} set to {value}", "param": t, **save_render("p6_changed")})
t, s = fresh_restore()
steps.append(
    {"step": "restored again into a fresh instance", "param": t, "settled_s": s, **save_render("p6_restored2")}
)
print(json.dumps(steps, indent=1, default=str))
