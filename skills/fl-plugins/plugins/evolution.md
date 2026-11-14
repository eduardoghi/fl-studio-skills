# Evolution guitars (Orange Tree Samples)

The Evolution libraries share one engine. "Manual" means the Evolution Engine user guide, version 1.3.5, in our own
words. "Observed" means Evolution Indie Rock (engine shown as 1.3.0) in Kontakt 8.14.1 Portable, FL Studio 26.1.7.

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
  channel. The bridge writes no MIDI channel per note, so neither is available from the piano roll script.
- Two notes on the same string need a small gap to be heard as two picks. A gap of 2 ticks at 96 PPQ was enough.

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
