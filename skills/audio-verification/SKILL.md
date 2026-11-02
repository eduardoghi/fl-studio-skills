---
name: audio-verification
description: Check exported audio with measurements instead of guessing, since the agent can't listen. Use after rendering a mix or stem from FL Studio, when the user reports noise, clicks, thumps, harshness or low volume, to confirm that chords sound the notes that were written, or to prepare level-matched versions for an A/B comparison.
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
wav-check width a.wav                         # left/right correlation and side level
wav-check match out/ --peak -8.8 a.wav b.wav  # same level for A/B listening
```

Run it with `uv run --no-project --with numpy python bin/wav-check` if numpy isn't installed.

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

## Comparing versions

Louder usually reads as better, so match levels before asking anyone to choose. Use `--peak` for whole takes
and `--rms` for short excerpts, where one hit would set the whole gain. Keep the original files, and say which
copies had their gain changed.

Change one thing per render.

## Limits

- The tool knows nothing about taste, feel, timing or whether a part suits the song.
- `thumps` finds low attacks with little midrange. Its default threshold of 12 dB is calibrated on one guitar part,
  and it can miss hits in very short files, because the attack threshold comes from the file itself.
- `chords` compares pitch classes between 70 Hz and 1 kHz. It can't tell octaves or inversions apart.
