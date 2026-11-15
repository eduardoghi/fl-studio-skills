# REAPER as the execution layer

Why REAPER replaces FL Studio for programmatic music production, what its API offers, and how the existing REAPER
bridges compare. Each statement is marked **Documented** (official documentation or the program's own text, with no
test of ours), **Tested** (run here, see [poc-results.md](poc-results.md)), or **Reported** (third-party sources).

The tests ran on REAPER 7.86 x64 on Windows 11, with Kontakt 8.14.1 and WASAPI shared audio.

## What REAPER fixes compared with FL Studio

| Limit met in FL Studio | In REAPER |
|---|---|
| The scripting API couldn't save the project | `Main_SaveProjectEx` saves and renames the project (Documented, Tested) |
| Notes went through a piano roll script and a queue | `MIDI_InsertNote` and friends write and read notes directly (Documented, Tested) |
| No MIDI channel per note | every note has a channel (Documented, Tested), which Evolution's Channel-Based Strings uses to pick the string (Tested) |
| Loading a plugin needed clicks in the browser | `TrackFX_AddByName` with a type prefix and an insert position (Documented, Tested) |
| No access to a plugin's whole state | `vst_chunk` through `TrackFX_Get/SetNamedConfigParm` (Documented, Tested), track and item state chunks, `.RfxChain` files (Documented) |
| Exporting meant driving dialogs | render settings through `GetSetProjectInfo` and `GetSetProjectInfo_String`, and `reaper -renderproject` (Documented, Tested) |
| Binary project file | the `.rpp` project is text, with plugin states as base64 blocks (Tested) |

## API facts that shape the design

- **Documented.** `MIDI_InsertNote(take, selected, muted, startppq, endppq, chan, pitch, vel, noSort)`, `MIDI_InsertCC`,
  `MIDI_GetNote`, `MIDI_GetCC`, `MIDI_GetAllEvts` and `MIDI_SetAllEvts`, `MIDI_Sort`, and conversions between ticks,
  seconds and quarter notes.
- **Tested.** Positions are whole ticks (960 per quarter note by default), and `MIDI_InsertNote` truncates a
  fractional tick instead of rounding it, so the caller rounds.
- **Documented.** `TrackFX_AddByName` takes the prefixes `VST3:`, `VST2:`, `VST:`, `AU:`, `JS:`, `DX:` and `FXADD:`,
  and `instantiate <= -1000` inserts at position `-1000 - instantiate`. CLAP isn't in the documented prefix list.
- **Documented.** Parameters are read and written by index, normalized or raw, with `TrackFX_GetFormattedParamValue`
  for the displayed text, `TrackFX_GetParamIdent` for a stable identifier and `TrackFX_GetParamSectionName` for the
  VST3 unit. `TrackFX_FormatParamValueNormalized` only works with plugins that support the Cockos extensions.
- **Documented.** Presets are REAPER's own, `.vstpreset` files for VST3, the plugin's factory preset (index -2) and
  the default user preset (-1).
- **Documented.** Render keys include `RENDER_FILE`, `RENDER_PATTERN`, `RENDER_FORMAT` (base64 sink settings),
  `RENDER_SRATE`, `RENDER_CHANNELS`, `RENDER_BOUNDSFLAG`, `RENDER_STARTPOS`, `RENDER_ENDPOS`, `RENDER_TARGETS` (the
  files a render would write) and `RENDER_STATS`.
- **Documented** (from `reaper.exe` itself). Command line switches include `-renderproject file.rpp` (render and
  exit), `-newinst` and `-nonewinst`, `-new`, `-template`, `-saveas`, `-close[all][:save|:nosave][:exit]`,
  `-ignoreerrors`, `-nosplash`, `-cfgfile` and `-batchconvert`. Scripts given on the command line run in order, and
  `-nonewinst` runs them in the instance already open.
- **Documented.** Lua 5.4 and EEL2 are built in. Python needs a separately installed Python of the same bitness.
- **Not found.** The ReaScript reference doesn't mention ARA. No way was found for a script to start Melodyne's
  analysis, read its notes or drive SpectraLayers' unmixing (Reported, forum and vendor pages). Both are tools for a
  person in REAPER, and the automated pipeline keeps its own analysis.
- **Not found.** No host API loads a Kontakt `.nki` or snapshot. NI's instrument banks switch instruments by program
  change but live inside the saved state. The practical route is to set an instrument once and keep its state (Tested).

## Existing REAPER bridges

Reviewed by reading their code, without running them.

| Project | Transport | License | Verdict |
|---|---|---|---|
| bonfire-systems/reaper-mcp | python-reapy over the web interface | MIT | ideas only. No plugin state, MIDI one note at a time, no timeouts, unmaintained dependency |
| Oisub/reaper-mcp | file mailbox and Lua | none | ideas only. Arbitrary Lua as the main tool, no render, and no license to reuse code |
| wretcher207/reaper-daemon | file mailbox and Lua | MIT | ideas only. No per-effect state, no note deletion, render not checked |
| danishaft/reaper-mcp | file mailbox and Lua | MIT | ideas only. Master-only WAV renders, likely Windows rename bugs, inactive |
| TwelveTake-Studios/reaper-mcp | file mailbox and Lua | MIT | ideas only. Best render checks, but writes aren't atomic and plugin state can't be written |
| xDarkzx/Reaper-MCP | file mailbox and Lua | Apache-2.0 | ideas only. Safe Windows transport and read-back, but no render checks or per-effect state |
| python-reapy and forks | web interface | MIT | not used. Unmaintained (last release 2020) |

None writes a plugin's state, bulk MIDI with controllers read back, or verified renders with explicit settings, which
are the core of this project. The ideas taken from them are request files with unique ids, publishing by rename,
one undo block per command, reading back what changed, and the render checks.

## Building projects through the API or by writing RPP

The proof of concept builds every project through the API in a new project tab and saves it with
`Main_SaveProjectEx`. That keeps REAPER as the one writer of its format and lets every step be read back.

Writing RPP text directly has one advantage found so far (Tested). Through the API, each variant needs the plugin
loaded in the interactive instance (Kontakt took 1 to 6 s to settle) and relies on the plugin saving its own state
again, while a captured state could be written into an RPP file unchanged. That matters for large batches of
candidates, and is worth measuring before adopting it.

### Measured (Tested, `poc/p12_rpp_template.py`)

Four variants (two Kontakt states with Evolution, two `Mix` settings of ValhallaVintageVerb, one part of six notes)
were built through the API and written from a template made of the first API project, by swapping each plugin's whole
`<VST ...>` block captured from the API projects and the render file name.

| Question | Through the API | From the template |
|---|---|---|
| Time per variant | 3.0 to 3.3 s (the Kontakt restore and settling) | under 0.02 s, after capturing the blocks from projects the API built |
| Text | | identical to the API project, or differing only in item numbering, colors and Kontakt's state bytes, which change on every read |
| Loading | | no dialog, and the bridge read back both plugins and `Mix` at 50 % |
| Render | each about 13 s, with the 5 s load delay | the same |
| Sound | repeats differed by -4.5 to -7.0 dB | within the same spread, except two of four template renders that also differed near one note (unexplained) |
| A damaged Kontakt block | | the render process crashed (0xC0000005) with no file and no dialog |

The repeats differed because VintageVerb's modulation changes between renders (see `skills/plugins`), so this test
couldn't show sound equivalence more closely than that. With the render itself taking about four times as long as
building through the API, a template saves little per variant, needs the API anyway to capture each state, and turns
a damaged block into a crash. Projects stay built through the API. A template is worth measuring again for a batch
large enough that building time matters, with the modulation off.
