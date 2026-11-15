# Guitar Rig 7 (Native Instruments)

Observed on Guitar Rig 7 Pro as a VST3 effect in FL Studio 26.1.7. The manual wasn't read for this note.

- On a mixer slot it reports 16 `Macros Control` parameters, the rack's input gain, gate, limiter and master volume,
  the preset volume and mix, and the tape decks and metronome. The other slots read `unused` until a preset with
  components is loaded.
- Once a preset loads, each component's controls fill those slots with names such as `AC Box XV Volume` or
  `Matched Cabinet Pro X-Fade`, so the chain can be read and adjusted from the host. Listing the `On/Off` entries that
  read `On` shows which components the preset uses.
- A fresh instance opens on an empty rack with the gate on at -71 dB. Placed after an instrument, that gate can cut
  quiet tails, so remove the instance or turn the gate off when it isn't processing anything.
- It reports a single preset to FL, so `fl_plugin_preset_step` can't browse its sounds.
- Its window ignored clicks posted by the bridge. With real mouse input a single click only selected a preset in the
  list, and a double click loaded it. Typing in its search box needed real key input too.
- The search covered the 1521 factory presets. Files in the user's `Sounds` folder (thousands of community presets)
  didn't come up by name.
- Real mouse and key input take the focus and move the person's pointer, so use them only with their permission and
  return the pointer afterwards.
