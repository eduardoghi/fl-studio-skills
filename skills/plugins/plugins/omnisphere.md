# Omnisphere 3

Everything here is observed on version 3.0.0d. The manual wasn't read for this note.

## Watch out

Patches change the part's octave without saying so. Check `OCTAVE` on the MAIN page after each load. The same chords
gave very different results depending on it:

| Patch (Scoring Electronic, Pads) | Octave on load |
|---|---|
| Analogue '80s Soundtrack | -1 |
| Swelling Warm JP-8 Solar | -1 |
| Harmonial Evolutions Warm | +1 |
| Distant Memories | 0 |

With Analogue '80s Soundtrack at -1, 58% of the energy fell below 120 Hz. At 0 that share was 27%.

Levels differ between patches too. The same chords at a 0 dB fader measured from -15.2 to -27.6 dBFS RMS, so render
each patch before comparing and match the pad to the part it sits under.

Slow patches lag behind a chord change. On two of the four patches above, `wav-check chords` read the previous chord
over the first beat of a 4 beat chord at 95 BPM, and all the notes after that. See `--skip` in `audio-verification`.

## Controlling it

Choosing a patch needs the interface. Pick DIRECTORY, then CATEGORY, then click a row in the list. One wheel notch
scrolls the list by one row. An asterisk after the patch name means it was edited, and a changed octave counts.

All of that worked with FL behind other windows. DIRECTORY and CATEGORY open Windows menus, which take `fl_menu_keys`
because a posted click closes them without choosing. Those two appear on screen. After that, `fl_click` on a row or
on the arrows beside the patch name changes the patch, and `fl_scroll` moves the list, with nothing shown in front of
other programs. The arrows do nothing until a directory is chosen.

Through the bridge the plugin reports 658 parameters, and only 10 are real. They are `Level (p1)` to `Level (p8)`, one
per part, plus `Bypass` and `Program`. `fl_plugin_params` hides the other 648. Filter, envelope and patch controls
aren't among them, so those stay on the panel. `fl_plugin_set` wasn't tried on it, and neither were `Program` or the
preset tools.

A new instance feeds the Master, so point its channel at its own insert before adding effects.
