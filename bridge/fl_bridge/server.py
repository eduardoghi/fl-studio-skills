"""MCP tools for controlling FL Studio from Claude Code."""

import re
import time

from mcp.server.fastmcp import FastMCP

from . import client, render, window
from .notes import check as check_notes  # fl_queue_notes has a parameter named notes.

server = FastMCP(
    "fl-bridge",
    instructions=(
        "Controls the project open in FL Studio. Every change is read back from FL. Nothing here takes the keyboard "
        "focus or moves the mouse, so FL can stay behind other windows, but not minimized when the tool needs its "
        "panels. While a tool drives FL's interface, FL and the menus and dialogs it opens are invisible and let clicks "
        "through, unless FL has the focus. If FL stays invisible after a failure, call fl_reveal. Nothing is saved "
        "from here. Piano roll actions are queued and need the ClaudeBridge script to run."
    ),
)


def _target(channel, track, slot):
    if channel is not None:
        return {"channel": channel}
    if track is None or slot is None:
        raise ValueError("pass channel for an instrument, or track and slot for a mixer effect")
    return {"track": track, "slot": slot}


def _loaded_channel(tries=40, sleep=time.sleep):
    """Return the last channel once its plugin finished opening. Until then FL reports only its wrapper."""
    row = client.call("channel_list", timeout=10)[-1]
    for _ in range(tries):
        if row["plugin"] != "Fruity Wrapper":
            break
        sleep(0.25)
        row = client.call("channel_list", timeout=10)[-1]
    return row


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
    name: str | None = None,
) -> dict:
    """Change a channel and return its state as FL reports it. track is the mixer track it feeds."""
    client.call(
        "channel_set",
        {"channel": channel, "volume": volume, "pan": pan, "muted": muted, "track": track, "name": name},
    )
    return client.settled("channel_get", {"channel": channel}, {"muted": muted, "track": track, "name": name})


@server.tool()
def fl_channel_steps(channel: int, pattern: str) -> dict:
    """Replace the step sequencer row of the current pattern. pattern has a 0 or 1 for each 16th note.

    Every step past the end of pattern is turned off, so a short pattern doesn't leave old steps behind.
    """
    if not re.fullmatch(r"[01]{1,64}", pattern):
        raise ValueError("pattern must be 1 to 64 characters of 0 and 1")
    return client.call("channel_steps", {"channel": channel, "steps": [c == "1" for c in pattern.ljust(64, "0")]})


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
    named_only: bool = True,
) -> dict:
    """List a plugin's named parameters. Pass channel for an instrument, or track and slot for an effect.

    named_only drops slots VSTs leave unassigned, such as Param 12, and the MIDI CC and aftertouch entries FL adds.
    hidden counts what it dropped. Pass False to reach them, for example to find a CC of a Kontakt instrument.
    """
    return client.call(
        "plugin_params",
        {**_target(channel, track, slot), "contains": contains, "limit": limit, "named_only": named_only},
        timeout=20,
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
def fl_queue_notes(notes: list[dict], expect: str) -> dict:
    """Queue notes for the ClaudeBridge piano roll script.

    Each note has pitch (0-127), start and length in beats, and velocity from 0 to 1. expect is the fingerprint
    of the target channel, from fl_queue_read. The script refuses if the piano roll holds other notes, because
    FL gives no way to read which channel it's showing.
    """
    check_notes(notes)
    return {
        "request": client.queue_piano_roll("add_notes", {"notes": notes}, expect),
        "next": "run ClaudeBridge in the piano roll",
    }


@server.tool()
def fl_queue_clear(expect: str) -> dict:
    """Queue removing every note from the open piano roll. Ctrl+Z in FL undoes it.

    expect works as in fl_queue_notes.
    """
    return {
        "request": client.queue_piano_roll("clear", expect=expect),
        "next": "run ClaudeBridge in the piano roll",
    }


@server.tool()
def fl_queue_discard() -> dict:
    """Drop a queued action that didn't run. Other queue tools refuse while one is waiting."""
    return {"discarded": client.discard_piano_roll()}


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
    """Apply a queued action to a channel by posting Ctrl+Alt+Y to the piano roll, without taking the focus.

    The shortcut repeats the last piano roll script, so ClaudeBridge must have been the last one run from
    Tools > Scripts in this FL session. Open that menu with fl_click and fl_menu_keys, and check the highlighted
    row with fl_capture before pressing enter, since another script would run instead.
    """
    client.focus_piano_roll(channel)
    window.run_last_script()
    result = client.piano_roll_result(request, timeout=3)
    if result is None:
        raise ValueError("ClaudeBridge didn't run. Start it once from Tools > Scripts in the piano roll")
    return result


@server.tool()
def fl_capture(folder: str | None = None, region: list[int] | None = None) -> list:
    """Save PNGs of FL's main window and any open menu, without touching the screen, and return their paths.

    Works behind other windows, not while minimized. region is [x, y, width, height] in the main window, for reading
    small controls. Pixels in the main capture are the coordinates fl_click takes, unless a region was cut.
    """
    return window.capture(folder, tuple(region) if region else None)


@server.tool()
def fl_click(x: int, y: int, button: str = "left") -> dict:
    """Click a point of the main window without moving the mouse. button is left or right.

    x and y come from an fl_capture of the whole window. A click on the Playlist grid paints a clip, and a click on a
    menu item only closes the menu, so use fl_menu_keys there.
    """
    return window.click(x, y, button)


@server.tool()
def fl_scroll(x: int, y: int, notches: int) -> dict:
    """Turn the mouse wheel over a point of the main window. Negative notches scroll down."""
    return window.scroll(x, y, notches)


@server.tool()
def fl_menu_keys(keys: list[str]) -> dict:
    """Send keys to the open menu. The keys are down, up, left, right, enter and escape.

    Disabled rows are skipped, so counts change with the state of the project. Check the highlighted row with
    fl_capture before sending enter. A menu opened by fl_click stays invisible until it is chosen or escaped, and
    fl_capture still sees it.
    """
    return window.menu_keys(keys)


@server.tool()
def fl_reveal() -> dict:
    """Close FL's open menus and make its windows visible and clickable again.

    For when FL stayed invisible because a tool stopped halfway. Returns how many menus were closed and the classes
    of the windows shown again.
    """
    return window.reveal()


@server.tool()
def fl_load_plugin(x: int, y: int) -> dict:
    """Open the plugin at a row of the browser in a new channel, and return that channel.

    x and y come from fl_capture. Another kind of row is refused. The new channel feeds the Master, so point it at a
    mixer track with fl_channel_set.
    """
    window.load_plugin(x, y, lambda: client.call("project")["channels"])
    return _loaded_channel()


@server.tool()
def fl_export(output: str, overwrite: bool = False) -> dict:
    """Export the project open in FL to a WAV, from memory, with FL staying open and behind other windows.

    output is an absolute path. An existing file is refused unless overwrite is true. Song mode exports the
    arrangement and pattern mode the current pattern, and song_mode in the answer says which. The export goes
    through FILE > Export > Wave file with FL and its dialogs invisible.
    """
    song_mode = client.call("project")["song_mode"]
    return {"output": output, "bytes": window.export_wav(output, overwrite), "song_mode": song_mode}


@server.tool()
def fl_render(project: str, output: str, overwrite: bool = False) -> dict:
    """Render a saved .flp to a WAV with FL closed. FL opens by itself, exports and closes.

    An existing output is refused unless overwrite is true.
    """
    return {"output": output, "bytes": render.render(project, output, overwrite=overwrite)}


def main():
    server.run()


if __name__ == "__main__":
    main()
