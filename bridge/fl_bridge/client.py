"""Sends requests to the script running inside FL Studio."""

import contextlib
import json
import os
import threading
import time
import uuid

from . import doorbell, paths

POLL_S = 0.02
SETTLE_S = 0.2
LOCK_TIMEOUT_S = 15.0

_thread_lock = threading.Lock()


class BridgeError(Exception):
    pass


def _lock_file(handle):
    """Take a lock the system releases if the process dies, so a crash can't block the bridge."""
    handle.seek(0)
    try:
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except ImportError:
        import fcntl

        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_file(handle):
    handle.seek(0)
    try:
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    except ImportError:
        import fcntl

        fcntl.flock(handle, fcntl.LOCK_UN)


@contextlib.contextmanager
def exclusive(folder, timeout=LOCK_TIMEOUT_S):
    """Keep other threads and server processes out of a mailbox, which only holds one request."""
    deadline = time.monotonic() + timeout
    if not _thread_lock.acquire(timeout=timeout):
        raise BridgeError("another request is still using the bridge")
    try:
        with open(folder / "bridge.lock", "a+b") as handle:
            while True:
                try:
                    _lock_file(handle)
                    break
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise BridgeError("another process is still using the bridge") from exc
                    time.sleep(POLL_S)
            try:
                yield
            finally:
                _unlock_file(handle)
    finally:
        _thread_lock.release()


def write_json(path, payload):
    """Replace the file in one step, so FL never reads half a request."""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(temporary, path)


def read_json(path):
    """Return the file's content, or None while it is missing or half written."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def wait_for(path, request_id, timeout):
    deadline = time.monotonic() + timeout
    while True:  # Reads once even with no timeout, which is how a finished action is collected.
        answer = read_json(path)
        if isinstance(answer, dict) and answer.get("id") == request_id:
            return answer
        if time.monotonic() >= deadline:
            return None
        time.sleep(POLL_S)


def call(command, params=None, timeout=5.0, ring=doorbell.ring):
    """Run one command inside FL and return its result."""
    folder = paths.device_dir()
    if not folder.is_dir():
        raise BridgeError(f"{folder} doesn't exist. Run bridge/install.py")
    request_id = uuid.uuid4().hex
    with exclusive(folder):
        write_json(folder / "request.json", {"id": request_id, "command": command, "params": params or {}})
        ring()
        answer = wait_for(folder / "response.json", request_id, timeout)
    if answer is None:
        raise BridgeError(
            f"FL didn't answer {command!r} within {timeout:g} s. Check that FL is open, loopMIDI is running and "
            "the port uses the 'Claude Bridge' controller type"
        )
    if not answer.get("ok"):
        raise BridgeError(f"{command}: {answer.get('error')}")
    return answer.get("result")


def focus_piano_roll(channel, command=None, sleep=time.sleep):
    """Open the piano roll of a channel.

    The piano roll keeps its channel while open, and FL applies interface
    changes after each call returns, so each step needs its own request. FL
    draws the channel name itself: the caption reads "Piano roll -" to both its
    API and Windows, so this can't prove which channel opened. Writes prove it
    with a fingerprint of the notes they expect to find.
    """
    command = command or call
    command("channel_select", {"channel": channel})
    sleep(SETTLE_S)
    command("piano_roll_show")
    sleep(SETTLE_S)
    state = command("focus_state")
    if state["selected"] != channel or not state["piano_roll_focused"] or not state["caption"].startswith("Piano roll"):
        raise BridgeError(f"the piano roll of channel {channel} didn't open: {state}")
    return state


def settled(command, params, check=None, sleep=time.sleep):
    """Read a state again after FL applied it, since mute and solo read stale inside the call that sets them."""
    sleep(SETTLE_S)
    state = call(command, params)
    for key, wanted in (check or {}).items():
        if wanted is not None and state[key] != wanted:
            raise BridgeError(f"FL reports {key}={state[key]!r} after asking for {wanted!r}")
    return state


def queue_piano_roll(action, payload=None, expect=None):
    """Queue an action for the ClaudeBridge script and return its id.

    The queue holds one action, so a second one would silently replace it.
    """
    folder = paths.piano_roll_dir()
    if not folder.is_dir():
        raise BridgeError(f"{folder} doesn't exist")
    request_id = uuid.uuid4().hex
    with exclusive(folder):
        pending = read_json(folder / "pianoroll_queue.json")
        if pending:
            raise BridgeError(
                f"{pending.get('action')!r} is still queued and hasn't run. Run it, or drop it with fl_queue_discard"
            )
        write_json(
            folder / "pianoroll_queue.json",
            {"id": request_id, "action": action, "payload": payload or {}, "expect": expect},
        )
    return request_id


def discard_piano_roll():
    """Drop the queued action and return its name, or None if nothing was queued."""
    folder = paths.piano_roll_dir()
    with exclusive(folder):
        pending = read_json(folder / "pianoroll_queue.json")
        write_json(folder / "pianoroll_queue.json", {})
    return pending.get("action") if pending else None


def piano_roll_result(request_id, timeout=0.0):
    """Return what the piano roll script reported for a request, or None if it hasn't run."""
    answer = wait_for(paths.piano_roll_dir() / "pianoroll_done.json", request_id, timeout)
    if answer is not None and not answer.get("ok"):
        raise BridgeError(f"piano roll script: {answer.get('error')}")
    return None if answer is None else answer.get("result")
