"""Proof of concept 3, analysis. Tell from the audio which string played each note and whether a pick was heard.

For each event of the layout JSON written by p3_channels.py:
- timbre, the levels of harmonics 1 to 8 relative to the fundamental over 50 to 600 ms after the start. A fretted
  note sounds darker than the same pitch on a thinner, open string, so the profiles of one pitch played on different
  strings differ, while repeats on one string stay close (the control)
- pick, how far the energy above 3 kHz rises in the 30 ms after the start compared with the 30 ms before. A hammer-on
  or pull-off rises little, a picked note a lot

Usage: uv run python poc/p3_analyse.py <layout.json> <render.wav>
"""

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

layout = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
x, sr = sf.read(sys.argv[2], dtype="float64", always_2d=True)
m = x.mean(1)
spq = 60 / layout["bpm"]


def harmonics(t, pitch):
    seg = m[int((t + 0.05) * sr) : int((t + 0.6) * sr)]
    spec = np.abs(np.fft.rfft(seg * np.hanning(seg.size)))
    f = np.fft.rfftfreq(seg.size, 1 / sr)
    f0 = 440 * 2 ** ((pitch - 69) / 12)
    lv = []
    for k in range(1, 9):
        band = (f > k * f0 * 0.97) & (f < k * f0 * 1.03)
        lv.append(20 * np.log10(spec[band].max() + 1e-12))
    return np.array(lv) - lv[0]


def pick(t):
    spec_hi = np.fft.rfftfreq(256, 1 / sr) > 3000

    def energy(a, b):
        seg = m[int(a * sr) : int(b * sr)]
        frames = [seg[i : i + 256] for i in range(0, len(seg) - 256, 64)]
        return np.mean([np.sum(np.abs(np.fft.rfft(fr * np.hanning(256)))[spec_hi] ** 2) for fr in frames]) + 1e-12

    before = energy(t - 0.03, t)
    if 10 * np.log10(before) < -60:  # nothing sounding before: a rise from silence says nothing about the pick
        return None
    return 10 * np.log10(energy(t, t + 0.03) / before)


rows = []
for e in layout["events"]:
    t = e["qn"] * spq
    h = harmonics(t, e["pitch"])[1:]
    p = pick(t)
    seg = m[int((t + 0.05) * sr) : int((t + 0.6) * sr)]
    rows.append(
        {
            **e,
            "time": round(t, 3),
            "harmonics_db": [round(v, 1) for v in h],
            "mean_harmonic_db": round(float(np.mean(h)), 1),
            "level_db": round(20 * np.log10(np.sqrt(np.mean(seg**2)) + 1e-12), 1),
            "pick_rise_db": None if p is None else round(p, 1),
        }
    )
string = [r for r in rows if r["pitch"] == 64]
ctrl = np.array([r["harmonics_db"] for r in string if "control" in r["tag"]])
spread_ctrl = float(np.mean(np.abs(ctrl - ctrl.mean(0))))
per_channel = {
    r["tag"]: round(float(np.mean(np.abs(np.array(r["harmonics_db"]) - ctrl.mean(0)))), 1)
    for r in string
    if "control" not in r["tag"]
}
print(
    json.dumps(
        {"rows": rows, "control_spread_db": round(spread_ctrl, 1), "distance_from_control_db": per_channel}, indent=1
    )
)
