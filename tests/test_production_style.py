from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from production_style import DAYPARTS, opening_context_problem, match_footage_problem


@pytest.mark.parametrize('daypart', DAYPARTS)
def test_natural_daypart_needs_no_clock(daypart):
    assert opening_context_problem(f'北京时间九月三十号{daypart}，中网首轮。') is None


@pytest.mark.parametrize('text', ['九月三十号下午', '北京时间下午', '北京时间九月三十号'])
def test_daypart_does_not_waive_date_or_timezone(text):
    assert opening_context_problem(text)


def test_night_session_opening_needs_no_clock():
    opening = ('北京时间十月五号夜场，中网第三轮。十六岁的孙心然，'
               '第一次参加巡回赛正赛，已经连赢两场。现在，她面对世界第四高芙。')
    assert opening_context_problem(opening) is None


@pytest.mark.parametrize('text, problem', [
    ('十月五号夜场，中网第三轮。', '没有北京时间口径'),
    ('北京时间夜场，中网第三轮。', '没有比赛日期'),
    ('北京时间十月五号，中网第三轮。', '没有已核实的开球时段'),
])
def test_night_session_keeps_opening_context_requirements(text, problem):
    assert opening_context_problem(text) == problem


def test_all_columns_have_one_canonical_time_policy():
    for file in ['CLAUDE.md', '.claude/skills/tennis-owner-taste/SKILL.md', '.claude/skills/tennis-editorial/SKILL.md']:
        text=(ROOT/file).read_text()
        assert '2026-09-30' in text and '不强制具体小时或分钟' in text
        assert all(word in text for word in ('夜里','凌晨','清晨','中午','傍晚'))
    prompt=(ROOT/'tools/draft_segments.py').read_text()
    assert '大概几点（不报到分钟）' not in prompt
    assert '自然时段' in prompt


def test_match_footage_default_rejects_photos_but_retains_native_cards():
    s={'cover':{'eyebrow':'赛场之上'},'segments':[{'image':'photo.jpg'}]}
    assert match_footage_problem(s)
    s['segments']=[{'stat_card':True,'image':'<stat_card>'},{'title_card':{'title':'比分'},'image':'<title_card>'}]
    assert match_footage_problem(s) is None
    s['cover']['eyebrow']='网球有故事';s['segments']=[{'image':'archive.jpg'}]
    assert match_footage_problem(s) is None
