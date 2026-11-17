# PRISM (Aurally Sound)

Audio to MIDI transcription. Observed on version 1.2.01 (VST3 with an ARA factory) in REAPER 7.86 on Windows. The
official documentation is at docs.aurallysound.com/prism.

## Using it with ARA in REAPER

- Insert it as a track effect. It analyzed the audio item on the track by itself, with no capture step, as soon as it
  was added.
- Every PRISM window shows one shared ARA document. The `Track:` selector at the top decides which track the window
  edits, analyzes and exports, whatever track the window belongs to. A window opened on one track came up showing
  another. Pick the track in that selector before changing the algorithm or saving.
- The algorithm selector (`Algo:`) offers `general`, `guitar dist` and `grand piano`. Changing it reanalyzes the
  selected track at once, and the choice stays with that track.
- The host sees only five parameters (bypass, wet, delta), so the track, the algorithm, the sensitivity and the export
  can't be reached as parameters.

## Controlling the window

- The window is drawn with JUCE and ignored posted clicks on `SAVE MIDI`. Real clicks worked on the buttons and on
  both selectors.

## Saving the MIDI

- `SAVE MIDI` opens a standard Windows save dialog (`Select file to save midi to`) in Documents, with the track name
  as the file name and the `.midi` extension.
- Setting the text of the edit with control ID 1001 didn't change the name. The file was saved under the default name.
- Typing with real keys was unreliable. A select-all didn't select, and the path landed after the default name.
- What worked was finding the edit that holds the default name, replacing its whole text with `EM_SETSEL` and
  `EM_REPLACESEL`, reading it back, and only then pressing `Save`. Check the name before saving every time.
- The file had 960 ticks per quarter note, the project's tempo and time signature, and note times counted from the
  start of the audio item, not of the project.
