# fl-bridge

MCP server that lets Claude Code work on the project open in FL Studio on Windows. Written after
FL Studio 26.1.4 broke the assumptions of an existing server, and tested against that build.

It depends on the MCP SDK only. The MIDI message goes straight through `winmm`.

## Setup

1. Install [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) and create a port named `FL MCP`.
   Set `FL_BRIDGE_MIDI_PORT` to use another name.
2. Copy the scripts into FL Studio's settings:

   ```sh
   python bridge/install.py
   ```

3. In FL, open Options > MIDI settings, select the port under Input and set its controller type to
   `Claude Bridge`. View > Script output should print `Claude Bridge 0.1.0 ready`.
4. Register the server:

   ```sh
   claude mcp add fl-bridge -- uv run --directory /path/to/fl-studio-skills/bridge fl-bridge
   ```

5. Run Tools > Scripts > ClaudeBridge once from any piano roll. `fl_piano_roll_run` repeats the last script with
   Ctrl+Alt+Y, which FL only enables after the first run of the session.

## What it can't do

- Load a plugin, create a channel, save the project or edit the Playlist. FL's scripting API offers none of these.
- Choose a preset by name. It can only step to the next or previous one.
- Render while FL is open. `fl_render` needs FL closed, uses what was last saved to disk and won't replace an existing
  WAV unless `overwrite` is set. It works on a copy next to the project, so relative sample paths still resolve.
- Undo a plugin change through FL. Parameter changes stay out of its history, so `fl_plugin_set` returns the old value.

## Writing notes safely

The piano roll can't say which channel it shows. Read the channel first, then pass the `fingerprint` of its notes as
`expect`, and the script refuses to write if it finds other notes. Each write returns the new fingerprint. Empty
channels share one fingerprint, as do channels with identical notes, so those can't be told apart.

The queue holds one action. A second one is refused until the first runs or `fl_queue_discard` drops it, and requests
from separate Claude Code sessions wait for each other.

`fl_piano_roll_run` sends keystrokes, so it refuses to run unless FL is the active window. If another piano roll
script was the last one used, the shortcut repeats that script. The call then fails, because ClaudeBridge didn't
report back, and the other script has already run.
