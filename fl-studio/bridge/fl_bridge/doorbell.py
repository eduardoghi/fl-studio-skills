"""Wakes the FL Studio script with one MIDI message through a virtual cable.

Talks to winmm directly, which keeps the MIDI libraries out of the dependencies.
"""

import ctypes
import os
import sys
from ctypes import wintypes

CONTROL_CHANGE_CHANNEL_16 = 0xBF
TRIGGER_CC = 110
TRIGGER_VALUE = 127
DEFAULT_PORT = "FL MCP"


class DoorbellError(Exception):
    pass


class MidiOutCaps(ctypes.Structure):
    _fields_ = [
        ("wMid", wintypes.WORD),
        ("wPid", wintypes.WORD),
        ("vDriverVersion", wintypes.UINT),
        ("szPname", wintypes.WCHAR * 32),
        ("wTechnology", wintypes.WORD),
        ("wVoices", wintypes.WORD),
        ("wNotes", wintypes.WORD),
        ("wChannelMask", wintypes.WORD),
        ("dwSupport", wintypes.DWORD),
    ]


def trigger_message():
    """Return the short MIDI message, with status, data1 and data2 from the low byte up."""
    return CONTROL_CHANGE_CHANNEL_16 | (TRIGGER_CC << 8) | (TRIGGER_VALUE << 16)


def port_names(winmm):
    names = []
    for device in range(winmm.midiOutGetNumDevs()):
        caps = MidiOutCaps()
        if winmm.midiOutGetDevCapsW(device, ctypes.byref(caps), ctypes.sizeof(caps)) == 0:
            names.append(caps.szPname)
    return names


def find_port(names, wanted):
    """Return the position of the first port whose name contains wanted."""
    for position, name in enumerate(names):
        if wanted.lower() in name.lower():
            return position
    raise DoorbellError(f"no MIDI port named {wanted!r}. Is loopMIDI running? Found: {names}")


def ring():
    if sys.platform != "win32":
        raise DoorbellError("the doorbell only supports Windows")
    winmm = ctypes.WinDLL("winmm")
    wanted = os.environ.get("FL_BRIDGE_MIDI_PORT") or DEFAULT_PORT
    names = port_names(winmm)
    device = find_port(names, wanted)
    handle = wintypes.HANDLE()
    status = winmm.midiOutOpen(ctypes.byref(handle), device, None, None, 0)
    if status != 0:
        raise DoorbellError(f"could not open MIDI port {names[device]!r}, winmm error {status}")
    try:
        status = winmm.midiOutShortMsg(handle, trigger_message())
    finally:
        winmm.midiOutClose(handle)
    if status != 0:
        raise DoorbellError(f"could not send to {names[device]!r}, winmm error {status}")
    return names[device]
