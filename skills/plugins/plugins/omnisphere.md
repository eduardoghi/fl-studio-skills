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

## In REAPER

Observed on 3.0.2c (VST3) in REAPER 7.86 with real mouse input, which moves the user's pointer, so ask first.

- A new instance opened on the about page. A click on the Spectrasonics logo brought back the main page.
- DIRECTORY and CATEGORY open Windows popup menus. A real click opens them, and the item takes a real click at its
  screen position as long as the plugin window isn't activated again first, because activating it closes the
  popup. A submenu opens when the pointer rests on its row, and the pointer has to slide right along that row to
  reach it.
- A real click on a row of the list loads the patch. Its full state, read with `fx.state_get` once two reads in a row
  match, rendered later with that patch in a new instance, so a screening can collect states first and render them
  in a batch. With a load delay (`fx_delay`) of 20 s, none of 25 such renders came out silent.
- The EFFECTS switch on the MAIN page turns off AMBIENCE, TONE and the FX page together, and the level moves with it.
  On two Live Keyboardist presets it changed the render's RMS by +7 dB (an electric piano, peaks past 0 dBFS) and
  -4 dB (a piano), so match levels again after switching it. AMBIENCE AMOUNT alone takes out the reverb.
- On Dreamy Rhodes, dragging the MAIN DECAY knob down, even 15 px, left only the attack click, about 40 dB quieter.
  Check each change to a MAIN envelope knob with a render before using it to shorten a sound.
