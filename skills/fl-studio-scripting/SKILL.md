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

Reload the script from View > Script output after replacing the file. A running script keeps the old code. That panel
is a top-level window that stays above FL and takes up the screen, so close it after reloading. `WM_CLOSE` works.

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

- A piano roll that is already open keeps its channel when another one is selected. Hide the window, select the
  channel and show the window, each in its own request. With the hide and the selection in one call, FL put the
  selection back on the piano roll's channel, and waiting longer didn't help.
- The caption can't prove the channel. FL draws the name itself, so `ui.getFocusedFormCaption()` and Windows both
  return `Piano roll -`. Compare the existing notes before writing. Comparing note counts was right on 10 of 10
  alternating reads, but two channels can share a count, so a hash of the notes is safer.
- Nothing in the API starts a piano roll script. Ctrl+Alt+Y runs the last one again, after a first run from
  Tools > Scripts in that session. See "Working without focus" for pressing it with FL behind other windows.

For dozens or hundreds of notes, `bin/fl-notes` in this repository talks to the bridge from Python instead of
passing every note through `fl_queue_notes`. `fl-notes read` saves channels of a pattern to a JSON file, and
`fl-notes write` writes such a file back. It reads every channel before writing any, so a channel holding other notes
stops the whole write, and it reads each channel back after writing it. Velocity is compared in FL's steps of 1/128,
since 0.62 reads back as 0.617, and times in ticks of the project's PPQ. The Empty template uses 96, where a length of
3.9 beats reads back as 3.8958. The same functions are in `fl_bridge.notes` for scripts that build their notes.

## Importing MIDI

FILE > Import > MIDI file, observed on 26.1.7 with a type 1 file at 960 PPQ holding three named tracks, markers, a
1/4 pickup bar, a tempo of 104.4859 BPM, velocities from 1 to 127, offsets of a few ticks, CC1, CC11, CC64 and
pitch bend. `fl_import_midi` wraps it.

- Every note came back with its pitch and velocity, a few velocities one step lower.
- Timing follows the project's PPQ. At 96 the offsets were rounded away (errors up to 5.4 ms) and so were short
  gaps between notes. At 960, start and length matched exactly.
- The tempo was rounded to 104.000. `fl_set_tempo` takes 3 decimals and truncates the rest (104.4859 became
  104.485).
- Each track became a channel named after it, with a mixer track, but all notes went into one pattern named after
  the file, and nothing was placed in the Playlist. The markers did appear on the Playlist's ruler.
- The pickup survived as an offset, the pickup note at beat 0 and the first downbeat at beat 1. The 1/4 time
  signature was not shown, so FL's bar numbers sit a beat ahead of the music's.
- FL asks to save changes before the Open dialog. With `Start new project` on, No discards the project. With it off,
  No only skips saving. FL turns `Start new project` back on for every import, and a new project starts at 96 PPQ.
- With `Create one channel per track`, a second import reused and renamed the existing channels from channel 0 on
  instead of adding new ones. A channel renamed beforehand got the MIDI track's name back. The notes went into the
  current pattern, and other patterns kept theirs.
- The Open dialog keeps the file name in an `Edit` with id 1148 inside a `ComboBoxEx32`, not the 1001 of the save
  dialog, and needs the same `EN_CHANGE`.
- Where CC and pitch bend end up wasn't checked. The piano roll script reads notes only.

The Playlist can't be written from a script. The `playlist` module of the API has track and performance mode
functions and nothing that adds, moves or reads clips.

## Rendering

`FL64.exe /R<output.wav> /Ewav /O<folder> project.flp` opens a separate FL, renders and closes. It took 18 s for
20 s of music with two Ample Guitar instances, and the file matched an export from the dialog within 0.2 dB of peak
and RMS. With FL already open the same command exits with code 0 and writes nothing, so check that the file exists.
No script call to load a plugin or render audio turned up, so plugin slots go through the interface.

## Working without focus

