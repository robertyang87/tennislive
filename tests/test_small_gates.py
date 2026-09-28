"""2026-09-28 返工审计里的八道小闸：每一道单拿出来都不大，每一道都各烧掉过一整趟 render
或者一次重推（`rework_audit_0928`，82 趟失败 run ＋ 25 次推送后重推）。

| # | 闸 | 来路 |
|---|---|---|
| 1 | 章节卡超 18 字在 `--dry-run` 就红 | china-open-withdrawals（run 36296202661）、asiad-2026-men-draw（run 36296693320） |
| 2 | 「写过源片末尾」容差改成减一帧 | hu-kopriva-chengdu-2026-r1（run 35949569743） |
| 3 | 误差带里的旁白要拿真 TTS 认账 | zverev-deminaur-laver-cup-2026 第 9 段（run 36257658569） |
| 4 | 蒙版先缩成裁框尺寸再 alphamerge | safiullin-bu-hangzhou-2026-qf（run 36323549463，424×108 对 424×109） |
| 5 | 已知带片尾板的源，话音后空太久，手写采访红 | alcaraz-fritz-interview（1b0b65ee5）、tien-cobolli（9ae8918fb） |
| 6 | 钩子「送××进决赛」不算赛果；「N号种子」只报 | bucsa-noskova（872c6dab6）；bu-majchrzak（61e62b8a5） |
| 7 | 多源 `_no_probe_why` 要带宽高帧率 | sinner-beijing-withdrawal-2026（run 36133328467） |
| 8 | 开着回贴、probe 没量板，手写红 | prozorova-eala（run 36020126044）、alcaraz-mensik-doubles（run 36197683115） |

每一道：手写 spec 硬、自动 spec 只报、已发的冻进豁免表（只许减、自带自检）。
"""
from __future__ import annotations

import inspect
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import build_match_reel as reel  # noqa: E402
import probe_board as pb  # noqa: E402
import probe_sources as ps  # noqa: E402
import render_title_card as tc  # noqa: E402
import taste_gates as T  # noqa: E402
import taste_gates_extra as TX  # noqa: E402
from interview_tail import END_BOARD_SOURCES, end_board_source, quiet_tail_problem  # noqa: E402

REELS = sorted((ROOT / "specs" / "reels").glob("*.json"))
WORKFLOW = ROOT / ".github" / "workflows" / "match-reel.yml"
AUTO = {"status": "ready_for_render"}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _segments(spec: dict):
    urls = reel.spec_sources(spec)
    return reel.parse_segments(spec, urls, next(iter(urls)))


