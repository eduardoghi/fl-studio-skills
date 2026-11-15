# Fruity Delay 3

## Watch out

A new instance starts with `Output wet` at 100%, `Feedback level` at 62.5% and `Time` at `4:0` (observed), which is far
more delay than a background effect needs. Lower `Output wet` first.

`Feedback level` above 100% adds up on each repeat, and high `Feedback resonance` can do the same below 100% (manual).

Three parameters share the name `Distortion`, so the bridge refuses to set them by name.

## Controls

| Name in the API | What it does |
|---|---|
| `Output wet`, `Output dry` | Echo and dry levels. Dry at 0 leaves only the echo |
| `Time`, `Tempo sync` | With sync on, `Time` reads in steps and follows tempo changes |
| `Keep pitch` | On keeps echo pitch while `Time` changes. Off gives a tape-style pitch glide |
| `Delay type` | Mono, True Stereo, Ping pong or off. Off keeps the filter and distortion, for use as an effect |
| `Feedback level` | How much echo returns |
| `Feedback cutoff`, `Filter mode` | The filter sits in the loop, so each repeat gets darker with LP |
| `Rate reduction`, `Bits reduction` | Lo-fi noise and grain. At maximum they do nothing (manual) |
| `Modulation time`, `Modulation rate` | Wow and flutter on the repeats |
| `Diffusion level` | Smears echoes toward a reverb sound |
| `Output tone` | Left is lowpass, center is off, right is highpass |

## Values used

Dotted eighth at 95 BPM (`Time` `3:0`, raw value 0.1864), `Output wet` 22.5%, `Feedback level` 34.4% on a clean guitar.
A second guitar used `Time` `4:0`, `Output wet` 15% and `Feedback level` 28.1%, so the two echo patterns don't land
together.
