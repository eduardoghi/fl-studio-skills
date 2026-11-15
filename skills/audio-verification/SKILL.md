---
name: audio-verification
description: Check exported audio with measurements instead of guessing, since the agent can't listen. Use after rendering a mix or stem from a DAW (REAPER, or FL Studio for older projects), when the user reports noise, clicks, thumps, harshness or low volume, to confirm that chords sound the notes that were written, to prepare level-matched versions for an A/B comparison, to audit the continuity of the transitions between sections, or to transcribe a part from a reference recording and check its rebuild against it.
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
| The render is much longer than the song | `timeline` | A constant floor keeping the host's tail detection open (seen in FL) |
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

Two renders of the same project don't always match. Sampled instruments rotate samples (round robin), and modulated
effects start at a different phase each time. In one rebuild no two of four renders of a guitar part matched, with
residuals up to -3 to -5 dB between repeats, and a reverb with its default modulation never rendered the same twice.
Before reading a difference between two versions as a change, render each a few times and judge it against the
spread between repeats (`mps wav variation` in this repository). Keep the effect as it will be in the mix and allow
for its variation, or turn its modulation off only for the comparison and say so.

To judge a rebuild as a whole, export each part alone from the same project (in FL, the same pattern) and compare its level relative to the sum
of the parts, section by section, with the same parts in the reference's stems. The median difference across sections
is the fixed gain a part needs, and the spread is what a fixed gain can't fix, such as a part that grows in the
reference's arrangement. In one rebuild the drums sat about 6 dB low in every section. Correcting the three parts
offline by their medians raised the correlation of the 100 ms envelope with the reference from 0.40-0.83 to
0.67-0.94 per section, before any change to notes.

### Tone apart from playing

To work on an instrument's sound without mixing in changes to the part, keep the MIDI fixed and change one link of the
chain per render. Measure at the reference's own attack times, since the render plays the same notes:

- how far the attack rises above the sustain right after it, broadband and above 2 kHz, where the pick sits
- how far the sound falls between one attack and the next
- crest factor, left-right correlation and the band profile normalized to the total

What one guitar showed, as things to check rather than rules:

- Compare the band profile with the reference band by band before trusting an amp and cabinet. Every cabinet tried
  cut 6 to 12 dB of the band the reference was strongest in and lifted 2 to 4 kHz, while the plain signal sat within
  about 2 dB, so the softer attack it gave came with the wrong tone.
- The same compressor settings did very different things before and after the instrument's output. Read the crest
  factor of each render rather than the threshold, and keep a compressor that lowers it without filling the gaps
  between notes more than the reference does.
- Width can come from the source instead of the reverb. Compare how the left and right attacks line up as well as
  the overall correlation. Two takes with no timing spread kept the attacks together, as the reference did, and a
  few milliseconds of spread already separated them.
- Fill between notes depends on the notes too. Extra attacks in the part fill the gaps whatever the tone, so read
  that measure again after fixing the playing.

## Transcribing a part from a reference

Notes taken from a recording are measurements with errors, not facts. Keep the raw output of every tool, record
which evidence supports each note, and keep the reason for every correction next to it, so a later pass can undo
one decision without redoing the rest. Mark what was detected, what was estimated and what a person confirmed by
ear. Agreement between tools raises confidence but doesn't confirm a note, since tools can share an error.

The points below come from transcribing one bass line from a separated stem. Treat the numbers as an example of
what to check, not as thresholds for another recording.

- Onset detectors that normalize by the maximum, as librosa's `onset_detect` does by default, lose a quiet stem to
  one click. A separated stem had one at the first downbeat, 40 times its 99th percentile, and only 6 attacks were
  left in two minutes. Normalize by a high percentile and clip instead.
- Pitch trackers answer "what pitch is sounding", not "where does a note start". None of the four tried (pYIN,
  CREPE, PESTO and Basic Pitch) split repeated notes of the same pitch reliably, and the line had more repeated
  pairs than pitch changes. Take attacks from the audio (spectral flux, the envelope) and ask the trackers only for
  the pitch between two attacks. On that bass each new pluck followed a short dip in the low-band envelope, which
  marked both the attack and the end of the previous note.
- Check the octave against the harmonic structure, not against one tracker. Energy at half the detected frequency
  points to a note an octave lower, and a second harmonic stronger than the fundamental can pull a tracker an
  octave up. Compare trackers and stems from other separation models before accepting a note in an unusual octave.
