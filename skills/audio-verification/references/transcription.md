# Transcribing a part from a reference

Read this when a part has to be transcribed from a recording or a stem, or when a rebuild is checked note by note
against it. The section on polyphonic parts covers chords, layers and processed guitars.

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
- A kick leaking into a separated bass stem can pass for a repeated note, since it brings a short dip and some top
  end with no pitch change. Missing support from other transcribers is not enough to merge a repeat into the note
  before it, since they also join real repeats. Check each doubtful repeat on its own:
  - a rest measured before it (a gap after the previous note) rules out merging, because merging holds the note over
    the silence;
  - a dip that recurs in the stem, in stems from other separation models and in the mix is a real articulation, while
    a dip only in one stem may be leakage or a separation artifact;
  - the drum stem's low band at the same instant tells whether the dip follows the kick, as a group statistic more
    than as proof for one event;
  - render both readings on the rebuild instrument and compare the envelope around the event, because an instrument
    whose re-pluck digs a deeper dip than the original's soft one can match worse by re-plucking a real attack.

  On one stem, 45 of 235 repeats had no support from PRISM, Melodyne or the EZbass tracker. Only 21 of them fell
  within 60 ms of a kick. Merging all 45 held a note over a 162 ms rest. A per-event check kept 39 merged, restored
  6, and moved the attack that sat inside the rest to where the stem came back.
- Keep the transcription apart from the version adapted to an instrument. An articulation that is really in the
  recording may be one the library can't play faithfully, such as a soft re-attack it plays with a deep dip or a
  short bend it plays as a long slide. Keep the evidence and the transcribed note in the transcription, and record
  each adaptation and its reason in the rendered version, so a MIDI tuned to one library isn't taken for a more
  accurate transcription.
- After any change to note starts or ends, scan the whole piece for places where the original stops and the render
  keeps sounding. Compare a 30 to 150 Hz envelope of the stem with the render's, flag stretches where the stem stays
  35 dB under its 95th percentile for 60 ms or more while the render doesn't, and sort each one:
  - a real rest stops in the mix and in other separations too;
  - a separation artifact is silent in one stem only;
  - natural decay falls gradually and is the same in the other stems;
  - with no MIDI note active, the sound comes from the instrument, such as a keyswitch, a release or a compressor
    tail.
- When an instrument's release fills a rest, ending the notes may not be enough. A pad patch with a long release
  stayed only 5 dB down in a rest of 0.6 s after its notes stopped, while the reference fell by more than 40 dB.
  Shorten the patch's release, end the notes earlier, mute them with an articulation, or add a volume envelope over
  the rest, and ramp any gain change over a few tens of milliseconds so it doesn't click.
- When a correction moves a note's start, recompute anything calibrated at the old one. A velocity measured at a
  start that sat inside a rest came out at 44 instead of about 112.
- A sampled instrument with round robin can play different samples in two renders even where the notes are the
  same, for example after notes were added or removed earlier. Compare two renders on a stretch whose notes are
  identical to learn that noise floor before reading per-event or per-bar differences. On one bass it reached 1 to 2
  dB per event.
- Commercial transcribers are a check, not a source of truth. On that bass, none added a note the segmentation had
  missed. Melodyne Melodic and the EZbass Audio Tracker joined repeated notes into long ones, and PRISM read 13 notes
  a semitone low. Count matched attacks, pitches on the matched notes and repeats kept, and render every candidate on
  the same instrument before judging by ear (`plugins/melodyne.md`, `plugins/ezbass.md` and `plugins/prism.md` in
  the plugins skill have the export steps).
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

## Polyphonic parts

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
- A strong note also lifts the bins a semitone away. In one pad stem, taking every bin above a floor filled the chords
  with pairs a semitone apart (B3 with C4, F#3 with G3), and keeping only bins that are local peaks across semitones
  left the triads. A local peak rule doesn't prove that two neighbouring notes can't sound together, so check a
  cluster against other evidence (another separator, the harmony, a render) before dropping it.
- Weak spectral evidence for a note doesn't show the note is absent. Before removing one, ask for a second sign, such
  as no rise of its semitone's energy at the attack. The two signs complement each other but aren't independent,
  since both read the same bins. A missing rise alone proves nothing either. In one octave layer, 22 of 143 notes read
  directly showed no rise because their pitch was already sounding, and all of them had strong evidence. Of 118 notes
  added by a doubling rule, 38 were weak and 21 were weak with no rise. Removing those 21 changed the pitch profile
  against the stem by less than the spread between two renders of the same notes, so the choice went to listening.
- For a sustained layer, read Mid and Side apart when it is wide, and place chord changes where the outgoing and
  incoming voices cross rather than on the grid. Rendering each voicing hypothesis on a plain sine and comparing the
  semitone profile per beat with the stem settled the voicings. It can't settle articulation (a held note against
  one struck again), because a sine with a long release hid a 30 ms gap. Test that on the instrument that will play
  the part.
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
