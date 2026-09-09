import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from interview_zh_tail import has_dangling_tail


def test_achievement_is_a_complete_word():
    assert not has_dangling_tail("这真是一项了不起的成就")
    assert not has_dangling_tail("成就  ")


def test_actual_incomplete_phrases_remain_blocked():
    for phrase in ("我当时就", "我的目标是花我的", "成就和", "成就的"):
        assert has_dangling_tail(phrase)


def test_translation_accepts_real_failure_without_model_retries():
    from draft_interview_spec import translate, _translation_line_ok

    class Chat:
        calls = 0

        def ask(self, *args, **kwargs):
            self.calls += 1
            return {"line": "这真是一项了不起的成就"}

    chat = Chat()
    assert translate([{"t": 0, "text": "it's an amazing achievement"}], chat) == [
        "这真是一项了不起的成就"
    ]
    assert chat.calls == 1
    assert not _translation_line_ok("这真是一项了不起的成就", 4)
    assert not _translation_line_ok("", None)

def test_result_predicate_dui_is_complete_but_preposition_is_not():
    from draft_interview_spec import _translation_line_ok
    for phrase in ("我状态没打对", "这次没有做对", "你说得对", "这样不对"):
        assert not has_dangling_tail(phrase)
        assert _translation_line_ok(phrase, None)
    for phrase in ("我对", "我需要面对", "我没做对的", "你说得对而"):
        assert has_dangling_tail(phrase)
    assert not _translation_line_ok("我状态没打对", 3)
