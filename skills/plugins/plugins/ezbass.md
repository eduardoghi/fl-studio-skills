# EZbass

Observed on version 1.3.4 (VST3) in FL Studio 26.1.7, with the EZbass Vintage model and its `Clean DI` preset unless
noted. The manual is behind a login and wasn't read. The installed `EZbass Key Switch Layout.pdf`, in the program
folder, lists the keyswitches.

## Check which build FL loads

FL listed EZbass under its VST plugins and loaded a VST2 build from 2020 (1.0.5) left in
`C:\Program Files\Common Files\VST2\Toontrack\`, while the standalone and the VST3 were 1.3.4. The old build refused
the EZbass Modern library with a dialog asking for version 1.1.0. The version shows under the logo at the bottom
left. Removing the old DLL and rescanning in Options > Manage plugins made FL use the VST3.

## Controlling it

- A new instance opened on EZbass Modern with the `Clean DI` preset.
- The model selector next to the preset name is a JUCE menu. It closes as soon as FL leaves the front, so the bridge
  can only reach it with `fl_click(..., focus=True)`, on the selector and again on the row.
- The bridge sees only four named parameters (Bridge, Neck, Tone and Sub-Bass level). Settings has no option for
  release or fret noise.

## Pitch and keyswitches

- It sounds an octave under the MIDI note written, as bass notation does. Note 47 sounded B1 (61.7 Hz) and 35
  sounded B0, so to play a pitch heard in a reference write it 12 semitones up.
- The PDF names keys with C3 = 60. In MIDI numbers the keyswitches sit on 21 to 32 and playing starts at 33.

| Note | PDF name | Behavior heard in renders |
| --- | --- | --- |
| 21 | A-1 Polyphony (hold) | overlapping notes each get their own attack |
| 27 | D#0 Loud Mute (press) | repeats the last note as a short percussive mute |
| 28 | E0 Ghost Note (press) | repeats the last note as a soft ghost |
| 29 | F0 Slide Down (press) | the sounding note falls about 10 semitones at about 22 semitones per second |
| 30 | F#0 Slide (hold) | slides to the next note when the two notes overlap, in about 100 ms for a fifth |
| 31 | G0 Slide Up (press) | the sounding note rises about 8 semitones at about 17 semitones per second |
| 32 | G#0 Legato (hold) | same as the default for overlapping notes |

The PDF also lists A#-1 Harmonic, B-1 Slap/Pop, C#0 Middle Finger and D0 Repeater, which weren't tried.

- Overlapping notes play legato by default, with no new attack, so notes meant to be plucked must end before the
  next one starts.
- The slide speed is fixed. It didn't change with the keyswitch's velocity or with the note's length, and the glide
  starts about 30 ms after the key. Without overlapping notes, Slide (30) only jumped to the next note.
- Every note-off plays a release with a small rise in pitch (under a semitone) that stays audible for 40 to 70 ms.
  Before a rest it reads as a short extra event, so end such notes earlier to match a muted reference.

## Velocity

Measured on notes 47, 54 and 59 with instrument-calibrate, three hits per velocity:

- The attack level (RMS of the first 30 ms) went from about -50 dB at velocity 1 to -15 dB at 127, a 35 dB range,
  monotonic and not straight.
- Hits of one velocity differed by 2.5 to 6.7 dB, with no pattern by repetition, so the round robin isn't a fixed
  alternation of fingers.
- Note 59 sat 2 to 6 dB under note 47 at low velocities, while 54 stayed within 2 dB of 47. Interpolating the curves
  in pitch predicted notes 44, 51 and 56 and unmeasured velocities within 0.87 dB (median, worst 3.1 dB).
- Timing an attack as the rise out of the dip in the low-band envelope put it 0 ms after the note-on for an isolated
  hit and 7.7 ms after it among other notes, where the previous note's release fills the dip.

## Rendering in REAPER

Observed in REAPER 7.86 (VST3 and VST2 builds of 1.3.4) on four notes rendered in a new process. With no load delay the file
was pure silence in both runs, and with `fx_delay` 5 the notes sounded. Give the project a load delay
(`docs/render-standard.md`).
