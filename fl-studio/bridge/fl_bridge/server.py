"""MCP tools for controlling FL Studio from Claude Code."""

import re
import time

from mcp.server.fastmcp import FastMCP

from . import client, midifile, render, window
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
    position: int | None = None,
) -> dict:
    """Set a plugin parameter found by its exact name, and return the old and new values.

    value goes from 0 to 1. Read the result's text field, since the scale of each parameter differs. When several
    parameters share the name, as the On/Off of each module in a Kontakt instrument, pass the position that
    fl_plugin_params lists for the one wanted. The name must still match the parameter at that position.
    """
    args = {**_target(channel, track, slot), "name": name, "value": value}
    if position is not None:
        args["position"] = position
    return client.call("plugin_set", args, timeout=20)


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
    """Save PNGs of FL's main window, any open menu and FL's other windows, without touching the screen.

    Works behind other windows, not while minimized. region is [x, y, width, height] in the main window, for reading
    small controls. Pixels in the main capture are the coordinates fl_click takes, unless a region was cut. Plugin
    menus and dialogs come as popup-N with their screen position, which a dialog blocking FL also shows.
    """
    return window.capture(folder, tuple(region) if region else None)


@server.tool()
def fl_click(x: int, y: int, button: str = "left", focus: bool = False, expect: str | None = None) -> dict:
    """Click a point of the main window without moving the mouse. button is left or right.

    x and y come from an fl_capture of the whole window. A click on the Playlist grid paints a clip, and a click on an
    FL menu item only closes the menu, so use fl_menu_keys there. A point inside a popup from fl_capture goes to it,
    which is how a row of a plugin's menu is chosen. focus brings FL to the front first and takes the keyboard from
    the program in use. Menus drawn with JUCE, as in EZdrummer 3 and EZbass, close as soon as FL leaves the front, so
    pass focus both to open one and to click its row. expect is part of the class of the window that should be under
    the point, such as JUCE for a Toontrack plugin or TEventEditForm for the piano roll. Without a match nothing is
    clicked, so a closed plugin window can't let a click through to the Playlist, where it would paint a clip.
    """
    return window.click(x, y, button, focus, expect)


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


EFFECT_SLOTS = 10


def effect_added(before, after):
    """Return the one effect that appeared in the first empty slot, or raise if anything else changed.

    before and after are a track's effect lists, [{"slot", "plugin"}]. Every effect of before must still be in its
    slot with the same name, so an effect that replaced another is caught.
    """
    old = {e["slot"]: e["plugin"] for e in before}
    new = {e["slot"]: e["plugin"] for e in after}
    changed = [s for s in old if new.get(s) != old[s]]
    if changed:
        raise client.BridgeError(f"slots {changed} changed: {before} became {after}")
    added = [s for s in new if s not in old]
    first_free = min(s for s in range(EFFECT_SLOTS) if s not in old)
    if added != [first_free]:
        raise client.BridgeError(f"expected one new effect in slot {first_free}, got {added}: {after}")
    return {"slot": first_free, "plugin": new[first_free]}


def _mixer_effects():
    """Effects of every mixer track that has any, keyed by track."""
    return {row["track"]: row["effects"] for row in client.call("mixer_list") if row["effects"]}


def other_tracks_changed(before, after, track):
    """Tracks other than track whose effects differ between two _mixer_effects snapshots."""
    return sorted(t for t in set(before) | set(after) if t != track and before.get(t, []) != after.get(t, []))


