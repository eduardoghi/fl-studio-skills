"""Tests for bin/instrument-calibrate with a synthetic instrument whose answer to velocity is known.

Run with `python3 -m unittest discover -s tests`. Needs numpy.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import numpy as np
except ImportError:
    raise unittest.SkipTest("instrument-calibrate needs numpy")

sys.path.insert(0, os.path.dirname(__file__))
from test_wav_check import RATE, wav_bytes

TOOL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "instrument-calibrate")
BPM = 120.0


def level_db(velocity):
    """The synthetic instrument's attack level, deliberately not linear in velocity."""
    return -45 + 33 * (velocity / 127) ** 0.6


def burst(level, seconds=0.3, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * RATE)) / RATE
    # White noise has an RMS of about 1, so the first 30 ms sit near the requested level.
    return 10 ** (level / 20) * rng.standard_normal(t.size) * np.exp(-t / 0.08)


def place(total_s, events):
    y = np.zeros(int(total_s * RATE))
    for start, sound in events:
        a = int(start * RATE)
        y[a : a + sound.size] += sound[: max(0, y.size - a)]
    return y


class InstrumentCalibrate(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def run_tool(self, *args):
        done = subprocess.run([sys.executable, TOOL, *map(str, args)], capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
        return done.stdout

    def write(self, name, y):
        path = self.dir / name
        path.write_bytes(wav_bytes(np.clip(y, -1, 1), fmt_tag=3, bits=32))
        return path

    def calibrate(self):
        layout = self.dir / "cal.json"
        self.run_tool("layout", layout, "--bpm", BPM, "--notes", "38", "--repeats", 2, "--gap", 1)
        doc = json.loads(layout.read_text())
        beat = 60 / BPM
        events = [(0.01 + h["start"] * beat, burst(level_db(h["velocity"]), seed=i)) for i, h in enumerate(doc["hits"])]
        render = self.write("render.wav", place(len(doc["hits"]) * beat + 1, events))
        curves = self.dir / "curves.json"
        self.run_tool("analyze", layout, render, curves)
        return json.loads(curves.read_text())

    def test_layout_spaces_hits_and_writes_fl_notes(self):
        layout = self.dir / "cal.json"
        out = self.run_tool(
            "layout", layout, "--bpm", BPM, "--notes", "36,49", "--long", "49", "--velocities", "40,100", "--repeats", 2
        )
        doc = json.loads(layout.read_text())
        self.assertEqual(len(doc["notes"]), 8)
        starts = [n["start"] for n in doc["notes"]]
        self.assertEqual(starts[:5], [0, 1.25, 2.5, 3.75, 5.0])  # the long note starts after four short gaps
        self.assertEqual(starts[5] - starts[4], 3.0)
        self.assertAlmostEqual(doc["notes"][0]["velocity"], 40 / 127, places=5)
        self.assertIn("8 hits", out)

    def test_analyze_recovers_a_curve_that_isnt_linear(self):
        result = self.calibrate()
        rows = result["curves"]["38"]
        self.assertAlmostEqual(result["render_offset_s"], 0.01, delta=0.003)
        # The decay pulls the 30 ms RMS a fixed amount under the burst's level, so the shape is what must match.
        offsets = [row["attack_db"] - level_db(row["velocity"]) for row in rows]
        self.assertLess(max(offsets) - min(offsets), 1.0)
        levels = [r["attack_db"] for r in rows]
        self.assertEqual(levels, sorted(levels))

    def test_velocity_inverts_the_curve_and_flags_the_floor(self):
        curves = self.dir / "curves.json"
        rows = [{"velocity": v, "attack_db": level_db(v)} for v in (1, 32, 64, 96, 127)]
        curves.write_text(json.dumps({"curves": {"38": rows}}))
        out = self.run_tool("velocity", curves, "--note", 38, "--anchor", 127, "--", -6, -60)
        lines = out.strip().splitlines()
        wanted = level_db(127) - 6
        velocity = int(lines[0].split("velocity ")[1].split()[0])
        self.assertLess(abs(level_db(velocity) - wanted), 1.0)
        self.assertIn("below_floor", lines[1])

    def test_compare_tells_secondary_attacks_from_unrelated_ones(self):
        times = [1.0, 2.0, 3.0]
        ref = place(4.5, [(t, burst(-12, seed=i)) for i, t in enumerate(times)])
        events = [(t + 0.5, burst(-12, seed=10 + i)) for i, t in enumerate(times)]  # one beat late in the file
        events += [(t + 0.5 + 0.12, burst(-10, seed=20 + i)) for i, t in enumerate(times)]  # sample's second hit
        events += [(4.4 + 0.5, burst(-12, seed=30))]
        ren = place(5.5, events)
        notes = self.dir / "times.json"
        notes.write_text(json.dumps(times))
        out_json = self.dir / "compare.json"
        self.run_tool(
            "compare",
            self.write("ref.wav", ref),
            self.write("ren.wav", ren),
            "--times",
            notes,
            "--offset",
            -0.5,
            "--out",
            out_json,
        )
        result = json.loads(out_json.read_text())
        self.assertEqual(len(result["render"]["at_note"]), 3)
        self.assertEqual(len(result["render"]["after_note"]), 3)
        self.assertEqual(len(result["render"]["unrelated"]), 1)  # the hit at 4.4 s has no note near it
        self.assertEqual(len(result["reference"]["at_note"]), 3)
        self.assertLess(max(abs(d) for d in result["dynamics_db"]), 1.0)


if __name__ == "__main__":
    unittest.main()
