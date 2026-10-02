"""Final publication invariants do not redefine legacy intermediate headlines."""
import html
import json
import re
from pathlib import Path

import pytest

from tools import push_reel
from tennislive.render.copy_title import copy_title, validate_copy_title
from tennislive.render.pushmsg import to_copy_page


def _caption(tmp_path, column, summary):
    caption = tmp_path / 'demo.xhs.txt'
    caption.write_text('正文有另外一个事实\n\n#网球时差', encoding='utf-8')
    (tmp_path / 'demo.json').write_text(json.dumps({
        'cover': {'eyebrow': column}, 'column': column,
        'push': {'summary': summary},
    }, ensure_ascii=False), encoding='utf-8')
    return caption


@pytest.mark.parametrize('column', ['赛场之上', '赛后开麦', '网球有故事'])
@pytest.mark.parametrize('summary, expected', [
    ('连赢9局，16 岁孙心然过关', '连赢9局16岁孙心然过关'),
    ('1' * 20, '1' * 20),
    ('甲' * 20, '甲' * 20),
    ('甲6-4\u200b7-6乙', '甲6-4，7-6乙'),
])
def test_all_columns_prepare_final_title_without_legacy_budget(tmp_path, column, summary, expected):
    caption = _caption(tmp_path, column, summary)
    got_column, title, body = push_reel.prepare_copy(caption, tmp_path / 'output')
    assert got_column == column and title == expected
    validate_copy_title(title)
    for page in (to_copy_page(title + '\n\n' + body),
                 push_reel.build_html('https://example.org/video.mp4',
                                      'https://example.org/copy.html', '',
                                      title + '\n\n' + body, '', column)):
        assert html.escape(expected) in page
        assert summary not in page or summary == expected


@pytest.mark.parametrize('column', ['赛场之上', '赛后开麦', '网球有故事'])
def test_overlong_final_title_fails_before_page_or_push(tmp_path, column):
    caption = _caption(tmp_path, column, '9' * 21)
    with pytest.raises(SystemExit, match='21 个字符'):
        push_reel.prepare_copy(caption, tmp_path / 'output')


def test_actual_interview_page_stage_emits_compact_copy(tmp_path, monkeypatch):
    caption = _caption(tmp_path, '赛后开麦', '伊埃拉 再胜斯维托丽娜')
    out = tmp_path / 'output' / 'interviews' / 'demo'
    monkeypatch.setattr('sys.argv', ['push_reel.py', '--stage', 'page',
        '--outdir', str(out), '--copy', str(caption), '--date', '2026-08-01'])
    assert push_reel.main() == 0
    page = (out / 'copy.html').read_text()
    title = html.unescape(re.search(r'<textarea id="title"[^>]*>(.*?)</textarea>', page).group(1))
    assert title == '伊埃拉再胜斯维托丽娜'
    validate_copy_title(title)


def test_existing_interview_intermediate_contract_is_unchanged(tmp_path):
    out = tmp_path / 'output' / 'interviews' / 'demo'
    assert push_reel.headline(out, '赛后开麦', '甲 vs 乙',
        summary='伊埃拉再胜斯维托丽娜', date='2026-08-01').startswith('8.1 赛后开麦')
    with pytest.raises(SystemExit, match='--date'):
        push_reel.headline(out, '赛后开麦', '甲 vs 乙')