- The tempo grid is evidence, not a target. Real attacks clustered tightly around grid positions while weak
  candidates without a dip spread evenly, and the even ones rarely appeared in the other stems. Use that to judge
  doubtful events, and keep the measured times of the notes kept. Don't move notes onto the grid and don't move
  pitches into the estimated key.
- Tell apart what looks alike in a pitch curve:
  - a repeated note has a new attack with no pitch change
  - legato (hammer-on, pull-off) changes pitch abruptly with no new attack
  - a slide changes pitch with no new attack and passes through the pitches between, which a fretted instrument
    shows as a staircase of semitones rather than a smooth glide
  - a rest is a fall in level, while a short event glued to the end of a note and followed by silence is usually the
    note being muted, sometimes together with a drum hit leaking into the stem
  - an event with no pitch and much brighter than the notes is usually leakage from another part
- When the instrument used for the rebuild has articulations (keyswitches for slides, legato on overlapping notes),
  probe what each one actually does in a render before relying on it, and keep notes that should be plucked from
  overlapping by accident.
- Compare the render with the reference using the same segmenter on both. It removes the bias of the method
  but not its blind spots, so read the disagreements one by one. Some will be the segmenter merging or splitting
  events in one of the two files, not a difference in the music.
- Sort what remains by cause before changing notes, whether transcription (wrong or missing notes), articulation
  (how a note starts, ends or moves), sustain (how it decays), timbre or mixing. Only the first two belong in the
  notes.
  A long note that decays faster in the render, or a darker tone in the reference, is for the sound or the mix.

### Polyphonic parts

These come from one guitar part with heavy stereo processing, again as examples of what to check.

- Validate every detector, including your own measurements, on a render of MIDI you know before trusting it on the
  reference. Render it dry and again with effects close to the reference's. On a clean render the best guitar model
  scored F 0.94, and with stereo modulation and reverb the same model fell to 0.29, firing short false notes at the
  modulation, while another model held 0.70. Pick tools and thresholds by that test, not by how much tools agree.
- A pitch-presence measure built from a constant-Q transform must center each semitone's bins on the semitone. With
  three bins per semitone grouped as 0, +33 and +67 cents, every played note also read as present a semitone
  below, which looked like wrong notes in both the render and the reference. Centered bins (-33, 0, +33) removed
  all of them. What a presence threshold still lets through is mostly harmonics 2 to 4 (+12, +19, +24 semitones).
- Treat a pitch 12, 19 or 24 semitones above another detected pitch, with weaker evidence and lower level, as a
  harmonic rather than a note.
- Count tools as independent only across model families. The same model on stems from two separators, or two
  checkpoints of one model, make the same mistakes. Requiring two families beat both single tools and a stricter
  three-family rule, which kept precision high but lost half the notes.
- Measure the time offset between the onset detector and each tool on the reference too, not only on the known
  render. On the known render every tool agreed with the detector within about 20 ms, while on the reference the
  tools put part of the attacks 50 to 90 ms after it. With a window of 50 ms on each side, the same attack became a
  second point, and then a short note that the render plucked again. Letting a tool's note up to 90 ms after a
  detected attack count for the nearest attack removed those points and didn't change the F score on the known
  renders.
- Before reading a higher onset count in the render as extra notes, measure the reference's spectral flux at the
  extra points against random times with no note. Most extra points had flux far above that baseline. They were
  softer attacks under the detector's threshold, not invented notes.
- A tail is not a note. Ending a note when it is no longer present at all keeps the reverb in it. Ending it when it
  falls a fixed amount below its own peak got the median duration right on the known render.
- Check that the notes can be played. On a guitar a new note on a string ends the one ringing on it, and the
  fretting hand spans a few frets. Assigning strings and frets at each attack removed every moment with more than
  six notes without capping the count, and the few attacks left without a fingering were mostly a harmonic or a
  leak from another part (a bass note an octave up in the guitar stem).
- Separate effects from playing before adding notes. A modulation that moves every pitch in phase is tremolo, one
  with a pick transient at each repeat is playing, and repeats that fall by a constant ratio are delay. A pitch
  modulating chorus spreads energy into the neighbouring semitones, so its absence in the reference rules out a
  strong one. Left and right attacks within a millisecond of each other point to one source spread by processing
  rather than two takes. A clean stop in the part gives the reverb's decay, which an estimate of note durations
  cannot.
- A level per note in a chord can't come from broadband RMS. The level of the note's own semitone separates the
  notes, but check that it rises steadily with velocity on the instrument, since a sample layer with a different
  harmonic balance can make it fall.
