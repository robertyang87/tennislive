from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

from tennislive import cli, timeutil
from tennislive.models import DailyData, Tour
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
