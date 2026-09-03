"""解说片线的中间物 `_outro.mp4` 不许进 git（review 2026-09-03 §2.2）。"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_片尾母版转码不许进git_清理步骤要删它():
    """`_outro.mp4` 是品牌片尾拼进成片前的中间物，零引用（specs/data/output 里
    一处都没提它），却跟着 `git add "$OUT_DIR"` 进了仓库 12 份。两头钉：仓库里
    一份都不许有；explainer.yml 的清理步骤要在提交之前删掉它（和 voice_*.mp3
    同一处，而不是另起一步——「加新能力就要同时改三处」那条的反面：删也要
    删在同一处）。"""
    tracked = subprocess.run(["git", "ls-files", "output"], capture_output=True,
                             text=True, cwd=ROOT, check=True).stdout.splitlines()
    leaked = [t for t in tracked if t.endswith("_outro.mp4")]
    assert not leaked, f"这些 _outro.mp4 还在 git 里：{leaked}"

    yml = (ROOT / ".github" / "workflows" / "explainer.yml").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in yml.splitlines() if not ln.strip().startswith("#"))
    voice_at = code.index('rm -f "$OUT_DIR"/voice_*.mp3')
    outro_at = code.index('rm -f "$OUT_DIR"/_outro.mp4')
    assert abs(outro_at - voice_at) < 400, "删 _outro.mp4 要和删 voice_*.mp3 在同一步"
    assert outro_at < code.index("git add"), "删中间物要排在 git add 之前"
    assert re.search(r"rm -f \"\$OUT_DIR\"/_outro\.mp4", code)
