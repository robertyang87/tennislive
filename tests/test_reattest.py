"""「重核对，不重渲」（`match-reel mode=reattest`）的判据。

账号所有者 2026-09-27 在 O1（质检指纹管到哪儿）三选一里选的：spec 渲完之后只改
注解或推送字段时，不重渲，重出一张绑定新 spec 字节、指着同一份成片的凭证。

来路（五趟 7~10 分钟、成片一个像素都没变的重渲）：eala-jovic 85b94e74、
mensik-tien d338e77d、medvedev-damm e15e73e5；gauff-jovic 80bbdd1a 推送之后链就
断着。wong-paul d5bbc48c 也在那五趟里，但它改的是真字段 `editorial`，**重核对
省不掉**（`test_editorial是真字段_改里面的数照旧重渲` 钉着这条边界）。

**「发出去的必须和质检过的是同一份」一个字都不许松**——所以这里的测试一半在验
「该过的过了」，一半在验「动了成片的、链被动过手脚的、Release 被换过的、
账本已经 sent 的，一条都过不去」。每一组都用真代码路径造链：
`render_inputs.record`（渲染那一刻）→ `check_reel_landed.write_attestation`
（L2 质检）→ Release 那一步回写 `video_url/video_bytes` 并删掉本地成片。
"""

from __future__ import annotations

import ast
import functools
import hashlib
import http.client
import json
import re
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import auto_push_gate as gate  # noqa: E402
import check_reel_landed as landed  # noqa: E402
import reattest_check as rc  # noqa: E402
import render_inputs as ri  # noqa: E402

SLUG = "demo"
FILM = b"the-checked-film-bytes"
WORKFLOW = ROOT / ".github/workflows/match-reel.yml"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _spec() -> dict:
    return {
        "slug": SLUG,
        "_column": "赛场之上",
        "_facts": ["四场合计 7 小时 01 分"],
        "source_url": "https://www.youtube.com/watch?v=demo",
        "cover": {
            "eyebrow": "赛场之上", "layout": "vs", "hook": "决胜盘一度落后\n她还是赢了",
            "_layout_why": "两张官方抠图都在",
            "portrait": {"image": "assets/reel/demo-cover.jpg", "_why": "赛后实拍"},
        },
        "segments": [
            {"start": 10.0, "end": 16.0, "quote": "What a shot\n这一拍太漂亮了",
             "score_inset": False, "_score_inset_why": "板在 168.8 撤掉"},
            {"start": 30.0, "end": 41.5, "narration": "第二盘她退台半步，把回发球兜回对角。",
             "score_inset": True, "_why": "段号交叉引用见第 2 段"},
        ],
        "push": {"auto": False, "summary": "她赢了", "_no_auto_why": "先验证"},
    }


