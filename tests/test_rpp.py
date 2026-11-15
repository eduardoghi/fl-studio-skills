"""Reading render settings and plugins from saved projects, on lines copied from REAPER 7.86 projects."""

from pathlib import Path

from mps import render, rpp

PROJECT = """<REAPER_PROJECT 0.1 "7.86/x64" 1794772900
  RENDER_FILE "V:\\\\renders\\\\take.wav"
  RENDER_FMT 0 2 44100
  RENDER_1X 0 0
  RENDER_RANGE 0 0 2 1 500
  RENDER_RESAMPLE 3 0 1
  RENDER_QDELAY 1
  RENDER_STEMS 1048576
  RENDER_DITHER 0
  RENDER_NORMALIZE 262144 0 0 0 0 1 1
  SAMPLERATE 44100 1 0
  <RENDER_CFG
    ZXZhdyAAAQ==
  >
  <TRACK {A}
    NAME "guitar"
    <FXCHAIN
      <VST "VST3i: Kontakt 8 (Native Instruments) (64 out)" "Kontakt 8 Portable.vst3" 0 "" 952745140{56} ""
      >
      <JS synthesis/tonegenerator ""
      >
    >
  >
>
"""


def test_render_settings():
    s = rpp.render_settings(PROJECT)
    assert s["format"] == "wav32f"
    assert (s["channels"], s["srate"], s["project_srate"]) == (2, 44100, 44100)
    assert (s["bounds"], s["start"], s["end"], s["tail_flag"], s["tail_ms"]) == (0, 0, 2, 1, 500)
    assert (s["settings"], s["fx_delay"], s["dither"], s["normalize"]) == (1048576, 1, 0, 262144)
    assert s["speed_label"] == "offline, full speed"
    assert s["file"] == "V:\\\\renders\\\\take.wav"


def test_plugins():
    assert rpp.plugins(PROJECT) == [
        {"type": "VST", "name": "VST3i: Kontakt 8 (Native Instruments) (64 out)", "file": "Kontakt 8 Portable.vst3"},
        {"type": "JS", "name": "synthesis/tonegenerator", "file": None},
    ]


def test_unknown_speed_and_format_are_reported_raw():
    s = rpp.render_settings(PROJECT.replace("RENDER_1X 0 0", "RENDER_1X 2 0").replace("ZXZhdyAAAQ==", "bDNwbQ=="))
    assert s["speed_label"] == "not mapped" and s["format"] == "bDNwbQ=="
    assert any("speed" in d for d in render.deviations(s))


def test_standard_deviations():
    s = rpp.render_settings(PROJECT)
    assert render.deviations(s) == []
    assert render.expected_seconds(s) == 2.5
    loud = dict(s, normalize=1, dither=1, srate=48000)
    found = render.deviations(loud)
    assert any("postprocessing" in d for d in found) and any("dither" in d for d in found)
    assert any("srate" in d for d in found)


def test_targets():
    assert [str(p) for p in render.targets({"file": "V:/r/take.wav", "pattern": "", "format": "wav32f"})] == [
        str(Path("V:/r/take.wav"))
    ]
    assert render.targets({"file": "V:/r", "pattern": "$project", "format": "wav32f"}) == []


def test_instruments_need_a_load_delay():
    s = rpp.render_settings(PROJECT)
    plugins = rpp.plugins(PROJECT)
    assert render.deviations(s, plugins) == []
    no_delay = dict(s, fx_delay=0)
    assert any("fx_delay" in d for d in render.deviations(no_delay, plugins))
    cockos = [{"type": "VST", "name": "VSTi: ReaSynth (Cockos)", "file": "reasynth.dll"}]
    assert render.deviations(no_delay, cockos) == []
