"""How `mps render` combines the render process's outcome, the file checks and the render standard."""

import json

import pytest

from mps import audio, cli, render

STANDARD_RPP = """<REAPER_PROJECT 0.1 "7.86/x64" 1794772900
  RENDER_FILE "{wav}"
  RENDER_FMT 0 2 44100
  RENDER_1X 0 0
  RENDER_RANGE 0 0 2 1 500
  RENDER_DITHER 0
  RENDER_NORMALIZE 262144 0 0 0 0 1 1
  SAMPLERATE 44100 1 0
  <RENDER_CFG
    ZXZhdyAAAQ==
  >
>
"""


@pytest.fixture
def fake_render(monkeypatch, tmp_path):
    out = tmp_path / "out.wav"

    def run(returncode, file_ok=True, extra=(), rpp_text=None, exists=False):
        if exists:
            out.write_bytes(b"")
        project = tmp_path / "p.rpp"
        if rpp_text is not None:
            project.write_text(rpp_text.format(wav=str(out).replace("\\", "\\\\")), encoding="utf-8")

        def fake_project(project, timeout):
            out.write_bytes(b"")
            return {"ok": True, "returncode": returncode, "started": 0.0}

        monkeypatch.setattr(render, "render_project", fake_project)
        monkeypatch.setattr(audio, "check", lambda path, **kw: {"ok": file_ok, "failures": [] if file_ok else ["x"]})
        return cli.main(["render", str(project), "--expect", str(out), *extra])

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


def test_existing_target_is_refused_without_overwrite(fake_render, capsys):
    assert fake_render(0, exists=True) == 1
    r = result(capsys)
    assert "existing" in r and "returncode" not in r


def test_existing_target_is_replaced_with_overwrite(fake_render, capsys):
    assert fake_render(0, exists=True, extra=["--overwrite"]) == 0


def test_standard_project_passes_and_writes_a_manifest(fake_render, capsys, tmp_path):
    assert fake_render(0, rpp_text=STANDARD_RPP) == 0
    r = result(capsys)
    assert r["standard"]["ok"] and r["expected_seconds"] == 2.5
    assert json.loads((tmp_path / "out.render.json").read_text(encoding="utf-8"))["settings"]["format"] == "wav32f"


def test_nonstandard_project_fails_unless_allowed(fake_render, capsys):
    wav24 = STANDARD_RPP.replace("ZXZhdyAAAQ==", "ZXZhdxgAAQ==")
    assert fake_render(0, rpp_text=wav24) == 1
    r = result(capsys)
    assert not r["standard"]["ok"] and "wav24" in r["standard"]["deviations"][0]
    assert fake_render(0, rpp_text=wav24, extra=["--allow-nonstandard", "--overwrite"]) == 0
