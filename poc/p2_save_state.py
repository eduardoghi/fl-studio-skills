"""Proof of concept 2. Save the state of the instrument set up by hand and the project holding it.

Writes the plugin's vst_chunk to a file named by its SHA-256, with a JSON record next to it (plugin identity, size,
hash), then saves the project.

Usage: uv run python poc/p2_save_state.py <track guid> <fx index> <state folder> <project.rpp> <label>
"""

import hashlib
import json
import sys
from pathlib import Path

from mps import reaper

track, fx, folder, rpp, label = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], sys.argv[5]
res = reaper.call("fx.state_get", {"track": track, "fx": fx}, timeout=60)
if res["status"] != reaper.OK:
    raise SystemExit(json.dumps(res, indent=1))
chunk = res["result"]["chunk"]
digest = hashlib.sha256(chunk.encode("ascii")).hexdigest()
folder.mkdir(parents=True, exist_ok=True)
(folder / f"{digest}.b64").write_text(chunk, encoding="ascii")
record = {"label": label, "sha256": digest, "length": len(chunk), "fx": res["result"]["fx"]}
(folder / f"{label}.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
saved = reaper.call("project.save", {"path": rpp}, timeout=60)
print(
    json.dumps({"state": record, "save": saved["status"], "project": saved.get("result", {}).get("project")}, indent=1)
)