def _disk_probes() -> dict[str, dict]:
    probes: dict[str, dict] = {}
    for path in sorted((ROOT / "output").glob("*/reel/*/probe.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        probes[data.get("url")] = data
    return probes


# ═══════════════════════════ ① 章节卡字数 ═══════════════════════════

#: china-open-withdrawals-story-2026 在 ca2d4829a 上的第 2 段——run 36296202661 红在
#: render_title_card，dry-run 当时 exit 0。
CHINA_OPEN_CARD = "至少14人退出女单\n9月30日正赛开打"


def test_章节卡超字数在dry_run就红_和render里是同一个函数(monkeypatch):
    assert len(CHINA_OPEN_CARD) == tc.MAX_CHARS + 1
    spec = {"segments": [{"title_card": CHINA_OPEN_CARD, "seconds": 2.0}]}
    with pytest.raises(reel.ReelError, match="最多 18 个字"):
        reel._normalize_title_card_segments(spec)
    ok = {"segments": [{"title_card": CHINA_OPEN_CARD[:tc.MAX_CHARS], "seconds": 2.0}]}
    reel._normalize_title_card_segments(ok)
    assert ok["segments"][0]["image"].startswith(reel.TITLE_CARD_PREFIX)
    # render 那一刻（build）和 dry-run 走的是同一个 length_problem——写两份必分叉
    calls = []
    real = tc.length_problem
    monkeypatch.setattr(tc, "length_problem", lambda t: calls.append(t) or real(t))
    with pytest.raises(SystemExit):
        tc.build(CHINA_OPEN_CARD)
    with pytest.raises(reel.ReelError):
        reel._normalize_title_card_segments(
            {"segments": [{"title_card": CHINA_OPEN_CARD, "seconds": 2.0}]})
    assert calls == [CHINA_OPEN_CARD, CHINA_OPEN_CARD], calls


def test_全库章节卡都装得下():
    bad = []
    for path in REELS:
        for i, seg in enumerate(_load(path).get("segments") or []):
            if isinstance(seg, dict) and seg.get("title_card") \
                    and tc.length_problem(str(seg["title_card"])):
                bad.append(f"{path.stem} 第 {i + 1} 段")
    assert not bad, bad


# ═══════════════════════════ ② 写过源片末尾：减一帧 ═══════════════════════════

def _seg(start: float, end: float, source: str = ""):
    return reel.parse_segments({"source_url": "u", "segments": [
        {"start": start, "end": end, "narration": "一句。"}]}, {"": "u"}, "")[0]


def test_写过源片末尾_容差是减一帧_hu_kopriva那一趟():
    """hu-kopriva-chengdu-2026-r1（466450041）末段 139.1–143.4，ttv 源片 probe 报 143.56、
    25 fps：143.4＋0.18＝143.58，老容差 +0.05 放行，render 报「分段比要求的短」。"""
    seg = _seg(139.1, 143.4)
    assert reel.segments_over_source_end([seg], {"": 143.56}, {"": 25.0}, legacy={})
    assert reel.segments_over_source_end([seg], {"": 143.56}, legacy={}), "帧率不知道也要按一帧算"
    # 留够一帧就放行；刚好贴着一帧的边也放行
    assert not reel.segments_over_source_end([_seg(139.1, 143.34)], {"": 143.56}, {"": 25.0},
                                             legacy={})
    # 帧率越高一帧越短：50 fps 时 143.54 以内都行
    assert not reel.segments_over_source_end([_seg(139.1, 143.36)], {"": 143.56}, {"": 50.0},
                                             legacy={})
    assert reel.segments_over_source_end([_seg(139.1, 143.36)], {"": 143.56}, {"": 25.0},
                                         legacy={})


def test_写过源片末尾的豁免只认没动过的end():
    seg = _seg(139.1, 143.4)
    frozen = {"x": {"1": 143.4}}
    assert not reel.segments_over_source_end([seg], {"": 143.6}, {"": 25.0}, slug="x",
                                             legacy=frozen), "冻住的、老容差以内的放行"
    assert reel.segments_over_source_end([seg], {"": 143.6}, {"": 25.0}, slug="y",
                                         legacy=frozen), "别的 slug 不认"
    assert reel.segments_over_source_end([_seg(139.1, 143.41)], {"": 143.6}, {"": 25.0},
                                         slug="x", legacy=frozen), "end 改过就回到新判据"
    assert reel.segments_over_source_end([seg], {"": 143.3}, {"": 25.0}, slug="x",
                                         legacy=frozen), "老容差以外的冻住也不认"


def test_写过源片末尾的两个调用方都传了帧率和slug():
    src = inspect.getsource(reel)
    dry = src[src.index("def probe_dry_run("):src.index("def probe_dry_run(") + 12000]
    call = dry[dry.index("hard.extend(segments_over_source_end("):]
    call = call[:call.index("for tag, spot in")]
    assert "_probe_fps_value" in call and "slug=" in call, call
    fit = inspect.getsource(reel._check_segments_fit)
    assert "source_fps_value" in fit and "slug=slug" in fit
    render = inspect.getsource(reel.render)
    assert "_check_segments_fit(segments, sources, slug=" in render


def test_写过源片末尾减一帧的豁免表只许减():
    legacy = reel.legacy_source_end()
    assert legacy, "豁免表读不到——路径或键名写错了"
    probes = _disk_probes()
    specs = {str(_load(p).get("slug") or p.stem): _load(p) for p in REELS}
    stale = []
    for slug, ends in legacy.items():
        spec = specs.get(slug)
        if spec is None:
            stale.append(f"{slug}（spec 没了）")
            continue
        segs = _segments(spec)
        urls = reel.spec_sources(spec)
        for number, end in ends.items():
            seg = segs[int(number) - 1] if int(number) <= len(segs) else None
            if seg is None or abs(seg.end - end) > 1e-6:
                stale.append(f"{slug} 第 {number} 段（end 改过了）")
                continue
            probe = probes.get(urls.get(seg.source, ""))
            if not probes:
                continue
            if probe is None or not reel.segments_over_source_end(
                    [seg], {seg.source: float(probe["duration"])},
                    {seg.source: reel._probe_fps_value(probe)}, legacy={}):
                stale.append(f"{slug} 第 {number} 段（按新判据已经不红）")
    assert not stale, "从 data/legacy_source_end_frame.json 删掉：" + "、".join(stale)
    assert len(legacy) <= 4 and sum(map(len, legacy.values())) <= 5


# ═══════════════════════════ ③ 误差带里的旁白认真 TTS 的账 ═══════════════════════════

#: zverev-deminaur-laver-cup-2026 在 4a2eb32c4 上的第 9 段（146.0–157.9，画面 11.9s）；
#: runner 上 Azure 实测 12.10s，render 红（run 36257658569）。
ZVEREV_SEG9 = ("十比九，轮到德米纳尔的赛点。一个很长的回合，他被兹维列夫左右调动，"
               "一次次滑到角上把球救回来。最后一拍，兹维列夫没打进。")


def _zverev_spec(**extra) -> tuple[dict, list]:
    spec = {"slug": "zz-new-laver-cup-2026", "source_url": "u",
            "segments": [{"start": 146.0, "end": 157.9, "narration": ZVEREV_SEG9}], **extra}
    return spec, _segments(spec)


def _tight(segments) -> list[int]:
    return [i for i, _s, room in reel.narration_estimates(segments)
            if -reel.SPEECH_EST_ERR <= room < reel.SPEECH_EST_ERR]


def test_误差带里的段没量过真TTS_手写的红_命令现成():
    spec, segs = _zverev_spec()
    tight = _tight(segs)
    assert tight == [0], "zverev-deminaur 第 9 段离线估落在误差带里——这正是那一趟没去量的原因"
    hard, soft, ok = reel.narration_check_findings(spec, segs, tight, record={}, legacy={}, env={})
    assert len(hard) == 1 and not soft and not ok, (hard, soft)
    assert "render --check-narration --spec specs/reels/zz-new-laver-cup-2026.json" in hard[0]
    assert "-f mode=narration -f slug=zz-new-laver-cup-2026" in hard[0]


def test_量过真TTS的账按旁白指纹认():
    spec, segs = _zverev_spec()
    fp = reel.narration_fingerprint(segs[0])
    # 装得下：放行，还要报出来认过账
    hard, soft, ok = reel.narration_check_findings(
        spec, segs, [0], record={fp: {"segment": 1, "spoken": 11.5}}, legacy={}, env={})
    assert not hard and ok, (hard, ok)
    # Azure 那一趟的真数 12.10 > 11.9 + 0.12：量过也红
    hard, soft, ok = reel.narration_check_findings(
        spec, segs, [0], record={fp: {"segment": 1, "spoken": 12.10}}, legacy={}, env={})
    assert len(hard) == 1 and "超出" in hard[0], hard
    # 改一个字，指纹变了，老账不认
    spec2, segs2 = _zverev_spec()
    segs2[0].narration += "！"
    hard, _soft, _ok = reel.narration_check_findings(
        spec2, segs2, [0], record={fp: {"segment": 1, "spoken": 11.5}}, legacy={}, env={})
    assert hard and "没有这几段" in hard[0]


def test_误差带那道闸_自动spec和runner的cover与narration趟只报_冻着的老片只认原文():
    spec, segs = _zverev_spec(_production=AUTO)
    hard, soft, _ok = reel.narration_check_findings(spec, segs, [0], record={}, legacy={}, env={})
    assert not hard and soft and "自动产的 spec 只报" in soft[0]
    spec, segs = _zverev_spec()
    for mode in ("narration", "cover"):
        hard, soft, _ok = reel.narration_check_findings(
            spec, segs, [0], record={}, legacy={}, env={"REEL_DRY_RUN_FOR": mode})
        assert not hard and soft, mode
    hard, _soft, _ok = reel.narration_check_findings(
        spec, segs, [0], record={}, legacy={}, env={"REEL_DRY_RUN_FOR": "render"})
    assert hard
    frozen = {spec["slug"]: reel.spec_narration_fingerprint(segs)}
    hard, soft, _ok = reel.narration_check_findings(spec, segs, [0], record={}, legacy=frozen,
                                                    env={})
    assert not hard and "legacy_narration_unchecked" in soft[0]
    segs[0].narration = segs[0].narration.replace("十比九", "10比9")
    hard, _soft, _ok = reel.narration_check_findings(spec, segs, [0], record={}, legacy=frozen,
                                                     env={})
    assert hard, "冻着的老片改了一个字就要重量"


def test_check_narration落账_dry_run读回来(tmp_path, monkeypatch):
    monkeypatch.setattr(reel, "NARRATION_CHECKS_DIR", tmp_path)
    spec, segs = _zverev_spec()
    path = reel.write_narration_record(spec["slug"], segs, {0: 11.4}, voice="v", rate="+6%",
                                       backend="azure")
    assert path.parent == tmp_path and path.name == "zz-new-laver-cup-2026.json"
    record = reel.load_narration_record(spec["slug"])
    assert record[reel.narration_fingerprint(segs[0])]["spoken"] == 11.4
    hard, _soft, ok = reel.narration_check_findings(spec, segs, [0], legacy={}, env={})
    assert not hard and ok


def test_误差带那道闸接在dry_run里_check_narration落账():
    src = inspect.getsource(reel.main)
    dry = src[src.index("if sure:"):]
    dry = dry[:dry.index("density_hint = ")]
    assert "narration_check_findings(" in dry and "return 1" in dry.split("if n_hard:")[1]
    check = src[src.index("if args.check_narration:"):]
    check = check[:check.index("if args.dry_run:")]
    assert "write_narration_record(" in check
    # render 的旁白闸和认账用同一个容差
    assert "NARRATION_OVER_TOL" in inspect.getsource(reel.narration_overruns)
    # runner 的 mode=narration 把账提交回分支（沙箱连不上 edge-tts）
    yml = WORKFLOW.read_text(encoding="utf-8")
    step = yml[yml.index("- name: narration — 只查旁白装不装得下"):]
    step = step[:step.index("\n      - name:")]
    assert "data/narration_checks/" in step and "push_with_rebase_retry" in step
    assert "exit $rc" in step, "装不下（rc=1）的那一趟也要落账，然后照样红"


def test_旁白没量过真TTS的豁免表只许减():
    legacy = reel.legacy_narration_unchecked()
    assert legacy, "豁免表读不到——路径或键名写错了"
    specs = {str(_load(p).get("slug") or p.stem): _load(p) for p in REELS}
    stale = []
    for slug, fingerprint in legacy.items():
        spec = specs.get(slug)
        if spec is None or (spec.get("_production") or {}).get("status") == "ready_for_render":
            stale.append(f"{slug}（spec 没了／是自动 spec）")
            continue
        segs = _segments(spec)
        if reel.spec_narration_fingerprint(segs) != fingerprint:
            stale.append(f"{slug}（旁白改过了，豁免已经不认）")
            continue
        hard, _soft, _ok = reel.narration_check_findings(spec, segs, _tight(segs),
                                                         legacy={}, env={})
        if not hard:
            stale.append(f"{slug}（已经量过账／不在误差带里了）")
    assert not stale, "从 data/legacy_narration_unchecked.json 删掉：" + "、".join(stale)
    assert len(legacy) <= 299


def test_豁免表外的手写spec误差带里的段都量过():
    bad = []
    for path in REELS:
        spec = _load(path)
        try:
            segs = _segments(spec)
        except reel.ReelError:
            continue
        hard, _soft, _ok = reel.narration_check_findings(spec, segs, _tight(segs), env={})
        bad += [f"{path.stem}: {h.strip()[:80]}" for h in hard]
    assert not bad, "\n".join(bad)


# ═══════════════════════════ ④ alphamerge：蒙版缩成裁框尺寸 ═══════════════════════════

@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="没有 ffmpeg")
def test_蒙版和裁框差一行也能alphamerge(tmp_path):
    """safiullin-bu-hangzhou-2026-qf：蒙版 424×108、裁框 424×109，ffmpeg 当场拒掉
    （run 36323549463）。真跑一遍 ffmpeg：缩过的能过，老写法（不缩）照样拒——两头都钉。"""
    mask = tmp_path / "mask.mkv"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=white:s=424x108:d=0.2:r=25", "-pix_fmt", "gray",
                    "-c:v", "ffv1", str(mask)], check=True)
    x0, y0, x1, y1 = 98, 920, 522, 1029                   # 424×109
    bw, sh = 566, 146

    def run(patch: str) -> subprocess.CompletedProcess:
        graph = "[0:v]split=2[m][wb];" + patch + "[m][b]overlay=0:800[v]"
        return subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             "testsrc=s=1920x1080:d=0.2:r=25", "-filter_complex", graph, "-map", "[v]",
             "-frames:v", "3", "-f", "null", "-"], capture_output=True, text=True)

    good = run(reel.masked_board_patch(x0, y0, x1, y1, str(mask), bw, sh))
    assert good.returncode == 0, good.stderr[-600:]
    old = (f"[wb]crop={x1 - x0}:{y1 - y0}:{x0}:{y0},format=rgb24[bc];"
           f"movie='{reel._escape(mask)}':dec_threads=1,format=gray[mask];"
           f"[bc][mask]alphamerge,scale={bw}:{sh}:flags=lanczos[b];")
    assert run(old).returncode != 0, "老写法居然过了——那这条判据就没钉住那次失败"


