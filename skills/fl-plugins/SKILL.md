---
name: fl-plugins
description: Notes on specific plugins used in FL Studio, covering what their controls do, the defaults that cause trouble and the exact parameter names for the bridge. Use before adding or adjusting one of the listed plugins, or when a sound problem may come from a plugin's settings.
---

# Plugin notes

Read only the file of the plugin in use:

| Plugin | File | Worth knowing first |
|---|---|---|
| Vintage Chorus | `plugins/vintage-chorus.md` | Adds hiss by default |
| Fruity Delay 3 | `plugins/fruity-delay-3.md` | Starts at 100% wet with long repeats |
| LuxeVerb | `plugins/luxeverb.md` | Starts at 0 dB wet, which covers the attack |
| Fruity Blood Overdrive | `plugins/fruity-blood-overdrive.md` | Louder than it looks, lower Post gain to compensate |
| Fruity Reeverb 2 | `plugins/fruity-reeverb-2.md` | Match room size and decay |
| Ample Guitar SC | `plugins/ample-guitar-sc.md` | Keyswitches are notes in the same piano roll |

Each file says where its facts come from. "Manual" means Image-Line's or Ample Sound's documentation, in our own words.
"Observed" means FL Studio 26.1.4 on one machine. The values are what one guitar track used, so they are starting
points to measure and not targets.

## Working with a plugin

1. List the real parameters first, because names differ from the labels on screen. `Size` on the panel is
   `Reverb size` in the API.

   ```text
   fl_plugin_params(track=10, slot=3, contains="reverb")
   ```

2. Set one by exact name. The value goes from 0 to 1, and the scale differs per parameter, so read the `text` field
   of the answer instead of assuming.

   ```text
   fl_plugin_set(name="Noise", value=0, track=9, slot=0)
   ```

3. Change one thing, render and measure with the `audio-verification` skill. Parameter changes stay out of FL's undo
   history, so keep the `before` value of each answer.

Check a new plugin's defaults before using it. A default that sounds fine alone can add noise or fill the mix later.

## Adding a plugin here

Create one file with its source marked, keep only what isn't obvious from the panel, and add it to the table above.
Paraphrase the manuals, since they are Image-Line's text.
