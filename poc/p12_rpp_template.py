"""Proof of concept 12. Variants of a project built through the API against the same variants written from a template.

Four variants combine two Kontakt states with two settings of ValhallaVintageVerb's Mix, on one part of six notes.

- API. Each variant is built in a new tab through the bridge (plugins added, the Kontakt state restored into a fresh
  instance, Mix set, notes written, render settings set) and saved.
- Template. The first API project is the template. Each plugin's whole block (`<VST ...` to its `>`) is captured
  from the API projects that hold that state, and each variant is written by swapping those blocks and the render
  file name. Nothing else in the text changes.

Every project is rendered in a separate process (API ones twice, for the natural variation), the template variants are
compared with the API ones, one template project is opened through the bridge to read its plugins back, and one with a
damaged Kontakt block is rendered to see how REAPER reports it.

Usage: uv run python poc/p12_rpp_template.py <folder> <kontakt state A.b64> <kontakt state B.b64>
"""

import json
import re
import sys
import time
from pathlib import Path

from mps import audio, reaper, render, state

folder, state_a, state_b = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
folder.mkdir(parents=True, exist_ok=True)
KONTAKT, VALHALLA = "VST3i:Kontakt 8", "VST3:ValhallaVintageVerb"
VARIANTS = [("A", state_a, 0.25), ("A", state_a, 0.5), ("B", state_b, 0.25), ("B", state_b, 0.5)]


def call(cmd, args=None, timeout=120):
    r = reaper.call(cmd, args or {}, timeout=timeout)
    if r["status"] != reaper.OK:
        raise SystemExit(f"{cmd}: {json.dumps(r)[:300]}")
    return r["result"]


def label(k, mix):
    return f"{k}_mix{int(mix * 100)}"


def build_api(k, chunk_file, mix):
    name = f"api_{label(k, mix)}"
    call("project.new_tab")
    call("project.set_tempo", {"bpm": 120, "srate": 44100})
    tr = call("track.add", {"name": "guitar"})["guid"]
    kon = call("fx.add", {"track": tr, "name": KONTAKT})
    call(
        "fx.restore_fresh",
        {"track": tr, "fx": kon["guid"], "chunk": chunk_file.read_text("ascii"), "name": KONTAKT},
        timeout=180,
    )
    state.settle(tr, 0)
    val = call("fx.add", {"track": tr, "name": VALHALLA})
    mix_param = next(
        p["index"] for p in call("fx.params", {"track": tr, "fx": val["guid"]})["params"] if p["name"] == "Mix"
    )
    set_mix = call("fx.set_param", {"track": tr, "fx": val["guid"], "param": mix_param, "value": mix})
    item = call("item.add_midi", {"track": tr, "start_qn": 0, "end_qn": 16})
    notes = [{"start_qn": 2 * c, "end_qn": 2 * c + 1.5, "chan": c, "pitch": 64, "vel": 100} for c in range(4)]
    notes += [
        {"start_qn": 9, "end_qn": 10.5, "chan": 0, "pitch": 67, "vel": 100},
        {"start_qn": 10, "end_qn": 11.5, "chan": 0, "pitch": 69, "vel": 100},
    ]
    call("midi.write", {"item": item["guid"], "notes": notes, "replace": True})
    call(
        "render.configure",
        {
            "format": "wav32f",
            "directory": str(folder),
            "pattern": name,
            "start": 0,
            "end": 8,
            "srate": 44100,
            "channels": 2,
            "fx_delay": 5,
        },
    )
    rpp = folder / f"{name}.rpp"
    call("project.save", {"path": str(rpp)})
    call("project.close_tab", {"path": str(rpp)})
    return rpp, set_mix["text"]


def fx_block(text, header_start):
    """The whole block of the plugin whose header line starts with header_start, as (start, end) offsets."""
    lines = text.splitlines(keepends=True)
    pos = 0
    for i, line in enumerate(lines):
        if line.lstrip().startswith(header_start):
            indent = line[: len(line) - len(line.lstrip())]
            end = pos
            for j in range(i, len(lines)):
                end += len(lines[j])
                if j > i and lines[j].rstrip("\r\n") == indent + ">":
                    return pos, end
        pos += len(line)
    raise ValueError(f"no block starting with {header_start!r}")


def swap(text, header_start, block):
    s, e = fx_block(text, header_start)
    return text[:s] + block + text[e:]


def render_one(rpp):
    res = render.render_project(rpp, timeout=300, fx_delay=5)
    wav = rpp.with_suffix(".wav")
    check = audio.check(wav, seconds=8, samplerate=44100, channels=2, subtype="FLOAT")
    return {
        "returncode_hex": res.get("returncode_hex"),
        "error": res.get("error"),
        "dialog": res.get("dialog"),
        "file_ok": check["ok"],
        "failures": check.get("failures"),
        "seconds": res.get("seconds"),
    }