def test_两处回贴都走同一个蒙版滤镜():
    src = inspect.getsource(reel)
    assert src.count("[bc][mask]alphamerge") == 1, "蒙版滤镜只许有 masked_board_patch 一份"
    assert src.count("masked_board_patch(x0, y0, x1, y1, seg.score_inset_mask, bw, sh)") == 2


# ═══════════════════════════ ⑤ 采访：已知带片尾板的源 ═══════════════════════════

def _interview(**extra) -> dict:
    return {"slug": "zz-new-laver-cup-interview", "start": 0.0, "end": 286.7,
            "url": "https://www.youtube.com/watch?v=zz",
            "source_verification": {"source": "Laver Cup"}, **extra}


#: alcaraz-fritz-laver-cup-2026-interview 第一版：end 286.7，最后一句「Carlos Alcaraz.」
#: 之后 283.7 起是拉沃尔杯片尾板（1b0b65ee5 的 `_end_why`）。
SPANS = [(270.0, 271.0, "and"), (282.9, 283.5, "Alcaraz.")]


def test_已知带片尾板的源_话音后空太久_手写的红():
    red, note = quiet_tail_problem(_interview(), SPANS, auto=False, legacy=frozenset())
    assert red and not note and "Laver Cup" in red and "_end_why" in red, (red, note)
    tv = _interview(source_verification={}, url="https://www.tennistv.com/videos/1/x")
    assert end_board_source(tv) == "Tennis TV"
    assert quiet_tail_problem(tv, SPANS, auto=False, legacy=frozenset())[0]
    # 认领、自动、冻着的、别家源：只报
    for spec, kw in ((_interview(_end_why="看过：那三秒是全场起立"), {"auto": False}),
                     (_interview(_end_board_ok="板上有他要的话"), {"auto": False}),
                     (_interview(), {"auto": True}),
                     (_interview(source_verification={"source": "US Open"}), {"auto": False})):
        red, _note = quiet_tail_problem(spec, SPANS, legacy=frozenset(), **kw)
        assert red is None, spec
    red, note = quiet_tail_problem(_interview(), SPANS, auto=False,
                                   legacy=frozenset({"zz-new-laver-cup-interview"}))
    assert red is None and "legacy" in note
    # 话音一落就收的（≤1.5 秒）不报
    assert quiet_tail_problem(_interview(end=284.5), SPANS, auto=False,
                              legacy=frozenset()) == (None, None)
    assert set(END_BOARD_SOURCES) == {"Laver Cup", "Tennis TV"}


