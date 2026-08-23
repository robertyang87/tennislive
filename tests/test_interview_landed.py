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


def test_ffprobe的csv输出带尾随逗号也解析得出来():
    """2026-08-20 撞的：`pegula-cirstea-cincinnati-2026-r16` 那趟 render 在
    最后一步（`check_interview_landed.check_film`）崩掉——`ffprobe`
    对 `-of csv=p=0` 吐出 `291.880000,`（带一个尾随空字段），裸的
    `float()` 直接 `ValueError`（run 32319565674）。

    `check_reel_landed.py` 早为同一个坑加过 `_ffprobe_float()`（见
    `test_match_reel.py::test_ffprobe的csv输出带尾随逗号也解析得出来`），
    这个文件是姊妹工具，当时没跟着改。补上同名同形状的辅助函数。
    """
    ci = _tool()

    # ① 正常的干净输出
    assert ci._ffprobe_float("291.880000\n") == pytest.approx(291.88)
    # ② 当天真炸的那个字符串——多一个尾随逗号（空字段）
    assert ci._ffprobe_float("291.880000,\n") == pytest.approx(291.88)
    # ③ 反向验证：换回没有这层保护的写法，②这个真实样本会崩
    with pytest.raises(ValueError):
        float("291.880000,\n".strip())


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


def test_bilingual_body只认正文同时间码双语不认顶栏(tmp_path):
    ci = _tool()
    ass = tmp_path / "x.ass"
    ass.write_text(
        "Dialogue: 0,0:00:00.00,0:00:10.00,HEADA,,0,0,0,,栏目顶栏\n"
        "Dialogue: 0,0:00:01.00,0:00:03.00,EN,,0,0,0,,Question\n"
        "Dialogue: 0,0:00:01.00,0:00:03.00,ZH,,0,0,0,,问题\n",
        encoding="utf-8")
    ok, detail = ci.bilingual_body_ok(ass, {"zh": ["问题"]})
    assert ok, detail

    ass.write_text(
        "Dialogue: 0,0:00:00.00,0:00:10.00,HEADA,,0,0,0,,栏目顶栏\n",
        encoding="utf-8")
    ok, _ = ci.bilingual_body_ok(ass, {"zh": ["问题"]})
    assert not ok, "顶栏有字不能冒充正文中英字幕"


def test_冷开场原解说也必须逐cue中英成对(tmp_path):
    ci = _tool()
    ass = tmp_path / "_lead.ass"
    ass.write_text(
        "Dialogue: 0,0:00:01.00,0:00:03.00,EN,,0,0,0,,Match point\n"
        "Dialogue: 0,0:00:01.00,0:00:03.00,ZH,,0,0,0,,赛点\n",
        encoding="utf-8")
    spec = {"lead_in": {"subs": [{"en": "Match point", "zh": "赛点"}]}}
    assert ci.bilingual_lead_ok(ass, spec)[0]

    ass.write_text(
        "Dialogue: 0,0:00:01.00,0:00:03.00,EN,,0,0,0,,Match point\n",
        encoding="utf-8")
    assert not ci.bilingual_lead_ok(ass, spec)[0], "只有英文不能通过冷开场双语质检"
