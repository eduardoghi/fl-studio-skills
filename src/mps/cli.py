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
from pathlib import Path

from mps import audio, reaper, render

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
    res = render.render_project(a.project, timeout=a.timeout)
    checks = []
    for path in a.expect or []:
        c = audio.check(path, seconds=a.seconds, samplerate=a.samplerate, channels=a.channels, subtype=a.subtype)
        if c.get("ok") and Path(path).stat().st_mtime < res.get("started", 0):
            c["ok"], c["failures"] = False, ["file is older than this render"]
        checks.append(c)
    ok = res.get("ok", False) and all(c["ok"] for c in checks)
    return emit({**res, "checks": checks, "ok": ok}, 0 if ok else 1)


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
    rn.set_defaults(fn=cmd_render)

    w = sub.add_parser("wav", help="facts about audio files")
    ws = w.add_subparsers(dest="action", required=True)
    i = ws.add_parser("info")
    i.add_argument("files", nargs="+")
    i.set_defaults(fn=cmd_wav_info)
    cp = ws.add_parser("compare")
    cp.add_argument("a")
    cp.add_argument("b")
    cp.set_defaults(fn=cmd_wav_compare)

    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except json.JSONDecodeError as e:
        return emit({"status": "usage", "error": f"bad JSON: {e}"}, 2)


if __name__ == "__main__":
    sys.exit(main())
