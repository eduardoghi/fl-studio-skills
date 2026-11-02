"""Checks that every skill can be found by Claude Code and by readers of the README.

Run with `python3 -m unittest discover -s tests`.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = sorted(path for path in (ROOT / "skills").iterdir() if path.is_dir())


def frontmatter(path):
    match = re.match(r"---\n(.*?)\n---\n", path.read_text(encoding="utf-8").replace("\r\n", "\n"), re.DOTALL)
    if match is None:
        return {}
    return dict(line.split(": ", 1) for line in match.group(1).splitlines())


class Skills(unittest.TestCase):
    def test_there_are_skills(self):
        self.assertTrue(SKILLS)

    def test_name_matches_the_folder(self):
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                self.assertEqual(frontmatter(skill / "SKILL.md").get("name"), skill.name)

    def test_description_says_when_to_use_it(self):
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                self.assertIn("Use ", frontmatter(skill / "SKILL.md").get("description", ""))

    def test_every_plugin_note_is_in_the_index(self):
        index = (ROOT / "skills" / "fl-plugins" / "SKILL.md").read_text(encoding="utf-8")
        for note in (ROOT / "skills" / "fl-plugins" / "plugins").glob("*.md"):
            with self.subTest(note=note.name):
                self.assertIn(f"`plugins/{note.name}`", index)

    def test_readme_lists_every_skill(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                self.assertIn(f"`skills/{skill.name}`", readme)


if __name__ == "__main__":
    unittest.main()
