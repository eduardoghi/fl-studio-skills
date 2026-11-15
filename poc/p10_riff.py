"""Proof of concept 10. Render four bars of a real guitar part in two ways and record everything needed to redo them.

The notes come from a build JSON (song_onset in seconds, length in quarter notes, velocity_midi, and string 0 to 5
from the low E up). They are placed at their song time, so the renders line up with the reference with no offset.

- strings, the state with Channel-Based Strings set to MIDI Guitar, each note on the channel of its string (channel
  0 is the highest string, so channel = 5 - string)
- auto, the default state, every note on channel 0, so the instrument picks the strings itself

For each variant a new project tab is made, Kontakt is added, the saved state is written into the fresh instance and
the instrument is left to settle, the notes are written and read back, the render is set explicitly, the project is
saved and closed, and it is rendered in a separate REAPER process. The files are checked and a manifest is written.

Usage: uv run python poc/p10_riff.py <build.json> <first bar> <last bar> <strings state.b64> <auto state.b64>
       <folder> <reference.wav> <instrument.nki> <bpm> <first downbeat s>
"""

import json
import sys
import time
from pathlib import Path

from mps import audio, manifest, reaper, render

SRATE, CHANNELS, FORMAT, SUBTYPE = 44100, 2, "wav24", "PCM_24"
build, b0, b1, strings_state, auto_state, folder, reference, nki = (
    Path(sys.argv[1]),
    int(sys.argv[2]),
    int(sys.argv[3]),
    Path(sys.argv[4]),
    Path(sys.argv[5]),
    Path(sys.argv[6]),
    Path(sys.argv[7]),
    Path(sys.argv[8]),
)
BPM, T0 = float(sys.argv[9]), float(sys.argv[10])
bar = 4 * 60 / BPM
start_s = T0 + (b0 - 2) * bar  # one bar of lead-in, so notes ringing into the first bar are there
end_s = T0 + b1 * bar + 1.0  # one second of tail
folder.mkdir(parents=True, exist_ok=True)


def ok(res):
    if res["status"] != reaper.OK:
        raise SystemExit(json.dumps(res, indent=1))
    return res["result"]


notes = [n for n in json.loads(build.read_text(encoding="utf-8"))["notes"] if start_s <= n["song_onset"] < end_s - 1.0]


def midi(channels_by_string):
    out = []
    for n in notes:
        qn = n["song_onset"] * BPM / 60
        out.append(
            {
                "start_qn": qn,
                "end_qn": qn + n["length"],
                "pitch": n["pitch"],
                "vel": n["velocity_midi"],
                "chan": (5 - n["string"]) if channels_by_string else 0,
            }
        )
    return out


def settle(track, param=80, limit=90):
    """Wait for Kontakt to finish loading. The text of a script parameter appears once the instrument is up, but in
    some fresh instances it stayed empty although the instrument had loaded, so after 10 s a state of stable length
    in two reads in a row is accepted too."""
    start, last, last_len = time.monotonic(), None, None
    while time.monotonic() - start < limit:
        rows = ok(reaper.call("fx.params", {"track": track, "fx": 0}, timeout=60))["params"]
        t = next((r["text"] for r in rows if r["index"] == param), "")
        if t and t == last:
            return {"after_s": round(time.monotonic() - start, 1), "by": "parameter text"}
        if time.monotonic() - start > 10:
            n = len(ok(reaper.call("fx.state_get", {"track": track, "fx": 0}, timeout=60))["chunk"])
            if n == last_len:
                return {"after_s": round(time.monotonic() - start, 1), "by": "state length"}
            last_len = n
        last = t
        time.sleep(1)
    raise SystemExit("instrument never settled")


