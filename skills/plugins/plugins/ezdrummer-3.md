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
