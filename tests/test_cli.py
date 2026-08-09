from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFont

from tennislive import cli, timeutil
from tennislive.models import DailyData, MatchStatus, Tour
from tennislive.render.cards import MARGIN, W, _find_font, _flash_headline_lines, _Fonts

from conftest import make_match


def test_flash_card_cli_blocks_sensitive_topic_without_rendering(tmp_path, monkeypatch):
    """A sensitive headline is routed to human review — nothing is rendered."""
    calls: list[str] = []
    monkeypatch.setattr(
        "tennislive.render.flashcard.generate_flash_card",
        lambda *a, **k: calls.append("render") or Path("x"),
    )
    outdir = tmp_path / "fc"
    result = cli.main(
        [
            "flash-card",
            "--headline",
            "WTA gender testing 新规引发争议",
            "--event",
            "多名球员公开质疑",
            "--outdir",
            str(outdir),
        ]
    )
    assert result == 3
    assert calls == []
    assert not (outdir / "flash_copy.txt").exists()


def test_flash_card_cli_generates_card_and_copy_for_light_news(tmp_path, monkeypatch):
    """Light sporting news renders a card and writes a copy file."""
    rendered: dict = {}

    def fake_render(headline, *, event, when, where, who, punch, source_label,
                    date_label, out_path, theme):
        rendered.update(headline=headline, event=event, where=where)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"jpg")
        return Path(out_path)

    monkeypatch.setattr(
        "tennislive.render.flashcard.generate_flash_card", fake_render
    )
    outdir = tmp_path / "fc"
    result = cli.main(
        [
            "flash-card",
            "--headline",
            "18岁小将爆冷淘汰头号种子",
            "--event",
            "决胜盘 10-8，救回 3 个赛点完成逆转。",
            "--where",
            "辛辛那提",
            "--who",
            "小将 vs 头号种子",
            "--outdir",
            str(outdir),
        ]
    )
    assert result == 0
    assert rendered["headline"] == "18岁小将爆冷淘汰头号种子"
    assert rendered["where"] == "辛辛那提"
    copy = (outdir / "flash_copy.txt").read_text("utf-8")
    assert copy.startswith("18岁小将爆冷淘汰头号种子")
    assert "📍 辛辛那提" in copy  # meta line assembled from structured fields
    assert "💬" in copy and "#网球" in copy


def test_flash_radar_queues_only_offcourt_nonsensitive_news(tmp_path, monkeypatch):
    """The radar keeps off-court, non-sensitive news; match/sensitive drop out."""
    import json as _json

    from tennislive.research.trends import TrendSignal

    # 时间戳跟着真实时钟走。原来写死在 2026-07-24，而 offcourt_flash_candidates
    # 的新鲜度闸门（48 小时）用的是 datetime.now()——测试只 monkeypatch 了
    # beijing_today，管不到它。所以现实时间一过 07-26 09:00Z，三条信号全部过期，
    # 候选恒为空，这条测试从此永远红。写成"相对现在"就跟日期无关了。
    fresh = datetime.now(timezone.utc) - timedelta(hours=2)

    def stamp(offset_minutes: int) -> str:
        return (fresh + timedelta(minutes=offset_minutes)).isoformat()

    signals = [
        TrendSignal(
            kind="official-news",
            source="ATP",
            title="Sinner beats Alcaraz 7-5 6-4 in Cincinnati final",
            url="u1",
            published_at=stamp(0),
        ),
        TrendSignal(
            kind="official-news",
            source="ATP",
            title="ATP announces electronic line calling across all events",
            url="u2",
            published_at=stamp(60),
        ),
        TrendSignal(
            kind="official-news",
            source="ITIA",
            title="Player suspended after positive doping test",
            url="u3",
            published_at=stamp(90),
        ),
    ]
    monkeypatch.setattr(
        "tennislive.research.trends.fetch_trend_signals",
        lambda *a, **k: (signals, {"radar": "ok"}),
    )
    monkeypatch.setattr(timeutil, "beijing_today", lambda: date(2026, 7, 24))

    result = cli.main(
        ["flash-radar", "--outdir", str(tmp_path), "--no-cards"]
    )
    assert result == 0

    radar_dir = tmp_path / "2026-07-24" / "flash_radar"
    queue = _json.loads((radar_dir / "flash_radar_queue.json").read_text("utf-8"))
    assert [c["url"] for c in queue["candidates"]] == ["u2"]
    push = (radar_dir / "flash_radar_push.html").read_text("utf-8")
    assert "electronic line calling" in push
    assert "Sinner beats" not in push  # match news never enters the flash queue


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


