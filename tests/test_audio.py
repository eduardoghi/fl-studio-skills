"""Checks on rendered files, with small synthetic WAVs."""

import numpy as np
import soundfile as sf

from mps import audio

SR = 44100


def tone(path, seconds=1.0, channels=2, level=0.5, subtype="PCM_24"):
    t = np.arange(int(SR * seconds)) / SR
    x = level * np.sin(2 * np.pi * 440 * t)
    sf.write(path, np.stack([x] * channels, axis=1), SR, subtype=subtype)
    return path


def test_check_passes_a_file_matching_the_experiment(tmp_path):
    p = tone(tmp_path / "a.wav")
    c = audio.check(p, seconds=1.0, samplerate=SR, channels=2, subtype="PCM_24")
    assert c["ok"], c["failures"]


def test_check_reports_each_mismatch(tmp_path):
    p = tone(tmp_path / "a.wav", seconds=0.5, channels=1, subtype="PCM_16")
    c = audio.check(p, seconds=1.0, samplerate=48000, channels=2, subtype="PCM_24")
    assert not c["ok"]
    assert len(c["failures"]) == 4


def test_check_flags_silence_and_missing_files(tmp_path):
    p = tone(tmp_path / "s.wav", level=0.0)
    assert any("silent" in f for f in audio.check(p)["failures"])
    assert audio.check(tmp_path / "nope.wav")["failures"] == ["missing"]


def test_compare_finds_identical_and_shifted_renders(tmp_path):
    a = tone(tmp_path / "a.wav")
    b = tone(tmp_path / "b.wav")
    assert audio.compare(a, b)["identical"]
    noise = np.random.default_rng(0).standard_normal((SR, 2)) * 0.1  # aperiodic, so only one lag fits
    sf.write(tmp_path / "n.wav", noise, SR, subtype="PCM_24")
    sf.write(tmp_path / "c.wav", np.roll(noise, 10, axis=0), SR, subtype="PCM_24")
    c = audio.compare(tmp_path / "n.wav", tmp_path / "c.wav")
    assert not c["identical"] and c["lag_samples"] == 10
