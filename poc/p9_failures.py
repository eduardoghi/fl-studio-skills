"""Proof of concept 9. How the bridge and client behave when things go wrong.

1. A command slower than the client's timeout (adding Kontakt with a 0.1 s timeout). If the bridge had claimed the
   request the outcome must be UNCERTAIN, and if not, NOT_STARTED with the request withdrawn.
2. A request whose expiry has passed, written straight into req/. The bridge must refuse it without running it.
3. A plugin's modal dialog (Kontakt's Instrument Options), to see whether it stops the bridge.
4. A modal dialog of REAPER itself, a message box opened by another script through `reaper -nonewinst`. It holds
   REAPER's main thread, so a request must come back NOT_STARTED, and the bridge must recover once it closes.
Usage: uv run python poc/p9_failures.py <track guid>
"""

import json
import os
import subprocess
import sys
import time
import uuid

from mps import reaper, render, windows

track = sys.argv[1]
report = {}

# 1. slower than the timeout
before = reaper.call("project.info")["result"]["tracks"][0]["fx"]
slow = reaper.call("fx.add", {"track": track, "name": "VST3:Kontakt 8", "position": 5}, timeout=0.1)
time.sleep(15)
inst = reaper.find_instance()
late = sorted(os.listdir(inst.path / "res"))
after = reaper.call("project.info")["result"]["tracks"][0]["fx"]
report["slow_command"] = {
    "status": slow["status"],
    "error": slow.get("error"),
    "late_responses_in_res": len(late),
    "fx_before": len(before),
    "fx_after": len(after),
}
for name in late:
    (inst.path / "res" / name).unlink()
if len(after) > len(before):  # undo the extra instance, with an explicit index
    reaper.call("fx.delete", {"track": track, "fx": len(after) - 1})

# 2. expired request
rid = uuid.uuid4().hex
req = {
    "id": rid,
    "cmd": "track.add",
    "args": {"name": "must not exist"},
    "created": time.time() - 60,
    "expires": time.time() - 30,
}
tmp = inst.path / "tmp" / f"{rid}.client"
tmp.write_text(json.dumps(req), encoding="utf-8")
os.rename(tmp, inst.path / "req" / f"{rid}.json")
res = inst.path / "res" / f"{rid}.json"
for _ in range(100):
    if res.exists():
        break
    time.sleep(0.05)
body = json.loads(res.read_text(encoding="utf-8"))
res.unlink()
names = [t["name"] for t in reaper.call("project.info")["result"]["tracks"]]
report["expired_request"] = {
    "status": body["status"],
    "error": body.get("error"),
    "track_was_added": "must not exist" in names,
}

# 3. modal dialog
reaper.call("fx.show", {"track": track, "fx": 0})
time.sleep(1.5)
h = windows.find("Kontakt 8 (Native")[0]
windows.click(h, 395, 113)  # gear icon of the instrument header, opens Instrument Options
time.sleep(2)
dialogs = [d for d in windows.dialogs() if d["title"] == "Instrument Options"]
blocked = reaper.call("ping", timeout=4) if dialogs else None
closed = windows.press(dialogs[0], "Cancel") if dialogs else False
if dialogs and not closed:
    windows.user32.PostMessageW(dialogs[0]["hwnd"], 0x0010, 0, 0)
time.sleep(2)
recovered = reaper.call("ping", timeout=10)
reaper.call("fx.show", {"track": track, "fx": 0, "show": False})
report["modal_dialog"] = {
    "dialog_opened": bool(dialogs),
    "buttons": dialogs[0]["buttons"] if dialogs else None,
    "status_while_open": blocked and blocked["status"],
    "error_while_open": blocked and blocked.get("error"),
    "status_after_close": recovered["status"],
}
# 4. a modal dialog of REAPER itself
script = inst.path / "tmp" / "mps_test_messagebox.lua"
script.write_text('reaper.ShowMessageBox("mps test dialog, closes by itself", "mps test", 0)', encoding="utf-8")
subprocess.Popen([str(render.reaper_exe()), "-nonewinst", str(script)])
time.sleep(3)
boxes = [d for d in windows.dialogs() if d["title"] == "mps test"]
held = reaper.call("ping", timeout=4)
pressed = windows.press(boxes[0], "OK") if boxes else False
time.sleep(2)
back = reaper.call("ping", timeout=10)
report["reaper_dialog"] = {
    "dialog_opened": bool(boxes),
    "status_while_open": held["status"],
    "error_while_open": held.get("error"),
    "pressed_ok": pressed,
    "status_after_close": back["status"],
}
print(json.dumps(report, indent=1))
