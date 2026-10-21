"""A doubles match decider determines the winner; set tiebreaks stay superscript."""
from pathlib import Path
import sys

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from render_story_info_band import (  # noqa: E402
    BRAND_GREEN, WHITE, SCORE, SCORE_LIGHT,
    _corner_people_runs, _corner_score_runs, label_fields_problem, render,
    score_number_colors, set_number_runs, set_score_wins,
)


def test_match_decider_is_a_complete_score_not_a_set_tiebreak():
    assert set_number_runs("[10-6]") == [
        ("[", False), ("10", True), ("-", False), ("6", False), ("]", False)]
    assert set_number_runs("[6-10]") == [
        ("[", False), ("6", False), ("-", False), ("10", True), ("]", False)]
    assert score_number_colors("6-3 1-6 [10-6]") is not None
    assert set_score_wins("6-3 1-6 [10-6]") == [True, False, True]
    assert set_score_wins("6-3 1-6 [6-10]") == [True, False, False]
    for malformed in ("[10-6", "10-6]", "[10-6](5)", "决胜抢十 [10-6]"):
        assert score_number_colors(malformed) is None

    ordinary = _corner_score_runs("7-6(7)", 115)
    assert [run.text for run in ordinary] == ["7", "-", "6", "7"]
    assert ordinary[-1].dy < 0 and ordinary[-1].font.size < 115
    assert ordinary[-1].fill == WHITE


@pytest.mark.parametrize("decider,winner", [("[10-6]", 0), ("[6-10]", 1)])
def test_match_decider_draw_runs_keep_brackets_and_choose_correct_team(decider, winner):
    metric = f"6-3 1-6 {decider}"
    runs = _corner_score_runs(metric, 115)
    decider_runs = runs[next(i for i, run in enumerate(runs) if run.text == "["):]
    assert "".join(run.text for run in decider_runs) == decider
    assert all(run.dy == 0 and run.font.size == 115 for run in decider_runs)
    for run in decider_runs:
        if run.text == "10":
            assert run.fill == BRAND_GREEN and Path(run.font.path) == SCORE
        elif run.text in ("6", "[", "]"):
            assert run.fill == WHITE and Path(run.font.path) == SCORE_LIGHT
    people = _corner_people_runs("穆霍娃 / 门西克 vs 本西奇 / 科博利", metric, 73)
    assert people[0].fill == (BRAND_GREEN if winner == 0 else WHITE)
    assert people[2].fill == (BRAND_GREEN if winner == 1 else WHITE)


@pytest.mark.parametrize("layout", ["corner", "classic"])
def test_bracketed_match_decider_renders_as_score_in_both_layouts(tmp_path, layout):
    label = {"topic": "美网混双冠军", "date": "2026.08.26", "place": "美网混双决赛",
             "people": "穆霍娃 / 门西克 vs 本西奇 / 科博利", "score": "6-3 1-6 [10-6]"}
    assert label_fields_problem(label) is None
    out = render(label["date"], label["topic"], label["people"],
                 tmp_path / f"{layout}.png", metric=label["score"], layout=layout)
    with Image.open(out) as image:
        assert image.mode == "RGBA" and image.getchannel("A").getbbox()
