# ReaSynth (REAPER)

REAPER's own small synth, a VSTi that ships with it. Observed in REAPER 7.86. Every control is a host parameter, so a
simple patch can be built and reproduced from parameters alone, with no interface.

## Parameters

| Index | Name | Notes |
|---|---|---|
| 0 | Attack | milliseconds, linear, 5000 ms at the top (a normalized 0.012 is 60 ms) |
| 1 | Release | milliseconds |
| 2, 3, 4 | Square mix, Saw mix, Triangle mix | with all mixes at 0 the voice is a sine |
| 5 | Volume | dB |
| 6 | Decay | milliseconds |
| 7 | Extra sine mix | a second sine |
| 8 | Extra sine tuning | cents, 0 at the middle and +2400 at the top (+1200, an octave up, is 0.75) |
| 9 | Sustain | dB |
| 10 | Pulse Width | |
| 11 | Global detune | |
| 12 | Legacy oscillator mode | |
| 13 | Portamento | |

## Watch out

- Setting a value by its displayed text can fail. The text "400" for Attack matched "400.0", while "60" found no
  match, so pass a normalized number when the value has to be exact.
- The extra sine's tuning reads like semitones but is in cents, so an octave up is 1200, not 12.
- The output is mono, both channels identical. Width needs two renders with opposite detune or processing after it.
- On a pad, a release long enough to sound smooth hid a 30 ms gap between chords, so it can't show whether a note
  is held or struck again.
