"""Proof of concept 8. Open a saved project in a new REAPER process and read the plugin states back through the
bridge that __startup.lua starts there.

Starts `reaper -newinst <project>`, waits for a new live bridge instance, reads the effect's vst_chunk (compared with
the saved file by SHA-256) and the formatted values of chosen parameters, then ends that process. The REAPER in use
is left alone.

Usage: uv run python poc/p8_reopen.py <project.rpp> <effect state.b64> <checks.json>
       checks.json lists {"fx": index, "param": index, "text": expected} entries for the first track
"""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from mps import reaper, render

project, state_file, checks = Path(sys.argv[1]), Path(sys.argv[2]), json.loads(Path(sys.argv[3]).read_text())
before = {i.id for i in reaper.list_instances() if i.alive}
proc = subprocess.Popen([str(render.reaper_exe()), "-newinst", "-nosplash", str(project)])
new = None
start = time.monotonic()
while time.monotonic() - start < 120 and new is None:
    time.sleep(1)
    live = [i for i in reaper.list_instances() if i.alive and i.id not in before]
    new = live[0] if live else None
if new is None:
    proc.kill()
    raise SystemExit("no bridge came up in the new REAPER process")
info = reaper.call("project.info", instance=new.id, timeout=60)
track = info["result"]["tracks"][0]["guid"]
time.sleep(5)  # Kontakt finishes loading its instrument after the project opens
results = []
for c in checks:
    rows = reaper.call("fx.params", {"track": track, "fx": c["fx"]}, instance=new.id, timeout=60)["result"]["params"]
    got = next(r["text"] for r in rows if r["index"] == c["param"])
    results.append({**c, "got": got, "ok": got == c["text"]})
effect = reaper.call("fx.state_get", {"track": track, "fx": 1}, instance=new.id, timeout=60)["result"]["chunk"]
saved = state_file.read_text("ascii")
report = {
    "instance": new.id,
    "project": info["result"]["project"],
    "seconds_to_bridge": round(time.monotonic() - start),
    "fx": [f["name"] for f in info["result"]["tracks"][0]["fx"]],
    "param_checks": results,
    "effect_state_identical": effect == saved,
    "effect_state_sha256": hashlib.sha256(effect.encode("ascii")).hexdigest(),
}
proc.kill()
print(json.dumps(report, indent=1))