def test_default_fonts_render_cjk_without_env(monkeypatch):
    """无环境变量时默认字体必须能画中文（2026-07-25 实测 bug）。

    assets/fonts/ 里 Latin-only 的 BarlowCondensed 按字母序排在 Noto 之前，
    早前的 "*" 泛匹配会把它选成正文默认字体，"网球时差"全渲染成豆腐块。
    Latin-only 字体绝不能排在 CJK 字体前面。
    """
    monkeypatch.delenv("TENNISLIVE_FONT", raising=False)
    monkeypatch.delenv("TENNISLIVE_FONT_BOLD", raising=False)

    for bold in (False, True):
        path, idx = _find_font(bold=bold)
        name = Path(path).name
        assert "barlow" not in name.lower(), name
        # 这里原来还有一条 `any(tag in name for tag in ("Noto", "CJK", "SC"))`。
        # 它是拿**文件名**近似「这是不是中文字体」，而判据其实就在下面几行：
        # 画出来看笔画。沙箱里装的中文字体是文泉驿正黑（`wqy-zenhei.ttc`），
        # 中文渲染完全正常，却因为名字里没有那三个词被判红——一条**假阴性**，
        # 26 条失败里唯一不是缺依赖的那条。CI 上装的是 Noto，两边都该绿。
        # 排除 barlow 这条留着：它挡的是具体那个文件，不是在猜字体语言。

        font = ImageFont.truetype(path, size=48, index=idx)

        def render(text: str) -> bytes:
            img = Image.new("L", (240, 64), 0)
            ImageDraw.Draw(img).text((0, 0), text, font=font, fill=255)
            return img.tobytes()

        # 有笔画，且不同汉字形状不同——豆腐块会每个字都一模一样
        assert render("网球时差") != render("")
        assert render("网") != render("时")


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
    monkeypatch.setattr(
        "tennislive.render.tournament_story.mark_adhoc_knowledge_published",
        lambda when: None,
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


def test_knowledge_adhoc_with_slug_does_not_need_live_match_data(tmp_path, monkeypatch):
    """指定 slug 时选题已经定死，下游只用 digest.today 取日期，不碰
    results/live/schedule/rankings——所以不该要求 build_digest（ESPN +
    SofaScore）都通才能发。真实事故：两个源同一天都 403，把一篇跟当日
    赛程毫无关系的 trivia 选题一起拖死（run 31263560107）。"""
    from tennislive.sources.base import SourceError

    def _boom(*args, **kwargs):
        raise SourceError("抓取失败：所有数据源均失败")

    monkeypatch.setattr(cli, "build_digest", _boom)
    marked: list[str] = []
    monkeypatch.setattr(
        "tennislive.render.tournament_story.mark_story_used",
        lambda slug, when: marked.append(slug),
    )
    monkeypatch.setattr(
        "tennislive.render.tournament_story.mark_adhoc_knowledge_published",
        lambda when: None,
    )

    outdir = tmp_path / "knowledge_adhoc"
    result = cli.main(
        ["knowledge-adhoc", "--slug", "hawkeye", "--outdir", str(outdir)]
    )
    assert result == 0
    assert marked == ["hawkeye"]
    assert (outdir / "story.json").exists()


def test_knowledge_adhoc_auto_selects_when_slug_omitted(tmp_path, monkeypatch):
    """留空 --slug 时必须复用常规每日流程的自动选题逻辑：不做 slug 校验，
    直接把 story=None 交给 generate_knowledge_package，由它内部调用
    tournament_story_candidates 按当日热度/时效排序、逐个候选试配图。"""
    from tennislive.digest import Digest
    from tennislive.render.tournament_story import find_story_by_slug

    today = date(2026, 7, 20)
    digest = Digest(today=today, source="test")
    monkeypatch.setattr(cli, "build_digest", lambda *args, **kwargs: digest)

    captured_story = object()  # sentinel distinct from None to prove it was overwritten

    def _fake_generate(digest, outdir, *, theme, story):
        nonlocal captured_story
        captured_story = story
        Path(outdir).mkdir(parents=True, exist_ok=True)
        return find_story_by_slug("hawkeye")

    monkeypatch.setattr(
        "tennislive.render.knowledge.generate_knowledge_package", _fake_generate
    )
    marked: list[str] = []
    monkeypatch.setattr(
        "tennislive.render.tournament_story.mark_story_used",
        lambda slug, when: marked.append(slug),
    )
    monkeypatch.setattr(
        "tennislive.render.tournament_story.mark_adhoc_knowledge_published",
        lambda when: None,
    )

    outdir = tmp_path / "knowledge_adhoc"
    result = cli.main(["knowledge-adhoc", "--outdir", str(outdir)])
    assert result == 0
    assert captured_story is None
    assert marked == ["hawkeye"]


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