@server.tool()
def fl_mixer_add_effect(x: int, y: int, track: int) -> dict:
    """Load the effect at a row of the browser into the first empty slot of a mixer track, and return the slot.

    x and y come from fl_capture, as for fl_load_plugin. FL sends a browser effect to the track of the selected
    channel, or into the slot of a plugin whose window is open, replacing it, even with the keyboard on the piano
    roll. So a channel feeding the track must exist (point one at it with fl_channel_set), every plugin window is
    closed first (the plugins stay loaded), and the new effect's window is closed after. Every track is read before
    and after. The call fails if the track is full, if the row isn't an effect, if another track changed, or if
    anything but one new effect in the first empty slot appeared. FL keeps no undo for this, so a failure names what
    changed, and fl_mixer_remove_effect can take a wrong effect out.
    """
    feeding = [c for c in client.call("channel_list") if c["track"] == track]
    if not feeding:
        raise ValueError(f"no channel feeds mixer track {track}. Point one at it with fl_channel_set first")
    before = _mixer_effects()
    if len(before.get(track, [])) >= EFFECT_SLOTS:
        raise ValueError(f"mixer track {track} has no empty slot")
    state = client.focus_piano_roll(feeding[0]["channel"])
    window.close_plugin_forms()
    if not state["caption"].startswith("Piano roll"):
        raise client.BridgeError(f"the focus stayed on {state['caption']!r}, which could be replaced. Nothing was sent")
    try:
        after = window.load_effect(x, y, _mixer_effects)
    except window.WindowError:
        after = _mixer_effects()
        changed = other_tracks_changed(before, after, track)
        if changed:
            raise client.BridgeError(f"FL changed tracks {changed} instead: {after}") from None
        raise
    time.sleep(client.SETTLE_S)
    window.close_plugin_forms()
    changed = other_tracks_changed(before, after, track)
    if changed:
        raise client.BridgeError(f"FL changed tracks {changed} instead of {track}: {after}")
    return {
        "track": track,
        "via_channel": feeding[0]["channel"],
        **effect_added(before.get(track, []), after.get(track, [])),
    }


def effect_form_id(track, slot):
    """The id ui.getFocusedFormID gives a mixer effect's window."""
    return ((track << 6) + slot) << 16


@server.tool()
def fl_mixer_remove_effect(track: int, slot: int) -> dict:
    """Delete the effect in a slot of a mixer track and return the track's effects after.

    The API can't remove a plugin, so this opens the effect's window (mixer.focusEditor), checks that the focused
    window is that effect, and chooses Delete in the window's menu and Ok in the Confirm box. Every other plugin
    window is closed first. Every track is read before and after, and the call fails unless only that slot emptied.
    """
    before = _mixer_effects()
    if slot not in {e["slot"] for e in before.get(track, [])}:
        raise ValueError(f"mixer track {track} has no effect in slot {slot}")
    window.close_plugin_forms()
    focused = client.call("effect_editor", {"track": track, "slot": slot})
    if focused["id"] != effect_form_id(track, slot):
        window.close_plugin_forms()
        raise client.BridgeError(f"the window that opened is {focused}, not track {track} slot {slot}. Nothing deleted")
    forms = window.plugin_forms()
    if len(forms) != 1:
        window.close_plugin_forms()
        raise client.BridgeError(f"expected one plugin window open, found {len(forms)}. Nothing deleted")
    window.delete_plugin_form(forms[0])
    time.sleep(client.SETTLE_S)
    after = _mixer_effects()
    want = {t: [e for e in effects if not (t == track and e["slot"] == slot)] for t, effects in before.items()}
    want = {t: e for t, e in want.items() if e}
    if after != want:
        raise client.BridgeError(f"expected only track {track} slot {slot} gone, got {after}")
    return {"track": track, "effects": after.get(track, [])}


@server.tool()
def fl_export(output: str, overwrite: bool = False) -> dict:
    """Export the project open in FL to a WAV, from memory, with FL staying open and behind other windows.

    output is an absolute path. An existing file is refused unless overwrite is true. Song mode exports the
    arrangement and pattern mode the current pattern, and song_mode in the answer says which. The export goes
    through FILE > Export > Wave file with FL and its dialogs invisible.
    """
    song_mode = client.call("project")["song_mode"]
    return {"output": output, "bytes": window.export_wav(output, overwrite), "song_mode": song_mode}