def test_采访预检把片尾板这一条接成红():
    import interview_preflight as ip  # noqa: PLC0415
    src = inspect.getsource(ip.subtitle_findings)
    assert "quiet_tail_problem(" in src and "problems.append" in src.split("quiet_tail_problem(")[1]


def _interview_specs() -> dict[str, dict]:
    out = {}
    for path in sorted((ROOT / "specs" / "interviews").glob("*.json")):
        if path.name.endswith(".draft.json"):
            continue
        spec = _load(path)
        out[str(spec.get("slug") or path.stem)] = spec
    return out


def _tail_verdict(spec: dict, legacy: frozenset):
    import interview_preflight as ip  # noqa: PLC0415
    from interview_tail import cache_word_spans  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as td:
        if not ip._materialize_captions(str(spec.get("slug")), Path(td)):
            return None
        return quiet_tail_problem(spec, cache_word_spans(Path(td), spec), legacy=legacy)


def test_片尾板那条的豁免表只许减_全库零误报():
    from interview_spec_gates import legacy  # noqa: PLC0415
    frozen = legacy("end_board_quiet_tail")
    assert frozen, "豁免表读不到"
    specs = _interview_specs()
    if not (ROOT / "output" / "interviews").is_dir():
        pytest.skip("这个检出里没有 output/interviews（字幕缓存）")
    stale = [s for s in frozen if s not in specs
             or not ((_tail_verdict(specs[s], frozenset()) or (None,))[0])]
    assert not stale, f"这些已经不红了，从 legacy_interview_gates.json 删掉：{stale}"
    assert len(frozen) <= 2
    bad = [slug for slug, spec in specs.items()
           if ((_tail_verdict(spec, frozen) or (None,))[0])]
    assert not bad, bad


