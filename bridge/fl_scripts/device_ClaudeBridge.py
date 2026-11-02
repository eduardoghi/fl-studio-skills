# name=Claude Bridge
# url=https://github.com/eduardoghi/fl-studio-skills
"""Runs requests from the fl-bridge server inside FL Studio.

The server writes request.json next to this file and sends CC 110 on MIDI
channel 16 through a virtual cable. This script answers in response.json.

FL Studio 26.1.4 only lets a script open files in its own folder and blocks
os.rename, so the mailbox lives here and responses are written in place. The
server retries when it reads a partial file. OnMidiMsg does the work because
OnIdle didn't run for a script with no port number.
"""

import json
import os
import time

import channels
import general
import midi
import mixer
import patterns
import plugins
import transport
import ui

BRIDGE_DIR = os.getcwd()  # FL loads the script with its own folder as the cwd.
REQUEST_FILE = os.path.join(BRIDGE_DIR, "request.json")
RESPONSE_FILE = os.path.join(BRIDGE_DIR, "response.json")
TRIGGER_CC = 110
TRIGGER_CHANNEL = 15
POLL_EVERY_S = 0.5
VERSION = "0.1.0"
EFFECT_SLOTS = 10
GENERATOR_SLOT = -1

_last_id = None
_last_poll = 0.0


def OnInit():
    print("Claude Bridge " + VERSION + " ready. Mailbox: " + BRIDGE_DIR)


def OnMidiMsg(event):
    if event.midiId == midi.MIDI_CONTROLCHANGE and event.midiChan == TRIGGER_CHANNEL and event.data1 == TRIGGER_CC:
        event.handled = True
        _serve()


def OnIdle():
    global _last_poll
    now = time.time()
    if now - _last_poll >= POLL_EVERY_S:
        _last_poll = now
        _serve()


def _serve():
    global _last_id
    try:
        with open(REQUEST_FILE) as f:
            request = json.load(f)
    except (FileNotFoundError, ValueError):
        return  # Nothing waiting, or the server is still writing.
    request_id = request.get("id")
    if not request_id or request_id == _last_id:
        return
    _last_id = request_id
    handler = HANDLERS.get(request.get("command"))
    if handler is None:
        _respond(request_id, error="unknown command " + repr(request.get("command")))
        return
    try:
        _respond(request_id, result=handler(request.get("params") or {}))
    except Exception as exc:  # noqa: BLE001 - FL raises SystemError and RuntimeError, and the server must see them.
        _respond(request_id, error=type(exc).__name__ + ": " + str(exc))


def _respond(request_id, result=None, error=None):
    payload = {"id": request_id, "ok": error is None, "result": result, "error": error}
    try:
        with open(RESPONSE_FILE, "w") as f:
            json.dump(payload, f)
    except Exception as exc:  # noqa: BLE001 - A blocked file raises SystemError, and this is the only place to show it.
        print("Claude Bridge: could not write the response: " + repr(exc))


def _target(params):
    """Return plugins.* (index, slot) for a channel instrument or a mixer effect."""
    if params.get("channel") is not None:
        return int(params["channel"]), GENERATOR_SLOT
    return int(params["track"]), int(params["slot"])


def _require_plugin(index, slot):
    if not plugins.isValid(index, slot):
        raise ValueError("no plugin at index " + str(index) + ", slot " + str(slot))


def _named_params(index, slot):
    """Yield (position, name) for real parameters. VSTs report thousands of empty ones."""
    for i in range(plugins.getParamCount(index, slot)):
        name = plugins.getParamName(i, index, slot)
        if name and name.strip() and not name.strip().startswith("?"):
            yield i, name


def _is_placeholder(name):
    """Recognize unassigned VST slots such as `Param 12` and `5. `, and the MIDI entries FL adds to every VST."""
    name = name.strip()
    if name.startswith("MIDI CC #") or (name.startswith("MIDI Channel ") and name.endswith(" Aftertouch")):
        return True
    if name.endswith(".") and name[:-1].isdigit():
        return True
    return name.startswith("Param ") and name[6:].isdigit()


def _param_row(i, name, index, slot):
    return {
        "name": name,
        "value": round(plugins.getParamValue(i, index, slot), 4),
        "text": plugins.getParamValueString(i, index, slot).strip(),
    }


def _find_param(index, slot, wanted):
    """Find a parameter by exact name, since indexes differ between plugins."""
    matches = [(i, n) for i, n in _named_params(index, slot) if n.strip().lower() == wanted.strip().lower()]
    if not matches:
        raise ValueError("no parameter named " + repr(wanted))
    if len(matches) > 1:
        raise ValueError(repr(wanted) + " matches " + str(len(matches)) + " parameters")
    return matches[0][0]