- Correcting each note's length by how long its pitch stays present in the reference and in the render didn't
  converge. A second pass still wanted to move most of the same notes, and one note stretched past a stop. In a
  dense part the presence of a single pitch is too noisy for per-note decisions, so judge durations by section
  measures and by the stops.
- An envelope that stays within a few dB, as in a compressed part with chords ringing into each other, has little
  shape to correlate. A low correlation of the 100 ms envelope there says little about the notes. Compare the
  attacks point by point instead.
- To tell a second layer from leakage of another part in its stem, count the layer's notes that start within 50 ms
  of a note of the other part with the same pitch class, and the same count with the layer's times shifted by a
  fraction of a beat. A rate near the shifted one means independent material. Mark the coinciding notes as probable
  leakage rather than deleting them.
- Check that the rebuild's effects don't smear the harmony more than the reference does. On one guitar the dry
  render's semitone spectrum matched the reference frame by frame better than the render with reverb, in every
  section.
- An audition of transcribed notes with one fixed level hides the layer's dynamics. Give each note the stem's level
  at that note, or the comparison by ear will mislead.

### Separated stems as targets

A separator's stems are a guess about the instrumentation, and a processed instrument can be split across several.
These checks come from one mix with a stereo processed guitar, a residual "other" stem and vocals.

- Compare the same stem across separators. Two estimates of the guitar agreed to 8 to 19 dB (SDR between them), while
  the two "other" stems agreed to about 0 dB, which means each separator put something different there. The sum of
  guitar, other and piano agreed better across three separators than the guitar alone (15 to 27 dB against 8 to 19),
  most in the loudest section. Where that happens, the split is arbitrary and the sum is the more reliable target for
  pitch and level, at the cost of including whatever else fell into those stems.
- Mid and side can tell different stories. The "other" stem was louder in side than in mid, with negative left-right
  correlation, and its side carried a harmony that both separators extracted alike (chroma 0.82 to 0.91 between
  them) but that differed from the guitar's at the same moment.
- Test where a residual stem comes from against each other stem, not only the obvious one. For each candidate source,
  correlate the residual's envelope with the source's envelope smoothed by exponential decays of a few T60 values,
  and its chroma with the source's chroma integrated over the past. A reverb or delay tail correlates better as the
  smoothing grows. A part split by the separator correlates at once. In one section the residual followed the
  vocals' harmony and their smoothed envelope, so it was the vocals' reverb or delay, not an instrument. In another
  it followed the guitar's envelope in sync.
- Run the separator on a mix you built, with known parts, before blaming the reference's stems on an effect. A
  guitar with a short stereo reverb and, separately, with a long dark tail added went 97 to 99% into the guitar stem,
  tail included, and the "other" stem stayed 54 dB or more below. Those effects couldn't produce the reference's
  residual, which pointed to a source the model doesn't call guitar.
- To get a known part for such a test, export each part alone from the same project with the others muted and add
  them offline. Subtracting an earlier render fails when the instrument isn't sample-identical between renders, as
  with round robin samples or modulated effects.

## Which string played a note

The same pitch on different guitar strings has a different pattern of harmonics, which can suggest the string a
recording used. It worked as a suggestion with confidence, never as a certainty.

1. Render a calibration with the instrument that will play the part, with each pitch of the part alone on every string
   that reaches it, twice.
2. Take each note's profile as the level of harmonics 2 to 8 relative to the fundamental, from 40 to 250 ms after the
   attack, so the pick transient stays out.
3. Compare profiles after removing a straight-line tilt over log2 of the harmonic number, which is what a broad EQ, a
   pickup or a clean amplifier changes. Leave out harmonics within 3% of a partial of another note sounding at the
   same time, and skip notes with fewer than four left.
4. Keep only suggestions whose best string is clearly ahead of the second, and let the fingering's physical
   constraints overrule them.

Measured on one sampled guitar. Each calibration repeat classified by the others was right for 73 of 74 notes. On a
render with known strings, notes whose second-best distance was at least twice the best were right for 20 of 20 dry
and 19 of 21 after synthetic high cut, saturation and reverb, while all notes together were right for 71 to 75%. A
real recording can hold processing or layered takes that this test doesn't cover, and in a dense part few notes start
alone, so expect suggestions for a minority of notes.

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

## Transition Continuity Audit

When a passage between sections sounds broken, read the notes of every channel on both sides of the boundary
(`midi.read` through the `reaper` skill, `fl-notes read` in FL, or the score a generator wrote) before touching anything. Run a light pass over the main
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