ping = ok(reaper.call("ping"))
variants = []
for label, state_file, by_string in (("strings", strings_state, True), ("auto", auto_state, False)):
    name = f"riff_b{b0}-{b1}_{label}"
    target = folder / f"{name}.wav"
    if target.exists():
        target.unlink()
    ok(reaper.call("project.new_tab"))
    ok(reaper.call("project.set_tempo", {"bpm": BPM, "srate": SRATE}))
    track = ok(reaper.call("track.add", {"name": f"guitar {label}"}))["guid"]
    fx = ok(reaper.call("fx.add", {"track": track, "name": "VST3:Kontakt 8", "position": 0}, timeout=60))
    state = state_file.read_text("ascii")
    ok(reaper.call("fx.state_set", {"track": track, "fx": 0, "chunk": state}, timeout=120))
    settled = settle(track)
    item = ok(reaper.call("item.add_midi", {"track": track, "start_qn": 0, "end_qn": end_s * BPM / 60}))
    written = midi(by_string)
    back = ok(reaper.call("midi.write", {"item": item["guid"], "notes": written, "replace": True}))
    conf = ok(
        reaper.call(
            "render.configure",
            {
                "directory": str(folder),
                "pattern": name,
                "format": FORMAT,
                "start": start_s,
                "end": end_s,
                "srate": SRATE,
                "channels": CHANNELS,
            },
        )
    )
    rpp = folder / f"{name}.rpp"
    ok(reaper.call("project.save", {"path": str(rpp)}, timeout=60))
    ok(reaper.call("project.close_tab", {"path": str(rpp)}))
    res = render.render_project(rpp, timeout=300)
    check = audio.check(target, seconds=end_s - start_s, samplerate=SRATE, channels=CHANNELS, subtype=SUBTYPE)
    binary = manifest.plugin_binary(fx["ident"])
    variants.append(
        {
            "label": label,
            "project": str(rpp),
            "project_sha256": manifest.sha256_file(rpp),
            "render": {
                "target": conf["targets"],
                "start_s": start_s,
                "end_s": end_s,
                "srate": SRATE,
                "channels": CHANNELS,
                "format": FORMAT,
                "process": res,
            },
            "output": {**check, "sha256": manifest.sha256_file(target) if target.exists() else None},
            "instrument": {
                "plugin": fx["name"],
                "ident": fx["ident"],
                "binary_version": manifest.file_version(binary) if binary else None,
                "state_file": str(state_file),
                "state_sha256": manifest.sha256_text(state),
                "settled_after_s": settled,
            },
            "midi": {
                "notes_written": len(written),
                "notes_read_back": len(back["notes"]),
                "channels_used": sorted({n["chan"] for n in written}),
            },
        }
    )
lib = Path(nki).parents[1]  # the library folder holds Instruments\<name>.nki and <name>.nicnt
record = {
    "experiment": f"riff bars {b0}-{b1}, strings by channel against automatic strings",
    "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "reaper": ping["reaper"],
    "bridge": ping["bridge"],
    "inputs": {
        "build": str(build),
        "build_sha256": manifest.sha256_file(build),
        "bars": [b0, b1],
        "bpm": BPM,
        "first_downbeat_s": T0,
        "reference": str(reference),
        "reference_sha256": manifest.sha256_file(reference),
    },
    "library": {
        "folder": str(lib),
        "nicnt_sha256": manifest.sha256_file(next(lib.glob("*.nicnt"))),
        "nki": nki,
        "nki_sha256": manifest.sha256_file(nki),
    },
    "variants": variants,
}
(folder / f"riff_b{b0}-{b1}_manifest.json").write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
print(
    json.dumps(
        {
            v["label"]: {
                "ok": v["output"]["ok"],
                "failures": v["output"].get("failures"),
                "seconds": v["output"].get("seconds"),
                "channels": v["midi"]["channels_used"],
                "notes": [v["midi"]["notes_written"], v["midi"]["notes_read_back"]],
                "render_s": v["render"]["process"].get("seconds"),
            }
            for v in variants
        },
        indent=1,
    )
)
