from pathlib import Path

from tennislive.models import MatchStatus
from tennislive.render.common import group_by_tournament, result_line, schedule_line
from tennislive.render.pushmsg import to_copy_page, to_push_html
from tennislive.render.wechat import article_title, to_html, to_markdown
from tennislive.render.xiaohongshu import post_title, to_post

from conftest import make_match


def test_result_line_winner_perspective():
    m = make_match(winner=1, sets=((4, 6), (3, 6)), tiebreaks=())
    line = result_line(m)
    # 胜者（德约科维奇）在前，比分从胜者视角
    assert line.startswith("🇷🇸 [5]德约科维奇 2-0")
    assert "6-4 6-3" in line


def test_result_line_with_tiebreak():
    m = make_match()
    line = result_line(m)
    assert "辛纳" in line and "7-6(3)" in line


def test_schedule_line_beijing_time():
    m = make_match(status=MatchStatus.SCHEDULED, winner=None, sets=(), tiebreaks=())
    # 12:30 UTC = 20:30 北京
    assert schedule_line(m).startswith("20:30")


def test_group_by_tournament_orders_gs_first():
    gs = make_match(tournament="Wimbledon", match_id="a")
    small = make_match(tournament="Nordea Open Bastad", match_id="b")
    groups = group_by_tournament([small, gs])
    assert groups[0].name_en == "Wimbledon"
    assert "大满贯" in groups[0].title


def test_wechat_markdown(sample_digest):
    md = to_markdown(sample_digest)
    assert "中国军团" in md          # 郑钦文在赛果里 → 中国军团板块
    assert "最新赛果" in md
    assert "今日赛程" in md
    assert "郑钦文" in md
    assert "北京时间" in md


def test_wechat_html_inline_styles_only(sample_digest):
    html = to_html(sample_digest)
    assert "<style" not in html      # 公众号会剥离 style 块，必须全内联
    assert 'style="' in html
    assert "郑钦文" in html


def test_wechat_title_length(sample_digest):
    assert len(article_title(sample_digest)) <= 64


def test_xhs_post(sample_digest):
    post = to_post(sample_digest)
    title = post_title(sample_digest)
    assert len(title) <= 20
    assert "#网球" in post
    body = post.split("\n", 2)[2]
    assert len(body) <= 1000


def test_push_copy_page_and_button(sample_digest):
    xhs = "测试标题 <1>\n\n正文第一行\n正文第二行"
    page = to_copy_page(xhs)
    push_html = to_push_html(
        sample_digest, cards=["card_00_cover.png"], xhs_text=xhs
    )

    assert "复制标题" in page and "复制正文" in page
    assert "测试标题 &lt;1&gt;" in page
    assert "正文第一行" in page
    assert "copy.html" in push_html
    assert "打开并复制文案" in push_html
    assert "正文第一行" not in push_html


def test_cards_generation(tmp_path, sample_digest):
    from tennislive.render.cards import generate_cards

    paths = generate_cards(sample_digest, tmp_path / "cards")
    assert len(paths) >= 3  # 封面 + 赛果页 + 赛程页
    for p in paths:
        assert Path(p).stat().st_size > 10_000  # 是实际渲染的 PNG 而非空文件
    names = [p.name for p in paths]
    assert "card_00_cover.png" in names
