"""MCP tools for controlling FL Studio from Claude Code."""

import re

from mcp.server.fastmcp import FastMCP

from . import client, hotkey, render

server = FastMCP(
    "fl-bridge",
    instructions=(
        "Controls the project open in FL Studio. Every change is read back from FL. Plugins can't be loaded and "
        "nothing is saved from here. Piano roll actions are queued and need the ClaudeBridge script to run."
    ),
)


def _target(channel, track, slot):
    if channel is not None:
        return {"channel": channel}
    if track is None or slot is None:
        raise ValueError("pass channel for an instrument, or track and slot for a mixer effect")
    return {"track": track, "slot": slot}


def rgb(color):
    """Convert '#RRGGBB' to the signed 32 bit integer FL stores."""
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("color must look like #RRGGBB")
    value = 0xFF000000 | int(color[1:], 16)
    return value - (1 << 32)


@server.tool()
def fl_status() -> dict:
    """Check that the bridge reaches FL and summarize the open project."""
    return {"bridge": client.call("ping", timeout=3), "project": client.call("project")}


@server.tool()
def fl_transport(action: str) -> dict:
    """Start or stop playback. action is play or stop."""
    return client.call("transport", {"action": action})


@server.tool()
def fl_set_tempo(bpm: float) -> dict:
    """Set the project tempo in BPM."""
    if not 10 <= bpm <= 522:
        raise ValueError("bpm must be between 10 and 522")
    return client.call("set_tempo", {"bpm": bpm})


@server.tool()
def fl_mixer_list() -> list:
    """List the master, named tracks and tracks with effects, with their loaded plugins."""
    return client.call("mixer_list", timeout=10)


@server.tool()
def fl_mixer_set(
    track: int,
    volume: float | None = None,
    pan: float | None = None,
    muted: bool | None = None,
    name: str | None = None,
    color: str | None = None,
) -> dict:
    """Change a mixer track and return its state as FL reports it.

    volume goes from 0 to 1, where 0.8 is 0 dB. pan goes from -1 to 1. color looks like #RRGGBB.
    """
    client.call(
        "mixer_set",
        {
            "track": track,
            "volume": volume,
            "pan": pan,
            "muted": muted,
            "name": name,
            "color": rgb(color) if color else None,
        },
    )
    return client.settled("mixer_get", {"track": track}, {"muted": muted})


@server.tool()
def fl_mixer_solo(track: int, soloed: bool) -> dict:
    """Solo a track or clear its solo. Other tracks can change mute state, so read the mixer afterwards."""
    client.call("mixer_solo", {"track": track, "soloed": soloed})
    return client.settled("mixer_get", {"track": track}, {"soloed": soloed})


@server.tool()
def fl_mixer_peaks(track: int | None = None) -> list:
    """Read current peak meters. Muted tracks still report peaks, so render and measure for real levels."""
    return client.call("mixer_peaks", {"track": track})


@server.tool()
def fl_pattern_list(last: int = 8) -> dict:
    """List patterns 1 to last with their names and lengths, and the current one."""
    return client.call("pattern_list", {"last": last})


@server.tool()
def fl_pattern_select(index: int) -> dict:
    """Make a pattern current. Notes and steps go to the current pattern."""
    client.call("pattern_select", {"index": index})
    return client.settled("pattern_list", {"last": index})


@server.tool()
def fl_pattern_name(index: int, name: str) -> dict:
    """Rename a pattern."""
    return client.call("pattern_name", {"index": index, "name": name})


@server.tool()
def fl_channel_list() -> list:
    """List Channel Rack channels with their instrument and mixer track."""
    return client.call("channel_list", timeout=10)


@server.tool()
def fl_channel_set(
    channel: int,
    volume: float | None = None,
    pan: float | None = None,
    muted: bool | None = None,
    track: int | None = None,
) -> dict:
    """Change a channel and return its state as FL reports it. track is the mixer track it feeds."""
    client.call("channel_set", {"channel": channel, "volume": volume, "pan": pan, "muted": muted, "track": track})
    return client.settled("channel_get", {"channel": channel}, {"muted": muted, "track": track})


@server.tool()
def fl_channel_steps(channel: int, pattern: str) -> dict:
    """Write the step sequencer of the current pattern. pattern is a string of 0 and 1, one per 16th note."""
    if not re.fullmatch(r"[01]{1,64}", pattern):
        raise ValueError("pattern must be 1 to 64 characters of 0 and 1")
    return client.call("channel_steps", {"channel": channel, "steps": [c == "1" for c in pattern]})


