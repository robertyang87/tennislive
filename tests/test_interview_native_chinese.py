"""Native Chinese is source evidence; English still requires both subtitles."""
import re

import pytest

from tools import build_interview_clip as clip
from tools.check_interview_landed import bilingual_body_ok


def mixed_spec():
    return {"start": 10.0, "end": 20.0, "asr_model": "small", "whisper_model": "medium",
            "event": "2026 WTA1000 北京 1/8决赛", "winner": "郑钦文",
            "interview_kind": "赛后场上采访",
            "push": {"matchup": "郑钦文 vs 查拉耶娃", "score": "6-1 2-6 6-4"},
            "transcript_languages": [{"start": 10.0, "end": 15.0, "language": "en"},
                                     {"start": 15.0, "end": 20.0, "language": "zh"}]}


def test_native_zh_uses_source_once_and_english_keeps_dual(tmp_path):
    spec = mixed_spec()
    lines = [{"a": 10.0, "b": 12.0, "en": "Thank you."},
             {"a": 15.0, "b": 18.0, "en": "今天比赛非常艰难。", "source_language": "en"}]
    spec["zh"] = ["谢谢", "今天比赛非常艰难"]
    ass = tmp_path / "body.ass"
    clip.write_ass(lines, spec["zh"], 10.0, ass, spec)
    events = [line for line in ass.read_text().splitlines() if line.startswith("Dialogue:")]
    assert sum(",EN," in e for e in events) == 1
    assert sum(",ZH," in e for e in events) == 2
    assert sum("今天比赛非常艰难" in e for e in events) == 1
    assert bilingual_body_ok(ass, spec)[0]
    # A missing English event must remain a QC failure in the English window.
    ass.write_text("\n".join(e for e in events if ",EN," not in e))
    assert not bilingual_body_ok(ass, spec)[0]


def test_native_source_cannot_be_replaced_by_a_translation(tmp_path):
    spec = mixed_spec()
    with pytest.raises(SystemExit, match="保留原话"):
        clip.write_ass([{"a": 15.0, "b": 17.0, "en": "今天比赛非常艰难。"}],
                       ["今天轻松赢了比赛"], 10.0, tmp_path / "body.ass", spec)


def test_chinese_word_boundaries_spacing_punctuation_and_no_lone_tail():
    words = [(0.0, "今天"), (0.2, "这"), (0.4, "场"), (0.6, "比赛"),
             (0.8, "非常"), (1.0, "艰难。"), (1.4, "谢谢"), (1.6, "大家！")]
    lines = clip.segment_native_zh(words, 0, 3, budget=6, width=len)
    assert lines[-1]["en"] == "谢谢大家！"
    assert "".join(s["en"] for s in lines) == "今天这场比赛非常艰难。谢谢大家！"
    assert all(len(re.sub(r"\W", "", s["en"])) > 1 for s in lines)
    assert all(len(s["en"]) <= 6 for s in lines)
    assert all(s["source_language"] == "zh" for s in lines)
    remainder = clip.segment_native_zh([(0, "今天"), (.2, "我们"), (.4, "认真"),
                                        (.6, "打"), (.8, "球")], 0, 2,
                                       budget=7, width=len)
    assert remainder[-1]["en"] == "打球"


def test_native_chinese_measures_the_real_chinese_font():
    text = "今天这场比赛非常非常艰难"
    words = [(i * .2, ch) for i, ch in enumerate(text)]
    lines = clip.segment_native_zh(words, 0, 5)
    assert "".join(s["en"] for s in lines) == text
    assert all(clip._zh_width(s["en"]) <= clip._LINE_PX for s in lines)


def test_english_segment_contract_is_unchanged_without_native_windows():
    words = [(10, "Thank"), (10.2, "you."), (11, "Great"), (11.3, "match.")]
    legacy = clip.segment(words, 10, 15, width=len, budget=952)
    assert clip.segment(words, 10, 15, width=len, budget=952,
                        language_windows=[{"start": 10, "end": 15, "language": "en"}]) == legacy
    mixed = clip.segment(words + [(15.1, "谢谢。")], 10, 20, width=len, budget=952,
                         language_windows=mixed_spec()["transcript_languages"])
    english = [{k: v for k, v in line.items() if k != "source_language"}
               for line in mixed if line["source_language"] == "en"]
    assert english == legacy


def test_explicit_chinese_comparison_ignores_asr_word_segmentation_only():
    a, b = "今天 这 场 比 赛 非常 艰 难", "今天这场比赛 非常艰难"
    assert clip.disagree_rate(a, b)[0] > .12
    assert clip.disagree_rate(a, b, native_chinese=True)[0] == 0
    assert clip.disagree_rate(a, b.replace("艰难", "轻松"), native_chinese=True)[0] > .12
    assert clip.compare_tokens("Thank you, uh.") == clip.compare_tokens("Thank you, uh.", native_chinese=True)
    assert clip.source_compare_tokens([(10, "今天比赛"), (16, "今天比赛")],
                                      mixed_spec()["transcript_languages"]) == ["今天比赛", "今", "天", "比", "赛"]


def test_native_zh_manual_clause_boundaries_do_not_enter_the_subtitle():
    words = [(0, "今天"), (.2, "比赛"), (1.5, "谢谢"), (1.7, "大家")]
    lines = clip.segment_native_zh(words, 0, 3, word_fix={"谢谢": "‖谢谢"})
    assert [s["en"] for s in lines] == ["今天比赛", "谢谢大家"]
    assert lines[1]["a"] == 1.5