# ═══════════════════════════ ⑥ 钩子：送别人进决赛不算赛果 ═══════════════════════════

def test_送别人进决赛不算交代赛果():
    """账号所有者 2026-09-25 看 bucsa-noskova「首盘5比2被追平／直落两盘送捷克进决赛」：
    「封面钩子文案没交代赛果啊」（872c6dab6）。"""
    assert not T.has_match_result("直落两盘送捷克进决赛")
    assert not T.has_match_result("77分钟送德国晋级")
    assert T.has_match_result("2比0胜布克沙进决赛"), "改好的那版"
    for line in ("这次送走卫冕冠军", "卫冕冠军被她送走", "首轮送走2024冠军",
                 "淘汰头号种子送中国队进决赛", "直落两盘进半决赛", "直落两盘"):
        assert T.has_match_result(line), line
    spec = _load(ROOT / "specs" / "reels" / "bucsa-noskova-bjk-cup-2026-sf.json")
    spec["cover"] = dict(spec["cover"], hook="首盘5比2被追平\n直落两盘送捷克进决赛")
    spec["cover"].pop("_hook_shape_why", None)
    assert T.hook_result_problem(spec, legacy={}), "被否的那版必须红"
    spec["cover"]["hook"] = "首盘5比2被追平\n2比0胜布克沙进决赛"
    assert T.hook_result_problem(spec, legacy={}) is None


