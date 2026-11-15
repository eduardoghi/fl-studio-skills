# music-production-skills

Skills, tools and notes for producing, rebuilding and checking music with Claude Code. REAPER is the DAW, driven
through a small bridge and a command line. The FL Studio tools this project started with are kept in `fl-studio/`
for older projects.

This repository was called `fl-studio-skills`. If you installed the plugin under that name, see
[docs/migration.md](docs/migration.md).

## Install the skills

Inside Claude Code, on version 2.1.275 or later:

```text
/plugin install music-production-skills --marketplace eduardoghi/music-production-skills
```

On older versions, add the marketplace first:

```text
/plugin marketplace add eduardoghi/music-production-skills
/plugin install music-production-skills@music-production-skills
```

That installs for your user. For one project, run this in a terminal after adding the marketplace:

```sh
claude plugin install music-production-skills@music-production-skills --scope project
```

The skills show up as `music-production-skills:reaper` and so on. To try a clone without installing it, run
`claude --plugin-dir /path/to/music-production-skills`.

The plugin only brings the skills. The REAPER bridge and the `mps` command line run from a clone, as the `reaper`
skill explains, and the FL Studio bridge has its own setup in `fl-studio/bridge/README.md`.

## Skills

- `skills/reaper`: drive REAPER through the mps bridge and command line, from building a project to a checked render.
- `skills/audio-verification`: check rendered audio with measurements, since the agent can't listen. Covers
  noise, thumps, harshness, levels, chord notes, level-matched A/B comparisons and a continuity audit of the
  transitions between sections.
- `skills/plugins`: notes per plugin on what the controls do, defaults that cause trouble, how their state restores,
  and parameter names, each marked with the host it was measured in.
- `skills/music-composition`: develop a musical idea through intentional changes, compared by listening instead of
  by adding layers, and compose the relationships between instrumental parts instead of independent patterns.
- `skills/fl-studio-scripting`: what scripts can and can't do inside FL Studio 2026, as observed on 26.1.4,
  including its file restrictions, callbacks and how to drive the interface from outside, with or without focus.

## Layout

- `reaper/mps_bridge.lua` runs inside REAPER and answers typed commands through request files. It never runs Lua code
  sent in a request.
- `src/mps/` is the Python library and the `mps` command line.
  - `reaper.py` sends commands and reports each outcome as `ok`, `error`, `expired`, `not_started` or `uncertain`.
  - `render.py` renders a saved project in a separate REAPER process.
  - `audio.py` checks rendered files and compares renders.
  - `windows.py` finds and answers dialogs, captures windows and clicks, for plugin interfaces with no API.
  - `manifest.py` collects hashes and plugin versions for experiment records.
- `bin/` holds scripts that work on audio files from any DAW.
  - `wav-check` measures WAV files for the `audio-verification` skill. Run it with `--help` for the commands.
  - `instrument-calibrate` turns renders of isolated hits into a curve of attack level per note and velocity, which
    converts relative levels heard in a reference into velocities, checks the curves on notes left out of them, and
    compares a part's render with the same part in a reference against the times of its notes. See
    `audio-verification`.
- `fl-studio/` holds the FL Studio tools, kept working and tested but no longer extended.
  - `bridge/` is `fl-bridge`, an MCP server that controls the project open in FL Studio. See its README.
  - `bin/fl-notes` reads and writes the notes of many channels through that bridge, checking each write by reading it
    back.
- `poc/` holds the proof of concept scripts for REAPER, kept as the evidence for `docs/poc-results.md`.
- `docs/` holds the investigation behind the move to REAPER, the proof of concept results, the render standard and the
  migration notes.

Windows runs a script by its extension and ignores the `#!` line, so each script in `bin/` has a `.cmd` next to it
that runs it with `python`. Put `bin\` on `PATH` to run them by name.

## The mps command line

```sh
uv sync
uv run mps reaper install          # start the bridge with every REAPER instance
uv run mps reaper start            # start it in the REAPER already open
uv run mps reaper call ping
uv run mps reaper call project.info
uv run mps render project.rpp --expect out.wav --seconds 12.48 --samplerate 44100 --channels 2 --subtype FLOAT
uv run mps wav compare a.wav b.wav
```

Every command prints JSON. Exit codes are 0 done, 1 failed, 2 bad usage, 3 not started, 4 uncertain (don't repeat
it blindly) and 5 expired. The `reaper` skill lists the bridge's commands.

### How the bridge stays safe

Each REAPER instance has its own folder with an id and a heartbeat. The client publishes a request by renaming it
into `req/` under a new name, the bridge claims it by renaming it into `work/`, and publishes the response the same
way, so no side ever reads half a file and a request can't run twice. If the client gives up while the request is
still in `req/`, it renames it away, and the command can then never run. If the request was claimed, the outcome is
uncertain and the client says so instead of retrying. Requests carry an expiry, so one left by a client that died is
refused rather than run late. Instances started to render get `MPS_ROLE=render` and don't start the bridge.

## Tests

```sh
pip install -r requirements-dev.txt
python -m pytest
ruff format --check bin/wav-check bin/instrument-calibrate src poc tests fl-studio/bin/fl-notes fl-studio/bridge fl-studio/tests
ruff check bin/wav-check bin/instrument-calibrate src poc tests fl-studio/bin/fl-notes fl-studio/bridge fl-studio/tests
```

The tests synthesize their WAV files, run the REAPER client against a fake bridge and fake FL Studio's modules, so no
audio, REAPER or FL Studio is needed. That only covers the logic, so a change to either bridge also needs a run
against the real program.

## License

MIT, see `LICENSE`.
