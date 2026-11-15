# Moving from fl-studio-skills

This repository was called `fl-studio-skills`, and its Claude Code plugin and marketplace had the same name. Both are
now `music-production-skills`. GitHub redirects the old repository address, but the plugin's new name means an
installed copy doesn't update to it by itself.

## The plugin

Remove the old marketplace, which also uninstalls the old plugin from every scope:

```sh
claude plugin marketplace remove fl-studio-skills
```

Then install the new one, inside Claude Code on version 2.1.275 or later:

```text
/plugin install music-production-skills --marketplace eduardoghi/music-production-skills
```

On older versions, or for one project, follow the install section of the [README](../README.md). If the old plugin
was installed with `--scope project`, the project's `.claude/settings.json` declared it, so install the new one there
the same way and commit that change.

## Skill names

The skills now show up as `music-production-skills:<skill>`. One skill was renamed:

| Before | Now |
|---|---|
| `fl-studio-skills:fl-plugins` | `music-production-skills:plugins` |
| `fl-studio-skills:audio-verification` | `music-production-skills:audio-verification` |
| `fl-studio-skills:music-composition` | `music-production-skills:music-composition` |
| `fl-studio-skills:fl-studio-scripting` | `music-production-skills:fl-studio-scripting` |

Instructions or prompts that name a skill by its old name need the new one. The plugin notes now say in which host
each behavior was measured, since some of them now come from REAPER.

## Files that moved

| Before | Now |
|---|---|
| `bridge/` | `fl-studio/bridge/` |
| `bin/fl-notes`, `bin/fl-notes.cmd` | `fl-studio/bin/fl-notes`, `fl-studio/bin/fl-notes.cmd` |
| `tests/test_bridge.py` | `fl-studio/tests/test_bridge.py` |

`bin/wav-check` and `bin/instrument-calibrate` stayed where they were.

## In a clone

Point the clone at the new address, although the old one still redirects:

```sh
git remote set-url origin https://github.com/eduardoghi/music-production-skills.git
```

If Claude Code runs `fl-bridge` from the clone, its MCP entry names the old folder. Change the `--directory` part of
the command to the new one:

```text
uv run --directory /path/to/music-production-skills/fl-studio/bridge fl-bridge
```

Of the FL Studio scripts that `fl-studio/bridge/install.py` copies, only the repository address in the header of
`device_ClaudeBridge.py` changed, so installing them again is optional.