@pytest.mark.parametrize('column', ['赛场之上', '赛后开麦', '网球有故事'])
def test_actual_check_page_push_use_identical_final_title(tmp_path, monkeypatch, capsys, column):
    import sys

    monkeypatch.syspath_prepend(str(Path(push_reel.__file__).parent))
    monkeypatch.chdir(tmp_path)
    caption = _caption(tmp_path, column, '1' * 10 + '\u3000' + '2' * 10)
    out = tmp_path / 'output' / 'demo'
    out.mkdir(parents=True)
    (out / 'render.json').write_text(json.dumps({'video_url': 'https://example.org/video.mp4'}))
    (out / push_reel.STAT_CARD_NAME).write_bytes(b'unit-test-stat-card')
    expected = '1' * 10 + '2' * 10
    observed = {}
    # Only external IO is stubbed. All production title/copy validators and HTML
    # builders run unchanged; no fake film/QC assertion is made by this test.
    monkeypatch.setattr(push_reel, 'wait_for_copy_page',
                        lambda url, expect: observed.setdefault('page_expect', expect))
    monkeypatch.setattr(push_reel, 'wait_for_video', lambda url: None)

    def fake_push(title, body, **kwargs):
        observed.update(push_title=title, push_body=body)
        return 'test-receipt'

    monkeypatch.setattr(push_reel, 'push', fake_push)
    base = ['push_reel.py', '--outdir', str(out), '--copy', str(caption), '--date', '2026-10-02']
    for stage in ('check', 'page', 'push'):
        monkeypatch.setattr(sys, 'argv', base + ['--stage', stage])
        assert push_reel.main() == 0
    assert observed['push_title'] == observed['page_expect'] == expected
    page = (out / 'copy.html').read_text()
    assert f'readonly>{expected}</textarea>' in page
    assert expected in observed['push_body']
    assert f'[preflight] title/tags/copy pass: {expected}' in capsys.readouterr().out


@pytest.mark.parametrize('stage', ['check', 'page', 'push'])
@pytest.mark.parametrize('column', ['赛场之上', '赛后开麦', '网球有故事'])
def test_every_stage_rejects_overlong_before_external_io(tmp_path, monkeypatch, stage, column):
    import sys

    caption = _caption(tmp_path, column, '9' * 21)
    out = tmp_path / 'output'
    reached = []
    monkeypatch.setattr(push_reel, 'push', lambda *args, **kwargs: reached.append('push'))
    monkeypatch.setattr(push_reel, 'wait_for_copy_page', lambda *args: reached.append('page'))
    monkeypatch.setattr(sys, 'argv', ['push_reel.py', '--stage', stage,
                        '--outdir', str(out), '--copy', str(caption)])
    with pytest.raises(SystemExit, match='21 个字符'):
        push_reel.main()
    assert reached == []
    assert not (out / 'copy.html').exists()


def test_shared_copy_page_and_alternative_titles_are_enforced():
    from tennislive.render.pushmsg import to_copy_page
    page = to_copy_page('10.2 赛场之上 | 连赢9局，16岁孙心然过关\n\n正文 空格保持',
                        alt_titles=['另一 个\t标题', '另一个标题'])
    assert '<textarea id="title" readonly>连赢9局16岁孙心然过关</textarea>' in page
    assert '正文 空格保持' in page
    assert page.count('readonly>另一个标题</textarea>') == 1
    with pytest.raises(SystemExit, match='21 个字符'):
        to_copy_page('标题\n\n正文', alt_titles=['9' * 21])
    with pytest.raises(SystemExit, match='21 个字符'):
        to_copy_page('9' * 21 + '\n\n正文')


def test_numeric_set_boundary_not_lost_with_whitespace_removal():
    assert copy_title('甲6-4\t7-6乙') == '甲6-4，7-6乙'


def test_every_active_explainer_has_valid_copy_title():
    from tools import explainer_preflight as preflight
    from tennislive.video.explainer import _SCRIPTS
    assert len(_SCRIPTS) >= 40
    for slug in _SCRIPTS:
        deck = preflight.load_deck(slug)
        assert preflight.copy_title_problems(deck) == [], slug
        validate_copy_title(deck.xhs.splitlines()[0])


def test_raw_publishing_qa_counts_ascii_and_rejects_whitespace():
    from datetime import date
    from tennislive.digest import Digest
    from tennislive.qa import check_xhs_post
    digest = Digest(today=date(2026, 10, 2))
    for title in ('1' * 21, '甲\t乙', '甲\u200b乙'):
        fatal, _ = check_xhs_post(digest, title + '\n\n正文')
        assert any('标题' in problem for problem in fatal)


def test_legacy_wrapper_removal_keeps_every_content_clause():
    assert copy_title("10.2赛场之上|甲逆转|乙遗憾止步") == "甲逆转乙遗憾止步"
    assert copy_title("10.2开打") == "10.2开打"
