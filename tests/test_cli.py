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
        lambda title, content, **kwargs: sent.append((title, content)),
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
    assert "7.19｜" in item["title"]
    assert len(item["cards"]) == 4
    assert all(Path(card).exists() for card in item["cards"])
    package = Path(item["package_dir"])
    assert (package / "xiaohongshu.txt").exists()
    assert (package / "pinned_comment.txt").exists()
    assert (package / "facts.json").exists()
    assert (package / "qa.txt").read_text(encoding="utf-8") == "OK"
    facts = json.loads((package / "facts.json").read_text(encoding="utf-8"))
    assert facts["cover"]["evidence"]["match_id"] == "preview-cn"
    assert facts["cover"]["main"] == item["cover_headline"]


def test_digest_cli_fatal_returns_two_without_advancing_state(tmp_path, monkeypatch):
    from tennislive.digest import Digest

    today = date(2026, 7, 20)
    invalid = make_match(home_name="?", match_id="invalid-name")
    digest = Digest(today=today, results=[invalid], source="test")
    state_calls: list[str] = []

    monkeypatch.setattr(cli, "build_digest", lambda *args, **kwargs: digest)
    monkeypatch.setattr(
        "tennislive.sources.sportradar.SportradarOfficialStats.from_env",
        lambda: None,
    )
    monkeypatch.setattr(
        "tennislive.render.ai_editorial.enrich_with_github_models",
        lambda _digest: SimpleNamespace(status="disabled in test"),
    )
    monkeypatch.setattr(
        "tennislive.render.tournament_story.mark_story_used",
        lambda *args, **kwargs: state_calls.append("story"),
    )
    monkeypatch.setattr(
        "tennislive.render.tournament_story.record_story_wishlist",
        lambda *args, **kwargs: state_calls.append("wishlist"),
    )
    monkeypatch.setattr(
        "tennislive.render.xiaohongshu.record_quiz",
        lambda *args, **kwargs: state_calls.append("quiz"),
    )
    outdir = tmp_path / "output"
    result = cli.main(
        [
            "digest",
            "--date",
            today.isoformat(),
            "--outdir",
            str(outdir),
            "--no-cards",
        ]
    )

    package = outdir / today.isoformat()
    assert result == 2
    assert "[FATAL] 存在空球员名" in (package / "qa.txt").read_text("utf-8")
    assert (package / "cover_facts.json").exists()
    assert (package / "pinned_comment.txt").exists()
    assert (outdir / "profile" / "background.png").exists()
    assert state_calls == []


def test_knowledge_adhoc_rejects_unknown_slug_without_touching_network(tmp_path, monkeypatch):
    """未知 slug 必须在联网抓取赛程之前就报错退出——知识帖只能从人工核验
    过的选题池里选，不支持凭空生成，所以这里不该给 build_digest 兜底。"""

    def _boom(*args, **kwargs):
        raise AssertionError("不应该在 slug 校验失败后还去抓取赛程数据")

    monkeypatch.setattr(cli, "build_digest", _boom)
    outdir = tmp_path / "knowledge_adhoc"
    result = cli.main(
        [
            "knowledge-adhoc",
            "--slug",
            "does-not-exist",
            "--outdir",
            str(outdir),
        ]
    )
    assert result == 2
    assert not outdir.exists()


def test_knowledge_adhoc_generates_into_its_own_directory(tmp_path, monkeypatch):
    from tennislive.digest import Digest
    from tennislive.render.tournament_story import find_story_by_slug

    today = date(2026, 7, 20)
    digest = Digest(today=today, source="test")
    story = find_story_by_slug("hawkeye")
    assert story is not None

    monkeypatch.setattr(cli, "build_digest", lambda *args, **kwargs: digest)
    marked: list[str] = []
    monkeypatch.setattr(
        "tennislive.render.tournament_story.mark_story_used",
        lambda slug, when: marked.append(slug),
    )

    outdir = tmp_path / "knowledge_adhoc"
    result = cli.main(
        [
            "knowledge-adhoc",
            "--slug",
            "hawkeye",
            "--outdir",
            str(outdir),
        ]
    )
    assert result == 0
    assert marked == ["hawkeye"]
    assert (outdir / "story.json").exists()
    assert (outdir / "cards").is_dir()


def test_knowledge_adhoc_surfaces_failure_detail_instead_of_a_bare_traceback(
    tmp_path, monkeypatch, capsys
):
    """generate_knowledge_package 耗尽候选时会先把失败原因写进
    visual_sources.json 再抛异常——cmd_knowledge_adhoc 必须捕获并把这份
    详情打印出来，而不是让调用方只看到一个裸的 traceback（这是从一次
    真实的 workflow 失败里发现的：只有 ValueError 消息，看不到具体哪个
    环节、哪个来源失败了）。"""
    from tennislive.digest import Digest
    from tennislive.render.tournament_story import find_story_by_slug

    today = date(2026, 7, 20)
    digest = Digest(today=today, source="test")
    story = find_story_by_slug("hawkeye")
    assert story is not None

    monkeypatch.setattr(cli, "build_digest", lambda *args, **kwargs: digest)

    def _boom(digest, outdir, *, theme, story):
        Path(outdir).mkdir(parents=True, exist_ok=True)
        (Path(outdir) / "visual_sources.json").write_text(
            '{"status": "fail", "errors": ["配图来源全部被拒绝"]}',
            encoding="utf-8",
        )
        raise ValueError("知识帖自动恢复已耗尽本轮候选：等待后续班次重新抓取事实与图片")

    monkeypatch.setattr(
        "tennislive.render.knowledge.generate_knowledge_package", _boom
    )

    outdir = tmp_path / "knowledge_adhoc"
    result = cli.main(
        ["knowledge-adhoc", "--slug", "hawkeye", "--outdir", str(outdir)]
    )
    assert result == 2
    captured = capsys.readouterr()
    assert "配图来源全部被拒绝" in captured.out


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
        lambda title, content, **kwargs: sent.append((title, content)),
    )

    assert cli.cmd_publish_flash(SimpleNamespace(manifest=str(manifest))) == 0

    assert sent[0][0].startswith("⏰")
    assert sent[0][1].count("<img ") == 2
    assert "置顶评论" in sent[0][1]
    assert "最关键的变量" in sent[0][1]


def test_publish_pushplus_uses_xiaohongshu_title(tmp_path, monkeypatch):
    package = tmp_path / "2026-07-21"
    package.mkdir()
    (package / "wechat_title.txt").write_text("网球晨报｜旧标题", encoding="utf-8")
    (package / "xiaohongshu.txt").write_text(
        "🏆7.21｜谢里夫这冠有点意外\n\n正文", encoding="utf-8"
    )
    (package / "push.html").write_text("<div>待发稿</div>", encoding="utf-8")
    sent = []
    monkeypatch.setattr(
        "tennislive.publish.pushplus.push",
        lambda title, content, **kwargs: sent.append((title, content)),
    )

    assert cli.cmd_publish_pushplus(SimpleNamespace(dir=str(package))) == 0
    assert sent == [("🏆7.21｜谢里夫这冠有点意外", "<div>待发稿</div>")]
