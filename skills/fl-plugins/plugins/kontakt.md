# Kontakt 8

Everything here is observed on version 8.14.1. The manual wasn't read for this note.

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

## Controlling it

The Kontakt instance reports through the bridge like any VST, but its parameters weren't listed for this note. Pass
`named_only=False` to `fl_plugin_params` to see the `MIDI CC #` entries FL adds, which are the place to start when an
instrument needs CC1 or CC11. Whether those entries reach an instrument wasn't tested, so render a test before
relying on them.
