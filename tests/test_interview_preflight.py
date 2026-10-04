"""赛后开麦 dispatch 之前的离线预检、片尾板／冻帧、拼接清单、推送后修订——判据。

来路和量法分别写在 `tools/interview_preflight.py`、`tools/interview_spec_gates.py`、
`tools/interview_tail.py`、`tools/interview_assembly.py`、`tools/interview_revision.py`
的 docstring 里；这里每一组都钉「把那道检查拆掉就红」。

⚠️ 不拿 `output/` 当判据的主语（CI 的稀疏检出没有它）：字幕缓存、成片、QC 凭证
一律在 tmp 里现造。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import build_interview_clip as bic  # noqa: E402
import interview_assembly as ia  # noqa: E402
import interview_preflight as pf  # noqa: E402
import interview_revision as ir  # noqa: E402
import interview_spec_gates as gates  # noqa: E402
import interview_tail as tail  # noqa: E402

SPECS = ROOT / "specs" / "interviews"


def _corpus():
    for p in sorted(SPECS.glob("*.json")):
        if not p.name.endswith(".draft.json"):
            yield json.loads(p.read_text(encoding="utf-8"))


def _judged(check: str, found: list[tuple[dict, str]]) -> list[str]:
    """全库测试的发现里，**自动链刚提交、还没核也没发**的那几条只报（K 的
    `unverified_auto_spec`），回其余的（照判）。

    这几条判据在出片那一趟 `build_interview_clip.main()` 开头都有同一道闸（`check_takeaway`、
    `check_score_orientation`），片子出不去；而 `interview-auto-render` 用 GITHUB_TOKEN 直推
    main、CI 不跑，这里判红只会红在下一个无关的 PR 上（批次 4 复审 BLOCKING，和 01684ef0
    拉沃尔杯那次同一个形状）。请求那条路在 `production_preflight.check_request` 就拦。"""
    import build_interview_request as req  # noqa: PLC0415

    auto, hard = {}, []
    for spec, what in found:
        slug = str(spec.get("slug") or "")
        if req.unverified_auto_spec(spec, slug):
            auto.setdefault(slug, []).append(what)
        else:
            hard.append(f"{slug}: {what}")
    req.report_unverified_auto(check, auto)
    return hard


# ── 一、收尾卡那一句要一行放得下 ─────────────────────────────────────────


def _card_spec(point: str, slug: str = "new-one") -> dict:
    return {"slug": slug, "start": 0.0, "end": 60.0, "zh": ["你好"],
            "takeaway": {"close": {"point": point, "ask": "你怎么看？"}}}


@pytest.mark.parametrize(("point", "where"), [
    # jodar-bublik 48a60760 之前那一版：渲完抽帧看到折成「费 / 德勒」
    ("首秀赢完球 他先谢看台上的费德勒", "首秀赢完球 他先谢看台上的费 ／ 德勒"),
    # deminaur-zverev 617db353 之前那一版：折成「一 / 直顶住」
    ("落后一盘又被破发 他说只是一直顶住", "落后一盘又被破发 他说只是一 ／ 直顶住"),
])
def test_量宽的尺子能复现老成片上看到的折点(point, where):
    """判据的量法要能把**成片上真看到的那个折点**原样算出来——算不出来就说明
    尺子和 Chromium 不是一把（字体、字号、字距、正文区宽度任何一个对不上）。
    那两张卡是 2026-09-27 之前的 CSS 渲的：任意字间可断、不 balance、左边距 92。"""
    lines = gates.card_lines(point, bic.CANVAS_W - 92 - bic.TAKEAWAY_PAD_RIGHT, keep_all=False)
    assert " ／ ".join(lines) == where


#: 现在的卡（keep-all ＋ balance、正文区 860px）真渲出来的行——Chromium 逐字取行
#: （`tests/test_interview_visual._LINES_JS` 那一套），2026-09-27 全库 104 张卡＋4 条
#: 长名字样例对过一遍，66 张多行卡的折点和 `card_lines` 逐字一样。这里钉各类形状各一张。
_CHROMIUM_LINES = [
    ("首秀赢完球 他先谢看台上的费德勒", ["首秀赢完球", "他先谢看台上的费德勒"]),     # 空格
    ("决胜盘 0-5 落后 救回赛点 连赢七局",                                           # balance：贪心会是
     ["决胜盘 0-5 落后", "救回赛点 连赢七局"]),                                      # 「…救回赛点 ／ 连赢七局」
    ("单打选手打双打 他说靠的是正手", ["单打选手打双打", "他说靠的是正手"]),         # ruud-zverev
    ("有球迷说「今晚想当一次菲律宾人」", ["有球迷说", "「今晚想当一次菲律宾人」"]),   # 开引号前可断
    ("去年在停车场哭，今年二夺辛辛那提", ["去年在停车场哭，", "今年二夺辛辛那提"]),   # 标点后可断
    ("达维多维奇·福基纳赢球后的第一反应", ["达维多维奇·", "福基纳赢球后的第一反应"]),  # 「·」后可断
    ("脚踝崴了两周没喘过气她说的还是准备好了",                                     # 无处可断：劈字、不 balance
     ["脚踝崴了两周没喘过气她说的还", "是准备好了"]),
    ("「在蒙特利尔比在多伦多更开心」", ["「在蒙特利尔比在多伦多更开心", "」"]),       # 闭引号前不许断→劈
    ("赢下德约 他先谈的是没兑现的那十三个破发点",                                   # 第二块比栏宽→三行
     ["赢下德约", "他先谈的是没兑现的那十三个破", "发点"]),
    ("0-5 落后追回来 赢的是世界第 8", ["0-5 落后追回来 赢的是世界第 8"]),            # 849px，一行
]


@pytest.mark.parametrize(("point", "lines"), _CHROMIUM_LINES)
def test_排行和现在的卡片CSS真渲出来的一样(point, lines):
    assert [ln.strip() for ln in gates.card_lines(point)] == lines


def test_收尾卡那一句放不下一行就红_报出来的折点就是卡上的折点():
    with pytest.raises(SystemExit, match="空格／标点处折开，排成 2 行「首秀赢完球 ／ 他先谢看台上的费德勒」"):
        bic.check_takeaway(_card_spec("首秀赢完球 他先谢看台上的费德勒"))
    with pytest.raises(SystemExit, match="在字中间劈开，排成 2 行「脚踝崴了两周没喘过气她说的还 ／ 是准备好了」"):
        bic.check_takeaway(_card_spec("脚踝崴了两周没喘过气她说的还是准备好了"))


@pytest.mark.parametrize("point", ["赢完球 先谢看台上的费德勒", "被逼到绝境 他只是一直顶住"])
def test_收尾卡改短之后的那两版放得下(point, capsys):
    bic.check_takeaway(_card_spec(point))


def test_收尾卡认领两行要写为什么():
    spec = _card_spec("首秀赢完球 他先谢看台上的费德勒")
    spec["takeaway"]["close"]["_wrap_ok"] = "有意在空格处折成两行"
    bic.check_takeaway(spec)


def test_请求预检就拦收尾卡折行_不等自动链建完spec(monkeypatch):
    """review 那条：`production_preflight.check_request` 不查这一项，请求里写长了要等
    auto-render 把它建成 spec、picker 预检报红才知道，多一整趟循环。同一份判据，豁免表同样认。"""
    import production_preflight as pp

    copies = []
    monkeypatch.setattr(pp, "check_copy", lambda *a, **k: copies.append(a))
    long_req = {"slug": "new-one", "xhs": "正文",
                "takeaway": {"close": {"point": "首秀赢完球 他先谢看台上的费德勒"}}}
    with pytest.raises(pp.RequestNotReady, match="首秀赢完球 ／ 他先谢看台上的费德勒"):
        pp.check_request(long_req)
    assert not copies, "折行那一项应该排在文案检查之前就拦下"
    pp.check_request({**long_req, "takeaway": {"close": {"point": "赢完球 先谢看台上的费德勒"}}})
    legacy = sorted(gates.legacy("takeaway_point_wrap"))[0]
    pinned = gates.legacy_table("takeaway_point_wrap")["points"][legacy]["close"]
    # 豁免表里的老 slug、原句没动：和 render 一样放行
    pp.check_request({**long_req, "slug": legacy, "takeaway": {"close": {"point": pinned}}})
    with pytest.raises(ValueError, match="放不下一行"):     # 老 slug 换了一句照样超宽：不认
        pp.check_request({**long_req, "slug": legacy})
    pp.check_request({"slug": "no-card", "xhs": "正文"})     # 没写解读卡的请求不判
    assert len(copies) == 3


def test_请求预检拦比分输家视角和总分差():
    """批次 4 复审 BLOCKING：`check_request` 原来只跑 `check_taste`，比分赢家视角和另一半
    口味闸（总分差、赛点同义反复、正文 markdown）要等出片那一趟 `main()` 才拦——而
    `interview-auto-render` 在那之前已经用 GITHUB_TOKEN 把 spec 直推 main（CI 不跑），
    全库测试到下一个 PR 才红。拿真请求改一处复现，**真跑**文案检查（不打桩）。"""
    import production_preflight as pp

    req = json.loads((ROOT / "requests" / "interviews"
                      / "pegula-navarro-us-open-2026-qf-interview.json").read_text("utf-8"))
    pp.check_request(req)                                   # 原样过得了
    with pytest.raises(pp.RequestNotReady, match="输家视角"):
        pp.check_request({**req, "push": {**req["push"], "score": "6-3 4-6 3-6"}})
    with pytest.raises(pp.RequestNotReady, match="总分"):
        pp.check_request({**req, "cover": {**req["cover"], "title": ["总分只多2分", "佩古拉赢了"]}})


def test_一条请求没过前置检查_不让整个请求生成步骤红(monkeypatch, tmp_path, capsys):
    """review 那条：`check_request` 抛了，`build_interview_request --write` 原来退 1——
    interview-auto-render 里它后面的「配结尾／提交／dispatch」只挂着
    `if: steps.gate.outputs.work == 'true'`，隐式的 success() 把它们一起跳过，
    一条请求的解读卡写长了，别的 spec 的提交和 dispatch 每 10 分钟卡一趟。
    请求自己的错（确定性的）只留名单、报 warning；别的失败照旧让 step 红。"""
    import build_interview_request as bir
    import production_preflight as pp

    long_req = {"slug": "too-long", "xhs": "正文",
                "takeaway": {"close": {"point": "首秀赢完球 他先谢看台上的费德勒"}}}
    monkeypatch.setattr(pp, "check_copy", lambda *a, **k: None)
    built = []

    def one(path, chat, *, write):
        if path.stem == "too-long":
            pp.check_request(long_req)                     # 真闸，不是桩
        if path.stem == "net-down":
            raise RuntimeError("第一份 ASR 为空")
        built.append(path.stem)
        return path.stem, 3, 60.0
    monkeypatch.setattr(bir, "_build_one", one)
    paths = [tmp_path / f"{n}.json" for n in ("too-long", "ok")]
    assert bir.build_all(paths, None, write=True) == 0
    out = capsys.readouterr().out
    assert built == ["ok"], "没过前置检查的那条之后的请求照常建"
    assert "::warning::too-long.json" in out and "放不下一行" in out
    assert "::error::" not in out
    assert bir.build_all([tmp_path / "net-down.json", *paths], None, write=True) == 1, \
        "网络／ASR 那类失败照旧让这一步红"


def test_量卡片宽度和渲卡片用的是同一组常量(monkeypatch, tmp_path):
    """**一个数写两处必分叉**：改了卡片留白，闸得跟着变，渲出来的 CSS 也得跟着变。"""
    seen = {}
    monkeypatch.setattr(bic, "_shoot", lambda html, dest: seen.setdefault("html", html))
    monkeypatch.setattr(bic, "TAKEAWAY_PAD_LEFT", 81)
    monkeypatch.setattr(bic, "TAKEAWAY_PAD_RIGHT", 200)
    monkeypatch.setattr(bic, "TAKEAWAY_POINT_TRACKING", 1.5)
    bic.build_takeaway_card(_card_spec("一句话"), "close", tmp_path / "x.png")
    assert "padding:206px 200px 150px 81px" in seen["html"]
    assert f"font-size:{bic.TAKEAWAY_POINT_PX}px" in seen["html"]
    assert "letter-spacing:1.5px" in seen["html"]
    assert gates.point_box_px() == bic.CANVAS_W - 81 - 200


def test_新的收尾卡都放得下一行():
    """存量也扫：豁免只认钉住的那一句（`points`），不再按 slug 整条跳过。"""
    bad = _judged("新的收尾卡都放得下一行",
                  [(s, p) for s in _corpus() for p in gates.takeaway_point_problems(s)])
    assert not bad, "\n".join(bad)


def test_收尾卡折行豁免钉在原句上_老slug改写成另一句照样超宽就红():
    """review 那条：豁免原来只按 slug 认——已发的那张卡改写成另一句、照样超一行，
    也静静放行，「只许减不许加」只管住了名字没管住内容。`frozen_tail_short` 钉 `end`，
    这张表钉 `point`。"""
    slug = sorted(gates.legacy("takeaway_point_wrap"))[0]
    pinned = gates.legacy_table("takeaway_point_wrap")["points"][slug]["close"]
    assert gates.takeaway_point_problems(_card_spec(pinned, slug)) == []
    rewritten = _card_spec("落后一盘又被破发 他说只是一直顶住", slug)
    assert any("直顶住" in p for p in gates.takeaway_point_problems(rewritten))
    with pytest.raises(SystemExit, match="直顶住"):
        bic.check_takeaway(rewritten)
    other_card = _card_spec(pinned, slug)
    other_card["takeaway"] = {"open": other_card["takeaway"]["close"]}
    assert gates.takeaway_point_problems(other_card), "钉的是哪张卡也要对得上"


def test_收尾卡折行豁免表只许减不许加_名字要真的存在且真的还放不下():
    legacy = gates.legacy("takeaway_point_wrap")
    assert legacy, "豁免表读不到——路径或键名写错了，整条判据会静静失效"
    assert len(legacy) <= 62, "只许减不许加：新片子的收尾卡要收到一行放得下"
    seen = {s["slug"]: s for s in _corpus()}
    missing = sorted(s for s in legacy if s not in seen)
    box = gates.point_box_px()
    fixed = sorted(
        s for s in legacy if s in seen
        and not any(gates.point_width(str(c.get("point") or "")) > box
                    for c in (seen[s].get("takeaway") or {}).values()
                    if isinstance(c, dict)))
    assert not missing, f"豁免表里有不存在的 slug（写错了就是一盏恒真的绿灯）：{missing}"
    assert not fixed, f"这些已经放得下一行了，从 data/legacy_interview_gates.json 删掉：{fixed}"
    points = gates.legacy_table("takeaway_point_wrap").get("points") or {}
    assert set(points) == set(legacy), \
        f"`points` 和 `slugs` 要一一对应：多 {sorted(set(points) - legacy)}、缺 {sorted(legacy - set(points))}"
    stale = sorted(f"{s}.{w}" for s, cards in points.items() if s in seen
                   for w, text in cards.items()
                   if str(((seen[s].get("takeaway") or {}).get(w) or {}).get("point")) != text)
    assert not stale, f"钉住的原句和 spec 对不上了（改过就不是存量，删掉这一条）：{stale}"


# ── 二、顶栏比分是赢家视角 ───────────────────────────────────────────────


def _score_spec(score: str, winner: str = "莱巴金娜") -> dict:
    return {"slug": "new-one", "winner": winner, "push": {"score": score}}


def test_顶栏比分写成输家视角就红():
    # zheng-rybakina-us-open-2026-qf-presser 857f1fbc 之前那一版
    with pytest.raises(SystemExit, match="输家视角"):
        bic.check_score_orientation(_score_spec("6-3 1-6 4-6"))
    bic.check_score_orientation(_score_spec("3-6 6-1 6-4"))
    bic.check_score_orientation(_score_spec("7-6(5) 6-7(3) 10-8"))      # 抢十盘也算完赛盘
    bic.check_score_orientation(_score_spec("6-3 2-1 Ret."))            # 退赛不判
    claimed = _score_spec("6-3 1-6 4-6")
    claimed["_score_orientation_why"] = "特殊赛制"
    bic.check_score_orientation(claimed)


@pytest.mark.parametrize(("score", "red"), [
    # 抢七注脚写全了：第一版只剥 `(\d+)`，`5-7` 被数成赢家丢的一盘，2:2 误红
    ("6-7(5-7) 6-4 6-4", False),
    ("6-7（5-7） 6-4 6-4", False),              # 全角括号
    ("7-6(10-8) 3-6 6-2", False),
    ("6-4 3-6 1-0(10-8)", False),               # 抢十代替决胜盘记成 1-0(10-8)
    ("6-4 3-6 [10-8]", False),                  # 方括号的抢十盘算一盘
    ("6-4 3-6 1-0[10-8]", False),               # 贴着 1-0 的方括号＝抢十盘，同 1-0(10-8)
    ("6-4 6-7(3) [10-8]", False),               # 抢七输掉的一盘后面单独一格的抢十盘
    # review 那条：贴在一盘后面的方括号是抢七注脚，原来被数成一盘 → 2:2 误红
    ("6-7[5-7] 6-4 6-4", False),
    ("6-7 [5-7] 6-4 6-4", False),               # 单独一格但到不了 10 分：只能是抢七小分
    ("6-7[5-7] 4-6", True),
    # 复审 nit：抢十盘直接贴在前一盘后面——前一盘不是抢七盘，这个方括号就是一盘，不是注脚
    ("6-4 3-6[10-8]", False),
    ("6-4 3-6[8-10]", True),
    ("7-6[7-5] 6-4", False),                    # 贴着抢七盘的仍是注脚
    ("6-4 3-6 [8-10]", True),                   # 抢十盘输了照样算输家视角
    ("6-7(5-7) 4-6", True),                     # 注脚剥干净之后输家视角照样红
    ("7-6(7-5) 3-6 6-7(4-7)", True),
    # 复审第三轮 nit：冒号写法同一套——贴着抢七盘的方括号到 10 分也是注脚（抢七可以打到 10-8）
    ("6:7[8:10] 6:4 6:4", False),
    ("7:6[10:8] 6:4", False),
    ("6:7[8:10] 4:6", True),
])
def test_抢七注脚整个剥掉_不许被当成另一盘(score, red):
    problem = gates.score_orientation_problem(_score_spec(score))
    assert bool(problem) is red, (score, problem, gates.completed_sets(score))


def test_全库顶栏比分都是赢家视角():
    bad = _judged("全库顶栏比分都是赢家视角",
                  [(s, p) for s in _corpus() if (p := gates.score_orientation_problem(s))])
    assert not bad, "\n".join(bad)


def test_顶栏比分那道闸坐在渲染入口_下载之前就红(tmp_path, monkeypatch, capsys):
    """不查源码文本，真跑 `main()`：L0 放行之后，比分方向错的 spec 在出片那几档第一步就退出，
    一个网络调用都不发。⚠️ 只交转写判定的那两档（subs／verify）只报不拦（2026-09-28 D2：
    比分方向不碰转写指纹，subs 要能和改文案、挑封面并行跑）——报还是要报。"""
    spec = _score_spec("6-3 1-6 4-6")
    spec.update({"url": "https://example.invalid/x", "start": 0, "end": 10,
                 "event": "2026 美网 1/4决赛"})
    path = tmp_path / "s.json"
    path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(bic, "check_source_contract", lambda s: "ok")
    monkeypatch.setattr(bic, "OUTDIR", tmp_path / "out")
    for name in ("storyboard_sheet", "fetch_words", "yt_download"):
        monkeypatch.setattr(bic, name, lambda *a, **k: pytest.fail("比分那道闸没拦住，已经走到下载"))
    for stage in ("render", "cover"):
        monkeypatch.setattr(sys, "argv", ["x", "--spec", str(path), "--stage", stage])
        with pytest.raises(SystemExit, match="输家视角"):
            bic.main()

    class Reached(Exception):
        pass

    def reached(*a, **k):
        raise Reached
    monkeypatch.setattr(bic, "storyboard_sheet", reached)
    monkeypatch.setattr(sys, "argv", ["x", "--spec", str(path), "--stage", "subs"])
    with pytest.raises(Reached):
        bic.main()
    assert "输家视角" in capsys.readouterr().out, "subs 那一档不拦，可红还要印出来"


# ── 三、离线预检：出片那一趟必红的，dispatch 之前在本地报 ─────────────────


def _full_spec(monkeypatch, tmp_path) -> dict:
    """一条能过出片那一趟全部 spec 闸的最小合成采访，外加仓库外的字幕缓存。"""
    from interview_source_gate import finalize_source_contract

    spec = finalize_source_contract({
        "slug": "preflight-fixture",
        "url": "https://example.test/oncourt",
        "requested_content_type": "on_court",
        "interview_kind": "赛后场上采访",
        "source_verification": {
            "status": "verified", "detected_type": "on_court",
            "method": "human_visual_verdict",
            "source_url": "https://example.test/oncourt",
            "evidence": [{"kind": "visual_verdict", "by": "test"}],
        },
        "match": {"id": "2026:test:qf:preflight-fixture", "event": "测试赛",
                  "round": "1/4决赛", "winner": "莱巴金娜", "loser": "郑钦文",
                  "participants": ["莱巴金娜", "郑钦文"]},
        "opening": {"kind": "match_end", "lead_in": 10.0,
                    "why": "正文源开头含同场赛点和现场解说"},
        "start": 0.0, "end": 6.0, "asr_model": "small.en",
        "event": "2026 美网 1/4决赛", "winner": "莱巴金娜",
        "push": {"matchup": "郑钦文 vs 莱巴金娜", "score": "3-6 6-1 6-4"},
        "zh": ["非常感谢大家", "这是一场精彩的比赛"],
        "transcript_verified": True,
        "takeaway": {"close": {"point": "赢完球 先谢看台", "ask": "你怎么看？"}},
        "cover": {"frame_at": 1.0},
    })
    out = tmp_path / "output" / "interviews"
    (out / spec["slug"]).mkdir(parents=True)
    words = [(1.0, "Thank"), (1.3, "you"), (1.6, "so"), (1.9, "much."),
             (4.0, "It"), (4.3, "was"), (4.6, "a"), (4.9, "great"), (5.2, "match")]
    (out / spec["slug"] / "cap_asr.json3").write_text(json.dumps({"events": [
        {"tStartMs": int(t * 1000), "dDurationMs": 250, "segs": [{"utf8": w}]}
        for t, w in words]}), encoding="utf-8")
    monkeypatch.setattr(pf, "OUTPUT", out)
    # 文案页那道闸查的是仓库里的 `.xhs.txt`，合成的 slug 没有；它有自己的判据
    monkeypatch.setattr(bic, "check_copy_page", lambda spec: None)
    return spec


def test_预检全绿的合成采访(monkeypatch, tmp_path):
    spec = _full_spec(monkeypatch, tmp_path)
    problems, _notes = pf.spec_problems(spec, copy=False)
    assert problems == [], problems


def test_全量预检也按已提交的封面扫描记录拦frame_at(monkeypatch, tmp_path):
    """rework_audit_0928：封面帧那一类在 dispatch 之前一道都没有，9 趟全是装完依赖、下完
    源片才红。记录（`mode=cover` 提交的、render 自动换帧提交的）已经说了哪一格不行，
    就在 dispatch 之前红，并把能直接换的那一格报出来。全量和探针两条路都要有。"""
    import interview_cover_scan as scan

    spec = _full_spec(monkeypatch, tmp_path)
    # 机器能换的那一格还得是文案点了名的人（`interview_cover_scan.named_in_copy`）
    spec["cover"]["tag"] = "2026 美网 · 莱巴金娜"
    block = {"status": "ok", "identity": {"verdict": "match", "name": "莱巴金娜",
                                          "similarity": {"莱巴金娜": 0.6}, "missing": [],
                                          "face_px": 300.0},
             "eyes": {"verdict": "open", "ear": 0.3, "face_px": 300.0}}
    entries = [{"frame_at": 1.0, "status": "fail", "issues": ["只检出 1 只眼"],
                "face": None, "margin": 2.0, "face_model": block},
               {"frame_at": 1.2, "status": "pass", "issues": [], "face": None,
                "margin": 3.0, "face_model": block}]
    # 记录的窗口（0.5–2.5）不是 render 现在会扫的那一段（frame_at 前后各 2 秒＝0–3）：
    # 判不准 render 扫不扫得到 1.2，拦下来、报出那一格
    record = scan.build_record(spec, (0.5, 2.5), 0.2, entries)
    path = pf.OUTPUT / spec["slug"] / scan.RECORD_NAME
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    problems, _ = pf.spec_problems(spec, copy=False)
    hit = [p for p in problems if p.startswith("_check_cover_scan")]
    assert len(hit) == 1 and "没过闸" in hit[0] and "1.2 秒" in hit[0], problems
    # 同一段、同一个间隔（D3）：render 红了会自动换上 1.2——不拦，提示里说一声
    path.write_text(json.dumps(scan.build_record(spec, (0.0, 3.0), 0.2, entries),
                               ensure_ascii=False), encoding="utf-8")
    problems, notes = pf.spec_problems(spec, copy=False)
    assert problems == [] and any("1.2 秒" in n and "render" in n for n in notes), (problems, notes)
    spec["cover"]["frame_at"] = 1.2
    assert pf.spec_problems(spec, copy=False)[0] == []


@pytest.mark.parametrize(("mutate", "expect"), [
    (lambda s: s["zh"].pop(), "对不上"),                                      # 117:114 那种
    (lambda s: s["zh"].__setitem__(0, "非" * 20), "中文超宽"),
    (lambda s: s["zh"].__setitem__(1, "这是一场精彩的"), "吊在"),   # 那一行英文没收在句号上
    (lambda s: s["push"].__setitem__("score", "6-3 1-6 4-6"), "输家视角"),
    (lambda s: s["takeaway"]["close"].__setitem__(
        "point", "落后一盘又被破发 他说只是一直顶住"), "直顶住"),
    # review 那条：`main()` 开头那排里有 `check_cover_hook`，手抄的闸表漏了它
    (lambda s: s["cover"].update(title=["赢完球", "先谢看台"], hook_accent="不在标题里的词"),
     "出现了 0 次"),
    # runner「发布文案前置检查」那一步的全称断言闸（main #1112 起）
    (lambda s: s["push"].__setitem__("lead", "他此前六次打进正赛，六次全部首轮出局。"),
     "全称断言"),
    # `main()` 在套 `en_fixed` 之前先查行号错位：0 起写成 1 起，第 2 行挂上了第 1 行的话
    (lambda s: s.__setitem__("en_fixed", {"2": "Thank you so much."}), "挂错了行"),
])
def test_预检把runner上必红的spec错在本地报出来(monkeypatch, tmp_path, mutate, expect):
    spec = _full_spec(monkeypatch, tmp_path)
    mutate(spec)
    problems, _ = pf.spec_problems(spec, copy=False)
    assert any(expect in p for p in problems), problems


def _leading_checks(fn_name: str) -> list[str]:
    """`build_interview_clip.<fn_name>` 函数体里**第一排连着的** `check_*(spec)` 调用。

    `main()` 里 L0 之后那一排包在一个 `try` 里（转写那几档只报不拦，2026-09-28 D2）——
    `try` 的正文照样算这一排，跳过它就只抠得到 L0 一道。"""
    import ast

    tree = ast.parse((ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == fn_name)
    out: list[str] = []
    flat: list[ast.stmt] = []
    for stmt in fn.body:
        flat += stmt.body if isinstance(stmt, ast.Try) else [stmt]
    for stmt in flat:
        call = stmt.value if isinstance(stmt, ast.Expr) else None
        name = (call.func.id if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                else "")
        if name.startswith("check_"):
            assert [ast.unparse(a) for a in call.args] == ["spec"] and not call.keywords, \
                f"{fn_name}() 里的 {name} 不再只吃 spec——预检跑不了它，要重新想"
            out.append(name)
        elif out:
            break
    return out


def test_预检的闸和出片那一趟main开头那一排是同一份():
    """review 那条：`_spec_gates` 是手抄的，`main()` 开头那排早就有 `check_cover_hook`
    （8f7bbd94 起），闸表里却没有——`hook_accent` 不在标题里，预检和探针都绿，runner
    第一秒红，stale 规则每 70 分钟再投一次。**按 ast 从 `main()`／`render()` 抠出来比**，
    两边再也分不了叉；排在最前面的是 runner「发布文案前置检查」那一步的全称断言闸。"""
    import production_preflight as pp

    main_checks = _leading_checks("main")
    assert len(main_checks) >= 8 and "check_cover_hook" in main_checks, \
        f"扫描面坏了：main() 开头只抠到 {main_checks}"
    expected = main_checks + _leading_checks("render")
    got = pf._spec_gates(bic)
    assert got[0] is pp.check_interview_spec_claims
    assert [g.__name__ for g in got[1:]] == expected
    assert all(getattr(bic, g.__name__) is g for g in got[1:])


def test_探针不要PIL也拦得住封面重点词和全称断言(monkeypatch, tmp_path):
    """两道都只读 spec、只要标准库——探针那台系统 python3 上照样判得出红，不许记成判不了。"""
    spec = _full_spec(monkeypatch, tmp_path)
    _no_pil(monkeypatch)
    spec["cover"].update(title=["赢完球", "先谢看台"], hook_accent="不在标题里的词")
    spec["push"]["lead"] = "他此前六次打进正赛，六次全部首轮出局。"
    red, unknown = pf.probe_problems(spec)
    assert any(r.startswith("check_cover_hook") for r in red), red
    assert any(r.startswith("check_interview_spec_claims") for r in red), red
    assert not any(u.startswith(("check_cover_hook", "check_interview_spec_claims"))
                   for u in unknown), unknown


def test_预检的文案项和runner同一条命令_tag超过五个就红(monkeypatch, tmp_path):
    spec = _full_spec(monkeypatch, tmp_path)
    specs = tmp_path / "specs"
    specs.mkdir()
    spec["push"]["summary"] = "莱巴金娜逆转郑钦文"
    (specs / f"{spec['slug']}.json").write_text(json.dumps(spec, ensure_ascii=False),
                                                encoding="utf-8")
    body = "第一行\n\n正文。\n\n" + " ".join(f"#标签{i}" for i in range(6))
    (specs / f"{spec['slug']}.xhs.txt").write_text(body, encoding="utf-8")
    monkeypatch.setattr(pf, "SPECS", specs)
    assert "tag" in (pf.copy_problem(spec["slug"], "2026-09-27") or "")
    (specs / f"{spec['slug']}.xhs.txt").write_text(body.rsplit(" ", 1)[0], encoding="utf-8")
    assert pf.copy_problem(spec["slug"], "2026-09-27") is None


def test_预检不往stdout漏字_那是dispatch名单(monkeypatch, tmp_path, capsys):
    """`pick_interview_renders` 的 stdout 第二行起是 dispatch 名单——闸里打印的
    `[解读卡] 自有画面…`、切行的「并短句」漏出来一行，就是把废话当 slug 投出去。"""
    spec = _full_spec(monkeypatch, tmp_path)
    spec["zh"].pop()
    pf.spec_problems(spec, copy=False)
    assert capsys.readouterr().out == ""


def test_预检红的spec不dispatch_进等待名单(monkeypatch, tmp_path):
    import pick_interview_renders as pick
    import interview_preflight

    spec = {"slug": "x"}
    monkeypatch.setattr(pick, "validate_source_contract", lambda s: None)
    monkeypatch.setattr(pick, "check_lead_in", lambda s: None)
    monkeypatch.setattr(pick, "SPECS", tmp_path)
    (tmp_path / "x.xhs.txt").write_text("文案", encoding="utf-8")
    spec.update({"opening": {"kind": "none"}, "zh": ["a"], "transcript_verified": True,
                 "takeaway": {"close": {}}, "cover": {"frame_at": 1}})
    monkeypatch.setattr(interview_preflight, "spec_problems",
                        lambda s, **kw: (["check_takeaway：卡上折成两行\n第二行"], []))
    assert pick.missing_for_render("x", spec) == ["预检：check_takeaway：卡上折成两行"]


def test_预检判不了就抛_不许当成判过了(monkeypatch):
    monkeypatch.setattr(bic, "_FONT_FILES", {"zh": ("/nonexistent/font.ttc", "fonts-noto-cjk")})
    with pytest.raises(pf.PreflightUnavailable):
        pf.spec_problems({"slug": "x"}, copy=False)


def _no_pil(monkeypatch):
    """模拟 interview-auto-render 探针那台系统 python3：`import PIL` 必抛 ImportError。"""
    monkeypatch.setitem(sys.modules, "PIL", None)
    monkeypatch.setattr(gates, "_POINT_FONT_CACHE", {})


def test_探针缺PIL时只跑不要量宽度的那几道_量宽度的记成判不了(monkeypatch, tmp_path):
    """review 那条：runner 的系统 python3 没有 PIL，`spec_problems` 在探针里一律抛——
    一条卡在量宽度上的红 spec 就每 10 分钟逼一次全量 job。`probe_problems` 不抛：
    不要 PIL 的闸照跑（红了就是红），要 PIL 的几项**说出来是判不了**。"""
    spec = _full_spec(monkeypatch, tmp_path)
    _no_pil(monkeypatch)
    with pytest.raises(pf.PreflightUnavailable):
        pf.spec_problems(spec, copy=False)
    red, unknown = pf.probe_problems(spec)
    assert red == [], red
    assert any(u.startswith("check_takeaway") for u in unknown), unknown
    assert set(pf.NEEDS_RENDER_ENV) <= set(unknown)
    spec["push"]["score"] = "6-3 1-6 4-6"                  # 不要 PIL 的闸：照样红
    red, _ = pf.probe_problems(spec)
    assert any(r.startswith("check_score_orientation") for r in red), red


def _probe_picker(monkeypatch, tmp_path):
    import interview_preflight
    import pick_interview_renders as pick

    specs = tmp_path / "specs"
    specs.mkdir()
    monkeypatch.setattr(pick, "SPECS", specs)
    monkeypatch.setattr(pick, "OUTPUT", tmp_path / "output")
    monkeypatch.setattr(pick, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(pick, "_rendered_slugs", lambda: set())
    monkeypatch.setattr(pick, "validate_source_contract", lambda s: None)
    monkeypatch.setattr(pick, "check_lead_in", lambda s: None)
    monkeypatch.setattr(pick, "VERDICT_CACHE", tmp_path / "cache" / "verdicts.json")
    monkeypatch.setattr(pick, "_VERDICTS", None)
    monkeypatch.setattr(pick, "_VERDICTS_DIRTY", False)
    monkeypatch.setattr(pick, "_UNKNOWN", [])
    spec = {"slug": "p", "opening": {"kind": "none"}, "zh": ["a"], "transcript_verified": True,
            "takeaway": {"close": {"point": "x"}}, "cover": {"frame_at": 1}}
    (specs / "p.json").write_text(json.dumps(spec), encoding="utf-8")
    (specs / "p.xhs.txt").write_text("文案", encoding="utf-8")
    return pick, interview_preflight, specs


def test_探针拿上一趟全量预检的结论顶判不了的那几项_输入一变就作废(monkeypatch, tmp_path):
    pick, ipf, specs = _probe_picker(monkeypatch, tmp_path)
    # ① 全量那一趟（dispatch 那一步）：判红，记进缓存
    monkeypatch.setattr(ipf, "spec_problems",
                        lambda s, **kw: (["check_takeaway：卡上折成两行\n折点"], []))
    ready, waiting = pick.todo_slugs()
    assert ready == [] and waiting == [("p", ["预检：check_takeaway：卡上折成两行"])]
    pick.save_verdicts()
    assert pick.VERDICT_CACHE.is_file()

    # ② 下一趟探针（新进程、系统 python3 没有 PIL）：同一份输入 → 拿缓存的结论，不逼全量
    def unavailable(s, **kw):
        raise ipf.PreflightUnavailable("缺 PIL")
    monkeypatch.setattr(ipf, "spec_problems", unavailable)
    monkeypatch.setattr(ipf, "probe_problems", lambda s: ([], ["check_takeaway（缺 PIL）"]))
    monkeypatch.setattr(pick, "PROBE", True)
    monkeypatch.setattr(pick, "_VERDICTS", None)
    ready, waiting = pick.todo_slugs()
    assert ready == [], "同一份输入全量判过是红的，探针不许再把它算成待投（那就是每 10 分钟一趟全量）"
    assert waiting and "上一趟全量预检" in waiting[0][1][0]

    # ③ spec 改了一个字节：结论作废，判不了 → 算待投，交给全量那一趟
    (specs / "p.json").write_text(json.dumps({**json.loads((specs / "p.json").read_text()),
                                              "zh": ["b"]}), encoding="utf-8")
    ready, waiting = pick.todo_slugs()
    assert ready == ["p"] and waiting == []
    assert pick._UNKNOWN == ["p"]

    # ④ 不要 PIL 的那几道红了，就是红——不看缓存
    monkeypatch.setattr(ipf, "probe_problems", lambda s: (["check_score_orientation：输家视角"], []))
    assert pick.missing_for_render("p", json.loads((specs / "p.json").read_text())) == [
        "预检：check_score_orientation：输家视角"]


def test_全量模式判不了照旧抛_只有探针才降级(monkeypatch, tmp_path):
    pick, ipf, specs = _probe_picker(monkeypatch, tmp_path)

    def unavailable(s, **kw):
        raise ipf.PreflightUnavailable("缺 PIL")
    monkeypatch.setattr(ipf, "spec_problems", unavailable)
    with pytest.raises(ipf.PreflightUnavailable):
        pick.todo_slugs()


def test_冷开场字幕要量宽度的那道在探针里同样记成判不了(monkeypatch, tmp_path):
    """review 那条的括号里：带 `lead_in` 的 spec 原来在便宜那几项（`check_lead_in` 量双语
    字幕宽度）就撞上缺 PIL，整个 picker 抛出去——探针同样只能「逼一趟全量」。"""
    pick, ipf, specs = _probe_picker(monkeypatch, tmp_path)

    def needs_pil(s):
        raise ModuleNotFoundError("No module named 'PIL'")
    monkeypatch.setattr(pick, "check_lead_in", needs_pil)
    with pytest.raises(ImportError):                 # 全量模式：判不了照旧抛
        pick.todo_slugs()
    monkeypatch.setattr(pick, "check_lead_in", lambda s: None)
    monkeypatch.setattr(ipf, "spec_problems", lambda s, **kw: ([], []))
    assert pick.todo_slugs() == (["p"], [])          # 全量判过：绿，记下来
    monkeypatch.setattr(pick, "check_lead_in", needs_pil)
    monkeypatch.setattr(ipf, "probe_problems", lambda s: ([], []))
    monkeypatch.setattr(pick, "PROBE", True)
    assert pick.todo_slugs() == (["p"], []) and pick._UNKNOWN == [], "输入没变：用全量的绿"


def test_预检结论缓存的键跟着预检实际读的字幕走_工作区有目录就认工作区(monkeypatch, tmp_path):
    """review 那条：`verdict_key` 原来按 `git ls-files`（index）记字幕，而 `_materialize_captions`
    工作区有目录就**只**读工作区——auto-render 把待处理请求的产物格加回稀疏范围、只提交
    `cap_asr.json3`，全量判的是没提交的 `cap_*`，记下的键却是下一趟 HEAD 原样复现的。"""
    pick, ipf, specs = _probe_picker(monkeypatch, tmp_path)
    out = tmp_path / "output" / "interviews"
    monkeypatch.setattr(ipf, "OUTPUT", out)
    monkeypatch.setattr(pick, "_code_fingerprint", lambda: "code")
    from_head = pick.verdict_key("p")               # 没有目录：按 HEAD（这个 slug 在 HEAD 里没字幕）
    assert from_head is not None
    (out / "p").mkdir(parents=True)
    (out / "p" / "cap_asr.json3").write_text('{"events": []}', encoding="utf-8")
    (out / "p" / "notes.md").write_text("不是字幕", encoding="utf-8")
    k1 = pick.verdict_key("p")
    (out / "p" / "cap_abc.en.json3").write_text('{"events": [1]}', encoding="utf-8")  # 没提交的字幕
    k2 = pick.verdict_key("p")
    (out / "p" / "cap_asr.json3").write_text('{"events": [2]}', encoding="utf-8")    # 工作区改了一份
    k3 = pick.verdict_key("p")
    assert len({from_head, k1, k2, k3}) == 4, "预检读的字幕变了，键必须跟着变"
    # 键里记的就是预检会放进去的那几份，一份不多一份不少
    work = tmp_path / "materialized"
    work.mkdir()
    assert ipf._materialize_captions("p", work)
    assert [c.split(":")[0] for c in ipf.caption_fingerprint("p")] == \
        sorted(q.name for q in work.iterdir())


def test_字幕指纹和HEAD同一个blob算法_内容没变不多逼一趟全量(monkeypatch, tmp_path):
    data = b'{"events": [{"tStartMs": 1}]}'
    blob = subprocess.run(["git", "hash-object", "--stdin"], input=data, capture_output=True,
                          check=True).stdout.decode().strip()
    assert pf._blob_id(data) == blob
    # 真仓库里挑一条 HEAD 有字幕的：从 HEAD 放进工作区之后，两个分支给出同一份指纹
    listing = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", "HEAD",
                              "--", "output/interviews/"], capture_output=True, text=True).stdout
    slug = next((ln.split("/")[2] for ln in listing.splitlines()
                 if ln.rsplit("/", 1)[-1].startswith("cap_")), None)
    if slug is None:
        pytest.skip("HEAD 里没有采访字幕缓存")
    monkeypatch.setattr(pf, "OUTPUT", tmp_path / "nowhere")
    head = pf.caption_fingerprint(slug)
    assert head
    (tmp_path / "out" / slug).mkdir(parents=True)
    assert pf._materialize_captions(slug, tmp_path / "out" / slug)
    monkeypatch.setattr(pf, "OUTPUT", tmp_path / "out")
    assert pf.caption_fingerprint(slug) == head


def test_工具崩了的红不记进预检缓存_下一趟探针交给全量重判(monkeypatch, tmp_path):
    """review 那条：`push_reel` 子进程偶发崩一次，全量记成红，探针就拿它当「同一份输入
    判过是红的」一直重放到北京日期翻过去——那条采访一整天不投。"""
    pick, ipf, specs = _probe_picker(monkeypatch, tmp_path)
    monkeypatch.setattr(ipf, "spec_problems", lambda s, **kw: ([], []))
    assert pick.todo_slugs() == (["p"], [])          # ① 全量判绿，记下来
    crash = f"文案（push_reel --stage check）{ipf.CRASHED}：KeyError: 'x'"
    monkeypatch.setattr(ipf, "spec_problems", lambda s, **kw: ([crash], []))
    ready, waiting = pick.todo_slugs()               # ② 同一份输入，这一趟工具崩了
    assert ready == [] and waiting, "崩了的这一趟照旧不投"
    pick.save_verdicts()
    saved = json.loads(pick.VERDICT_CACHE.read_text(encoding="utf-8"))
    assert "p" not in saved, "崩溃不是判据的结论，不许记（连前一趟的绿也作废）"

    def unavailable(s, **kw):
        raise ipf.PreflightUnavailable("缺 PIL")
    monkeypatch.setattr(ipf, "spec_problems", unavailable)
    monkeypatch.setattr(ipf, "probe_problems", lambda s: ([], ["check_takeaway（缺 PIL）"]))
    monkeypatch.setattr(pick, "PROBE", True)
    monkeypatch.setattr(pick, "_VERDICTS", None)
    assert pick.todo_slugs() == (["p"], []) and pick._UNKNOWN == ["p"], "③ 探针判不了，交给全量"


def test_文案那一项分得清判据红和工具崩(monkeypatch):
    import production_preflight

    def fail(stderr):
        def run(*a, **k):
            raise subprocess.CalledProcessError(1, ["push_reel"], output="", stderr=stderr)
        return run
    monkeypatch.setattr(production_preflight, "check_copy",
                        fail("Traceback (most recent call last):\n  File \"x\"\nKeyError: 'x'"))
    assert pf.CRASHED in (pf.copy_problem("x", "2026-09-27") or "")
    monkeypatch.setattr(production_preflight, "check_copy", fail("tag 超过 5 个（6）"))
    verdict = pf.copy_problem("x", "2026-09-27") or ""
    assert "tag" in verdict and pf.CRASHED not in verdict


def test_探针里量宽度撞上缺字体的OSError也算判不了_不是红(monkeypatch, tmp_path):
    """review 那条：探针排在 apt 装 fonts-noto-cjk 之前。哪天系统 python3 带上了 PIL，
    `check_trail_in`／`check_lead_in` 量双语宽度撞的就是「中文字体不在」的 OSError——
    记成红就是一次「没活就早退」的假早退。全量模式不放宽（`_require_env` 先查过字体）。"""
    spec = _full_spec(monkeypatch, tmp_path)

    def no_font(*a, **k):
        raise OSError("cannot open resource")
    monkeypatch.setattr(bic, "check_trail_in", no_font)
    red, unknown = pf.probe_problems(spec)
    assert red == [], red
    assert any("cannot open resource" in u for u in unknown), unknown
    err, _ = pf._run_gate(no_font, spec)
    assert err and "OSError" in err, "全量模式：OSError 照旧记红"

    pick, ipf, specs = _probe_picker(monkeypatch, tmp_path)
    monkeypatch.setattr(pick, "check_lead_in", no_font)

    def unavailable(s, **kw):
        raise ipf.PreflightUnavailable("缺字体")
    monkeypatch.setattr(ipf, "spec_problems", unavailable)
    monkeypatch.setattr(ipf, "probe_problems", lambda s: ([], []))
    with pytest.raises(OSError):                     # 全量模式：判不了照旧抛
        pick.todo_slugs()
    monkeypatch.setattr(pick, "PROBE", True)
    assert pick.todo_slugs() == (["p"], []) and pick._UNKNOWN == ["p"], \
        "探针：冷开场那道判不了——不崩、不记红，交给全量"


def test_预检结论同样的内容写出同样的字节(monkeypatch, tmp_path):
    """工作流按文件指纹判「结论有变才另存一份缓存」——插入顺序不同也要写出同样的字节。"""
    import pick_interview_renders as pick

    monkeypatch.setattr(pick, "VERDICT_CACHE", tmp_path / "v.json")
    written = []
    for rows in ({"a": {"key": "1", "missing": []}, "b": {"key": "2", "missing": ["x"]}},
                 {"b": {"key": "2", "missing": ["x"]}, "a": {"key": "1", "missing": []}}):
        monkeypatch.setattr(pick, "_VERDICTS", rows)
        monkeypatch.setattr(pick, "_VERDICTS_DIRTY", True)
        pick.save_verdicts()
        written.append(pick.VERDICT_CACHE.read_bytes())
    assert written[0] == written[1]


def test_auto_render的探针带probe_预检结论缓存前后两步路径对得上():
    import yaml

    wf = yaml.safe_load((ROOT / ".github/workflows/interview-auto-render.yml").read_text(
        encoding="utf-8"))
    steps = wf["jobs"]["auto"]["steps"]
    names = [st.get("name", "") for st in steps]
    gate = steps[names.index("没活就早退")]
    assert "pick_interview_renders.py --probe" in gate["run"]
    restore = [i for i, st in enumerate(steps) if st.get("uses") == "actions/cache/restore@v4"
               and "tennislive-preflight" in str((st.get("with") or {}).get("path"))]
    save = [i for i, st in enumerate(steps) if st.get("uses") == "actions/cache/save@v4"
            and "tennislive-preflight" in str((st.get("with") or {}).get("path"))]
    dispatch = next(i for i, n in enumerate(names) if n.startswith("dispatch 未 render"))
    assert restore and restore[0] < names.index("没活就早退"), "探针之前要先取回上一趟的结论"
    assert save and save[0] > dispatch, "全量那一趟判完（dispatch 那一步）才存"
    assert "always()" in str(steps[save[0]].get("if")), "dispatch 那步红了也要存下已判的结论"
    # review 那条：键带 run_id、一趟存一份——有草稿时每 10 分钟一趟全量，一天 144 条一样的缓存。
    # 结论有变才存；键**仍然**带 run_id（写入后不可覆盖：按内容或日期定键，A→B→A 那一下存不进去，
    # restore-keys 取回的「最新一份」就成了 B）。
    changed = next(i for i, st in enumerate(steps) if st.get("id") == "verdicts")
    assert dispatch < changed < save[0]
    assert "steps.verdicts.outputs.changed == 'true'" in str(steps[save[0]].get("if"))
    assert "verdicts_sha" in gate["run"].split("pick_interview_renders.py --probe")[0], \
        "取回的那份的指纹要在探针之前记下"
    assert "steps.gate.outputs.verdicts_sha" in steps[changed]["run"]
    assert "always()" in str(steps[changed].get("if"))
    assert "github.run_id" in steps[save[0]]["with"]["key"]
    import pick_interview_renders as pick
    cache_dir = steps[restore[0]]["with"]["path"].replace("~", str(Path.home()))
    assert Path(cache_dir) in pick.VERDICT_CACHE.parents or \
        str(pick.VERDICT_CACHE).startswith(cache_dir), (pick.VERDICT_CACHE, cache_dir)


def test_采访工作流在取字幕之前跑离线预检():
    import yaml

    steps = yaml.safe_load((ROOT / ".github/workflows/interview-clip.yml").read_text(
        encoding="utf-8"))["jobs"]
    steps = next(iter(steps.values()))["steps"]
    names = [s.get("name", "") for s in steps]
    runs = [str(s.get("run", "")) for s in steps]
    at = next(i for i, r in enumerate(runs) if "tools/interview_preflight.py" in r)
    assert "mode == 'render'" in steps[at].get("if", "")
    assert names.index("装系统依赖") < at, "量中文宽度的字体是那一步装的"
    assert at < names.index("取字幕切行"), "预检要排在取字幕、下源片之前"


#: picker／预检 import 了、但改了也不改变「谁能投」的模块（只出提示）。
#: ⚠️ `spec_wording` 原来在这儿（预检只拿它出 ⚠️ 措辞提示）——预检接上全称断言闸之后，
#: `absolute_claims.interview_texts` 的扫描面就是它的 `interview_outward_texts`，改了会变红绿。
_WAKE_EXEMPT: dict[str, str] = {}
#: 预检那排闸在 picker／预检之外的模块里：全称断言闸（`production_preflight`）→ 判据本身
#: （`absolute_claims`）。它们 import 的本地模块同样要叫醒。
_WAKE_GATE_MODULES = ("production_preflight", "absolute_claims")


def test_auto_render被预检和picker的判据改动叫醒():
    """review 那条：`interview-auto-render.yml` 的 `on.push.paths` 没列新加的几道闸，
    修一道闸要干等最多 10 分钟的定时班次才重判等待名单。**按 import 推导**：picker 和
    预检直接 import 的每一个本地工具模块、以及豁免表，都要在 paths 里。"""
    import re as _re

    import yaml

    wf = yaml.safe_load((ROOT / ".github/workflows/interview-auto-render.yml").read_text(
        encoding="utf-8"))
    paths = set((wf.get(True) or wf.get("on"))["push"]["paths"])
    local = {p.stem for p in (ROOT / "tools").glob("*.py")}
    gate_mods = {g.__module__ for g in pf._spec_gates(bic)} - {"build_interview_clip"}
    assert gate_mods <= set(_WAKE_GATE_MODULES), \
        f"预检那排闸来自这些模块，`_WAKE_GATE_MODULES` 没跟上：{sorted(gate_mods)}"
    need = set()
    for mod in ("pick_interview_renders", "interview_preflight", *_WAKE_GATE_MODULES):
        src = (ROOT / "tools" / f"{mod}.py").read_text(encoding="utf-8")
        found = set(_re.findall(r"^\s*(?:from|import) ([a-z_]+)", src, _re.M)) & local
        assert found, f"{mod} 一个本地 import 都没扫到——扫描面坏了"
        need |= found | {mod}
    need -= set(_WAKE_EXEMPT)
    missing = sorted(f"tools/{m}.py" for m in need if f"tools/{m}.py" not in paths)
    assert not missing, f"改了这些判据不会叫醒 picker：{missing}"
    assert "data/legacy_interview_gates.json" in paths
    # 口味闸的存量表（`taste_gates.LEGACY_PATH`）：改豁免同样改变谁能投
    assert "data/legacy_taste_gates.json" in paths
    assert len(wf[True]["push"]["paths"]) == len(paths), "paths 里有重复的条目"


# ── 四、默认终点和片尾板 ─────────────────────────────────────────────────


def _rows(last_end: float) -> list[dict]:
    return [{"t": 1.0, "end": 1.4, "text": "Hello"},
            {"t": last_end - 0.3, "end": last_end, "text": "thanks."},
            {"t": last_end + 0.5, "end": last_end + 0.9, "text": "[Music]"}]


#: `interview_tail` 模块 docstring 第一节：话说完就收的 12 条人手终点，离词尾的中位。
_HUMAN_TRIM_MEDIAN = 0.79


@pytest.mark.parametrize(("last_end", "board", "duration"), [
    (111.98, 114.4, 117.42),    # tien-cobolli：第一版 end＝全长 117.42，板从 114.4 起
    (115.35, 116.1, 119.15),    # sabalenka-pegula：end＝全长，板从 116.1 起淡入（已发）
])
def test_没给end时默认收在最后一个词之后_偏向多留(last_end, board, duration):
    """review 那条（首轮 nit 7 起）：默认终点原来是「词尾 ＋ 0.5」，比人手收尾的中位 0.79
    还紧——为的是躲开 sabalenka-pegula 那张 +0.75 的板，代价是话音后的掌声和庆祝。
    第四节上线之后自动默认的 `end` 撞上板由出片那一趟当场收
    （`test_自动默认的end撞上片尾板_直接收到算出来的终点_不红`），躲板不必再从默认值里扣；
    「默认取值要偏向多留」（tennis-video-craft 2026-08-12）。"""
    import build_interview_request as bir

    start, end = bir.request_window({}, duration, _rows(last_end))
    assert start == 0.0 and end >= last_end + _HUMAN_TRIM_MEDIAN - 0.005, \
        f"默认终点 {end} 离词尾 {last_end} 不到人手收尾的中位 {_HUMAN_TRIM_MEDIAN}：偏向少留了"
    assert end < duration, "默认终点不许退回源片全长"
    assert bir.request_window({"end": 100.0}, duration, _rows(last_end)) == (0.0, 100.0)
    assert bir.request_window({}, duration, None) == (0.0, duration)


def test_请求生成器切行和写进spec的是同一个默认终点(monkeypatch, tmp_path):
    """真跑 `build_interview_request._build_one`：没给 `end` 的请求，切行的窗和
    写进 spec 的 `end` 都是「最后一个词 ＋ 一口气」，不是源片全长。"""
    import build_interview_request as bir
    import draft_interview_spec

    path = tmp_path / "demo.json"
    path.write_text('{"slug":"demo","url":"https://youtu.be/x"}', encoding="utf-8")
    monkeypatch.setattr(bir, "_transcribe_request", lambda url, d, model: (_rows(50.0), 80.0))
    windows, seen = [], {}
    monkeypatch.setattr(bic, "segment", lambda words, start, end, budget=None, ruler=None: (
        windows.append((start, end)) or [{"a": 0.0, "b": 1.0, "en": "hello"}]))
    monkeypatch.setattr(draft_interview_spec, "translate",
                        lambda rows, chat, max_zh_chars=None: ["你好"])
    monkeypatch.setattr(bir, "build_spec", lambda req, zh, duration: seen.update(req) or {})
    bir._build_one(path, object(), write=False)
    assert windows == [(0.0, 50.0 + tail.DEFAULT_TAIL)]
    assert seen["end"] == 50.0 + tail.DEFAULT_TAIL


def test_自动草稿的默认终点也跟着最后一个词(monkeypatch, tmp_path):
    """真跑 `draft_interview_spec._build_one`：草稿的 `end` 不再是源片全长。"""
    import draft_interview_spec as dis

    monkeypatch.setattr(dis, "SPECS", tmp_path / "specs")
    monkeypatch.setattr(dis, "OUTDIR", tmp_path / "out")
    monkeypatch.setattr(dis, "transcribe", lambda url, td: (_rows(50.0), 80.0))
    monkeypatch.setattr(dis, "translate", lambda rows, chat: ["译文"] * len(rows))
    cal = [{"en": "Cincinnati Open", "zh": "辛辛那提大师赛", "start": "08-16",
            "end": "08-23", "pat": "cincinnati"}]
    cand = {"title": "Cincinnati 2026 R3 Alexander Zverev Interview",
            "url": "https://example.test/x"}
    slug, ok, msg = dis._build_one(cand, None, cal, write=True)
    assert ok, msg
    draft = json.loads((tmp_path / "specs" / f"{slug}.draft.json").read_text(encoding="utf-8"))
    assert draft["end"] == 50.0 + tail.DEFAULT_TAIL, draft["end"]


_N = tail.CARD_W * tail.CARD_H


def _gray(value: int) -> bytes:
    return bytes([value]) * _N


def _pattern(seed: int) -> bytes:
    """一帧「画面」：按 seed 变化的条纹，相邻 seed 之间差别明显（模拟换了镜头的画面）。"""
    return bytes((((i % tail.CARD_W) * 5 + (i // tail.CARD_W) * 3 + seed * 17) % 200) + 30
                 for i in range(_N))


def _card(k: int) -> bytes:
    """一张静止的板：逐帧几乎一样，只有压缩噪声那么点变化（实测相邻帧差 0.01~0.3）。"""
    base = bytearray(_pattern(999))
    if k % 5 == 0:
        base[k % _N] = min(255, base[k % _N] + 1)
    return bytes(base)


def _talking(k: int) -> bytes:
    """同一个镜头里人在动：每帧只有一小块在变（相邻帧差几个点，不是换镜头）。"""
    base = bytearray(_pattern(7))
    for i in range(0, _N // 4):
        j = (i * 3 + k * 11) % _N
        base[j] = min(255, base[j] + 6)
    return bytes(base)


def test_片尾板检测_硬切到静止板认得出():
    frames = [_pattern(k) for k in range(40)] + [_card(k) for k in range(25)]
    assert tail.trailing_card(frames, 100.0) == pytest.approx(104.0)


def test_片尾板检测_黑场加淡入认得出_起点算在黑场():
    card = _card(1)
    fade = [bytes(int(x * a) for x in card) for a in (0.2, 0.4, 0.6, 0.8)]
    frames = ([_pattern(k) for k in range(30)] + [_gray(1)] + fade
              + [_card(k) for k in range(20)])
    assert tail.trailing_card(frames, 0.0) == pytest.approx(3.0)


def test_片尾板检测_机位不动的发布会不误认():
    """发布会：机位锁死、人坐着说话，相邻帧差很小但**一直在变**——而且前面恰好有
    一刀切到这个机位（真实发布会的相邻帧差中位 0.29 起）。只剩「不动」那一条在拦。"""
    base = _pattern(5)
    presser = [bytes(min(255, b + ((i + k) % 3 == 0)) for i, b in enumerate(base))
               for k in range(60)]
    frames = [_pattern(k) for k in range(20)] + presser
    assert tail.trailing_card(frames, 0.0) is None


def test_片尾板检测_画面自己停住_没有切换不算板():
    """源片自己的冻帧（同一个镜头停住）：前面没有一刀切换，不是板——
    `end` 越过源片画面的那种冻帧由 `end_card_problem` 按视频流时长另外拦。"""
    frames = [_talking(k) for k in range(30)] + [_talking(30)] * 20
    assert tail.trailing_card(frames, 0.0) is None


def _clip(dest: Path, parts: list[tuple[str, float]]) -> Path:
    """用 ffmpeg 真造一条源片：[(lavfi 视频源, 秒数)] 依次拼起来。"""
    inputs, n = [], 0
    for src, secs in parts:
        sep = ":" if "=" in src else "="
        inputs += ["-f", "lavfi", "-t", str(secs), "-i", f"{src}{sep}s=320x180:r=25"]
        n += 1
    concat = "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
                    "-filter_complex", concat, "-map", "[v]", "-c:v", "libx264",
                    "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(dest)],
                   check=True, capture_output=True, timeout=120)
    return dest


def test_源片到手就量_end压进片尾板或越过画面都红(tmp_path):
    src = _clip(tmp_path / "s.mp4", [("testsrc2", 4.0), ("color=c=0x203040", 2.0)])
    spec = {"slug": "x", "start": 0.0, "end": 6.0}
    problem = tail.end_card_problem(spec, src)
    assert problem and "片尾板" in problem and "收到 3.8" in problem
    assert tail.end_card_problem({**spec, "end": 3.9}, src) is None
    assert tail.end_card_problem({**spec, "_end_board_ok": "看过，是要的画面"}, src) is None
    frozen = tail.end_card_problem({**spec, "end": 7.5}, src)
    assert frozen and "冻住" in frozen


def test_已发的短冻帧挂豁免表_end一改或越过太多照旧红(tmp_path, monkeypatch):
    """review 那条：`FROZEN_SLACK` 0.2 秒只校准过 1.1~1.7 秒那五条，0.2~1 秒的老片子重渲时
    也会红——新闸撞旧内容。不放松门槛，按量出来的名单豁免；豁免只认量的那一刻的 `end`。"""
    src = _clip(tmp_path / "s.mp4", [("testsrc2", 4.0)])
    table = tmp_path / "legacy.json"
    table.write_text(json.dumps({"frozen_tail_short": {
        "slugs": ["old-one", "long-one"], "end": {"old-one": 4.5, "long-one": 5.3}}}),
        encoding="utf-8")
    monkeypatch.setattr(gates, "LEGACY", table)
    assert tail.end_card_problem({"slug": "old-one", "start": 0.0, "end": 4.5}, src) is None
    changed = tail.end_card_problem({"slug": "old-one", "start": 0.0, "end": 4.6}, src)
    assert changed and "冻住" in changed, "改了 end 就是新内容，回到正常的闸"
    assert "冻住" in (tail.end_card_problem({"slug": "new-one", "start": 0.0, "end": 4.5},
                                           src) or "")
    too_long = tail.end_card_problem({"slug": "long-one", "start": 0.0, "end": 5.3}, src)
    assert too_long and "冻住" in too_long, "越过 1 秒以上是校准过的那一类，照旧红"


def test_短冻帧豁免表只许减不许加_名字要真的存在_end还是量的那一刻():
    table = gates.legacy_table("frozen_tail_short")
    slugs = gates.legacy("frozen_tail_short")
    assert slugs, "豁免表读不到——路径或键名写错了，整条判据会静静失效"
    assert len(slugs) <= 2, "只许减不许加：新片子的 end 要收在源片画面以内"
    seen = {s["slug"]: s for s in _corpus()}
    assert slugs <= set(seen), sorted(slugs - set(seen))
    ends = table.get("end") or {}
    moved = sorted(s for s in slugs if abs(float(seen[s]["end"]) - float(ends.get(s, -1))) >= 0.005)
    assert not moved, f"这些的 end 已经改过了（豁免不再生效），从表里删掉：{moved}"
    for s, v in (table.get("measured_frozen_s") or {}).items():
        assert FROZEN_BAND[0] < v <= tail.LEGACY_FROZEN_MAX, (s, v)


FROZEN_BAND = (0.1, 1.05)


def test_正常结尾的源片不红(tmp_path):
    src = _clip(tmp_path / "s.mp4", [("testsrc2", 5.0)])
    assert tail.end_card_problem({"slug": "x", "start": 0.0, "end": 5.0}, src) is None


def test_片尾板那道闸排在编码之前(tmp_path, monkeypatch):
    """真跑 `render()`：源片尾巴是一张板、`end` 压了进去——必须在正片编码
    （`-filter_complex` 那次 ffmpeg）之前就退出。"""
    src = _clip(tmp_path / "s.mp4", [("testsrc2", 4.0), ("color=c=0x203040", 2.0)])
    monkeypatch.setattr(bic, "check_takeaway", lambda spec: None)
    monkeypatch.setattr(bic, "yt_download", lambda *a, **k: src)
    real = subprocess.run

    def run(cmd, *a, **k):
        if cmd and cmd[0] == "ffmpeg" and "-filter_complex" in cmd:
            pytest.fail("片尾板没拦住，已经开始编码正片")
        return real(cmd, *a, **k)

    monkeypatch.setattr(bic.subprocess, "run", run)
    spec = {"slug": "x", "url": "https://example.invalid/x", "start": 0.0, "end": 6.0}
    with pytest.raises(SystemExit, match="片尾板"):
        bic.render(spec, tmp_path / "x.ass", tmp_path)


def test_render把产物目录交给check_tail_自动收短才量得到词尾(tmp_path, monkeypatch):
    """词尾托底读的是产物目录里的 `cap_asr.json3`——`render()` 调 `check_tail` 时漏传
    `outdir`，托底就静静失效（终点照旧落在最后一个词里），什么都不会红。"""
    seen = {}

    def spy(spec, src, workdir=None):
        seen["workdir"] = workdir
        raise SystemExit("spy")

    monkeypatch.setattr(bic, "check_takeaway", lambda spec: None)
    monkeypatch.setattr(bic, "yt_download", lambda *a, **k: tmp_path / "s.mp4")
    monkeypatch.setattr(bic, "check_tail", spy)
    with pytest.raises(SystemExit, match="spy"):
        bic.render({"slug": "x", "url": "u", "start": 0.0, "end": 6.0},
                   tmp_path / "x.ass", tmp_path)
    assert seen["workdir"] == tmp_path


def test_自动默认的end撞上片尾板_直接收到算出来的终点_不红(tmp_path, capsys):
    """review 那条：`default_end`（最后一个词 ＋ 0.5）看不见板——alcaraz-fritz 的板在词尾
    ＋0.11 秒、拉沃尔杯四条主持人的话压在板上。自动产出的 spec 没人会来改 `end`，
    红了就是每 70 分钟重投一次、永远红下去；闸已经算出了终点，就直接用它。"""
    src = _clip(tmp_path / "s.mp4", [("testsrc2", 4.0), ("color=c=0x203040", 2.0)])
    spec = {"slug": "x", "start": 0.0, "end": 6.0, "_end_default": 6.0}
    assert tail.end_is_auto(spec)
    trim = bic.check_tail(spec, src)
    assert spec["end"] == pytest.approx(3.8)
    assert trim and trim["from"] == 6.0 and trim["to"] == pytest.approx(3.8)
    assert "自动收到 3.80" in capsys.readouterr().out, "收短要在日志里说一声"


def test_自动默认的end越过画面又压着板_两道都收(tmp_path):
    src = _clip(tmp_path / "s.mp4", [("testsrc2", 4.0), ("color=c=0x203040", 2.0)])
    spec = {"slug": "x", "start": 0.0, "end": 7.5, "_end_default": 7.5}
    trim = bic.check_tail(spec, src)
    assert spec["end"] == pytest.approx(3.8) and len(trim["why"]) == 2


def test_自动收短时板紧贴话尾_终点托底在量出来的词尾_不吃字尾(tmp_path):
    """review 那条：「板前 0.2 秒」在 alcaraz-fritz 那种板（词尾 ＋0.11 秒）上落进最后一个词里
    0.09 秒。自动那条路拿 `cap_asr.json3` 量出来的词尾托底，但不越过板前最后一帧确定
    不是板的采样；话压在板上还在说的不托底。人给的 end 那条路（红的那句话）不变。"""
    src = _clip(tmp_path / "s.mp4", [("testsrc2", 4.0), ("color=c=0x203040", 2.0)])

    def trimmed(words):
        (tmp_path / "cap_asr.json3").write_text(json.dumps({"events": [
            {"tStartMs": int(a * 1000), "dDurationMs": int(d * 1000), "segs": [{"utf8": w}]}
            for a, d, w in words]}), encoding="utf-8")
        spec = {"slug": "x", "start": 0.0, "end": 6.0, "_end_default": 6.0,
                "asr_model": "small.en"}
        bic.check_tail(spec, src, tmp_path)
        return spec["end"]

    assert trimmed([(3.0, 0.5, "thank"), (3.6, 0.29, "you.")]) == pytest.approx(3.89)
    assert trimmed([(3.0, 0.5, "thank"), (4.2, 0.5, "everyone")]) == pytest.approx(3.8), \
        "话压在板上：不托底"
    assert trimmed([(3.0, 0.98, "thanks.")]) == pytest.approx(3.9), "托底不越过 card − 1/fps"
    assert trimmed([(1.0, 0.4, "hi"), (3.2, 0.3, "[Music]")]) == pytest.approx(3.8), \
        "最后一个真词离板很远：照旧板前 0.2"
    assert "收到 3.8" in (tail.end_card_problem(
        {"slug": "x", "start": 0.0, "end": 6.0}, src) or "")


@pytest.mark.parametrize("spec", [
    {"end": 6.0},                                   # 人写的 end（没有 _end_default）
    {"end": 6.0, "_end_default": 5.5},              # 生成器给过默认值，后来有人改了 end
    {"end": 6.0, "_request_origin": {"request": {"end": 6.0}, "duration": 6.0}},
])
def test_人给的end撞上片尾板照旧红(tmp_path, spec):
    src = _clip(tmp_path / "s.mp4", [("testsrc2", 4.0), ("color=c=0x203040", 2.0)])
    spec = {"slug": "x", "start": 0.0, **spec}
    assert not tail.end_is_auto(spec)
    with pytest.raises(SystemExit, match="片尾板"):
        bic.check_tail(spec, src)
    assert spec["end"] == 6.0, "人给的数不许被悄悄改掉"


def test_老spec_请求没写end而end还等于源片全长_算自动():
    """默认终点上线之前请求没给 `end` 时一律取全长（`else duration`）——那一批的
    `end` 就是源片全长，同样没人给过。"""
    origin = {"request": {"url": "u"}, "duration": 119.1531875}
    assert tail.end_is_auto({"end": 119.15, "_request_origin": origin})
    assert not tail.end_is_auto({"end": 112.0, "_request_origin": origin})


def test_生成器没拿到人给的end时记下默认值(monkeypatch, tmp_path):
    """请求／草稿两条生成路都要把算出来的 `end` 记进 `_end_default`——出片那一趟
    靠它分辨「没人给过」。请求里写了 `end` 的不记。"""
    import build_interview_request as bir
    import draft_interview_spec

    path = tmp_path / "demo.json"
    monkeypatch.setattr(bir, "_transcribe_request", lambda url, d, model: (_rows(50.0), 80.0))
    monkeypatch.setattr(bic, "segment", lambda words, start, end, budget=None, ruler=None: (
        [{"a": 0.0, "b": 1.0, "en": "hello"}]))
    monkeypatch.setattr(draft_interview_spec, "translate",
                        lambda rows, chat, max_zh_chars=None: ["你好"])
    for req, marked in (({"slug": "demo", "url": "https://youtu.be/x"}, True),
                        ({"slug": "demo", "url": "https://youtu.be/x", "end": 30.0}, False)):
        built: dict = {}
        monkeypatch.setattr(bir, "build_spec", lambda r, zh, duration, built=built: (
            built.update(end=r["end"]) or built))
        path.write_text(json.dumps(req), encoding="utf-8")
        bir._build_one(path, object(), write=False)
        assert ("_end_default" in built) is marked, (req, built)
        if marked:
            assert tail.end_is_auto(built)

    import draft_interview_spec as dis
    monkeypatch.setattr(dis, "SPECS", tmp_path / "specs")
    monkeypatch.setattr(dis, "OUTDIR", tmp_path / "out")
    monkeypatch.setattr(dis, "transcribe", lambda url, td: (_rows(50.0), 80.0))
    monkeypatch.setattr(dis, "translate", lambda rows, chat: ["译文"] * len(rows))
    cal = [{"en": "Cincinnati Open", "zh": "辛辛那提大师赛", "start": "08-16",
            "end": "08-23", "pat": "cincinnati"}]
    cand = {"title": "Cincinnati 2026 R3 Alexander Zverev Interview",
            "url": "https://example.test/x"}
    slug, ok, msg = dis._build_one(cand, None, cal, write=True)
    assert ok, msg
    draft = json.loads((tmp_path / "specs" / f"{slug}.draft.json").read_text(encoding="utf-8"))
    assert tail.end_is_auto(draft), draft.get("_end_default")


def test_收短记进render_json_没收短就把上一版那笔删掉(tmp_path):
    (tmp_path / "render.json").write_text('{"video_url": "u", "end_trim": {"to": 1}}',
                                          encoding="utf-8")
    ia.record([], tmp_path)
    data = json.loads((tmp_path / "render.json").read_text(encoding="utf-8"))
    assert "end_trim" not in data and data["video_url"] == "u"
    ia.record([], tmp_path, end_trim={"from": 6.0, "to": 3.8})
    data = json.loads((tmp_path / "render.json").read_text(encoding="utf-8"))
    assert data["end_trim"] == {"from": 6.0, "to": 3.8}


# ── 五、拼接清单：解读卡的声音、品牌片尾 ─────────────────────────────────


def _meta(*rows) -> dict:
    return {"assembly": {"parts": list(rows)}}


def test_拼接清单_解读卡静音或片尾丢了就不合格():
    spec = {"takeaway": {"close": {"point": "x", "ask": "y？"}}}
    body = {"role": "body", "seconds": 60.0}
    card = {"role": "takeaway_close", "seconds": 6.0, "peak_db": -12.0}
    outro = {"role": "outro", "seconds": 3.0, "peak_db": -11.0}
    assert ia.problems(spec, _meta(body, card, outro)) == []
    assert any("静音" in p for p in ia.problems(
        spec, _meta(body, {**card, "peak_db": -91.0}, outro)))
    assert any("片尾" in p for p in ia.problems(spec, _meta(body, card)))
    assert any("没有这张卡" in p for p in ia.problems(spec, _meta(body, outro)))
    assert any("assembly" in p for p in ia.problems(spec, {}))
    claimed = {**spec, "_takeaway_silent_why": "x", "_no_outro_why": "y"}
    assert ia.problems(claimed, _meta(body, {**card, "peak_db": -91.0})) == []


def _tiny(dest: Path, seconds: float, *, tone: bool) -> Path:
    audio = "sine=frequency=440:sample_rate=48000" if tone else "anullsrc=r=48000:cl=stereo"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"color=c=black:s=64x64:r=25:d={seconds}",
         "-f", "lavfi", "-t", str(seconds), "-i", audio, "-t", str(seconds),
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-ar", "48000", "-ac", "2", str(dest)],
        check=True, capture_output=True, timeout=120)
    return dest


def test_拼接清单是量出来的_静音卡在render_json里就是静音(tmp_path):
    """查产物，不查信号：退路走没走过，看那一段的音轨，不看「调没调合成」。"""
    parts = [_tiny(tmp_path / "_body.mp4", 2.0, tone=True),
             _tiny(tmp_path / "_takeaway_close.mp4", 2.0, tone=False),
             _tiny(tmp_path / "_outro.mp4", 1.0, tone=True)]
    (tmp_path / "render.json").write_text(json.dumps({"video_url": "u"}), encoding="utf-8")
    ia.record(parts, tmp_path)
    meta = json.loads((tmp_path / "render.json").read_text(encoding="utf-8"))
    assert meta["video_url"] == "u", "合并写，不覆盖"
    roles = [r["role"] for r in meta["assembly"]["parts"]]
    assert roles == ["body", "takeaway_close", "outro"]
    bad = ia.problems({"takeaway": {"close": {"point": "x"}}}, meta)
    assert len(bad) == 1 and "静音" in bad[0]


def test_L2闸照spec核拼接清单(tmp_path, monkeypatch, capsys):
    import check_interview_landed as ci

    film = _tiny(tmp_path / "x.mp4", 1.0, tone=True)
    (tmp_path / "render.json").write_text(json.dumps(
        {"film_seconds": 1.0, **_meta({"role": "body", "seconds": 1.0})}), encoding="utf-8")
    monkeypatch.setattr(ci, "CANVAS_W", 64)
    monkeypatch.setattr(ci, "CANVAS_H", 64)
    spec = {"zh": [], "takeaway": {"close": {"point": "x"}}}
    bad = ci.check_film(film, spec, tmp_path / "x.ass")
    out = capsys.readouterr().out
    assert "成片里却没有这张卡" in out and "没有品牌片尾" in out
    assert bad >= 2


# ── 六、推送之后改了 spec：内容改了就是修订 ───────────────────────────────


def test_内容指纹不看注解():
    a = {"slug": "x", "end": 10.0, "_why": "一", "cover": {"frame_at": 1, "_why": "a"}}
    b = {**a, "_why": "二", "cover": {"frame_at": 1, "_why": "b"}}
    assert ir.content_sha256(a) == ir.content_sha256(b)
    assert ir.content_sha256(a) != ir.content_sha256({**a, "end": 9.0})


#: 出片那条路会读、但**不进画面**的键（闸、认领、核验、推送正文）。和 `ir.FILM_KEYS`
#: 一起必须盖住 `build_interview_clip` 读到的每一个键和全库出现过的每一个键——
#: 新加一个字段，不分类就红，逼着人判一次「它进不进成片」。
_NOT_FILM = frozenset({
    "slug", "source_title", "cookies", "push",   # push 按子键另分（PUSH_FILM_KEYS）
    "whisper_model", "whisper_vad_filter", "transcript_languages", "transcript_verified", "transcript_verification",
    "transcript_disagree_ok", "suspect", "suspect_ok", "caption_gaps_ok",
    "human_quote", "human_quote_ok", "opening", "requested_content_type", "match",
    "source_verification", "featured_player", "interviewee", "max_zh_chars",
    # 固定居中策略只允许 cx=0.5/track=false；这两个键只由 crop_policy 闸读取，
    # 采访渲染器取景仍由 crop_ratio/crop_keep_top/crop_shift_x 决定。
    "cx", "track",
})


def test_内容指纹只认会进成片的键():
    """review 那条：第一版把「去掉 `_` 注解」当成内容，推送后只改了 `transcript_verified`
    `caption_gaps_ok` `suspect_ok` `whisper_model` `match` `source_verification` 也会重渲——
    edge-tts／Chromium 不是逐字节确定的，新成片指纹一变，微信上就多一条一样的消息。"""
    base = {"slug": "x", "url": "u", "start": 0.0, "end": 10.0, "zh": ["你好"],
            "event": "2026 美网 第一轮", "cover": {"frame_at": 1.0},
            "push": {"matchup": "甲 vs 乙", "score": "6-3 6-4", "summary": "甲赢了",
                     "lead": "正文", "auto": True},
            "lead_in": {"url": "v", "start": 1.0, "end": 9.0, "subs": [], "why": "a",
                        "verification": {"method": "m"}, "source_captions": []},
            "takeaway": {"close": {"point": "一句话"}}}
    h = ir.content_sha256(base)
    for key, value in (("transcript_verified", True), ("caption_gaps_ok", {"1-2": "掌声"}),
                       ("suspect_ok", {"3": "对的"}), ("whisper_model", "large-v3"),
                       ("match", {"id": "m2"}), ("source_verification", {"status": "v"}),
                       ("requested_content_type", "on_court"), ("opening", {"kind": "none"}),
                       ("featured_player", "甲")):
        assert ir.content_sha256({**base, key: value}) == h, f"改 `{key}` 不该算内容"
    assert ir.content_sha256({**base, "push": {**base["push"], "lead": "改了正文",
                                               "auto": False}}) == h
    assert ir.content_sha256({**base, "lead_in": {**base["lead_in"], "why": "b",
                                                  "verification": {"method": "n"}}}) == h
    for changed in ({**base, "zh": ["您好"]}, {**base, "event": "2026 美网 第二轮"},
                    {**base, "cover": {"frame_at": 2.0}},
                    {**base, "push": {**base["push"], "score": "6-3 7-5"}},
                    {**base, "push": {**base["push"], "summary": "乙输了"}},
                    {**base, "lead_in": {**base["lead_in"], "start": 2.0}},
                    {**base, "takeaway": {"close": {"point": "另一句"}}},
                    {**base, "en_fixed": {"1": "Hi"}}, {**base, "crop_shift_x": 40}):
        assert ir.content_sha256(changed) != h, changed


def test_内容指纹白名单盖住出片读的每一个键():
    """`build_interview_clip` 读到的键、全库 spec 里出现过的键，每一个都要被判过：
    进成片（`ir.FILM_KEYS`）或不进（`_NOT_FILM`）。两边都不在＝新字段没人判过。"""
    import re as _re

    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    read = {k for k in _re.findall(r'spec(?:\.get\(|\[)"([a-z_]+)"', src)
            if not k.startswith("_")}
    seen = {k for spec in _corpus() for k in spec if not k.startswith("_")}
    assert not (ir.FILM_KEYS & _NOT_FILM)
    assert {"zh", "end", "cover", "takeaway"} <= read, "扫描面坏了：出片读的键一个都没扫到"
    unclassified = sorted((read | seen) - ir.FILM_KEYS - _NOT_FILM)
    assert not unclassified, f"这些键没判过进不进成片：{unclassified}"


def test_推送后只改了不进成片的键_不重渲():
    now = datetime(2026, 9, 27, 1, 0, tzinfo=timezone.utc)
    spec = {"slug": "x", "end": 117.42, "zh": ["a"]}
    qc = {"film_sha256": "F", "spec_content_sha256": ir.content_sha256(spec)}
    pushed = {"film_sha256": "F", "at": "2026-09-26T18:57:00Z"}
    for edit in ({"transcript_verified": True}, {"caption_gaps_ok": {"1-2": "掌声"}},
                 {"suspect_ok": {"2": "对"}}, {"whisper_model": "large-v3"},
                 {"match": {"id": "z"}}, {"source_verification": {"status": "verified"}}):
        assert ir.post_push_edit({**spec, **edit}, pushed, qc, now) == (False, ""), edit


def test_推送后改内容在窗口里就重渲_窗口外说一声_只改注解安静跳过():
    now = datetime(2026, 9, 27, 1, 0, tzinfo=timezone.utc)
    spec = {"slug": "x", "end": 117.42, "_why": "a"}
    qc = {"film_sha256": "F", "spec_content_sha256": ir.content_sha256(spec)}
    pushed = {"film_sha256": "F", "at": "2026-09-26T18:57:00Z"}
    trimmed = {**spec, "end": 114.2}                    # tien-cobolli 9ae8918f 那一刀
    assert ir.post_push_edit(trimmed, pushed, qc, now) == (True, "")
    assert ir.post_push_edit({**spec, "_why": "b"}, pushed, qc, now) == (False, "")
    late = now + timedelta(hours=ir.AUTO_REVISION_HOURS)
    revise, why = ir.post_push_edit(trimmed, pushed, qc, late)
    assert not revise and "_publication_revision" in why
    # 内容指纹上线之前的产物：照老规矩，不批量唤醒旧片
    assert ir.post_push_edit(trimmed, pushed, {"film_sha256": "F"}, now) == (False, "")
    assert ir.post_push_edit(trimmed, {**pushed, "film_sha256": "G"}, qc, now) == (False, "")


def test_QC凭证记下内容指纹(tmp_path, monkeypatch):
    import check_interview_landed as ci
    import interview_source_gate

    spec = {"slug": "demo", "requested_content_type": "on_court", "zh": ["你好"], "end": 5}
    spec_path = tmp_path / "demo.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "poster.jpg").write_bytes(b"p")
    (tmp_path / ci.COVER_VISUAL_ATTESTATION).write_text("{}", encoding="utf-8")
    ass = tmp_path / "demo.ass"
    ass.write_text("", encoding="utf-8")
    film = tmp_path / "demo.mp4"
    film.write_bytes(b"film")
    monkeypatch.setattr(ci, "cover_visual_ok",
                        lambda *a: (True, "", {"expected_subject": "x"}))
    monkeypatch.setattr(interview_source_gate, "validate_source_contract", lambda s: "a")
    monkeypatch.setattr(interview_source_gate, "content_identity_id", lambda s: "c")
    qc = json.loads(ci.write_attestation(film, spec_path, spec, ass, tmp_path)
                    .read_text(encoding="utf-8"))
    assert qc["spec_content_sha256"] == ir.content_sha256(spec)


def _picker(monkeypatch, tmp_path):
    import interview_preflight
    import pick_interview_renders as pick

    specs = tmp_path / "specs"
    specs.mkdir()
    out = tmp_path / "output"
    monkeypatch.setattr(pick, "SPECS", specs)
    monkeypatch.setattr(pick, "OUTPUT", out)
    monkeypatch.setattr(pick, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(pick, "LEGACY_INPUT_BASELINE", tmp_path / "baseline.json")
    monkeypatch.setattr(pick, "_rendered_slugs", lambda: {"x"})
    monkeypatch.setattr(pick, "missing_for_render", lambda slug, spec: [])
    monkeypatch.setattr(interview_preflight, "spec_problems", lambda s, **kw: ([], []))
    spec = {"slug": "x", "end": 117.42, "_why": "a"}
    (specs / "x.json").write_text(json.dumps(spec), encoding="utf-8")
    (out / "x").mkdir(parents=True)
    (out / "x" / "qc_attestation.json").write_text(json.dumps({
        "status": "pass", "film_sha256": "F", "spec_sha256": pick._sha256(specs / "x.json"),
        "spec_content_sha256": ir.content_sha256(spec)}), encoding="utf-8")
    (out / "x" / "pushed.json").write_text(json.dumps(
        {"film_sha256": "F", "at": "2026-09-26T18:57:00Z"}), encoding="utf-8")
    return pick, specs


def test_推送后手改spec_自动链当成修订投出去(monkeypatch, tmp_path):
    """tien-cobolli 推送 11 分钟后 9ae8918f 收掉片尾板，之后 5 小时 43 分钟没人重渲——
    原来这里对有 pushed.json 的一律 `continue`。"""
    pick, specs = _picker(monkeypatch, tmp_path)
    now = datetime(2026, 9, 26, 19, 10, tzinfo=timezone.utc)
    assert pick.todo_slugs(now=now) == ([], [])
    (specs / "x.json").write_text(json.dumps({"slug": "x", "end": 114.2, "_why": "a"}),
                                  encoding="utf-8")
    assert pick.todo_slugs(now=now)[0] == ["x"]
    ready, waiting = pick.todo_slugs(now=now + timedelta(days=3))
    assert ready == [] and "_publication_revision" in waiting[0][1][0]
    (specs / "x.json").write_text(json.dumps({"slug": "x", "end": 117.42, "_why": "b"}),
                                  encoding="utf-8")
    assert pick.todo_slugs(now=now) == ([], []), "只改注解不重渲"


def test_缺字段的坏spec记成红_不把picker整个带崩(monkeypatch, tmp_path):
    """一条缺 `end` 的 spec 在 runner 上一样会崩；预检要把它记成红，而不是抛出去
    让 `pick_interview_renders` 这一趟别的 slug 也投不出去。"""
    spec = _full_spec(monkeypatch, tmp_path)
    del spec["end"]
    problems, _ = pf.spec_problems(spec, copy=False)
    assert any("KeyError" in p for p in problems), problems
