# LuxeVerb

## Watch out

A new instance starts with `Output wet level` at 0 dB, `Reverb decay` at 5.2 s and `Reverb size` at 20 (observed). On
a clean part that covers the attack, so lower the wet level before judging the sound.

`Input low cut` starts at 20 Hz (observed). Raising it keeps the tail from muddying the low end.

`Input high cut` changes the character of the tail. At 1682 Hz only the lower band of a distorted guitar enters the
reverb. Adding chorus, delay and this reverb took 2-6 kHz from 17% to 7% of the energy (observed), so raise this first
if a dense part sounds dull. How much of the fall came from this control alone wasn't measured.

## Controls

| Name in the API | What it does |
|---|---|
| `Output wet level`, `Output dry level` | Levels in dB |
| `Reverb decay` | Tail length to about -60 dB |
| `Reverb size` | Echo spacing, not decay. 0-10 is plate-like, 10-50 acoustic, above 50 cavernous (manual) |
| `Reverb brightness` | Highs in the tail |
| `Reverb character` | 0.5 is smoothest. Lower is grittier, higher bunches into a fuzzy echo |
| `Reverb pre-delay` | Gap before the tail, which helps the attack stay clear |
| `Reverb mod amp`, `Reverb mod frequency` | Chorus-like movement in the tail |
| `Reverb freeze mode` | Normal, Freeze holds the sound and cuts the input, Sustain keeps building |
| `Input high cut`, `Input low cut` | Band that enters the reverb |
| `Output stereo width` | Read 1.20 by default (observed). The manual gives 1.25 as normal output |
| `Toggle feedback`, `Feedback gain` | Pitch shifted feedback, off by default. High gain turns unstable |
| `Envelope mode`, `Envelope scale` | Modulates wet or decay from the input. Positive gives gating, negative gives ducking |

`Input wet gain` flashes red on the panel when the input limiter engages (manual).

## Values used

| Part | Wet | Decay | Size | Low cut | High cut |
|---|---|---|---|---|---|
| Clean guitar | -10.4 dB | 3.97 s | 40 | 205 Hz | 15 kHz |
| Distorted guitar | -3.8 dB | 7.5 s | 52 | 205 Hz | 1682 Hz |
