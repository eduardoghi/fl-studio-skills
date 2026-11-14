---
name: audio-verification
description: Check exported audio with measurements instead of guessing, since the agent can't listen. Use after rendering a mix or stem from FL Studio, when the user reports noise, clicks, thumps, harshness or low volume, to confirm that chords sound the notes that were written, to prepare level-matched versions for an A/B comparison, or to audit the continuity of the transitions between sections.
---

# Verifying exported audio

The agent can't hear the result. `bin/wav-check` turns a rendered WAV into numbers, which is enough to find
many concrete problems and never enough to say that something sounds good. Report what was measured and
leave taste to the person listening.

Peak meters read during playback only prove that a track has signal. Render a file and measure that.

## Commands

```sh
wav-check measure a.wav b.wav                 # peak, RMS, loudest passage, energy per band
wav-check timeline a.wav --step 4             # peak per interval
wav-check noise a.wav --start 24              # floor level, bands and slow level swings
wav-check thumps a.wav --bpm 95               # low attacks with almost no midrange
wav-check chords a.wav --bpm 95 'Bm:0.3-3.3:B,F#,C#'
wav-check chords a.wav --bpm 95 --skip 1 'Gm:28-32:G,Bb,D'
wav-check width a.wav                         # left/right correlation and side level
wav-check match out/ --peak -8.8 a.wav b.wav  # same level for A/B listening
wav-check cut out/ --bpm 95 --end 32 a.wav b.wav  # the same passage, levels untouched
```

Installed as a plugin, `wav-check` is on `PATH`. In a clone it is `bin/wav-check`, two folders above this file. It
needs numpy, so run `uv run --no-project --with numpy python <path to wav-check>` if numpy isn't installed.

## From a complaint to a measurement

| The user says | Run | Look for |
|---|---|---|
| Too quiet | `measure` | The peak. Then read the master and track faders before touching anything else |
| Harsh, metallic | `measure` | The share of 2-6 kHz, compared with an earlier version |
| Dull | `measure` | The same band falling too far, 120-500 Hz taking over |
| Hiss or a wave in the background | `timeline`, then `noise` | A floor that doesn't decay and a swing below a few Hz |
| Thumps or clicks in the middle | `thumps` | The beat, then the note at that beat |
| The render is much longer than the song | `timeline` | A constant floor keeping FL's tail detection open |
| Wrong notes, odd harmony | `chords` on the dry track | Missing pitch classes |

## What the numbers looked like in practice

These come from one clean electric guitar track at 95 BPM, and they are examples, not targets.

- **Background wave.** `timeline` showed a constant floor near -62 dBFS after the music ended, and the render
  ran 50 s for 20 s of song. `noise` put 94% of the energy above 2 kHz with a swing at 0.8 Hz. The cause was the
  `Noise` knob of Vintage Chorus, on by default. It emulates analog hiss, and the chorus modulates it, which is
  why it sounded like a wave. Turning it off dropped the hiss by 19 dB in quiet passages and cut the render to 28 s.
- **Thump.** `thumps` flagged beat 19.55, 16.8 dB above the midrange, and the note there was a low palm mute
  at velocity 0.41. Palm mute depth grows as velocity falls in Ample Guitar, so low velocities on a low string
  can read as a hit with no pitch.
- **Too bright.** Energy at 2-6 kHz went from 4% to 14% with the amp's bright switch and treble up, and the
  listener called it metallic. A setting near 8% was the middle ground.

## Check notes before effects

Run `chords` on the track with no distortion, delay or reverb. Each effect moves the reading.

- Distortion adds partials that were never played. A G chord with no third read B as a strong note after overdrive.
- A long reverb tail carries the previous chord, so a pitch class from the last chord can appear as `extra`.

A `DIFFERS` on a wet track is not a wrong note until the dry track says so. A passage should start after the attack
and end before the next chord.

A synth pad has the same problem with no effect on its mixer track, since a patch can carry its own release and
effects, so it can read the last chord for a while. `--skip` moves the start of every passage by that many beats, and the printed range shows what was read.
On a 4 beat chord at 95 BPM, two pads read `DIFFERS` over the whole chord and `ok` from the second beat, so the notes
were right and the change was slow.

## Comparing versions

Louder usually reads as better, so match levels before asking anyone to choose. Use `--peak` for whole takes
and `--rms` for short excerpts, where one hit would set the whole gain. Keep the original files, and say which
copies had their gain changed.

Use `cut` instead when the level difference is the thing being compared, such as a passage with and without a new
layer. It keeps each file's level. End the cut before the next section starts, because a fade over the entry of a
band leaves that entry in the file. Measure the same range as well, since a window that runs into the next section
counts its level.

