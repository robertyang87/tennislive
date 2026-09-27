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


# ── 一、收尾卡那一句要一行放得下 ─────────────────────────────────────────


def _card_spec(point: str, slug: str = "new-one") -> dict:
    return {"slug": slug, "start": 0.0, "end": 60.0, "zh": ["你好"],
            "takeaway": {"close": {"point": point, "ask": "你怎么看？"}}}


@pytest.mark.parametrize(("point", "where"), [
    # jodar-bublik 48a60760 之前那一版：渲完抽帧看到折成「费 / 德勒」
    ("首秀赢完球 他先谢看台上的费德勒", "费 ／ 德勒"),
    # deminaur-zverev 617db353 之前那一版：折成「一 / 直顶住」
    ("落后一盘又被破发 他说只是一直顶住", "一 ／ 直顶住"),
])
def test_收尾卡那一句放不下一行就红_折点和成片上看到的一样(point, where):
    """判据的量法要能把**成片上真看到的那个折点**原样算出来——算不出来就说明
    尺子和 Chromium 不是一把（字体、字号、字距、正文区宽度任何一个对不上）。"""
    with pytest.raises(SystemExit, match=where):
        bic.check_takeaway(_card_spec(point))


@pytest.mark.parametrize("point", ["赢完球 先谢看台上的费德勒", "被逼到绝境 他只是一直顶住"])
def test_收尾卡改短之后的那两版放得下(point, capsys):
    bic.check_takeaway(_card_spec(point))


def test_收尾卡认领两行要写为什么():
    spec = _card_spec("首秀赢完球 他先谢看台上的费德勒")
    spec["takeaway"]["close"]["_wrap_ok"] = "有意在空格处折成两行"
    bic.check_takeaway(spec)


def test_量卡片宽度和渲卡片用的是同一组常量(monkeypatch, tmp_path):
    """**一个数写两处必分叉**：改了卡片留白，闸得跟着变，渲出来的 CSS 也得跟着变。"""
    seen = {}
    monkeypatch.setattr(bic, "_shoot", lambda html, dest: seen.setdefault("html", html))
    monkeypatch.setattr(bic, "TAKEAWAY_PAD_RIGHT", 200)
    bic.build_takeaway_card(_card_spec("一句话"), "close", tmp_path / "x.png")
    assert "padding:206px 200px 150px 92px" in seen["html"]
    assert f"font-size:{bic.TAKEAWAY_POINT_PX}px" in seen["html"]
    assert gates.point_box_px() == bic.CANVAS_W - 92 - 200


def test_新的收尾卡都放得下一行():
    legacy = gates.legacy("takeaway_point_wrap")
    bad = [f"{s['slug']}: {p}" for s in _corpus() if s["slug"] not in legacy
           for p in gates.takeaway_point_problems(s)]
    assert not bad, "\n".join(bad)


def test_收尾卡折行豁免表只许减不许加_名字要真的存在且真的还放不下():
    legacy = gates.legacy("takeaway_point_wrap")
    assert legacy, "豁免表读不到——路径或键名写错了，整条判据会静静失效"
    assert len(legacy) <= 61, "只许减不许加：新片子的收尾卡要收到一行放得下"
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


def test_全库顶栏比分都是赢家视角():
    bad = [f"{s['slug']}: {p}" for s in _corpus()
           if (p := gates.score_orientation_problem(s))]
    assert not bad, "\n".join(bad)


def test_顶栏比分那道闸坐在渲染入口_下载之前就红(tmp_path, monkeypatch):
    """不查源码文本，真跑 `main()`：L0 放行之后，比分方向错的 spec 在第一步就退出，
    一个网络调用都不发。"""
    spec = _score_spec("6-3 1-6 4-6")
    spec.update({"url": "https://example.invalid/x", "start": 0, "end": 10,
                 "event": "2026 美网 1/4决赛"})
    path = tmp_path / "s.json"
    path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(bic, "check_source_contract", lambda s: "ok")
    monkeypatch.setattr(bic, "storyboard_sheet",
                        lambda *a, **k: pytest.fail("比分那道闸没拦住，已经走到下载"))
    monkeypatch.setattr(sys, "argv", ["x", "--spec", str(path), "--stage", "subs"])
    with pytest.raises(SystemExit, match="输家视角"):
        bic.main()


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


@pytest.mark.parametrize(("mutate", "expect"), [
    (lambda s: s["zh"].pop(), "对不上"),                                      # 117:114 那种
    (lambda s: s["zh"].__setitem__(0, "非" * 20), "中文超宽"),
    (lambda s: s["zh"].__setitem__(1, "这是一场精彩的"), "吊在"),   # 那一行英文没收在句号上
    (lambda s: s["push"].__setitem__("score", "6-3 1-6 4-6"), "输家视角"),
    (lambda s: s["takeaway"]["close"].__setitem__(
        "point", "落后一盘又被破发 他说只是一直顶住"), "直顶住"),
])
def test_预检把runner上必红的spec错在本地报出来(monkeypatch, tmp_path, mutate, expect):
    spec = _full_spec(monkeypatch, tmp_path)
    mutate(spec)
    problems, _ = pf.spec_problems(spec, copy=False)
    assert any(expect in p for p in problems), problems


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


# ── 四、默认终点和片尾板 ─────────────────────────────────────────────────


def _rows(last_end: float) -> list[dict]:
    return [{"t": 1.0, "end": 1.4, "text": "Hello"},
            {"t": last_end - 0.3, "end": last_end, "text": "thanks."},
            {"t": last_end + 0.5, "end": last_end + 0.9, "text": "[Music]"}]


@pytest.mark.parametrize(("last_end", "board", "duration"), [
    (111.98, 114.4, 117.42),    # tien-cobolli：第一版 end＝全长 117.42，板从 114.4 起
    (115.35, 116.1, 119.15),    # sabalenka-pegula：end＝全长，板从 116.1 起淡入（已发）
])
def test_没给end时默认收在最后一个词之后_躲开量到的片尾板(last_end, board, duration):
    import build_interview_request as bir

    start, end = bir.request_window({}, duration, _rows(last_end))
    assert start == 0.0 and end < board, f"默认终点 {end} 压进了 {board} 起的片尾板"
    assert end >= last_end, "默认终点把最后一个词切掉了"
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
    monkeypatch.setattr(bic, "segment", lambda words, start, end, budget=None: (
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
