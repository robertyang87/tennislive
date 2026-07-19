from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

from tennislive import cli, timeutil
from tennislive.models import DailyData, MatchStatus, Tour
from tennislive.render.cards import MARGIN, W, _flash_headline_lines, _Fonts

from conftest import make_match


def test_flash_headline_wrap_balances_long_chinese_title(monkeypatch):
    regular_font = Path("assets/fonts/NotoSansSC-Regular-sub.ttf").resolve()
    bold_font = Path("assets/fonts/NotoSansSC-Bold-sub.ttf").resolve()
    monkeypatch.setenv("TENNISLIVE_FONT", str(regular_font))
    monkeypatch.setenv("TENNISLIVE_FONT_BOLD", str(bold_font))
    draw = ImageDraw.Draw(Image.new("RGB", (W, 300)))

    lines = _flash_headline_lines(
        draw,
        "西西帕斯爆冷淘汰科利尼翁",
        _Fonts().title,
        W - 2 * MARGIN,
    )

    assert len(lines) == 2
    assert min(len(line) for line in lines) >= 3
    assert abs(len(lines[0]) - len(lines[1])) <= 1


def test_flash_uses_bundled_editorial_display_fonts(monkeypatch):
    monkeypatch.delenv("TENNISLIVE_FONT_DISPLAY", raising=False)
    monkeypatch.delenv("TENNISLIVE_FONT_LATIN", raising=False)

    fonts = _Fonts()

    assert "Smiley Sans" in fonts.display_title.getname()[0]
    assert "Barlow Condensed" in fonts.latin.getname()[0]


def test_flash_writes_one_review_manifest_for_duplicate_source_rows(
    tmp_path, monkeypatch
):
    today = date(2026, 7, 19)
    now = datetime(2026, 7, 19, 20, tzinfo=timezone(timedelta(hours=8)))
    match = make_match(
        home_name="Qinwen Zheng",
        home_country="CHN",
        tournament="Prague Open",
        tour=Tour.WTA,
        start_utc=now.astimezone(timezone.utc) - timedelta(hours=3),
        match_id="hot-cn",
    )
    match.tournament.level = "WTA250"

    regular_font = Path("assets/fonts/NotoSansSC-Regular-sub.ttf").resolve()
    bold_font = Path("assets/fonts/NotoSansSC-Bold-sub.ttf").resolve()
    monkeypatch.setenv("TENNISLIVE_FONT", str(regular_font))
    monkeypatch.setenv("TENNISLIVE_FONT_BOLD", str(bold_font))
    monkeypatch.setattr(timeutil, "beijing_today", lambda: today)
    monkeypatch.setattr(timeutil, "now_beijing", lambda: now)
    monkeypatch.setattr(
        cli,
        "fetch_day",
        lambda requested, prefer=None: DailyData(
            date_beijing=requested.isoformat(), matches=[match], source="test"
        ),
    )
    monkeypatch.chdir(tmp_path)

    manifest = tmp_path / "review.json"
    args = SimpleNamespace(
        outdir=str(tmp_path / "output"),
        source=None,
        no_publish=True,
        manifest=str(manifest),
    )

    assert cli.cmd_flash(args) == 0

    import json

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(payload["items"]) == 1
    assert payload["items"][0]["match_id"] == "hot-cn"
    assert len(payload["items"][0]["title_candidates"]) == 3
    card = Path(payload["items"][0]["card"])
    assert card.exists()
    with Image.open(card) as image:
        assert image.size == (1080, 1440)


