# fl-studio-skills

Skills and helper scripts for producing music in FL Studio with Claude Code. New skills get added as they're needed.

## Skills

- `skills/audio-verification`: check rendered audio with measurements, since the agent can't listen. Covers
  noise, thumps, harshness, levels, chord notes and level-matched A/B comparisons.
- `skills/fl-studio-scripting`: what scripts can and can't do inside FL Studio 2026, as observed on 26.1.4,
  including its file restrictions, callbacks and how to drive the interface safely from outside.

## Scripts

- `bin/wav-check`: measures WAV files for the `audio-verification` skill. Run it with `--help` for the commands.

## Tests

```sh
python3 -m unittest discover -s tests
```

The tests synthesize their WAV files, so no audio or FL Studio is needed. They need `numpy` and are skipped
without it.

## License

MIT, see `LICENSE`.
