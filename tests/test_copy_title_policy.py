from pathlib import Path

import pytest

from tennislive.render.copy_title import copy_title, validate_copy_title
from tools.push_reel import headline


@pytest.mark.parametrize('space', [' ', '\t', '\n', '\r', '\u00a0', '\u3000', '\u200b', '\ufeff'])
def test_all_whitespace_removed(space):
    assert copy_title(f'16{space}岁孙心然{space}过关') == '16岁孙心然过关'


def test_digits_and_punctuation_each_count():
    assert validate_copy_title('1' * 19 + '?') == '1' * 19 + '?'
    with pytest.raises(SystemExit, match='21 个字符'):
        validate_copy_title('1' * 20 + '?')
    with pytest.raises(SystemExit, match='21 个字符'):
        copy_title('a' * 21)


def test_copy_title_is_not_in_frame_title():
    assert headline(Path('output/2026-10-02/reel/sun'), '赛场之上', '',
                    summary='连赢9局，16岁孙心然过关') == '连赢9局16岁孙心然过关'


def test_essential_numeric_punctuation_survives():
    assert copy_title('6-4,7-6，胜率50%！') == '6-4,7-6胜率50%'
    assert copy_title('10.2开打？') == '10.2开打？'
    assert headline(Path('output/x'), '赛场之上', '甲 vs 乙', score='6-4 7-6') == '甲6-4，7-6乙'


def test_no_silent_truncation():
    with pytest.raises(SystemExit, match='超过 20'):
        headline(Path('output/x'), '赛场之上', '', summary='字' * 21)


def test_raw_validator_rejects_whitespace_and_empty():
    with pytest.raises(SystemExit, match='空白'):
        validate_copy_title('甲 乙')
    with pytest.raises(SystemExit, match='不能为空'):
        copy_title('\u3000\u200b')


def test_interview_generator_keeps_existing_contract():
    assert headline(Path('output/interviews/x'), '赛后开麦', '甲 vs 乙',
                    summary='伊埃拉再胜斯维托丽娜', date='2026-08-01') == '8.1 赛后开麦 | 伊埃拉再胜斯维托丽娜'
    with pytest.raises(SystemExit, match='--date'):
        headline(Path('output/interviews/x'), '赛后开麦', '甲 vs 乙')
