# Transition continuity audit

Read this when a passage between sections sounds broken, or before the final export of a piece with several
sections.

When a passage between sections sounds broken, read the notes of every channel on both sides of the boundary
(`midi.read` through the `reaper` skill, `fl-notes read` in FL, or the score a generator wrote) before touching anything. Run a light pass over the main
boundaries before the final export of a piece with several sections too, when the notes and the section boundaries
are available. It doesn't need repeating after every small edit. Check four things in a window of a bar or two around
each boundary:

1. Gaps. A part ends before the part that takes over starts, or one line stops and resumes with a hole in between.
2. Stray notes. Short notes left at the start of a section by a range that ran one chord too far.
3. Rearticulations. The same pitch ends and starts again on one channel, which a legato instrument plays as a new
   attack. Overlapping notes of different pitches are a legato transition, not a new attack.
4. Abrupt controls. A large step between two consecutive CC1 or CC11 values, a CC64 release that cuts notes the pedal
   was holding, or note-offs on several channels at the same barline. A controller holds its value until the next
   event, so judge the size of each step, not the time between events. A ramp drawn in small steps isn't a jump, and
   a step while the channel is silent only prepares its next entry.

Compare sounding times, not written ones. Add the attack and legato delays measured for each instrument, and treat a
note under a held sustain pedal as lasting until the pedal lifts. In Cinematic Studio Strings the previous note kept
sounding through a legato transition until the new one was heard, so there the transition delay wasn't a gap. Check
that in a render before assuming it for another library. Say which delays and releases weren't measured, because a
long release can fill a gap that the notes show. To confirm that a gap is audible, render the stems and run
`timeline` with a short `--step` on each.

Report each finding with the channel, bar and beat, the events involved and why it looks suspicious. Don't fix
anything from the audit alone. A silence, a new bow stroke or a sudden contrast can be what the composer wanted, so
each finding is a question for the person who wrote it. Controls that a project draws as automation clips aren't in
the notes, so say when they couldn't be checked.
