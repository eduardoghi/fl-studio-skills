"""Proof of concept 10a. Load a Kontakt instrument into a new Kontakt instance and save its state.

Opens a new project tab, adds Kontakt, opens its window, opens the KONTAKT menu with a real click (Qt ignored posted
clicks on it in REAPER), picks Load with a posted click, types the .nki path in the file dialog, waits for the
instrument to settle and saves the plugin state by its SHA-256. The tab is closed without saving afterwards.

Usage: uv run python poc/p10_default_state.py <instrument.nki> <state folder> <label> <watched param index>
"""

import hashlib
import json
import sys
import time
from pathlib import Path

from mps import reaper, windows

MENU, LOAD = (226, 75), (51, 140)  # in the REAPER window holding Kontakt, measured from a capture
nki, folder, label, param = sys.argv[1], Path(sys.argv[2]), sys.argv[3], int(sys.argv[4])


def ok(res):
    if res["status"] != reaper.OK:
        raise SystemExit(json.dumps(res, indent=1))
    return res["result"]


ok(reaper.call("project.new_tab"))
track = ok(reaper.call("track.add", {"name": "state capture"}))["guid"]
ok(reaper.call("fx.add", {"track": track, "name": "VST3:Kontakt 8", "position": 0}, timeout=60))
ok(reaper.call("fx.show", {"track": track, "fx": 0}))
time.sleep(2)
h = next(w for w in windows.find("Kontakt 8 (Native") if "state capture" in windows._text(w))
windows.real_click(h, *MENU)
time.sleep(1)
windows.click(h, *LOAD)
time.sleep(2)
dialog = next(d for d in windows.dialogs() if d["title"] == "Load")
windows.fill_file_dialog(dialog, nki)
start, last, text = time.monotonic(), None, ""
while time.monotonic() - start < 90:
    rows = ok(reaper.call("fx.params", {"track": track, "fx": 0}, timeout=60))["params"]
    text = next((r["text"] for r in rows if r["index"] == param), "")
    if text and text == last:
        break
    last = text
    time.sleep(1)
time.sleep(2)
chunk = ok(reaper.call("fx.state_get", {"track": track, "fx": 0}, timeout=60))["chunk"]
digest = hashlib.sha256(chunk.encode("ascii")).hexdigest()
folder.mkdir(parents=True, exist_ok=True)
(folder / f"{digest}.b64").write_text(chunk, encoding="ascii")
record = {"label": label, "sha256": digest, "length": len(chunk), "instrument": nki, "watched_param_text": text}
(folder / f"{label}.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
ok(reaper.call("fx.show", {"track": track, "fx": 0, "show": False}))
project = ok(reaper.call("ping"))["project"]
print(json.dumps(record, indent=1))
