# ValhallaVintageVerb

Everything here is observed on version 4.0.5. The manual wasn't read for this note.

## Watch out

`Mix` starts at 100%. On an insert that removes the dry signal, so lower it first, or put the plugin on a send track
where 100% is what you want.

A default instance loads `Concert Hall` with `seventies` color, 4.00 s `Decay`, 100% `Size` and 20 ms `PreDelay`. The
panel describes that color as limited to a 10 kHz bandwidth, and `HighCut` starts at 8000 Hz, so the tail starts dark.
`LowCut` starts at 10 Hz, which lets low notes into the tail.

## Controls

These are the exact names in the API, and some differ from the panel. `BassFreq` on the panel is `BassXover`, and
`Early` and `Late` are `EarlyDiffusion` and `LateDiffusion`.

| Name in the API | Default |
|---|---|
| `Mix` | 100.0 % |
| `PreDelay` | 20.00 ms |
| `Decay` | 4.00 s |
| `Size` | 100.0 % |
| `Attack` | 50.0 % |
| `BassMult` | 1.50 X |
| `BassXover` | 300 Hz |
| `HighShelf` | -24.00 dB |
| `HighFreq` | 6000 Hz |
| `EarlyDiffusion` | 100.0 % |
| `LateDiffusion` | 100.0 % |
| `ModRate` | 2.53 Hz |
| `ModDepth` | 38.0 % |
| `HighCut` | 8000 Hz |
| `LowCut` | 10 Hz |
| `ColorMode` | seventies |
| `ReverbMode` | Concert Hall |
| `Bypass` | Off |

The plugin reports 162 entries, and the 144 after these are `MIDI CC #` slots that `fl_plugin_params` hides. These
were read through the bridge, but `fl_plugin_set` wasn't tried on them yet, so confirm the first change in the `text`
field of the answer.

## Saved state

Observed in REAPER 7.86. The state (`vst_chunk`) read the same bytes each time, and it restored exactly both into the
running instance and into a fresh one, with every displayed value back as saved. A project saved and opened in a new
REAPER process gave the same state byte for byte. So a hash of this plugin's state does compare configurations.

## Repeated renders differ

Observed in REAPER 7.86, rendering a tone through the default instance three times in separate processes. No two
renders were identical, with residuals of -5.0 to -16.4 dB between them, and the difference grew through each file.
With `ModDepth` at 0 the three renders were sample-identical. The modulation seems to start at a different phase each
time. Behind Kontakt, at `Mix` 50 %, repeats of one project differed by -4.5 to -7.0 dB.

So with modulation on, two renders of the same project don't match, and a comparison between versions has to use
several renders of each, or set `ModDepth` to 0 while comparing what comes before the reverb.
