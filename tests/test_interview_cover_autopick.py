"""赛后开麦：封面帧红了，render 就地扫、**自动换一格过闸＋是本人＋睁眼的**，接着出片。

来路（rework_audit_0928 第二类，账都是实的）：interview-clip **9 趟 run（7 条 slug，
46.5 runner-分钟）红在封面帧**，另有两条认错人／闭眼的推了出去才换
（tien-cobolli 97.0 是阿加西、ruud-cerundolo 245.0 低头闭眼，9ae8918f）。09-27 把封面
挪到转写和编码之前之后红得早了，可红了照样整趟作废——cobolli-mensik 那趟就地扫出的
第一名 29.4，正是人后来写进 spec 的那一格（23ed3bfb9），又等了一整趟。

判据分四组：
1. **真像素**：拿仓库里真发过的那几张海报（`tests/fixtures/faces/`）当源片的帧，
   走真的 `audit_poster(face=True)`——认错人、闭眼的那一格不换，挑本人睁眼的写进 spec
2. 机器换帧只认 `match` ＋ `open`（比终审严一档：这一帧没有人看过），而且认出来的人
   必须是封面文案点了名的（`expected_subject` 退回 winner 会落到对手身上：佩古拉亚军致辞）
3. 改写 spec 只动 `cover.frame_at`、`cover._why` 那一句标注和 `cover._frame_autopick`
   （全库 spec 逐条改一遍验）；人给原来那一帧写的认领挪进 `_frame_autopick.dropped`
4. 「提交成片」把换过的 spec 跟成片一起提交；撞车重放时别人改过 spec 就不覆盖
5. dispatch 之前的离线预检：已提交的扫描记录说 frame_at 不行就红，顺手报能换的那一格
"""
from __future__ import annotations

import copy
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import audit_interview_cover as auditor  # noqa: E402
import face_checks  # noqa: E402
import interview_cover_scan as scan  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "faces"
AGASSI = FIX / "tien-cobolli-poster-74235cea-agassi.jpg"
TIEN_OK = FIX / "tien-cobolli-poster-aa052bf0.jpg"
RUUD_CLOSED = FIX / "ruud-cerundolo-poster-9380e58f-eyes-closed.jpg"
RUUD_OK = FIX / "ruud-cerundolo-poster-bf53644c.jpg"
SPECS = ROOT / "specs" / "interviews"


@pytest.fixture
def model():
    try:
        return face_checks.load()
    except face_checks.ModelUnavailable as exc:
        if os.environ.get("CI"):
            pytest.fail(f"CI 上人脸模型必须在（ci.yml「备好人脸模型」那一步）：{exc}")
        pytest.skip(f"本机没有人脸模型（python tools/face_checks.py fetch）：{exc}")


def _memo_pixels(monkeypatch):
    """同一张图只量一次：Haar 和人脸模型都只看像素，按字节哈希缓存（一张 1~2 秒）。
    判定（`validate_result` / `problems_of` / `autopick_problem`）照走真的。"""
    real_analyze, real_face = auditor.analyze_poster, auditor.poster_face_model
    cache: dict = {}

    def key(path: Path, *extra) -> tuple:
        return (hashlib.sha256(Path(path).read_bytes()).hexdigest(), *extra)

    def analyze(poster):
        k = key(poster, "haar")
        if k not in cache:
            cache[k] = real_analyze(poster)
        return copy.deepcopy(cache[k])

    def face(poster, expected):
        k = key(poster, "face", expected)
        if k not in cache:
            cache[k] = real_face(poster, expected)
        return copy.deepcopy(cache[k])

    monkeypatch.setattr(auditor, "analyze_poster", analyze)
    monkeypatch.setattr(auditor, "poster_face_model", face)


class _FakeClip:
    """`run_scan` 要的那几样：源片已在手上、帧由 `frames(t)` 决定是哪一张真海报。"""
    SOURCE_FMT = "fmt"

    class NoFrameAt(RuntimeError):
        pass

    def __init__(self, frames, end: float, outdir: Path):
        self.frames, self.end, self.outdir = frames, end, outdir
        self.rendered: list[float] = []

    def yt_download(self, url, dest, fmt, spec):
        dest.write_bytes(b"src")
        return dest

    def probe_video_duration(self, _src):
        return self.end

    def _logo_filter(self, spec, src, out):
        return ""

    def canvas_page(self):
        import contextlib  # noqa: PLC0415
        return contextlib.nullcontext("page")

    def cover_poster(self, spec, src, out, logo="", *, at=None, dest=None, page=None):
        t = spec["cover"]["frame_at"] if at is None else at
        self.rendered.append(t)
        dest = dest or out / "poster.jpg"
        shutil.copy(self.frames(t), dest)
        return dest


