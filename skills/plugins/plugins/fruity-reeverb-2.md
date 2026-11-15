# Fruity Reeverb 2

## Watch out

Keep `Room size` and `Decay time` in proportion, with small rooms for short decays and large rooms for long ones (manual).

The mouse wheel moves these knobs in large steps, and eight to ten steps took `Wet level`, `Room size` and `Decay time`
to their minimum (observed). Set them through the bridge and read the `text` field.

On a send track, the manual says to use `Dry level` 0% and `Wet level` 100%.

## Controls

| Name in the API | What it does |
|---|---|
| `Wet level`, `Dry level` | Reverb and dry levels |
| `Early reflection level` | First reflections |
| `Room size`, `Decay time` | Virtual room and tail to -60 dB |
| `Predelay` | Gap before the first reflection. Long values can sound like slapback |
| `Low cut`, `High cut` | Band of the reverb. Low cut reduces rumble on drums |
| `Diffusion` | Low gives distinct echoes, high gives a dense noise-like tail |
| `High damping` | Damps highs in the tail. The maximum turns it off |
| `Bass multiplier`, `Crossover` | Decay of the lows, and where they begin |
| `Mod Depth`, `Mod Speed` | Moves the reverb time to reduce metallic ringing. High values detune |
| `Stereo separation` | Width of the wet signal only |

## Values used

On acoustic drums, `Wet level` 19%, `Room size` 26 and `Decay time` 1.7 s.
