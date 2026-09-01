#!/usr/bin/env python3
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = (
    "tools/draft_interview_spec.py",
    "tools/attach_interview_lead_in.py",
    "tools/build_interview_clip.py",
    "tools/detect_highlights.py",
)


def ytdlp_commands(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.List) or not node.elts:
            continue
        first = node.elts[0]
        if not isinstance(first, ast.Constant) or first.value != "yt-dlp":
            continue
        yield [
            item.value
            for item in node.elts
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        ]


class InterviewYtdlpEjsTest(unittest.TestCase):
    def test_every_interview_ytdlp_command_has_node_and_ejs(self):
        total = 0
        for relative in TARGETS:
            commands = list(ytdlp_commands(ROOT / relative))
            self.assertTrue(commands, relative)
            for values in commands:
                total += 1
                self.assertIn("--js-runtimes", values, relative)
                self.assertEqual(
                    values[values.index("--js-runtimes") + 1], "node", relative
                )
                self.assertIn("--remote-components", values, relative)
                self.assertEqual(
                    values[values.index("--remote-components") + 1],
                    "ejs:github",
                    relative,
                )
        self.assertGreaterEqual(total, 6)


if __name__ == "__main__":
    unittest.main()
