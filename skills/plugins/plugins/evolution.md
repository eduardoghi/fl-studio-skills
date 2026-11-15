# Evolution guitars (Orange Tree Samples)

The Evolution libraries share one engine. "Manual" means the Evolution Engine user guide, version 1.3.5, in our own
words. "Observed" means Evolution Indie Rock (engine shown as 1.3.0) in Kontakt 8.14.1 Portable, FL Studio 26.1.7,
unless it says REAPER 7.86.

## Overlapping notes

Manual. In the polyphonic string mode, the default, two overlapping notes within the legato range play as a
hammer-on or pull-off whichever strings they would use. The range is a major second up and down by default.

Observed. A part where every pair of notes sounding together was at least three semitones apart rendered with all
its written pitch classes, checked with `wav-check chords` bar by bar. A riff that lets four notes ring, such as one
string each, needs that kind of voicing or a smaller range.

- The range is reachable through the bridge as `Range Up` and `Range Dn` (2 ST by default). Each name appears twice,
  for the legato range and for the separate slide range, so `fl_plugin_set` by name can't tell them apart. That is a
  limit of setting parameters by name in the bridge.
- Manual. The engine keeps legato apart per MIDI channel, and a channel-based string mode picks the string from the
  channel. The FL bridge writes no MIDI channel per note, so neither is available from FL's piano roll script. REAPER
  writes a channel per note, see Strings by MIDI channel.
- Two notes on the same string need a small gap to be heard as two picks. A gap of 2 ticks at 96 PPQ was enough.
- Observed in renders, by the pick transient above 3 kHz at the second note. A note starting 2 semitones above one
  still held rose about 1 dB (no pick, a hammer-on), the same pair without overlap rose 26 dB, and a pair 5 semitones
  apart rose 28 dB even when overlapping. Two semitones down while overlapping rose 17 dB, a partial pull-off.

## Velocity

Observed on Indie Rock with no snapshot loaded, notes 54, 61, 66 and 73, three hits per velocity:

- Velocity 1 is nearly silent (about -77 dB attack RMS against -26 to -31 dB at 127), and from 12 to 127 the attack
  rises about 25 dB, monotonic and not straight. Hits of one velocity differ by under 3 dB, mostly under 1.1 dB.
- The curves differ by a few dB across the neck. Interpolating them in pitch predicted other notes and velocities
  within 1.3 dB (median), worst 3 dB.
- The level of a note's own semitone does not rise steadily. On notes 61 and 66 it fell 4 to 7 dB from velocity 96 up,
  likely a sample layer with a different harmonic balance, so it can't stand in for velocity in a chord.

## Tone

- The TONE page shows Distortion, Tremolo and Volume stompboxes, with a scroll bar for more below, which the bridge
  can't scroll (see Controlling it).
- Against one clean, reverberant rock guitar stem, Indie Rock's band profile matched within about 1 dB from 150 Hz
  to 4 kHz with no snapshot, while Evolution Strawberry sat 6 dB higher from 1 to 2 kHz and 5 dB lower from 150 to
  300 Hz. Comparing libraries this way, on the same notes, picks one before any mixing.

## Signal and tone chain

Manual. The SETUP list has a signal blend between the guitar as recorded and an enhanced version processed to bring
up the sustain, since a guitar is "attack heavy and light on the sustain". Indie Rock was recorded through a studio
console, tube preamps and compressors, with no amplifier, so its as-recorded signal is close to a DI. The TONE chain
runs distortion, tremolo, volume, wah, pedal reverb, EQ, compressor, chorus, flanger, rack reverb, delay, amp, spring
reverb and cabinet, so the built-in compressor sits before the amp.

Observed on Indie Rock with one MIDI part, measured against the part it was transcribed from:

- The blend is the parameter `Signal` (0% as recorded). At 50 to 75% the pick attack above 2 kHz dropped by 2 to 8 dB
  relative to the sustain that follows, the crest factor by 3 to 5 dB and the dip between notes by 3 to 6 dB, with the
  band profile unchanged within 1 dB.
- Every module's switch is a parameter named `On/Off`, as are their `Type`, `Gain` and `Mix`, so pick them by position
  (`fl_plugin_set` with `position`, from `fl_plugin_params`). The text of a Kontakt parameter changes a moment after
  it is set, and the answer to the set still shows the old text, so read it again after about 150 ms.
- The amp has 9 types, the cabinet 34 types, and the microphones and their positions depend on the cabinet.
- The built-in compressor lowered the crest factor much more than Fruity Compressor after the instrument at the same
  threshold, ratio and times, which barely moved the peaks.
- `Tracks` (Single, Double, Triple, Quad) layers separate takes left and right. With `Humanize` at 0 the left and right
  attacks stayed together and the left-right correlation fell to 0.3 to 0.5, at 5% it fell to about 0.1 with the
  attacks still together, and at 20% the attacks spread over about 13 ms.

## Initial state

Observed with no snapshot loaded:

- The chord mode is `Disabled`, so the main range plays the notes as written. In the other chord modes the main range
  is muted and held notes become strums (Manual).
- Only `SUSTAIN` is mapped, to velocity 1 to 127. Palm mute, mute, harmonics and the rest are unmapped.
- The playable range on Kontakt's keyboard is MIDI 40 to about 87. The strum and drone keys sit just below it, and
  the performance effect keys above it.

