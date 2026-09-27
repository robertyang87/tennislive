"""封面认人＋睁眼（`tools/face_checks.py` / `reel_face_gate.py` / 采访封面闸）。

账号所有者 2026-09-27 在多选题里选了 O2+O3「两个都加」。这里的判据全拿**仓库里
真发过的封面**当夹具（`tests/fixtures/faces/`，字节和历史 blob 一模一样，
不给仓库多添一个字节）：

| 夹具 | 是什么 | 该怎么判 |
|---|---|---|
| `tien-cobolli-poster-74235cea-agassi.jpg` | 勒纳·钱的采访封面，97.0 那帧切到了**阿加西**，推出去才换（9ae8918f） | 不是本人 |
| `tien-cobolli-poster-aa052bf0.jpg` | 换成 79.6 之后的那版 | 是本人、睁眼 |
| `ruud-cerundolo-poster-9380e58f-eyes-closed.jpg` | 鲁德发布会 245.0，**低头闭眼**，Haar 数到两只眼放行了 | 闭眼 |
| `ruud-cerundolo-poster-bf53644c.jpg` | 换成 257.2 正脸睁眼那版 | 是本人、睁眼 |
| `wong-vallejo-cover-frame-689.8.jpg` | 「赛场之上」抽帧封面 cover_src/ 里那一帧 | 是黄泽林、睁眼 |

⚠️ **实现没装 insightface 包**（它会把 cv2 换成 5.x，见 face_checks 顶部），前后处理是
照抄的。2026-09-27 在一次性 venv 里拿 insightface 2.0 本身跑同样五张图逐数对过：
框和 5 点 Δ ≤ 0.0001px、512 维向量余弦 ≥ 0.99995、106 点 Δ ≤ 0.052px。那个对照
CI 上跑不了（不装那个包），数记在这儿。

⚠️ **模型不在就跳过——但 CI 上不许跳**：CI 在「备好人脸模型」那一步下好了，
那儿缺模型是红（`CI` 环境变量）。一条常年跳过的检查和常年红是同一个毛病。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import face_checks  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "faces"
AGASSI = FIX / "tien-cobolli-poster-74235cea-agassi.jpg"
TIEN_OK = FIX / "tien-cobolli-poster-aa052bf0.jpg"
RUUD_CLOSED = FIX / "ruud-cerundolo-poster-9380e58f-eyes-closed.jpg"
RUUD_OK = FIX / "ruud-cerundolo-poster-bf53644c.jpg"
WONG_FRAME = FIX / "wong-vallejo-cover-frame-689.8.jpg"


@pytest.fixture
def model():
    try:
        return face_checks.load()
    except face_checks.ModelUnavailable as exc:
        if os.environ.get("CI"):
            pytest.fail(f"CI 上人脸模型必须在（ci.yml「备好人脸模型」那一步）：{exc}")
        pytest.skip(f"本机没有人脸模型（python tools/face_checks.py fetch）：{exc}")


def _photo(poster: Path):
    """海报的照片区——和采访封面闸同一块（y 150~960）。"""
    from PIL import Image  # noqa: PLC0415

    with Image.open(poster) as im:
        return im.convert("RGB").crop((0, 150, 1080, 960))


# ---------------------------------------------------------------- 认人

def test_阿加西那帧认得出不是勒纳钱_换过的那帧认得出是他(model):
    bad = face_checks.identify(_photo(AGASSI), ["勒纳·钱"], model=model)
    assert bad["verdict"] == "mismatch", bad
    assert bad["similarity"]["勒纳·钱"] < face_checks.MISMATCH_SIM
    good = face_checks.identify(_photo(TIEN_OK), ["勒纳·钱"], model=model)
    assert good["verdict"] == "match" and good["name"] == "勒纳·钱", good
    # 双打／两个人的时候：两个都不像才算不是
    both = face_checks.identify(_photo(AGASSI), ["勒纳·钱", "科博利"], model=model)
    assert both["verdict"] == "mismatch", both


def test_有人没官方头像就不许判不是他(model):
    """费德勒、锦织圭这类**仓库里没有头像**的人：认不了是「拿不准」，不是「不是他」。
    判成 mismatch 会把一张对的封面硬拦下来。"""
    res = face_checks.identify(_photo(AGASSI), ["勒纳·钱", "一个仓库里没有头像的人"],
                               model=model)
    assert res["verdict"] == "unknown", res
    assert "没有官方头像" in res["reason"]


# ---------------------------------------------------------------- 睁眼

def test_鲁德低头那帧判闭眼_正脸那帧判睁眼(model):
    closed = face_checks.eyes_open(_photo(RUUD_CLOSED), model=model)
    assert closed["verdict"] in ("closed", "downcast"), closed
    assert closed["ear"] < face_checks.EYE_OPEN_EAR
    for poster in (RUUD_OK, TIEN_OK, AGASSI):
        opened = face_checks.eyes_open(_photo(poster), model=model)
        assert opened["verdict"] == "open", (poster.name, opened)


def test_眼睛序号取的是眼睑不是眉毛(model):
    """106 点的眼睛序号是拿参考实现在鲁德正脸上逐点画出来认的。钉住几何关系：
    上眼睑在下眼睑之上、眼角在两边、两只眼一左一右——序号抄错一个就会红。"""
    img = face_checks.read_bgr(_photo(RUUD_OK))
    face = face_checks.largest_face(model, img)
    pts = model.landmarks(img, face)
    centers = []
    for eye in face_checks._EYES:
        (ax, _), (bx, _) = (pts[i] for i in eye["corners"])
        for up, lo in zip(eye["upper"], eye["lower"]):
            assert pts[up][1] < pts[lo][1], (up, lo)
            assert min(ax, bx) < pts[up][0] < max(ax, bx)
        centers.append((ax + bx) / 2)
        # 眼睛在脸框上半截（眉毛也在上半截，但眼睑开口只有几像素——量的是开口）
        assert face.bbox[1] < pts[eye["upper"][1]][1] < (face.bbox[1] + face.bbox[3]) / 2
    assert abs(centers[0] - centers[1]) > face.height * 0.2, "两只眼挤在一起＝序号取错了"


# ---------------------------------------------------------------- 从数重判

def test_凭证里的结论从数重判不信字符串():
    """落盘的凭证会被推送闸再判一遍——手改 `"verdict": "match"` 骗不过去。"""
    block = {"status": "ok",
             "identity": {"verdict": "match", "similarity": {"勒纳·钱": -0.004},
                          "missing": [], "face_px": 364.0},
             "eyes": {"verdict": "open", "ear": 0.097, "face_px": 364.0}}
    problems, _ = face_checks.problems_of(block)
    assert any("不是本人" in p for p in problems), problems
    assert any("闭眼" in p for p in problems), problems
    # 反过来：数是好的，字符串写坏了也不许误拦
    good = {"status": "ok",
            "identity": {"verdict": "mismatch", "similarity": {"鲁德": 0.66},
                         "missing": [], "face_px": 348.0},
            "eyes": {"verdict": "closed", "ear": 0.28, "face_px": 348.0}}
    assert face_checks.problems_of(good) == ([], [])


def test_门槛落在量出来的那两组数之间():
    """门槛的来路写在 face_checks 的注释里（85 张同一个人、14529 对不同的人），
    这条钉住它们的相对位置：改门槛之前先回去重量，别顺手调。"""
    assert face_checks.MISMATCH_SIM < 0.217 - 0.05, "同一个人最低 0.217，硬拦那档要留余量"
    assert face_checks.MATCH_SIM > 0.308, "不同的人 99.9 分位 0.308"
    assert 0.097 < face_checks.EYE_CLOSED_EAR < face_checks.EYE_OPEN_EAR < 0.164, (
        "鲁德闭眼 0.097 要拦；胡佳咬牙 0.164、阿尔卡拉斯大笑 0.171 不许误拦")
    # 三档各拿一个真量到的数钉住（仓库里没有「垂眼」那一档的封面夹具，郑钦文那张
    # 是官方图、不在封面闸的管辖里，所以只钉数）
    assert face_checks.eyes_verdict(0.097, 322.0)[0] == "closed"
    assert face_checks.eyes_verdict(0.147, 374.0)[0] == "downcast"
    assert face_checks.eyes_verdict(0.171, 191.0)[0] == "open"
    assert face_checks.eyes_verdict(0.05, 40.0)[0] == "unknown", "脸太小不许判"


# ---------------------------------------------------------------- 大声降级

def test_模型加载不了是大声降级不是通过(monkeypatch, tmp_path):
    def _boom(**_kw):
        raise face_checks.ModelUnavailable("测试：假装没装 onnxruntime")

    monkeypatch.setattr(face_checks, "load", _boom)
    res = face_checks.check_frame(_photo(RUUD_CLOSED), ["鲁德"])
    assert res["status"] == "unavailable"
    assert res["problems"] == [] and res["warnings"], res
    assert "假装没装" in res["warnings"][0]

    # 采访封面闸：不拦，但凭证里有 warnings，render.json 里记下 unavailable
    import audit_interview_cover as cover  # noqa: PLC0415

    spec = {"slug": "t", "subject": "鲁德", "cover": {"frame_at": 245.0}}
    spec_path = tmp_path / "t.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "cover_visual_attestation.json"
    (tmp_path / "render.json").write_text('{"film_seconds": 1.0}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["audit_interview_cover.py", "--spec", str(spec_path),
                                      "--poster", str(RUUD_CLOSED), "--out", str(out)])
    assert cover.main() == 0, "模型不在不许把整道闸拖红（Haar 那部分照旧判）"
    proof = json.loads(out.read_text(encoding="utf-8"))
    assert proof["result"]["face_model"]["status"] == "unavailable"
    assert proof["warnings"], "降级必须留在凭证里"
    render = json.loads((tmp_path / "render.json").read_text(encoding="utf-8"))
    assert render["film_seconds"] == 1.0, "只许加一个键，别的不动"
    assert render["face_checks"]["cover"]["status"] == "unavailable"


# ---------------------------------------------------------------- 采访封面闸

def _audit(tmp_path, monkeypatch, poster: Path, subject: str, **cover_extra) -> tuple[int, dict]:
    import audit_interview_cover as cover  # noqa: PLC0415

    spec = {"slug": "t", "subject": subject, "cover": {"frame_at": 10.0, **cover_extra}}
    spec_path = tmp_path / f"{poster.stem}.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / f"{poster.stem}.proof.json"
    monkeypatch.setattr(sys, "argv", ["audit_interview_cover.py", "--spec", str(spec_path),
                                      "--poster", str(poster), "--out", str(out)])
    rc = cover.main()
    return rc, json.loads(out.read_text(encoding="utf-8"))


def test_采访封面闸拦得住阿加西和闭眼_放得过换好的那两版(model, tmp_path, monkeypatch):
    rc, proof = _audit(tmp_path, monkeypatch, AGASSI, "勒纳·钱")
    assert rc == 1 and any("不是本人" in i for i in proof["issues"]), proof["issues"]
    rc, proof = _audit(tmp_path, monkeypatch, RUUD_CLOSED, "鲁德")
    assert rc == 1 and any("闭眼" in i or "垂眼" in i for i in proof["issues"]), proof["issues"]
    for poster, who in ((TIEN_OK, "勒纳·钱"), (RUUD_OK, "鲁德")):
        rc, proof = _audit(tmp_path, monkeypatch, poster, who)
        assert rc == 0 and proof["status"] == "pass", (poster.name, proof["issues"])
        assert "face model" in proof["identity_evidence"]


def test_采访封面认领口把硬问题降成提示(model, tmp_path, monkeypatch):
    rc, proof = _audit(tmp_path, monkeypatch, RUUD_CLOSED, "鲁德",
                       _face_check_why="测试：这一帧就是要他低头的那一下")
    assert rc == 0, proof["issues"]
    assert any("已认领" in w for w in proof["warnings"]), proof["warnings"]


def test_推送闸复核老凭证不追溯():
    """2026-09-27 之前的凭证没有 `face_model` 块——那时这道闸还不存在，不追溯。"""
    import audit_interview_cover as cover  # noqa: PLC0415

    assert cover.face_model_issues({"face": {}}, {"cover": {}}) == ([], [])


# ---------------------------------------------------------------- 赛场之上：封面抽帧

def _reel():
    import build_match_reel  # noqa: PLC0415

    return build_match_reel


def _cached_cover(tmp_path: Path, frame_src, frame_at: float, spec: dict) -> dict:
    """在 tmp_path 里摆一份 runner 会留下的 cover_src/（帧 ＋ manifest）。"""
    reel = _reel()
    cache = tmp_path / reel.COVER_SRC_DIR
    cache.mkdir(parents=True, exist_ok=True)
    if isinstance(frame_src, Path):
        shutil.copyfile(frame_src, cache / "portrait.jpg")
    else:
        frame_src.save(cache / "portrait.jpg", quality=95)
    art = spec["cover"]["portrait"]
    key = reel._cover_asset_key(art, "", "frame")
    (cache / "manifest.json").write_text(json.dumps({"portrait": key}), encoding="utf-8")
    return spec


def _tien_spec(frame_at: float, **portrait) -> dict:
    return {"slug": "tien-test",
            "cover": {"layout": "solo", "portrait": {"frame_at": frame_at, **portrait},
                      "matchup": [{"name": "勒纳·钱"}, {"name": "科博利"}]},
            "stats": {"a": {"headshot": "assets/players/headshots/atp-T0HA.png"},
                      "b": {"headshot": "assets/players/headshots/atp-C0E9.png"}}}


def test_赛场之上抽帧封面认错人当场拦(model, tmp_path):
    reel = _reel()
    spec = _cached_cover(tmp_path, _photo(AGASSI), 97.0, _tien_spec(97.0))
    with pytest.raises(reel.ReelError, match="不是勒纳·钱／科博利里的任何一个"):
        reel.resolve_cover_payload(spec["cover"], tmp_path, sources=None, primary="",
                                   spec=spec)
    # 认领之后放行，但要出声
    claimed = _cached_cover(tmp_path, _photo(AGASSI), 97.0,
                            _tien_spec(97.0, _face_check_why="测试：讲的就是阿加西在看台"))
    reel.resolve_cover_payload(claimed["cover"], tmp_path, sources=None, primary="",
                               spec=claimed)
    assert "已认领" in " ".join(reel._FACE_REPORT["cover"]["warnings"])


def test_赛场之上抽帧封面闭眼当场拦(model, tmp_path):
    reel = _reel()
    spec = {"slug": "ruud-test",
            "cover": {"layout": "solo", "portrait": {"frame_at": 245.0},
                      "matchup": [{"name": "鲁德"}, {"name": "塞伦多洛"}]},
            "stats": {"a": {"headshot": "assets/players/headshots/atp-RH16.png"},
                      "b": {"headshot": "assets/players/headshots/atp-C0AU.png"}}}
    _cached_cover(tmp_path, _photo(RUUD_CLOSED), 245.0, spec)
    with pytest.raises(reel.ReelError, match="闭眼|垂眼"):
        reel.resolve_cover_payload(spec["cover"], tmp_path, sources=None, primary="",
                                   spec=spec)


def test_赛场之上抽帧封面对的人放行并出声(model, tmp_path, capsys):
    reel = _reel()
    spec = {"slug": "wong-test",
            "cover": {"layout": "solo", "portrait": {"frame_at": 689.8},
                      "matchup": [{"name": "黄泽林"}, {"name": "巴列霍"}]},
            "stats": {"a": {"headshot": "assets/players/headshots/atp-W0BH.png"},
                      "b": {"headshot": "assets/players/headshots/atp-V0DP.png"}}}
    _cached_cover(tmp_path, WONG_FRAME, 689.8, spec)
    reel.resolve_cover_payload(spec["cover"], tmp_path, sources=None, primary="",
                               spec=spec)
    out = capsys.readouterr().out
    assert "[封面认人] 像 黄泽林" in out, out
    assert reel._FACE_REPORT["cover"]["problems"] == []


def test_dry_run就查cover_src里已经抓好的那一帧(model, tmp_path):
    reel = _reel()
    src = (ROOT / "tools" / "build_match_reel.py").read_text(encoding="utf-8")
    import re  # noqa: PLC0415

    dry = src[src.index("    if args.dry_run:"):]
    # 切到这一支结束：下一行缩进回到 4 格（main 里的下一条语句）
    end = re.search(r"\n    \S", dry[20:])
    dry = dry[:20 + end.start()] if end else dry
    assert "hard = _dry_run_cover_face(spec, Path(args.outdir)) or hard" in dry, (
        "`--dry-run` 那一支没挂封面认人——函数写了没人调，等于没有")
    spec = _cached_cover(tmp_path, _photo(AGASSI), 97.0, _tien_spec(97.0))
    assert reel._dry_run_cover_face(spec, tmp_path) is True
    # 没抓过（manifest 对不上这一版）＝交给 runner，不算红也不装作查过
    moved = _tien_spec(98.0)
    assert reel._dry_run_cover_face(moved, tmp_path) is False


# ---------------------------------------------------------------- 分段 3:4 画面（只报）

def test_分段画面旁白讲甲画面是乙只报不拦(model, tmp_path):
    """真跑一遍 ffmpeg 抓帧 → 按窗口裁 → 认人：拿勒纳·钱的封面照片做一段 2 秒的源片，
    旁白点的是科博利。"""
    import reel_face_gate as gate  # noqa: PLC0415

    if not shutil.which("ffmpeg"):
        if os.environ.get("CI"):
            pytest.fail("CI 装着 ffmpeg，这条不许跳过")
        pytest.skip("没有 ffmpeg")
    still = tmp_path / "still.jpg"
    _photo(TIEN_OK).save(still, quality=95)
    src = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-loop", "1",
                    "-i", str(still), "-t", "2", "-r", "25", "-pix_fmt", "yuv420p",
                    "-c:v", "libx264", "-preset", "ultrafast", str(src)], check=True)
    spec = _tien_spec(1.0)

    def seg(text):
        return SimpleNamespace(start=0.0, end=2.0, cx=0.5, narration=text, fit="crop",
                               image=None, source="", crop_zoom=1.0, fill_y=None)

    segments = [seg("科博利这一拍打得太狠"), seg("勒纳·钱笑了"), seg("两个人都没说话")]
    rep = gate.segment_checks(spec, segments, {"": src}, {}, source_w=1080, crop_w=1080,
                              window=lambda x, s: (1080, 810, x, 0),
                              vf_for=lambda _k: (), workdir=tmp_path)
    assert rep["status"] == "ok" and rep["report_only"] is True
    assert [r["segment"] for r in rep["segments"]] == [1, 2], "没点名／点了两个人的段不查"
    assert rep["frames"] == 4 and rep["faces"] == 4, rep
    assert len(rep["findings"]) == 2 and all("旁白讲科博利" in f for f in rep["findings"])
    assert rep["segments"][0]["named"] == "科博利" and rep["segments"][0]["other_seen"] == 2
    assert rep["segments"][1]["named"] == "勒纳·钱" and rep["segments"][1]["other_seen"] == 0
    assert rep["segments"][1]["named_seen"] == 2, "点对了名的段要数得出来——只在出事时出声证明不了看过"


def test_分段认人和编码同时跑_结果落进render_json(model, tmp_path, capsys):
    """render() 里它排在 `track_shots` 之后、分段编码之前**开跑**（后台一个线程），
    写 render.json 时才交卷——只报不拦的东西不许占关键路径（账号所有者 2026-09-27
    「加速」）。整条 render 在测试里跑不起来（要源片、TTS、Chromium），所以两头钉：
    挂钩的位置按源码顺序查，交卷那一步真跑一遍。"""
    import ast  # noqa: PLC0415

    import reel_face_gate as gate  # noqa: PLC0415

    reel = _reel()
    src = (ROOT / "tools" / "build_match_reel.py").read_text(encoding="utf-8")
    body = next(n for n in ast.parse(src).body
                if isinstance(n, ast.FunctionDef) and n.name == "render")
    code = ast.get_source_segment(src, body)
    start = code.index("reel_face_gate.start_segment_checks(")
    assert code.index("track_shots(") < start < code.index("ThreadPoolExecutor(max_workers=workers)"), (
        "分段认人要在跟踪之后（要窗口）、编码之前开跑（和编码并行）")
    assert '"face_checks": _face_checks_record(face_segments)' in code

    # 交卷：真跑一遍后台那条
    still = tmp_path / "still.jpg"
    _photo(TIEN_OK).save(still, quality=95)
    video = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-loop", "1",
                    "-i", str(still), "-t", "2", "-r", "25", "-pix_fmt", "yuv420p",
                    "-c:v", "libx264", "-preset", "ultrafast", str(video)], check=True)
    seg = SimpleNamespace(start=0.0, end=2.0, cx=0.5, narration="科博利这一拍", fit="crop",
                          image=None, source="", crop_zoom=1.0, fill_y=None)
    reel._FACE_REPORT.clear()
    fut = gate.start_segment_checks(_tien_spec(1.0), [seg], {"": video}, {},
                                    source_w=1080, crop_w=1080,
                                    window=lambda x, s: (1080, 810, x, 0),
                                    vf_for=lambda _k: (), workdir=tmp_path)
    record = reel._face_checks_record(fut)
    assert record["cover"]["status"] == "not_applicable"
    assert record["segments"]["status"] == "ok" and len(record["segments"]["findings"]) == 2
    out = capsys.readouterr().out
    assert "[分段认人] ⚠️" in out and "只报不拦" in out
    # 后台那条炸了：记成 error，不许当成「查过了」
    boom = gate._POOL.submit(lambda: 1 / 0)
    assert reel._face_checks_record(boom)["segments"]["status"] == "error"


# ---------------------------------------------------------------- 依赖与缓存

def test_人脸模型缓存键跟着模型版本走():
    """凡是装了 `faces` 的工作流：都要缓存 `~/.cache/tennislive/face-models`，键里带
    `MODEL_VERSION`，而且缓存和「备好」两步排在第一次用到模型之前。换权重就改
    `MODEL_VERSION`——这条逼着三条工作流一起改，否则 runner 上拿的是旧缓存。"""
    import yaml  # noqa: PLC0415

    assert face_checks.model_dir() == (Path.home() / ".cache" / "tennislive"
                                       / "face-models" / face_checks.MODEL_VERSION)
    users = {"interview-clip.yml": "audit_interview_cover.py",
             "match-reel.yml": "dry-run — 先把 spec 的形状错拦在编码之前",
             "ci.yml": "pytest"}
    for name, first_use in users.items():
        wf = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
        steps = [s for job in wf["jobs"].values() for s in job.get("steps") or []]
        runs = "\n".join(str(s.get("run") or "") for s in steps)
        assert "faces" in runs and "pip install" in runs, f"{name} 没装 faces extra"
        cache = [s for s in steps if (s.get("with") or {}).get("path")
                 == "~/.cache/tennislive/face-models"]
        assert len(cache) == 1, f"{name} 要恰好一步缓存人脸模型"
        assert face_checks.MODEL_VERSION in str(cache[0]["with"]["key"]), (
            f"{name} 的缓存键没带 {face_checks.MODEL_VERSION}")
        fetch = [i for i, s in enumerate(steps) if "face_checks.py fetch" in str(s.get("run"))]
        use = [i for i, s in enumerate(steps)
               if first_use in str(s.get("run") or "") or first_use == s.get("name")]
        assert fetch and use and steps.index(cache[0]) < fetch[0] < use[0], (
            f"{name}：缓存 → 备好 → 第一次用，顺序不对")


def test_不许装insightface包本身():
    """它依赖 opencv-python 5.x，一装就把 Haar 那道闸用的 CascadeClassifier 顶没了。"""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"insightface' not in text
    for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
        body = "\n".join(ln for ln in wf.read_text(encoding="utf-8").splitlines()
                         if not ln.lstrip().startswith("#"))
        assert "install insightface" not in body and " insightface " not in body, wf.name
