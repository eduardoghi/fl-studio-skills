"""State checks with a fake bridge, and the judgement of renders against natural variation."""

import hashlib
import json

import numpy as np
import pytest
import soundfile as sf

from mps import audio, reaper, state


class FakeBridge:
    """Answers the commands state.py sends, with parameter text that can lag or stay empty."""

    def __init__(self, texts_by_read, length=100):
        self.texts_by_read = texts_by_read
        self.reads = 0
        self.length = length
        self.calls = []

    def __call__(self, cmd, args, instance=None, timeout=10):
        self.calls.append(cmd)
        if cmd == "fx.params":
            texts = self.texts_by_read[min(self.reads, len(self.texts_by_read) - 1)]
            self.reads += 1
            params = [{"index": i, "name": f"p{i}", "ident": str(i), "text": t} for i, t in enumerate(texts)]
            return {"status": reaper.OK, "result": {"params": params}}
        if cmd == "fx.state_get":
            return {"status": reaper.OK, "result": {"chunk": "QUJD", "length": self.length, "fx": {"name": "X"}}}
        if cmd in ("fx.state_set", "fx.restore_fresh"):
            return {"status": reaper.OK, "result": {"fx": {"guid": "{NEW}"}, "identical": False}}
        raise AssertionError(cmd)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def test_settle_waits_for_the_same_text_twice(monkeypatch):
    fake = FakeBridge([["", ""], ["1", "2"], ["1", "3"], ["1", "3"]])
    monkeypatch.setattr(reaper, "call", fake)
    c = Clock()
    got = state.settle("{T}", 0, sleep=c.sleep, clock=c)
    assert got["text_available"] and [p["text"] for p in got["params"]] == ["1", "3"]


def test_settle_accepts_empty_text_once_the_state_length_is_stable(monkeypatch):
    fake = FakeBridge([["", ""]])
    monkeypatch.setattr(reaper, "call", fake)
    c = Clock()
    got = state.settle("{T}", 0, sleep=c.sleep, clock=c)
    assert not got["text_available"] and got["seconds"] >= state.TEXT_GRACE_S


def test_settle_gives_up(monkeypatch):
    fake = FakeBridge([[str(i)] for i in range(100)])
    monkeypatch.setattr(reaper, "call", fake)
    c = Clock()
    with pytest.raises(state.StateError):
        state.settle("{T}", 0, limit=5, sleep=c.sleep, clock=c)


def test_compare_params_reports_changed_text():
    saved = [{"index": 0, "name": "a", "text": "0 %"}, {"index": 1, "name": "b", "text": "x"}]
    now = [{"index": 0, "name": "a", "text": "100 %"}, {"index": 1, "name": "b", "text": "x"}]
    got = state.compare_params(saved, now)
    assert not got["ok"] and got["differ"] == [{"index": 0, "name": "a", "saved": "0 %", "now": "100 %"}]


def _stored(tmp_path, texts):
    chunk = "QUJD"
    sha = hashlib.sha256(chunk.encode()).hexdigest()
    f = tmp_path / f"{sha}.b64"
    f.write_text(chunk, encoding="ascii")
    params = [{"index": i, "name": f"p{i}", "ident": str(i), "text": t} for i, t in enumerate(texts)]
    (tmp_path / f"{sha}.json").write_text(json.dumps({"params": params, "text_available": True}), encoding="utf-8")
    return f


def test_restore_refuses_a_file_that_changed(tmp_path, monkeypatch):
    f = _stored(tmp_path, ["1"])
    f.write_text("QUJE", encoding="ascii")
    monkeypatch.setattr(reaper, "call", FakeBridge([["1"]]))
    got = state.restore("{T}", 0, f)
    assert not got["ok"] and not got["integrity"]["ok"]


def test_restore_fresh_checks_configuration(tmp_path, monkeypatch):
    f = _stored(tmp_path, ["1", "2"])
    fake = FakeBridge([["1", "2"]])
    monkeypatch.setattr(reaper, "call", fake)
    monkeypatch.setattr(state.time, "sleep", lambda s: None)
    got = state.restore("{T}", 0, f, name="VST3i:X")
    assert got["ok"] and got["mode"] == "fresh instance" and "fx.restore_fresh" in fake.calls


def test_restore_with_different_text_fails_level_2(tmp_path, monkeypatch):
    f = _stored(tmp_path, ["1", "2"])
    monkeypatch.setattr(reaper, "call", FakeBridge([["1", "9"]]))
    monkeypatch.setattr(state.time, "sleep", lambda s: None)
    got = state.restore("{T}", 0, f)
    assert not got["ok"] and got["configuration"]["differ"][0]["now"] == "9"


def _wav(path, x):
    sf.write(path, np.stack([x, x], 1), 44100, subtype="FLOAT")
    return path


def test_variation_verdicts(tmp_path):
    rng = np.random.default_rng(1)
    base = rng.standard_normal(44100) * 0.1
    a = _wav(tmp_path / "a.wav", base)
    b = _wav(tmp_path / "b.wav", base)
    c = base.copy()
    c[1000:2000] += rng.standard_normal(1000) * 0.05
    c = _wav(tmp_path / "c.wav", c)
    small = _wav(tmp_path / "small.wav", base + rng.standard_normal(44100) * 0.001)
    big = _wav(tmp_path / "big.wav", base + rng.standard_normal(44100) * 0.1)

    same = audio.variation([a, b], [_wav(tmp_path / "d.wav", base), small])
    assert same["natural_residual_db"] == float("-inf")
    assert [x["verdict"] for x in same["candidates"]] == ["identical", "outside"]

    varied = audio.variation([a, c], [small, big])
    assert [x["verdict"] for x in varied["candidates"]] == ["within", "outside"]

    single = audio.variation([a], [small])
    assert single["candidates"][0]["verdict"] == "different, variation unknown"