FL can stay behind other windows while it is driven, so the person can keep typing elsewhere. Messages posted to its
windows don't take the focus or move the mouse. FL still opens menus and dialogs above other programs, so the bridge
hides them as described in "Hiding FL while it works".

| Action | What worked | What failed |
|---|---|---|
| See FL | `PrintWindow` with flag 2 on the main window | Minimized, it returns a 160x28 bar or fails |
| Click a panel or a VST | Post `WM_MOUSEMOVE`, button down and up to the innermost window at the point | A click sent to a parent panel |
| Scroll | Post `WM_MOUSEWHEEL` to the innermost window, with screen coordinates in lParam | |
| Choose a menu item | Post arrow keys and enter to the menu's window | Posted clicks close the menu and choose nothing |
| Press a shortcut | Hold the modifiers in FL's thread, then post the key to a panel | Posting to the main window, or posting Ctrl as a key |
| Load a plugin | Row menu in the browser, `Open in new channel` | Posted drags start and never drop |
| Fill a save dialog | `WM_SETTEXT` on the `Edit` with id 1001, then `WM_COMMAND` with `EN_CHANGE` to its parent, then `BM_CLICK` on button 1 | The other `Edit`, which belongs to the address bar and is ignored. `WM_SETTEXT` alone, which on Windows 11 build 26300 saved as `untitled.wav` |
| Export | FILE > Export > Wave file with keys, then Start, with FL hidden | Ctrl+R raised FL above the focused window. Render minimized restores FL at the end, and that took the focus |

Shortcuts need the most care. FL reads Ctrl and Alt from the state of its own thread, so attach to that thread with
`AttachThreadInput`, change the state with `SetKeyboardState`, post the key with `WM_SYSKEYDOWN` when Alt is held, and
restore the state before detaching. Only FL's thread sees the change, so the real keyboard isn't affected. Ctrl+Alt+Y
and Ctrl+R both worked sent to the piano roll, and Ctrl+Alt+Y did nothing sent to the main window.

- Menus are `TQuickPopupMenuWindow` for FL and `#32768` for a VST such as Omnisphere. Both are top-level windows of
  FL's process, so capture them on their own.
- EZdrummer 3 and EZbass draw their menus with JUCE, as `JUCE_...` windows with four 12 pixel shadow windows around
  them. With FL in the background the menu closed before it could be seen, so the kit and bass selectors only worked
  with FL brought to the front first. Windows only lets the process with the last input change the foreground.
  `SetForegroundWindow` after a synthetic Alt press worked about half the time and failed three times in a row with a
  browser in front, and attaching to the input of the foreground window's thread as well made it work. Nothing
  brings FL forward while the session is locked, when the foreground window is the lock screen.
- A capture goes stale when a plugin window closes. A click meant for EZdrummer's kit selector, sent after its
  window was closed, landed on the Playlist and painted a clip. `fl_click` takes `expect` to check the class of the
  window under the point first. The Playlist and the piano roll are both `TEventEditForm`, so it can't tell those
  two apart. The menu stayed open between
  calls while FL kept the front, and a posted click on a row chose it. When the person clicked in another program in
  between, the menu was gone, so the click on the row brings FL to the front again.
- A posted click on the Velocity and Mapping tabs of EZdrummer's `E-Drums/MIDI In` panel did nothing, even with FL in
  front, while its buttons and menus answered.
- Keys skip disabled rows, so counts change with the state of the project. `Run last script again` only enables after
  a first run, for example. In a project that was never saved, `Delete unused files and save project` is disabled too,
  and Export moved one row up. Capture the menu and read the highlighted row before sending enter.
- `right` on a row without a submenu opens the next menu of the menu bar, so keys sent after a wrong count act there.
  Close the menus and open FILE again rather than correcting from where the highlight landed.
