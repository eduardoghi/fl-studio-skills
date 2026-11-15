# Plugin state checks

How a saved plugin state is checked after a restore, and what was measured. The three levels and what each proves
are described in `src/mps/state.py`. Measured on REAPER 7.86 x64 and Windows 11 on 2026-11-15, with Kontakt 8.14.1
and Evolution Indie Rock, on a part of six notes over 8 s rendered as 32-bit float in separate processes.

## Tools

- `mps state save --track <guid> --fx <index or guid> <folder>` waits for the plugin to settle, stores the state as
  `<sha256>.b64` and records the plugin, its binary version and the text of every exposed parameter in
  `<sha256>.json`.
- `mps state restore --track <guid> --fx <index or guid> <file.b64>` checks the file's hash, writes the state back,
  waits for the plugin to settle and compares every parameter's text with the record. With `--fresh <name>` it uses
  the bridge's `fx.restore_fresh`, which adds a new instance after the old one, refuses if it isn't the same binary,
  writes the state into it and only then deletes the old one.
- `mps wav variation --reference <renders of the unchanged project> --candidate <renders to judge>` compares each
  candidate with the variation between the references (`identical`, `within`, `outside`).

## Settling

A plugin counts as settled when two reads of its parameter list one second apart give the same text. Kontakt left the
text empty in some fresh instances during the proof of concept, so after 10 s an unchanged state length also counts,
with the text reported as unavailable and level 2 left unjudged. In these tests Kontakt settled in 1.1 to 1.2 s after
each restore, with its text available.

## Kontakt results

| Test | Level 2 | Level 3 |
|---|---|---|
| State saved, then restored into a fresh instance | 4148 parameters, same text | |
| `Signal` changed from 0 to 100 % | the comparison reported `Signal` 0 % to 100 % | outside (residual -4.7 dB against the originals) |
| Then restored into a fresh instance | same text | identical to the originals |
| Changed, then restored into the running instance after settling | same text | identical to the originals |
| Changed, then restored into the running instance and saved at once | | identical to the originals |
| A different state (default settings instead of strings by channel) written into the running instance | | identical to two renders of a fresh restore of that state, which differ from the first state (residual +2.5 dB) |

The three renders of the original state were sample-identical to each other, so "identical" here means no sample
differed. Every Kontakt render ended with exit code 0xC000000D and complete files.

So with this plugin, library and host, writing a state into the running instance restored it exactly, in the two
cases tested. The fresh instance is still the default in this repository's procedures, because it was measured the
same way and doesn't depend on what the running instance held before. Other Kontakt libraries and other plugins
weren't tested and aren't assumed to behave the same.

## The proof of concept's in-place test

The proof of concept concluded that writing a state into the running Kontakt didn't restore it, from parameter text
read right after each step. Rendered later, the two projects it saved were sample-identical to the nine renders of
the original state made that day, including the project meant to hold the change. The change had never reached the
sound, so that test said nothing about restoring, and its conclusion was withdrawn.
