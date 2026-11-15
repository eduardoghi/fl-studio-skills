"""Client for the file bridge that runs inside REAPER (reaper/mps_bridge.lua).

A request is one JSON file with a unique id. It is written in the instance's tmp/ folder and published by renaming it
into req/, a name that doesn't exist yet, so the bridge never sees half a file. The bridge claims it by renaming it
into work/, runs it and publishes the response into res/ the same way. Where the request file sits when the client
gives up tells what happened:

- A request still in req/ was never taken. The client renames it away, and if that rename wins the command will
  never run, so the outcome is NOT_STARTED.
- A request in work/, or gone without a response, started and its effect is unknown, so the outcome is UNCERTAIN.
  The client never repeats it on its own.

Every request also carries an expiry time, so a request left behind by a client that died is refused rather than
run late.
"""

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

HEARTBEAT_MAX_AGE = 5.0

OK, ERROR, EXPIRED, NOT_STARTED, UNCERTAIN = "ok", "error", "expired", "not_started", "uncertain"


class BridgeError(Exception):
    """No usable REAPER instance, or a request that can't be sent."""


def resource_path() -> Path:
    env = os.environ.get("MPS_REAPER_RESOURCE")
    return Path(env) if env else Path(os.environ["APPDATA"]) / "REAPER"


def instances_root() -> Path:
    return resource_path() / "mps" / "instances"


@dataclass
class Instance:
    id: str
    path: Path
    info: dict
    heartbeat_age: float

    @property
    def alive(self) -> bool:
        return self.heartbeat_age <= HEARTBEAT_MAX_AGE


def heartbeat_age(path: Path) -> float:
    try:
        return time.time() - (path / "heartbeat").stat().st_mtime
    except FileNotFoundError:
        return float("inf")


def list_instances() -> list[Instance]:
    root = instances_root()
    found = []
    for d in sorted(root.iterdir()) if root.is_dir() else []:
        try:
            info = json.loads((d / "info.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        found.append(Instance(d.name, d, info, heartbeat_age(d)))
    return found


def find_instance(instance_id: str | None = None) -> Instance:
    live = [i for i in list_instances() if i.alive]
    if instance_id:
        match = [i for i in live if i.id == instance_id]
        if not match:
            raise BridgeError(f"no live REAPER instance {instance_id}")
        return match[0]
    if not live:
        raise BridgeError("no live REAPER instance with the bridge running (see `mps reaper start`)")
    if len(live) > 1:
        raise BridgeError("several live REAPER instances, pick one with --instance: " + ", ".join(i.id for i in live))
    return live[0]


def call(
    cmd: str,
    args: dict | None = None,
    *,
    instance: str | None = None,
    timeout: float = 10.0,
    expect_project: str | None = None,
    poll: float = 0.02,
) -> dict:
    """Run one bridge command and return its response, with "status" set to one of the outcomes above."""
    inst = find_instance(instance)
    rid = uuid.uuid4().hex
    request = {
        "id": rid,
        "cmd": cmd,
        "args": args or {},
        "created": time.time(),
        "expires": time.time() + timeout,
        "expect_project": expect_project,
    }
    tmp = inst.path / "tmp" / f"{rid}.client"
    req = inst.path / "req" / f"{rid}.json"
    work = inst.path / "work" / f"{rid}.json"
    res = inst.path / "res" / f"{rid}.json"
    tmp.write_text(json.dumps(request), encoding="utf-8")
    os.rename(tmp, req)  # the destination never exists, so this publishes the whole file at once
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if res.exists():
            return _take(res)
        # The bridge can't beat while it runs a command, so a stale heartbeat only ends the wait while the request is
        # still unclaimed (REAPER hung or gone). A claimed one gets the whole timeout, as a slow plugin load needs.
        if heartbeat_age(inst.path) > HEARTBEAT_MAX_AGE * 2 and req.exists():
            break
        time.sleep(poll)
    if res.exists():
        return _take(res)
    withdrawn = inst.path / "tmp" / f"{rid}.withdrawn"
    try:
        os.rename(req, withdrawn)
        withdrawn.unlink()
        return {"id": rid, "status": NOT_STARTED, "error": _why(inst, "the bridge never took the request")}
    except FileNotFoundError:
        pass
    if res.exists():
        return _take(res)
    where = "is running" if work.exists() else "ran but left no response"
    return {"id": rid, "status": UNCERTAIN, "error": _why(inst, f"the command {where}; its effect is unknown")}


def _take(res: Path) -> dict:
    body = json.loads(res.read_text(encoding="utf-8"))
    res.unlink()
    return body


def _why(inst: Instance, what: str) -> str:
    age = heartbeat_age(inst.path)
    beat = "no heartbeat" if age == float("inf") else f"last heartbeat {age:.1f} s ago"
    return f"{what} ({beat})"