def _spec_at(slug: str, frame_at: float, **extra) -> dict:
    spec = json.loads((SPECS / f"{slug}.json").read_text(encoding="utf-8"))
    spec["cover"]["frame_at"] = frame_at
    spec["cover"].pop("scan_window", None)
    spec["cover"].pop(scan.AUTOPICK_KEY, None)
    spec.update(extra)
    return spec


# ---------------------------------------------------------------- 一、真像素

@pytest.mark.parametrize(("slug", "bad_at", "bad", "good", "span", "want"), [
    # 鲁德发布会：推出去的 245.0 低头闭眼（EAR 0.097）。近处 ±2 秒全是闭眼，
    # 要靠整段粗扫找到 257 秒那一段正脸睁眼的——人后来换的是 257.2
    ("ruud-cerundolo-laver-cup-2026-presser", 245.0, RUUD_CLOSED, RUUD_OK, (255.0, 259.0), "闭眼"),
    # 勒纳·钱：推出去的 97.0 是阿加西（相似度 -0.004）。近处一格本人睁眼的就够
    ("tien-cobolli-laver-cup-2026-interview", 97.0, AGASSI, TIEN_OK, None, "不是本人"),
], ids=["鲁德闭眼", "阿加西"])
def test_真海报_认错人和闭眼的那一格不换_换上本人睁眼的(model, monkeypatch, tmp_path,
                                           slug, bad_at, bad, good, span, want):
    _memo_pixels(monkeypatch)
    def frames(t: float) -> Path:
        if span is None:    # 近处：97.0 本身和前一格是阿加西，97.4 起是本人
            return bad if t < 97.3 else good
        # 近处全闭眼；整段只在 span 里有正脸（其余是阿加西那种别人）
        return good if span[0] <= t <= span[1] else bad if abs(t - bad_at) <= 2.5 else AGASSI

    extra = ({"start": 0.0, "end": 114.2} if span is None
             else {"start": 240.0, "end": span[1] + 1.0})
    spec = _spec_at(slug, bad_at, **extra)
    spec["cover"]["scan_step"] = 0.4        # 近处 11 格——判的是挑法，不是步长
    spec_path = tmp_path / f"{slug}.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    outdir = tmp_path / slug
    outdir.mkdir()
    clip = _FakeClip(frames, end=spec["end"] + 5.0, outdir=outdir)

    assert scan.run_scan(spec, outdir, clip, keep_source=True, autopick=True,
                         spec_path=spec_path) == 0
    record = json.loads((outdir / scan.RECORD_NAME).read_text(encoding="utf-8"))
    bad_entry = scan.find_entry(record, bad_at)
    assert bad_entry["status"] == "fail" and any(want in i for i in bad_entry["issues"]), (
        f"{bad_at} 那一格（推出去才换的那张）扫描没判出「{want}」：{bad_entry}")
    new = json.loads(spec_path.read_text(encoding="utf-8"))
    t = new["cover"]["frame_at"]
    assert frames(t) == good, f"自动换上的 {t} 秒不是本人睁眼的那张"
    note = new["cover"][scan.AUTOPICK_KEY]
    assert note["from"] == bad_at and note["to"] == t and want in note["why"], note
    if span is not None:
        assert record.get("sweep"), "近处没有能换的，没去整段粗扫"
    # 海报已按新帧重渲、同一把终审过得去、扫描记录对得上（推送闸 cover_scan_gate 同一个函数）
    assert clip.rendered[-1] == t
    _res, issues = auditor.audit_poster(outdir / "poster.jpg", new, face=True)
    assert issues == [], issues
    assert scan.record_problem(record, new) == ""
    # `_why` 前面标了一句「说的是原来那一帧」，原话一字不少；别的字段一个没动
    assert new["cover"]["_why"].startswith(scan.WHY_MARK), new["cover"]["_why"]
    assert new["cover"]["_why"].endswith(spec["cover"]["_why"])
    before = copy.deepcopy(spec)
    before["cover"].update(frame_at=t, _why=new["cover"]["_why"], **{scan.AUTOPICK_KEY: note})
    assert new == before


#: `_entry` 默认认出来的是鲁德——文案点了鲁德的名，机器才换得了
DEMO = {"slug": "demo", "url": "u", "cover": {"frame_at": 10.0, "tag": "2026 拉沃尔杯 · 鲁德"}}


def _entry(t: float, *, status="pass", verdict="match", sim=0.6, ear=0.3, face_px=300.0,
           model_status="ok", margin=3.0, sims=None) -> dict:
    block = {"status": model_status}
    if model_status == "ok":
        block.update(identity={"verdict": verdict, "name": "鲁德",
                               "similarity": sims or {"鲁德": sim},
                               "missing": [], "face_px": face_px},
                     eyes={"verdict": "open", "ear": ear, "face_px": face_px})
    else:
        block["error"] = "没装 onnxruntime"
    return {"frame_at": t, "status": status, "issues": [] if status == "pass" else ["x"],
            "face": {"eyes": 2, "sharpness": 90, "face_height_ratio": 0.3}, "margin": margin,
            "face_model": block}


