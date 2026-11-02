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
   Ctrl+Alt+Y, which FL only enables after the first run of the session. An agent can do this with `fl_click` on the
   piano roll's menu arrow, `fl_menu_keys` and `fl_capture`.

After changing a file in `fl_scripts`, run `install.py` again and reload the script in FL. A running script keeps the
old code, so a new parameter such as `name` in `fl_channel_set` fails its read back until then.

## What it can't do

- Save the project or edit the Playlist. FL's scripting API offers neither.
- Choose a preset by name. It can only step to the next or previous one.
- Undo a plugin change through FL. Parameter changes stay out of its history, so `fl_plugin_set` returns the old value.

## Working behind other windows

Nothing here takes the keyboard focus or moves the mouse, so FL can sit behind other programs while someone types in
them. Menus and dialogs still appear above other windows for a moment, because FL opens them that way.

- `fl_capture` saves PNGs of the main window and any open menu. Coordinates in a full capture are what `fl_click` and
  `fl_scroll` take.
- `fl_click` also works inside a plugin's panel. A click on the Playlist grid paints a clip, so don't use it there.
- `fl_menu_keys` chooses from an open menu. Read the highlighted row with `fl_capture` before sending `enter`.
- `fl_load_plugin` opens a browser row in a new channel, and refuses a row that isn't a plugin.
- `fl_export` exports the open project, unsaved changes included, and FL stays open. `fl_render` is for when FL is
  closed. It uses what was last saved to disk and works on a copy next to the project, so relative sample paths still
  resolve. Both refuse to replace a WAV unless `overwrite` is set.

The ones that touch FL's panels need it visible behind other windows, not minimized. Dragging doesn't work this way,
because FL starts the drag and never drops. These tools only support Windows.

## Writing notes safely

The piano roll can't say which channel it shows. Read the channel first, then pass the `fingerprint` of its notes as
`expect`, and the script refuses to write if it finds other notes. Each write returns the new fingerprint. Empty
channels share one fingerprint, as do channels with identical notes, so those can't be told apart.

The queue holds one action. A second one is refused until the first runs or `fl_queue_discard` drops it, and requests
from separate Claude Code sessions wait for each other.

`fl_piano_roll_run` posts its shortcut to the piano roll, so FL doesn't need to be the active window. If another piano
roll script was the last one used, the shortcut repeats that script. The call then fails, because ClaudeBridge didn't
report back, and the other script has already run.
