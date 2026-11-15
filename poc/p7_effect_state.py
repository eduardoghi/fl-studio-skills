"""Proof of concept 7. Save and restore the state of a VST3 effect, in place and into a fresh instance.

Adds the effect after the instrument, sets three parameters, saves its vst_chunk and the formatted values of all
its parameters, changes two of them, writes the saved state back into the same instance and compares every
formatted value, then does the same into a freshly added instance.

Usage: uv run python poc/p7_effect_state.py <track guid> <effect name> <state folder>
"""

import hashlib
import json
import sys
import time
from pathlib import Path

from mps import reaper

track, name, folder = sys.argv[1], sys.argv[2], Path(sys.argv[3])


def ok(res):
    if res["status"] != reaper.OK:
        raise SystemExit(json.dumps(res, indent=1))
    return res["result"]


def values(fx):
    time.sleep(0.3)
    return {p["name"]: p["text"] for p in ok(reaper.call("fx.params", {"track": track, "fx": fx}))["params"]}


def find(fx, pname):
    return next(
        p["index"]
        for p in ok(reaper.call("fx.params", {"track": track, "fx": fx, "contains": pname}))["params"]
        if p["name"] == pname
    )


fx = ok(reaper.call("fx.add", {"track": track, "name": name, "position": 1}))["index"]
for pname, v in (("Mix", 0.3), ("Decay", 0.2), ("PreDelay", 0.1)):
    ok(reaper.call("fx.set_param", {"track": track, "fx": fx, "param": find(fx, pname), "value": v}))
original = values(fx)
chunk = ok(reaper.call("fx.state_get", {"track": track, "fx": fx}))["chunk"]
digest = hashlib.sha256(chunk.encode("ascii")).hexdigest()
folder.mkdir(parents=True, exist_ok=True)
(folder / f"{digest}.b64").write_text(chunk, encoding="ascii")
again = ok(reaper.call("fx.state_get", {"track": track, "fx": fx}))["chunk"]
for pname, v in (("Mix", 0.9), ("Decay", 0.8)):
    ok(reaper.call("fx.set_param", {"track": track, "fx": fx, "param": find(fx, pname), "value": v}))
changed = values(fx)
in_place = ok(reaper.call("fx.state_set", {"track": track, "fx": fx, "chunk": chunk}))
after_in_place = values(fx)
ok(reaper.call("fx.delete", {"track": track, "fx": fx}))
fx = ok(reaper.call("fx.add", {"track": track, "name": name, "position": 1}))["index"]
fresh = ok(reaper.call("fx.state_set", {"track": track, "fx": fx, "chunk": chunk}))
after_fresh = values(fx)


def diff(a, b):
    return {k: [a[k], b.get(k)] for k in a if a[k] != b.get(k)}


print(
    json.dumps(
        {
            "effect": name,
            "state_sha256": digest,
            "state_length": len(chunk),
            "two_reads_identical": again == chunk,
            "changed": diff(original, changed),
            "in_place": {"chunk_identical": in_place["identical"], "differences": diff(original, after_in_place)},
            "fresh": {"chunk_identical": fresh["identical"], "differences": diff(original, after_fresh)},
            "values": original,
        },
        indent=1,
    )
)
