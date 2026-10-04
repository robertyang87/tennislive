"""比分板回贴：probe 那一趟逐帧量板，`--dry-run` 0.2 秒预判 render 会在哪一段红。

来路：2026-09-27 全库返工盘点，比分板回贴是「赛场之上」头号返工来源（22 次返工、
11 趟 render 红在蒙版那一步），而每一次都是渲完把成片拉回来才发现的——判「这一段
有没有板」要解源片，dry-run 原来看不到。见 tools/probe_board.py 的 docstring。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_match_reel as b  # noqa: E402
import probe_board as pb  # noqa: E402

COURT = (123, 167, 128)
ATP_BOX = pb.CALIBRATED["atp"][0]
USO_BOX = pb.CALIBRATED["us-open"][0]


def _frame(*, atp: bool = False, wta: bool = False) -> np.ndarray:
    """一帧 1920×1080：球场绿底，按标定框画一块合成的 ATP / WTA 板（颜色取两家判据
    docstring 里量出来的那几个值）。ATP 板右缘在带内 300（盘分蓝 220~259），
    WTA 板有薄荷绿局分格（200~239），右缘实际画在 296；必须量图形边界，
    不靠「最后一列薄荷绿 +56」裁断更宽的合成图形。"""
    f = np.zeros((1080, 1920, 3), np.uint8)
    f[:] = COURT
    if atp:
        x0, y0, _x1, y1 = ATP_BOX
        f[y0:y1, x0:x0 + 220] = (6, 16, 36)
        f[y0:y1, x0 + 220:x0 + 260] = (22, 16, 248)
        f[y0:y1, x0 + 260:x0 + 300] = (38, 60, 50)
    if wta:
        x0, y0, _x1, y1 = pb.CALIBRATED["wta"][0]
        f[y0:y1, x0:x0 + 200] = (55, 95, 66)
        f[y0:y1, x0 + 200:x0 + 240] = (21, 255, 171)
        f[y0:y1, x0 + 240:x0 + 296] = (55, 95, 66)
    return f


def _board(profile: str, runs: list, *, box=None, fps: int = 5, t0: float = 0.0) -> dict:
    """手搓一份 probe.json 的 `board`：runs = [(帧数, raw 绝对坐标 | -1 | None, anchored | None)]。"""
    frames = sum(n for n, _r, _a in runs)
    box = box or pb.CALIBRATED[profile][0]
    present = sum(n for n, r, _a in runs if r is not None)
    unresolved = sum(n for n, r, _a in runs if r is not None and r < 0)
    return {"version": 1, "fps": fps, "t0": t0, "frames": frames,
            "scans": [{"box": list(box), "frames": frames,
                       "profiles": {profile: {"present": present, "unresolved": unresolved,
                                              "runs": [list(r) for r in runs]}}}]}


def _atp_spec(segments: list, **kw) -> dict:
    # 一段都没开回贴的话 parse_segments 会把 scorebox 判成死键——补一段开着的，
    # 放在 0~0.4s（下面每一份手搓的数据里板在那儿都在，不会自己触发第一条闸）
    if not any(s.get("score_inset") is True for s in segments):
        segments = segments + [{"start": 0.0, "end": 0.4, "score_inset": True}]
    return {"slug": "brand-new-hangzhou-2026-r1", "topbar": {"line1": "2026 ATP250 杭州 第二轮"},
            "cover": {"eyebrow": "赛场之上"}, "scorebox": list(ATP_BOX), "source_url": "u",
            "segments": segments, **kw}


def _findings(spec: dict, board: dict | None, profile: str) -> tuple[list[str], list[str]]:
    segments = b.parse_segments(spec, {"": Path("a.mp4")}, "")
    probe = {"url": "u", "duration": 600.0}
    if board is not None:
        probe["board"] = board
    return pb.board_findings(spec, segments, {"u": probe}, {"": "u"},
                             profile=profile, tail=b.SEG_FADE)


def _seg(start, end, inset, **kw):
    s = {"start": start, "end": end, "score_inset": inset, **kw}
    if inset is False:
        s.setdefault("_score_inset_why", "回放")
    return s


# 0~5s 板在（右缘 398），5~10s 板不在——5 fps
ON_THEN_OFF = [(25, 398, 398), (25, None, None)]


def test_开着回贴却一帧板都没有_dry_run就红():
    """`prozorova-eala` 第 13 段（run 36020126044）、`alcaraz-mensik-doubles` 第 9 段
    （run 36197683115）那个形状：开着 score_inset 的段里一帧板都没有，render 的逐帧
    蒙版在源片下完之后才报。现在 probe 量过，dry-run 当场红。"""
    spec = _atp_spec([_seg(0.5, 4.5, True), _seg(5.5, 9.5, True)])
    hard, _soft = _findings(spec, _board("atp", ON_THEN_OFF), "atp")
    assert len(hard) == 1 and "第 2 段" in hard[0] and "一帧板都没认出" in hard[0], hard
    # 板只在后半段淡出的那一段不算（渲染时自动不贴，09-24 的规矩）
    spec = _atp_spec([_seg(3.0, 8.0, True)])
    hard, _soft = _findings(spec, _board("atp", ON_THEN_OFF), "atp")
    assert hard == []


def test_写着不贴而板连着在画面里_手写的新spec硬():
    """`osaka-mertens` 第 ② 段（64f8dbaf）：写着 false，板要到 0.88 秒后才撤，居中窗口
    露出半截板、名字被裁掉。现在「板连着在 ≥ 0.8 秒」手写的新 spec 当场红。"""
    spec = _atp_spec([_seg(0.5, 4.5, False), _seg(5.5, 9.5, False)])
    hard, _soft = _findings(spec, _board("atp", ON_THEN_OFF), "atp")
    assert len(hard) == 1 and "第 1 段" in hard[0] and "写着不贴" in hard[0], hard

    # 认领了 → 只报，而且要把认领的理由打出来
    spec = _atp_spec([_seg(0.5, 4.5, False, _board_on_screen_why="比赛已经结束，顶栏有终局比分")])
    hard, soft = _findings(spec, _board("atp", ON_THEN_OFF), "atp")
    assert hard == [] and any("已认领" in s and "顶栏有终局比分" in s for s in soft)

    # 豁免表里的老 spec、自动产的 spec → 只报不拦
    legacy = sorted(pb.legacy_board_on_screen())[0]
    for spec in (_atp_spec([_seg(0.5, 4.5, False)], slug=legacy),
                 _atp_spec([_seg(0.5, 4.5, False)], _production={"status": "ready_for_render"})):
        hard, soft = _findings(spec, _board("atp", ON_THEN_OFF), "atp")
        assert hard == [] and any("写着不贴" in s for s in soft), spec.get("slug")

    # 板只闪了 0.6 秒（冷开场头上淡出的残影）→ 不提；整幅铺进来的段原板本来就在画面里 → 不提
    flicker = [(3, 398, 398), (47, None, None)]
    hard, soft = _findings(_atp_spec([_seg(0.0, 9.0, False)]), _board("atp", flicker), "atp")
    assert hard == [] and not any("写着不贴" in s for s in soft)
    spec = _atp_spec([_seg(0.5, 4.5, False, fit="full_source")])
    hard, soft = _findings(spec, _board("atp", ON_THEN_OFF), "atp")
    assert hard == [] and not any("写着不贴" in s for s in soft)


def test_连着在的门槛和render认为值得贴的那一档是同一个数():
    """`ON_SCREEN_MIN_S` 就是 render 自己的 `BOARD_SPAN_MIN`（「短于这个的在场片段不值得贴」）。
    两个数分叉的样子是 dry-run 逼人去贴一段 render 自己都不贴的闪烁。"""
    assert pb.ON_SCREEN_MIN_S == b.BOARD_SPAN_MIN


def _uso_spec(segments: list) -> dict:
    return {"slug": "new-us-open-2027-r1", "layout": "band",
            "topbar": {"line1": "2027 美网 第一轮"}, "cover": {"eyebrow": "赛场之上"},
            "scorebox": list(USO_BOX), "source_url": "u", "segments": segments}


def test_美网带式量不出几何或板比框宽_dry_run就红():
    """8 趟美网 run 红在 scoreboard_geometry（`rybakina-sabalenka` 8a523097 等）：
    板在、右缘一帧都量不出 → 「no stable geometry」；量到的板比框宽 →
    「Verified graphic exceeds source box」。两种都是 probe 的数一对就知道的。"""
    x1 = USO_BOX[2]
    wide = [(25, x1 + 10, x1 + 10)]
    hard, _ = _findings(_uso_spec([_seg(0.5, 4.5, True)]), _board("us-open", wide), "us-open")
    assert len(hard) == 1 and "exceeds source box" in hard[0], hard
    blind = [(25, -1, None)]
    hard, _ = _findings(_uso_spec([_seg(0.5, 4.5, True)]), _board("us-open", blind), "us-open")
    assert len(hard) == 1 and "no stable" in hard[0], hard
    fits = [(25, x1 - 40, x1 - 40)]
    hard, _ = _findings(_uso_spec([_seg(0.5, 4.5, True)]), _board("us-open", fits), "us-open")
    assert hard == []


def test_右缘量不出或x1写窄了_巡回赛转播只报():
    """ATP/WTA/金杯的 x1 只是提示：有签名色撑着的帧照量到的贴，没撑着的按 x1 截——
    render 不会红，所以只报；但要报出来，别让「最右那一列被截」不吭声。"""
    x1 = ATP_BOX[2]
    runs = [(10, x1 + 60, x1 + 60), (15, -1, None)]
    hard, soft = _findings(_atp_spec([_seg(0.5, 4.5, True)]), _board("atp", runs), "atp")
    assert hard == []
    assert any("右缘量不出" in s for s in soft), soft
    assert any("会按 x1 截" in s and str(x1 + 60) in s for s in soft), soft


def test_没有数据或者框对不上_这一层只报没查():
    """框对不上、量板失败：只报「没查」，**不许不吭声**——「没查」和「查过没问题」在
    dry-run 里要长得不一样。老 probe（逐帧量板之前）而这一段开着回贴：2026-09-28 起
    手写的新 spec 红（带重跑 probe 的命令），见 `tests/test_small_gates.py`。"""
    spec = _atp_spec([_seg(5.5, 9.5, True)])
    for board, word in ((_board("atp", ON_THEN_OFF, box=(98, 870, 519, 980)), "对不上"),
                        ({"version": 1, "error": "ffmpeg 解板失败"}, "ffmpeg 解板失败")):
        hard, soft = _findings(spec, board, "atp")
        assert hard == [] and any(word in s for s in soft), (word, soft)
    hard, soft = _findings(spec, None, "atp")
    assert len(hard) == 1 and "早于逐帧量板" in hard[0] and "mode=probe" in hard[0], hard
    # 自动产的 spec 照旧只报
    hard, soft = _findings(_atp_spec([_seg(5.5, 9.5, True)],
                                     _production={"status": "ready_for_render"}), None, "atp")
    assert hard == [] and any("早于逐帧量板" in s for s in soft), soft


def test_probe_dry_run真的接上了回贴那一层(monkeypatch):
    """判据接没接上，不查源码里有没有那一行——真跑一遍 `probe_dry_run`。"""
    probe = {"url": "u", "duration": 600.0, "width": 1920, "height": 1080,
             "scene_cuts": [], "point_ends": [], "silent_audio": [],
             "board": _board("atp", ON_THEN_OFF)}
    monkeypatch.setattr(b, "claim_probes", lambda spec: ({"u": (Path("x"), probe)}, []))
    bad = _atp_spec([_seg(0.5, 4.5, True), _seg(5.5, 9.5, True)])
    assert b.probe_dry_run(bad, b.parse_segments(bad, {"": Path("a.mp4")}, "")) is True
    good = _atp_spec([_seg(0.5, 4.5, True), _seg(5.5, 9.5, False)])
    assert b.probe_dry_run(good, b.parse_segments(good, {"": Path("a.mp4")}, "")) is False


def test_逐帧量板用的是render那一套判据_合成帧量得出板在哪(tmp_path):
    """纯函数那一层：合成帧喂进 `scan_frames`，ATP 板量到 398、WTA 板量到 386，
    别家判据在这两种板上一帧都不认——而 RLE 存进 probe.json 再读回来一字不差。"""
    plan = pb.plan_boxes(None, pb.CALIBRATED_SOURCE)
    ox = min(box[0] for _p, box in plan)
    oy = min(box[1] for _p, box in plan)
    right = max(box[0] + pb.band_width(p, box, 1920) for ps, box in plan for p in ps)
    bottom = max(box[3] for _p, box in plan)
    frames = ([_frame(atp=True)] * 3 + [_frame()] * 2 + [_frame(wta=True)] * 2)
    scans = pb.scan_frames(iter(f[oy:bottom, ox:right] for f in frames), plan, 1920, (ox, oy))
    got = {(tuple(e["box"]), p): pb.frames_of(json.loads(json.dumps(e)), p)
           for e in scans for p in e["profiles"]}
    assert got[(ATP_BOX, "atp")] == [(398, 398)] * 3 + [None] * 4
    assert got[(pb.CALIBRATED["wta"][0], "wta")] == [None] * 5 + [(386, 386)] * 2
    others = [k for k, v in got.items() if k[1] not in ("atp", "wta") and any(v)]
    assert others == [], others


def _band(frame: np.ndarray, profile: str) -> np.ndarray:
    x0, y0, _x1, y1 = pb.CALIBRATED[profile][0]
    return frame[y0:y1, x0:x0 + pb.band_width(profile, pb.CALIBRATED[profile][0], 1920)]


def test_measure分得开有签名色撑着的右缘和没撑着的():
    """render 在 x1 之外贴不贴，看的是这一帧有没有签名色撑着（`beyond_hint`）。
    probe 要把两个数分开存，dry-run 才推得出「哪几帧会按 x1 截」：

    - ATP 板右边接一面深色挡板：判据不封顶会一路读到 500，有盘分蓝撑着的只到 324
      （最后一列蓝 259 ＋1 ＋小分格 64）
    - 深色一路连到带的右头：右缘量不出（-1），也没有撑着的
    - WTA 开局还没有局分（没有薄荷绿）：板在、量得到 300，但没撑着——render 按 x1 截
    """
    wall = _frame(atp=True)
    x0, y0, _x1, y1 = ATP_BOX
    wall[y0:y1, x0 + 300:x0 + 500] = (6, 16, 36)
    assert pb.measure("atp", _band(wall, "atp")) == (500, 324)
    wall[y0:y1, x0 + 300:] = (6, 16, 36)
    assert pb.measure("atp", _band(wall, "atp")) == (-1, None)
    no_mint = _frame()
    wx0, wy0, _wx1, wy1 = pb.CALIBRATED["wta"][0]
    no_mint[wy0:wy1, wx0:wx0 + 300] = (55, 95, 66)
    assert pb.measure("wta", _band(no_mint, "wta")) == (300, None)
    assert pb.measure("atp", _band(_frame(), "atp")) is None


def _write_video(path: Path, frames: list[np.ndarray], fps: int = 5) -> None:
    h, w = frames[0].shape[:2]
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pixel_format", "rgb24",
         "-video_size", f"{w}x{h}", "-framerate", str(fps), "-i", "-",
         "-c:v", "ffv1", "-pix_fmt", "bgr0", str(path)],
        input=b"".join(f.tobytes() for f in frames), capture_output=True)
    assert proc.returncode == 0, proc.stderr[-400:]


def test_probe模式把板逐帧量进probe_json(tmp_path, monkeypatch):
    """probe 那一趟真的把 `board` 写进 probe.json——真解一条合成源片（前 2 秒有 ATP 板、
    后 1 秒没有），其余下载/切点/缩略图墙这些要网络和大源片的步骤打桩。"""
    source = tmp_path / "src.mkv"
    _write_video(source, [_frame(atp=True)] * 10 + [_frame()] * 5)
    monkeypatch.setattr(b, "download", lambda url, dest, **kw: source)
    monkeypatch.setattr(b, "scene_changes", lambda *a, **kw: [])
    monkeypatch.setattr(b, "contact_sheet", lambda *a, **kw: [])
    monkeypatch.setattr(b, "fetch_captions", lambda *a, **kw: None)
    monkeypatch.setattr(b, "measure_point_ends", lambda *a, **kw: ([], None, None))
    monkeypatch.setattr(b, "silent_audio_spans", lambda *a, **kw: None)
    out = tmp_path / "probe"
    monkeypatch.setattr(sys, "argv", ["build_match_reel.py", "probe", "--url", "u",
                                      "--outdir", str(out)])
    assert b.main() == 0
    board = json.loads((out / "probe.json").read_text(encoding="utf-8"))["board"]
    assert board["fps"] == pb.PROBE_FPS and board["frames"] == 15, board
    atp = next(e for e in board["scans"] if tuple(e["box"]) == ATP_BOX)
    edges = pb.frames_of(atp, "atp")
    assert edges[:10] == [(398, 398)] * 10 and edges[10:] == [None] * 5

    # 这一趟给的框和标定带都对不上 → 收的时候补扫一份，五家判据都跑
    extra = pb.BoardScan(source, (1920, 1080)).finish("1483,647,1920,850")
    assert [e["box"] for e in extra["scans"]][-1] == [1483, 647, 1920, 850]
    assert set(extra["scans"][-1]["profiles"]) == set(pb.CALIBRATED)


def test_量板失败不许把probe带崩_但要出声并落进probe_json(tmp_path, capsys):
    board = pb.BoardScan(tmp_path / "missing.mkv", (1920, 1080)).finish("")
    assert set(board) == {"version", "error"}, board
    assert "没量成" in capsys.readouterr().out
    skipped = pb.BoardScan(tmp_path / "missing.mkv", (1280, 720)).finish("")
    assert "skipped" in skipped


def _custom_box_has_probe(spec: dict, profile: str, probes=None, *, box=None, url=None) -> bool:
    """A custom box is valid only with a real same-source, same-profile scan."""
    if probes is None:
        probes, missing = b.probes_for_spec(spec)
        if missing:
            return False
    urls = spec.get("sources") or {"": spec.get("source_url")}
    owned = {url: [box]} if url is not None else pb.scoreboxes_by_url(spec, urls)
    for source_url, boxes in owned.items():
        probe = probes.get(source_url) or {}
        board = probe.get("board") or {}
        if probe.get("url") != source_url or not board.get("frames"):
            return False
        for source_box in boxes:
            scan, _ = pb._pick_scan(board, source_box, profile)
            if not scan or not scan.get("frames") or not (scan["profiles"][profile].get("runs")):
                return False
    return bool(owned)


def test_custom_scorebox_needs_matching_source_and_scan():
    box = [90, 870, 516, 984]
    spec = {"source_url": "https://example.test/source", "scorebox": box}
    probe = {"url": spec["source_url"], "board": _board("wta", [(5, 386, 386)], box=box)}
    assert _custom_box_has_probe(spec, "wta", {spec["source_url"]: probe})
    assert not _custom_box_has_probe(spec, "wta", {})
    assert not _custom_box_has_probe(spec, "atp", {spec["source_url"]: probe})
    wrong = json.loads(json.dumps(probe)); wrong["url"] = "https://example.test/different-cut"
    assert not _custom_box_has_probe(spec, "wta", {spec["source_url"]: wrong})
    wrong = json.loads(json.dumps(probe)); wrong["board"]["scans"][0]["box"][3] = 980
    assert not _custom_box_has_probe(spec, "wta", {spec["source_url"]: wrong})


def test_custom_segment_boxes_need_their_own_source_scan():
    official = [86, 827, 554, 988]
    supplement = [14, 964, 392, 1072]
    urls = {"official": "https://example.test/official", "supplement": "https://example.test/supplement"}
    spec = {"sources": urls, "scorebox": official, "segments": [
        {"source": "official", "score_inset": True},
        {"source": "supplement", "score_inset": True, "scorebox": supplement}]}
    probes = {urls["official"]: {"url": urls["official"], "board": _board("wta", [(5, 554, 554)], box=official)},
              urls["supplement"]: {"url": urls["supplement"], "board": _board("wta", [(5, 392, 392)], box=supplement)}}
    assert _custom_box_has_probe(spec, "wta", probes)
    assert not _custom_box_has_probe(spec, "wta", {urls["official"]: probes[urls["official"]]})
    wrong = json.loads(json.dumps(probes))
    wrong[urls["supplement"]]["board"] = wrong[urls["official"]]["board"]
    assert not _custom_box_has_probe(spec, "wta", wrong)  # Correct URL with the other source's box.
    wrong = json.loads(json.dumps(probes))
    wrong[urls["supplement"]]["url"] = urls["official"]
    assert not _custom_box_has_probe(spec, "wta", wrong)  # Correct box with the other source's URL.


def test_标定框和全库spec用的框对得上():
    """`CALIBRATED` 是全库 spec 量出来的，不是拍的——哪天某家转播换了框，这条先红，
    probe 就不会拿一条旧带去量新 spec（那样 dry-run 只会说「框对不上」，这一层白装）。"""
    from reel_facts import broadcast_profile, spec_tour, us_open_match_line  # noqa: PLC0415

    seen: dict[str, list[bool]] = {}
    for path in sorted((ROOT / "specs" / "reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        box = spec.get("scorebox") if isinstance(spec, dict) else None
        if not isinstance(box, list) or len(box) != 4:
            continue
        line1 = str((spec.get("topbar") or {}).get("line1", ""))
        if spec.get("layout") == "band":
            if not us_open_match_line(line1):
                continue
            prof = "us-open"
        else:
            prof = broadcast_profile(line1, str((spec.get("_production") or {}).get("event") or ""),
                                     spec_tour(spec))
        if prof not in pb.CALIBRATED:
            continue
        urls = spec.get("sources") or {"": spec.get("source_url")}
        for url, boxes in pb.scoreboxes_by_url(spec, urls).items():
            for source_box in boxes:
                seen.setdefault(prof, []).append(
                    any(pb.same_box(source_box, cal) for cal in pb.CALIBRATED[prof])
                    or _custom_box_has_probe(spec, prof, box=source_box, url=url))
    for prof in ("atp", "wta", "itf-bjk", "lavercup"):
        assert len(seen.get(prof, [])) >= 5, f"{prof} 一条 spec 都没扫到，判据的主语像是没了"
        assert all(seen[prof]), f"{prof} 有 spec 的 scorebox 既不在 CALIBRATED，也缺少同源自定义扫描"
    uso = seen.get("us-open", [])
    assert len(uso) >= 40 and sum(uso) >= 0.9 * len(uso), (sum(uso), len(uso))


def test_板在画面里却写着不贴_豁免表只许减():
    """豁免表自检：定规矩那天是 71 条（有 scorebox、至少一段不是 true 的 spec），只许减。
    它们的 probe 都早于逐帧量板、没数据可判，所以自检查的是「这道闸碰得到它」——
    某条已经全段 true 了，它就不该再占着豁免表。"""
    data = json.loads((ROOT / "data" / "legacy_board_on_screen.json").read_text(encoding="utf-8"))
    legacy = data["reels"]
    assert len(legacy) == len(set(legacy)), "豁免表里有重复的名字"
    assert len(legacy) <= 71, "豁免表只许减不许加（定规矩那天是 71 条）"
    assert pb.legacy_board_on_screen() == frozenset(legacy)
    for slug in legacy:
        path = ROOT / "specs" / "reels" / f"{slug}.json"
        assert path.is_file(), f"豁免表里的 {slug} 根本不存在"
        spec = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(spec.get("scorebox"), list), f"{slug} 没有 scorebox，这道闸碰不到它"
        touchable = [s for s in spec.get("segments") or []
                     if not (s.get("image") or s.get("title_card") or s.get("stat_card"))
                     and s.get("score_inset") is not True
                     and not isinstance(s.get("score_inset"), dict)]
        assert touchable, f"{slug} 已经全段回贴——从豁免表里把它删掉（只许减不许加）"


@pytest.mark.parametrize("given, extra", [
    ("98,920,519,1029", False),      # 和标定框对得上 → 不另扫
    ("1483,647,1920,850", True),     # 猜到了右上角 → 另扫一份，五家判据都跑
    ("", False),
])
def test_要扫哪些框(given, extra):
    box = tuple(int(v) for v in given.split(",")) if given else None
    plan = pb.plan_boxes(box, pb.CALIBRATED_SOURCE)
    assert len(plan) == sum(len(v) for v in pb.CALIBRATED.values()) + extra, plan
    if extra:
        assert plan[-1] == (tuple(pb.CALIBRATED), box)
    # 不是 1920×1080 的源片：标定带不适用，只扫这一趟给的框
    assert pb.plan_boxes(box, (1280, 720)) == ([] if box is None else [(tuple(pb.CALIBRATED), box)])
