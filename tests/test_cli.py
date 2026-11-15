"""Exit codes of `mps reaper call` and what `mps reaper prune` removes."""

import json
import os
import time

import pytest

from mps import cli, reaper


@pytest.mark.parametrize(
    ("status", "code"),
    [(reaper.OK, 0), (reaper.ERROR, 1), (reaper.NOT_STARTED, 3), (reaper.UNCERTAIN, 4), (reaper.EXPIRED, 5)],
)
def test_call_exit_codes(monkeypatch, capsys, status, code):
    monkeypatch.setattr(reaper, "call", lambda *a, **kw: {"status": status, "result": {}})
    assert cli.main(["reaper", "call", "ping"]) == code
    assert json.loads(capsys.readouterr().out)["status"] == status


def test_call_without_instance_is_not_started(monkeypatch, capsys):
    def no_instance(*a, **kw):
        raise reaper.BridgeError("no live REAPER instance")

    monkeypatch.setattr(reaper, "call", no_instance)
    assert cli.main(["reaper", "call", "ping"]) == 3


def test_bad_json_arguments_are_usage_errors(capsys):
    assert cli.main(["reaper", "call", "ping", "--args", "{not json"]) == 2


def _instance(root, name, beat_age):
    d = root / "mps" / "instances" / name
    for sub in ("req", "work", "res", "tmp"):
        (d / sub).mkdir(parents=True)
    (d / "info.json").write_text("{}")
    (d / "heartbeat").write_text("1")
    t = time.time() - beat_age
    os.utime(d / "heartbeat", (t, t))
    return d


def test_prune(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MPS_REAPER_RESOURCE", str(tmp_path))
    dead = _instance(tmp_path, "dead", 7200)
    unfinished = _instance(tmp_path, "unfinished", 7200)
    (unfinished / "work" / "x.json").write_text("{}")
    live = _instance(tmp_path, "live", 0)
    old = live / "res" / "old.json"
    old.write_text("{}")
    os.utime(old, (time.time() - 7200, time.time() - 7200))
    (live / "res" / "new.json").write_text("{}")
    assert cli.main(["reaper", "prune", "--older-than", "60"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"removed": ["dead"], "kept_with_unfinished_requests": ["unfinished"], "stale_responses_removed": 1}
    assert not dead.exists() and unfinished.exists()
    assert sorted(p.name for p in (live / "res").iterdir()) == ["new.json"]
