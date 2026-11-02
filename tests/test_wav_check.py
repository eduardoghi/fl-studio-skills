"""Tests for bin/wav-check against WAV files synthesized here.

Run with `python3 -m unittest discover -s tests`. Needs numpy.
"""
import os
import struct
import subprocess
import sys
import tempfile
import unittest

try:
    import numpy as np
except ImportError:
    raise unittest.SkipTest("wav-check needs numpy")

WAV_CHECK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "wav-check")
RATE = 44100


def tone(freq, seconds, amp=0.5):
    t = np.arange(int(seconds * RATE)) / RATE
    return amp * np.sin(2 * np.pi * freq * t)


def wav_bytes(x, fmt_tag=1, bits=16):
    if x.ndim == 1:
        x = np.column_stack([x, x])
    if fmt_tag == 3:
        pcm = x.astype("<f4").tobytes()
    elif bits == 24:
        v = (np.clip(x, -1, 1) * 8388607).astype(np.int32).ravel()
        pcm = np.column_stack([v & 255, (v >> 8) & 255, (v >> 16) & 255]).astype("u1").tobytes()
    else:
        pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
    block = x.shape[1] * bits // 8
    head = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt "
    head += struct.pack("<IHHIIHH", 16, fmt_tag, x.shape[1], RATE, RATE * block, block, bits)
    return head + b"data" + struct.pack("<I", len(pcm)) + pcm


class WavCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, x, **kwargs):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as f:
            f.write(wav_bytes(x, **kwargs))
        return path

    def run_tool(self, *args, code=0):
        done = subprocess.run([sys.executable, WAV_CHECK, *args], capture_output=True, text=True)
        self.assertEqual(done.returncode, code, done.stderr + done.stdout)
        return done.stdout

    def test_measure_reports_level_and_band(self):
        out = self.run_tool("measure", self.write("a.wav", tone(1000, 2)))
        self.assertIn("peak -6.0 dBFS", out)
        self.assertIn("RMS -9.0 dBFS", out)
        self.assertIn("500-2000 Hz 100%", out)

    def test_reads_24_bit_and_float(self):
        for name, kwargs in (("p24.wav", {"bits": 24}), ("f32.wav", {"fmt_tag": 3, "bits": 32})):
            out = self.run_tool("measure", self.write(name, tone(1000, 1), **kwargs))
            self.assertIn("peak -6.0 dBFS", out)

    def test_timeline_shows_where_the_music_ends(self):
        x = np.concatenate([tone(440, 4), np.zeros(4 * RATE)])
        lines = self.run_tool("timeline", self.write("a.wav", x), "--step", "4").splitlines()
        self.assertIn("-6.0", lines[0])
        self.assertIn("-240.0", lines[1])

    def test_noise_finds_the_slow_swing(self):
        rng = np.random.default_rng(1)
        t = np.arange(20 * RATE) / RATE
        hiss = rng.normal(0, 0.002, len(t))
        hiss = np.diff(hiss, prepend=0) * (1 + 0.8 * np.sin(2 * np.pi * 0.8 * t))
        out = self.run_tool("noise", self.write("a.wav", hiss), "--start", "0")
        self.assertIn("strongest swing 0.80 Hz", out)
        self.assertIn("6000-20000 Hz", out)

    def test_thumps_finds_a_low_hit_without_midrange(self):
        x = tone(1000, 8, amp=0.02)
        hit = tone(90, 0.12, amp=0.6) * np.linspace(1, 0, int(0.12 * RATE))
        at = int(4 * 60 / 95 * RATE)
        x[at:at + len(hit)] += hit
        out = self.run_tool("thumps", self.write("a.wav", x), "--bpm", "95")
        self.assertIn("bar 2", out)

    def test_thumps_stays_quiet_on_plain_notes(self):
        out = self.run_tool("thumps", self.write("a.wav", tone(440, 4)), "--bpm", "95")
        self.assertIn("no low attack", out)

    def test_chords_passes_and_fails(self):
        c_major = tone(261.63, 4, 0.2) + tone(329.63, 4, 0.2) + tone(392.0, 4, 0.2)
        path = self.write("a.wav", c_major)
        out = self.run_tool("chords", path, "--bpm", "120", "C:0-8:C,E,G")
        self.assertIn("ok", out)
        out = self.run_tool("chords", path, "--bpm", "120", "Cm:0-8:C,Eb,G", code=1)
        self.assertIn("missing Eb", out)
        self.assertIn("extra E", out)

    def test_width(self):
        left = tone(440, 1)
        self.assertIn("correlation 1.00", self.run_tool("width", self.write("mono.wav", left)))
        inverted = self.write("inverted.wav", np.column_stack([left, -left]))
        self.assertIn("correlation -1.00", self.run_tool("width", inverted))

    def test_match_sets_the_level_and_cuts(self):
        path = self.write("a.wav", tone(440, 4, amp=0.05))
        out_dir = os.path.join(self.tmp.name, "out")
        self.run_tool("match", out_dir, "--peak", "-6", "--seconds", "2", path)
        out = self.run_tool("measure", os.path.join(out_dir, "a.wav"))
        self.assertIn("2.0 s", out)
        self.assertIn("peak -6.0 dBFS", out)


if __name__ == "__main__":
    unittest.main()
