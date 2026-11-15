"""Save a plugin's whole state and restore it, checked at the first two of three levels.

1. Integrity. The stored file's SHA-256 matches its name, which only proves the file didn't change since it was
   saved. Some plugins (Kontakt) give different bytes for the same state on every read, so a new hash after a
   restore says nothing about the plugin.
2. Configuration. The displayed text of every exposed parameter after the restore, against the text recorded when
   the state was saved. Some plugins report it late or leave it empty, which is reported as unavailable.
3. Sound. Renders of the restored state against repeated renders of the original, judged by the variation between
   those repeats (`mps wav variation`). Only this level shows the sound came back.

How a plugin takes a state back is a property of that plugin and isn't assumed for another one (skills/plugins).
"""

import hashlib
import json
import time
from pathlib import Path

from mps import manifest, reaper

# A parameter list read twice this far apart with the same text counts as settled.
SETTLE_STEP_S = 1.0
# Kontakt left the parameter text empty in some fresh instances although the instrument had loaded. After this long,
# a state whose length stopped changing counts as settled, with the text reported as unavailable.
TEXT_GRACE_S = 10.0


class StateError(Exception):
    pass


def _ok(res: dict) -> dict:
    if res.get("status") != reaper.OK:
        raise StateError(json.dumps(res, default=str))
    return res["result"]


def _params(track: str, fx, instance=None) -> list[dict]:
    res = _ok(reaper.call("fx.params", {"track": track, "fx": fx}, instance=instance, timeout=60))
    return [{"index": p["index"], "name": p["name"], "ident": p["ident"], "text": p["text"]} for p in res["params"]]


def _length(track: str, fx, instance=None) -> int:
    return _ok(reaper.call("fx.state_get", {"track": track, "fx": fx}, instance=instance, timeout=120))["length"]


def settle(track: str, fx, *, limit: float = 60.0, instance=None, sleep=None, clock=None) -> dict:
    """Wait until the plugin's parameter text stops changing, as a sign that a load or restore finished."""
    sleep = sleep or time.sleep
    clock = clock or time.monotonic
    start = clock()
    last, last_len = None, None
    while clock() - start < limit:
        params = _params(track, fx, instance)
        texts = [p["text"] for p in params]
        if texts == last and any(texts):
            return {"seconds": round(clock() - start, 1), "params": params, "text_available": True}
        if clock() - start >= TEXT_GRACE_S and not any(texts):
            n = _length(track, fx, instance)
            if n == last_len:
                return {"seconds": round(clock() - start, 1), "params": params, "text_available": False}
            last_len = n
        last = texts
        sleep(SETTLE_STEP_S)
    raise StateError(f"the plugin didn't settle within {limit:.0f} s")


def save(track: str, fx, folder: str | Path, *, instance=None) -> dict:
    """Store the state as <sha256>.b64 with a record of the plugin and its parameter text next to it."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    settled = settle(track, fx, instance=instance)
    got = _ok(reaper.call("fx.state_get", {"track": track, "fx": fx}, instance=instance, timeout=120))
    chunk = got["chunk"]
    sha = hashlib.sha256(chunk.encode("ascii")).hexdigest()
    ident = got["fx"].get("ident") or ""
    binary = manifest.plugin_binary(ident) if ident else None
    record = {
        "sha256": sha,
        "length": len(chunk),
        "plugin": got["fx"].get("name"),
        "ident": ident,
        "version": manifest.file_version(binary) if binary else None,
        "params": settled["params"],
        "text_available": settled["text_available"],
        "saved": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (folder / f"{sha}.b64").write_text(chunk, encoding="ascii")
    (folder / f"{sha}.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    return {"state": str(folder / f"{sha}.b64"), **{k: v for k, v in record.items() if k != "params"}}


def integrity(state_file: str | Path) -> dict:
    """Level 1. Whether the stored state still has the hash it was named after."""
    p = Path(state_file)
    sha = manifest.sha256_file(p)
    return {"ok": sha == p.stem, "sha256": sha, "named": p.stem}


def compare_params(saved: list[dict], now: list[dict]) -> dict:
    """Level 2. Parameters whose displayed text differs from the text recorded with the state."""
    before = {p["index"]: p for p in saved}
    after = {p["index"]: p for p in now}
    differ = [
        {"index": i, "name": before[i]["name"], "saved": before[i]["text"], "now": after[i]["text"]}
        for i in sorted(before.keys() & after.keys())
        if before[i]["text"] != after[i]["text"]
    ]
    missing = sorted(before.keys() ^ after.keys())
    return {
        "ok": not differ and not missing,
        "compared": len(before.keys() & after.keys()),
        "differ": differ,
        "missing": missing,
    }


def restore(track: str, fx, state_file: str | Path, *, name: str | None = None, instance=None) -> dict:
    """Write a stored state back, into a new instance when a plugin name is given (fx.restore_fresh) or into the
    running one otherwise, and check levels 1 and 2."""
    p = Path(state_file)
    level1 = integrity(p)
    if not level1["ok"]:
        return {"ok": False, "integrity": level1, "error": "the state file doesn't match its hash, nothing restored"}
    chunk = p.read_text(encoding="ascii")
    if name:
        cmd, args = "fx.restore_fresh", {"track": track, "fx": fx, "chunk": chunk, "name": name}
    else:
        cmd, args = "fx.state_set", {"track": track, "fx": fx, "chunk": chunk}
    done = _ok(reaper.call(cmd, args, instance=instance, timeout=180))
    target = done["fx"]["guid"]
    settled = settle(track, target, instance=instance)
    record_file = p.with_suffix(".json")
    if record_file.is_file():
        record = json.loads(record_file.read_text(encoding="utf-8"))
        level2 = compare_params(record["params"], settled["params"])
        level2["text_available"] = settled["text_available"] and record.get("text_available", True)
        if not level2["text_available"]:
            # empty text proves nothing either way, so the level can't be judged
            level2["ok"] = None
    else:
        level2 = {"ok": None, "reason": "no record of the parameter text saved with the state"}
    return {
        "ok": level2.get("ok") is not False,
        "mode": "fresh instance" if name else "in place",
        "fx": target,
        "read_back_identical": done.get("identical"),
        "integrity": level1,
        "configuration": level2,
        "settled_s": settled["seconds"],
        "sound": "not checked here, render and run mps wav variation",
    }
