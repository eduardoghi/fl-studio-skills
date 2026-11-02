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
- Soloing a track makes the others report as muted. Read `isTrackMuted` after clearing the solo, not before.
- Piano roll scripts have no API to start them, so someone has to run them from Tools > Scripts in the piano
  roll of the target channel. Confirm the channel in the window title first, because notes go to whatever is open.
- No script call to load a plugin or render audio turned up, so plugin slots and the export dialog went through
  the interface. FL also has a command line exporter for saved projects, which wasn't tested here.

## Driving the interface from outside

Keystrokes go to the active window, not to FL. On a desktop with other terminals open, one misplaced click sent
shortcuts and a file path into another program.

- Before sending keys, read the title of the foreground window and refuse to continue if it isn't FL.
- Click only inside FL's current window rectangle. Don't maximize or resize it, because the user may need the
  windows around it.
- Coordinates go stale whenever a panel moves. Capture the screen before the first click of each step.
- Plugin windows open at different cascaded positions, so read each one before using a wheel or click on a knob.
- After a render, the mixer can sit behind the Playlist. A click meant for a mixer slot then paints clips in the
  Playlist. Bring the mixer forward by its header and check the panel title first. Right-click removes a stray clip.
- The first click on an inactive panel may only focus it. If a plugin window didn't open, don't send wheel events
  anyway, because they land on whatever is underneath.
- Check values in the hint bar after each change. Some knobs move in large steps and reach the minimum quickly.
- Render with the export dialog in Pattern mode when the song isn't arranged yet, and read its settings before
  pressing Start.
