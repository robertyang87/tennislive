"""每条源先 probe、`--dry-run` 拿 probe 的宽高帧率预演 `check_sources_match`（`tools/probe_sources.py`）。

来路：2026-09-16 ~ 09-26 多源「网球有故事」剪辑片在 render 里红了 7 趟几何（38.9 runner
分钟），全在源片下完之后（中位 230 秒）才红；7 趟的 runner dry-run 全是「一份 probe.json
都没认领上」——其中 4 趟的 probe 早就落了库，只是在别的 slug 目录下。
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

from production_history import should_check

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_match_reel as reel  # noqa: E402
import probe_sources as ps  # noqa: E402

NONE: dict = {}


def _probe(url: str, w=1920, h=1080, fps="25/1", fps_value=25.0) -> dict:
    return {"url": url, "width": w, "height": h, "fps": fps, "fps_value": fps_value,
            "duration": 300.0, "scene_cuts": [], "point_ends": []}


def _spec(**extra) -> dict:
    return {"slug": "new-story", "sources": {"a": "A", "b": "B"},
            "segments": [{"source": "a", "start": 1.0, "end": 5.0, "narration": "一句。"},
                         {"source": "b", "start": 1.0, "end": 5.0, "narration": "又一句。"}],
            **extra}


def test_源片没probe_新手写spec硬_认领存量自动只报():
    probes = {"A": _probe("A")}
    hard, soft = ps.coverage_findings(_spec(), probes, legacy=NONE)
    assert len(hard) == 1 and "源 b" in hard[0] and "mode=probe" in hard[0], hard
    # 精简检出里 probe 可能在仓库里、只是没落盘：先指 materialize，排在「重跑 probe」前面
    hint = hard[0].find("probe_sources.py materialize")
    assert 0 <= hint < hard[0].index("mode=probe"), hard
    # 多源的认领要带宽高帧率（2026-09-28）：一句话的认领会把几何预演整层关掉，手写的红
    hard, soft = ps.coverage_findings(_spec(_no_probe_why={"b": "私有录屏，下不下来"}),
                                      probes, legacy=NONE)
    assert len(hard) == 1 and "没写宽高帧率" in hard[0], hard
    claim = {"b": {"why": "私有录屏，下不下来", "width": 1920, "height": 1080, "fps": "25/1"}}
    hard, soft = ps.coverage_findings(_spec(_no_probe_why=claim), probes, legacy=NONE)
    assert not hard and any("已认领" in s for s in soft)
    hard, soft = ps.coverage_findings(_spec(), probes, legacy={"new-story": ["b"]})
    assert not hard and any("legacy_no_probe_sources" in s for s in soft)
    auto = _spec(_production={"status": "ready_for_render"})
    hard, soft = ps.coverage_findings(auto, probes, legacy=NONE)
    assert not hard and any("自动产的 spec 只报" in s for s in soft)
    imported = _spec(_import={"kind": "finished_master_inspection"})
    assert ps.coverage_findings(imported, {}, legacy=NONE) == ([], [])
    # 老 probe 没记宽高帧率：多源只报一句「几何没查」，单源不报（没有可比的）
    old = {"A": {"url": "A"}, "B": _probe("B")}
    assert any("没记宽高帧率" in s for s in ps.coverage_findings(_spec(), old, legacy=NONE)[1])
    single = {"slug": "x", "source_url": "A", "segments": []}
    assert ps.coverage_findings(single, {"A": {"url": "A"}}, legacy=NONE) == ([], [])


def _geometry(spec, probes):
    with redirect_stdout(io.StringIO()):
        return ps.geometry_findings(spec, probes, reel.check_sources_match, reel.ReelError)[0]


def test_几何按probe的宽高帧率预演render里同一道check_sources_match():
    # hsieh-chan-handshake-feud-2026（run 36260393395）那个形状：720p 混进 1080p
    hard = _geometry(_spec(), {"A": _probe("A"), "B": _probe("B", 1298, 720)})
    assert hard and "尺寸对不上" in hard[0] and "['b']" in hard[0], hard
    # 帧率不一样又没认领 → 红；认领了 → 放行
    mixed = {"A": _probe("A"), "B": _probe("B", fps="30000/1001", fps_value=29.97)}
    assert _geometry(_spec(), mixed) and "帧率" in _geometry(_spec(), mixed)[0]
    assert not _geometry(_spec(mixed_fps={"b": "只放说话头"}), mixed)
    # conform 认领的源按基准尺寸算（和 render 的 conform_sources 同一个基准）
    small = {"A": _probe("A"), "B": _probe("B", 1920, 1012)}
    assert not _geometry(_spec(conform={"b": "电影画幅，放大 1.067×"}), small)
    # 存档源整幅 contain 不受尺寸闸管（同 render）
    arch = _spec(archival={"b": "1933 新闻片"})
    arch["segments"][1]["fit"] = "contain"
    assert not _geometry(arch, {"A": _probe("A"), "B": _probe("B", 640, 480)})
    # 缺一条的宽高帧率就不判——拿半张表比会误报，缺的那条由覆盖那道去报
    assert not _geometry(_spec(), {"A": _probe("A")})


def test_帧率按分数式比_老probe的全精度不许误报():
    """`zheng-rybakina`：两条源都是 `30000/1001`，一份 probe 存 `fps_value=29.97`、
    一份存 `29.97002997002997`——按存的数比相对差 1e-6，全库扫描里被误报成帧率不一样。"""
    probes = {"A": _probe("A", fps="30000/1001", fps_value=29.97),
              "B": _probe("B", fps="30000/1001", fps_value=29.97002997002997)}
    assert not _geometry(_spec(), probes)


def test_dry_run一份probe都没有时新手写spec也要红(monkeypatch):
    """「一份都没认领上」原来是早退、返回 False——最该拦的那一类（一条都没 probe）
    从这儿溜走：davis-cup-china-first-world-group-1 两趟都是这个形状。"""
    spec = {"slug": "brand-new", "source_url": "U",
            "segments": [{"start": 1.0, "end": 5.0, "narration": "一句。"}]}
    monkeypatch.setattr(reel, "probes_for_spec", lambda _s: ({}, [""]))
    segs = reel.parse_segments(spec, {"": Path("x")}, "")
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert reel.probe_dry_run(spec, segs) is True
    assert "都没认领上" in buf.getvalue() and "mode=probe" in buf.getvalue()
    # 几何那道也接上了：两条源都有 probe、尺寸对不上 → 红
    two = _spec()
    monkeypatch.setattr(reel, "probes_for_spec", lambda _s: (
        {"A": _probe("A"), "B": _probe("B", 1280, 720)}, []))
    segs = reel.parse_segments(two, {"a": Path("x"), "b": Path("y")}, "")
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert reel.probe_dry_run(two, segs) is True
    assert "预演 check_sources_match" in buf.getvalue(), buf.getvalue()


def test_没probe的豁免表只许减不许加():
    legacy = ps.legacy_no_probe()
    assert legacy, "豁免表读不到——路径或键名写错了，整条判据会静静失效"
    specs = {}
    for path in (ROOT / "specs" / "reels").glob("*.json"):
        spec = json.loads(path.read_text(encoding="utf-8"))
        specs[str(spec.get("slug") or path.stem)] = spec
    missing = sorted(s for s in legacy if s not in specs)
    assert not missing, f"豁免表里的 slug 不存在：{missing}"
    for slug, keys in legacy.items():
        urls = ps.spec_urls(specs[slug])
        gone = sorted(k for k in keys if k not in urls)
        assert not gone, f"{slug} 已经没有这几条源了，从豁免表里删掉：{gone}"
        assert not ps.is_auto(specs[slug]), f"{slug} 是自动 spec，本来就只报，别挂表"
    # 仓库里落着的 probe（CI 的稀疏检出带着 output/**/*.json）补上了的，要删掉
    probes, _ = reel.claim_probes({"sources": {f"{s}/{k}": ps.spec_urls(specs[s])[k]
                                               for s, ks in legacy.items() for k in ks}})
    fixed = sorted(f"{s}/{k}" for s, ks in legacy.items() for k in ks
                   if ps.spec_urls(specs[s])[k] in probes)
    assert not fixed, f"这些源已经有 probe 了，从豁免表里删掉：{fixed}"
    # 定规矩那天（2026-09-27）量出来 16 条 spec、34 条源；rebase 到当天的 main 时
    # pegula-anisimova 已经补了 probe，减掉之后是 15 条、33 条
    assert len(legacy) <= 15 and sum(map(len, legacy.values())) <= 33


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout


def test_按URL把别的slug目录下的probe落盘_部分克隆一趟批量取回(tmp_path, monkeypatch):
    """runner 的稀疏检出是 `blob:none` 的部分克隆、只拉本 slug 的 probe 目录——多源
    片子的源 probe 在别的 slug 目录下（hsieh-chan-uso3、proz-mia25……）就看不见。
    这里用本地「远端」＋ `--filter=blob:none` 克隆复现 runner 那个形状。"""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    _git(origin, "config", "user.email", "t@t")
    _git(origin, "config", "user.name", "t")
    for rel, url in [("output/2026-09-25/reel/quiet-src-a/probe.json", "A"),
                     ("output/2026-09-26/reel/other-b/probe.json", "B"),
                     ("output/2026-09-26/reel/unrelated/probe.json", "Z")]:
        (origin / rel).parent.mkdir(parents=True)
        (origin / rel).write_text(json.dumps(_probe(url)), encoding="utf-8")
    (origin / "README").write_text("x", encoding="utf-8")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "probes")
    _git(origin, "config", "uploadpack.allowFilter", "true")
    _git(origin, "config", "uploadpack.allowAnySHA1InWant", "true")
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", "--filter=blob:none", "--sparse",
         f"file://{origin}", str(clone))
    assert not (clone / "output").exists()
    assert _git(clone, "config", "--get", "remote.origin.promisor").strip() == "true"
    calls: list[list[str]] = []
    real_git = ps._git

    def spy(args, cwd, stdin=None, env=None):
        calls.append(list(args))
        return real_git(args, cwd, stdin, env)

    monkeypatch.setattr(ps, "_git", spy)
    got = ps.materialize(_spec(), cwd=clone)
    # 一趟批量 fetch（逐个懒取在 runner 上是几百次往返，ci.yml 那段注释量过 400~600ms/次）
    fetches = [c for c in calls if "fetch" in c]
    assert len(fetches) == 1 and "--stdin" in fetches[0], calls
    assert got == ["output/2026-09-25/reel/quiet-src-a/probe.json",
                   "output/2026-09-26/reel/other-b/probe.json"], got
    assert json.loads((clone / got[1]).read_text(encoding="utf-8"))["url"] == "B"
    assert not (clone / "output/2026-09-26/reel/unrelated/probe.json").exists()
    assert _git(clone, "status", "--porcelain").strip() == "", "落盘的 probe 不许弄脏工作区"


def test_工作流dry_run之前按URL把probe落盘():
    flow = yaml.safe_load((ROOT / ".github" / "workflows" / "match-reel.yml")
                          .read_text(encoding="utf-8"))
    step = next(s for s in flow["jobs"]["reel"]["steps"]
                if str(s.get("name", "")).startswith("dry-run"))
    run = step["run"]
    code = [line.split("#")[0] for line in run.splitlines()]
    at = next(i for i, line in enumerate(code) if "probe_sources.py materialize" in line)
    dry = next(i for i, line in enumerate(code) if "render --dry-run" in line)
    assert at < dry
    # `git sparse-checkout add` 会把稀疏范围外落好的文件清掉——落盘必须排在每一个 add 之后
    adds = [i for i, line in enumerate(code) if "sparse-checkout add" in line]
    assert adds and max(adds) < at, (adds, at)
    # 取失败要往下传（这一趟覆盖只报），mode 也要传（只在 render 硬）
    fail = "\n".join(code[at:dry])
    assert f"export {ps.MATERIALIZE_FAILED_ENV}=1" in fail, fail
    assert f'export {ps.MODE_ENV}="${{{{ github.event.inputs.mode }}}}"' in fail, fail


def test_覆盖只在mode_render硬_取probe失败这趟只报(monkeypatch):
    """评审 2026-09-27 两条 nit：cover／narration 两趟共用 dry-run 那一步，却用不到
    probe——一条还没 probe 的源不许挡住出封面（时效第一、封面排最前）；工作流按 URL
    取 probe.json 失败时，「认领不到」可能只是没拉回来，硬红只会把人领去重跑 probe。"""
    probes = {"A": _probe("A")}
    hard, _soft = ps.coverage_findings(_spec(), probes, legacy=NONE, env={})
    assert hard, "本地不传 mode＝按 render 算，照旧硬"
    assert ps.coverage_findings(_spec(), probes, legacy=NONE,
                                env={ps.MODE_ENV: "render"})[0]
    for mode in ("cover", "narration"):
        hard, soft = ps.coverage_findings(_spec(), probes, legacy=NONE,
                                          env={ps.MODE_ENV: mode})
        assert not hard and any(f"mode={mode}" in s for s in soft), (mode, hard, soft)
    hard, soft = ps.coverage_findings(_spec(), probes, legacy=NONE,
                                      env={ps.MATERIALIZE_FAILED_ENV: "1"})
    assert not hard and any("取 probe.json 那一步失败了" in s for s in soft), soft
    # 接到 dry-run 上：一条都没 probe 的新手写 spec，mode=cover 那一趟不红
    spec = {"slug": "brand-new", "source_url": "U",
            "segments": [{"start": 1.0, "end": 5.0, "narration": "一句。"}]}
    monkeypatch.setattr(reel, "probes_for_spec", lambda _s: ({}, [""]))
    monkeypatch.setenv(ps.MODE_ENV, "cover")
    segs = reel.parse_segments(spec, {"": Path("x")}, "")
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert reel.probe_dry_run(spec, segs) is False, buf.getvalue()


def test_取probe不完整要非0退出(tmp_path, monkeypatch, capsys):
    """原来批量 fetch 失败只打一句 warning、退出码 0——工作流以为落好了，dry-run 接着
    按「没 probe」硬红。现在取得不完整就记下原因、`main` 退出码 1。"""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    _git(origin, "config", "user.email", "t@t")
    _git(origin, "config", "user.name", "t")
    rel = "output/2026-09-25/reel/quiet-src-a/probe.json"
    (origin / rel).parent.mkdir(parents=True)
    (origin / rel).write_text(json.dumps(_probe("A")), encoding="utf-8")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "probes")
    _git(origin, "config", "uploadpack.allowFilter", "true")
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", "--filter=blob:none", "--sparse",
         f"file://{origin}", str(clone))
    origin.rename(tmp_path / "gone")                      # 远端没了：批量 fetch 必失败
    problems: list[str] = []
    assert ps.materialize(_spec(), cwd=clone, problems=problems) == []
    assert any("批量取 probe.json 失败" in p for p in problems), problems
    assert any("没取回来" in p for p in problems), problems
    # main 把它变成退出码
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    monkeypatch.setattr(ps, "materialize",
                        lambda spec, ref="HEAD", cwd=ROOT, problems=None:
                        (problems.append("批量取 probe.json 失败：x") or []))
    assert ps.main(["materialize", str(spec_path)]) == 1
    assert "批量取 probe.json 失败" in capsys.readouterr().err
    monkeypatch.setattr(ps, "materialize", lambda spec, ref="HEAD", cwd=ROOT, problems=None: [])
    assert ps.main(["materialize", str(spec_path)]) == 0


def test_豁免表外的手写spec每条源都认领得到probe():
    """CI 的稀疏检出带着 `output/**/*.json`，所以 probe.json 在盘上；本地精简 worktree
    没有 `output/` 时跳过（「没有」和「查过」不许长一样，所以是 skip 不是 pass）。"""
    probes = {}
    for path in sorted((ROOT / "output").glob("*/reel/*/probe.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        probes[data.get("url")] = data
    if not probes:
        pytest.skip("这个检出里没有 output/*/reel/*/probe.json")
    bad = []
    for path in sorted((ROOT / "specs" / "reels").glob("*.json")):
        if not should_check('tests/test_probe_sources.py::test_豁免表外的手写spec每条源都认领得到probe', path):
            continue
        hard, _soft = ps.coverage_findings(json.loads(path.read_text(encoding="utf-8")), probes)
        bad += [f"{path.stem}: {line.strip()[:120]}" for line in hard]
    assert not bad, "\n".join(bad)
