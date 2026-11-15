"""Proof of concept 13. Malformed requests written straight into the bridge's folder each get an error answer, and
the bridge keeps running. One case asks track.add with a list as args, which must be refused without adding a track.

Usage: uv run python poc/p13_malformed_requests.py (with REAPER and the bridge running)
"""

import json
import os
import time
import uuid

from mps import reaper

inst = reaper.find_instance()
cases = {
    "expect_project_number": {"cmd": "ping", "args": {}, "expect_project": 123},
    "expires_text": {"cmd": "ping", "args": {}, "expires": "soon"},
    "args_list": {"cmd": "track.add", "args": [1, 2]},
    "not_json": None,
}
out = {}
for name, body in cases.items():
    rid = uuid.uuid4().hex
    tmp = inst.path / "tmp" / f"{rid}.client"
    tmp.write_text("{not json" if body is None else json.dumps({"id": rid, **body}), encoding="utf-8")
    os.rename(tmp, inst.path / "req" / f"{rid}.json")
    res = inst.path / "res" / f"{rid}.json"
    t = time.monotonic()
    while not res.exists() and time.monotonic() - t < 5:
        time.sleep(0.05)
    out[name] = json.loads(res.read_text(encoding="utf-8")) if res.exists() else "no answer"
    if res.exists():
        res.unlink()
out["ping_after"] = reaper.call("ping")["status"]
print(
    json.dumps(
        {
            k: (v if isinstance(v, str) else {"status": v.get("status"), "error": v.get("error")})
            for k, v in out.items()
        },
        indent=1,
    )
)
