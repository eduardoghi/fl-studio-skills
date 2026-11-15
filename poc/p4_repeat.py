"""Proof of concept 4. Render one saved project several times and compare the renders with each other.

Each render runs in a separate REAPER process. The output is moved aside after each run, so the next render never
meets an existing file (REAPER would ask before overwriting, in a dialog nobody sees).

Usage: uv run python poc/p4_repeat.py <project.rpp> <expected render path> <runs> <label>
"""

import itertools
import json
import sys
from pathlib import Path

from mps import audio, render

project, target, runs, label = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
files, results = [], []
for k in range(runs):
    if target.exists():
        raise SystemExit(f"{target} exists, move it first")
    res = render.render_project(project, timeout=300)
    check = audio.check(target)
    out = target.with_name(f"{label}_run{k + 1}{target.suffix}")
    if target.exists():
        target.rename(out)
        files.append(out)
    results.append(
        {
            "run": k + 1,
            "returncode": res.get("returncode"),
            "seconds": round(res.get("seconds", 0), 2),
            "file_ok": check["ok"],
            "failures": check.get("failures"),
        }
    )
pairs = []
for a, b in itertools.combinations(files, 2):
    c = audio.compare(a, b)
    pairs.append(
        {
            "a": a.name,
            "b": b.name,
            **{k: c[k] for k in ("identical", "lag_samples", "residual_db", "correlation", "level_difference_db")},
        }
    )
print(json.dumps({"runs": results, "pairs": pairs}, indent=1, default=str))
