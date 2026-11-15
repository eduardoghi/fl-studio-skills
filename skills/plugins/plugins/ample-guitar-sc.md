# Ample Guitar SC

Sampled electric guitar. Everything here is from version 4.0.1, whose manuals are in `Documents\Ample Sound\Manuals`.

## Watch out

Ample numbers octaves differently from FL. Ample's `E1` is MIDI 40, which FL shows as `E3`, so its `C0` keyswitch is
MIDI 24 (observed). Keyswitches are notes in the same piano roll, placed just before the notes they affect.

Palm mute depth grows as velocity falls (manual). A low palm mute at velocity 0.41 on the sixth string came out as a
pitchless thump 16.8 dB above the midrange (observed).

In the default Instrument mode two notes on one string can't sound together (manual), so a note ends when another note
takes its string. The instrument picks the string, and string keyswitches `G0` to `C1` force it.

The Default preset has its internal EQ and delay on (`FX-EQ-Toggle`, `FX-Delay-Toggle`), so check them before adding
FL effects (observed). No parameter listed which amp is active, so choosing one still needs the interface.

## Keyswitches

MIDI numbers assume `E1` = 40.

| Articulation | Ample | MIDI |
|---|---|---|
| Pinch harmonic | `B-1` | 23 |
| Sustain and pop | `C0` | 24 |
| Natural harmonic | `C#0` | 25 |
| Palm mute | `D0` | 26 |
| Slide in and out | `D#0` | 27 |
| Legato slide | `E0` | 28 |
| Hammer-on and pull-off | `F0` | 29 |
| Slide guitar | `F#0` | 30 |

Legato slide and hammer-on need two overlapping notes after the keyswitch, and they revert by themselves (manual).
Pressing `C0` and `D0` together gives sustain at high velocity and palm mute at low velocity. Velocity 127 on Sustain
triggers a pop or pinch harmonic instead.

## Parameters

Each instance reports 361 named parameters out of 4240. Filter them with `contains`.

| Name in the API | What it does |
|---|---|
| `Open Str First` | Prefers open strings for `E1 A1 D2 G2 B2 E3` |
| `Auto Legato` | Off, slide or hammer-on. Off keeps overlapping notes from becoming slides |
| `Play Mode` | Instrument, Keyboard, Solo, Power Chord or Octave |
| `M-Doubling Tog`, `M-Doubling Wid` | Two takes panned apart, which helps a rhythm part |
| `AMP-JC120-Distortion` | Preamp distortion of the clean amp. 0 disables it |
| `AMP-57D-PreODEnabled`, `AMP-57D-Gain` | Predrive and input of the 57 Delight amp |

Every amp's knobs are listed under its own `AMP-` prefix, whether or not that amp is active.

## Values used

Clean part on Jazz 120 with `AMP-JC120-Bright` on, `AMP-JC120-Treble` 4.60 and `AMP-JC120-Distortion` 0, which gave
about 8% of the energy at 2-6 kHz with effects. With bright off it fell to about 4%, and with bright on and more treble
it reached 14%, which the listener called metallic.

Distorted part on 57 Delight with Predrive on, `AMP-57D-Gain` 10, the Mid+Bridge pickup and doubling on.
