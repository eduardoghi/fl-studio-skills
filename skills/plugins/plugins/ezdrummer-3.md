# EZdrummer 3

Observed on version 3.1.2 in FL Studio 26.1.7, with the Post-Rock kit. The manual is behind a login and wasn't read.

## Note map

The default MIDI In preset is `Toontrack Standard`, in Settings > E-Drums/MIDI In. Each note below was written as one
hit, rendered and measured, so the piece is identified by its sound and not only by its name in a list.

| Note | Piece | What the render showed |
|---|---|---|
| 36 | Kick | 99% of the energy below 150 Hz, 0.19 s |
| 38 | Snare, center | Body at 141 Hz, 0.20 s |
| 40 | Snare, rimshot | Same body, 4.5 dB louder than 38 |
| 37 | Snare, sidestick | Mostly 150 Hz to 5 kHz, quieter |
| 42 | Hi-hat, closed | 72% above 5 kHz, 0.29 s |
| 44 | Hi-hat, pedal | Quiet, 25% above 5 kHz |
| 46 | Hi-hat, open | 64% above 5 kHz, 1.0 s |
| 49, 57 | Crash 1 and 2 | Broad band, long |
| 51 | Ride, bow | Long, centroid near 1 kHz |
| 53 | Ride, bell | Long, brighter than 51 |
| 48, 47, 45 | Toms, high to low | Pitched at 124, 105 and 108 Hz |
| 43, 41 | Floor toms | Pitched at 67 and 59 Hz |

47 and 45 sounded nearly the same pitch on this kit, so check toms by ear on another one. The cymbals came out about
20 dB below the kick with the kit's mixer preset, which is a mixer setting rather than the map.

## Controlling it

- Through the bridge it reports 245 parameters, and only 5 are real (`1. Bleed - OH`, `2. Bleed - Ambience`,
  `3. Bleed - Crunch`, `4. Tape - Drive` and `Bypass`). `fl_plugin_params` hides the rest. Kits, grooves and the map
  have no parameters.
- The kit selector and the Settings menu are JUCE menus. They close as soon as FL leaves the front, which is the
  plugin's behavior, so the bridge can only reach them with `fl_click(..., focus=True)` on both the selector and the
  row. See "Working without focus" in `fl-studio-scripting`.
- In the E-Drums/MIDI In panel, the Velocity and Mapping tabs ignored posted clicks even with FL in front, while the
  panel's selectors answered. The map was read from renders instead.
- Choosing a kit loads its own mixer preset, `Basic Rogers` for Post-Rock.
- In REAPER 7.86 the kit selector took a real click on the selector and on the row, and Post-Rock loaded its mixer
  preset there too. The same MIDI rendered in REAPER came out 2.1 dB louder than FL's render in every band, with the
  same band profile and stereo, so match the level when moving a part between hosts. With the level matched, the two
  differed by -7.4 dB of residual against -13.5 dB between two REAPER renders, from different round robin samples.
- A new instance feeds the Master and follows the host tempo (`Follow Host` is on). It plays the notes it receives
  without anything in its own timeline.

## Separate outputs without the interface

Seen on 3.1.2 only (the state header reads `EZd3` followed by the bytes 03 01 02) in REAPER 7.86, with Post-Rock and
its Basic Rogers mixer. Check the state and the result again on any other version before relying on this.

- The plugin has 32 outputs, and its internal mixer is stored as text inside the state (`fx.state_get`). Each mic
  routes to a bus (`route buss N`). The buses come in left and right pairs (here Kick 0/1, Snare 2/3, Hi-Hat 4/5, Toms
  6/7, OH 8/9, Ambience 10/11, FX 12/13, a shared Comp 14/15 and a shared Reverb 16/17). Each one has its own effect,
  and the channels feed the shared pairs through `send 7` (Comp) and `send 8` (Reverb). Every bus pair, the shared
  ones included, had `route output 0`, which is outputs 1/2, and nothing processed the sum after the outputs.
- Changing that 0 to a single digit N for both halves of a pair moves the bus to output N (channels 2N+1 and 2N+2).
  A single digit keeps the state the same length. A longer edit wasn't tried, since the header may hold the size.
  Leave the original state on the approved track and put the edited copy in a new instance.
- To hear the outputs in REAPER, give the instrument's track as many channels as the outputs use (`track.set
  channels`), turn its send to the parent off and capture each pair on its own track with a post-FX send from that
  pair (`send.add src_channel`).
- Moving nine pairs left output 0 digitally silent. The sum of the outputs matched the same kit rendered in stereo
  within 0.06 dB per section and 0.06 dB of band error, the same as two stereo renders. The shared Comp and Reverb come
  out on their own outputs, so the sum keeps the parallel compression and the reverb, and each channel keeps its own
  bleed. The outputs measured as expected (Kick centroid 59 Hz, Hi-Hat 8.8 kHz). The FX bus was silent in that song.
- The separated version is a new performance. Against an FL render of the same MIDI, both REAPER versions stayed
  within 0.16 dB per section but left -7 dB of residual from other round robin samples. Keep the approved render
  playing when its exact samples matter.
- There's no fixed offset between the hosts to correct. Correlating the band below 150 Hz over 15 s windows put the
  REAPER render -3 to +6 samples from the FL render depending on the window, against 0 to 2 samples between two REAPER
  renders. Above 2 kHz the two hosts correlated under 0.2, since the samples differ.
- Each render picks other samples, so outputs rendered in separate passes aren't one performance. Nine outputs
  rendered one per pass summed to -14 dB of residual against the sum rendered in one pass, close to the -10 dB between
  two whole renders. To get every output of one performance, render once to a multichannel master. Give the master as
  many channels as the instrument's track (`MASTER_NCH 20 2` in the .rpp, which the bridge doesn't set), leave the
  instrument's send to the parent on, drop the capture tracks, and render 20 channels (`render.configure` with
  `channels` 20, then `mps render --channels 20 --allow-nonstandard`). Each pair of the file is one output, and the
  pairs sum to the stereo performance of that pass.
