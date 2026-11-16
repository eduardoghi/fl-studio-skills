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
- With several REAPER instances open, pass `--instance`. `mps reaper instances` lists them with their heartbeat. A
  script that calls `mps.reaper.call` directly is pinned to one with the environment variable `MPS_REAPER_INSTANCE`.
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
| `item.add_audio` | `track`, `path`, `position` (seconds) | the item's GUID and length, for re-amping a rendered DI through effect chains |
| `midi.write` | `item`, `notes`, `ccs`, `replace` | every note and event read back |
| `midi.read` | `item` | notes and events |
| `fx.add` | `track`, `name`, `position` (optional) | the effect's index, GUID and name |
| `fx.delete` | `track`, `fx` | |
| `fx.params` | `track`, `fx`, `contains` (optional) | index, name, normalized value, displayed text, identifier |
| `fx.set_param` | `track`, `fx`, `param`, `value` | value before and after, and the displayed text |
| `fx.show` | `track`, `fx`, `show` | opens or hides the plugin window |
| `fx.state_get` | `track`, `fx` | the whole state (`vst_chunk`) and its length |
| `fx.state_set` | `track`, `fx`, `chunk` | whether the state read back identical |
| `fx.restore_fresh` | `track`, `fx`, `chunk`, `name` | writes the state into a new instance of the same binary, then deletes the old one |
| `render.configure` | `format`, `directory`, `pattern`, `start`, `end`, `srate`, `channels`, `tail_ms` and `fx_delay` (optional) | the settings read back and the files a render would write |

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
Set them once, store the whole state, and later projects take it back instead of repeating the clicks.

```text
mps state save --track <guid> --fx 0 states/                                  # <sha256>.b64 and <sha256>.json
mps state restore --track <guid> --fx 0 states/<sha256>.b64 --fresh "VST3i:Kontakt 8"
mps wav variation --reference orig_1.wav orig_2.wav orig_3.wav --candidate restored.wav
```

- `save` waits for the plugin to settle and records its binary version and the text of every parameter.
- `restore` refuses a file whose hash changed, writes the state (into a new instance with `--fresh`, through
  `fx.restore_fresh`, which deletes the old one only after the new one took the state), waits again and lists every
  parameter whose text differs from the record.
- `variation` judges renders of the restored state against the variation between repeated renders of the original.

A matching hash only says the file didn't change, matching parameter text is a partial check (some plugins report it
late or not at all), and only the render comparison shows the sound came back. How a state restores is a property of
each plugin and isn't assumed for another one. The `plugins` skill records what was tested per plugin, and
`docs/state-checks.md` has the measurements. Use `--fresh` by default, since it doesn't depend on what the running
instance held.

## Rendering

Renders follow the standard in `docs/render-standard.md` (32-bit float WAV, 44.1 kHz, stereo, explicit bounds, no
dither or postprocessing, offline at full speed, a load delay for instruments).

1. `render.configure` with `format` `wav32f`, `srate` 44100, `channels` 2, the bounds, `fx_delay` 5 when the project
   has an instrument plugin (samplers rendered silence without it) and, when a sound must ring out, `tail_ms`. It
   fixes dither and postprocessing off, and returns the settings and the `targets`.
2. `project.save`, since the render reads the saved file.
3. Render in a separate process, which leaves the open REAPER alone:

```text
mps render project.rpp --expect out.wav --samplerate 44100 --channels 2 --subtype FLOAT
```

- The render process opens the project with `reaper/mps_render.lua`, which waits for the project's tempo to apply,
  renders, waits 3 s (`--settle`) and quits normally. Quitting at once, as `-renderproject` does (`--mode
  renderproject`), crashed every process that had Kontakt loaded. The record's `process_check` confirms the render
  used the saved tempo. It starts with `MPS_ROLE=render`, so the bridge doesn't start in it.
- A dialog in the render process, such as a missing plugin, ends it in seconds with the dialog's text, instead of
  waiting for the timeout. The progress window doesn't count, and the `fx_delay` prompt is answered with the
  project's own delay.
- It refuses when a target file already exists, since a render writes over it without asking. Pass `--overwrite`
  only for a file that isn't kept as evidence.
- Each expected file is checked for presence, format, channels, signal, being newer than the render, and the length
  the saved bounds and tail imply (or `--seconds`).
- `ok` is true only when the files check out, the process exited with code 0 and the saved settings match the
  standard (`--allow-nonstandard` accepts others). A render whose process ended with another code reports
  `files_ok` and `abnormal_exit: true` apart, and isn't a normal success even with complete files.
- The record (`out.render.json` next to the file, or `--manifest`) keeps the project hash, the saved settings, the
  plugins with their binary versions, REAPER's version, the outcome and each file's facts and hash.
- Repeated renders of the same project can differ, from round robin samples or modulation (ValhallaVintageVerb with
  its default modulation never rendered the same twice). Before reading a difference between two versions as a
  change, render each a few times and judge them with `mps wav variation`, or turn the modulation off while comparing.

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
- Projects are built through the API. Writing `.rpp` text from a template was measured and not adopted
  (`docs/reaper-investigation.md`). Reading a saved project, as `mps render` does for its record, is fine.