- Keep the menus open for as little as possible by sending all the keys from one process.
- Enter and escape can close a menu before the key is released, so don't treat a failed key up as an error.
- A plugin's row menu has a fixed size in the browser, which tells it from the menu of a folder before choosing.
- The bridge kept working while FL was minimized, but nothing can be seen or clicked there. An export through the
  FILE menu still worked once from a minimized FL, which came out of the minimized state during the render.
- Check window order as well as focus when testing this. FL came to the front during an export without taking the
  focus, and a test that only read the foreground window didn't notice.

## Hiding FL while it works

A window of another process can be made invisible and click-through from outside, with `WS_EX_LAYERED` and
`WS_EX_TRANSPARENT` set through `SetWindowLongPtrW` and alpha 0 from `SetLayeredWindowAttributes`. Posted keys and
clicks still reach it, and `PrintWindow` still captures it. With an FL menu hidden like that, clicks in other programs
landed there and the menu stayed open, so it doesn't capture the mouse.

- New windows come from a WinEvent hook on FL's process, `EVENT_OBJECT_CREATE` and `EVENT_OBJECT_SHOW`, out of context.
  The events arrive with the window already visible, 0 to 16 ms later for menus and up to about 150 ms for the save
  dialog. Nobody saw a flash.
- Moving a menu off screen doesn't work, because FL pulls it back to the edge of the monitor.
- Pushing FL down the window order lost. The save dialog raised FL 33 times in 80 ms, and FL stayed above the focused
  window for about 0.25 s anyway, so the main window is hidden during actions too. Whatever part of FL was uncovered
  disappears for that time.
- FL can end the action above the focused window and show up over it once visible again, as it did over a game. Put
  it back below that window before restoring its style. With the dialogs closed by then, that holds.
- Leave everything visible when FL has the focus, since the person is using it.
- Restore the styles in a `finally`. A process that dies inside the shield leaves FL invisible and unclickable, so
  `fl_reveal` drops both bits from every FL window. FL's own windows had neither.
- A menu opened by one call waits for the next, so it stays hidden between calls. FL makes a new window for each menu.
- Kontakt's window and its menus are drawn inside FL's plugin form, a child of the main window, so they never cover
  other programs.
- A "Python message" from a piano roll script showed hidden and closed with a posted click on Ok. Once, after a script
  error, three larger message windows appeared with FL in front and FL closed. That wasn't reproduced.
- A piano roll script's error box, a `TMsgForm` titled `Error`, stayed open outside the main window's capture and made
  every later bridge call fail with `Operation unsafe at current time`. `WM_CLOSE` closed it. `fl_capture` now saves
  such windows as `popup-N`.

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
- `Process.MainWindowHandle` can point at a plugin's popup menu or window, which then reads as FL having moved. Find
  the main window by enumerating the visible top-level windows of FL's process for a title containing `FL Studio`. The
  title is `FL Studio 2026` with no project and `<project>.flp - FL Studio 2026` with one. Stop if nothing matches,
  because offsets computed from an empty rectangle send the clicks somewhere else.
- The export dialog opened at the same screen position after the main window moved, so don't derive its buttons from
  the main window's rectangle.
- Any click on the Playlist grid paints a clip, including a click meant only to give FL focus. Use the empty background
  behind the panels for that. The clip snaps to the nearest grid line, so aim just after the bar line and check where
  it landed.
- An instrument dragged from the browser to the empty area of the Channel Rack gets a new channel, and it feeds the
  Master. To add an effect, select the mixer track first and drag the plugin onto a slot.
- `Send to selected channel or focused plugin`, in the right-click menu of an effect's row in the browser, puts the
  effect on the mixer track of the channel selected in the Channel Rack, not on the track selected in the mixer. With
  a plugin window open and focused, it added nothing to the selected channel's track. Close plugin windows, select the
  channel, send, and read the mixer to confirm where the effect landed.
- Delete on a channel or a mixer slot opens a `Confirm` window with Ok and Cancel. Plugin windows stay open behind the
  panels, and raising the Channel Rack by its header reaches the channels under them.
