---
name: reaper
description: Drive REAPER from an agent through this repository's bridge and the mps command line, to build projects, write MIDI with a channel per note, load plugins, save and restore their state, and render in a separate process with checked files. Use when creating, editing or rendering a REAPER project, when a plugin's state must be kept or compared, or when a render needs to be trusted as evidence.
---

# REAPER through the mps bridge

A Lua script inside REAPER answers typed commands sent as files, and the `mps` command line sends them and renders.
It never runs Lua code sent in a request. What each statement rests on, and what was measured, is in
`docs/poc-results.md` and `docs/reaper-investigation.md`. Measured on REAPER 7.86 x64 and Windows 11.

## Setup

The bridge and the command line live in a checkout of this repository. Run `mps` with `uv run --project <checkout>`,
which keeps the current folder, so relative paths in arguments still point where you are.

```text
uv sync --project <checkout>
uv run --project <checkout> mps reaper install    # loads the bridge from Scripts/__startup.lua at every start
uv run --project <checkout> mps reaper start      # starts it in the REAPER already open
uv run --project <checkout> mps reaper call ping
```

`install` writes the checkout's path into `__startup.lua`, so move the checkout and the bridge stops loading.

## Calling commands

```text
mps reaper call <command> --args '{"...": ...}'
mps reaper call <command> --args-file args.json --out result.json
```

Every call prints JSON and exits with a code that says what happened.

| Code | Status | Meaning |
|---|---|---|
| 0 | `ok` | it ran |
| 1 | `error` | it ran and failed, or was refused, with the project unchanged unless the error says otherwise |
| 2 | | bad usage, such as invalid JSON |
| 3 | `not_started` | no bridge answered, or the request was withdrawn before it ran, so it can never run |
| 4 | `uncertain` | the bridge took it but didn't answer in time. Read the state back before repeating it |
| 5 | `expired` | it waited too long and was refused without running |

- Pass `--expect-project <path.rpp>` to any command that changes a project, so it is refused if another tab is in
  front.
- Each changing command is one undo step, and its answer says whether the project changed.
- With several REAPER instances open, pass `--instance`. `mps reaper instances` lists them with their heartbeat.
- Use `--args-file` for large arguments such as plugin states, which reach 2 MB.

## Commands

| Command | Arguments | Answer |
|---|---|---|
| `ping` | | instance, bridge and REAPER versions, project |
| `project.new_tab` | | opens an empty tab, leaving the tab in use alone |
| `project.open` | `path` | opens it in a new tab, without prompts |
| `project.save` | `path` (optional) | saves, and with `path` the project takes that name |
| `project.close_tab` | `path` | closes the tabs holding that file, refusing one with unsaved changes |
| `project.info` | | tempo, sample rate, tracks with their items and effects |
| `project.set_tempo` | `bpm`, `srate` (optional) | the values read back |
| `track.add` | `name`, `index` (optional) | the track with its GUID |
| `item.add_midi` | `track`, `start_qn`, `end_qn` | the item's GUID |
| `midi.write` | `item`, `notes`, `ccs`, `replace` | every note and event read back |
| `midi.read` | `item` | notes and events |
| `fx.add` | `track`, `name`, `position` (optional) | the effect's index, GUID and name |
| `fx.delete` | `track`, `fx` | |
| `fx.params` | `track`, `fx`, `contains` (optional) | index, name, normalized value, displayed text, identifier |
| `fx.set_param` | `track`, `fx`, `param`, `value` | value before and after, and the displayed text |
| `fx.show` | `track`, `fx`, `show` | opens or hides the plugin window |
| `fx.state_get` | `track`, `fx` | the whole state (`vst_chunk`) and its length |
| `fx.state_set` | `track`, `fx`, `chunk` | whether the state read back identical |
| `render.configure` | `format`, `directory`, `pattern`, `start`, `end`, `srate`, `channels` | the settings read back and the files a render would write |

Tracks and items are named by GUID. `fx` is the effect's index on the track or its GUID. `name` in `fx.add` takes a
type prefix, such as `VST3:Kontakt 8` or `JS:`. `format` is `wav16`, `wav24` or `wav32f`.

## MIDI

- Notes are `{"start_qn", "end_qn", "chan", "pitch", "vel"}`, with times in quarter notes from the project start,
  `chan` from 0 to 15 (0 is MIDI channel 1) and `vel` from 1 to 127.
- Events are `{"qn", "status", "chan", "msg2", "msg3"}`. Status `0xB0` (176) is a controller, `0xE0` (224) a pitch
  bend with the low 7 bits in `msg2`, and `0xC0` (192) a program change.
- Times are stored in whole ticks, 960 per quarter note. REAPER truncates a fractional tick, so the bridge rounds.
  Expect a time to read back within half a tick.
- A channel per note is what lets an instrument pick a string per channel, as Evolution's Channel-Based Strings does
  (see the `plugins` skill).

## Plugin state

Some plugin settings aren't host parameters, such as a Kontakt instrument or a setting deep in a library's menus.
Set them once, read the whole state with `fx.state_get`, and keep it as a file named by its SHA-256. Later projects
take it back with `fx.state_set` instead of repeating the clicks.

How a state restores is a property of each plugin and isn't assumed for another one. The `plugins` skill records what
was tested per plugin, such as Kontakt needing a fresh instance (delete, add again, then write) and ValhallaVintageVerb
restoring in place. Check a restore at the level the work needs. A matching hash only says the file didn't change,
matching parameter text is a partial check, and only a render compared with renders of the original state shows the
sound came back.

## Rendering

1. `render.configure` with explicit settings, and check the `targets` it returns.
2. `project.save`, since the render reads the saved file.
3. Render in a separate process, which leaves the open REAPER alone:

```text
mps render project.rpp --expect out.wav --seconds 12.48 --samplerate 44100 --channels 2 --subtype FLOAT
```

- The render process starts with `MPS_ROLE=render`, so the bridge doesn't start in it.
- A dialog in the render process, such as a missing plugin, ends it in seconds with the dialog's text, instead of
  waiting for the timeout.
- Each expected file is checked for presence, duration, format, channels, signal and being newer than the render.
- `ok` is true only when the files check out and the process exited with code 0. Renders of projects with Kontakt
  ended with code 0xC000000D with complete files. Such a render reports `files_ok: true` and `abnormal_exit: true`,
  and isn't a normal success until the cause is understood.
- Use `wav32f` at 44.1 kHz in stereo for anything that will be measured, so peaks above 0 dBFS aren't clipped.
  `render.configure` doesn't set dither, normalization or tails yet, and renders up to `end` with no tail added.
- Repeated renders of the same project can differ, from round robin samples or modulation. Before reading a
  difference between two versions as a change, render one of them a few times and compare with `mps wav compare`,
  which reports the lag, the residual and whether the files are identical.

## Plugin windows

Use the interface only when no API, MIDI, preset or saved state reaches the setting. `mps.windows` finds dialogs,
captures windows and sends clicks, file names and keys without moving the mouse. Some controls only answer real mouse
input, which moves the user's pointer, so ask before using it. In REAPER that was Kontakt's own menu and the scroll bar
of Evolution's SETUP list.

Deferred scripts kept running while a plugin or REAPER showed a modal dialog, so the bridge still answers then.

## Known limits

- No host API loads a Kontakt `.nki` or snapshot. Load it once through the interface and keep the state.
- The scripting API has no ARA access, so Melodyne and SpectraLayers are tools for a person working in REAPER, and
  their results come back as exported files.
- Writing an `.rpp` file directly instead of building through the API wasn't adopted. The comparison is open in
  `docs/reaper-investigation.md`.
