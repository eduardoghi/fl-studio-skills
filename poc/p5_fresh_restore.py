"""Proof of concept 5b. Restore a saved state into a freshly added instance of the plugin, then wait until it settles.

Deletes the plugin at the given index, adds the same plugin again at that position, writes the saved vst_chunk into
it and polls until the watched parameter shows text and two reads of it agree. Prints the parameter text and how
long the plugin took to settle.

Usage: uv run python poc/p5_fresh_restore.py <track guid> <fx index> <plugin name> <state.b64> <watched param index>
"""

import json
import sys
import time
from pathlib import Path

from mps import reaper

track, fx, name, state_file, param = sys.argv[1], int(sys.argv[2]), sys.argv[3], Path(sys.argv[4]), int(sys.argv[5])


def ok(res):
    if res["status"] != reaper.OK:
        raise SystemExit(json.dumps(res, indent=1))
    return res["result"]


def text():
    rows = ok(reaper.call("fx.params", {"track": track, "fx": fx, "contains": None}, timeout=60))["params"]
    return next(r for r in rows if r["index"] == param)["text"]


ok(reaper.call("fx.delete", {"track": track, "fx": fx}))
added = ok(reaper.call("fx.add", {"track": track, "name": name, "position": fx}, timeout=60))
start = time.monotonic()
set_res = ok(
    reaper.call("fx.state_set", {"track": track, "fx": fx, "chunk": state_file.read_text("ascii")}, timeout=120)
)
seen, last = [], None
while time.monotonic() - start < 60:
    t = text()
    seen.append(t)
    if t and t == last:
        break
    last = t
    time.sleep(1)
print(
    json.dumps(
        {
            "added": added["name"],
            "settled_after_s": round(time.monotonic() - start, 1),
            "param_text": seen[-1],
            "texts_seen": seen[:8],
        },
        indent=1,
    )
)
