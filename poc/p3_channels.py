"""Proof of concept 3. Write a test part for Channel-Based Strings, set the render explicitly and save the project.

Every event sits at a known quarter note, listed in the JSON written next to the project, so the analysis can find
each one in the render. Channels are 0-based here (0 is MIDI channel 1).

- String choice, with E4 (64) on channels 0 to 3, then E4 four times on channel 0 as the control
- Legato, with 60 then 62 overlapping on the same channel, the same pair on two channels, and the pair without
  overlap
- E2 (40) on channel 0, a note the highest string can't play

Usage: uv run python poc/p3_channels.py <track guid> <project.rpp> <render folder> <name>
"""

import json
import sys
from pathlib import Path

from mps import reaper

BPM = 104.4858
track, rpp, render_dir, name = sys.argv[1], Path(sys.argv[2]), sys.argv[3], sys.argv[4]


def ok(res):
    if res["status"] != reaper.OK:
        raise SystemExit(json.dumps(res, indent=1))
    return res["result"]


notes, events = [], []


def note(qn, length, pitch, chan, vel=100, tag=""):
    notes.append({"start_qn": qn, "end_qn": qn + length, "pitch": pitch, "chan": chan, "vel": vel})
    events.append({"qn": qn, "pitch": pitch, "chan": chan, "tag": tag})


for k in range(4):
    note(2 * k, 1.5, 64, k, tag=f"E4 channel {k + 1}")
for k in range(4):
    note(8 + 2 * k, 1.5, 64, 0, tag="E4 channel 1, control")
note(16, 1.0, 60, 1, tag="legato same channel, first")
note(16.75, 1.0, 62, 1, tag="legato same channel, second")
note(20, 1.0, 60, 1, tag="legato two channels, first")
note(20.75, 1.0, 62, 2, tag="legato two channels, second")
note(24, 0.7, 60, 1, tag="no overlap, first")
note(24.75, 1.0, 62, 1, tag="no overlap, second")
note(28, 1.5, 40, 0, tag="E2 on channel 1")
end_qn = 32
item = ok(reaper.call("item.add_midi", {"track": track, "start_qn": 0, "end_qn": end_qn}))
back = ok(reaper.call("midi.write", {"item": item["guid"], "notes": notes, "replace": True}))
seconds = end_qn * 60 / BPM
conf = ok(
    reaper.call(
        "render.configure",
        {
            "directory": render_dir,
            "pattern": name,
            "format": "wav24",
            "start": 0,
            "end": seconds,
            "srate": 44100,
            "channels": 2,
        },
    )
)
saved = ok(reaper.call("project.save", {"path": str(rpp)}, timeout=60))
layout = {
    "bpm": BPM,
    "seconds": seconds,
    "events": events,
    "render": conf,
    "project": saved["project"],
    "notes_read_back": len(back["notes"]),
}
rpp.with_suffix(".json").write_text(json.dumps(layout, indent=1), encoding="utf-8")
print(
    json.dumps(
        {"targets": conf["targets"], "seconds": seconds, "notes": len(back["notes"]), "project": saved["project"]},
        indent=1,
    )
)
