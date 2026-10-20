"""解说转写跟 probe 并行，不塞进 probe（2026-10-12 等了 10 分钟手搓的那一趟）。"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import source_asr  # noqa: E402


def _steps(name: str) -> list[dict]:
    wf = yaml.safe_load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))
    return [s for job in wf["jobs"].values() for s in job.get("steps") or []]


def test_probe用上存档就并行派发转写_不在probe里跑模型():
    steps = _steps("match-reel.yml")
    names = [s.get("name", "") for s in steps]
    at = names.index("probe — 并行派发解说转写")
    assert names.index("probe — 有 Release 存档就用存档") < at < names.index("probe — 下载 + 缩略图墙")
    step = steps[at]
    assert step.get("continue-on-error") is True, "派不出去不许让 probe 红"
    assert "gh workflow run source-asr.yml" in step["run"]
    assert "data/source_asr/$KEY/medium.en.json" in step["run"], "已有转写不重跑"
    # 配音自动听审（2026-10-20）在 render 里转写的是**我们自己的配音**，不是源片解说，
    # 那一步单独认领；源片转写仍然不许回到 match-reel 里。
    body = "\n".join(s.get("run") or "" for s in steps
                     if "voice_auto_review.py" not in (s.get("run") or ""))
    assert "faster-whisper" not in body and "source_asr.py" not in body


def test_转写工作流两档都跑_按视频id落库():
    run = "\n".join(s.get("run") or "" for s in _steps("source-asr.yml"))
    assert "small.en medium.en" in run
    assert 'OUT="data/source_asr/$KEY"' in run
    assert "push_with_rebase_retry" in run


def test_截区间转写的时间码加回源片绝对秒():
    seg = [{"start": 1.0, "end": 2.0, "text": "x", "words": [{"w": "x", "s": 1.1, "e": 1.9}]}]
    got = source_asr.shift(seg, 100.0)
    assert (got[0]["start"], got[0]["end"]) == (101.0, 102.0)
    assert (got[0]["words"][0]["s"], got[0]["words"][0]["e"]) == (101.1, 101.9)
