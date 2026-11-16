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

## In REAPER

Observed with Guitar Rig 7.0.2 as a VST3 effect in REAPER 7.86.

- The window still ignored posted clicks. A real click in the search box, typing the name with real Unicode key input,
  and a real double click on the result loaded a preset. Save the whole state afterwards (`mps state save`) and write
  it into later instances, so the clicks happen once per preset.
- Each factory rack preset (`Rack Presets\*.ngrr`, 1392 files here) starts with readable XML naming its amplifiers,
  characters and genres, for example `RP://Amplifiers` then a tab and `AC Box XV`. Reading it finds presets by amp
  without opening the plugin. `So Near So Far` uses the AC Box XV, and `Basic Twang Reverb` the Twang Reverb.
- After a preset loaded, `Metronome On/Off` read `On`. Turn it off before rendering.
- Two renders of the same chain on the same audio weren't identical, with a residual about 44 dB down.