def test_publish_flash_pins_committed_card_revision(tmp_path, monkeypatch):
    import json

    manifest = tmp_path / "review.json"
    manifest.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "title": "郑钦文赢下关键战",
                        "title_candidates": ["郑钦文赢下关键战", "郑钦文三盘过关"],
                        "text": "郑钦文赢下关键战\n\n比分与判断",
                        "card": "output/2026-07-19/flash/card.png",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    sent = []
    monkeypatch.setenv("GITHUB_REPOSITORY", "robertyang87/tennislive")
    monkeypatch.setenv(
        "TENNISLIVE_ASSET_REV", "d5a809e19988db7a69cac573842367bd07c900ad"
    )
    monkeypatch.setattr(
        "tennislive.publish.pushplus.push",
        lambda title, content: sent.append((title, content)),
    )

    args = SimpleNamespace(manifest=str(manifest))
    assert cli.cmd_publish_flash(args) == 0

    assert len(sent) == 1
    assert "@d5a809e19988db7a69cac573842367bd07c900ad/output/" in sent[0][1]
    assert "备选标题" in sent[0][1]


def test_content_command_generates_complete_preview_package(tmp_path, monkeypatch):
    import json

    today = date(2026, 7, 19)
    now = datetime(2026, 7, 19, 20, tzinfo=timezone(timedelta(hours=8)))
    match = make_match(
        home_name="Qinwen Zheng",
        home_country="CHN",
        tournament="Prague Open",
        tour=Tour.WTA,
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        start_utc=now.astimezone(timezone.utc) + timedelta(hours=2),
        match_id="preview-cn",
        round_name="Round of 16",
    )
    match.tournament.level = "WTA250"
    monkeypatch.setattr(timeutil, "beijing_today", lambda: today)
    monkeypatch.setattr(timeutil, "now_beijing", lambda: now)
    monkeypatch.setattr(
        cli,
        "fetch_day",
        lambda requested, prefer=None: DailyData(
            date_beijing=requested.isoformat(), matches=[match], source="test"
        ),
    )
    monkeypatch.setattr(
        "tennislive.render.webcards.generate_match_deck",
        lambda *args, **kwargs: [
            ("cover", Image.new("RGB", (1080, 1440), "#062019")),
            ("match", Image.new("RGB", (1080, 1440), "#0b3b2c")),
            ("insight", Image.new("RGB", (1080, 1440), "#0b3b2c")),
            ("discussion", Image.new("RGB", (1080, 1440), "#0b3b2c")),
        ],
    )
    monkeypatch.chdir(tmp_path)

    manifest = tmp_path / "review.json"
    args = SimpleNamespace(
        outdir=str(tmp_path / "output"),
        source=None,
        manifest=str(manifest),
    )

    assert cli.cmd_content(args) == 0

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["kind"] == "preview"
    assert item["match_id"] == "preview-cn"
    assert len(item["cards"]) == 4
    assert all(Path(card).exists() for card in item["cards"])
    package = Path(item["package_dir"])
    assert (package / "xiaohongshu.txt").exists()
    assert (package / "pinned_comment.txt").exists()
    assert (package / "facts.json").exists()
    assert (package / "qa.txt").read_text(encoding="utf-8") == "OK"


def test_publish_content_includes_all_cards_and_review_fields(tmp_path, monkeypatch):
    import json

    manifest = tmp_path / "content.json"
    manifest.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "kind": "preview",
                        "title": "郑钦文20:00出战",
                        "title_candidates": ["郑钦文20:00出战", "今晚这场值得看"],
                        "text": "郑钦文20:00出战\n\n赛前看点",
                        "pinned_comment": "你认为最关键的变量是什么？",
                        "cards": ["output/a.png", "output/b.png"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    sent = []
    monkeypatch.setenv("GITHUB_REPOSITORY", "robertyang87/tennislive")
    monkeypatch.setenv("TENNISLIVE_ASSET_REV", "abc123")
    monkeypatch.setattr(
        "tennislive.publish.pushplus.push",
        lambda title, content: sent.append((title, content)),
    )

    assert cli.cmd_publish_flash(SimpleNamespace(manifest=str(manifest))) == 0

    assert sent[0][0].startswith("⏰")
    assert sent[0][1].count("<img ") == 2
    assert "置顶评论" in sent[0][1]
    assert "最关键的变量" in sent[0][1]
