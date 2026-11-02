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
