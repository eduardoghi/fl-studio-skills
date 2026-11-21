# Re-attacks, sustained notes and strings

Read this when a transcription may be missing re-attacks of notes already sounding, or when the guitar string that
played a note matters.

A transcription that gives almost every note the same length, from one attack to the next, may be cutting sustained
notes at each attack and missing re-attacks of notes already sounding. In one guitar part, 35 of 110 transcribed notes
continued the previous note of the same pitch with no new attack, while the recording had about twice as many attacks
as the transcription, many on sixteenth offbeats.

- Count attacks in the recording itself, from the spectral flux of the percussive part (HPSS) above 2.5 kHz, and
  compare their number and the intervals between them with a render of the transcription.
- To tell which known pitch was re-attacked, compare the level of its fundamental band after the attack with the
  minimum just before. On a render with known notes, a rise of 3 dB was right for 87% of the re-attacks it found and
  found 62% of them, and a rise of 1 dB was right for 84% and found 83%.
- Don't search every pitch this way. The pick's transient raises every band at once, and measured at the attack the
  search invented hundreds of pitches on the known render. Measured in the sustain, 60 to 140 ms after the attack, and
  requiring a tonal peak, it still invented about one pitch per attack, scattered over unrelated intervals. Pitches
  missing from a transcription need another source, such as a polyphonic editor.
- An octave above a note sounding at the same time can be the lower note's second harmonic read as a note. Compare the
  even-to-odd harmonic ratio of the lower note with a calibration of that note alone, since a real upper note raises
  the even harmonics well above it. The test only works one way, since a weak real note passes as a harmonic.

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
