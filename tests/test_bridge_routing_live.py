"""Folders, colors, sends, track order, markers and the pre-FX volume envelope against a live REAPER.

Runs only with MPS_LIVE_REAPER set, like test_bridge_envelope_live.py, in a new project tab that is closed after.
"""

import os
import re

import pytest

from mps import reaper

pytestmark = pytest.mark.skipif(not os.environ.get("MPS_LIVE_REAPER"), reason="needs a live REAPER (MPS_LIVE_REAPER)")


def call(cmd, args=None):
    return reaper.call(cmd, args or {}, timeout=60)


def ok(cmd, args=None):
    r = call(cmd, args)
    assert r["status"] == "ok", r
    return r["result"]


@pytest.fixture
def project(tmp_path):
    ok("project.new_tab")
    path = tmp_path / "routing.rpp"
    yield path
    ok("project.save", {"path": str(path)})
    ok("project.close_tab", {"path": str(path)})


def test_folder_color_send_and_order(project):
    folder = ok("track.add", {"name": "bus"})["guid"]
    child = ok("track.add", {"name": "child"})["guid"]
    ret = ok("track.add", {"name": "return"})["guid"]
    assert ok("track.set", {"track": folder, "folder_depth": 1, "color": [10, 20, 30]})["color"] == [10, 20, 30]
    ok("track.set", {"track": child, "folder_depth": -1})
    assert ok("track.set", {"track": ret, "main_send": False})["main_send"] is False
    send = ok("send.add", {"track": child, "dest": ret, "volume_db": -6, "mode": "pre_fx"})
    assert send["mode"] == 1 and abs(send["volume_db"] + 6) < 1e-6 and send["dest"] == ret
    assert ok("track.move", {"track": ret, "index": 0})["index"] == 0
    info = ok("project.info")
    names = [t["name"] for t in info["tracks"]]
    assert names == ["return", "bus", "child"]
    assert [t["folder_depth"] for t in info["tracks"]] == [0, 1, -1]


def test_send_from_a_channel_pair(project):
    src = ok("track.add", {"name": "multi"})["guid"]
    dst = ok("track.add", {"name": "out 3/4"})["guid"]
    ok("track.set", {"track": src, "channels": 4})
    send = ok("send.add", {"track": src, "dest": dst, "mode": "post_fx", "src_channel": 2})
    assert send["src_channel"] == 2 and send["mode"] == 3
    assert call("send.add", {"track": src, "dest": dst, "src_channel": 3})["status"] == "error"


def test_bad_requests_change_nothing(project):
    a = ok("track.add", {"name": "a"})["guid"]
    for cmd, args in (("send.add", {"track": a, "dest": a}), ("track.set", {"track": a, "color": [1, 2]}),
                      ("track.set", {"track": a, "folder_depth": 2}), ("track.set", {"track": a, "channels": 3}),
                      ("send.add", {"track": a, "dest": a, "mode": "sideways"})):
        assert call(cmd, args)["status"] == "error", (cmd, args)
    t = ok("project.info")["tracks"][0]
    assert t["sends"] == [] and t["color"] is None and t["folder_depth"] == 0 and t["channels"] == 2


def test_markers_and_regions(project):
    ok("marker.add", {"name": "A", "position": 9.8, "end": 41.9, "color": [0, 120, 200]})
    ok("marker.add", {"name": "pause", "position": 91.98})
    assert call("marker.add", {"name": "bad", "position": 5, "end": 4})["status"] == "error"
    marks = ok("project.info")["markers"]
    assert [(m["name"], m["region"]) for m in marks] == [("A", True), ("pause", False)]


def test_pre_fx_volume_envelope(project):
    t = ok("track.add", {"name": "feed"})["guid"]
    ok("envelope.set", {"track": t, "target": "volume_prefx", "points": [{"time": 0.5, "value": -10.0},
                                                                         {"time": 1.5, "value": 0.0}]})
    assert call("envelope.set", {"track": t, "target": "pan", "points": [{"time": 0, "value": 0}]})["status"] == "error"
    ok("project.save", {"path": str(project)})
    text = project.read_text(encoding="utf-8", errors="replace")
    block = re.search(r"<VOLENV\b(.*?)\n\s*>", text, re.DOTALL)
    assert block is not None and len(re.findall(r"^\s*PT ", block.group(1), re.MULTILINE)) == 2
    assert re.search(r"<VOLENV2\b", text) is None  # the post-FX volume envelope stays untouched