def test_钩子里的N号种子只报不拦_那句话只有会话转述():
    """账号所有者 09-26 那句（「封面别说淘汰八号种子，说挺进 8 强」）只以会话转述的形式留在
    61e62b8a5 的提交说明里——同一段里另一句抽帧的话，CLAUDE.md 记的原话和提交说明的
    转述不一样，说明这一段是转述。按 09-27 他选的口径，转述出来的规则只进清单自查，
    不做闸（`tennis-owner-taste`「〔推断·只自查，永不做成闸〕」）。钩子本身照结果闸判。"""
    spec = {"slug": "zz-seed", "cover": {"eyebrow": "赛场之上",
                                         "hook": "只差一分被拖进决胜盘\n他还是淘汰了八号种子"}}
    assert T.hook_result_problem(spec, legacy={}) is None
    assert T.hook_jargon_problem(spec, legacy={}) is None
    assert TX.hook_identity_note(spec), "只报的那条还在"


# ═══════════════════════════ ⑦ 多源认领要带宽高帧率 ═══════════════════════════

def _two_sources(claim) -> dict:
    return {"slug": "zz-new-withdrawal-story", "sources": {"main": "M", "xvid": "X"},
            "segments": [{"source": "main", "start": 1.0, "end": 5.0, "narration": "一句。"},
                         {"source": "xvid", "start": 1.0, "end": 5.0, "narration": "又一句。"}],
            "_no_probe_why": claim}


