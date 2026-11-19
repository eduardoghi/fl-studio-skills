"""envelope.set against a live REAPER. A request that fails validation must leave the envelope as it was.

Runs only when the environment variable MPS_LIVE_REAPER is set and one REAPER instance with the bridge is running (or
MPS_REAPER_INSTANCE names one). Each test works in a new project tab and closes it, and reads the envelope back from
the saved project file, so no extra bridge command is needed.
"""

import os
import re

import pytest

from mps import reaper

pytestmark = pytest.mark.skipif(not os.environ.get("MPS_LIVE_REAPER"), reason="needs a live REAPER (MPS_LIVE_REAPER)")


def call(cmd, args=None):
    r = reaper.call(cmd, args or {}, timeout=60)
    return r


def ok(cmd, args=None):
    r = call(cmd, args)
    assert r["status"] == "ok", r
    return r["result"]


def envelope_points(path, block):
    """PT lines of the first <block ... > section of a saved project."""
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    m = re.search(r"<" + block + r"\b(.*?)\n\s*>", text, re.DOTALL)
    return [] if m is None else re.findall(r"^\s*PT .*$", m.group(1), re.MULTILINE)


@pytest.fixture
def project(tmp_path):
    ok("project.new_tab")
    path = tmp_path / "envelope.rpp"
    yield path
    ok("project.save", {"path": str(path)})
    ok("project.close_tab", {"path": str(path)})


BAD_POINTS = [
    [{"time": 1.0, "value": 0.0}, {"time": 2.0, "value": "loud"}],
    [{"time": 1.0, "value": 0.0}, {"time": -1.0, "value": 0.0}],
    [{"time": 1.0, "value": 0.0}, {"time": 2.0, "value": 12.0}],
    [{"time": 1.0, "value": 0.0, "shape": 9}],
    [{"time": 1.0, "value": 0.0}, "not a point"],
]


@pytest.mark.parametrize("bad", BAD_POINTS)
def test_invalid_volume_request_keeps_the_envelope(project, bad):
    track = ok("track.add", {"name": "env"})["guid"]
    ok("envelope.set", {"track": track, "points": [{"time": 0.5, "value": 0.0}, {"time": 1.5, "value": -6.0}]})
    ok("project.save", {"path": str(project)})
    before = envelope_points(project, "VOLENV2")
    assert len(before) == 2
    r = call("envelope.set", {"track": track, "points": bad})
    assert r["status"] == "error"
    ok("project.save", {"path": str(project)})
    assert envelope_points(project, "VOLENV2") == before


def test_invalid_parameter_request_keeps_the_envelope(project):
    track = ok("track.add", {"name": "env"})["guid"]
    fx = ok("fx.add", {"track": track, "name": "JS:Utility/volume"})["guid"]
    ok("envelope.set", {"track": track, "fx": fx, "param": 0, "points": [{"time": 0.5, "value": 0.25},
                                                                         {"time": 1.5, "value": 0.75}]})
    ok("project.save", {"path": str(project)})
    before = envelope_points(project, "PARMENV")
    assert len(before) == 2
    for args in ({"param": 0, "points": [{"time": 1.0, "value": 1.5}]},
                 {"param": 9999, "points": [{"time": 1.0, "value": 0.5}]},
                 {"param": 0.5, "points": [{"time": 1.0, "value": 0.5}]}):
        r = call("envelope.set", {"track": track, "fx": fx, **args})
        assert r["status"] == "error", args
    ok("project.save", {"path": str(project)})
    assert envelope_points(project, "PARMENV") == before


def test_invalid_request_creates_no_parameter_envelope(project):
    track = ok("track.add", {"name": "env"})["guid"]
    fx = ok("fx.add", {"track": track, "name": "JS:Utility/volume"})["guid"]
    r = call("envelope.set", {"track": track, "fx": fx, "param": 0, "points": [{"time": 1.0, "value": 2.0}]})
    assert r["status"] == "error"
    ok("project.save", {"path": str(project)})
    assert envelope_points(project, "PARMENV") == []
