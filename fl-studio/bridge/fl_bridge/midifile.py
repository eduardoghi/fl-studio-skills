"""Checks a standard MIDI file before anything in FL is changed for an import."""

import struct
from pathlib import Path


class MidiFileError(ValueError):
    pass


def check(path):
    """Read the header and chunk list of a standard MIDI file and return its format, tracks and ticks per beat.

    Refuses a missing file, a file that isn't MIDI, SMPTE timing (FL places notes by ticks per beat) and a file
    whose track chunks don't match the header or run past its end.
    """
    path = Path(path)
    if not path.is_file():
        raise MidiFileError(f"{path} doesn't exist")
    data = path.read_bytes()
    if len(data) < 14 or data[:4] != b"MThd":
        raise MidiFileError(f"{path} isn't a standard MIDI file")
    length, fmt, ntracks, division = struct.unpack(">IHHH", data[4:14])
    if length < 6 or fmt not in (0, 1, 2):
        raise MidiFileError(f"{path} has an invalid MIDI header")
    if division & 0x8000:
        raise MidiFileError(f"{path} uses SMPTE timing, which FL's import doesn't place by beats")
    pos, tracks = 8 + length, 0
    while pos + 8 <= len(data):
        kind, size = data[pos : pos + 4], struct.unpack(">I", data[pos + 4 : pos + 8])[0]
        if pos + 8 + size > len(data):
            raise MidiFileError(f"{path} is truncated inside a {kind!r} chunk")
        tracks += kind == b"MTrk"
        pos += 8 + size
    if tracks != ntracks:
        raise MidiFileError(f"{path} declares {ntracks} tracks and holds {tracks}")
    return {"format": fmt, "tracks": ntracks, "ppq": division}
