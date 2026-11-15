# Proof of concept results

Everything here was run on REAPER 7.86 x64, Windows 11, Kontakt 8.14.1 with Evolution Indie Rock (engine 1.3.0) and
ValhallaVintageVerb, with the scripts in `poc/`. The projects, states and renders live outside the repository, in the
work folder of the song being rebuilt. The real case was bars 5 to 8 of its guitar part.

## Bridge and protocol

- The bridge runs in the open REAPER through `reaper -nonewinst reaper/mps_bridge.lua` (`mps reaper start`), and from
  `Scripts/__startup.lua` in every new instance (`mps reaper install`). In a new REAPER process it answered 8 s after
  the process started.
- Launching the script again replaces the running copy without a dialog, through `set_action_options(1 | 2)`. The copy
  running before that option existed was only ended by the relaunch, and had to be started once more.
- A request held past its expiry was refused with `expired` and didn't run.
- A command longer than the client's timeout (`debug.sleep` of 3 s against 1 s) came back `uncertain`, and its late
  response appeared in `res/` afterwards. Nothing was repeated.
- With two live instances the client refused to guess and asked for `--instance`.
- Unlike FL Studio, deferred scripts kept running while a modal dialog was open, both Kontakt's Instrument Options
  and a message box from another script. The bridge answered with either open.
- An unknown plugin name came back `not_found` with the project unchanged.

## Projects and MIDI

- A project made in a new tab (the tab in use left alone), with tempo and sample rate set, one track and one MIDI
  item, was saved with `Main_SaveProjectEx` and its tabs closed by path afterwards.
- 13 notes with 7 channels, different velocities and lengths, plus a controller, a second controller, a pitch bend
  and a program change, were written and read back with the same channel, pitch, velocity and status bytes. Times
  matched within half a tick after rounding to whole ticks.

## Instrument, strings and legato

- Kontakt was added through the API. Loading Evolution inside it took the Kontakt menu (a real click, since Qt
  ignored a posted click there in REAPER), its Load row (a posted click worked) and the standard file dialog (filled
  without the mouse).
- Channel-Based Strings sits deep in Evolution's SETUP list, which is not a parameter. Dragging the list's scroll bar
  with the real mouse reached it (the wheel didn't scroll it), and its menu offered Disabled, MIDI Guitar, Bottom to
  Top and Top to Bottom. MIDI Guitar was chosen and the whole state saved, so this needs doing once.
- With MIDI Guitar, E4 on channels 1 to 4 sounded on four different strings. Its harmonics fell from -9.6 dB to
  -20.4, -29.7 and -27.9 dB relative to the fundamental, as from the open high string to fretted notes on thicker
  strings, while four repeats on channel 1 stayed within 3.4 dB of each other. So channel 1 is the highest string.
- E2 on channel 1, which the highest string can't play, still sounded.
- Two overlapping notes a tone apart on the same channel played as a hammer-on (the pick band rose 1.1 dB at the
  second note). The same pair on two channels was picked (23.3 dB), like the pair without overlap (25.8 dB). So legato
  stays within a string.

## Plugin state

- Kontakt's state with Evolution was 1.8 MB of base64 and went through the bridge and JSON without trouble.
- Two reads of Kontakt's state in a row gave different bytes of the same length, so its state can't be compared by
  hash. Valhalla's state read the same each time.
- Writing a saved state into the running Kontakt looked like it didn't restore it (a changed parameter stayed changed
  and the parameter text went blank). Deleting the plugin, adding it again and writing the state into the new
  instance did. **Corrected later the same day.** That reading came only from parameter text read right after each
  step, and Kontakt updates its text late. Rendering the two projects that test saved showed the "changed" project
  sample-identical to the original, so the change had never reached the sound and the test couldn't tell anything
  about restoring. Measured by render in `docs/state-checks.md`, writing the state into the running instance
  restored it exactly.
- Restore cycle on the channel test part, each step rendered in a separate process and compared with a render of the
  original state.
  - Restored into a fresh instance, the render was sample-identical.
  - With `Signal` moved from 0 to 100%, it differed (residual -5.3 dB).
  - Restored again into a fresh instance, it was sample-identical again.
- Valhalla's state restored exactly both in place and into a fresh instance, with every parameter's displayed value
  back as saved.
- The parameter text Kontakt reports to the host appeared 1 to 6 s after a restore, but in some fresh instances it
  stayed empty although the instrument had loaded, so waiting on it alone isn't reliable.

## Persistence

- The saved project opened in a new REAPER process reported the same Kontakt parameter value, Valhalla's three
  parameters as saved, and Valhalla's state identical byte for byte to the saved file.
- Every render runs in a new process that loads the saved project, so the sample-identical renders above are also
  persistence results for Kontakt's state.

## Rendering

- `reaper -newinst -nosplash -renderproject` with `MPS_ROLE=render` rendered in a separate process in 5 to 11 s
  without disturbing the open instance, which kept its project and kept answering.
- Format (24-bit WAV), sample rate, channel count, start and end were set explicitly and read back, and
  `RENDER_TARGETS` named the file. Every file was checked for presence, duration, format, channels, signal and being
  newer than the render.
- The render process exited with code 0xC000000D after every render of a Kontakt project, with complete files (the
  cause was isolated later, see `docs/render-standard.md`). The
  exit code was recorded and the file checks decided during the proof of concept. Since then `mps render` reports
  such a render as an abnormal exit and not as a success, until the cause is known.
- Natural variation. 8 of 9 renders of the same project were sample-identical, and one differed on 6 of 15 notes
  (round robin or random sample choice). A difference between two renders only means a change when it exceeds that.
- A project with a missing plugin made the render process show "Project Load Warning". The client found that dialog
  in that process, ended it and reported it within seconds.
- The render progress window is a dialog too. Counting it as an error ended a render early once, and the duration
  check caught the short file. It is now skipped.

## Real case

Bars 5 to 8 of the guitar part (110 notes from the earlier transcription) were rendered twice, with each note on the
channel of the string the fingering model chose and with the instrument choosing strings itself. Both files passed
every check. They differed strongly from each other (correlation 0.27), and a manifest records the inputs and their
hashes, the library files, the plugin and its version, the state hashes, the render settings and the output hashes.
