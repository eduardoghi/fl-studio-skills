"""How `mps render` combines the render process's outcome with the file checks."""

import json

import pytest

from mps import audio, cli, render


@pytest.fixture
def fake_render(monkeypatch, tmp_path):
    out = tmp_path / "out.wav"
    out.write_bytes(b"")

    def run(returncode, file_ok=True):
        monkeypatch.setattr(
            render,
            "render_project",
            lambda project, timeout: {"ok": True, "returncode": returncode, "started": 0.0},
        )
        monkeypatch.setattr(audio, "check", lambda path, **kw: {"ok": file_ok, "failures": [] if file_ok else ["x"]})
        return cli.main(["render", "p.rpp", "--expect", str(out)])

    return run


def result(capsys):
    return json.loads(capsys.readouterr().out)


def test_normal_exit_with_good_files_is_ok(fake_render, capsys):
    assert fake_render(0) == 0
    r = result(capsys)
    assert r["ok"] and r["files_ok"] and not r["abnormal_exit"]


def test_abnormal_exit_with_good_files_is_not_ok(fake_render, capsys):
    assert fake_render(0xC000000D) == 1
    r = result(capsys)
    assert r["files_ok"] and r["abnormal_exit"] and not r["ok"]


def test_bad_files_are_not_ok(fake_render, capsys):
    assert fake_render(0, file_ok=False) == 1
    r = result(capsys)
    assert not r["files_ok"] and not r["ok"]
