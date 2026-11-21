---
name: audio-verification
description: Check exported audio with measurements instead of guessing, since the agent can't listen. Use after rendering a mix or stem from a DAW (REAPER, or FL Studio for older projects), when the user reports noise, clicks, thumps, harshness or low volume, to confirm that chords sound the notes that were written, to prepare level-matched versions for an A/B comparison, to audit the continuity of the transitions between sections, or to transcribe a part from a reference recording and check its rebuild against it.
---

# Verifying exported audio

The agent can't hear the result. `bin/wav-check` turns a rendered WAV into numbers, which is enough to find
many concrete problems and never enough to say that something sounds good. Report what was measured and
leave taste to the person listening.

Peak meters read during playback only prove that a track has signal. Render a file and measure that.

## Reference files

Read only the file that matches the problem. Each one is self-contained.

- **A part has to be transcribed from a recording or checked note by note against it.** See
  [references/transcription.md](references/transcription.md).
- **Separated stems are the target, or a residual stem needs explaining.** See
  [references/separated-stems.md](references/separated-stems.md).
- **Re-attacks may be missing, or the string that played a note matters.** See
  [references/reattacks-and-strings.md](references/reattacks-and-strings.md).
- **A recorded part's dynamics go onto a virtual instrument.** See
  [references/velocities.md](references/velocities.md).
- **A passage between sections sounds broken, or a piece is about to be exported.** See
  [references/transitions.md](references/transitions.md).

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

Louder usually reads as better, so match levels before asking anyone to choose. What to match depends on the
question:

- For tone alone, matching each excerpt's own level is fair.
- For playing, dynamics, rests, articulation or arrangement, the level differences between passages are part of what
  is compared. Compute one gain per file on the whole piece and keep it in every excerpt taken from it. Level the
  whole files first and then take the excerpts with `cut`, which keeps levels. `match --seconds` cuts and fades each
  file before computing its gain, so it levels the excerpt itself and suits only the first case.

Use `--peak` for whole takes and `--rms` for short excerpts, where one hit would set the whole gain. Keep the
original files, and say which copies had their gain changed.

When versions differ in sustain, don't level them bar by bar against the reference again. A version with less
sustain then gets louder attacks, which hides the change being compared. Keep the per-bar gain curve of the control,
move it by one global offset per version, and record that offset separately. On one layer, switching a piano
preset's effects off took about 4.4 dB off its raw level, which a single offset of +5.65 dB put back without touching
the curve.

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
for its variation, or turn its modulation off only for the comparison and say so. `mps wav variation` compares the
signals sample by sample, which tells whether renders differ, not whether a given measure moved. When a decision
rests on a small difference in an attack, envelope, dynamics or band measure, take that measure on several renders
of each candidate and compare the medians against the spread. Call a difference inside the spread inconclusive, not
an improvement.

When a listening file is a sum of parts made offline, check that it equals the declared parts times their gains,
on the lossless files before any MP3. Give every candidate the same accompaniment, ideally the same audio files
rather than new renders, so round robin and modulation in the accompaniment don't differ between candidates.

To confirm automation or routing in a mix with modulated effects, also render a copy with the modulated sends muted.
What's left plays the same every time and should match the offline sum of the same parts with the same curves,
sample by sample. In one mix the full render matched its offline sum only to −14 dB of residual (modulated reverbs
and a delay), while the copy without them matched to −83 dB. That confirmed every envelope point by point.

Read the delivered files back before handing them over.
- **WAV with dither.** A 24-bit file with TPDF dither added once should read back equal to the quantized samples, with
  a residual near −144 dBFS against the float master.
- **MP3.** Decode it and measure its true peak at 8x oversampling, since the encoding can pass the master's ceiling.
  One MP3 made from a −1 dBTP master decoded at −0.975 dBTP (see Pro-L 2 in the `plugins` skill).

When two measures disagree, compare their windows, bands and definitions before changing the part. A dip at a chord
change read 1.8 dB when the minimum within 0.15 s was compared with the level 0.1 to 0.3 s away, and 15.5 dB when the
minimum within 0.5 s was compared with the median 0.6 to 1.3 s away. The minimum fell 0.2 s before the change, inside
the first method's reference window.

Report each number with what it takes to reproduce it where it applies, such as the band, the window length and
overlap, the range analyzed, how active frames were chosen, the normalization or gain, and the formula. Values that worked
on one recording are examples, not thresholds.

To judge a rebuild as a whole, export each part alone from the same project (in FL, the same pattern) and compare its level relative to the sum
of the parts, section by section, with the same parts in the reference's stems. The median difference across sections
is the fixed gain a part needs, and the spread is what a fixed gain can't fix, such as a part that grows in the
reference's arrangement. In one rebuild the drums sat about 6 dB low in every section. Correcting the three parts
offline by their medians raised the correlation of the 100 ms envelope with the reference from 0.40-0.83 to
0.67-0.94 per section, before any change to notes.

Loudness weighting still counts much of what lies below 60 Hz. When a part carries far more sub-bass than the
reference's stem, its loudness overstates what is heard. In one rebuild a low cut at 35 Hz took 1.8 LU off the drum
part, 1.3 LU of it from below 60 Hz, and the mix bands above 60 Hz moved under 0.2 dB. Measure the filter itself
before reading such a change, since a cut set at 35 Hz also took 2 dB from 60-100 Hz on the drums (see Pro-Q 4 in the
`plugins` skill). With both signals high-passed at 60 Hz (4th order), the unfiltered drums read 1.3 to 2.8 LU low
against the reference's stem, where the full band had read 0.2 to 1.2 LU low. So
compare part levels above the sub when the parts differ there, and calibrate the separator on the rebuild, whose true
parts are known (here the stem read within 0.35 dB of the true drums). The same applies to band shares normalized to
the total. A sub cut raises every other band's share, so read absolute bands with one reference gain instead.

### Tone apart from playing

To work on an instrument's sound without mixing in changes to the part, keep the MIDI fixed and change one link of the
chain per render. Measure at the reference's own attack times, since the render plays the same notes:

- how far the attack rises above the sustain right after it, broadband and above 2 kHz, where the pick sits
- how far the sound falls between one attack and the next
- crest factor, left-right correlation and the band profile normalized to the total

Choose the bands for the instrument and the question. When nearly all the energy falls in one band, the profile
can't tell versions apart. Guitar bands put 99% of a bass in their lowest band, while 20-80, 80-150, 150-300,
300-1000 and 1000-4000 Hz separated the bass versions. Those are an example, not a standard.

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
- A preset's internal effects can set most of its sustain. Render it with them off, and with each one off, before
  changing note lengths, envelopes or the instrument. On a piano preset that decayed far slower than the reference,
  the decay between attacks went from -1.3 to -16 dB/s with the effects off, and to -12.4 with only the reverb off,
  while shorter notes moved it about 2 dB/s and the amp envelope about 3. On an electric piano, neither the effects
  nor the note lengths moved the decay inside a note beyond the spread between renders (4.4 dB/s on that preset).
  There the effects made only the tail after the last note, so measure that spread before ranking the changes.

## Limits

- The tool knows nothing about taste, feel, timing or whether a part suits the song.
- `thumps` finds low attacks with little midrange. Its default threshold of 12 dB is calibrated on one guitar part,
  and it can miss hits in very short files, because the attack threshold comes from the file itself.
- `chords` compares pitch classes between 70 Hz and 1 kHz. It can't tell octaves or inversions apart.
