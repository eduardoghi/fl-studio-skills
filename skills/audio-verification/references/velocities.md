# Velocities from a reference

Read this when the dynamics of a recorded part have to be copied onto a virtual instrument.

To copy the dynamics of a recorded part onto a virtual instrument, measure how the instrument answers velocity
instead of assuming a straight line, then map the reference's relative levels through that curve.

```sh
instrument-calibrate layout cal.json --bpm 104.5 --notes 36,38,42 --long 46,49,51
fl-notes write cal.json 4          # the file holds "notes" for one channel; wrap them as {"3": [...]} first
instrument-calibrate analyze cal.json render.wav curves.json
instrument-calibrate velocity curves.json --note 38 --anchor 120 -- -2 -9.5 -24
instrument-calibrate validate curves.json held_out.json   # curves of notes or velocities left out of the first
instrument-calibrate compare ref_snare.wav render_snare.wav --times snare_times.json --offset -1.677
```

The `fl-notes write` line is the FL step. The layout's `notes` give `start` and `length` in beats and `velocity`
from 0 to 1, so in REAPER write them with `midi.write` (the `reaper` skill) as `start_qn` = `start`, `end_qn` =
`start` + `length` and `vel` = `velocity` × 127, rounded.

- Calibrate each note and articulation on its own, with a few hits per velocity, since samples rotate. On one drum
  kit the spread between hits of the same velocity stayed under 1.5 dB for drums and reached 3 dB for cymbals.
- Use the attack level (RMS of the first 30 ms), not the peak. Curves were monotonic and far from straight, and the
  range from velocity 1 to 127 went from 15 dB on toms to 40 dB on a crash, so one mapping for every piece is wrong.
- Check the attack measure against a render of known, varied velocities, dry and compressed. On a polyphonic guitar
  part the 30 ms RMS kept a rank correlation of 0.55 to 0.79 with velocity, the rise in energy over the attack and
  the rise above 2 kHz kept less, and spectral flux stayed under 0.4. Flux follows how much the spectrum changes,
  which new pitches drive, more than how hard the note was played.
- A level from a mixed or separated reference carries gain and processing. Take each hit's difference from the
  loudest hits of the same part, and pick the velocity of those loudest hits as an anchor. Where the transcription was
  right, the render matched the reference's relative level per note within 0.3 dB.
- Don't calibrate from per-note levels that don't repeat between separators or that stay inside the instrument's own
  variation between renders. Measure the same notes on a second separator's stem, and on two identical renders,
  first. In one doubling layer, the levels per note correlated 0.21 between two separators and 0.38 between two
  renders of the same MIDI, so the notes kept one velocity.
- A target under the instrument's softest velocity can't be played, and velocity 1 left such hits up to 28 dB too
  loud. `velocity` flags them so they can be dropped or given another articulation.
- A pitched instrument can answer velocity differently across its range. Calibrate a few notes spread over the
  range in use, render a second layout with other notes and velocities, and run `validate` on it. If interpolating
  in pitch clearly beats one mean curve, use it (`velocity` interpolates a note without its own curve). The round
  robin sets how close any model can get. `plugins/ezbass.md` in the plugins skill has one measured case.
- When some of the reference's attacks start from silence and others from a sounding note, a 30 ms window starts
  at different points of the rise and biases the level of one group. Check the velocities by context (after a
  rest, after a note). The peak of the first 100 ms against the peak curve (`--key peak_db`) moves much less.
- Measure the instrument's delay with the same onset method used on the reference, in a render of the whole part,
  since a method that keys on what precedes an attack can read isolated hits and connected notes differently. The
  same goes for the end of notes before a rest, where the instrument's release may keep sounding after the
  reference has stopped.
- Compare one part at a time, with that part rendered alone against the same part in the reference. Attacks counted
  in a full mix mislead. A kick part matched its 195 notes exactly, while a band filter over the whole drum mix
  counted 398 low attacks in the reference and 542 in the render. `compare` sorts the attacks into those at a note,
  those 30 to 250 ms after one (a sample's second hit or a ring) and unrelated ones.
- When no articulation of the instrument comes close, compare the band profile around the hits, normalized to one
  band, before changing notes. A difference shared by every articulation is timbre or processing for the mix stage.
