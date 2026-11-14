# EZbass

Observed on version 1.3.4 (VST3) in FL Studio 26.1.7. The manual is behind a login and wasn't read.

## Check which build FL loads

FL listed EZbass under its VST plugins and loaded a VST2 build from 2020 (1.0.5) left in
`C:\Program Files\Common Files\VST2\Toontrack\`, while the standalone and the VST3 were 1.3.4. The old build refused
the EZbass Modern library with a dialog asking for version 1.1.0. The version shows under the logo at the bottom
left. Removing the old DLL and rescanning in Options > Manage plugins made FL use the VST3.

## Controlling it

- A new instance opened on EZbass Modern with the `Clean DI` preset.
- The model selector next to the preset name is a JUCE menu. It closes as soon as FL leaves the front, so the bridge
  can only reach it with `fl_click(..., focus=True)`, on the selector and again on the row.
- Its parameters, articulations and keyswitches weren't checked yet.
