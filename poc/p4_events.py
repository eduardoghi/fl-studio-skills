"""Proof of concept 4, analysis. Group repeated renders into sample-identical sets and find the notes that differ.

Usage: uv run python poc/p4_events.py <layout.json> <render.wav> [...]
"""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

layout = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
files = sys.argv[2:]
spq = 60 / layout["bpm"]
data = {f: sf.read(f, dtype="float64", always_2d=True)[0] for f in files}
groups = {}
for f, x in data.items():
    groups.setdefault(hashlib.sha256(x.tobytes()).hexdigest()[:12], []).append(f.split("\\")[-1])
sr = 44100
ref = data[files[0]]
per_event = []
for e in layout["events"]:
    t = e["qn"] * spq
    a, b = int(t * sr), int((t + 1.0) * sr)
    seg = ref[a:b]
    diffs = []
    for f in files[1:]:
        d = data[f][a:b] - seg
        diffs.append(round(20 * np.log10((np.sqrt(np.mean(d**2)) + 1e-12) / (np.sqrt(np.mean(seg**2)) + 1e-12)), 1))
    per_event.append({"tag": e["tag"], "residual_db_vs_first": diffs})
print(json.dumps({"identical_groups": groups, "events": per_event}, indent=1))