def _project_state():
    project = client.call("project")
    channels = client.call("channel_list", timeout=10)
    patterns = client.call("pattern_list", {"last": max(project["patterns"], 1) + 1})["patterns"]
    return {"project": project, "channels": channels, "patterns": patterns}


@server.tool()
def fl_set_ppq(ppq: int) -> dict:
    """Set the project's timebase (PPQ) in Options > Project general settings, and read it back.

    Use 960 before importing MIDI with fine timing. At FL's default of 96 one tick is about 6 ms at 100 BPM, and an
    import rounds every note to it. ppq is one of 24, 48, 72, 96, 120, 144, 168, 192, 384, 768 or 960.
    """
    before = client.call("project")["ppq"]
    window.set_ppq(before, ppq)
    after = client.settled("project", {}, check={"ppq": ppq})["ppq"]
    return {"before": before, "after": after}


DEFAULT_PATTERN_NAME = re.compile(r"Pattern \d+")


def import_refusal(state):
    """Return why an import could change data the project already holds, or None when it looks empty.

    FL's import reuses channels from channel 0 on and renames them, so only one channel without a plugin and
    patterns that all keep their default name and length count as empty. A sample loaded in that channel isn't
    visible to the API, which is the case this check can't see.
    """
    channels, patterns = state["channels"], state["patterns"]
    if len(channels) > 1:
        return f"the project has {len(channels)} channels, which the import would rename and reuse"
    if channels and channels[0]["plugin"] is not None:
        return f"channel 0 holds {channels[0]['plugin']}, which the import would rename and reuse"
    used = [p["name"] for p in patterns if not DEFAULT_PATTERN_NAME.fullmatch(p["name"]) or p["length"] != 16]
    if used:
        return f"patterns {used} hold data, and the import would rename the channel their notes belong to"
    return None


@server.tool()
def fl_import_midi(
    path: str,
    allow_existing_channels: bool = False,
    realign_events: bool = False,
    import_time_signatures: bool = True,
    import_zero_velocity: bool = False,
) -> dict:
    """Import a MIDI file into the open project, into a new empty pattern, and report what changed.

    Never starts a new project, so the project's PPQ stays. FL's import reuses the channels from channel 0 on,
    renaming them after the MIDI tracks, so a project that doesn't look empty is refused unless
    allow_existing_channels is true. The file is checked before anything changes. Notes go to the current pattern, so
    an unused pattern after the last one is selected first. Every option of the import form is set, none is left to
    FL's previous state. FL rounds the MIDI tempo to a whole BPM, so set the tempo afterwards with fl_set_tempo.
    Returns the project state before and after, the options read on the form, the new pattern and warnings. A
    warning means another pattern changed, so stop and look before going on.
    """
    midi = midifile.check(path)
    before = _project_state()
    refusal = import_refusal(before)
    if refusal and not allow_existing_channels:
        raise ValueError(f"{refusal}. Import into an empty project, or pass allow_existing_channels")
    target = before["project"]["patterns"] + 1
    client.call("pattern_select", {"index": target})
    client.settled("project", {}, check={"current_pattern": target})
    options = window.import_midi(
        path,
        {
            "start_new_project": False,
            "realign_events": realign_events,
            "import_time_signatures": import_time_signatures,
            "one_channel_per_track": True,
            "set_mixer_tracks": True,
            "import_zero_velocity": import_zero_velocity,
        },
    )
    after = _project_state()
    if after["project"]["ppq"] != before["project"]["ppq"]:
        raise client.BridgeError(f"the PPQ changed from {before['project']['ppq']} to {after['project']['ppq']}")
    untouched = [p for p in before["patterns"] if p["index"] != target]
    changed = [p for p in untouched if p not in after["patterns"]]
    warnings = [f"pattern {p['index']} ({p['name']}) changed during the import" for p in changed]
    return {
        "pattern": target,
        "midi": midi,
        "options": options,
        "before": before,
        "after": after,
        "other_patterns_changed": changed,
        "warnings": warnings,
    }


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