# ---------------------------------------------------------------- 二、只认 match ＋ open

@pytest.mark.parametrize(("kw", "why"), [
    ({}, ""),
    ({"status": "fail"}, "没过闸"),
    ({"sim": 0.25}, "认不出是封面主角"),          # 中间地带：终审只提示，机器不换
    ({"sim": 0.05}, "认不出是封面主角"),          # 别人
    ({"ear": 0.14}, "眼睛不算睁着"),              # 垂眼
    ({"ear": 0.09}, "眼睛不算睁着"),              # 闭眼
    ({"face_px": 60.0}, "眼睛不算睁着"),          # 脸小到量不了眼睛：unknown 也不换
    ({"model_status": "unavailable"}, "人脸模型不可用"),
])
def test_机器换帧只认match和open_拿不准的一律不换(kw, why):
    """终审把「认人拿不准」「睁眼量不了」记成提示——人挑的那一帧人看过。机器换上的
    那一帧没人看过，所以比终审严一档。判定从存下的数重算：手改 verdict 字符串骗不过去。"""
    entry = _entry(10.0, **kw)
    got = scan.autopick_problem(entry, DEMO)
    assert (got == "") if not why else (why in got), (kw, got)
    forged = _entry(10.0, sim=0.05)
    forged["face_model"]["identity"]["verdict"] = "match"       # 手改字符串
    assert "认不出" in scan.autopick_problem(forged, DEMO)
    assert "没跑认人" in scan.autopick_problem({**_entry(1.0), "face_model": None}, DEMO)


def _record(spec: dict, entries: list[dict], **kw) -> dict:
    return json.loads(json.dumps(scan.build_record(spec, (8.0, 12.0), 0.2, entries, **kw)))


def test_挑过闸名单里第一个机器能换的_余量大的在前():
    spec = DEMO
    entries = [_entry(10.0, status="fail"), _entry(10.2, sim=0.25, margin=9.0),
               _entry(10.4, margin=4.0), _entry(10.6, margin=5.0)]
    record = _record(spec, entries)
    assert record["passing"][0] == 10.2, "排序按余量，这一格余量最大"
    assert scan.pick(record, spec)["frame_at"] == 10.6, "余量最大的那格认人拿不准，该跳过去"
    assert scan.pick(_record(spec, [_entry(10.0, status="fail")]), spec) is None
    assert scan.pick(None, spec) is None


def test_扫描说spec那一帧能过却被终审红了_不换照原样红(tmp_path, capsys):
    """同一份 cover_poster ＋ 同一把 audit_poster：两边说法不一样就是分叉了（bug），
    不许趁机换一帧把分叉盖过去。"""
    spec = {"slug": "demo", "url": "u", "cover": {"frame_at": 10.0}}
    path = tmp_path / "s.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    record = _record(spec, [_entry(10.0), _entry(10.2)])
    assert scan._autopick(spec, path, record, lambda s: None) == scan.AUTOPICK_NONE
    assert "分叉" in capsys.readouterr().out
    assert json.loads(path.read_text(encoding="utf-8")) == spec, "分叉了还改写了 spec"


