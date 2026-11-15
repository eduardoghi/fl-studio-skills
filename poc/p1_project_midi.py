"""Proof of concept 1. Create a project through the API, write MIDI in bulk and read it back.

Opens a new project tab (the tab in use is left alone), sets the tempo and sample rate, adds a track and a MIDI item,
writes notes with different channels, velocities and lengths plus controllers and pitch bend, reads them back and
compares every field, then saves the project and checks the saved file mentions the notes. REAPER keeps MIDI
positions as whole ticks of the item (960 per quarter note by default), so times are compared within half a tick.

Usage: uv run python poc/p1_project_midi.py <folder for the project>
"""

import json
import sys
from pathlib import Path

from mps import reaper


def ok(res):
    if res["status"] != reaper.OK:
        raise SystemExit(json.dumps(res, indent=1))
    return res["result"]


folder = Path(sys.argv[1])
folder.mkdir(parents=True, exist_ok=True)
rpp = folder / "p1_project_midi.rpp"
ok(reaper.call("project.new_tab"))
ok(reaper.call("project.set_tempo", {"bpm": 104.4858, "srate": 44100}))
track = ok(reaper.call("track.add", {"name": "synthetic"}))
item = ok(reaper.call("item.add_midi", {"track": track["guid"], "start_qn": 0, "end_qn": 8}))
notes = [
    {
        "start_qn": 0.0 + 0.5 * k,
        "end_qn": 0.0 + 0.5 * k + 0.37 + 0.01 * k,
        "chan": k % 6,
        "pitch": 52 + k,
        "vel": 20 + 7 * k,
    }
    for k in range(12)
]
notes.append({"start_qn": 6.0, "end_qn": 7.5, "chan": 15, "pitch": 40, "vel": 127})
ccs = [
    {"qn": 0.0, "status": 0xB0, "chan": 0, "msg2": 1, "msg3": 64},
    {"qn": 1.0, "status": 0xB0, "chan": 3, "msg2": 11, "msg3": 100},
    {"qn": 2.0, "status": 0xE0, "chan": 2, "msg2": 0, "msg3": 96},
    {"qn": 3.0, "status": 0xC0, "chan": 0, "msg2": 5, "msg3": 0},
]
back = ok(reaper.call("midi.write", {"item": item["guid"], "notes": notes, "ccs": ccs, "replace": True}))
again = ok(reaper.call("midi.read", {"item": item["guid"]}))
problems = []
if len(back["notes"]) != len(notes):
    problems.append(f"{len(back['notes'])} notes read back, {len(notes)} written")
got = sorted(back["notes"], key=lambda n: (n["start_qn"], n["pitch"]))
for w, g in zip(sorted(notes, key=lambda n: (n["start_qn"], n["pitch"])), got):
    for key in ("chan", "pitch", "vel"):
        if w[key] != g[key]:
            problems.append(f"note {w['pitch']}: {key} {g[key]} != {w[key]}")
    for key in ("start_qn", "end_qn"):
        if abs(w[key] - g[key]) > 0.5 / 960 + 1e-9:
            problems.append(f"note {w['pitch']}: {key} {g[key]} != {w[key]}")
if len(back["ccs"]) != len(ccs):
    problems.append(f"{len(back['ccs'])} controller events read back, {len(ccs)} written")
for w, g in zip(ccs, sorted(back["ccs"], key=lambda c: c["qn"])):
    if (w["status"], w["chan"], w["msg2"], w["msg3"]) != (g["status"], g["chan"], g["msg2"], g["msg3"]):
        problems.append(f"event at {w['qn']}: {g} != {w}")
if again != back:
    problems.append("a second read differs from the read after writing")
saved = ok(reaper.call("project.save", {"path": str(rpp)}))
text = rpp.read_text(encoding="utf-8", errors="replace")
info = ok(reaper.call("project.info"))
report = {
    "project": saved["project"],
    "dirty_after_save": saved["dirty"],
    "notes_written": len(notes),
    "notes_read": len(back["notes"]),
    "events_written": len(ccs),
    "events_read": len(back["ccs"]),
    "ticks_per_qn": round(back["notes"][1]["start_ppq"] / 0.5),
    "problems": problems,
    "rpp_has_midi_source": "<SOURCE MIDI" in text,
    "rpp_bytes": len(text),
    "tracks_in_project": [t["name"] for t in info["tracks"]],
    "bpm": info["bpm"],
    "srate": info["srate"],
}
report["closed_tabs"] = ok(reaper.call("project.close_tab", {"path": saved["project"]}))["closed"]
print(json.dumps(report, indent=1))
sys.exit(1 if problems else 0)
