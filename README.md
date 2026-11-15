# music-production-skills

Tools and notes for producing, rebuilding and checking music with an agent, with REAPER as the DAW. It follows
[fl-studio-skills](https://github.com/eduardoghi/fl-studio-skills), which stays as it is.

This is a proof of concept. The REAPER bridge, renders in a separate process and file checks work, and the results are
in [docs/poc-results.md](docs/poc-results.md). The investigation behind the choice of REAPER is in
[docs/reaper-investigation.md](docs/reaper-investigation.md).

## Layout

- `reaper/mps_bridge.lua` runs inside REAPER and answers typed commands through request files. It never runs Lua
  code sent in a request.
- `src/mps/` is the Python library and the `mps` command line.
  - `reaper.py` sends commands and reports each outcome as `ok`, `error`, `expired`, `not_started` or `uncertain`.
  - `render.py` renders a saved project in a separate REAPER process.
  - `audio.py` checks rendered files and compares renders.
  - `windows.py` finds and answers dialogs, captures windows and clicks, for plugin interfaces with no API.
  - `manifest.py` collects hashes and plugin versions for experiment records.
- `poc/` holds the proof of concept scripts, kept as the evidence for the results.

## Use

```sh
uv sync
uv run mps reaper install          # start the bridge with every REAPER instance
uv run mps reaper start            # start it in the REAPER already open
uv run mps reaper call ping
uv run mps reaper call project.info
uv run mps render project.rpp --expect out.wav --seconds 12.48 --samplerate 44100 --channels 2 --subtype PCM_24
uv run mps wav compare a.wav b.wav
```

Every command prints JSON. Exit codes are 0 done, 1 failed, 2 bad usage, 3 not started, 4 uncertain (don't repeat
it blindly) and 5 expired.

## How the bridge stays safe

Each REAPER instance has its own folder with an id and a heartbeat. The client publishes a request by renaming it
into `req/` under a new name, the bridge claims it by renaming it into `work/`, and publishes the response the same
way, so no side ever reads half a file and a request can't run twice. If the client gives up while the request is
still in `req/`, it renames it away, and the command can then never run. If the request was claimed, the outcome is
uncertain and the client says so instead of retrying. Requests carry an expiry, so one left by a client that died is
refused rather than run late. Instances started to render get `MPS_ROLE=render` and don't start the bridge.