def _tempo():
    # Project tempo comes back as BPM * 1000 on current builds.
    bpm = mixer.getCurrentTempo()
    return bpm / 1000.0 if bpm >= 1000 else bpm


def _h_ping(params):
    return {"version": VERSION, "api": general.getVersion()}


def _h_project(params):
    return {
        "bpm": _tempo(),
        "playing": bool(transport.isPlaying()),
        "song_mode": bool(transport.getLoopMode()),
        "ppq": general.getRecPPQ(),
        "channels": channels.channelCount(),
        "current_pattern": patterns.patternNumber(),
        "patterns": patterns.patternCount(),
    }


def _h_transport(params):
    action = params["action"]
    if action == "play" and not transport.isPlaying():
        transport.start()
    elif action == "stop":
        transport.stop()
    elif action not in ("play", "stop"):
        raise ValueError("action must be play or stop")
    return {"playing": bool(transport.isPlaying())}


def _h_set_tempo(params):
    general.processRECEvent(midi.REC_Tempo, int(float(params["bpm"]) * 1000), midi.REC_Control | midi.REC_UpdateControl)
    return {"bpm": _tempo()}


def _track_row(track):
    return {
        "track": track,
        "name": mixer.getTrackName(track),
        "volume": round(mixer.getTrackVolume(track), 4),
        "pan": round(mixer.getTrackPan(track), 4),
        "muted": bool(mixer.isTrackMuted(track)),
        "soloed": bool(mixer.isTrackSolo(track)),
        "effects": [
            {"slot": slot, "plugin": plugins.getPluginName(track, slot)}
            for slot in range(EFFECT_SLOTS)
            if plugins.isValid(track, slot)
        ],
    }


def _tracks():
    # trackCount() also counts a last entry that isn't a real track, and FL warns when it's read.
    return range(mixer.trackCount() - 1)


def _h_mixer_list(params):
    rows = [_track_row(track) for track in _tracks()]
    return [r for r in rows if r["track"] == 0 or r["effects"] or not r["name"].startswith("Insert ")]


def _h_mixer_set(params):
    track = int(params["track"])
    if params.get("volume") is not None:
        mixer.setTrackVolume(track, float(params["volume"]))
    if params.get("pan") is not None:
        mixer.setTrackPan(track, float(params["pan"]))
    if params.get("muted") is not None and bool(mixer.isTrackMuted(track)) != bool(params["muted"]):
        mixer.muteTrack(track)
    if params.get("name") is not None:
        mixer.setTrackName(track, str(params["name"]))
    if params.get("color") is not None:
        mixer.setTrackColor(track, int(params["color"]))
    return _track_row(track)


def _h_mixer_solo(params):
    track = int(params["track"])
    if bool(mixer.isTrackSolo(track)) != bool(params["soloed"]):
        mixer.soloTrack(track)
    return _track_row(track)


def _h_mixer_peaks(params):
    tracks = _tracks() if params.get("track") is None else [int(params["track"])]
    rows = [{"track": t, "left": mixer.getTrackPeaks(t, 0), "right": mixer.getTrackPeaks(t, 1)} for t in tracks]
    return [r for r in rows if r["left"] or r["right"]]


def _channel_row(channel):
    return {
        "channel": channel,
        "name": channels.getChannelName(channel),
        "volume": round(channels.getChannelVolume(channel), 4),
        "pan": round(channels.getChannelPan(channel), 4),
        "muted": bool(channels.isChannelMuted(channel)),
        "track": channels.getTargetFxTrack(channel),
        "plugin": plugins.getPluginName(channel, GENERATOR_SLOT) if plugins.isValid(channel, GENERATOR_SLOT) else None,
    }


def _check_channel(channel):
    if not 0 <= channel < channels.channelCount():
        raise ValueError("no channel " + str(channel))


def _h_pattern_select(params):
    index = int(params["index"])
    if not 1 <= index <= patterns.patternMax():
        raise ValueError("no pattern " + str(index))
    patterns.jumpToPattern(index)
    return {}


def _h_pattern_name(params):
    patterns.setPatternName(int(params["index"]), str(params["name"]))
    return {"name": patterns.getPatternName(int(params["index"]))}


def _h_pattern_list(params):
    return {
        "current": patterns.patternNumber(),
        "patterns": [
            {"index": i, "name": patterns.getPatternName(i), "length": patterns.getPatternLength(i)}
            for i in range(1, int(params.get("last", 8)) + 1)
        ],
    }


def _h_channel_list(params):
    return [_channel_row(c) for c in range(channels.channelCount())]


def _h_channel_set(params):
    channel = int(params["channel"])
    _check_channel(channel)
    if params.get("volume") is not None:
        channels.setChannelVolume(channel, float(params["volume"]))
    if params.get("pan") is not None:
        channels.setChannelPan(channel, float(params["pan"]))
    if params.get("muted") is not None and bool(channels.isChannelMuted(channel)) != bool(params["muted"]):
        channels.muteChannel(channel)
    if params.get("track") is not None:
        channels.setTargetFxTrack(channel, int(params["track"]))
    if params.get("name") is not None:
        channels.setChannelName(channel, str(params["name"]))
    return _channel_row(channel)