## Controlling it

- Kontakt reported every parameter's `value` as 0.0 while its `text` was right (`2 ST`, `50 %`). Read the text.
- The SETUP list ignored posted wheel events and clicks on its scroll bar, and the bridge can't drag, so settings
  below the first five rows can't be reached through the interface.
- A library loads without a double click through KONTAKT menu > Load recent, which the bridge can click because
  Kontakt draws its menus inside the plugin window. Loading from the Libraries browser needs a double click.
- The snapshot arrows in the instrument header did nothing with posted clicks, even with real mouse input before a
  snapshot was loaded, and the snapshot files are obfuscated. A snapshot loads by its file instead, through
  KONTAKT menu > Load (see `kontakt.md`), and then shows in the header. Reading the parameters after the load tells
  which modules the snapshot turned on.
- The gear icon at the left of the instrument header opens Instrument Options, a modal dialog that blocks FL and the
  bridge until it is closed (WM_CLOSE on its window cancels it).
- Cloning the channel (channel menu > Clone) copies the instrument with all its settings into a new channel right
  below, which shifts the index of every channel after it, but not their notes.
- Manual. `Channel-Based Strings` picks the string from the MIDI channel, channel 1 for the highest string by default.
  The legato logic also runs separately per MIDI channel, which needs Kontakt's MIDI input set to omni.

## Strings by MIDI channel

Observed in REAPER 7.86:

- `Channel-Based Strings` sits deep in the SETUP list and isn't a host parameter. Dragging the list's scroll bar with
  the real mouse reached it, and the wheel didn't scroll it. Its menu offers Disabled, MIDI Guitar, Bottom to Top and
  Top to Bottom. Set it once and save the whole state (see `kontakt.md`, In REAPER, for restoring it).
- With MIDI Guitar, E4 on channels 1 to 4 sounded on four strings. Its harmonics fell from -9.6 dB to -20.4, -29.7 and
  -27.9 dB relative to the fundamental, as from the open high string to fretted notes on thicker strings, while four
  repeats on channel 1 stayed within 3.4 dB of each other. So channel 1 is the highest string.
- E2 on channel 1, below what the highest string can play, still sounded, so the engine doesn't reject an impossible
  string. The note writer has to choose playable strings.
- Two overlapping notes a tone apart on the same channel played as a hammer-on (the pick band above 3 kHz rose 1.1 dB
  at the second note). On two channels the same pair was picked (23.3 dB), like the pair without overlap (25.8 dB).
  Legato stays within a string.
- 8 of 9 renders of the same part were sample-identical, and one differed on some notes, likely a round robin. Measure
  this variation before reading a small difference between two renders as a change. On a denser part of 110 notes, no
  two of four renders matched.
- Which string plays a note changes the brightness of the whole part. On one riff, a fingering model that charged 1 per
  fret of hand movement and only 0.1 per fret of height kept the hand at frets 7 to 16 and put a fifth of the notes on
  the low E string. The spectral centroid was 455 Hz, against 793 Hz when the engine chose the strings itself. Making a
  position change cost more than small moves and charging 0.5 per fret of height, still within a four-fret hand, raised
  it to 553 Hz. Check the string and fret distribution of a fingering before blaming the tone.
- With all notes on channel 1, the engine played that riff mostly in low position, on the B string at frets 0 to 6
  (estimated from the harmonic profile of 21 notes, see the `audio-verification` skill).

## Articulations

Observed on Indie Rock in REAPER 7.86.

- The PLAY page lists SUSTAIN (mapped to velocity 1 to 127), PALM MUTE, MUTE, HARMONICS and SQUEAL, the last four
  unmapped in the initial state. Each takes Velocity, Keyswitch, Latching Keyswitch, Sustain Pedal, Soft Pedal, Random
  or Controller #n from a menu at its row. Choosing Keyswitch assigned the next free low key, C#1 (MIDI 37) for the
  first and C1 (36) for the second, in Kontakt's naming where C3 is 60. Save the state afterwards, since none of this
  is a host parameter.
- A keyswitch acts on the whole instance, sent on the note's channel or on channel 1, so with Channel-Based Strings a
  part that needs an articulation and a part that doesn't need separate instances.
- On F#3 at velocity 100, a plain note fell 20 dB in about 1 s. Palm mute fell 20 dB in 290 ms and moved the spectral
  centroid from about 415 to 195 Hz, still clearly pitched. Mute (a dead note) fell 20 dB in 30 ms with the harmonic
  share 12 to 23 dB lower, nearly unpitched. Treat them as different articulations.
- Keyswitches held only around each note-on (from 20 ms before to 50 ms after) were enough. A part of 57 notes played
  that way rendered with its centroid at 449 Hz against 647 Hz without the keyswitch, and much shorter notes.
- The default pick style on the SETUP page is Economy Picking.

Manual, from the Evolution Rock Standard user's guide (same engine). The pick styles below were confirmed on Indie
Rock only as far as the default shown. Samples come in
three dynamics, down and up strokes and two round robins each, with every string recorded on its own. The SETUP list
has a pick style (Alternate, which goes back to a downstroke after a release gate time, Economy, and 8th and 16th note,
which play downbeats down and upbeats up), Pick Noise Amount, Release Volume, Legato Volume and the legato ranges, and
a fretting position that steers the automatic string choice.
