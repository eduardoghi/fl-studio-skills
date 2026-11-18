# Melodyne 5 Studio (Celemony)

Audio to note detection and pitch editing. Observed on the standalone `Melodyne.exe` of version 5 on Windows, used to
export the detected notes of a separated bass stem as MIDI with no editing.

## Use the standalone for exports

- As a VST3 track effect in REAPER 7.86 the editor stayed empty, with the algorithm menu greyed out, while the audio
  items of the project showed `OFFLINE`. That wasn't solved. The standalone avoids the host entirely.
- The standalone has a native Win32 menu bar, so every menu item can be sent as `WM_COMMAND` with its ID, found with
  `GetMenu`, `GetSubMenu` and `GetMenuItemID`. No mouse is needed for the menus. Some IDs seen on this build:

| Menu item | ID |
| --- | --- |
| File > Import Audio... | 9534 |
| File > Export ... | 9533 |
| Edit > Select All | 9591 |
| Algorithm > Melodic | 9793 |
| Algorithm > Set Default > Melodic | 9801 |
| Track > Delete Track | 9638 |

- Read the IDs again on another build instead of trusting this table. The check marks of a menu are current only
  after sending `WM_INITMENUPOPUP` for it.

## Importing

- A file passed on the command line wasn't open when the window appeared, but it showed up later as a second track
  next to the one imported from the menu. Start the program with no argument.
- `Import Audio...` opens a standard Windows dialog. Put the full path in the edit with control ID 1148 with
  `EM_SETSEL` and `EM_REPLACESEL`, read it back, then press the button with ID 1.
- Set the default algorithm before importing, so the first detection already uses it. The algorithm items stay
  greyed out until something is selected, so select all before choosing one for audio already detected.
- A welcome window covers the editor on the first start and needs a real click on `Close`.

## Exporting MIDI

- `Export ...` opens Melodyne's own small window with the format (MIDI was already selected) and the range. Its
  `Export ...` button took a real click.
- Next comes a `Browse For Folder` dialog with no usable path field. Accepting the default folder (the user profile)
  wrote the files there. Note which files are new by their time and move them.
- It writes two files named after the track. `<track>.mid` holds the notes under one fixed tempo, and
  `<track>.tempo.mid` holds the detected tempo map with no notes. Convert the note ticks with the map from the second
  file, not with the tempo inside the first.

## What the Melodic algorithm gave on a bass

- It joined repeated notes of the same pitch into one long note. Of the 235 repeated attacks found in the stem by an
  envelope-based segmenter, it kept 86, so its note count came out at about half.
- The notes it did start were almost all real attacks (95 % within 50 ms of an attack from the audio), and their
  pitches agreed with three pitch trackers on 121 of 126.
