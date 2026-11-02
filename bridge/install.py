#!/usr/bin/env python3
"""Copy the bridge scripts into FL Studio's settings folder.

Run it from anywhere, then pick 'Claude Bridge' as the controller type of the
virtual MIDI port in Options > MIDI settings.
"""

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fl_bridge import paths


def main():
    settings = paths.settings_dir()
    if not settings.is_dir():
        sys.exit(f"{settings} doesn't exist. Open FL Studio once so it creates its folders")
    device = paths.device_dir()
    device.mkdir(parents=True, exist_ok=True)
    piano_roll = paths.piano_roll_dir()
    piano_roll.mkdir(parents=True, exist_ok=True)
    for source, folder in (
        (HERE / "fl_scripts" / "device_ClaudeBridge.py", device),
        (HERE / "fl_scripts" / "ClaudeBridge.pyscript", piano_roll),
    ):
        shutil.copy2(source, folder / source.name)
        print(f"installed {folder / source.name}")


if __name__ == "__main__":
    main()
