"""tools/draft_interview_spec.py —— 自动建「赛后开麦」spec 草稿（纯函数，不联网）。

转写/翻译要 faster-whisper + DeepSeek（Actions 里跑），这里只测不联网的
拼接逻辑：受访者从名册认、slug 生成、草稿结构、cap_asr.json3 的形状、
翻译行数闸、同 slug 不许静默覆盖。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


@pytest.fixture()
def tool(monkeypatch):
    sys.path.insert(0, str(_TOOLS))
    import draft_interview_spec as d  # noqa: PLC0415

    return d


def _cal():
    return [{"en": "Cincinnati Open", "zh": "辛辛那提大师赛", "start": "08-16",
             "end": "08-23", "pat": "cincinnati"}]


def test_event_year_round从标题解析(tool):
    ev, year, rnd = tool._event_year_round(
        "Cincinnati 2026 R3 Alexander Zverev Interview", _cal())
    assert (ev, year, rnd) == ("cincinnati", "2026", "r3")
    ev, year, rnd = tool._event_year_round(
        "On-Court Interview | Quarterfinal | Rome 2026", [])
    assert rnd == "qf", "四分之一决赛 → qf"


def test_interviewee_en从名册认人不按位置猜(tool):
    """**旧版取「最后一个大写词」在真实标题上几乎全错**——受访者常在标题开头，
    尾巴是赛事名。判据拿 `data/oncourt_interviews.json` 里的真实标题形状：
    受访者在头、在尾、在冒号后都要认得出，认的是**名册里的全名**。"""
    # 受访者在开头，尾巴是赛事名（旧版取出来是 Hopman/Mastercard 一类）
    assert tool.interviewee_en(
        "Karen Khachanov on-court interview (RR) | Mastercard Hopman Cup 2018"
    ) == "Karen Khachanov"
    # 受访者在中间（冒号后）
    assert tool.interviewee_en(
        "On-Court Interview: Jasmine Paolini feels 'elated' with her win"
    ) == "Jasmine Paolini"
    # 受访者在结尾
    assert tool.interviewee_en(
        "Cincinnati 2026 R3 Alexander Zverev Interview") == "Alexander Zverev"
    # 双人标题取位置靠前的那个
    assert tool.interviewee_en(
        "Djokovic and Kyrgios' BROMANCE BLOSSOMS in on-court interview"
    ).endswith("Djokovic")
    # 名册里没有的名字：返回空串，不许瞎猜
    assert tool.interviewee_en("Some Nobody Qualifier Interview 2026") == ""


def test_build_spec草稿结构(tool):
    c = {"title": "Cincinnati 2026 R3 Alexander Zverev Interview",
         "url": "https://t.co/x", "event_zh": "辛辛那提大师赛", "id": "VID1"}
    spec = tool.build_spec(c, ["萨沙 恭喜你", "这场打得很过瘾"], 53.7, _cal())
    assert spec["_draft"] is True
    assert spec["slug"] == "zverev-cincinnati-2026-r3"
    assert spec["start"] == 0.0 and spec["end"] == 53.7
    assert spec["asr_model"] == "small.en"
    assert spec["whisper_model"] == "medium.en"
    assert spec["column"] == "赛后开麦"
    assert spec["_interviewee_en"] == "Alexander Zverev", \
        "promote 按它查赛果，不能再让 promote 从标题猜第二遍"
    # _build_one 已先用正式 segment() 切行再翻译，机器译文与 render 行号同源，
    # 不再人为留空制造必经人工接力。
    assert spec["zh"] == ["萨沙 恭喜你", "这场打得很过瘾"]
    assert spec["_zh_draft"] == ["萨沙 恭喜你", "这场打得很过瘾"]
    assert spec["transcript_verified"] is False, "双模型核对由 render 的 verify_transcript 完成"
    assert spec["transcript_verification"] == "auto_pending"
    assert spec["requested_content_type"] == "on_court"
    assert spec["interview_kind"] == "赛后场上采访"
    assert spec["_candidate_id"] == "VID1"


def test_build_spec认不出受访者要报错不许瞎猜(tool):
    c = {"title": "Some Nobody Qualifier Interview 2026", "url": "x"}
    with pytest.raises(ValueError, match="认不出受访者"):
        tool.build_spec(c, ["a"], 10.0, _cal())


def test_cap_json3是fetch_words认的形状(tool):
    """`fetch_words` 报错正文写的约定：`events[].tStartMs` + `segs[].utf8`。
    `dDurationMs` 也要给——`_caption_spans` 按它算空档，全 0 的话 whisper
    分段之间的每个间隙都会被误报成空档，render 那道闸淹在假红里。"""
    rows = [{"t": 1.42, "end": 3.9, "text": "Well, thank you."},
            {"t": 4.0, "end": 4.5, "text": "It was tough."}]
    data = tool.cap_json3(rows)
    evs = data["events"]
    assert evs[0]["tStartMs"] == 1420
    assert evs[0]["dDurationMs"] == 2480
    assert evs[0]["segs"] == [{"utf8": "Well, thank you."}]
    assert evs[1]["tStartMs"] == 4000 and evs[1]["dDurationMs"] == 500
    # whisper 不分说话人，不许编 `>> ` 标记（假边界比没有更糟）
    assert not any(">>" in s["utf8"] for e in evs for s in e["segs"])


def test_批量行数对不上不许按位置硬贴(tool):
    """模型合并两句不报错，而错位的译文从那一条起**每一行都挂在别人的英文上**
    ——比缺译文糟得多。

    ⚠️ **2026-08-29 这条换过一次主语，不是放松。** 它原来叫
    `test_翻译行数对不上要当场报错`，钉的是「批量条数对不上就当场
    `RuntimeError` 整批作废」；`_translate_batch` 后来改成**二分到每一行都有
    独立响应**，那个异常不再抛，判据当场变成一条常年红——`主语没了就得换判据`。
    换的是机制，**不变量一个字没动：绝不按位置硬贴**。

    所以这条按内容验，不按条数验：批量一律少回一条，逼它一路二分到单行，
    每一句英文最后拿到的必须是**它自己那一句**的译文。只数条数的话，
    「三条英文配三条别人的译文」照样过关——那正是这条测试要拦的那种。
    """
    asked: list[list[str]] = []

    def _body(user: str) -> list[str]:
        head, *rest = user.splitlines()
        if rest:                                  # 批量：`N. 原文`
            return [ln.split(". ", 1)[-1] for ln in rest]
        return [head.split("：", 1)[-1]]           # 单行兜底那条 prompt

    class _Chat:
        def ask(self, _sys, user, **_k):
            body = _body(user)
            asked.append(body)
            if len(body) > 1:                      # 批量永远少回一条
                return {"lines": [f"译:{body[0]}"]}
            return {"line": f"译:{body[0]}"}

    rows = [{"t": 0.0, "text": "a"}, {"t": 1.0, "text": "b"}, {"t": 2.0, "text": "c"}]
    assert tool.translate(rows, _Chat()) == ["译:a", "译:b", "译:c"]
    # 判据自己的判据：批量那一路真的走到过（否则上面那行只证明了单行翻译能用）
    assert any(len(b) > 1 for b in asked), "这一趟根本没走批量，二分那条路没验到"


def test_单行兜底也拿不到译文时要报错不许塞空字幕(tool):
    """二分到单行仍然拿不到非空译文时**必须报错**——服务故障时静静塞进一批
    空字幕，比整条视频停下来糟得多（画面上会是「有中文行、但那一行是空的」）。
    """
    class _Chat:
        def ask(self, *_a, **_k):
            return {"line": "   "}                 # 永远只回空白

    rows = [{"t": 0.0, "text": "a"}, {"t": 1.0, "text": "b"}]
    with pytest.raises(RuntimeError, match="单行兜底三次都没成"):
        tool.translate(rows, _Chat())


def test_同slug不许静默覆盖(tool, monkeypatch, tmp_path):
    """同一天同赛事两条候选算出同一个 slug 时，旧版后写的直接盖掉先写的、
    一个字不吭。现在占坑失败要换 `-2`…，全占满返回 None。"""
    specs = tmp_path / "specs" / "interviews"
    specs.mkdir(parents=True)
    monkeypatch.setattr(tool, "SPECS", specs)
    assert tool._claim_slug("zverev-cincinnati-2026-r3") == "zverev-cincinnati-2026-r3"
    (specs / "zverev-cincinnati-2026-r3.draft.json").write_text("{}")
    assert tool._claim_slug("zverev-cincinnati-2026-r3") == "zverev-cincinnati-2026-r3-2"
    # 正式 spec 也算占用（提升过的不许被新草稿顶名）
    (specs / "zverev-cincinnati-2026-r3-2.json").write_text("{}")
    assert tool._claim_slug("zverev-cincinnati-2026-r3") == "zverev-cincinnati-2026-r3-3"


def test_下载失败要带yt_dlp尾部原因不许只报CalledProcessError(tool, monkeypatch, tmp_path):
    class _Failed:
        returncode = 1
        stdout = ""
        stderr = "HTTP Error 403: Forbidden from signed manifest"

    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: _Failed())
    monkeypatch.setattr("tennislive.video.official.media_url", lambda url: url)
    with pytest.raises(RuntimeError, match="HTTP Error 403.*signed manifest"):
        tool.transcribe("https://example.test/interview", tmp_path)
