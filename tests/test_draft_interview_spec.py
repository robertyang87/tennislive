"""tools/draft_interview_spec.py —— 自动建「赛后开麦」spec 草稿（纯函数，不联网）。

转写/翻译要 faster-whisper + DeepSeek（Actions 里跑），这里只测不联网的
拼接逻辑：受访者从名册认、slug 生成、草稿结构、cap_asr.json3 的形状、
翻译行数闸、同 slug 不许静默覆盖。
"""

from __future__ import annotations

import json
import shutil
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
        if "【目标，只翻译这一条】" in user:
            target = user.split("【目标，只翻译这一条】", 1)[1].splitlines()[0]
            return [target]
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


def test_单行兜底带前后文并把失败原因反馈给重试(tool):
    """费德勒全文第 83 行真实形状：英文按字幕宽度切在所有格中间。

    批量翻译拆到单行后若只喂 ``My goal was to spend my``，模型会逐字给出
    ``我的目标是花我的``；它既意思悬空又以「的」收尾，连续三次原样失败。
    单行仍需保持一行一译，但必须看得到下一条才能把中文语序自然切成
    ``我曾希望用一生 / 做自己热爱的事``。
    """
    prompts: list[str] = []
    target_attempts = 0

    class _Chat:
        def ask(self, _sys, user, **_k):
            nonlocal target_attempts
            prompts.append(user)
            if "逐条翻译成中文" in user:          # 强制走批量二分→单行兜底
                return {"lines": []}
            if "My goal was to spend my" in user and \
                    "【目标，只翻译这一条】My goal was to spend my" in user:
                target_attempts += 1
                if target_attempts == 1:
                    return {"line": "我的目标是花我的"}
                assert "以虚词“的”收尾" in user
                return {"line": "我曾希望用一生"}
            if "【目标，只翻译这一条】life doing something I love" in user:
                return {"line": "做自己热爱的事"}
            return {"line": "成名从不是目标"}

    rows = [
        {"t": 0.0, "text": "but fame was never the goal."},
        {"t": 1.0, "text": "My goal was to spend my"},
        {"t": 2.0, "text": "life doing something I love"},
    ]
    assert tool.translate(rows, _Chat(), max_zh_chars=13) == [
        "成名从不是目标", "我曾希望用一生", "做自己热爱的事",
    ]
    target_prompt = next(
        p for p in prompts if "【目标，只翻译这一条】My goal was to spend my" in p
    )
    assert "【上一条，仅供理解】but fame was never the goal." in target_prompt
    assert "【下一条，仅供理解】life doing something I love" in target_prompt
    assert target_attempts == 2, "坏答案应带着明确失败原因重试，不能原样撞三次"


def test_单行上下文能跨过二十五行批次边界(tool):
    """第 24 行的下一条在第二批；上下文必须来自完整 rows，不能只看当前批。"""
    seen_target = ""

    class _Chat:
        def ask(self, _sys, user, **_k):
            nonlocal seen_target
            if "逐条翻译成中文" in user:
                return {"lines": []}
            marker = "【目标，只翻译这一条】"
            target = user.split(marker, 1)[1].splitlines()[0]
            if target == "row-24":
                seen_target = user
            return {"line": f"译{target.split('-')[-1]}"}

    rows = [{"t": float(i), "text": f"row-{i}"} for i in range(26)]
    out = tool.translate(rows, _Chat(), max_zh_chars=13)
    assert out == [f"译{i}" for i in range(26)]
    assert "【上一条，仅供理解】row-23" in seen_target
    assert "【下一条，仅供理解】row-25" in seen_target


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


def test_抽音频的依赖要在开跑前就查掉而不是下到一半才报(tool, monkeypatch, capsys):
    """缺 ffmpeg 要死在第 5 秒，并且说出路——钉行为和位置两头。

    来路：oncourt-interviews run 138~142 连炸 5 趟，日志里是

        ⚠️ Fery Enjoying the Winston-Salem Nights: RuntimeError: yt-dlp 音频
        下载失败（exit 1）：... ERROR: Postprocessing: ffprobe and ffmpeg not found

    真因那半句埋在 1800 字符的 yt-dlp 尾巴里，外面套着一句「这条源失败了」，
    而它上一行刚打印「Tennis TV 解出 HLS」——**读起来像这条源的问题**。

    ⚠️ **位置那一头不能省**：只钉行为的话，把这段挪到下载之后照样绿，而那
    正好是这次真出事的样子（工具是在下载途中才发现缺依赖的）。CLAUDE.md
    「只测行为拦不住位置错」记的就是这个形状。
    """
    d = tool

    # ① 行为：认得出缺了谁
    real = shutil.which
    # 只撤销这一个模拟。直接调用 monkeypatch.undo() 会把 pytest 9 的
    # capsys 内部补丁也一起撤掉，后面的 stderr 断言便会读到空字符串。
    with monkeypatch.context() as media_patch:
        media_patch.setattr(
            shutil, "which",
            lambda b, *a, **k: None if b in ("ffmpeg", "ffprobe") else real(b, *a, **k))
        assert d._missing_media_tools() == ["ffmpeg", "ffprobe"]
    assert "ffmpeg" not in d._missing_media_tools(), (
        "沙箱里 ffmpeg 是在的（启动钩子装的），这条判据的前提没了")

    # ② 位置：预检必须排在真正干活之前
    src = Path("tools/draft_interview_spec.py").read_text(encoding="utf-8")
    main_src = src.split("def main() -> int:", 1)[1]
    at_check = main_src.find("_missing_media_tools()")
    at_work = main_src.find("ThreadPoolExecutor(")
    assert at_check >= 0, "main() 里没有这道预检了"
    assert 0 <= at_check < at_work, (
        "预检排到干活后面去了——那就退回「下到一半才发现装少了」，"
        "而那次的报错读起来像「这条源下不动」。")

    # ③ 报错要说出路：光说「缺 ffmpeg」，下一个人还得自己翻工作流
    monkeypatch.setattr(d, "_missing_media_tools", lambda: ["ffmpeg"])
    monkeypatch.setattr(sys, "argv", ["draft_interview_spec.py"])
    assert d.main() == 2
    err = capsys.readouterr().err
    assert "ensure_ffmpeg" in err and "postprocessing" in err.lower(), (
        "报错没给出路：要点明「-x 是 postprocessing、和源是不是 HLS 无关」，"
        "并指出工作流里加 `ensure_ffmpeg`。\n实际输出：" + err)