def _h_channel_steps(params):
    channel = int(params["channel"])
    _check_channel(channel)
    for position, on in enumerate(params["steps"]):
        channels.setGridBit(channel, position, 1 if on else 0)
    return {"channel": channel, "steps": len(params["steps"]), "pattern": patterns.patternNumber()}


def _h_piano_roll_hide(params):
    """Hide the piano roll, which keeps its old channel while it stays open."""
    ui.hideWindow(midi.widPianoRoll)
    return {}


def _h_channel_select(params):
    # A separate request from the hide. Hiding in the same call put the selection back on the piano roll's channel.
    channel = int(params["channel"])
    _check_channel(channel)
    channels.selectOneChannel(channel)
    return {"channel": channel}


def _h_piano_roll_show(params):
    # A separate request from the hide, since FL applies interface changes after the call returns.
    ui.showWindow(midi.widPianoRoll)
    ui.setFocused(midi.widPianoRoll)
    return {}


def _h_focus_state(params):
    selected = channels.selectedChannel()
    return {
        "selected": selected,
        "name": channels.getChannelName(selected),
        "piano_roll_focused": bool(ui.getFocused(midi.widPianoRoll)),
        "caption": ui.getFocusedFormCaption(),
    }


def _h_plugin_params(params):
    index, slot = _target(params)
    _require_plugin(index, slot)
    needle = (params.get("contains") or "").lower()
    found = [(i, n) for i, n in _named_params(index, slot) if needle in n.lower()]
    shown = found
    if params.get("named_only", True):
        shown = [(i, n) for i, n in found if not _is_placeholder(n)]
    return {
        "plugin": plugins.getPluginName(index, slot),
        "count": len(shown),
        "hidden": len(found) - len(shown),
        "params": [_param_row(i, n, index, slot) for i, n in shown[: int(params.get("limit", 200))]],
    }


def _h_plugin_set(params):
    index, slot = _target(params)
    _require_plugin(index, slot)
    value = float(params["value"])
    if not 0.0 <= value <= 1.0:
        raise ValueError("value must be between 0 and 1")
    position = _find_param(index, slot, params["name"])
    before = plugins.getParamValue(position, index, slot)
    plugins.setParamValue(value, position, index, slot)
    row = _param_row(position, plugins.getParamName(position, index, slot), index, slot)
    row["before"] = round(before, 4)
    return row


def _h_plugin_presets(params):
    index, slot = _target(params)
    _require_plugin(index, slot)
    return {"plugin": plugins.getPluginName(index, slot), "presets": plugins.getPresetCount(index, slot)}


def _h_plugin_preset_step(params):
    index, slot = _target(params)
    _require_plugin(index, slot)
    if params["direction"] == "next":
        plugins.nextPreset(index, slot)
    elif params["direction"] == "previous":
        plugins.prevPreset(index, slot)
    else:
        raise ValueError("direction must be next or previous")
    return {"preset": plugins.getName(index, slot, midi.FPN_Preset)}


def _h_pad_map(params):
    channel = int(params["channel"])
    _require_plugin(channel, GENERATOR_SLOT)
    count = plugins.getPadInfo(channel, GENERATOR_SLOT, 0, 0)
    return [{"pad": pad, "note": plugins.getPadInfo(channel, GENERATOR_SLOT, 1, pad)} for pad in range(count)]


HANDLERS = {
    "ping": _h_ping,
    "project": _h_project,
    "transport": _h_transport,
    "set_tempo": _h_set_tempo,
    "mixer_list": _h_mixer_list,
    "mixer_set": _h_mixer_set,
    "mixer_solo": _h_mixer_solo,
    "mixer_peaks": _h_mixer_peaks,
    "channel_list": _h_channel_list,
    "channel_set": _h_channel_set,
    "channel_steps": _h_channel_steps,
    "pattern_select": _h_pattern_select,
    "pattern_name": _h_pattern_name,
    "pattern_list": _h_pattern_list,
    "channel_select": _h_channel_select,
    "piano_roll_hide": _h_piano_roll_hide,
    "piano_roll_show": _h_piano_roll_show,
    "focus_state": _h_focus_state,
    "mixer_get": lambda params: _track_row(int(params["track"])),
    "channel_get": lambda params: _channel_row(int(params["channel"])),
    "plugin_params": _h_plugin_params,
    "plugin_set": _h_plugin_set,
    "plugin_presets": _h_plugin_presets,
    "plugin_preset_step": _h_plugin_preset_step,
    "pad_map": _h_pad_map,
}
