# Fruity Blood Overdrive

Signal flow is `Pre band` > `Pre amp` > `Post filter` > `Post gain` > digital clipping at the output (manual).

## Watch out

The level climbs fast, up to 300% of the input (manual). `Pre amp` 0.55 with `Post gain` -0.125 hit -2.9 dBFS peak and
-10.5 dBFS RMS on a guitar, while 0.40 with -0.375 gave -5.1 and -20.0 (observed). Lower `Post gain`, not the input,
because lowering the input removes the distortion (manual).

Distortion adds partials that were never played, so a G chord without a third read B as a strong note (observed). Check
chord notes on the dry track.

Even at zero drive it compresses a full mix and flattens its balance (manual).

## Controls

| Name in the API | What it does |
|---|---|
| `Pre amp` | Drive. The displayed value matches the raw one |
| `x100` | Multiplies the drive by 100. Meant for single instruments |
| `Post gain` | Output trim. The displayed value is the raw value minus 1 (observed) |
| `Pre band`, `Color` | Filter before the drive and its cutoff, to remove highs that turn harsh |
| `Post filter` | Lowpass after the drive. Was already 0 here, so raising it darkens the sound |

The manual calls `Pre band` a low-pass in one place and a band-pass in another.

## Values used

| Part | Pre amp | Post gain |
|---|---|---|
| Synth pad | 0.40 | -0.075 |
| Distorted guitar | 0.40 | -0.375 |
| Bass, just for body | 0.15 | default |
