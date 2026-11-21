# Vocal takes against a guide

Read this when a sung take has to be placed against a guide vocal and the song's timeline, checked for pitch and
notes, or tuned without changing the performance.

These come from one take sung along with a generated guide, an octave below it and with no processing, as examples
of what to check.

## Placing the take

- **Put the guide on the project's timeline first.** A guide's own accompaniment can run against the project's
  timeline even when the arrangement is the same. Correlate the spectral flux of the guide's accompaniment with the
  project's reference over the whole song, then refine on the waveform below 200 Hz. One set of stems ran 0.444 s
  ahead of the project. In windows of 10 s along the song the offset stayed between 0.429 and 0.446 s, so there was no
  drift to correct. Stems exported together share their timeline.
- **Align by pitch class, not by level.** A take in another octave and timbre doesn't match the guide's envelope
  well. One level envelope gave phrase offsets that disagreed by up to 500 ms. Track f0 on both (torchcrepe worked),
  turn each voiced frame into a 12-class pitch vector, which ignores the octave, and correlate the two sequences at
  every lag. The peak stood clear of the next candidate (0.32 against 0.21) and agreed with the level envelope's best
  lag within 20 ms.
- **Correct phrases only when methods agree.** Melody repeats in a song, so a short phrase can lock onto the wrong
  place. In the take, the long phrases sat within −80 to +70 ms of the guide, while some short ones gave 400 to
  600 ms by one method and much less by another. Shift a phrase only when its offset holds across methods. Otherwise
  keep the global offset and leave the phrase to listening.

## Pitch and notes

- **Tuning.** Measure tuning against the nearest semitone, on the middle 60 % of each note, so the scoops at the ends
  don't count. The take had a median deviation of 16 cents, and only 5 notes of 250 ms or more were over 25 cents.
- **Notes that differ from the guide.** With the octave removed, a note that sits on a semitone but far from the
  guide's note is a different note, not bad tuning. Check which note the harmony supports with the accompaniment's
  chroma at that moment. Of nine notes that differed from the guide, four had the guide's pitch class clearly stronger
  in the accompaniment (1.00 against 0.30, for example). Those are questions for a new take, and tuning shouldn't
  move them.

## Tuning without changing the performance

- **How.** Shift whole notes, not frames. Praat's PSOLA through parselmouth (`To Manipulation`, multiply the pitch
  tier over each note with ramps of about 40 ms, `Get resynthesis (overlap-add)`) keeps the formants. Because the
  whole contour of the note moves by one factor, the vibrato, the entry and the exit stay as sung.
- **Where.** Take only the corrected notes from the resynthesis, with short crossfades where the factor is still 1,
  and keep the rest of the take sample for sample.
- **Measured on 5 notes corrected by 75 % of their deviation.** They went from −40 to +46 cents to −16 to +2 cents.
  The vibrato changed by at most 3 cents and the level by at most 0.2 dB. The resynthesis left a small coloration in
  those notes, up to −1.6 dB between 800 Hz and 6 kHz, which is worth reporting.
- **Check the two versions.** Run them through the same chain and compare them outside the corrected notes. With the
  same compressor and de-esser, the two differed by −86 to −90 dBFS there.
