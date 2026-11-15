"""The client's outcome rules, against a fake bridge folder. No REAPER needed."""

import json
import os
import threading
import time

import pytest

from mps import reaper


@pytest.fixture
def instance(tmp_path, monkeypatch):
    monkeypatch.setenv("MPS_REAPER_RESOURCE", str(tmp_path))
    d = tmp_path / "mps" / "instances" / "abc"
    for sub in ("req", "work", "res", "tmp"):
        (d / sub).mkdir(parents=True)
    (d / "info.json").write_text(json.dumps({"instance": "abc"}))
    (d / "heartbeat").write_text("1")
    return d


def beat(d, stop):
    while not stop.is_set():
        (d / "heartbeat").write_text(str(time.time()))
        time.sleep(0.1)


def bridge(d, stop, *, respond=True, claim=True, delay=0.0):
    """Claim requests by renaming them into work/, then publish a response by renaming it into res/."""
    while not stop.is_set():
        for name in os.listdir(d / "req"):
            if not claim:
                continue
            try:
                os.rename(d / "req" / name, d / "work" / name)
            except FileNotFoundError:
                continue
            req = json.loads((d / "work" / name).read_text())
            time.sleep(delay)
            if respond:
                tmp = d / "tmp" / (name + ".tmp")
                tmp.write_text(json.dumps({"id": req["id"], "status": "ok", "result": {"cmd": req["cmd"]}}))
                os.rename(tmp, d / "res" / name)
                (d / "work" / name).unlink()
        time.sleep(0.01)


def run(d, **kw):
    stop = threading.Event()
    threads = [
        threading.Thread(target=beat, args=(d, stop)),
        threading.Thread(target=bridge, args=(d, stop), kwargs=kw),
    ]
    for t in threads:
        t.start()
    return stop, threads


def finish(stop, threads):
    stop.set()
    for t in threads:
        t.join()


def test_ok_response_is_returned_and_removed(instance):
    stop, threads = run(instance)
    try:
        res = reaper.call("ping", timeout=2)
    finally:
        finish(stop, threads)
    assert res["status"] == reaper.OK and res["result"] == {"cmd": "ping"}
    assert os.listdir(instance / "res") == []


def test_request_never_taken_is_withdrawn_and_not_started(instance):
    stop, threads = run(instance, claim=False)
    try:
        res = reaper.call("track.add", timeout=0.3)
    finally:
        finish(stop, threads)
    assert res["status"] == reaper.NOT_STARTED
    assert os.listdir(instance / "req") == []  # withdrawn, so a late bridge can never run it


def test_claimed_request_without_response_is_uncertain(instance):
    stop, threads = run(instance, respond=False)
    try:
        res = reaper.call("track.add", timeout=0.3)
    finally:
        finish(stop, threads)
    assert res["status"] == reaper.UNCERTAIN
    assert "is running" in res["error"]


def test_slow_response_after_timeout_is_uncertain(instance):
    stop, threads = run(instance, delay=0.6)
    try:
        res = reaper.call("track.add", timeout=0.2)
    finally:
        finish(stop, threads)
    assert res["status"] == reaper.UNCERTAIN


def test_no_live_instance_is_an_error(instance):
    (instance / "heartbeat").unlink()
    with pytest.raises(reaper.BridgeError, match="no live REAPER instance"):
        reaper.call("ping", timeout=0.1)


def test_several_live_instances_need_a_choice(instance, tmp_path):
    other = tmp_path / "mps" / "instances" / "def"
    for sub in ("req", "work", "res", "tmp"):
        (other / sub).mkdir(parents=True)
    (other / "info.json").write_text("{}")
    (other / "heartbeat").write_text("1")
    (instance / "heartbeat").write_text("1")
    with pytest.raises(reaper.BridgeError, match="several live"):
        reaper.find_instance()
    assert reaper.find_instance("def").id == "def"
