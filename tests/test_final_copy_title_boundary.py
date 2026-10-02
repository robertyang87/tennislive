"""Final publishing always retains date+column+| inside the 20-character limit."""
import html
import json
import re
from pathlib import Path

import pytest

from tools import push_reel
from tennislive.render.copy_title import (
    copy_hook_budget, copy_title, make_copy_title, validate_copy_title,
)
from tennislive.render.pushmsg import to_copy_page


def _caption(tmp_path, column, summary, slug='demo'):
    caption = tmp_path / f'{slug}.xhs.txt'
    caption.write_text('正文有另外一个事实\n\n#网球时差', encoding='utf-8')
    (tmp_path / f'{slug}.json').write_text(json.dumps({
        'cover': {'eyebrow': column}, 'column': column,
        'push': {'summary': summary},
    }, ensure_ascii=False), encoding='utf-8')
    return caption


@pytest.mark.parametrize('column', ['赛场之上', '赛后开麦', '网球有故事'])
@pytest.mark.parametrize('date,label', [('2026-10-02', '10.2'), ('2026-12-28', '12.28')])
def test_complete_prefix_counts_toward_twenty(tmp_path, column, date, label):
    budget = copy_hook_budget(label, column)
    hook = '1' * (budget - 1) + '?'
    caption = _caption(tmp_path, column, hook)
    _, title, body = push_reel.prepare_copy(caption, tmp_path / 'output', date=date)
    assert title == f'{label}{column}|{hook}' and len(title) == 20
    validate_copy_title(title, require_prefix=True)
    assert html.escape(title) in to_copy_page(title + '\n\n' + body)
    caption = _caption(tmp_path, column, hook + '?')
    with pytest.raises(SystemExit, match='21 个字符'):
        push_reel.prepare_copy(caption, tmp_path / 'output', date=date)


@pytest.mark.parametrize('slug,hook,count', [
    ('sun-lys-beijing-2026-r1', '孙心然连赢9局过关', 18),
    ('nishikori-tiafoe-tokyo-2026-r1', '锦织东京告别蒂亚福晋级', 20),
    ('zverev-norrie-beijing-2026-r1', '首盘救险兹维列夫晋级', 19),
    ('shang-baez-beijing-2026-r1', '商竣程主场逆转', 16),
])
def test_explicit_publishing_hooks_leave_attested_spec_immutable(tmp_path, slug, hook, count):
    caption = _caption(tmp_path, '赛场之上', '连赢9局，16岁孙心然过关', slug)
    spec_path = tmp_path / f'{slug}.json'
    before = spec_path.read_bytes()
    _, title, _ = push_reel.prepare_copy(caption, tmp_path / 'output', date='2026-10-02')
    assert title == f'10.2赛场之上|{hook}' and len(title) == count
    assert spec_path.read_bytes() == before


def test_legacy_interview_helper_stays_unchanged(tmp_path):
    out = tmp_path / 'output' / 'interviews' / 'demo'
    assert push_reel.headline(out, '赛后开麦', '甲 vs 乙',
        summary='伊埃拉再胜斯维托丽娜', date='2026-08-01').startswith('8.1 赛后开麦')
    with pytest.raises(SystemExit, match='--date'):
        push_reel.headline(out, '赛后开麦', '甲 vs 乙')


@pytest.mark.parametrize('column', ['赛场之上', '赛后开麦', '网球有故事'])
def test_actual_check_page_push_retain_identical_prefix(tmp_path, monkeypatch, capsys, column):
    import sys

    monkeypatch.syspath_prepend(str(Path(push_reel.__file__).parent))
    monkeypatch.chdir(tmp_path)
    budget = copy_hook_budget('10.2', column)
    caption = _caption(tmp_path, column, '1' * (budget - 1) + '\u3000?')
    out = tmp_path / 'output' / 'demo'
    out.mkdir(parents=True)
    (out / 'render.json').write_text(json.dumps({'video_url': 'https://example.org/video.mp4'}))
    (out / push_reel.STAT_CARD_NAME).write_bytes(b'unit-test-stat-card')
    expected = f'10.2{column}|' + '1' * (budget - 1) + '?'
    observed = {}
    # Only external IO is stubbed; title validation and HTML generation are real.
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
    assert len(expected) == 20
    assert f'readonly>{expected}</textarea>' in (out / 'copy.html').read_text()
    assert expected in observed['push_body']
    assert f'[preflight] title/tags/copy pass: {expected}' in capsys.readouterr().out


@pytest.mark.parametrize('stage', ['check', 'page', 'push'])
@pytest.mark.parametrize('column', ['赛场之上', '赛后开麦', '网球有故事'])
def test_every_stage_rejects_twenty_one_before_io(tmp_path, monkeypatch, stage, column):
    import sys

    hook = '9' * (copy_hook_budget('10.2', column) + 1)
    caption = _caption(tmp_path, column, hook)
    out = tmp_path / 'output'
    reached = []
    monkeypatch.setattr(push_reel, 'push', lambda *args, **kwargs: reached.append('push'))
    monkeypatch.setattr(push_reel, 'wait_for_copy_page', lambda *args: reached.append('page'))
    monkeypatch.setattr(sys, 'argv', ['push_reel.py', '--stage', stage, '--date', '2026-10-02',
                        '--outdir', str(out), '--copy', str(caption)])
    with pytest.raises(SystemExit, match='21 个字符'):
        push_reel.main()
    assert reached == [] and not (out / 'copy.html').exists()


def test_shared_copy_page_and_alternatives_keep_prefix():
    raw = '10.2 赛场之上 | 孙心然连赢9局过关'
    page = to_copy_page(raw + '\n\n正文 空格保持',
        alt_titles=['10.2赛场之上|另一 个\t标题', '10.2赛场之上|另一个标题'])
    assert 'readonly>10.2赛场之上|孙心然连赢9局过关</textarea>' in page
    assert '正文 空格保持' in page
    assert page.count('readonly>10.2赛场之上|另一个标题</textarea>') == 1
    with pytest.raises(SystemExit, match='21 个字符'):
        to_copy_page(raw + '\n\n正文', alt_titles=['10.2赛场之上|' + '9' * 12])
    with pytest.raises(SystemExit, match='日期'):
        to_copy_page('没有日期栏目\n\n正文')
    with pytest.raises(SystemExit, match='主题不能为空'):
        make_copy_title('10.2', '赛场之上', '')


def test_number_punctuation_and_prefix_are_preserved():
    assert copy_title('10.2 赛场之上｜甲6-4\u200b7-6乙') == '10.2赛场之上|甲6-4，7-6乙'
    assert copy_title('10.2赛场之上|甲逆转|乙止步') == '10.2赛场之上|甲逆转|乙止步'


def test_all_explainers_fit_even_the_widest_date():
    from tools import explainer_preflight as preflight
    from tennislive.video.explainer import _SCRIPTS
    assert len(_SCRIPTS) >= 40
    for slug in _SCRIPTS:
        deck = preflight.load_deck(slug, '12.28')
        assert preflight.copy_title_problems(deck) == [], slug
        title = deck.xhs.splitlines()[0]
        validate_copy_title(title, require_prefix=True)
        assert title.startswith('12.28')


def test_raw_qa_rejects_missing_prefix_whitespace_and_overflow():
    from datetime import date
    from tennislive.digest import Digest
    from tennislive.qa import check_xhs_post
    digest = Digest(today=date(2026, 10, 2))
    for title in ('1' * 21, '甲\t乙', '甲\u200b乙', '只保留主题'):
        fatal, _ = check_xhs_post(digest, title + '\n\n正文')
        assert any('标题' in problem for problem in fatal)
