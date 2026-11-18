---
name: plugins
description: Notes on specific instruments and effects, covering what their controls do, the defaults that cause trouble, how their state can be saved and restored, and the parameter names a host sees. Use before adding or adjusting one of the listed plugins, or when a sound problem may come from a plugin's settings.
---

# Plugin notes

Read only the file of the plugin in use:

| Plugin | File | Worth knowing first |
|---|---|---|
| Vintage Chorus (FL Studio) | `plugins/vintage-chorus.md` | Adds hiss by default |
| Fruity Delay 3 (FL Studio) | `plugins/fruity-delay-3.md` | Starts at 100% wet with long repeats |
| LuxeVerb (FL Studio) | `plugins/luxeverb.md` | Starts at 0 dB wet, which covers the attack |
| Fruity Blood Overdrive (FL Studio) | `plugins/fruity-blood-overdrive.md` | Louder than it looks, lower Post gain to compensate |
| Fruity Reeverb 2 (FL Studio) | `plugins/fruity-reeverb-2.md` | Match room size and decay |
| Ample Guitar SC | `plugins/ample-guitar-sc.md` | Keyswitches are notes in the same piano roll |
| Omnisphere 3 | `plugins/omnisphere.md` | Patches change the octave, and choosing one needs the interface |
| ValhallaVintageVerb | `plugins/valhalla-vintageverb.md` | Starts at 100% mix, and its saved state restores exactly |
| EZdrummer 3 | `plugins/ezdrummer-3.md` | Note map measured, and its menus need the host in front |
| EZbass | `plugins/ezbass.md` | sounds an octave under the note written, keyswitch map, slides at a fixed speed, overlaps play legato, FL can load an old VST2 build |
| Evolution (Orange Tree) | `plugins/evolution.md` | Overlapping notes a tone apart become legato, unless each string gets its own MIDI channel |
| Kontakt 8 | `plugins/kontakt.md` | Its state bytes change on every read, so compare states by render |
| Guitar Rig 7 | `plugins/guitar-rig-7.md` | Exposes its components only after a preset loads, which takes a real double click |
| Archetype Cory Wong X | `plugins/archetype-cory-wong-x.md` | Its default amp and cabinet scoop the mids while the centroid looks right |
| PRISM (Aurally Sound) | `plugins/prism.md` | Every window shows one shared ARA document, so pick the track first |
| Melodyne 5 Studio | `plugins/melodyne.md` | The standalone's menus take `WM_COMMAND`, and its MIDI export puts the tempo map in a second file |

Each file says where its facts come from. "Manual" means the maker's documentation, in our own words. "Observed"
means a measurement on one machine, in FL Studio 26.1.4 or 26.1.7 or in REAPER 7.86, as each file states. A behavior
seen in one host or one plugin isn't assumed for another until it is tested there. The values are what one guitar
track used, so they are starting points to measure and not targets.

## Working with a plugin

1. List the real parameters first, because names differ from the labels on screen. `Size` on the panel is
   `Reverb size` in the API. Several parameters can share a name, as the `On/Off` of every module in a Kontakt
   instrument, so address them by index or position.

   In REAPER, through the `reaper` skill's bridge:

   ```text
   mps reaper call fx.params --args-file args.json        # {"track": "<guid>", "fx": 0, "contains": "reverb"}
   ```

   In FL Studio, through the legacy bridge:

   ```text
   fl_plugin_params(track=10, slot=3, contains="reverb")
   ```

   The FL list leaves out slots a VST didn't assign, such as `Param 12`, and the `MIDI CC #` and aftertouch entries FL
   adds. `hidden` counts them, and `named_only=False` shows them.

2. Set one and read its displayed text back, since the value goes from 0 to 1 and the scale differs per parameter.
   In REAPER that is `fx.set_param` with the index. In FL it is `fl_plugin_set` by exact name, with the `position`
   that `fl_plugin_params` lists when the name repeats.

   ```text
   fl_plugin_set(name="On/Off", position=63, value=1, channel=6)
   ```

3. Change one thing, render and measure with the `audio-verification` skill. Parameter changes stay out of FL's undo
   history, so keep the `before` value of each answer.

Check a new plugin's defaults before using it. A default that sounds fine alone can add noise or fill the mix later.

## Saving and restoring a plugin's state

A host can save a plugin's whole state as an opaque block (REAPER's `vst_chunk`) and write it back. Whether the
plugin takes it back, and how to check, differs per plugin, so each note records what was tested. Three checks mean
different things:

- integrity, the SHA-256 of the stored block, which only proves the file didn't change
- configuration, the displayed values of the exposed parameters after the restore, which some plugins report late or
  not at all
- sound, a render compared with renders of the original state, against the variation between repeated renders of
  that same state

## Adding a plugin here

Create one file with its source marked, keep only what isn't obvious from the panel, and add it to the table above.
Paraphrase the manuals.
