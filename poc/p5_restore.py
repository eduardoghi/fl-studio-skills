"""Proof of concept 5. Change an instrument or effect, restore its saved state and check it came back.

Steps, all on the project open in the current tab:
1. set one parameter to another value (the change), save the project as <base>_changed.rpp
2. write the saved state back with fx.state_set, read the parameter and the state again, save as <base>_restored.rpp

Both projects keep the render settings of the open project, with the output name changed, so each can be rendered
and compared with a render of the original state.

Usage: uv run python poc/p5_restore.py <track guid> <fx index> <param index> <new value 0..1> <state.b64> <base path>
"""

import hashlib
import json
import sys
from pathlib import Path

from mps import reaper

track, fx, param, value, state_file, base = (
    sys.argv[1],
    int(sys.argv[2]),
    int(sys.argv[3]),
    float(sys.argv[4]),
    Path(sys.argv[5]),
    Path(sys.argv[6]),
)


def ok(res):
    if res["status"] != reaper.OK:
        raise SystemExit(json.dumps(res, indent=1))
    return res["result"]


def param_text():
    rows = ok(reaper.call("fx.params", {"track": track, "fx": fx}, timeout=60))["params"]
    return next(r for r in rows if r["index"] == param)["text"]


def save_as(suffix):
    path = base.with_name(base.name + suffix + ".rpp")
    ok(reaper.call("render.configure", {**render, "pattern": base.name + suffix}))
    ok(reaper.call("project.save", {"path": str(path)}, timeout=60))
    return str(path)


saved = state_file.read_text(encoding="ascii")
saved_hash = hashlib.sha256(saved.encode("ascii")).hexdigest()
layout = json.loads(Path(ok(reaper.call("ping"))["project"]).with_suffix(".json").read_text(encoding="utf-8"))
r = layout["render"]
render = {
    "directory": str(Path(r["targets"]).parent),
    "format": "wav24",
    "start": r["start"],
    "end": r["end"],
    "srate": int(r["srate"]),
    "channels": int(r["channels"]),
}
before = param_text()
ok(reaper.call("fx.set_param", {"track": track, "fx": fx, "param": param, "value": value}))
changed_text = param_text()
changed_project = save_as("_changed")
back = ok(reaper.call("fx.state_set", {"track": track, "fx": fx, "chunk": saved}, timeout=60))
restored_text = param_text()
again = ok(reaper.call("fx.state_get", {"track": track, "fx": fx}, timeout=60))["chunk"]
restored_project = save_as("_restored")
print(
    json.dumps(
        {
            "param_before": before,
            "param_changed": changed_text,
            "param_restored": restored_text,
            "state_identical_after_set": back["identical"],
            "state_hash_saved": saved_hash,
            "state_hash_read_again": hashlib.sha256(again.encode("ascii")).hexdigest(),
            "changed_project": changed_project,
            "restored_project": restored_project,
        },
        indent=1,
    )
)
