# EZdrummer 3

Everything here is observed on version 3.1.2, with the kit loading on a new instance. The manual wasn't read for this
note, and the plugin was only loaded, not played.

## Controlling it

Expect to work on its panel and in the piano roll. It reports 245 parameters through the bridge. Of the first 12, four
had names, `1. Bleed - OH`, `2. Bleed - Ambience`, `3. Bleed - Crunch` and `4. Tape - Drive`, and the rest were blank
slots like `5. `, which `fl_plugin_params` hides. The other 233 weren't read.

Grooves live in its own timeline, which has no parameters in that list. The note map wasn't checked, so read it from
the plugin or the manual before writing drum notes, because the FPC map in a project doesn't carry over.

A new instance feeds the Master, and the panel showed `Follow Host` with the project's 95 BPM.