def test_近处没有就整段粗扫_一格都没有才退出3_spec不动(tmp_path, monkeypatch):
    """近处 ±2 秒一格都换不了 → 整段采访（start–end）粗扫（≤ 40 格、跳过近处）；
    粗扫也没有 → `AUTOPICK_NONE`，spec 一个字节不动。"""
    spec = {"slug": "demo", "url": "u", "start": 0.0, "end": 100.0,
            "cover": {"frame_at": 50.0, "scan_step": 0.5, "tag": "2026 拉沃尔杯 · 鲁德"}}
    grid, span, step = scan.sweep_plan(spec, scan.scan_window(spec), 120.0)
    assert span == (0.0, 100.0) and step >= scan.SWEEP_MIN_STEP
    assert len(grid) <= scan.SWEEP_MAX_FRAMES
    good_at: set[float] = {grid[7]}

    def audit(path, spec_t, *, face=False):
        assert face, "扫描那一格没跑认人＋睁眼"
        t = spec_t["cover"]["frame_at"]
        e = _entry(t)
        ok = t in good_at
        return ({"face": e["face"] | {"box": [1, 200, 3, 4], "contrast": 90,
                                      "face_area_ratio": 0.05},
                 "face_model": {"status": "ok", "identity": e["face_model"]["identity"],
                                "eyes": {**e["face_model"]["eyes"], "ear": 0.3 if ok else 0.1}}},
                [] if ok else ["这张脸闭眼：眼睛纵横比 0.10 < 0.12"])

    monkeypatch.setattr(scan, "audit_poster", audit)
    monkeypatch.setattr(scan, "contact_sheet", lambda *a, **k: None)
    outdir = tmp_path / "demo"
    outdir.mkdir()
    path = tmp_path / "demo.json"
    text = json.dumps(spec, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")

    class Clip(_FakeClip):
        def cover_poster(self, spec, src, out, logo="", *, at=None, dest=None, page=None):
            dest = dest or out / "poster.jpg"
            dest.write_bytes(b"x")
            self.rendered.append(spec["cover"]["frame_at"] if at is None else at)
            return dest

    clip = Clip(None, end=120.0, outdir=outdir)
    assert scan.run_scan(spec, outdir, clip, keep_source=True, autopick=True,
                         spec_path=path) == 0
    record = json.loads((outdir / scan.RECORD_NAME).read_text(encoding="utf-8"))
    assert record["sweep"] == {"window": [0.0, 100.0], "step": step}, record.get("sweep")
    near = [e["frame_at"] for e in record["candidates"] if 48.0 <= e["frame_at"] <= 52.0]
    assert len(near) == 9 and len(record["candidates"]) == 9 + len(grid), "粗扫又扫了一遍近处"
    new = json.loads(path.read_text(encoding="utf-8"))
    assert new["cover"]["frame_at"] == grid[7]
    assert clip.rendered[-1] == grid[7], "换了帧却没按新帧重渲海报"

    good_at.clear()
    path.write_text(text, encoding="utf-8")
    assert scan.run_scan(spec, outdir, clip, keep_source=True, autopick=True,
                         spec_path=path) == scan.AUTOPICK_NONE
    assert path.read_text(encoding="utf-8") == text, "一格都没挑到，spec 却被改了"


def test_整段粗扫的格子数和窗口():
    times, span, step = scan.sweep_plan({"start": 10.0, "end": 400.0}, (98.0, 102.0), 300.0)
    assert span == (10.0, 299.95) and len(times) <= scan.SWEEP_MAX_FRAMES
    assert not any(98.0 <= t <= 102.0 for t in times), "近处已经密扫过，粗扫又扫一遍"
    assert max(times) < 300.0 - 0.04, "越过视频流末尾"
    times, _span, step = scan.sweep_plan({"start": 0.0, "end": 12.0}, (5.0, 7.0), None)
    assert step == scan.SWEEP_MIN_STEP and 6.0 not in times
    assert scan.sweep_plan({"start": 5.0, "end": 5.0}, (0, 1), None)[0] == []


def test_旧记录没逐格跑认人就不对账(monkeypatch):
    """`face_in_scan` 之前写的记录，`pass` 只说明 Haar 过了——可能闭眼、可能是别人，
    不许拿它挡人，也不许拿它自动换（`pick` 看的是 `face_model`，旧记录里没有）。"""
    spec = {"slug": "demo", "url": "u", "cover": {"frame_at": 10.0}}
    record = _record(spec, [_entry(10.0, status="fail")])
    assert "没过闸" in scan.record_problem(record, spec)
    legacy = {k: v for k, v in record.items() if k != "face_in_scan"}
    assert "认人" in scan.stale_ruler(legacy)
    assert scan.record_problem(legacy, spec) == ""


def _headshot_poster(name: str, dest: Path) -> Path:
    """拿官方头像拼一张海报（照片区 1080×810，和 `cover_poster` 出的同一块几何）。
    像素是合成的，相似度会偏高——判的是「认出来是谁之后换不换」，不是认人准不准。"""
    from PIL import Image  # noqa: PLC0415

    head = Image.open(face_checks.headshot_path(name)).convert("RGB")
    w = int(head.width * auditor.PHOTO_HEIGHT / head.height)
    canvas = Image.new("RGB", auditor.CANVAS, (20, 30, 40))
    canvas.paste(head.resize((w, auditor.PHOTO_HEIGHT), Image.LANCZOS),
                 ((auditor.CANVAS[0] - w) // 2, auditor.PHOTO_TOP))
    canvas.save(dest, quality=95)
    return dest


def test_真spec_佩古拉亚军致辞_冠军那一格认人match也不许换(model, monkeypatch, tmp_path):
    """复审 BLOCKING（2026-09-28）：`pegula-eala-dc2026-final` 是佩古拉的亚军致辞（tag
    「2026 华盛顿决赛 · 佩古拉」），可 spec 没写 `subject`／`match.loser`，
    `expected_subject` 退回 `winner`＝伊埃拉。人挑的那一帧（佩古拉）终审判 mismatch 红，
    原来的 autopick 接着把近处一格冠军的脸（match、睁眼）换上去、终审 match、推送闸也
    match——给亚军致辞配上冠军的脸，一道都拦不住。现在：认出来的人必须是文案点了名的。"""
    _memo_pixels(monkeypatch)
    slug = "pegula-eala-dc2026-final"
    spec = json.loads((SPECS / f"{slug}.json").read_text(encoding="utf-8"))
    assert auditor.expected_subject(spec) == "伊埃拉" and "佩古拉" in spec["cover"]["tag"], (
        "前提变了：这条 spec 的主角推断已经不落在对手身上，这条判据要换一条真 spec")
    pegula = _headshot_poster("佩古拉", tmp_path / "pegula.jpg")
    eala = _headshot_poster("伊埃拉", tmp_path / "eala.jpg")
    at = float(spec["cover"]["frame_at"])

    def frames(t: float) -> Path:        # 近处有一段切给冠军的镜头
        return eala if at - 1.0 <= t < at else pegula

    spec["cover"]["scan_step"] = 0.4
    spec_path = tmp_path / f"{slug}.json"
    text = json.dumps(spec, ensure_ascii=False, indent=2) + "\n"
    spec_path.write_text(text, encoding="utf-8")
    outdir = tmp_path / slug
    outdir.mkdir()
    clip = _FakeClip(frames, end=float(spec["end"]) + 5.0, outdir=outdir)
    rc = scan.run_scan(spec, outdir, clip, keep_source=True, autopick=True, spec_path=spec_path)
    record = json.loads((outdir / scan.RECORD_NAME).read_text(encoding="utf-8"))
    champ = [e for e in record["candidates"] if frames(e["frame_at"]) == eala]
    assert champ and all(e["status"] == "pass" for e in champ), (
        "前提没了：冠军那几格本该过得了终审（认人 match、睁眼）——这条判据要的就是这种格子")
    for e in champ:
        assert "封面文案" in scan.autopick_problem(e, spec), scan.autopick_problem(e, spec)
    assert rc == scan.AUTOPICK_NONE, "冠军的脸被换上了亚军致辞的封面"
    assert spec_path.read_text(encoding="utf-8") == text, "没换帧却改了 spec"
    assert "sweep" not in record, "主角都不是文案点名的人，整段粗扫只会白烧一分半钟"


def test_双打只换文案点了名的那个搭档():
    """`alcaraz-mensik` 的主角推断是「阿尔卡拉斯/门西克」（两人之一就 match），而文案只点了
    阿尔卡拉斯（「阿尔卡拉斯笑着拿下」）：门西克那一格机器不许换。"""
    spec = json.loads((SPECS / "alcaraz-mensik-laver-cup-2026-interview.json")
                      .read_text(encoding="utf-8"))
    assert "门西克" not in scan.cover_copy(spec) and "阿尔卡拉斯" in scan.cover_copy(spec)
    mensik = _entry(10.0, sims={"阿尔卡拉斯": 0.05, "门西克": 0.6})
    alcaraz = _entry(10.2, sims={"阿尔卡拉斯": 0.6, "门西克": 0.05})
    assert "封面文案" in scan.autopick_problem(mensik, spec)
    assert scan.autopick_problem(alcaraz, spec) == ""
    record = _record({**spec, "cover": {**spec["cover"], "frame_at": 10.0}},
                     [mensik, {**alcaraz, "margin": 1.0}])
    assert record["passing"][0] == 10.0, "前提：门西克那一格余量更大、排第一"
    assert scan.pick(record, spec)["frame_at"] == 10.2


def test_主角推断落在对手身上的存量spec_整段粗扫之前就认出来():
    """全库量（2026-09-28）：108 条认得出主角的采访 spec 里 104 条的文案点了主角的名；
    没点的 4 条是三条主角推断落到对手身上的，加上主角没官方头像的颁奖礼。"""
    flagged, named = set(), 0
    for path in sorted(SPECS.glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(spec.get("cover"), dict):
            continue
        if scan.subject_unnamed(spec):
            flagged.add(path.stem)
        elif auditor.expected_subject(spec):
            named += 1
    assert {"pegula-eala-dc2026-final", "nakashima-shelton-mtl2026-final",
            "williams-sisters-cincinnati-2026-r1-presser"} <= flagged, flagged
    assert named >= 100, f"只有 {named} 条文案点了主角的名——机器换帧会被大面积误拦"


# ---------------------------------------------------------------- 三、改写 spec

def test_改写spec只动frame_at和换帧记录_全库每一条都验():
    """认得出原文是哪种 `json.dumps` 写法的，diff 只有 frame_at、`_why` 那两行加上新增的
    `_frame_autopick` 那几行；认不出的（手排过的）退回缩进 2，但解析出来必须一模一样。"""
    note = {"from": 1.0, "to": 2.5, "at": "2026-09-28T00:00:00Z", "why": "只检出 1 只眼",
            "chosen": {"margin": 3.1, "name": "某某", "similarity": 0.5, "ear": 0.3},
            "record": scan.RECORD_NAME}
    minimal = reformatted = 0
    for path in sorted(SPECS.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if not isinstance(data.get("cover"), dict) or "frame_at" not in data["cover"]:
            continue
        out = scan.rewrite_frame_at(text, 12.34, note)
        got = json.loads(out)
        want = copy.deepcopy(data)
        want["cover"].update(frame_at=12.34, **{scan.AUTOPICK_KEY: note})
        if isinstance(data["cover"].get("_why"), str) and data["cover"]["_why"].strip():
            why = got["cover"]["_why"]
            assert why.startswith(scan.WHY_MARK) and why.endswith(data["cover"]["_why"]), why
            assert f"{data['cover']['frame_at']} 秒那一帧" in why, why
            want["cover"]["_why"] = why
        assert got == want, path.name
        diff = list(difflib.ndiff(text.splitlines(), out.splitlines()))
        removed = [ln for ln in diff if ln.startswith("- ")]
        added = {ln[2:] for ln in diff if ln.startswith("+ ")}
        # frame_at、_why 那两行，外加（新键接在 cover 末尾时）上一行补的逗号
        rest = [ln for ln in removed if '"frame_at"' not in ln and '"_why"' not in ln]
        if len(rest) <= 1 and all(ln[2:] + "," in added for ln in rest):
            minimal += 1
            assert any('"frame_at"' in ln for ln in removed), (path.name, removed)
        else:
            reformatted += 1
    assert minimal >= 90, f"只有 {minimal} 条 spec 改得最小——认写法那一步坏了"
    assert reformatted <= 12, reformatted
    with pytest.raises(json.JSONDecodeError):
        scan.rewrite_frame_at("{坏的", 1.0, note)


def test_换帧之后人给原来那一帧写的认领挪走_why标一句_再换一次不叠两层():
    """`_face_check_why`／`_frame_scan_why` 是给人看过的那一帧写的：留在 cover 上，下次尺子
    一变就替一帧没人看过的开脱。挪进 `_frame_autopick.dropped`（原话不丢）；`_why` 前面
    标一句它说的是哪一帧。连换两次：标注只一层、第一次挪走的认领接着留着。"""
    spec = {"slug": "demo", "cover": {"frame_at": 30, "_why": "30 秒正脸，笑着",
                                      "_face_check_why": "教练席那一幕，要的就是他",
                                      "_frame_scan_why": "人看过"}}
    note = {"from": 30, "to": 29.4}
    once = json.loads(scan.rewrite_frame_at(json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
                                            29.4, note))
    cover = once["cover"]
    assert not set(scan.STALE_CLAIMS) & set(cover), cover
    assert cover[scan.AUTOPICK_KEY]["dropped"] == {
        "_face_check_why": "教练席那一幕，要的就是他", "_frame_scan_why": "人看过"}
    assert cover["_why"].startswith(scan.WHY_MARK) and cover["_why"].endswith("30 秒正脸，笑着")
    assert "30 秒那一帧" in cover["_why"] and "29.4 秒是机器换的" in cover["_why"]
    twice = json.loads(scan.rewrite_frame_at(json.dumps(once, ensure_ascii=False, indent=2),
                                             31.0, {"from": 29.4, "to": 31.0}))["cover"]
    assert twice["_why"].count(scan.WHY_MARK) == 1, twice["_why"]
    assert "30 秒那一帧" in twice["_why"], "第二次标注把人挑的那一帧说成了机器换的那一帧"
    assert twice["_why"].endswith("30 秒正脸，笑着")
    assert twice[scan.AUTOPICK_KEY]["dropped"] == cover[scan.AUTOPICK_KEY]["dropped"]
    # 没有认领、没有 _why 的：什么都不多加
    bare = json.loads(scan.rewrite_frame_at('{"cover": {"frame_at": 1}}', 2.0, {"to": 2.0}))
    assert bare == {"cover": {"frame_at": 2.0, scan.AUTOPICK_KEY: {"to": 2.0}}}


# ---------------------------------------------------------------- 四、提交成片

def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          cwd=cwd, check=True, capture_output=True, text=True).stdout


def _commit_step(tmp_path: Path, *, autopicked: bool, race: str = "") -> tuple:
    """「提交成片」在真 git 仓库里跑一遍。`race`：'' 直推；'other' 别人推过无关文件；
    'spec' 别人推过同一份 spec（人工修改）；'spec_rec' 别人连 spec 带一份扫描记录一起推过。"""
    import yaml  # noqa: PLC0415

    remote, work = tmp_path / "remote.git", tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    shutil.copy(ROOT / ".gitignore", work / ".gitignore")
    spec_rel = Path("specs/interviews/demo.json")
    (work / spec_rel).parent.mkdir(parents=True)
    (work / spec_rel).write_text('{\n  "cover": {\n    "frame_at": 30\n  }\n}\n', encoding="utf-8")
    _git(work, "add", ".")
    _git(work, "commit", "-qm", "base")
    _git(work, "remote", "add", "origin", str(remote))
    _git(work, "push", "-q", "origin", "main")
    if race:
        other = tmp_path / "other"
        subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
        target = other / ("README.md" if race == "other" else spec_rel)
        target.write_text('{\n  "cover": {\n    "frame_at": 44.4\n  }\n}\n'
                          if race.startswith("spec") else "别人刚推过\n", encoding="utf-8")
        if race == "spec_rec":
            theirs = other / "output" / "interviews" / "demo" / scan.RECORD_NAME
            theirs.parent.mkdir(parents=True)
            theirs.write_text('{"method": "cover_scan_v1", "who": "theirs"}', encoding="utf-8")
        _git(other, "add", ".")
        _git(other, "commit", "-qm", "race")
        _git(other, "push", "-q", "origin", "main")
    outdir = work / "output" / "interviews" / "demo"
    outdir.mkdir(parents=True)
    (outdir / "poster.jpg").write_bytes(b"poster")
    (outdir / scan.RECORD_NAME).write_text('{"method": "cover_scan_v1"}', encoding="utf-8")
    if autopicked:
        (work / spec_rel).write_text('{\n  "cover": {\n    "frame_at": 31.4\n  }\n}\n',
                                     encoding="utf-8")
        (tmp_path / "cover-autopicked").write_text("", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("python", "sleep"):
        (bin_dir / name).write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        (bin_dir / name).chmod(0o755)
    wf = yaml.safe_load((ROOT / ".github/workflows/interview-clip.yml").read_text(encoding="utf-8"))
    step = next(s for s in wf["jobs"]["render"]["steps"] if s.get("name") == "提交成片")
    body = (str(step["run"]).replace("${{ github.event.inputs.slug }}", "demo")
            .replace("${{ github.ref_name }}", "main"))
    assert "${{" not in body, body
    (tmp_path / "step.sh").write_text(body, encoding="utf-8")
    env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
               MODE="render", RUNNER_TEMP=str(tmp_path))
    done = subprocess.run(["bash", "-e", str(tmp_path / "step.sh")], cwd=work, env=env,
                          capture_output=True, text=True, timeout=120)
    return done, remote


def _remote_frame(remote: Path) -> float:
    return json.loads(_git(remote, "show", "main:specs/interviews/demo.json"))["cover"]["frame_at"]


@pytest.mark.parametrize("race", ["", "other"], ids=["直推", "撞车重放"])
def test_换过帧的spec跟成片一起提交(tmp_path, race):
    """只提交产物不提交 spec：main 上 spec 的哈希对不上 QC／封面凭证——推送闸报「spec 在
    质检后发生过变化」不推，picker 判「当前 spec 没出过片」过 70 分钟又投一趟、再红再换，
    永远落不了地。"""
    done, remote = _commit_step(tmp_path, autopicked=True, race=race)
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert _remote_frame(remote) == 31.4, "换过帧的 spec 没跟成片一起落库"
    log = _git(remote, "log", "-1", "--format=%s", "main")
    assert "封面自动换帧" in log, log
    tree = _git(remote, "ls-tree", "-r", "--name-only", "main").split()
    assert f"output/interviews/demo/{scan.RECORD_NAME}" in tree

    plain = tmp_path / "plain"
    plain.mkdir()
    done, remote = _commit_step(plain, autopicked=False, race=race)
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert _remote_frame(remote) == 30, "没换帧却动了 spec"


@pytest.mark.parametrize("race", ["spec", "spec_rec"], ids=["分支上没有记录", "分支上有别人的记录"])
def test_撞车重放时别人改过spec就不覆盖_扫描记录也留分支上那一份(tmp_path, race):
    """重放把本趟那一版 spec 放回去之前，比一下别人动没动过它：动过就留别人的
    （盖掉就是吞掉一次人工修改），出声，凭证对不上的那一半交给 picker 按新 spec 重渲。

    **扫描记录也退回分支上那一份**（复审 2026-09-28 复现）：本趟的记录要是落了库，别人那版
    spec 的 frame_at（多半还是原来红的那一格）在 dispatch 之前的预检就红——picker 把它停进
    waiting 等人改，而不是按新 spec 重渲、封面再红再自动换。"""
    done, remote = _commit_step(tmp_path, autopicked=True, race=race)
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert _remote_frame(remote) == 44.4, "重放把别人刚改的 spec 盖掉了"
    assert "被别人改过" in done.stdout, done.stdout
    tree = _git(remote, "ls-tree", "-r", "--name-only", "main").split()
    assert "output/interviews/demo/poster.jpg" in tree
    rec = f"output/interviews/demo/{scan.RECORD_NAME}"
    if race == "spec":
        assert rec not in tree, "留了别人的 spec，却把本趟的扫描记录落了库"
    else:
        assert json.loads(_git(remote, "show", f"main:{rec}")).get("who") == "theirs", (
            "留了别人的 spec，扫描记录却不是分支上那一份")
    log = _git(remote, "log", "-1", "--format=%s", "main")
    assert "留了别人的" in log, log


# ---------------------------------------------------------------- 五、dispatch 之前

def test_预检按已提交的扫描记录拦没过闸的frame_at_顺手报能换的那一格(monkeypatch, tmp_path):
    import interview_preflight as pf  # noqa: PLC0415

    out = tmp_path / "output" / "interviews"
    (out / "demo").mkdir(parents=True)
    monkeypatch.setattr(pf, "OUTPUT", out)
    spec = DEMO
    assert pf.cover_scan_problem(spec) is None, "没有记录不许拦——存量一份记录都没有"
    record = _record(spec, [_entry(10.0, status="fail"), _entry(10.2, sim=0.25, margin=9),
                            _entry(10.4)])
    (out / "demo" / scan.RECORD_NAME).write_text(json.dumps(record), encoding="utf-8")
    red = pf.cover_scan_problem(spec)
    assert red and "没过闸" in red and "10.4 秒" in red, red
    assert pf.cover_scan_problem({**spec, "cover": {"frame_at": 10.4}}) is None
    unscanned = pf.cover_scan_problem({**spec, "cover": {"frame_at": 33.0}})
    assert unscanned and "没扫过" in unscanned, unscanned
    # 探针（系统 python3，没有 PIL）也跑这一道：它只要标准库
    monkeypatch.setitem(sys.modules, "PIL", None)
    red_probe, _unknown = pf.probe_problems(spec)
    assert any(r.startswith("_check_cover_scan") for r in red_probe), red_probe


def test_没有产物目录就从HEAD读记录_预检缓存的键跟着记录走(monkeypatch, tmp_path):
    """interview-auto-render 的稀疏检出不带 output/：从 HEAD 读（和字幕缓存同一个口径）。
    记录一换，`verdict_key` 就变——缓存里那条「frame_at 没过闸」不许替新记录说话。"""
    import interview_preflight as pf  # noqa: PLC0415

    repo = tmp_path / "repo"
    rec_dir = repo / "output" / "interviews" / "demo"
    rec_dir.mkdir(parents=True)
    spec = DEMO
    (rec_dir / scan.RECORD_NAME).write_text(
        json.dumps(_record(spec, [_entry(10.0, status="fail"), _entry(10.4)])), encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "r")
    shutil.rmtree(repo / "output")                  # 稀疏检出：工作区里没有这一格
    monkeypatch.setattr(pf, "ROOT", repo)
    monkeypatch.setattr(pf, "OUTPUT", repo / "output" / "interviews")
    red = pf.cover_scan_problem(spec)
    assert red and "10.4 秒" in red, red
    fp1 = pf.cover_record_fingerprint("demo")
    assert fp1 and pf.cover_record_fingerprint("nope") == ""
    blob = subprocess.run(["git", "-C", str(repo), "rev-parse",
                           f"HEAD:output/interviews/demo/{scan.RECORD_NAME}"],
                          capture_output=True, text=True, check=True).stdout.strip()
    assert fp1 == blob, "工作区和 HEAD 两条路给的指纹不是同一种算法"

    import pick_interview_renders as pick  # noqa: PLC0415

    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "demo.json").write_text(json.dumps(spec), encoding="utf-8")
    monkeypatch.setattr(pick, "SPECS", specs)
    monkeypatch.setattr(pick, "_code_fingerprint", lambda: "code")
    monkeypatch.setattr(pf, "caption_fingerprint", lambda slug: [])
    k1 = pick.verdict_key("demo")
    monkeypatch.setattr(pf, "cover_record_fingerprint", lambda slug: "another-blob")
    assert pick.verdict_key("demo") != k1, "扫描记录换了，预检缓存的键没变"


def test_记录里那一格只红在认人睁眼上_人写了face_check_why就不拦():
    """扫描之后人看过那一帧、写了 `_face_check_why` 认领：终审（`face_model_issues`）对它
    放行，扫描记录的对账也得放行——否则记录和终审说两句话，只能重扫或再写一句
    `_frame_scan_why`。认领只管认人／睁眼：记录里那一格还有 Haar／构图的毛病，照样拦。"""
    closed = _entry(10.0, ear=0.09)
    face_red = face_checks.problems_of(closed["face_model"])[0]
    assert face_red and all(p.startswith("这张脸") for p in face_red), face_red
    closed.update(status="fail", issues=list(face_red))
    haar_too = {**closed, "issues": [*face_red, "只检出 1 只眼，正面睁眼合同要求 ≥ 2"]}
    claimed = {**DEMO, "cover": {**DEMO["cover"], "_face_check_why": "低头那一下就是这段采访的落点"}}
    record = _record(DEMO, [closed, _entry(10.2)])
    assert "没过闸" in scan.record_problem(record, DEMO), "没认领的闭眼帧不许放"
    assert scan.record_problem(record, claimed) == ""
    record = _record(DEMO, [haar_too, _entry(10.2)])
    assert "没过闸" in scan.record_problem(record, claimed), "认领认人／睁眼，却把 Haar 的毛病一起放了"
    # 存下来的 issues 字符串是手改的（和存的数对不上）：不信字符串，照样拦
    forged = {**closed, "issues": ["这张脸闭眼：随便写的"]}
    assert "没过闸" in scan.record_problem(_record(DEMO, [forged]), claimed)
