# Kontakt 8

Everything here is observed on version 8.14.1. The manual wasn't read for this note. The sections up to Controlling
it were observed in FL Studio 26.1.x, and the REAPER section in REAPER 7.86 (details in `docs/poc-results.md`).

## Finding a library

A new instance opens on a browser overlay. Its Instruments page listed only the factory content, and the Libraries
tab belongs to Classic View, under the KONTAKT menu.

The overlay stays on top after switching, so the screen looks unchanged. Close it with its x before deciding that the
switch failed. Check the menu too, since `Switch to Default View` in its place means the switch worked.

The menu has different items in each view, so the same position means something else after switching. A click meant
for `Switch to Classic View`, repeated at the same spot in Classic View, opened the submenu of `Purge all instances`.
Capture the open menu before each click.

## Loading an instrument

KONTAKT menu > Load opens a file dialog that accepts a full path to a `.nki`. A library that isn't registered still
loads this way, but the instrument shows `DEMO` beside its name, and the Libraries tab stays empty. Registering a
commercial library takes its serial in Native Access. Check for `DEMO` before building on an instrument, because a
render from it wasn't tested.

Spitfire libraries show a help bubble on first load. It covers the controls, and a click dismisses it.

The same dialog accepts a snapshot (`.nksn`, in the library's `Snapshots` folder). Loaded this way it replaced the
settings of the instrument already in the rack, without adding a second one, and the header showed its name. The
KONTAKT menu and its Load row answered posted clicks, and the dialog is a standard Windows one, so a snapshot loads
without real mouse input, by setting the path in its file name field and clicking its Open button.

## Controlling it

An instrument's own controls appear as parameters in the order of its panels, without the panel name, so names like
`On/Off` repeat and the position tells them apart. Kontakt reports every value as 0.0 and updates the text a moment
after a set, so read the text again after about 150 ms (`plugins/evolution.md` has a measured case).

Kontakt draws its window with Qt. Its menus and some buttons answered posted clicks, but the snapshot arrows of an
instrument header didn't, even with the pointer moved over them first. Load snapshots by file instead.

The Kontakt instance reports through the bridge like any VST. Pass
`named_only=False` to `fl_plugin_params` to see the `MIDI CC #` entries FL adds, which are the place to start when an
instrument needs CC1 or CC11. Whether those entries reach an instrument wasn't tested, so render a test before
relying on them.

## In REAPER

Observed in REAPER 7.86, with Evolution Indie Rock loaded:

- The KONTAKT menu ignored a posted click there, unlike in FL, and opened with a real click. Its Load row then took a
  posted click, and the file dialog took the `.nki` path without the mouse, as in FL.
- On a later day the real click opened the menu only after the pointer had moved over the header for a moment.
  Posted mouse moves before a posted click, sent messages with activation and a posted press alone still didn't open
  it. UI Automation lists the header button as `Kontakt File Menu` with an Invoke pattern, but invoking it didn't lead
  to a Load dialog.
- Real input needs an unlocked Windows session. While it was locked there was no input desktop, and a screen capture
  returned the lock screen. Wait for the person to be idle for a few seconds before each real click, since they may
  be using the mouse, and check that the pointer landed where it should.
- A saved state (`vst_chunk`) restored exactly, by render, both written into a new instance (`mps state restore
  --fresh`) and written into the running one, including a different state of the same library. That was Evolution
  Indie Rock, and other libraries weren't tested. The fresh instance stays the default. An earlier note said the
  running instance ignored the state, but that came from parameter text read too early and was withdrawn
  (`docs/state-checks.md`).
- Kontakt updates a parameter's text about a second after a set or a restore, so the text an answer carries is the
  old one. Read the list again until it stops changing before comparing.
- Two reads of the state in a row gave different bytes of the same length, so a hash only proves that a stored file
  didn't change. Compare Kontakt states by render.
- The state with Evolution was about 1.8 MB of base64.
- The parameter text appeared 1 to 6 s after a restore, but in some fresh instances it stayed empty although the
  instrument had loaded. Don't wait on the text alone. Accept a stable text, or a state whose length stayed the same
  after about 10 s.
- A REAPER process that quit right after rendering with Kontakt loaded, even with no instrument in it, ended with
  code 0xC000000D, although the files were complete. Waiting 3 s before quitting avoided it, which `mps render` does.
  Other instruments and effects tested didn't cause it (`docs/render-standard.md`).