Change one thing per render.

## Velocities from a reference

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

- Calibrate each note and articulation on its own, with a few hits per velocity, since samples rotate. On one drum
  kit the spread between hits of the same velocity stayed under 1.5 dB for drums and reached 3 dB for cymbals.
- Use the attack level (RMS of the first 30 ms), not the peak. Curves were monotonic and far from straight, and the
  range from velocity 1 to 127 went from 15 dB on toms to 40 dB on a crash, so one mapping for every piece is wrong.
- A level from a mixed or separated reference carries gain and processing. Take each hit's difference from the
  loudest hits of the same part, and pick the velocity of those loudest hits as an anchor. Where the transcription was
  right, the render matched the reference's relative level per note within 0.3 dB.
- A target under the instrument's softest velocity can't be played, and velocity 1 left such hits up to 28 dB too
  loud. `velocity` flags them so they can be dropped or given another articulation.
- For a pitched instrument, calibrate a few notes across the range in use and render a second layout with other
  notes and velocities for `validate`. On a sampled bass the top of the range sat 2 to 6 dB under the bottom at low
  velocities, and interpolating in pitch predicted the held-out notes within 0.9 dB (median), as close as the
  round robin allows (3 to 6 dB between hits of one velocity). `velocity` interpolates a note that has no curve.
- When the reference's attacks start from a sounding note or from silence alike, the attack window lands at
  different points of the rise. On a bass that left notes after a rest 25 velocities too soft. The peak of the first
  100 ms against the peak curve (`--key peak_db`) removed that bias.
- Measure the instrument's delay with the same onset method used on the reference, in a render of the whole part.
  The same bass read 0 ms late on isolated hits and 7.7 ms late among other notes, where the method finds the dip
  before each attack. Notes before a rest also need the instrument's release in mind, since its tail kept sounding
  40 to 70 ms past the reference's end, so those notes were shortened by that much.
- Compare one part at a time, with that part rendered alone against the same part in the reference. Attacks counted
  in a full mix mislead. A kick part matched its 195 notes exactly, while a band filter over the whole drum mix
  counted 398 low attacks in the reference and 542 in the render. `compare` sorts the attacks into those at a note,
  those 30 to 250 ms after one (a sample's second hit or a ring) and unrelated ones.
- When no articulation of the instrument comes close, compare the band profile around the hits, normalized to one
  band, before changing notes. A difference shared by every articulation is timbre or processing for the mix stage.

## Transition Continuity Audit

When a passage between sections sounds broken, read the notes of every channel on both sides of the boundary
(`fl-notes read`, or the score a generator wrote) before touching anything. Run a light pass over the main
boundaries before the final export of a piece with several sections too, when the notes and the section boundaries
are available. It doesn't need repeating after every small edit. Check four things in a window of a bar or two around
each boundary:

1. Gaps. A part ends before the part that takes over starts, or one line stops and resumes with a hole in between.
2. Stray notes. Short notes left at the start of a section by a range that ran one chord too far.
3. Rearticulations. The same pitch ends and starts again on one channel, which a legato instrument plays as a new
   attack. Overlapping notes of different pitches are a legato transition, not a new attack.
4. Abrupt controls. A large step between two consecutive CC1 or CC11 values, a CC64 release that cuts notes the pedal
   was holding, or note-offs on several channels at the same barline. A controller holds its value until the next
   event, so judge the size of each step, not the time between events. A ramp drawn in small steps isn't a jump, and
   a step while the channel is silent only prepares its next entry.

Compare sounding times, not written ones. Add the attack and legato delays measured for each instrument, and treat a
note under a held sustain pedal as lasting until the pedal lifts. In Cinematic Studio Strings the previous note kept
sounding through a legato transition until the new one was heard, so there the transition delay wasn't a gap. Check
that in a render before assuming it for another library. Say which delays and releases weren't measured, because a
long release can fill a gap that the notes show. To confirm that a gap is audible, render the stems and run
`timeline` with a short `--step` on each.

Report each finding with the channel, bar and beat, the events involved and why it looks suspicious. Don't fix
anything from the audit alone. A silence, a new bow stroke or a sudden contrast can be what the composer wanted, so
each finding is a question for the person who wrote it. Controls that a project draws as automation clips aren't in
the notes, so say when they couldn't be checked.

## Limits

- The tool knows nothing about taste, feel, timing or whether a part suits the song.
- `thumps` finds low attacks with little midrange. Its default threshold of 12 dB is calibrated on one guitar part,
  and it can miss hits in very short files, because the attack threshold comes from the file itself.
- `chords` compares pitch classes between 70 Hz and 1 kHz. It can't tell octaves or inversions apart.
