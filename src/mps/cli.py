"""Command line for the mps library. Every command prints one JSON document and exits with a meaningful code.

Exit codes:
  0  done
  1  the command ran and failed, or a check failed
  2  bad usage
  3  not started (no instance, or the request was withdrawn before it ran)
  4  uncertain (it may or may not have taken effect; don't repeat it blindly)
  5  expired before it ran
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from mps import audio, manifest, reaper, render, rpp, state

CODES = {reaper.OK: 0, reaper.ERROR: 1, reaper.NOT_STARTED: 3, reaper.UNCERTAIN: 4, reaper.EXPIRED: 5}
BRIDGE = Path(__file__).resolve().parents[2] / "reaper" / "mps_bridge.lua"
MARK_BEGIN, MARK_END = "-- mps bridge (begin)", "-- mps bridge (end)"


def emit(obj, code=0):
    print(json.dumps(obj, indent=1, default=str))
    return code


def cmd_call(a):
    if a.args_file:
        args = json.loads(Path(a.args_file).read_text(encoding="utf-8"))
    else:
        args = json.loads(a.args) if a.args else {}
    try:
        res = reaper.call(a.command, args, instance=a.instance, timeout=a.timeout, expect_project=a.expect_project)
    except reaper.BridgeError as e:
        return emit({"status": reaper.NOT_STARTED, "error": str(e)}, 3)
    if a.out and res.get("status") == reaper.OK:
        Path(a.out).write_text(json.dumps(res["result"], indent=1), encoding="utf-8")
        res["result"] = {"written": a.out}
    return emit(res, CODES.get(res.get("status"), 1))


def cmd_instances(a):
    return emit(
        [{"id": i.id, "alive": i.alive, "heartbeat_age": i.heartbeat_age, **i.info} for i in reaper.list_instances()]
    )


def cmd_prune(a):
    # keeps any folder with a request in work/, which records a command whose outcome is still unknown
    import shutil

    removed, kept = [], []
    for i in reaper.list_instances():
        if i.heartbeat_age < a.older_than * 60:
            continue
        if any((i.path / "work").iterdir()):
            kept.append(i.id)
            continue
        shutil.rmtree(i.path)
        removed.append(i.id)
    return emit({"removed": removed, "kept_with_unfinished_requests": kept})


def cmd_install(a):
    startup = reaper.resource_path() / "Scripts" / "__startup.lua"
    text = startup.read_text(encoding="utf-8") if startup.exists() else ""
    if MARK_BEGIN in text:
        return emit({"installed": str(startup), "changed": False})
    block = f"{MARK_BEGIN}\ndofile([[{BRIDGE}]])\n{MARK_END}\n"
    startup.parent.mkdir(parents=True, exist_ok=True)
    startup.write_text(text + ("\n" if text and not text.endswith("\n") else "") + block, encoding="utf-8")
    return emit({"installed": str(startup), "changed": True})


def cmd_start(a):
    # runs the bridge in the REAPER instance already open, without restarting it
    subprocess.Popen([str(render.reaper_exe()), "-nonewinst", str(BRIDGE)])
    return emit({"started": str(BRIDGE)})


def cmd_render(a):
    project = Path(a.project)
    settings, plugins = rpp.read(project) if project.is_file() else ({}, [])
    off_standard = render.deviations(settings, plugins) if settings else []
    # without --seconds, the length follows from the saved bounds and tail
    seconds = a.seconds if a.seconds is not None else render.expected_seconds(settings)
    # a render writes over its target without asking, which would destroy an earlier render kept as evidence
    existing = sorted({str(p) for p in [*render.targets(settings), *map(Path, a.expect or [])] if p.exists()})
    if existing and not a.overwrite:
        return emit(
            {"ok": False, "error": "target files exist, pass --overwrite to replace them", "existing": existing}, 1
        )
    # REAPER asks before writing over a file when it renders from a script, so the files allowed to go are removed
    for path in existing:
        Path(path).unlink()
    res = render.render_project(
        project, timeout=a.timeout, mode=a.mode, settle=a.settle, fx_delay=settings.get("fx_delay") or 0.0
    )
    checks = []
    for path in a.expect or []:
        c = audio.check(path, seconds=seconds, samplerate=a.samplerate, channels=a.channels, subtype=a.subtype)
        if c.get("ok") and Path(path).stat().st_mtime < res.get("started", 0):
            c["ok"], c["failures"] = False, ["file is older than this render"]
        if Path(path).is_file():
            c["sha256"] = manifest.sha256_file(path)
        checks.append(c)
    files_ok = all(c["ok"] for c in checks)
    # complete files from a process that crashed on exit are kept apart from a normal render (see render.py)
    abnormal = res.get("returncode", 0) != 0
    standard_ok = not off_standard or a.allow_nonstandard
    ok = res.get("ok", False) and files_ok and not abnormal and standard_ok
    record = {
        **res,
        "ok": ok,
        "files_ok": files_ok,
        "abnormal_exit": abnormal,
        "standard": {"ok": not off_standard, "deviations": off_standard, "allowed": bool(a.allow_nonstandard)},
        "checks": checks,
        "project": {"path": str(project), "sha256": manifest.sha256_file(project) if project.is_file() else None},
        "settings": settings,
        "expected_seconds": seconds,
        "plugins": [{**p, **(manifest.plugin_version(p["file"]) if p["file"] else {})} for p in plugins],
        "reaper": {"exe": str(render.reaper_exe()), "version": manifest.file_version(render.reaper_exe())},
        "recorded": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    out = a.manifest or (str(Path(a.expect[0]).with_suffix(".render.json")) if a.expect else None)
    if out:
        Path(out).write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
        record["manifest"] = out
    return emit(record, 0 if ok else 1)


def _fx(value):
    # an effect is named by its index on the track or by its GUID
    return int(value) if value.isdigit() else value


def cmd_state_save(a):
    try:
        return emit(state.save(a.track, _fx(a.fx), a.folder, instance=a.instance))
    except (state.StateError, reaper.BridgeError) as e:
        return emit({"ok": False, "error": str(e)}, 1)


def cmd_state_restore(a):
    try:
        res = state.restore(a.track, _fx(a.fx), a.state, name=a.fresh, instance=a.instance)
    except (state.StateError, reaper.BridgeError) as e:
        return emit({"ok": False, "error": str(e)}, 1)
    return emit(res, 0 if res["ok"] else 1)


def cmd_wav_variation(a):
    res = audio.variation(a.reference, a.candidate or [])
    # a candidate outside the natural variation is a finding, not a failure of the command
    return emit(res)


def cmd_wav_info(a):
    return emit([audio.info(p) for p in a.files])


def cmd_wav_compare(a):
    return emit(audio.compare(a.a, a.b))


def main(argv=None):
    p = argparse.ArgumentParser(prog="mps", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="group", required=True)

    r = sub.add_parser("reaper", help="talk to a running REAPER through the bridge")
    rs = r.add_subparsers(dest="action", required=True)
    c = rs.add_parser("call", help="run one bridge command")
    c.add_argument("command")
    c.add_argument("--args", help="JSON object with the command's arguments")
    c.add_argument("--args-file", help="file with the JSON arguments, for large ones such as plugin states")
    c.add_argument("--out", help="write the result to this file instead of printing it")
    c.add_argument("--instance")
    c.add_argument("--timeout", type=float, default=10.0)
    c.add_argument("--expect-project", help="refuse to run unless this project is the current tab")
    c.set_defaults(fn=cmd_call)
    rs.add_parser("instances", help="list bridge instances and their heartbeat").set_defaults(fn=cmd_instances)
    pr = rs.add_parser("prune", help="delete folders of instances whose heartbeat stopped long ago")
    pr.add_argument("--older-than", type=float, default=60.0, help="minutes without a heartbeat")
    pr.set_defaults(fn=cmd_prune)
    rs.add_parser("install", help="load the bridge from Scripts/__startup.lua").set_defaults(fn=cmd_install)
    rs.add_parser("start", help="start the bridge in the open REAPER now").set_defaults(fn=cmd_start)

    rn = sub.add_parser("render", help="render a saved project in a separate REAPER process and check the files")
    rn.add_argument("project")
    rn.add_argument("--expect", nargs="*", help="files the render must produce")
    rn.add_argument("--seconds", type=float)
    rn.add_argument("--samplerate", type=int)
    rn.add_argument("--channels", type=int)
    rn.add_argument("--subtype", help="soundfile subtype, such as PCM_24 or FLOAT")
    rn.add_argument("--timeout", type=float, default=600.0)
    rn.add_argument("--overwrite", action="store_true", help="replace target files that already exist")
    rn.add_argument(
        "--mode",
        choices=["script", "renderproject"],
        default="script",
        help="render through reaper/mps_render.lua and quit normally (default), or with -renderproject",
    )
    rn.add_argument("--settle", type=float, default=3.0, help="seconds to wait after the render before quitting")
    rn.add_argument("--manifest", help="where to write the render record (default: next to the first expected file)")
    rn.add_argument(
        "--allow-nonstandard", action="store_true", help="accept render settings that differ from the standard"
    )
    rn.set_defaults(fn=cmd_render)

    st = sub.add_parser("state", help="save a plugin's state and restore it with checks")
    sts = st.add_subparsers(dest="action", required=True)
    sv = sts.add_parser("save", help="store the state as <sha256>.b64 with the plugin and its parameter text")
    sv.add_argument("--track", required=True, help="track GUID")
    sv.add_argument("--fx", required=True, help="effect index or GUID")
    sv.add_argument("folder")
    sv.add_argument("--instance")
    sv.set_defaults(fn=cmd_state_save)
    rs2 = sts.add_parser("restore", help="write a stored state back and check its integrity and configuration")
    rs2.add_argument("--track", required=True, help="track GUID")
    rs2.add_argument("--fx", required=True, help="effect index or GUID")
    rs2.add_argument("state", help="the <sha256>.b64 file")
    rs2.add_argument(
        "--fresh", metavar="NAME", help="restore into a new instance added by this name (needed for Kontakt)"
    )
    rs2.add_argument("--instance")
    rs2.set_defaults(fn=cmd_state_restore)

    w = sub.add_parser("wav", help="facts about audio files")
    ws = w.add_subparsers(dest="action", required=True)
    i = ws.add_parser("info")
    i.add_argument("files", nargs="+")
    i.set_defaults(fn=cmd_wav_info)
    cp = ws.add_parser("compare")
    cp.add_argument("a")
    cp.add_argument("b")
    cp.set_defaults(fn=cmd_wav_compare)
    va = ws.add_parser("variation", help="judge renders against the variation between repeated reference renders")
    va.add_argument("--reference", nargs="+", required=True, help="renders of the unchanged project")
    va.add_argument("--candidate", nargs="*", help="renders to judge")
    va.set_defaults(fn=cmd_wav_variation)

    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except json.JSONDecodeError as e:
        return emit({"status": "usage", "error": f"bad JSON: {e}"}, 2)


if __name__ == "__main__":
    sys.exit(main())