report: dict = {"api": {}, "template": {}}

# API
t0 = time.monotonic()
api = {}
for k, chunk_file, mix in VARIANTS:
    t = time.monotonic()
    rpp, mix_text = build_api(k, chunk_file, mix)
    api[label(k, mix)] = rpp
    report["api"][label(k, mix)] = {"build_s": round(time.monotonic() - t, 2), "mix_text": mix_text}
report["api_total_s"] = round(time.monotonic() - t0, 2)

# template, with the capture of each block timed apart from writing the variants
t = time.monotonic()
texts = {lb: p.read_text(encoding="utf-8") for lb, p in api.items()}
kontakt_blocks, valhalla_blocks = {}, {}
for lb, text in texts.items():
    k, mix = lb.split("_")
    s, e = fx_block(text, '<VST "VST3i: Kontakt')
    kontakt_blocks.setdefault(k, text[s:e])
    s, e = fx_block(text, '<VST "VST3: ValhallaVintageVerb')
    valhalla_blocks.setdefault(mix, text[s:e])
report["template_capture_s"] = round(time.monotonic() - t, 4)
template = texts["A_mix25"]
t = time.monotonic()
tpl = {}
for k, _, mix in VARIANTS:
    lb = label(k, mix)
    text = swap(template, '<VST "VST3i: Kontakt', kontakt_blocks[k])
    text = swap(text, '<VST "VST3: ValhallaVintageVerb', valhalla_blocks[f"mix{int(mix * 100)}"])
    out = folder / f"tpl_{lb}.rpp"
    text = re.sub(r'RENDER_FILE "[^"]*"', f'RENDER_FILE "{out.with_suffix(".wav")!s}"'.replace("\\", "\\\\"), text)
    out.write_text(text, encoding="utf-8")
    tpl[lb] = out
report["template_write_s"] = round(time.monotonic() - t, 4)

# renders
for lb, api_rpp in api.items():
    a1 = render_one(api_rpp)
    first = api_rpp.with_suffix(".wav")
    keep = folder / f"api_{lb}_run1.wav"
    first.replace(keep)
    a2 = render_one(api_rpp)
    t1 = render_one(tpl[lb])
    v = audio.variation([keep, first], [tpl[lb].with_suffix(".wav")])
    report["template"][lb] = {
        "api_runs": [a1, a2],
        "template_run": t1,
        "natural_residual_db": v["natural_residual_db"],
        "verdict": v["candidates"][0]["verdict"],
        "closest_residual_db": v["candidates"][0]["closest_residual_db"],
    }

# the variants differ from each other, so the comparison could have failed
cross = audio.compare(folder / "api_A_mix25.wav", folder / "api_B_mix50.wav")
report["A25_vs_B50"] = {"identical": cross.get("identical"), "residual_db": cross.get("residual_db")}

# read a template project back through the bridge
opened = call("project.open", {"path": str(tpl["B_mix50"])}, timeout=180)
info = call("project.info", timeout=60)
tr = info["tracks"][0]["guid"]
state.settle(tr, 0)
val_mix = next(p["text"] for p in call("fx.params", {"track": tr, "fx": 1})["params"] if p["name"] == "Mix")
report["opened_template"] = {
    "project": opened["project"],
    "fx": [f["name"] for f in info["tracks"][0]["fx"]],
    "valhalla_mix_text": val_mix,
    "api_mix_text": report["api"]["B_mix50"]["mix_text"],
}
call("project.close_tab", {"path": str(tpl["B_mix50"])})

# a damaged Kontakt block (one base64 line cut short)
text = tpl["A_mix25"].read_text(encoding="utf-8")
s, e = fx_block(text, '<VST "VST3i: Kontakt')
block = text[s:e].splitlines(keepends=True)
block[3] = block[3][: len(block[3]) // 2] + "\n"
broken = folder / "tpl_broken.rpp"
broken_text = text[:s] + "".join(block) + text[e:]
broken_text = re.sub(
    r'RENDER_FILE "[^"]*"', f'RENDER_FILE "{broken.with_suffix(".wav")!s}"'.replace("\\", "\\\\"), broken_text
)
broken.write_text(broken_text, encoding="utf-8")
b = render_one(broken)
if b["file_ok"]:
    vb = audio.compare(folder / "api_A_mix25.wav", broken.with_suffix(".wav"))
    b["vs_intact"] = {"identical": vb.get("identical"), "residual_db": vb.get("residual_db")}
report["broken_block"] = b

(folder / "p12_results.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
print(json.dumps(report, indent=1, default=str))
