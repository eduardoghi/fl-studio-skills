# Guitar Rig 7 (Native Instruments)

Observed on Guitar Rig 7 Pro as a VST3 effect in FL Studio 26.1.7. The manual wasn't read for this note.

- On a mixer slot it reports 16 `Macros Control` parameters, the rack's input gain, gate, limiter and master volume,
  the preset volume and mix, and the tape decks and metronome. The other slots read `unused` until a preset with
  components is loaded, so an empty rack exposes nothing about amps or cabinets.
- A fresh instance opens on an empty rack with the gate on at -71 dB. Placed after an instrument, that gate can cut
  quiet tails, so remove the instance or turn the gate off when it isn't processing anything.
- It reports a single preset to FL, so `fl_plugin_preset_step` can't browse its 1500 sounds.
- Its window ignored clicks posted by the bridge, both on the preset list and elsewhere, so presets and components
  can't be chosen without real mouse input. Plan a chain with plugins whose parameters are reachable, or have a
  person load the preset.