MAIN_PROBE = {"M": {"url": "M", "width": 1920, "height": 1080, "fps": "25/1", "fps_value": 25.0}}


def test_多源认领不带宽高帧率_手写的红_带了几何照跑():
    """sinner-beijing-withdrawal-2026（97ebe27a2）的 xvid 480×852 没 probe：认领一句话
    就把几何预演整层关掉，render 下完源片才红（run 36133328467）。"""
    hard, _soft = ps.coverage_findings(_two_sources({"xvid": "X 上的视频，probe 不了"}),
                                       MAIN_PROBE, legacy={}, env={})
    assert len(hard) == 1 and "没写宽高帧率" in hard[0], hard
    geo = {"xvid": {"why": "X 上的视频，probe 不了", "width": 480, "height": 852, "fps": "30/1"}}
    spec = _two_sources(geo)
    hard, soft = ps.coverage_findings(spec, MAIN_PROBE, legacy={}, env={})
    assert not hard and any("已认领" in s for s in soft)
    g_hard, _ = ps.geometry_findings(spec, MAIN_PROBE, reel.check_sources_match, reel.ReelError)
    assert g_hard and "check_sources_match" in g_hard[0], "几何预演要拿认领的宽高照跑"
    same = _two_sources({"xvid": dict(geo["xvid"], width=1920, height=1080, fps="25/1")})
    assert ps.geometry_findings(same, MAIN_PROBE, reel.check_sources_match, reel.ReelError) \
        == ([], [])
    # 自动 spec、单源：只报／不要求
    auto = dict(_two_sources({"xvid": "probe 不了"}), _production=AUTO)
    assert ps.coverage_findings(auto, MAIN_PROBE, legacy={}, env={})[0] == []
    single = {"slug": "zz-one", "source_url": "Y", "_no_probe_why": {"": "probe 不了"},
              "segments": [{"start": 1.0, "end": 5.0, "narration": "一句。"}]}
    assert ps.coverage_findings(single, {}, legacy={}, env={})[0] == []
    # 写坏的几何不算写了
    for bad in ({"why": "x", "width": "宽", "height": 852, "fps": "30/1"},
                {"why": "x", "width": 480, "height": 852}):
        assert ps.claimed_geometry(bad) is None


# ═══════════════════════════ ⑧ 开着回贴、probe 没量板 ═══════════════════════════

