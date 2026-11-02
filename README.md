# fl-studio-skills

Skills and helper scripts for producing music in FL Studio with Claude Code. New skills get added as they're needed.

## Skills

- `skills/audio-verification`: check rendered audio with measurements, since the agent can't listen. Covers
  noise, thumps, harshness, levels, chord notes and level-matched A/B comparisons.
- `skills/fl-studio-scripting`: what scripts can and can't do inside FL Studio 2026, as observed on 26.1.4,
  including its file restrictions, callbacks and how to drive the interface safely from outside.

- `skills/fl-plugins`: notes per plugin on what the controls do, defaults that cause trouble and parameter names.

## Scripts

- `bin/wav-check`: measures WAV files for the `audio-verification` skill. Run it with `--help` for the commands.
- `bridge/`: `fl-bridge`, an MCP server that controls the project open in FL Studio. See `bridge/README.md`.

## Tests

```sh
pip install -r requirements-dev.txt
python3 -m unittest discover -s tests
ruff format --check bin/wav-check tests bridge
ruff check bin/wav-check tests bridge
```

The tests synthesize their WAV files and fake FL Studio's modules, so no audio or FL Studio is needed. That only
covers the logic, so a change to the bridge also needs a run against the real program. The `wav-check` tests
need `numpy` and are skipped without it.

## License

MIT, see `LICENSE`.
