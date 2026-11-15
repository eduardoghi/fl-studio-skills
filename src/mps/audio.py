"""Facts about rendered audio files and simple comparisons between them."""

from pathlib import Path

import numpy as np
import soundfile as sf

SILENCE_DB = -90.0


def db(x: float) -> float:
    return float(20 * np.log10(max(x, 1e-12)))


def info(path: str | Path) -> dict:
    """Format, duration and level of a file."""
    f = sf.info(str(path))
    x, _ = sf.read(str(path), dtype="float64", always_2d=True)
    peak = float(np.abs(x).max()) if x.size else 0.0
    rms = float(np.sqrt(np.mean(x**2))) if x.size else 0.0
    # the level of the last 100 ms says whether the file ends in silence or cuts a sound or a tail short
    end = x[-max(1, f.samplerate // 10) :]
    end_rms = float(np.sqrt(np.mean(end**2))) if end.size else 0.0
    return {
        "path": str(path),
        "format": f.format,
        "subtype": f.subtype,
        "samplerate": f.samplerate,
        "channels": f.channels,
        "frames": f.frames,
        "seconds": f.frames / f.samplerate,
        "peak_db": db(peak),
        "rms_db": db(rms),
        "end_rms_db": db(end_rms),
        "silent": db(peak) < SILENCE_DB,
    }


def check(
    path: str | Path,
    *,
    seconds: float | None = None,
    samplerate: int | None = None,
    channels: int | None = None,
    subtype: str | None = None,
    tolerance_s: float = 0.01,
) -> dict:
    """Compare a file with what an experiment expected. Returns the facts and a list of failed checks."""
    p = Path(path)
    if not p.is_file():
        return {"path": str(p), "ok": False, "failures": ["missing"]}
    facts = info(p)
    failures = []
    if facts["silent"]:
        failures.append(f"silent (peak {facts['peak_db']:.1f} dB)")
    if seconds is not None and abs(facts["seconds"] - seconds) > tolerance_s:
        failures.append(f"duration {facts['seconds']:.4f} s, expected {seconds:.4f} s")
    if samplerate is not None and facts["samplerate"] != samplerate:
        failures.append(f"sample rate {facts['samplerate']}, expected {samplerate}")
    if channels is not None and facts["channels"] != channels:
        failures.append(f"{facts['channels']} channels, expected {channels}")
    if subtype is not None and facts["subtype"] != subtype:
        failures.append(f"subtype {facts['subtype']}, expected {subtype}")
    return {**facts, "ok": not failures, "failures": failures}


def compare(a: str | Path, b: str | Path, *, max_lag_ms: float = 20.0) -> dict:
    """How far two renders of the same material differ.

    The second file is shifted by the lag (up to max_lag_ms) that best lines it up with the first, then subtracted.
    residual_db is the level of the difference relative to the first file (very negative means nearly identical,
    -inf when sample-identical). lag_samples is positive when the second file is late. identical says whether the
    samples match exactly with no shift.
    """
    x, sr = sf.read(str(a), dtype="float64", always_2d=True)
    y, sr2 = sf.read(str(b), dtype="float64", always_2d=True)
    if sr != sr2 or x.shape[1] != y.shape[1]:
        return {"comparable": False, "reason": "different sample rate or channel count"}
    n = min(len(x), len(y))
    x, y = x[:n], y[:n]
    identical = bool(np.array_equal(x, y))
    m = x.mean(1)
    k = y.mean(1)
    max_lag = int(sr * max_lag_ms / 1000)
    best, lag = -np.inf, 0
    for lg in range(-max_lag, max_lag + 1):
        if lg >= 0:
            c = float(np.dot(m[lg:], k[: n - lg]))
        else:
            c = float(np.dot(m[: n + lg], k[-lg:]))
        if c > best:
            best, lag = c, lg
    if lag >= 0:
        xs, ys = x[lag:], y[: n - lag]
    else:
        xs, ys = x[: n + lag], y[-lag:]
    ref = float(np.sqrt(np.mean(xs**2)))
    diff = float(np.sqrt(np.mean((xs - ys) ** 2)))
    corr = float(np.corrcoef(xs.mean(1), ys.mean(1))[0, 1]) if ref > 0 else float("nan")
    return {
        "comparable": True,
        "identical": identical,
        "lag_samples": -lag,
        "residual_db": db(diff) - db(ref) if diff > 0 else float("-inf"),
        "correlation": corr,
        "level_difference_db": db(float(np.sqrt(np.mean(ys**2)))) - db(ref),
    }
