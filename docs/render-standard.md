# Render standard

Every render that will be measured, compared or kept as evidence follows one standard, so two renders differ only by
what was changed on purpose. Statements are marked **Documented** (the ReaScript reference in the REAPER SDK header,
`reaper_plugin_functions.h`) or **Tested** (REAPER 7.86 x64 on Windows 11, 2026-11-15).

## The standard

| Setting | Value | Why |
|---|---|---|
| Format | WAV, 32-bit float (`wav32f`) | peaks above 0 dBFS survive, and no rounding enters the samples |
| Sample rate | 44.1 kHz, the same as the project | no resampling in the render |
| Channels | 2 | |
| Bounds | explicit start and end (`RENDER_BOUNDSFLAG` 0) | the length doesn't depend on where items end |
| Tail | none unless asked, then `tail_ms` past the end | the length is always end minus start plus the tail |
| Dither and noise shaping | off (`RENDER_DITHER` 0) | they add noise that differs between renders |
| Postprocessing | all off (`RENDER_NORMALIZE` with the flag 4<<16) | normalization, limiting, fades, trimming and padding change levels and length |
| Speed | offline, full speed | the render doesn't depend on the audio device or on real time |

`render.configure` in the bridge sets all of these and reads them back. Format, sample rate, channels, start and end
are arguments, `tail_ms` and `fx_delay` are optional, and the rest is fixed.

## What `mps render` records

`mps render` reads the saved project before rendering, since the separate render process loads exactly that file. It
writes a record next to the first expected file (`<name>.render.json`), or where `--manifest` says, with

- the project's path and SHA-256
- the render settings found in the project, and how they differ from the standard
- the length the bounds and tail imply, used to check each file when `--seconds` isn't given
- every plugin with the binary found for it and the version that binary declares, and REAPER's version
- the process outcome (exit code, time, any dialog that ended it)
- each file's format, length, peak, RMS, the RMS of its last 100 ms (whether it ends in silence or cuts something
  short) and its SHA-256

A render counts as `ok` only when the process exited with code 0, every file checks out and the settings match the
standard. `--allow-nonstandard` accepts other settings, and the record still lists the differences.

A render writes over its target without asking. `mps render` refuses when a target file already exists, either the
one the project names or one passed with `--expect`, unless `--overwrite` is given.

## How the settings appear in a saved project

**Tested**, by setting each value through the API, saving, and reading the `.rpp` text. The render dialog showed the
same values.

| Project line | Holds |
|---|---|
| `RENDER_FILE` | the directory and the file name, joined when the name has no wildcards |
| `RENDER_FMT` | an unknown first field, the channels and the sample rate |
| `RENDER_1X` | the speed in the first field. 0 is "Offline render, full speed" in the dialog. Other values weren't mapped |
| `RENDER_RANGE` | the bounds flag, start, end, tail flag and tail in ms |
| `RENDER_STEMS` | `RENDER_SETTINGS` |
| `RENDER_QDELAY` | `RENDER_DELAY`, written only when it is set |
| `RENDER_DITHER`, `RENDER_NORMALIZE` | the API values in the first field |
| `<RENDER_CFG` | the format as base64, on the next line |
| `SAMPLERATE` | the project sample rate in the first field |

The speed has no documented API key (Documented, by its absence from the `GetSetProjectInfo` list). New projects
started at offline full speed, and a project with any other value is reported as off the standard.

## Waiting for samples to load

**Documented.** `RENDER_SETTINGS` flag 16<<16 delays the start of a render by `RENDER_DELAY` seconds, "to allow FX to
initialize and load samples". `render.configure` sets both when `fx_delay` is above 0.

**Tested.** The render process then shows a countdown dialog titled "Render Queue Delay" before rendering, which
`mps render` treats as progress and not as an error. With 1 s, the process took about 1 s longer and the file had the
expected length. Whether the delay changes anything for Kontakt is part of the investigation of exit code 0xC000000D.