@server.tool()
def fl_channel_focus(channel: int) -> dict:
    """Select a channel and reopen the piano roll on it."""
    return client.focus_piano_roll(channel)


@server.tool()
def fl_plugin_params(
    channel: int | None = None,
    track: int | None = None,
    slot: int | None = None,
    contains: str | None = None,
    limit: int = 200,
) -> dict:
    """List a plugin's named parameters. Pass channel for an instrument, or track and slot for an effect."""
    return client.call(
        "plugin_params", {**_target(channel, track, slot), "contains": contains, "limit": limit}, timeout=20
    )


@server.tool()
def fl_plugin_set(
    name: str,
    value: float,
    channel: int | None = None,
    track: int | None = None,
    slot: int | None = None,
) -> dict:
    """Set a plugin parameter found by its exact name, and return the old and new values.

    value goes from 0 to 1. Read the result's text field, since the scale of each parameter differs.
    """
    return client.call("plugin_set", {**_target(channel, track, slot), "name": name, "value": value}, timeout=20)


@server.tool()
def fl_plugin_presets(channel: int | None = None, track: int | None = None, slot: int | None = None) -> dict:
    """Report how many presets a plugin has."""
    return client.call("plugin_presets", _target(channel, track, slot))


@server.tool()
def fl_plugin_preset_step(
    direction: str, channel: int | None = None, track: int | None = None, slot: int | None = None
) -> dict:
    """Move to the next or previous preset. This replaces the plugin's current settings."""
    return client.call("plugin_preset_step", {**_target(channel, track, slot), "direction": direction})


@server.tool()
def fl_pad_map(channel: int) -> list:
    """Read which MIDI note triggers each pad of an FPC channel."""
    return client.call("pad_map", {"channel": channel})


@server.tool()
def fl_queue_notes(notes: list[dict], expect_notes: int) -> dict:
    """Queue notes for the ClaudeBridge piano roll script.

    Each note has pitch (0-127), start and length in beats, and velocity from 0 to 1. expect_notes is how many
    notes the target channel has now, from fl_queue_read. The script refuses if the piano roll shows another
    count, because FL gives no way to read which channel it's showing.
    """
    for i, note in enumerate(notes):
        if not 0 <= int(note["pitch"]) <= 127 or float(note["start"]) < 0 or float(note["length"]) <= 0:
            raise ValueError(f"note {i} is out of range")
        if not 0 <= float(note.get("velocity", 0.8)) <= 1:
            raise ValueError(f"note {i} has a velocity outside 0 to 1")
    return {
        "request": client.queue_piano_roll("add_notes", {"notes": notes}, expect_notes),
        "next": "run ClaudeBridge in the piano roll",
    }


@server.tool()
def fl_queue_clear(expect_notes: int) -> dict:
    """Queue removing every note from the open piano roll. Ctrl+Z in FL undoes it.

    expect_notes works as in fl_queue_notes.
    """
    return {
        "request": client.queue_piano_roll("clear", expect_notes=expect_notes),
        "next": "run ClaudeBridge in the piano roll",
    }


@server.tool()
def fl_queue_read() -> dict:
    """Queue reading the notes of the open piano roll. Collect them with fl_piano_roll_result."""
    return {"request": client.queue_piano_roll("read"), "next": "run ClaudeBridge in the piano roll"}


@server.tool()
def fl_piano_roll_result(request: str) -> dict:
    """Return the outcome of a queued action, or say that the script hasn't run yet."""
    result = client.piano_roll_result(request)
    return {"done": False} if result is None else {"done": True, "result": result}


@server.tool()
def fl_piano_roll_run(channel: int, request: str) -> dict:
    """Apply a queued action to a channel without clicking, by pressing FL's Ctrl+Alt+Y.

    The shortcut repeats the last piano roll script, so ClaudeBridge must have been the last one run from
    Tools > Scripts in this FL session. It sends keys, so it refuses to run unless FL is the active window.
    """
    client.focus_piano_roll(channel)
    hotkey.run_last_script()
    result = client.piano_roll_result(request, timeout=3)
    if result is None:
        raise ValueError("ClaudeBridge didn't run. Start it once from Tools > Scripts in the piano roll")
    return result


@server.tool()
def fl_render(project: str, output: str) -> dict:
    """Render a saved .flp to a WAV with FL closed. FL opens by itself, exports and closes."""
    return {"output": output, "bytes": render.render(project, output)}


def main():
    server.run()


if __name__ == "__main__":
    main()
