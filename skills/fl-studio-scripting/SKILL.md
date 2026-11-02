---
name: fl-studio-scripting
description: Write and debug Python scripts that run inside FL Studio 2026, and drive its interface from outside. Use when a MIDI controller script or a piano roll script fails with SystemError, can't read or write a file, or never runs its idle callback, when building a bridge between an agent and FL Studio, or when automating FL's windows on Windows.
---

# FL Studio 2026 scripting in practice

Everything here was observed on FL Studio 26.1.4 on Windows, MIDI scripting version 45, with the embedded
Python 3.12.1. It comes from one install, so treat it as observed behavior of that build, not as documented API.
For the API itself see [delorenj/flstudio-scripting-skill](https://github.com/delorenj/flstudio-scripting-skill).

## Files

A script can only open files inside its own folder. A probe that wrote to seven folders succeeded only in the
script's folder, `Settings/Hardware/<name>/`, and reading a file elsewhere failed the same way.

| Call | Inside its own folder | Elsewhere |
|---|---|---|
| `open` | works | `SystemError` |
| `os.mkdir`, `os.makedirs` | not tested | `SystemError` |
| `os.rename` | `SystemError` | not tested |
| `os.path.exists`, `os.path.isdir` | works | works |

The failure looks like this, and it isn't an `OSError`:

```text
SystemError: <class '_io.FileIO'> returned NULL without setting an exception
```

`except OSError` doesn't catch it, so an error in `OnInit` stops the script. Catch `Exception` around file calls
and print the error. An except clause that hides read errors makes a blocked file look like an empty mailbox.

What follows from that for a bridge with an outside process:

- Keep the mailbox in the script's folder, and point the outside process there. A folder under the user's home
  doesn't work, even with normal Windows permissions.
- `os.getcwd()` returned the script's folder for both a device script and a piano roll script.
- Device scripts and piano roll scripts live in different folders, so each one got its own mailbox. Reading across
  them wasn't tested.
- Without `rename` there is no atomic replace on FL's side. Write in place and let the reader retry on partial JSON.
- Mark a piano roll queue as done by overwriting the file with `{}`, then treat an empty object as nothing queued.

## Callbacks

`OnMidiMsg` ran on every incoming message. `OnIdle` never ran for a script with no port number
(`device.isAssigned()` was 0 and `device.getPortNumber()` was -1), which may be the cause, though that wasn't
isolated. Don't rely on `OnIdle` alone. A bridge can do its work from `OnMidiMsg` when the doorbell arrives and keep
`OnIdle` as a polling fallback.

Reload the script from View > Script output after replacing the file. A running script keeps the old code.

## Mixer and channels

- While a script message box is open, calling `mixer.setTrackVolume` raises
  `RuntimeError: Operation unsafe at current time`. Close the dialog and retry.
- FL applies mute, solo and window changes after the call returns. `isTrackMuted` read in the same call returns the
  old value, so read it in a later request. Showing a window right after hiding it in one call has the same problem.
- Soloing a track makes the others report as muted. Read `isTrackMuted` after clearing the solo, not before.
- `mixer.getTrackPeaks` kept reporting levels on muted tracks, so it can't prove what is audible.
- `mixer.trackCount()` includes a last entry that isn't a real track. Reading it logs `Invalid mixer track nr`.
- `plugins.getName(index, slot, midi.FPN_Preset)` returned an empty string after `nextPreset` and a name after the
  next step, so don't use it to confirm the current preset.

## Plugins

`plugins.*` takes `(index, slot)`. For an instrument, index is the channel and slot is -1. For an effect, index is
the mixer track and slot goes from 0 to 9.

- VSTs report thousands of parameters, mostly empty. Ample Guitar SC has 361 named ones out of 4240. Skip names that
  are blank or start with `?`, and find parameters by name, because indexes differ between plugins.
- `setParamValue` took effect at once on LuxeVerb and Ample Guitar SC, and `getParamValueString` gives the value in
  the plugin's own units, such as `7.527s`.
- Parameter changes and `nextPreset` didn't enter the undo history, so keep the old values to restore them.
- `plugins.getPadInfo(channel, -1, 1, pad)` gives the note of an FPC pad, and option 0 gives the pad count.
- Which of Ample Guitar's amps is active isn't among the parameters that were listed.

## Piano roll

- A piano roll that is already open keeps its channel when another one is selected. Select the channel, hide the
  window, and show it in a later request.
- The caption can't prove the channel. FL draws the name itself, so `ui.getFocusedFormCaption()` and Windows both
  return `Piano roll -`. Compare the existing notes before writing. Comparing note counts was right on 10 of 10
  alternating reads, but two channels can share a count, so a hash of the notes is safer.
- Nothing in the API starts a piano roll script. Ctrl+Alt+Y runs the last one again, after a first run from
  Tools > Scripts in that session, and the keys need FL as the active window.

## Rendering

`FL64.exe /R<output.wav> /Ewav /O<folder> project.flp` opens a separate FL, renders and closes. It took 18 s for
20 s of music with two Ample Guitar instances, and the file matched an export from the dialog within 0.2 dB of peak
and RMS. With FL already open the same command exits with code 0 and writes nothing, so check that the file exists.
No script call to load a plugin or render audio turned up, so plugin slots go through the interface.

## Driving the interface from outside

Keystrokes go to the active window, not to FL. On a desktop with other terminals open, one misplaced click sent
shortcuts and a file path into another program.

- Before sending keys, read the title of the foreground window and refuse to continue if it isn't FL.
- Click only inside FL's current window rectangle. Don't maximize or resize it, because the user may need the
  windows around it.
- Coordinates go stale whenever a panel moves. Capture the screen before the first click of each step.
- Plugin windows open at different cascaded positions, so read each one before using a wheel or click on a knob.
- Clicking FL's title bar can send a detached piano roll behind the Playlist, and the same stray click problem follows.
- After a render, the mixer can sit behind the Playlist. A click meant for a mixer slot then paints clips in the
  Playlist. Bring the mixer forward by its header and check the panel title first. Right-click removes a stray clip.
- The first click on an inactive panel may only focus it. If a plugin window didn't open, don't send wheel events
  anyway, because they land on whatever is underneath.
- Check values in the hint bar after each change. Some knobs move in large steps and reach the minimum quickly.
- Render with the export dialog in Pattern mode when the song isn't arranged yet, and read its settings before
  pressing Start.
