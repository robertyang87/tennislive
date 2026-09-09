"""Regression guards for numbered, paragraph-duplicated subtitle translations."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import draft_interview_spec as draft


LONG_QUESTION = (
    "你在今天这场比赛中面对了很多困难尤其是在决胜盘的关键时刻"
    "你曾经获得过改变比赛走势的机会但最终没有把握住"
    "现在回过头来看你认为自己在哪些方面还有提升空间以及接下来准备如何调整训练计划"
)
ROWS = [{"text": text} for text in (
    "You had chances in the final set.",
    "What could you have done differently?",
    "How will you prepare for the next tournament?",
)]


class Responses:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = 0

    def ask(self, *args, **kwargs):
        self.calls += 1
        return next(self.responses)


@pytest.mark.parametrize("prefix", ["68. ", "73. ", "68．", "68、", "68) "])
def test_reject_input_number_prefix(prefix):
    line = prefix + "我会继续努力"
    assert not draft._translation_line_ok(line, None)
    assert "行号" in draft._translation_line_issue(line, None)


@pytest.mark.parametrize("line", ["2026年我会继续努力", "3.5小时的比赛很艰难"])
def test_preserve_actual_numbers(line):
    assert draft._translation_line_ok(line, None)


def test_numbered_single_response_retries():
    chat = Responses({"line": "68. 我会继续努力"}, {"line": "我会继续努力"})
    assert draft.translate([ROWS[0]], chat) == ["我会继续努力"]
    assert chat.calls == 2


def test_numbered_response_never_silently_stripped():
    chat = Responses(*[{"line": "68. " + LONG_QUESTION}] * 3)
    with pytest.raises(RuntimeError, match="三次"):
        draft.translate([ROWS[0]], chat)


def test_long_duplicate_batch_is_retried():
    chat = Responses(
        {"lines": [LONG_QUESTION] * 3},
        {"line": "决胜盘你曾有机会"},
        {"lines": ["哪些地方可以做得更好", "你将如何备战下一站"]},
    )
    assert draft.translate(ROWS, chat) == [
        "决胜盘你曾有机会", "哪些地方可以做得更好", "你将如何备战下一站"
    ]
    assert chat.calls == 3


def test_split_fallback_cannot_hide_long_duplicates():
    chat = Responses(
        {"lines": [LONG_QUESTION] * 3},
        {"line": LONG_QUESTION},
        {"lines": [LONG_QUESTION] * 2},
    )
    with pytest.raises(RuntimeError, match="逐行对齐失败.*整段复制"):
        draft.translate(ROWS, chat)


def test_short_repeated_translations_are_allowed():
    rows = [{"text": text} for text in ["Thanks", "Thank you", "Many thanks"]]
    assert draft.translate(rows, Responses({"lines": ["谢谢"] * 3})) == ["谢谢"] * 3


def test_identical_source_repetitions_are_allowed():
    rows = [ROWS[0]] * 3
    assert draft.translate(rows, Responses({"lines": [LONG_QUESTION] * 3})) == [LONG_QUESTION] * 3


def test_global_guard_detects_duplicates_across_batches():
    rows = [{"text": f"Different source sentence {i}"} for i in range(26)]
    first = [f"对应译文第{i}句" for i in range(25)]
    first[0] = first[24] = LONG_QUESTION
    chat = Responses({"lines": first}, {"line": LONG_QUESTION})
    with pytest.raises(RuntimeError, match="逐行对齐失败"):
        draft.translate(rows, chat)
