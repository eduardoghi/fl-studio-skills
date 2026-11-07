"""Read and write the notes of many channels at once, without passing them through the MCP tools.

Each channel goes through the same steps as the tools. Its piano roll opens, the action is queued, Ctrl+Alt+Y runs
ClaudeBridge and the result is collected. Writes check the fingerprint and read the notes back.
"""

import time

from . import client, window

RUN_TRIES = 4
RESULT_TIMEOUT_S = 8.0
TICKS_PER_BEAT = 960  # Only for comparing, so it needs no more than FL's own resolution.
DEFAULT_VELOCITY = 0.8  # What ClaudeBridge writes when a note has no velocity.


def check(notes):
    """Refuse notes FL would reject or change, before anything is queued."""
    for i, note in enumerate(notes):
        if not 0 <= int(note["pitch"]) <= 127 or float(note["start"]) < 0 or float(note["length"]) <= 0:
            raise ValueError(f"note {i} is out of range")
        if not 0 <= float(note.get("velocity", DEFAULT_VELOCITY)) <= 1:
            raise ValueError(f"note {i} has a velocity outside 0 to 1")


def _key(note):
    # FL keeps velocity in steps of 1/128, so a written 0.62 reads back as 0.617.
    return (
        int(note["pitch"]),
        round(float(note["start"]) * TICKS_PER_BEAT),
        round(float(note["length"]) * TICKS_PER_BEAT),
        round(float(note.get("velocity", DEFAULT_VELOCITY)) * 128),
    )


def same(got, want):
    return sorted(map(_key, got)) == sorted(map(_key, want))


def run(channel, action, payload=None, expect=None, sleep=time.sleep):
    """Queue one action, apply it to a channel and return the result."""
    request = client.queue_piano_roll(action, payload, expect)
    try:
        for attempt in range(RUN_TRIES):
            client.focus_piano_roll(channel)
            try:
                window.run_last_script()
                break
            except window.WindowError:
                if attempt == RUN_TRIES - 1:
                    raise
                sleep(1)
        result = client.piano_roll_result(request, timeout=RESULT_TIMEOUT_S)
    except BaseException:
        client.discard_piano_roll()  # A queued action left behind would block the next tool.
        raise
    if result is None:
        client.discard_piano_roll()
        raise client.BridgeError(
            f"ClaudeBridge didn't run on channel {channel}. Start it once from Tools > Scripts in the piano roll"
        )
    return result


def select_pattern(index, sleep=time.sleep):
    client.call("pattern_select", {"index": index})
    sleep(client.SETTLE_S)
    current = client.call("project")["current_pattern"]
    if current != index:
        raise client.BridgeError(f"FL shows pattern {current} after asking for {index}")


def read(pattern, channels):
    """Return the notes and fingerprint of each channel in one pattern, keyed by channel."""
    select_pattern(pattern)
    try:
        return {c: run(c, "read") for c in channels}
    finally:
        client.call("piano_roll_hide")


def write(pattern, data, replace=False):
    """Write a list of notes per channel into a pattern and return one line of report per channel.

    Every channel is read before anything is written, so a channel holding other notes stops the whole write
    instead of leaving it half done. Those notes are only cleared with replace.
    """
    for notes in data.values():
        check(notes)
    select_pattern(pattern)
    try:
        current = {c: run(c, "read") for c in data}
        busy = [c for c, r in current.items() if r["notes"] and not same(r["notes"], data[c])]
        if busy and not replace:
            raise client.BridgeError(f"channels {busy} hold other notes. Pass replace to clear them")
        report = []
        for c, want in data.items():
            if current[c]["notes"] and c not in busy:
                report.append(f"{c}: already written, {len(want)} notes")
                continue
            fingerprint = current[c]["fingerprint"]
            if c in busy:
                fingerprint = run(c, "clear", expect=fingerprint)["fingerprint"]
            run(c, "add_notes", {"notes": want}, fingerprint)
            back = run(c, "read")["notes"]
            if not same(back, want):
                raise client.BridgeError(
                    f"channel {c} read back {len(back)} notes that differ from the {len(want)} written"
                )
            report.append(f"{c}: {len(want)} notes written and read back")
        return report
    finally:
        client.call("piano_roll_hide")