def _write_spec(repo: Path, spec: dict) -> Path:
    path = repo / "specs/reels" / f"{SLUG}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _rendered(repo: Path, spec: dict | None = None) -> Path:
    """按生产链的顺序造一份「渲完、质检过、发了 Release」的产物目录。"""
    spec = spec or _spec()
    spec_path = _write_spec(repo, spec)
    (repo / "specs/reels" / f"{SLUG}.xhs.txt").write_text("文案", encoding="utf-8")
    asset = repo / "assets/reel/demo-cover.jpg"
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes(b"\xff\xd8 official photo")
    outdir = repo / "output/2026-09-27/reel" / SLUG
    outdir.mkdir(parents=True)
    film = outdir / f"{SLUG}.mp4"
    film.write_bytes(FILM)
    (outdir / "subtitles.ass").write_text(
        "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,这一拍太漂亮了\n", encoding="utf-8")
    (outdir / "topbar.ass").write_text("Dialogue: 顶栏\n", encoding="utf-8")
    (outdir / "poster.jpg").write_bytes(b"\xff\xd8 poster")
    (outdir / "render.json").write_text('{"film_seconds": 1}', encoding="utf-8")
    # ① 渲染那一刻（build_match_reel.main 在 render() 之后调的就是它）
    ri.record(spec_path, outdir, film, repo)
    # ② L2 质检（match-reel.yml「查成片本身合不合格」）
    landed.write_attestation(film, spec_path, spec)
    # ③ 成片发到 Release、本地那份删掉（match-reel.yml 同名步骤）
    meta = json.loads((outdir / "render.json").read_text(encoding="utf-8"))
    meta.update({"video_url": f"https://example.test/{SLUG}.mp4", "video_bytes": len(FILM)})
    (outdir / "render.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
    film.unlink()
    return outdir


def _release_ok(url: str) -> tuple[str, int]:
    return _sha(FILM), len(FILM)


def _edit(repo: Path, change, base: dict | None = None) -> Path:
    spec = json.loads(json.dumps(base)) if base is not None else _spec()
    change(spec)
    return _write_spec(repo, spec)


def _assess(repo: Path, outdir: Path) -> rc.Assessment:
    return rc.assess(repo, SLUG, outdir, repo / "specs/reels" / f"{SLUG}.json")


# ── 该过的过了 ─────────────────────────────────────────────────────────────


def test_渲染那一刻清单和凭证互相钉住(tmp_path):
    outdir = _rendered(tmp_path)
    manifest_bytes = (outdir / ri.MANIFEST_NAME).read_bytes()
    manifest = json.loads(manifest_bytes)
    qc = json.loads((outdir / "qc_attestation.json").read_text(encoding="utf-8"))
    render = json.loads((outdir / "render.json").read_text(encoding="utf-8"))
    assert manifest["film_sha256"] == qc["film_sha256"] == _sha(FILM)
    assert qc["render_inputs_sha256"] == render["render_inputs_sha256"] == _sha(manifest_bytes)
    assert manifest["spec_sha256"] == qc["spec_sha256"]
    # 注解和推送块不进投影，`_column` 进（它决定字幕下锚）
    assert "_facts" not in manifest["projection"] and "push" not in manifest["projection"]
    assert "_why" not in manifest["projection"]["segments"][1]
    assert manifest["projection"]["_column"] == "赛场之上"
    assert manifest["assets"] == {"assets/reel/demo-cover.jpg": _sha(b"\xff\xd8 official photo")}
    assert set(manifest["artifacts"]) == {"subtitles.ass", "topbar.ass", "poster.jpg"}
    assert ["cover", "_layout_why"] in manifest["claims"]
    assert _assess(tmp_path, outdir).status == "same"


def test_只改注解和推送字段_重核对通过且新凭证绑同一份成片(tmp_path):
    """五条来路的形状各来一处：_why / _facts / _score_inset_why / push.auto / push.summary。"""
    outdir = _rendered(tmp_path)
    old_qc_bytes = (outdir / "qc_attestation.json").read_bytes()

    def change(spec):
        spec["segments"][1]["_why"] = "段号交叉引用跟着重排改对：见第 1 段"
        spec["_facts"] = ["四场合计 163+70+87+161 ＝ 481 分钟"]
        spec["segments"][0]["_score_inset_why"] = "拿成片逐帧量过：168.8~169.4 撤掉"
        spec["push"] = {"auto": True, "summary": "她逆转赢了"}
        spec["_no_repeat"] = "同栏目讲过的是另一场"

    spec_path = _edit(tmp_path, change)
    assert _assess(tmp_path, outdir).status == "reattest"

    a = rc.apply(tmp_path, SLUG, outdir, spec_path, run_url="https://run/1",
                 now="2026-09-27T12:00:00Z", fetch=_release_ok)
    assert a.status == "reattest", a.reasons
    qc_bytes = (outdir / "qc_attestation.json").read_bytes()
    qc = json.loads(qc_bytes)
    render = json.loads((outdir / "render.json").read_text(encoding="utf-8"))
    assert qc["spec_sha256"] == _sha(spec_path.read_bytes())
    assert qc["film_sha256"] == _sha(FILM) and qc["film_bytes"] == len(FILM)
    assert qc["reattest"]["previous_attestation_sha256"] == _sha(old_qc_bytes)
    assert qc["reattest"]["film_verified"] == "release-sha256"
    assert render["qc_attestation_sha256"] == _sha(qc_bytes)
    assert render["film_sha256"] == qc["film_sha256"]
    assert render["reattests"][-1]["spec_sha256"] == qc["spec_sha256"]
    # 再改一次注解，第二次重核对照样认得出这条链（凭证钉的还是同一份清单）
    spec_path = _edit(tmp_path, lambda s: (change(s), s.update({"_note": "第二次"})))
    assert rc.apply(tmp_path, SLUG, outdir, spec_path, fetch=_release_ok).status == "reattest"


# ── 动了成片的，过不去 ──────────────────────────────────────────────────────


@pytest.mark.parametrize("change, where", [
    (lambda s: s["segments"][1].update(narration="第二盘她上网截击。"), "第 2 段旁白"),
    (lambda s: s["segments"][0].update(end=16.5), "第 1 段画面"),
    (lambda s: s["segments"][0].update(quote="What a shot\n这一拍真漂亮"), "第 1 段原声字幕"),
    (lambda s: s["cover"].update(hook="决胜盘一度落后\n她赢了"), "封面"),
    (lambda s: s.update(_column="网球有故事"), "渲染参数"),          # 注解里唯一进成片的那种
    (lambda s: s["segments"].pop(0), "段落结构"),
])
def test_动了渲染输入就不许重核对(tmp_path, change, where):
    outdir = _rendered(tmp_path)
    spec_path = _edit(tmp_path, change)
    a = _assess(tmp_path, outdir)
    assert a.status == "render", a.reasons
    assert any(where in r for r in a.reasons), a.reasons
    before = (outdir / "qc_attestation.json").read_bytes()
    assert rc.apply(tmp_path, SLUG, outdir, spec_path, fetch=_release_ok).status == "render"
    assert (outdir / "qc_attestation.json").read_bytes() == before, "拒绝的那一趟不许动凭证"


def test_editorial是真字段_改里面的数照旧重渲(tmp_path):
    """wong-paul d5bbc48c 的形状：加错的分钟数在 `editorial.human_context.facts` 里。

    `editorial` 只进闸（`_validate_editorial_contract` / `ending_payoff_problem`），但它
    是真字段、在投影里——重核对**不**替它省那一趟（评审拿真提交重放量过：报「渲染参数：
    editorial.human_context.facts[3]」）。文档里曾把它算进「省得掉的五趟」，这条钉住边界：
    哪天要放它，得先让归类扫描像管 `push` 那样管住谁读 `editorial`，再改这条。
    """
    base = dict(_spec(), editorial={"human_context": {"facts": ["四场合计 7 小时 01 分"]}})
    outdir = _rendered(tmp_path, base)
    _edit(tmp_path, lambda s: s["editorial"]["human_context"].update(
        facts=["四场合计 8 小时 01 分"]), base)
    a = _assess(tmp_path, outdir)
    assert a.status == "render", a.reasons
    assert any("editorial.human_context.facts[0]" in r for r in a.reasons), a.reasons


def test_同一个路径换了一张图也不许重核对(tmp_path):
    """O4「自动换图」正是这个形状：spec 一个字不变，封面那张图的字节变了。"""
    outdir = _rendered(tmp_path)
    (tmp_path / "assets/reel/demo-cover.jpg").write_bytes(b"\xff\xd8 another photo")
    _edit(tmp_path, lambda s: s["cover"]["portrait"].update(_why="换成官方图"))
    a = _assess(tmp_path, outdir)
    assert a.status == "render" and any("素材文件变了" in r for r in a.reasons), a.reasons


def test_删掉渲染时的认领注解就不许重核对(tmp_path):
    """`_layout_why` 这类认领只有 build_cover 在编码里查，dry-run 够不着——删掉等于绕过。"""
    outdir = _rendered(tmp_path)
    _edit(tmp_path, lambda s: s["cover"].pop("_layout_why"))
    a = _assess(tmp_path, outdir)
    assert a.status == "render" and any("认领没了" in r for r in a.reasons), a.reasons
    # 改写认领的**措辞**不算删（dry-run 照样重跑那些闸）
    _edit(tmp_path, lambda s: s["cover"].update(_layout_why="两张官方抠图都在（WTA 图库）"))
    assert _assess(tmp_path, outdir).status == "reattest"


def test_只调换源片的顺序也不许重核对(tmp_path):
    """评审 2026-09-27 拦下的阻断项：投影 `sort_keys` 之后比，键的顺序被抹平了。

    渲染器按插入顺序取主源片（`next(iter(spec_sources(spec)))`，没写 `source` 的段都
    从它取画面）。两个源调个儿、再补一句 `_why`——原来 `spec_problems` 返回 `[]`，
    重核对会把「r1 当主源」渲出来的成片推给一份「r2 当主源」的 spec。
    """
    import build_match_reel as bmr  # noqa: PLC0415

    base = _spec()
    del base["source_url"]
    base["sources"] = {"r1": "https://www.youtube.com/watch?v=aaa",
                       "r2": "https://www.youtube.com/watch?v=bbb"}
    base["segments"][1]["source"] = "r2"      # 第 1 段没写 source：从主源片取
    outdir = _rendered(tmp_path, base)

    def swap(spec):
        spec["sources"] = {"r2": spec["sources"]["r2"], "r1": spec["sources"]["r1"]}
        spec["_why"] = "源片顺序按出场排"

    spec_path = _edit(tmp_path, swap, base)
    new = json.loads(spec_path.read_bytes())
    # 前提：渲染器自己认出来的主源片真的换了人（不是测试一厢情愿）
    assert next(iter(bmr.spec_sources(base))) == "r1"
    assert next(iter(bmr.spec_sources(new))) == "r2"

    manifest = json.loads((outdir / ri.MANIFEST_NAME).read_text(encoding="utf-8"))
    problems = ri.spec_problems(spec_path.read_bytes(), manifest)
    assert any("键的顺序变了" in p and "sources" in p for p in problems), problems
    # 清单里的投影指纹同样按原顺序算：换了顺序，指纹就不是那一个
    assert manifest["projection_sha256"] != _sha(
        ri.canonical(ri.project(new)).encode("utf-8"))
    a = _assess(tmp_path, outdir)
    assert a.status == "render", a.reasons
    before = (outdir / "qc_attestation.json").read_bytes()
    assert rc.apply(tmp_path, SLUG, outdir, spec_path, fetch=_release_ok).status == "render"
    assert (outdir / "qc_attestation.json").read_bytes() == before

    # 别处的键换顺序也算：宁可多判一次重渲，不一处处去证明哪张表的顺序无关
    _edit(tmp_path, lambda s: s.update(cover=dict(reversed(list(s["cover"].items())))), base)
    a = _assess(tmp_path, outdir)
    assert a.status == "render" and any("cover" in r and "键的顺序" in r for r in a.reasons)
    # 注解插在中间、不动其余键的相对顺序——不算换顺序
    _edit(tmp_path, lambda s: s.update(cover={"_note": "x", **s["cover"]}), base)
    assert _assess(tmp_path, outdir).status == "reattest"


def test_sources表里下划线开头的键也是源_不当注解剥(tmp_path):
    """评审 2026-09-27（第二轮）：`spec_sources` 不按下划线跳过，`sources` 里插一句
    `"_why"` 它就成了第一条、成了主源片——投影要是把它当注解剥掉，重核对会放过去。"""
    import build_match_reel as bmr  # noqa: PLC0415

    base = _spec()
    del base["source_url"]
    base["sources"] = {"r1": "https://www.youtube.com/watch?v=aaa",
                       "r2": "https://www.youtube.com/watch?v=bbb"}
    outdir = _rendered(tmp_path, base)

    def annotate(spec):
        spec["sources"] = {"_why": "两场集锦按出场排", **spec["sources"]}

    spec_path = _edit(tmp_path, annotate, base)
    new = json.loads(spec_path.read_bytes())
    # 前提：渲染器真把这句 `_why` 当成了主源片（不是测试一厢情愿）
    assert next(iter(bmr.spec_sources(new))) == "_why"
    manifest = json.loads((outdir / ri.MANIFEST_NAME).read_text(encoding="utf-8"))
    problems = ri.spec_problems(spec_path.read_bytes(), manifest)
    assert any("sources" in p for p in problems), problems
    assert _assess(tmp_path, outdir).status == "render"


def _gated_spec() -> dict:
    """在样板上补几条**有闸读**的认领：配音参数、预制封面、全屏照片、退回 edge-tts。"""
    spec = _spec()
    spec["cover"].update(approved_image="assets/reel/demo-approved.jpg",
                         _approved_by_user=True)
    spec["segments"][1]["voice"] = {"rate": "-8%", "_why": "这一段是崩盘，降速"}
    spec["segments"].append({"image": "assets/reel/demo-photo.jpg", "image_kind": "photo",
                             "seconds": 3, "narration": "赛后她跪在场上。",
                             "_photo_source": "https://photos.example/1",
                             "_photo_caption_safety": "字幕在下三分之一，脸在上半"})
    spec.update(tts_backend="edge", _tts_backend_why="Azure 钥匙 401")
    spec["stats"] = {"_why": "数据来自 flashscore"}
    spec["editorial"] = {"_why": "技战术按官方逐分核过"}
    spec["_score_inset_why"] = "promote 写的说明：没有闸读顶层这一句"
    # main 在 #1102 / #1104 加的四道 dry-run 闸的认领（2026-09-27 rebase 时归的类）
    spec.update(_short_match_why="对手第一盘 0-3 退赛，官方用时 19 分钟",
                _cover_reuse_why="同站两条共用一张官方赛后照，账号所有者认过",
                _numeral_display_why="「四分之一决赛」是赛事名，不是数字")
    spec["segments"][0]["_board_on_screen_why"] = "这几秒是慢镜回放，板是回放条不是比分"
    # #1105（wp/face-eye-checks）合进 main 的封面认人／睁眼：只在 render 里查
    spec["cover"]["portrait"]["_face_check_why"] = "讲的就是她闭眼流泪那一刻"
    # 2026-09-28 合 main 归的类（数字静音预测、probe 覆盖、口味闸）
    spec["segments"][0].update(_quote_kind="broadcast",
                               _digital_silence_why="看过：这两秒是解说停顿，现场声本来就轻")
    spec["_no_probe_why"] = {"r2": "这条源片 probe 那一趟 403，画面按缩略图墙核过"}
    spec["stats"]["_winners_ue_why"] = "五类源都查空"
    return spec


@pytest.mark.parametrize("change, claim", [
    (lambda s: s["cover"].update(_approved_by_user=False), "cover._approved_by_user"),
    (lambda s: s["cover"].update(_layout_why="   "), "cover._layout_why"),
    (lambda s: s["segments"][1]["voice"].pop("_why"), "segments[1].voice._why"),
    (lambda s: s["segments"][1]["voice"].update(_why=None), "segments[1].voice._why"),
    (lambda s: s["segments"][2].update(_photo_source="http://photos.example/1"),
     "segments[2]._photo_source"),
    (lambda s: s["segments"][2].update(_photo_caption_safety=False),
     "segments[2]._photo_caption_safety"),
    (lambda s: s.update(_tts_backend_why=["Azure 401"]), "_tts_backend_why"),
    (lambda s: s.pop("_short_match_why"), "_short_match_why"),
    (lambda s: s.update(_cover_reuse_why="   "), "_cover_reuse_why"),
    (lambda s: s.update(_numeral_display_why=None), "_numeral_display_why"),
    (lambda s: s["segments"][0].pop("_board_on_screen_why"),
     "segments[0]._board_on_screen_why"),
    (lambda s: s["cover"]["portrait"].update(_face_check_why=""),
     "cover.portrait._face_check_why"),
    (lambda s: s["segments"][0].update(_quote_kind="interview"), "segments[0]._quote_kind"),
    (lambda s: s["segments"][0].pop("_digital_silence_why"),
     "segments[0]._digital_silence_why"),
    (lambda s: s.update(_no_probe_why={"r2": "  "}), "_no_probe_why"),
    (lambda s: s["stats"].update(_winners_ue_why=""), "stats._winners_ue_why"),
])
def test_认领按那道闸自己的口径算数(tmp_path, change, claim):
    """评审 2026-09-27：原来的 `_filled` 认 `False`、认一串空格——`build_cover` 两个都拒。

    认领「还在不在」要照那道闸自己的读法：`not cover.get("_approved_by_user")`、
    `str(cover.get("_layout_why", "")).strip()`、`isinstance(why, str) and why.strip()`……
    """
    base = _gated_spec()
    outdir = _rendered(tmp_path, base)
    claims = json.loads((outdir / ri.MANIFEST_NAME).read_text(encoding="utf-8"))["claims"]
    assert claim in {ri.path_str(p) for p in claims}, claims
    _edit(tmp_path, change, base)
    a = _assess(tmp_path, outdir)
    assert a.status == "render", a.reasons
    assert any("认领没了" in r and claim in r for r in a.reasons), a.reasons


def test_同名的纯说明删了照样可以重核对(tmp_path):
    """评审 2026-09-27：原来按键名在任意深度认领，`segments[i]._why` 一删就要重渲七分钟。

    只有闸真读的那个位置算认领（`_seg_voice` 读的是 `segments[i].voice._why`）。
    """
    base = _gated_spec()
    outdir = _rendered(tmp_path, base)
    claims = {ri.path_str(p) for p in json.loads(
        (outdir / ri.MANIFEST_NAME).read_text(encoding="utf-8"))["claims"]}
    for documentary in ("segments[1]._why", "cover.portrait._why", "stats._why",
                        "editorial._why", "_score_inset_why"):
        assert documentary not in claims, f"{documentary} 没有闸读，不该记成认领"

    def drop(spec):
        del spec["segments"][1]["_why"], spec["cover"]["portrait"]["_why"]
        del spec["stats"]["_why"], spec["editorial"]["_why"], spec["_score_inset_why"]
        spec["segments"][1]["voice"]["_why"] = "改个说法：崩盘那一段，降速"   # 措辞改了不算删

    _edit(tmp_path, drop, base)
    a = _assess(tmp_path, outdir)
    assert a.status == "reattest", a.reasons


def test_注解表登记的读取函数和代码对得上():
    """`Gate.where` 是照闸的读法手写的；谁在渲染路径上新读一处，这里红，逼着回头看位置。"""
    actual: dict[str, set[str]] = {}
    for module in _render_path_modules():
        for key, fn, _ in _key_reads(module):
            if key in ri.GATE_ANNOTATIONS:
                actual.setdefault(key, set()).add(fn)
    drift = {key: (sorted(note.read_by), sorted(actual.get(key, set())))
             for key, note in ri.GATE_ANNOTATIONS.items()
             if set(note.read_by) != actual.get(key, set())}
    assert not drift, f"GATE_ANNOTATIONS 的 read_by（登记的 / 代码里的）对不上：{drift}"
    for key, note in ri.GATE_ANNOTATIONS.items():
        for pattern in note.where:
            assert pattern.split(".")[-1] == key, f"{key} 的 where 写成了 {pattern}"


def test_同一个路径换了一张图_spec没动也要报重渲(tmp_path, capsys):
    """评审 2026-09-27：原来 spec 字节没变就先报「什么都不用做」，素材根本没核。"""
    outdir = _rendered(tmp_path)
    (tmp_path / "assets/reel/demo-cover.jpg").write_bytes(b"\xff\xd8 another photo")
    a = _assess(tmp_path, outdir)
    assert a.status == "render" and any("素材文件变了" in r for r in a.reasons), a.reasons
    assert rc.main(["--slug", SLUG, "--repo", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "要重渲" in out and "什么都不用做" not in out


# ── 链被动过手脚的，过不去 ─────────────────────────────────────────────────


@pytest.mark.parametrize("tamper, needle", [
    (lambda o: (o / ri.MANIFEST_NAME).write_text(
        (o / ri.MANIFEST_NAME).read_text(encoding="utf-8").replace("赛场之上", "网球有故事"),
        encoding="utf-8"), "被改过"),
    (lambda o: (o / "poster.jpg").write_bytes(b"\xff\xd8 swapped poster"), "poster.jpg"),
    (lambda o: (o / "subtitles.ass").write_text("Dialogue: 换过\n", encoding="utf-8"),
     "subtitles.ass"),
    (lambda o: (o / ri.MANIFEST_NAME).unlink(), "渲染时还没有这个功能"),
    (lambda o: (o / "render.json").write_text(json.dumps({
        **json.loads((o / "render.json").read_text(encoding="utf-8")),
        "film_sha256": "0" * 64}), encoding="utf-8"), "同一份成片"),
])
def test_凭证链本身对不上就判不了(tmp_path, tamper, needle):
    outdir = _rendered(tmp_path)
    tamper(outdir)
    spec_path = _edit(tmp_path, lambda s: s.update(_note="只改注解"))
    a = _assess(tmp_path, outdir)
    assert a.status == "unknown" and any(needle in r for r in a.reasons), a.reasons
    assert rc.apply(tmp_path, SLUG, outdir, spec_path, fetch=_release_ok).status == "unknown"


def test_Release上的成片被换过就不许重核对(tmp_path):
    """跨天重渲 `--clobber` 掉 tag 上的附件：本地链自洽，Release 已经是另一份。"""
    outdir = _rendered(tmp_path)
    before = (outdir / "qc_attestation.json").read_bytes()
    spec_path = _edit(tmp_path, lambda s: s.update(_note="只改注解"))
    for fetched in [(_sha(b"another film"), len(FILM)), (_sha(FILM), len(FILM) + 1)]:
        a = rc.apply(tmp_path, SLUG, outdir, spec_path, fetch=lambda url, f=fetched: f)
        assert a.status == "unknown" and "Release" in a.reasons[0], a.reasons
    assert (outdir / "qc_attestation.json").read_bytes() == before


@pytest.mark.parametrize("error", [
    urllib.error.HTTPError("https://example.test/demo.mp4", 404, "Not Found", None, None),
    urllib.error.URLError("Name or service not known"),
    TimeoutError("read timed out"),
    http.client.IncompleteRead(b"partial"),
])
def test_Release上的成片取不到_判不了而不是一屏traceback(tmp_path, capsys, monkeypatch, error):
    """Release 附件被删（404）、断网、读到一半断：核不了它是不是那一份 → 判不了、凭证不动，
    CLI 退出码照旧非零（--apply 那一步红），但报的是人话。"""
    outdir = _rendered(tmp_path)
    before = (outdir / "qc_attestation.json").read_bytes()
    spec_path = _edit(tmp_path, lambda s: s.update(_note="只改注解"))

    def unreachable(url):
        raise error

    a = rc.apply(tmp_path, SLUG, outdir, spec_path, fetch=unreachable)
    assert a.status == "unknown", a.reasons
    assert "取不到" in a.reasons[0] and type(error).__name__ in a.reasons[0], a.reasons
    assert (outdir / "qc_attestation.json").read_bytes() == before
    monkeypatch.setitem(rc.apply.__kwdefaults__, "fetch", unreachable)   # CLI 走默认的 fetch
    code = rc.main(["--slug", SLUG, "--repo", str(tmp_path), "--outdir", str(outdir),
                    "--apply"])
    out = capsys.readouterr().out
    assert code != 0 and "[判不了]" in out and "取不到" in out, out


def test_CLI退出码_本地问一句就知道派哪一档(tmp_path, capsys):
    outdir = _rendered(tmp_path)
    argv = ["--slug", SLUG, "--repo", str(tmp_path)]
    assert rc.main(argv) == 0 and "什么都不用做" in capsys.readouterr().out
    _edit(tmp_path, lambda s: s.update(_note="只改注解"))
    assert rc.main(argv) == 0 and "mode=reattest" in capsys.readouterr().out
    _edit(tmp_path, lambda s: s["segments"][1].update(narration="换一句"))
    assert rc.main(argv) == 1 and "要重渲" in capsys.readouterr().out
    (outdir / ri.MANIFEST_NAME).unlink()
    assert rc.main(argv) == 2 and "判不了" in capsys.readouterr().out


# ── 发布门禁：认重核对出的凭证，但不信它一面之词 ─────────────────────────────


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _commit(repo: Path) -> None:
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=a@b", "-c", "user.name=c", "commit", "-qm", "x")


@pytest.fixture()
def reattested(tmp_path: Path) -> tuple[Path, Path]:
    """渲完之后只补了 `push.auto`（medvedev-damm e15e73e5 的形状），重核对过。"""
    _git(tmp_path, "init", "-q")
    outdir = _rendered(tmp_path)
    _commit(tmp_path)
    spec_path = _edit(tmp_path, lambda s: s.update(push={"auto": True, "summary": "她赢了"}))
    # 没重核对之前：老闸照旧拦住（这是它本来就该做的事，一个字没松）
    with pytest.raises(gate.Skip, match="spec 在质检后发生过变化"):
        gate.validate_qc(tmp_path, SLUG, outdir)
    assert rc.apply(tmp_path, SLUG, outdir, spec_path, fetch=_release_ok).status == "reattest"
    _commit(tmp_path)
    return tmp_path, outdir


def test_发布门禁认重核对出的凭证(reattested):
    repo, outdir = reattested
    assert gate.validate_qc(repo, SLUG, outdir) == _sha(FILM)
    gate.wants_auto_push(repo, SLUG, outdir)          # 不抛 Skip ＝ 该发


def test_重核对之后账本已经sent的照样拦住(reattested):
    """账本按成片 hash 记，重核对之后还是同一份成片——「没有真改动就不该有新消息」。"""
    repo, outdir = reattested
    from publication_ledger import write  # noqa: PLC0415
    write(repo, gate.LEDGER_COLUMN, SLUG, _sha(FILM), status="sent",
          run_url="https://run/0", now="2026-09-27T11:00:00Z")
    _commit(repo)
    with pytest.raises(gate.Skip, match="持久发布账本已有 sent"):
        gate.wants_auto_push(repo, SLUG, outdir)
    with pytest.raises(SystemExit, match="禁止盲目重发"):
        gate.ledger_status(repo, outdir, "sending", "https://run/1", "now")


@pytest.mark.parametrize("field", ["summary", "lead"])
@pytest.mark.parametrize("marker", [True, False], ids=["同日_pushed.json在", "跨天_只剩账本"])
def test_已发的片子只改推送文案_重核对之后也不重推(tmp_path, field, marker):
    """账号所有者 2026-09-27 对复审那一问的答复原话：「只改推送文案不重推」。

    发出去之后只改 `push.summary` / `push.lead`：成片一个像素没变，重核对照样出凭证
    （文案是推送那一刻现读的，下次真要发时用的是新的）；但这一份成片**已经发过**——
    `pushed.json` 在（同日）或只剩发布账本那一笔 `sent`（跨天、目录里没有 marker），
    门禁都拦住，连表单勾「强制推送」也拦住。要新文案发出去，产物得真的变（CLAUDE.md 9/22）。
    """
    _git(tmp_path, "init", "-q")
    base = _spec()
    base["push"] = {"auto": True, "summary": "她赢了", "lead": "决胜盘一度落后。"}
    outdir = _rendered(tmp_path, base)
    from publication_ledger import write  # noqa: PLC0415
    write(tmp_path, gate.LEDGER_COLUMN, SLUG, _sha(FILM), status="sent",
          run_url="https://run/0", now="2026-09-27T11:00:00Z")
    if marker:
        (outdir / gate.MARKER).write_text('{"at": "2026-09-27T11:00:00Z"}\n', encoding="utf-8")
    _commit(tmp_path)

    spec_path = _edit(tmp_path, lambda s: s["push"].update({field: "改过的推送文案"}), base)
    assert _assess(tmp_path, outdir).status == "reattest"
    assert rc.apply(tmp_path, SLUG, outdir, spec_path, fetch=_release_ok).status == "reattest"
    _commit(tmp_path)
    assert gate.validate_qc(tmp_path, SLUG, outdir) == _sha(FILM)     # 凭证是成立的
    for forced in (False, True):
        with pytest.raises(gate.Skip, match="持久发布账本已有 sent"):
            gate.wants_auto_push(tmp_path, SLUG, outdir, forced=forced)
    with pytest.raises(SystemExit, match="禁止盲目重发"):
        gate.ledger_status(tmp_path, outdir, "sending", "https://run/1", "now")
    if marker:
        # 账本那一笔哪天丢了（老片子 2026-08-24 之前没有账本），pushed.json 照样拦住
        ledger = sorted(p.relative_to(tmp_path).as_posix()
                        for p in (tmp_path / "data").rglob(f"{SLUG}.json"))
        assert ledger, "账本那一笔没落在 data/ 下，这半条测不到东西"
        _git(tmp_path, "rm", "-q", *ledger)
        _commit(tmp_path)
        with pytest.raises(gate.Skip, match="已经推过了"):
            gate.wants_auto_push(tmp_path, SLUG, outdir, forced=True)


def test_质检只钉描述这份成片的清单(tmp_path, capsys):
    """复审 2026-09-28：盘上躺着上一趟剩的清单（记的是别的成片）、`render.json` 又没钉它
    （导入流程拷进来的那种）——原来照钉，发布门禁报「render.json 钉的清单和凭证钉的不是
    同一份」、自动链只印一行 `[跳过]`。现在不钉，门禁退回 spec 字节那一道照发。"""
    _git(tmp_path, "init", "-q")
    outdir = _rendered(tmp_path)
    film = outdir / f"{SLUG}.mp4"
    film.write_bytes(b"another-film")                      # 同一个目录里的另一份成片
    (outdir / "render.json").write_text(json.dumps({
        "film_seconds": 1, "video_url": "https://example.test/x.mp4",
        "video_bytes": len(b"another-film")}), encoding="utf-8")
    spec_path = tmp_path / "specs/reels" / f"{SLUG}.json"
    landed.write_attestation(film, spec_path, json.loads(spec_path.read_text(encoding="utf-8")))
    qc = json.loads((outdir / "qc_attestation.json").read_text(encoding="utf-8"))
    assert "render_inputs_sha256" not in qc
    assert "不是这一份成片的渲染输入清单" in capsys.readouterr().out
    film.unlink()
    _commit(tmp_path)
    assert gate.validate_qc(tmp_path, SLUG, outdir) == _sha(b"another-film")
    # 对得上的那一份照钉（`_rendered` 走的就是这条路，见上面那几条）
    assert json.loads((_rendered(tmp_path / "ok") / "qc_attestation.json")
                      .read_text(encoding="utf-8"))["render_inputs_sha256"]


def test_稀疏检出里本地问_不把人送去白渲(tmp_path, capsys):
    """复审 2026-09-28：`output/` 那一格在仓库里、只是没检出——原来报「一份都没有——先
    mode=render」。现在按 `git ls-tree` 认出来，告诉人先拉下来。"""
    _git(tmp_path, "init", "-q")
    outdir = _rendered(tmp_path)
    _commit(tmp_path)
    _git(tmp_path, "rm", "-rq", "--cached", "--", "output")   # 只从工作区消失：
    _git(tmp_path, "reset", "-q")                              # 索引/HEAD 里照旧有
    for p in sorted(outdir.rglob("*"), reverse=True):
        p.unlink() if p.is_file() else p.rmdir()
    assert rc.main(["--slug", SLUG, "--repo", str(tmp_path)]) == 2
    out = capsys.readouterr().out
    assert "git sparse-checkout add output/2026-09-27/reel/demo" in out
    assert "先 mode=render" not in out


def test_O4换封面永远走render不走重核对(tmp_path):
    """O4 自动换图（`cover_upgrade.apply_upgrade`）换的是封面——真改动，走 render。

    用 `cover_upgrade.upgraded_portrait` 自己拼出来的 portrait，照 `apply_upgrade` 的写法
    落盘：`frame_at` 没了、`image` 指向新存的 `assets/reel/<slug>-official.jpg`，外加一段
    `_why` / `_gates` 注解。注解那一半重核对认，封面那一半不认——判 render，凭证不动。
    """
    import cover_upgrade as cu  # noqa: PLC0415

    base = _spec()
    base["cover"]["portrait"] = {"frame_at": 162.4, "zoom": 1.2,
                                 "_why": "推送窗口内没有官方实拍，抽帧"}
    outdir = _rendered(tmp_path, base)
    before = (outdir / "qc_attestation.json").read_bytes()

    chosen = {
        "candidate": cu.Candidate(channel="wta", url="https://img.test/official.jpg",
                                  caption="Coco Gauff in action"),
        "evidence": {"size": (4000, 2667),
                     "layout": {"zoom": 1.0, "focus": 0.5, "focus_y": 0.3, "fill": 2.47,
                                "face_out": [400, 300, 700, 650]},
                     "face": {"similarity": {"高芙": 0.61}, "ear": 0.3}},
        "blob": b"\xff\xd8 new official photo",
    }
    ctx = cu.MatchContext(slug=SLUG, subject_zh="高芙", subject_en="Coco Gauff",
                          event_en="Beijing", tz="Asia/Shanghai")
    image_rel = f"assets/reel/{SLUG}-official.jpg"
    (tmp_path / image_rel).write_bytes(chosen["blob"])
    portrait = cu.upgraded_portrait(base["cover"]["portrait"], chosen, ctx, image_rel)
    assert "frame_at" not in portrait and portrait["image"] == image_rel
    spec_path = _edit(tmp_path, lambda s: s["cover"].update(portrait=portrait), base)

    a = _assess(tmp_path, outdir)
    assert a.status == "render", a.reasons
    assert any("封面" in r for r in a.reasons), a.reasons
    assert rc.apply(tmp_path, SLUG, outdir, spec_path, fetch=_release_ok).status == "render"
    assert (outdir / "qc_attestation.json").read_bytes() == before, "拒绝的那一趟不许动凭证"


def test_reattest不顶掉在跑的render():
    """O4 无人值守派的 render 在跑时有人派 reattest：reattest 排队，不把 render 顶掉。"""
    import yaml  # noqa: PLC0415

    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    cancel = doc["concurrency"]["cancel-in-progress"]
    assert "github.event.inputs.mode != 'reattest'" in cancel, cancel
    assert "github.event.inputs.mode != 'push'" in cancel, cancel


def test_发布门禁不信重核对凭证的一面之词(reattested):
    """有人手搓一张凭证（spec 字节对得上），而旁白其实改了——门禁自己重算投影拦住。"""
    repo, outdir = reattested
    spec_path = _edit(repo, lambda s: (s.update(push={"auto": True, "summary": "她赢了"}),
                                       s["segments"][1].update(narration="偷改的旁白")))
    qc_path = outdir / "qc_attestation.json"
    qc = json.loads(qc_path.read_text(encoding="utf-8"))
    qc["spec_sha256"] = _sha(spec_path.read_bytes())
    qc_path.write_text(json.dumps(qc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    meta = json.loads((outdir / "render.json").read_text(encoding="utf-8"))
    meta["qc_attestation_sha256"] = _sha(qc_path.read_bytes())
    (outdir / "render.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    _commit(repo)
    with pytest.raises(gate.Skip, match="重核对凭证不成立.*第 2 段旁白"):
        gate.validate_qc(repo, SLUG, outdir)

    # 重核对凭证没钉清单也不认；钉着的清单被换过也不认
    del qc["render_inputs_sha256"]
    qc_path.write_text(json.dumps(qc, ensure_ascii=False), encoding="utf-8")
    meta["qc_attestation_sha256"] = _sha(qc_path.read_bytes())
    (outdir / "render.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    _commit(repo)
    with pytest.raises(gate.Skip, match="没有钉住渲染输入清单"):
        gate.validate_qc(repo, SLUG, outdir)


def _forge(outdir: Path, spec_path: Path, *, manifest_too: bool = False) -> None:
    """手搓一张**不带 `reattest`** 的凭证：spec 字节补对、`render.json` 跟着指过去。

    `manifest_too`：连清单记的 spec 字节也改掉、三处 sha 重新钉上——整条链自洽，
    只剩「清单里的投影还是渲染那一刻的」这一处破绽。
    """
    spec_sha = _sha(spec_path.read_bytes())
    meta = json.loads((outdir / "render.json").read_text(encoding="utf-8"))
    qc_path = outdir / "qc_attestation.json"
    qc = json.loads(qc_path.read_text(encoding="utf-8"))
    if manifest_too:
        manifest_path = outdir / ri.MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["spec_sha256"] = spec_sha
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
        qc["render_inputs_sha256"] = meta["render_inputs_sha256"] = _sha(
            manifest_path.read_bytes())
    qc["spec_sha256"] = spec_sha
    qc_path.write_text(json.dumps(qc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    meta["qc_attestation_sha256"] = _sha(qc_path.read_bytes())
    (outdir / "render.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def test_发布门禁每次都重算投影_不看凭证带不带reattest(tmp_path):
    """评审 2026-09-27：原来只在凭证带 `reattest` 时才重算——手搓的凭证不写那一段就绕过去了。"""
    _git(tmp_path, "init", "-q")
    outdir = _rendered(tmp_path)
    _commit(tmp_path)

    # ① 偷改了旁白、整条链（清单 / 凭证 / render.json）都手搓自洽、凭证不带 reattest：
    #    只剩重算投影这一道拦得住
    spec_path = _edit(tmp_path, lambda s: s["segments"][1].update(narration="偷改的旁白"))
    _forge(outdir, spec_path, manifest_too=True)
    _commit(tmp_path)
    with pytest.raises(gate.Skip, match="渲染输入对不上.*第 2 段旁白"):
        gate.validate_qc(tmp_path, SLUG, outdir)


def _repin_manifest(outdir: Path, change) -> None:
    """改清单、再把凭证和 render.json 钉到改过的那一份上（造一份「旧口径渲的」产物）。"""
    manifest_path = outdir / ri.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    change(manifest)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    qc_path = outdir / "qc_attestation.json"
    qc = json.loads(qc_path.read_text(encoding="utf-8"))
    meta = json.loads((outdir / "render.json").read_text(encoding="utf-8"))
    qc["render_inputs_sha256"] = meta["render_inputs_sha256"] = _sha(manifest_path.read_bytes())
    qc_path.write_text(json.dumps(qc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    meta["qc_attestation_sha256"] = _sha(qc_path.read_bytes())
    (outdir / "render.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def _as_v1(manifest: dict) -> None:
    """v1 的清单：投影 `sort_keys` 之后存（2026-09-27 之前的口径）。"""
    manifest["version"] = 1
    manifest["projection"] = json.loads(json.dumps(manifest["projection"], sort_keys=True))


def test_旧口径的清单_普通渲染照发(tmp_path):
    """评审 2026-09-27（第二轮）：门禁原来不看清单版本，一律按今天的口径重算——
    VERSION 一升，升级之前渲、之后才推的片子就被判成「渲染输入对不上」（v1→v2 那次
    「按原顺序比」会把每份 v1 清单都判成键的顺序变了）。

    普通渲染的凭证照旧由 spec 字节逐字节钉着；重核对凭证判不了就不认。
    """
    _git(tmp_path, "init", "-q")
    outdir = _rendered(tmp_path)
    _repin_manifest(outdir, _as_v1)
    _commit(tmp_path)
    # 前提：拿今天的口径去比这份 v1 清单，确实会误判（不是测试一厢情愿）
    manifest = json.loads((outdir / ri.MANIFEST_NAME).read_text(encoding="utf-8"))
    spec_bytes = (tmp_path / "specs/reels" / f"{SLUG}.json").read_bytes()
    assert any("键的顺序" in p for p in ri.spec_problems(spec_bytes, manifest))
    assert gate.validate_qc(tmp_path, SLUG, outdir) == _sha(FILM)

    # 版本号不是「比今天旧的一个整数」（将来的、乱写的）：不认
    _repin_manifest(outdir, lambda m: m.update(version=ri.VERSION + 1))
    _commit(tmp_path)
    with pytest.raises(gate.Skip, match="的版本 .* 不认"):
        gate.validate_qc(tmp_path, SLUG, outdir)


def test_旧口径的清单_重核对凭证不认(reattested):
    """同上一条：重核对出的凭证钉着旧口径的清单——判不了，不认。"""
    repo, r_outdir = reattested
    assert gate.validate_qc(repo, SLUG, r_outdir) == _sha(FILM)   # 前提：改之前是认的
    _repin_manifest(r_outdir, _as_v1)
    _commit(repo)
    with pytest.raises(gate.Skip, match="判不了，不认"):
        gate.validate_qc(repo, SLUG, r_outdir)


#: 以后可能有人对投影那几张表做的改动——**都不升 `VERSION`**。
_TABLE_CHANGES = {
    # 把一个注解改判成「进成片」（评审第三轮原样复现的那一条）
    "RENDER_ANNOTATIONS 加键": lambda mp: mp.setitem(
        ri.RENDER_ANNOTATIONS, "_facts", "假设哪天渲染开始读它"),
    # 把一个真字段改判成「只进推送」
    "PUBLISH_FIELDS 加键": lambda mp: mp.setitem(ri.PUBLISH_FIELDS, "source_url", frozenset()),
}


@pytest.mark.parametrize("change", list(_TABLE_CHANGES.values()), ids=list(_TABLE_CHANGES))
def test_投影那几张表改了而版本号没升_已渲的片子照发(tmp_path, monkeypatch, change):
    """评审 2026-09-27（第三轮）复现的：往 `RENDER_ANNOTATIONS` 里加一个键、没升
    `VERSION`，改之前渲、改之后才合并的片子——spec 一个字节没动——门禁拿新口径比旧
    清单，报「渲染输入变了——渲染参数：_facts」。自动链上那个 `Skip` 只印一行
    `[跳过]`，这条片子就**不吭声地永远不推**。

    现在清单记着渲染那一刻的口径指纹（`rules_digest`），门禁按「旧口径」走：普通渲染
    退回 spec 字节那一道（照发），`reattest_check` 判不了（不拿新口径误判成「要重渲」）。
    """
    _git(tmp_path, "init", "-q")
    outdir = _rendered(tmp_path)
    _commit(tmp_path)
    manifest = json.loads((outdir / ri.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["rules"] == ri.rules_digest() and ri.same_rules(manifest)
    assert gate.validate_qc(tmp_path, SLUG, outdir) == _sha(FILM)

    change(monkeypatch)
    # 前提：拿改过的表去比这份清单，确实会误判（不是测试一厢情愿）
    spec_bytes = (tmp_path / "specs/reels" / f"{SLUG}.json").read_bytes()
    assert ri.spec_problems(spec_bytes, manifest), "改表没改动投影，这条测试是空转"
    assert not ri.same_rules(manifest)
    assert gate.validate_qc(tmp_path, SLUG, outdir) == _sha(FILM)
    a = _assess(tmp_path, outdir)
    assert a.status == "unknown" and any("旧口径" in r for r in a.reasons), a.reasons


@pytest.mark.parametrize("change", list(_TABLE_CHANGES.values()), ids=list(_TABLE_CHANGES))
def test_投影那几张表改了而版本号没升_重核对凭证不认(reattested, monkeypatch, change):
    repo, r_outdir = reattested
    assert gate.validate_qc(repo, SLUG, r_outdir) == _sha(FILM)   # 前提：改之前是认的
    change(monkeypatch)
    with pytest.raises(gate.Skip, match="旧口径.*判不了，不认"):
        gate.validate_qc(repo, SLUG, r_outdir)


def _sorted_project(spec, _orig=ri.project):
    return json.loads(json.dumps(_orig(spec), sort_keys=True))


def _strip_sources_annotations(spec, _orig=ri.project):
    out = _orig(spec)
    if isinstance(out.get("sources"), dict):
        out["sources"] = {k: v for k, v in out["sources"].items() if not str(k).startswith("_")}
    return out


def _order_blind_diff(old, new, path=None, _orig=ri.diff_paths):
    return [p for p in _orig(old, new, path) if p[-1:] != [ri.ORDER]]


@pytest.mark.parametrize("attr, value", [
    ("ASSET_SUFFIXES", ri.ASSET_SUFFIXES | {".pdf"}),
    ("project", _sorted_project),                     # v1 那种 sort_keys
    ("project", _strip_sources_annotations),          # 第二轮那种「sources 里的 _ 键当注解剥」
    ("canonical", lambda obj: json.dumps(obj, separators=(",", ":"))),   # ensure_ascii
    ("diff_paths", _order_blind_diff),                # 不报键的顺序
], ids=["后缀表", "投影排序", "sources剥下划线", "canonical转义", "diff不看顺序"])
def test_口径指纹跟着投影的行为变(monkeypatch, attr, value):
    """`rules_digest` 不只认表里的键名，`project` / `canonical` / `diff_paths` 在样本
    spec 上的行为一变也要变——这几处每一处改了都会让旧清单被误判。"""
    before = ri.rules_digest()
    monkeypatch.setattr(ri, attr, value)
    assert ri.rules_digest() != before


def test_口径指纹跨进程稳定():
    """渲染在一台 runner 上算、门禁在另一台上算：指纹要是跟着哈希种子变（frozenset 的
    遍历顺序），每一份清单都会被当成旧口径——重核对永远判不了，而且不吭声。"""
    code = "import sys; sys.path.insert(0, 'tools'); import render_inputs as r; print(r.rules_digest())"
    got = {subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                          check=True, env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"}
                          ).stdout.strip() for seed in ("1", "2", "3")}
    assert got == {ri.rules_digest()}, got


def test_加一道闸不动口径指纹(monkeypatch):
    """反过来：`GATE_ANNOTATIONS` 不进指纹——兄弟分支每加一道闸（归类测试逼着加的），
    已渲片子的清单照旧有效，不会平白全部退回旧口径。"""
    before = ri.rules_digest()
    monkeypatch.setitem(ri.GATE_ANNOTATIONS, "_new_gate_why",
                        ri._gate("假设的新闸", "new_gate", "_new_gate_why"))
    assert ri.rules_digest() == before


def test_闸口径收严了_spec没动的片子照发_改过的照样按新口径判(tmp_path, monkeypatch):
    """复审 fix 轮：`GATE_ANNOTATIONS` 故意不进口径指纹，于是某条分支把 `Gate.rule` 收严
    （`text_str` → `text`）之后，门禁拿新口径重判渲染时记下的认领——spec 一个字节没动的
    片子也会被判「认领没了」、自动链只印一行 `[跳过]`。spec 就是渲染那一份时不重判；
    spec 改过（重核对）时照旧按今天的口径判。"""
    _git(tmp_path, "init", "-q")
    outdir = _rendered(tmp_path)
    _commit(tmp_path)
    strict = ri.GATE_ANNOTATIONS["_layout_why"]._replace(rule=lambda v: False)
    monkeypatch.setitem(ri.GATE_ANNOTATIONS, "_layout_why", strict)
    assert gate.validate_qc(tmp_path, SLUG, outdir) == _sha(FILM)

    # 改过 spec 的（重核对出的凭证）：新口径照样咬
    monkeypatch.undo()
    spec_path = _edit(tmp_path, lambda s: s.update(_note="只改注解"))
    assert rc.apply(tmp_path, SLUG, outdir, spec_path, fetch=_release_ok).status == "reattest"
    _commit(tmp_path)
    monkeypatch.setitem(ri.GATE_ANNOTATIONS, "_layout_why", strict)
    with pytest.raises(gate.Skip, match="认领没了：cover._layout_why"):
        gate.validate_qc(tmp_path, SLUG, outdir)


def test_spec变了而凭证不是重核对出的_发布门禁不认(tmp_path):
    """只改了注解（投影不变）、却手搓凭证而不走 reattest：清单记的 spec 和凭证记的
    不是同一份——那等于绕过了 runner 那一步的素材字节和 Release 现算，不认。"""
    _git(tmp_path, "init", "-q")
    outdir = _rendered(tmp_path)
    _commit(tmp_path)
    spec_path = _edit(tmp_path, lambda s: s.update(_note="只改注解"))
    _forge(outdir, spec_path)
    _commit(tmp_path)
    with pytest.raises(gate.Skip, match="而凭证不是重核对出的"):
        gate.validate_qc(tmp_path, SLUG, outdir)


def test_render_json钉的清单要和凭证钉的是同一份(tmp_path):
    _git(tmp_path, "init", "-q")
    outdir = _rendered(tmp_path)
    meta = json.loads((outdir / "render.json").read_text(encoding="utf-8"))
    meta["render_inputs_sha256"] = "0" * 64
    (outdir / "render.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    _commit(tmp_path)
    with pytest.raises(gate.Skip, match="render.json 钉的 render_inputs.json 和凭证钉的不是同一份"):
        gate.validate_qc(tmp_path, SLUG, outdir)


def test_清单在质检后被换过发布门禁也拦住(tmp_path):
    _git(tmp_path, "init", "-q")
    outdir = _rendered(tmp_path)
    manifest = outdir / ri.MANIFEST_NAME
    manifest.write_text(manifest.read_text(encoding="utf-8") + " ", encoding="utf-8")
    _commit(tmp_path)
    with pytest.raises(gate.Skip, match="在质检后变过"):
        gate.validate_qc(tmp_path, SLUG, outdir)


# ── 「哪些字段进成片」不是靠记的 ────────────────────────────────────────────


_IMPORT_ROOTS = ("tools/build_match_reel.py", "tools/check_reel_landed.py")


def _resolve(name: str) -> Path | None:
    if "." not in name and (ROOT / "tools" / f"{name}.py").is_file():
        return ROOT / "tools" / f"{name}.py"
    if name.startswith("tennislive"):
        p = ROOT / "src" / Path(*name.split("."))
        if p.with_suffix(".py").is_file():
            return p.with_suffix(".py")
        if (p / "__init__.py").is_file():
            return p / "__init__.py"
    return None


#: 采访线（赛后开麦）的入口：这几个**函数里**的延迟 import 不跟着走。`mode=reattest`
#: 只管竖版短片（`match-reel.yml`），而这两处是共用模块里专给采访 spec 的那一半——
#: 跟着走进去，`build_interview_clip` 整条线的读法（顶栏开关、片尾板认领、推送标题
#: 进台头……）就全要在竖版短片的表里登记，其中「采访台头印 `push`」还得登成
#: 「只进推送」，那是假话（2026-09-28 合 main 时量出来的：两处延迟 import 把 7 个
#: 采访模块、25 处读法拉进了扫描）。
#: 只剪**这几处 import**，不剪模块：别的地方哪天真从竖版短片 import 了采访模块，它照样
#: 进图、照样要归类；这几个函数本身也照样扫（`interview_*` 读到的键照旧要登记）。
#: 判据 `test_采访线的入口只从采访线的函数调`：这几个函数在图里只被采访线的函数、
#: CLI 入口调，渲染/质检一条都够不着。
_OTHER_LINE_GATEWAYS: dict[tuple[str, str], str] = {
    ("check_polyphones.py", "interview_texts"):
        "采访 spec 念出来的文本（build_interview_clip 调）；竖版短片走 reel_texts",
    ("taste_gates_extra.py", "interview_ledger_dir"):
        "采访线的发布账本目录（interview_taste_extra 调）；竖版短片走 reel_ledger_dir",
}


def _imports_in(tree: ast.AST) -> list[tuple[str, str]]:
    """(所在顶层函数, 模块名)：每一处 import，含函数里的延迟 import。"""
    out: list[tuple[str, str]] = []
    for top in getattr(tree, "body", []):
        fn = top.name if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)) else "<module>"
        for node in ast.walk(top):
            if isinstance(node, ast.Import):
                out += [(fn, a.name) for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                out += [(fn, node.module)] + [(fn, f"{node.module}.{a.name}") for a in node.names]
    return out


def _render_path_modules() -> list[Path]:
    """从渲染和质检入口顺着 import 走一遍（含函数里的延迟 import，采访线入口除外）。"""
    seen: dict[Path, None] = {}
    todo = [ROOT / r for r in _IMPORT_ROOTS]
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        seen[f] = None
        for fn, name in _imports_in(ast.parse(f.read_text(encoding="utf-8"))):
            if (f.name, fn) in _OTHER_LINE_GATEWAYS:
                continue
            p = _resolve(name)
            if p and p not in seen:
                todo.append(p)
    return list(seen)


#: 读法里拼出来的键（f"_{x}"、"_" + x）认不出是哪一个，一律记成这个——它不在任何
#: 表里，所以必然报「没归类」，逼着把它改成字面键名。
DYNAMIC_KEY = "_<拼出来的键>"


def _const_strings(value: ast.AST | None) -> set[str] | None:
    """模块顶层一个常量的字符串值：`"_x"`、`("_a", "_b")`、`frozenset({"_a"})`……不是返回 None。"""
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return {value.value}
    if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
            and value.func.id in ("frozenset", "set", "tuple", "list")
            and len(value.args) == 1 and not value.keywords):
        value = value.args[0]
    if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
        return {e.value for e in value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return None


def _module_consts(path: Path) -> dict[str, set[str]]:
    """模块顶层 `NAME = <字符串或字符串序列>` → 值（`x.get(KEY)` / `for k in KEYS` 要用）。"""
    stat = path.stat()
    return {k: set(v) for k, v in _module_consts_cached(str(path), stat.st_mtime_ns,
                                                        stat.st_size).items()}


@functools.lru_cache(maxsize=None)
def _module_consts_cached(path: str, _mtime: int, _size: int) -> dict[str, frozenset[str]]:
    consts: dict[str, set[str]] = {}
    for node in ast.parse(Path(path).read_text(encoding="utf-8")).body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign) else [])
        values = _const_strings(getattr(node, "value", None))
        if values is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                consts.setdefault(target.id, set()).update(values)
    return {k: frozenset(v) for k, v in consts.items()}


def _import_path(name: str, near: Path) -> Path | None:
    """import 的模块名 → 文件：同目录的兄弟模块（测试里造的）优先，其次 tools/、src/。"""
    sibling = near.parent / f"{name}.py"
    return sibling if "." not in name and sibling.is_file() else _resolve(name)


def _key_reads(path: Path) -> list[tuple[str, str, int]]:
    """(键, 所在函数, 行号)：`x[K]`、`x.get/pop/setdefault(K)`、`K in x`。

    K 不只认字面量（评审 2026-09-27：只认字面量是个潜在的洞）——还认模块顶层的
    字符串常量（`KEY = "_why"` 然后 `x.get(KEY)`）、循环变量走的字面量序列
    （`for k in ("_a", "_b"): x.get(k)`）；以 `_` 开头拼出来的键（f-string、`+`）
    认不出是哪一个，记成 `DYNAMIC_KEY`。

    **不经下标、按键名比出来的读**也认（评审第三轮：原来看不见）——
    `for k, v in spec.items(): if k == "_x"`、`k in ("_x", "_y")`、
    `spec.keys() & {"_x"}` / `set(spec) >= {"_x"}`：比较或集合运算里出现的
    `_` 开头字面量（和只进推送的字段名）一律当成一次读。

    **常量不只认字面量本身**（复审 fix 轮量出来的三个盲区，都拿合成模块复现过）：
    模块顶层的序列常量（`KEYS = ("_a", "_b")` / `frozenset({...})`，然后
    `for k in KEYS` 或 `k in KEYS`）、从别的模块 import 进来的常量
    （`from m import KEY` / `import m` 再 `m.KEY`）——都按它们的值算。按后缀／前缀
    批量读（`k.endswith("_why")`）不是单个键，归 `_affix_batches` 那张表管。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    consts = _module_consts(path)
    modules: dict[str, dict[str, set[str]]] = {}      # `import m as alias` → m 的常量
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            source = _import_path(node.module, path)
            if source is None:
                continue
            theirs = _module_consts(source)
            for alias in node.names:
                if alias.name in theirs:
                    consts.setdefault(alias.asname or alias.name, set()).update(theirs[alias.name])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                # `import a.b.c` 绑定的是 `a`，`a.X` 不是 c 的常量——只认有别名或不带点的
                source = _import_path(alias.name, path)
                if source is not None and (alias.asname or "." not in alias.name):
                    modules[alias.asname or alias.name] = _module_consts(source)
    names: dict[str, set[str]] = {k: set(v) for k, v in consts.items()}
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.comprehension)) and isinstance(node.target, ast.Name):
            values = (_const_strings(node.iter)
                      if isinstance(node.iter, (ast.Tuple, ast.List, ast.Set))
                      else set(consts.get(node.iter.id, set()))
                      if isinstance(node.iter, ast.Name) else None)
            if values:
                names.setdefault(node.target.id, set()).update(values)

    def const_of(arg: ast.AST) -> set[str]:
        """一个操作数若是常量（本模块顶层、import 进来的、`m.KEY`），它的值。"""
        if isinstance(arg, ast.Name):
            return consts.get(arg.id, set())
        if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name):
            return modules.get(arg.value.id, {}).get(arg.attr, set())
        return set()

    def keys_of(arg: ast.AST) -> set[str]:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return {arg.value}
        if isinstance(arg, ast.Name):
            return names.get(arg.id, set())
        if isinstance(arg, ast.Attribute):
            return const_of(arg)
        head = (arg.values[0] if isinstance(arg, ast.JoinedStr) and arg.values
                else arg.left if isinstance(arg, ast.BinOp) else None)
        if (isinstance(head, ast.Constant) and isinstance(head.value, str)
                and head.value.startswith("_") and not head.value.startswith("__")):
            return {DYNAMIC_KEY}
        return set()

    def named_keys(operand: ast.AST) -> set[str]:
        """比较/集合运算的一个操作数里，按名字点到的键：字面量本身、字面量序列的元素，
        或一个常量（顶层 / import 进来的）的值。循环变量**不**算——它按名字全模块共享，
        拿来比较会把别的函数的键记到这个函数头上。"""
        elts = (operand.elts if isinstance(operand, (ast.Tuple, ast.List, ast.Set))
                else [operand])
        values = {e.value for e in elts
                  if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        values |= const_of(operand)
        return {v for v in values
                if (v.startswith("_") and not v.startswith("__")) or v in ri.PUBLISH_FIELDS}

    out: list[tuple[str, str, int]] = []

    def visit(node: ast.AST, fn: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn = node.name
        keys: set[str] = set()
        if isinstance(node, ast.Subscript):
            keys = keys_of(node.slice)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr in ("get", "pop", "setdefault") and node.args):
            keys = keys_of(node.args[0])
        elif isinstance(node, ast.Compare):
            if any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
                keys = set(keys_of(node.left))
            for operand in [node.left, *node.comparators]:
                keys |= named_keys(operand)
        elif (isinstance(node, ast.BinOp)
              and isinstance(node.op, (ast.BitAnd, ast.BitOr, ast.BitXor, ast.Sub))):
            for operand in (node.left, node.right):
                if isinstance(operand, (ast.Set, ast.Name, ast.Attribute)):
                    keys |= named_keys(operand)
        for key in sorted(keys):
            out.append((key, fn, getattr(node, "lineno", 0)))
        for child in ast.iter_child_nodes(node):
            visit(child, fn)

    visit(tree, "<module>")
    return out


def test_读取扫描认得出不是字面量的键(tmp_path):
    """上面那条归类判据的眼睛：常量、循环变量、拼出来的键都要看得见，否则是空转。"""
    module = tmp_path / "m.py"
    module.write_text(
        'KEY = "_via_const"\n'
        "def gate(spec, x):\n"
        "    spec.get(KEY)\n"
        '    for k in ("_via_loop", "plain"):\n'
        "        spec[k]\n"
        '    spec.get(f"_{x}_why")\n'
        '    return ("_" + x) in spec\n'
        "def by_name(spec):\n"
        "    for k, v in spec.items():\n"
        '        if k == "_via_eq" or "_via_eq_rhs" != k:\n'
        "            pass\n"
        '        if k in ("_via_in_literal", "plain2"):\n'
        "            pass\n"
        '    if spec.keys() & {"_via_set_op"}:\n'
        "        pass\n"
        '    return set(spec) >= {"_via_set_cmp"} or any(k == "push" for k in spec)\n',
        encoding="utf-8")
    keys = {(key, fn) for key, fn, _ in _key_reads(module)}
    assert {("_via_const", "gate"), ("_via_loop", "gate"), ("plain", "gate"),
            (DYNAMIC_KEY, "gate")} <= keys, keys
    # 不经下标、按键名比出来的读（评审第三轮）
    assert {("_via_eq", "by_name"), ("_via_eq_rhs", "by_name"),
            ("_via_in_literal", "by_name"), ("_via_set_op", "by_name"),
            ("_via_set_cmp", "by_name"), ("push", "by_name")} <= keys, keys
    assert ("plain2", "by_name") not in keys, "普通字符串比较不是键读，别把噪音拉进来"
    assert DYNAMIC_KEY not in ri.RENDER_ANNOTATIONS and DYNAMIC_KEY not in ri.GATE_ANNOTATIONS


def test_读取扫描认得出常量序列和import进来的键(tmp_path):
    """复审 fix 轮拿合成模块复现的三个盲区里的两个：序列常量、import 进来的常量。

    （第三个——按后缀批量读 `k.endswith("_why")`——不是单个键，见
    `test_按前后缀批量读注解的扫描认得出`。）
    """
    (tmp_path / "keys_mod.py").write_text(
        'KEY = "_via_import"\n'
        'SEQ = frozenset({"_via_import_seq", "plain3"})\n'
        'ATTR = "_via_module_attr"\n', encoding="utf-8")
    module = tmp_path / "m.py"
    module.write_text(
        "import keys_mod\n"
        "from keys_mod import KEY, SEQ as ALIASED\n"
        'KEYS = ("_via_tuple_a", "_via_tuple_b")\n'
        'FROZEN = frozenset({"_via_frozenset"})\n'
        "def loops(spec):\n"
        "    for k in KEYS:\n"
        "        spec.get(k)\n"
        "    return [spec[k] for k in ALIASED]\n"
        "def by_name(spec):\n"
        "    for k, v in spec.items():\n"
        "        if k in FROZEN:\n"
        "            pass\n"
        "    return spec.keys() & FROZEN\n"
        "def imported(spec):\n"
        "    spec.get(KEY)\n"
        "    return spec.get(keys_mod.ATTR)\n", encoding="utf-8")
    keys = {(key, fn) for key, fn, _ in _key_reads(module)}
    assert {("_via_tuple_a", "loops"), ("_via_tuple_b", "loops"),
            ("_via_import_seq", "loops")} <= keys, keys
    assert ("_via_frozenset", "by_name") in keys, keys
    assert {("_via_import", "imported"), ("_via_module_attr", "imported")} <= keys, keys


#: 渲染路径上读 `_` 键、但读的**不是 spec**（渲染自己攒的运行时字典）的地方。
#: 按（键, 函数）逐处登记，不按键名整批放：同一个键哪天在别的函数里被当成 spec
#: 字段读，照样要归类。
_NOT_SPEC_READS: dict[tuple[str, str], str] = {
    ("push", "story_photo_push_indices"): "比较 story_photo_motion 的值 push；不是读取 spec 的推送块。下方专门判据禁止此函数读取推送块。",
    ("_key", "_gate_cover_face"): "`_FACE_REPORT[\"cover\"][\"_key\"]`：这一趟算过的封面帧"
                                  "缓存键（`_face_gate_key`），渲染自己写、自己读",
}


def test_story_photo_motion_push_is_a_value_not_the_publication_block():
    tree = ast.parse((ROOT / "tools/build_match_reel.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "story_photo_push_indices")
    for node in ast.walk(fn):
        if isinstance(node, ast.Subscript):
            assert not (isinstance(node.slice, ast.Constant) and node.slice.value == "push")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"get", "pop", "setdefault"} and node.args:
                assert not (isinstance(node.args[0], ast.Constant) and node.args[0].value == "push")
    assert any(isinstance(n, ast.Compare) and any(
        isinstance(c, ast.Constant) and c.value == "push" for c in n.comparators)
        for n in ast.walk(fn))


def test_渲染路径读到的注解键都要归类():
    """O1 的 b 方案被否掉的理由是「要证明渲染器从不读被排除的键」——现在它是机械的。

    渲染/质检路径上每一处 `_` 键的读取，都要在 `RENDER_ANNOTATIONS`（进成片、
    留在指纹里）或 `GATE_ANNOTATIONS`（只进闸、值不进指纹）里认领；只进推送的
    真字段（`push`）只许在认领过的函数里读。新读一个没归类的键 → 这里红，
    逼着回答一句「它进不进成片」。
    """
    modules = _render_path_modules()
    names = {m.name for m in modules}
    assert {"build_match_reel.py", "check_reel_landed.py", "reel_facts.py",
            "render_stat_card.py", "versus_poster.py"} <= names, (
        f"import 图没走到该走的模块，判据是空转：{sorted(names)}")

    classified = set(ri.RENDER_ANNOTATIONS) | set(ri.GATE_ANNOTATIONS)
    seen: set[str] = set()
    seen_runtime: set[tuple[str, str]] = set()
    stray: list[str] = []
    for module in modules:
        for key, fn, line in _key_reads(module):
            where = f"{module.relative_to(ROOT)}:{line} {fn}()"
            if (key, fn) in _NOT_SPEC_READS:
                seen_runtime.add((key, fn))
                continue
            if key.startswith("_") and not key.startswith("__"):
                seen.add(key)
                if key not in classified:
                    stray.append(f"{where} 读了 {key!r}")
            elif key in ri.PUBLISH_FIELDS:
                if fn not in ri.PUBLISH_FIELDS[key]:
                    stray.append(f"{where} 读了只进推送的 {key!r}——它要是进了成片，"
                                 "就不能再整块排除在渲染输入之外")
    assert not stray, (
        "渲染/质检路径上读到了没归类的键。它进成片就加进 render_inputs.RENDER_ANNOTATIONS"
        "（改了要重渲），只进闸就加进 GATE_ANNOTATIONS 并写清哪道闸：\n  "
        + "\n  ".join(stray))

    # 表自带自检：表里有、代码里没人读的，是过期条目——删掉，别让它看起来像在管事
    stale = sorted(classified - seen)
    assert not stale, f"这些键渲染/质检路径上已经没人读了，从表里删掉：{stale}"
    stale_runtime = sorted(set(_NOT_SPEC_READS) - seen_runtime)
    assert not stale_runtime, f"_NOT_SPEC_READS 里这几处已经没人读了，删掉：{stale_runtime}"
    assert not set(ri.RENDER_ANNOTATIONS) & set(ri.GATE_ANNOTATIONS)
    assert all(why.strip() for why in ri.RENDER_ANNOTATIONS.values())
    assert all(note.why.strip() for note in ri.GATE_ANNOTATIONS.values())


def _calls_by_function(path: Path) -> dict[str, set[tuple[str, str]]]:
    """顶层函数 → 它调到的 (模块文件名, 函数名)。

    只认解析得出是哪个模块的调用：本模块顶层定义的 `f(...)`、`from m import f` 进来的
    `f(...)`、`import m` 之后的 `m.f(...)`。方法调用（`x.get(...)`）认不出，不记——
    按裸函数名对会撞名（`spec_wording.spoken_texts` 和 `check_polyphones.spoken_texts`
    是两个函数）。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    local = {top.name for top in tree.body
             if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef))}
    imported: dict[str, tuple[str, str]] = {}     # 名字 → (模块文件名, 原名)
    modules: dict[str, str] = {}                  # 别名 → 模块文件名
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            src = _resolve(node.module)
            for alias in node.names:
                if src is not None:
                    imported[alias.asname or alias.name] = (src.name, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                src = _resolve(alias.name)
                if src is not None and (alias.asname or "." not in alias.name):
                    modules[alias.asname or alias.name] = src.name
    out: dict[str, set[tuple[str, str]]] = {}
    for top in tree.body:
        fn = top.name if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)) else "<module>"
        for node in ast.walk(top):
            if not isinstance(node, ast.Call):
                continue
            target = None
            if isinstance(node.func, ast.Name):
                if node.func.id in local:
                    target = (path.name, node.func.id)
                elif node.func.id in imported:
                    target = imported[node.func.id]
            elif (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                  and node.func.value.id in modules):
                target = (modules[node.func.value.id], node.func.attr)
            if target:
                out.setdefault(fn, set()).add(target)
    return out


#: 采访线入口在竖版短片的 import 图里**只许**被这些函数调（往上追到头）：采访线自己的
#: 函数（`interview_` 开头）和下面这几个命令行入口——渲染/质检把这些模块当库
#: `import`，它们不跑。
_OTHER_LINE_CALLERS: dict[tuple[str, str], str] = {
    ("check_polyphones.py", "spoken_texts"): "命令行按 --slug 认栏目（只有 main 调它）",
    ("check_polyphones.py", "main"): "命令行入口",
}


def test_采访线的入口只从采访线的函数调():
    """`_OTHER_LINE_GATEWAYS` 剪掉的那几处延迟 import，前提是竖版短片够不着那几个函数。

    在剪过的 import 图里往上追「谁调了它」：追到的每一个都得是采访线的函数
    （`interview_` 开头）或命令行入口。哪天 `validate_spec` 调了 `interview_taste_extra`，
    这里红——那时采访模块就真在竖版短片的渲染路径上了，得把它们放回扫描、逐个归类。
    """
    modules = _render_path_modules()
    by_name = {m.name: m for m in modules}
    callers: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for module in modules:
        for fn, targets in _calls_by_function(module).items():
            for target in targets:
                callers.setdefault(target, set()).add((module.name, fn))
    for (module_name, gateway), why in _OTHER_LINE_GATEWAYS.items():
        assert why.strip()
        module = by_name.get(module_name)
        assert module is not None, f"{module_name} 已经不在渲染路径上了，把它从表里删掉"
        lazy = [name for fn, name in _imports_in(ast.parse(module.read_text(encoding="utf-8")))
                if fn == gateway]
        assert lazy, f"{module_name}:{gateway} 里已经没有延迟 import 了，把它从表里删掉"
        todo, seen, bad = [(module_name, gateway)], set(), []
        while todo:
            for caller in sorted(callers.get(todo.pop(), set())):
                if caller in seen or caller in _OTHER_LINE_CALLERS:
                    continue
                seen.add(caller)
                if caller[1].startswith("interview_"):
                    todo.append(caller)
                else:
                    bad.append(f"{caller[0]}:{caller[1]} → … → {module_name}:{gateway}")
        assert not bad, ("竖版短片的函数够得着采访线入口了——采访模块在渲染路径上，"
                         f"不能再从扫描里剪掉：{bad}")


def test_quote_kind的口径和闸是同一份():
    import taste_gates_extra  # noqa: PLC0415
    assert ri.QUOTE_KINDS == taste_gates_extra.QUOTE_KINDS


def _affix_batches(path: Path) -> set[tuple[str, str]]:
    """(模块, 顶层函数)：里面有按 `_` 开头的前缀／后缀批量认键的地方。

    `key.startswith("_")`（整批注解）、`k.endswith("_why")`（按后缀认一批认领，复审
    fix 轮量出来的盲区）、`startswith(("_a", "_b"))`——**单个键**的扫描看不见这种写法。
    `"__"` 开头的（dunder）不算。
    """
    found: set[tuple[str, str]] = set()
    for top in ast.parse(path.read_text(encoding="utf-8")).body:
        if not isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(top):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("startswith", "endswith") and node.args):
                continue
            affixes = _const_strings(node.args[0]) or set()
            if any(a.startswith("_") and not a.startswith("__") for a in affixes):
                found.add((path.name, top.name))
    return found


def test_按前后缀批量读注解的扫描认得出(tmp_path):
    module = tmp_path / "m.py"
    module.write_text(
        "def by_suffix(spec):\n"
        '    return [v for k, v in spec.items() if k.endswith("_why")]\n'
        "def by_prefix(spec):\n"
        '    return [k for k in spec if str(k).startswith(("_claim", "x"))]\n'
        "def dunder(name):\n"
        '    return name.startswith("__")\n'
        "def plain(name):\n"
        '    return name.endswith(".json")\n', encoding="utf-8")
    assert _affix_batches(module) == {("m.py", "by_suffix"), ("m.py", "by_prefix")}


def test_按下划线整批跳过的地方只许在闸和推送里():
    """`key.startswith("_")` 是「按约定整批处理注解」——它出现在渲染代码里就要问一句。

    现在全部落在措辞闸、推送元数据、`_reject_underscored_fields` 和投影本身里，
    都是**跳过**注解；哪天渲染代码开始按前缀批量**读**注解（上面那条按字面键名扫的
    测试看不见这种写法），这张表会红。按顶层函数认，嵌套的 helper 跟着它走。
    按后缀批量认（`k.endswith("_why")`）同样算（`_affix_batches`）。
    """
    allowed = {
        ("build_match_reel.py", "_reject_underscored_fields"),   # 闸：`_push` 这种假字段
        ("render_inputs.py", "is_annotation"),                    # 投影本身
        ("push_reel.py", "push_meta"),                            # 推送元数据
        ("spec_wording.py", "voiced_texts"), ("spec_wording.py", "outward_deep"),
        ("spec_wording.py", "outward_flat"),
        ("spec_wording.py", "interview_outward_texts"),           # 措辞闸
        ("reel_asset_gates.py", "_images_in"),                    # 闸：图片解码，注解里的路径不算
        ("build_match_reel.py", "_face_checks_record"),           # 写 render.json：剥掉运行时缓存键
        ("reel_facts.py", "annotation_strings"),                  # 闸：注解里的「要等」（waiting_fact_problem）
        ("design_tokens.py", "css_base"),                         # 不是 spec：设计 token 名按 `_ms` 转 CSS 时长
        ("spec_wording.py", "non_annotation_strings"),            # 措辞闸：「N 强」扫非注解文字
        ("taste_gates_extra.py", "interview_taste_extra"),        # 口味闸：采访推送文案跳过注解
    }
    found = set()
    for module in _render_path_modules():
        found |= _affix_batches(module)
    assert found - allowed == set(), (
        f"渲染路径上新出现了按下划线批量处理注解的函数：{sorted(found - allowed)}")
    assert allowed - found == set(), f"表里的条目已经不在了，删掉：{sorted(allowed - found)}"


def test_清单里的产物名和渲染写的是同一个():
    import build_match_reel as bmr  # noqa: PLC0415
    import push_reel  # noqa: PLC0415

    assert bmr.POSTER_NAME in ri.ARTIFACTS and push_reel.STAT_CARD_NAME in ri.ARTIFACTS
    body = (ROOT / "tools/build_match_reel.py").read_text(encoding="utf-8")
    render_body = body[body.index("\ndef render("):body.index("\ndef _escape(")]
    for name in ("subtitles.ass", "topbar.ass"):
        assert f'outdir / "{name}"' in render_body, f"render() 不再写 {name}，清单跟着改"
    assert landed.RENDER_INPUTS_NAME == ri.MANIFEST_NAME


def _run_main(tmp_path: Path, monkeypatch, *, cover_only: bool, tag: str) -> Path:
    """跑真 `main()`（假 `render()`），spec 是本文件造的——不借仓库里的真 spec：
    `main()` 在 `render()` 之前还有 `load_spec` / 措辞闸，哪天加一道硬闸拦了某条老片子，
    这里不该跟着红（复审 fix 轮）。"""
    import build_match_reel as bmr  # noqa: PLC0415

    spec_path = _write_spec(tmp_path, _spec())

    def fake_render(spec, outdir, **kw):
        outdir.mkdir(parents=True, exist_ok=True)
        if kw.get("cover_only"):
            (outdir / "poster.jpg").write_bytes(b"poster")
            return outdir / "poster.jpg"
        film = outdir / f"{spec['slug']}.mp4"
        film.write_bytes(FILM)
        (outdir / "render.json").write_text("{}", encoding="utf-8")
        return film

    monkeypatch.setattr(bmr, "render", fake_render)
    # main() 开头会挂代理 CA、按 spec 设 TTS 后端的环境变量——别漏进同一个 worker 的别的测试
    monkeypatch.setattr(bmr.localca, "trust_local_proxy_ca", lambda: None)
    monkeypatch.delenv("TENNISLIVE_TTS_BACKEND", raising=False)
    outdir = tmp_path / tag
    argv = ["build_match_reel.py", "render", "--spec", str(spec_path),
            "--outdir", str(outdir)] + (["--cover-only"] if cover_only else [])
    monkeypatch.setattr(sys, "argv", argv)
    assert bmr.main() == 0
    return outdir


def test_渲完就写清单_只出封面不写(tmp_path, monkeypatch):
    """跑真 `main()`：清单是 render() 之后那一行写的，不是文档里说的。"""
    assert not (_run_main(tmp_path, monkeypatch, cover_only=True, tag="cover")
                / ri.MANIFEST_NAME).exists()
    full = _run_main(tmp_path, monkeypatch, cover_only=False, tag="full")
    spec_path = tmp_path / "specs/reels" / f"{SLUG}.json"
    manifest = json.loads((full / ri.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["spec_sha256"] == _sha(spec_path.read_bytes())
    assert manifest["film_sha256"] == _sha(FILM)
    render = json.loads((full / "render.json").read_text(encoding="utf-8"))
    assert render["render_inputs_sha256"] == _sha((full / ri.MANIFEST_NAME).read_bytes())


def test_清单写不成不许把渲完的片子打红(tmp_path, monkeypatch, capsys):
    """`record` 抛错（怪素材字符串让 `sha256_file` 抛 `OSError`）→ main 照样 0、只警告，
    而且什么都不留：半截清单被质检钉进凭证、render.json 却没钉，门禁会不吭声地永远不推。"""
    def broken(*_a, **_k):
        raise OSError("怪素材路径")

    monkeypatch.setattr(ri, "build", broken)
    outdir = _run_main(tmp_path, monkeypatch, cover_only=False, tag="full")
    assert not (outdir / ri.MANIFEST_NAME).exists()
    assert "render_inputs_sha256" not in json.loads(
        (outdir / "render.json").read_text(encoding="utf-8"))
    assert "清单没写成" in capsys.readouterr().out


def test_清单写到一半出错_不留半截(tmp_path):
    """清单已经落盘、回写 render.json 那一步才出错：清单要删掉，别留一份没人钉的。"""
    spec_path = _write_spec(tmp_path, _spec())
    outdir = tmp_path / "out"
    outdir.mkdir()
    film = outdir / f"{SLUG}.mp4"
    film.write_bytes(FILM)
    (outdir / "subtitles.ass").write_text("Dialogue: 字幕\n", encoding="utf-8")
    (outdir / "render.json").mkdir()          # 回写 render.json 必然 IsADirectoryError
    assert ri.record_best_effort(spec_path, outdir, film, tmp_path) is None
    assert not (outdir / ri.MANIFEST_NAME).exists()
    # 质检那一头：盘上没有清单就不钉，发布门禁退回 spec 字节那一道
    (outdir / "render.json").rmdir()
    landed.write_attestation(film, spec_path, _spec())
    qc = json.loads((outdir / "qc_attestation.json").read_text(encoding="utf-8"))
    assert "render_inputs_sha256" not in qc


# ── 工作流：够得着、够轻、和 render 不并行、落库后走同一道发布门禁 ──────────────


def _steps() -> dict[str, dict]:
    import yaml  # noqa: PLC0415

    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return {s.get("name", ""): s for s in doc["jobs"]["reel"]["steps"]}


def _runs_for(step: dict, mode: str) -> bool:
    """按 `if:` 里的 mode 条件判这一步在该 mode 下跑不跑（只认本工作流用到的两种写法）。"""
    cond = str(step.get("if", ""))
    eq = set(re.findall(r"inputs\.mode\s*==\s*'([a-z-]+)'", cond))
    ne = set(re.findall(r"inputs\.mode\s*!=\s*'([a-z-]+)'", cond))
    if eq:
        return mode in eq
    return mode not in ne


def test_mode_reattest够得着而且不碰源片不渲不装重依赖():
    import yaml  # noqa: PLC0415

    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    inputs = doc[True]["workflow_dispatch"]["inputs"]
    assert "reattest" in inputs["mode"]["options"]
    assert len(inputs) <= 25, "表单满 25 项，reattest 只能是 mode 的一个选项，不能加输入"

    steps = _steps()
    step = steps["reattest — 渲染输入没变就重出凭证，不重渲"]
    assert step["if"] == "github.event.inputs.mode == 'reattest'"
    assert "reattest_check.py" in step["run"] and "--apply" in step["run"]
    assert "--outdir" in step["run"], "outdir 要用按 slug 反查出来的那个，不能让工具自己猜"

    for name in ("发布文案前置检查", "dry-run — 先把 spec 的形状错拦在编码之前",
                 "写复制页（必须排在提交之前）", "提交产物"):
        assert _runs_for(steps[name], "reattest"), f"「{name}」在 reattest 下不跑"
    for name, step in steps.items():
        if any(heavy in name for heavy in ("render — 出成片", "查成片本身合不合格",
                                           "成片发到 Release", "缓存源片", "算出源片缓存的键",
                                           "起 PO token", "装 ffmpeg", "缓存 apt", "装中文字体",
                                           "Chromium", "抠图模型", "缓存 TTS",
                                           "丢掉不进仓库的中间物", "上传 artifact")):
            assert not _runs_for(step, "reattest"), f"「{name}」在 reattest 下也跑了"

    install = steps["装依赖"]["run"]
    branch = install[install.index('= "reattest" ]'):]
    branch = branch[:branch.index("exit 0")]
    assert "pip install -q -e ." in branch and "python -c \"import" in branch
    for heavy in ("yt-dlp", "visualqa", "webrender", "cutout", "edge-tts"):
        assert heavy not in branch

    paths = steps["算出目录"]["run"]
    assert re.search(r'= "push" \][^\n]*\n[^\n]*= "reattest" \]; then\n\s*MATCH=\$\(git ls-tree',
                     paths), "reattest 要和 push 一样按 slug 反查渲的那天的目录，不能按今天拼"

    # 和 render 同一个并发组：同一条片子两者不并行
    group = doc["concurrency"]["group"]
    assert "inputs.mode == 'reattest' && 'render'" in group

    # 落库之后走 render 那同一道完整发布门禁（main 上工作流自己的提交不触发 auto-push-reel）
    for name in ("render 质检落库后读取 spec 自动推送规则", "render 质检落库后自动派发微信推送"):
        assert _runs_for(steps[name], "reattest") and _runs_for(steps[name], "render")
    body = WORKFLOW.read_text(encoding="utf-8")
    assert body.index("- name: reattest — 渲染输入没变") < body.index("- name: 提交产物")
