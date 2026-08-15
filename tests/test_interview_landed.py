"""tools/check_interview_landed.py —— 采访片 L2 成片落地闸。

只测**不联网/不碰成片**的半截：ass_has_dialogue、check_offline 的记分。
check_film 要 ffprobe + 成片，交给真实环境（和 check_reel_landed 同理由）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


def _tool():
    sys.path.insert(0, str(Path("tools").resolve()))
    import check_interview_landed as ci  # noqa: PLC0415

    return ci


def test_ass_has_dialogue认得Dialogue行(tmp_path):
    ci = _tool()
    ass = tmp_path / "x.ass"
    ass.write_text("[Events]\nDialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,你好\n",
                   encoding="utf-8")
    assert ci.ass_has_dialogue(ass) is True
    ass.write_text("[Script Info]\nTitle: x\n", encoding="utf-8")
    assert ci.ass_has_dialogue(ass) is False
    assert ci.ass_has_dialogue(tmp_path / "不存在.ass") is False


def test_check_offline全绿返回0(tmp_path, capsys):
    ci = _tool()
    spec = {"slug": "demo", "zh": ["你好"]}
    (tmp_path / "render.json").write_text(
        json.dumps({"video_url": "https://x/demo.mp4", "video_bytes": 12345}),
        encoding="utf-8")
    (tmp_path / "demo.ass").write_text("Dialogue: 0,0:00:00,0:00:01,,x\n",
                                       encoding="utf-8")
    bad = ci.check_offline(spec, tmp_path)
    assert bad == 0
    out = capsys.readouterr().out
    assert "成片在 Release 上" in out and "字幕 有 Dialogue" in out


def test_check_offline缺啥记啥(tmp_path, capsys):
    """每缺一样计 1 项不合格，且要出声——「没判」和「判了没问题」分得开。"""
    ci = _tool()
    spec = {"slug": "demo", "zh": []}
    bad = ci.check_offline(spec, tmp_path)  # 空目录：ass 无 + zh 空 = 2（render.json 无是"跳过"）
    assert bad == 2, f"ass 无 + zh 空应记 2，实际 {bad}"
    out = capsys.readouterr().out
    assert "不合格" in out