def test_开着回贴而probe没量板_手写的红_命令带url和框():
    spec = {"slug": "zz-new-singapore-2026-r2", "topbar": {"line1": "2026 WTA500 新加坡 1/8决赛"},
            "cover": {"eyebrow": "赛场之上"}, "scorebox": [90, 870, 550, 980],
            "source_url": "https://www.youtube.com/watch?v=zz",
            "segments": [{"start": 5.0, "end": 9.0, "score_inset": True, "narration": "一句。"}]}
    segs = _segments(spec)
    probe = {"url": spec["source_url"], "duration": 600.0, "clip_from": 120.0}
    hard, _soft = pb.board_findings(spec, segs, {spec["source_url"]: probe},
                                    {"": spec["source_url"]}, profile="wta", tail=reel.SEG_FADE)
    assert len(hard) == 1, hard
    assert ("mode=probe -f slug=zz-new-singapore-2026-r2 -f url=https://www.youtube.com/watch?v=zz"
            in hard[0] and "-f clip_from=120.0" in hard[0]
            and "-f scorebox=90,870,550,980" in hard[0]), hard[0]


def test_没量板的豁免表只许减():
    legacy = pb.legacy_board_unprobed()
    assert legacy, "豁免表读不到"
    specs = {str(_load(p).get("slug") or p.stem): _load(p) for p in REELS}
    probes = _disk_probes()
    stale = []
    for slug, keys in legacy.items():
        spec = specs.get(slug)
        if spec is None or (spec.get("_production") or {}).get("status") == "ready_for_render":
            stale.append(f"{slug}（spec 没了／是自动 spec）")
            continue
        urls = reel.spec_sources(spec)
        segs = _segments(spec)
        for key in keys:
            if key not in urls or not any(s.source == key and s.score_inset for s in segs):
                stale.append(f"{slug}/{key}（源没了或回贴关了）")
            elif probes and (probes.get(urls[key]) or {}).get("board"):
                stale.append(f"{slug}/{key}（已经重跑过 probe，有 board 了）")
    assert not stale, "从 data/legacy_board_unprobed.json 删掉：" + "、".join(stale)
    assert len(legacy) <= 78 and sum(map(len, legacy.values())) <= 84


def test_豁免表外的手写spec开着回贴的源都量过板():
    probes = _disk_probes()
    if not probes:
        pytest.skip("这个检出里没有 output/*/reel/*/probe.json")
    bad = []
    for path in REELS:
        spec = _load(path)
        try:
            segs = _segments(spec)
            profile = reel.scoreboard_profile(spec, segs)
        except reel.ReelError:
            continue
        urls = reel.spec_sources(spec)
        hard, _soft = pb.board_findings(spec, segs, {u: probes[u] for u in urls.values()
                                                     if u in probes},
                                        urls, profile=profile, tail=reel.SEG_FADE)
        bad += [f"{path.stem}: {h.strip()[:90]}" for h in hard if "早于逐帧量板" in h]
    assert not bad, "\n".join(bad)


def test_全库写过源片末尾零误报():
    probes = _disk_probes()
    if not probes:
        pytest.skip("这个检出里没有 output/*/reel/*/probe.json")
    bad = []
    for path in REELS:
        spec = _load(path)
        try:
            segs = _segments(spec)
        except reel.ReelError:
            continue
        urls = reel.spec_sources(spec)
        over = reel.segments_over_source_end(
            segs,
            {s.source: (float(p["duration"]) if (p := probes.get(urls.get(s.source, "")))
                        and p.get("duration") else None) for s in segs},
            {s.source: reel._probe_fps_value(probes.get(urls.get(s.source, ""))) for s in segs},
            slug=str(spec.get("slug") or ""))
        bad += [f"{path.stem}: {line.strip()[:80]}" for line in over]
    assert not bad, "\n".join(bad)


def test_自动spec和手写spec的区分用的是同一个口径():
    """八道闸里「自动 spec」全认 `_production.status == ready_for_render`（采访线认
    `taste_gates.interview_is_auto`），别哪一道自己发明一个。"""
    assert re.search(r'_production.*ready_for_render', inspect.getsource(
        reel.narration_check_findings))
    assert "ready_for_render" in inspect.getsource(pb.board_findings)
    assert "is_auto(spec)" in inspect.getsource(ps.coverage_findings)
