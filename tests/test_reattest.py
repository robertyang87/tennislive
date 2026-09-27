"""「重核对，不重渲」（`match-reel mode=reattest`）的判据。

账号所有者 2026-09-27 在 O1（质检指纹管到哪儿）三选一里选的：spec 渲完之后只改
注解或推送字段时，不重渲，重出一张绑定新 spec 字节、指着同一份成片的凭证。

来路（五趟 7~10 分钟、成片一个像素都没变的重渲）：eala-jovic 85b94e74、
mensik-tien d338e77d、wong-paul d5bbc48c、medvedev-damm e15e73e5；gauff-jovic
80bbdd1a 推送之后链就断着。

**「发出去的必须和质检过的是同一份」一个字都不许松**——所以这里的测试一半在验
「该过的过了」，一半在验「动了成片的、链被动过手脚的、Release 被换过的、
账本已经 sent 的，一条都过不去」。每一组都用真代码路径造链：
`render_inputs.record`（渲染那一刻）→ `check_reel_landed.write_attestation`
（L2 质检）→ Release 那一步回写 `video_url/video_bytes` 并删掉本地成片。
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
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
    (lambda o: (o / ri.MANIFEST_NAME).unlink(), "之前渲的"),
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


def _render_path_modules() -> list[Path]:
    """从渲染和质检入口顺着 import 走一遍（含函数里的延迟 import）。"""
    seen: dict[Path, None] = {}
    todo = [ROOT / r for r in _IMPORT_ROOTS]
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        seen[f] = None
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            todo += [p for p in map(_resolve, names) if p and p not in seen]
    return list(seen)


#: 读法里拼出来的键（f"_{x}"、"_" + x）认不出是哪一个，一律记成这个——它不在任何
#: 表里，所以必然报「没归类」，逼着把它改成字面键名。
DYNAMIC_KEY = "_<拼出来的键>"


def _key_reads(path: Path) -> list[tuple[str, str, int]]:
    """(键, 所在函数, 行号)：`x[K]`、`x.get/pop/setdefault(K)`、`K in x`。

    K 不只认字面量（评审 2026-09-27：只认字面量是个潜在的洞）——还认模块顶层的
    字符串常量（`KEY = "_why"` 然后 `x.get(KEY)`）、循环变量走的字面量序列
    （`for k in ("_a", "_b"): x.get(k)`）；以 `_` 开头拼出来的键（f-string、`+`）
    认不出是哪一个，记成 `DYNAMIC_KEY`。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: dict[str, set[str]] = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.setdefault(target.id, set()).add(node.value.value)
    for node in ast.walk(tree):
        if (isinstance(node, (ast.For, ast.comprehension)) and isinstance(node.target, ast.Name)
                and isinstance(node.iter, (ast.Tuple, ast.List, ast.Set))):
            names.setdefault(node.target.id, set()).update(
                e.value for e in node.iter.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str))

    def keys_of(arg: ast.AST) -> set[str]:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return {arg.value}
        if isinstance(arg, ast.Name):
            return names.get(arg.id, set())
        head = (arg.values[0] if isinstance(arg, ast.JoinedStr) and arg.values
                else arg.left if isinstance(arg, ast.BinOp) else None)
        if (isinstance(head, ast.Constant) and isinstance(head.value, str)
                and head.value.startswith("_") and not head.value.startswith("__")):
            return {DYNAMIC_KEY}
        return set()

    out: list[tuple[str, str, int]] = []

    def visit(node: ast.AST, fn: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn = node.name
        arg = None
        if isinstance(node, ast.Subscript):
            arg = node.slice
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr in ("get", "pop", "setdefault") and node.args):
            arg = node.args[0]
        elif (isinstance(node, ast.Compare)
              and any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops)):
            arg = node.left
        if arg is not None:
            for key in sorted(keys_of(arg)):
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
        '    return ("_" + x) in spec\n', encoding="utf-8")
    keys = {(key, fn) for key, fn, _ in _key_reads(module)}
    assert {("_via_const", "gate"), ("_via_loop", "gate"), ("plain", "gate"),
            (DYNAMIC_KEY, "gate")} <= keys, keys
    assert DYNAMIC_KEY not in ri.RENDER_ANNOTATIONS and DYNAMIC_KEY not in ri.GATE_ANNOTATIONS


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
    stray: list[str] = []
    for module in modules:
        for key, fn, line in _key_reads(module):
            where = f"{module.relative_to(ROOT)}:{line} {fn}()"
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
    assert not set(ri.RENDER_ANNOTATIONS) & set(ri.GATE_ANNOTATIONS)
    assert all(why.strip() for why in ri.RENDER_ANNOTATIONS.values())
    assert all(note.why.strip() for note in ri.GATE_ANNOTATIONS.values())


def test_按下划线整批跳过的地方只许在闸和推送里():
    """`key.startswith("_")` 是「按约定整批处理注解」——它出现在渲染代码里就要问一句。

    现在全部落在措辞闸、推送元数据、`_reject_underscored_fields` 和投影本身里，
    都是**跳过**注解；哪天渲染代码开始按前缀批量**读**注解（上面那条按字面键名扫的
    测试看不见这种写法），这张表会红。按顶层函数认，嵌套的 helper 跟着它走。
    """
    allowed = {
        ("build_match_reel.py", "_reject_underscored_fields"),   # 闸：`_push` 这种假字段
        ("render_inputs.py", "is_annotation"),                    # 投影本身
        ("push_reel.py", "push_meta"),                            # 推送元数据
        ("spec_wording.py", "voiced_texts"), ("spec_wording.py", "outward_deep"),
        ("spec_wording.py", "outward_flat"),
        ("spec_wording.py", "interview_outward_texts"),           # 措辞闸
    }
    found = set()
    for module in _render_path_modules():
        for top in ast.parse(module.read_text(encoding="utf-8")).body:
            if not isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(top):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "startswith" and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and node.args[0].value == "_"):
                    found.add((module.name, top.name))
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


def test_渲完就写清单_只出封面不写(tmp_path, monkeypatch):
    """跑真 `main()`：清单是 render() 之后那一行写的，不是文档里说的。"""
    import build_match_reel as bmr  # noqa: PLC0415

    spec_path = ROOT / "specs/reels/bu-majchrzak-hangzhou-2026-r2.json"
    assert spec_path.is_file(), "样板 spec 不在了，换一条现存的"

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
    for cover_only, want in ((True, False), (False, True)):
        outdir = tmp_path / ("cover" if cover_only else "full")
        argv = ["build_match_reel.py", "render", "--spec", str(spec_path),
                "--outdir", str(outdir)] + (["--cover-only"] if cover_only else [])
        monkeypatch.setattr(sys, "argv", argv)
        assert bmr.main() == 0
        assert (outdir / ri.MANIFEST_NAME).is_file() is want
    manifest = json.loads((tmp_path / "full" / ri.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["spec_sha256"] == _sha(spec_path.read_bytes())
    assert manifest["film_sha256"] == _sha(FILM)
    render = json.loads((tmp_path / "full/render.json").read_text(encoding="utf-8"))
    assert render["render_inputs_sha256"] == _sha((tmp_path / "full" / ri.MANIFEST_NAME).read_bytes())


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
