"""P6：同一条源片别 probe 两遍——`tools/probe_claims.py` + 编排器 + match-reel.yml。

来路见 `tools/probe_claims.py` 的 docstring：628 份 probe.json 里 38 条源片被不止一个
slug probe 过；带自动备料的 144 趟 probe 里 8 趟撞了先例（会话先做了、或者同一批里两个
slug 指着同一场）。

⚠️ 这里的 git 仓库都是现搭的（裸远端 ＋ 一份和 runner 同形状的检出：部分克隆、浅、
稀疏），**不拿仓库自己的 `output/` 当判据的主语**——CI 上它不在。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import git_blobs  # noqa: E402
import probe_claims  # noqa: E402

YT = "https://www.youtube.com/watch?v=4I6d_2Evv-s"
KEY = "4I6d_2Evv-s"


def _git(cwd: Path, *args: str) -> str:
    res = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                         env={**os.environ, **git_blobs.BOT_ENV})
    assert res.returncode == 0, f"git {' '.join(args)}: {res.stderr}"
    return res.stdout


def _write(root: Path, rel: str, body: str | dict) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")


def _today() -> str:
    return probe_claims.beijing_today().isoformat()


@pytest.fixture
def repo(tmp_path):
    """裸远端 ＋ 一份 runner 形状的检出（`--filter=blob:none --depth=1 --sparse`，
    停在特性分支上，`output/` 不在稀疏范围里）。"""
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    _git(remote, "config", "uploadpack.allowFilter", "true")
    _git(remote, "config", "uploadpack.allowAnySHA1InWant", "true")
    seed = tmp_path / "seed"
    _git(tmp_path, "init", "-q", "-b", "main", str(seed))
    _write(seed, "tools/keep.txt", "x")
    _write(seed, "data/keep.txt", "x")
    # 会话 23 分钟前在 main 上落的 probe（wang-prozorova 那种形状）
    _write(seed, f"output/{_today()}/reel/wang-garland-singapore-2026-r2/probe.json", {"url": YT})
    # 同一天别的源片、以及不带这场姓的目录——都不该被认成先例
    _write(seed, f"output/{_today()}/reel/zverev-khachanov/probe.json",
           {"url": "https://www.youtube.com/watch?v=uuLC8AhqDx0"})
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", "seed")
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-q", "origin", "main")
    _git(seed, "switch", "-q", "-c", "feature")
    _write(seed, "tools/feature.txt", "branch work")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", "feature")
    _git(seed, "push", "-q", "origin", "feature")

    def clone(name: str) -> Path:
        work = tmp_path / name
        _git(tmp_path, "clone", "-q", "--filter=blob:none", "--depth=1", "--branch", "feature",
             "--sparse", f"file://{remote}", str(work))
        _git(work, "sparse-checkout", "set", "data", "tools")
        # 前提自证：和 runner 同形状，不然下面测的是另一条路
        assert git_blobs.is_partial_clone(work) and git_blobs.is_shallow(work)
        return work

    return SimpleNamespace(remote=remote, seed=seed, work=clone("work"), clone=clone)


def _remote_claims(remote: Path) -> dict | None:
    res = subprocess.run(["git", "--git-dir", str(remote), "show",
                          f"main:{probe_claims.claim_path(KEY)}"], capture_output=True, text=True)
    return json.loads(res.stdout) if res.returncode == 0 else None


# ------------------------------------------------------------------ 视频 id


def test_视频id按YouTube和TennisTV认_认不出的不认领():
    k = probe_claims.video_key
    assert k(YT) == KEY
    assert k("https://www.youtube.com/watch?feature=share&v=4I6d_2Evv-s&t=12") == KEY
    assert k("https://youtu.be/4I6d_2Evv-s?si=abc") == KEY, "同一条片子带不带 ?si= 是同一个键"
    assert k("https://www.youtube.com/shorts/-fc7s7gPebI") == "-fc7s7gPebI"
    assert k("https://www.tennistv.com/videos/4581010/hangzhou-2026-r1-bu-zheng") == "tennistv-4581010"
    assert k("https://players.brightcove.net/6041795521001/default_default/index.html?videoId=1") is None
    assert k("https://yt/x") is None and k("") is None and k(None) is None


# ------------------------------------------------------------------ probe 那一步


def test_probe开跑就往main上推认领_不碰当前分支和工作区(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo.work)
    head = _git(repo.work, "rev-parse", "HEAD").strip()
    rc = probe_claims.main(["probe-step", "--url", YT, "--slug", "wang-garland",
                            "--branch", "feature", "--run-id", "42"])
    assert rc == 0
    doc = _remote_claims(repo.remote)
    assert doc, "认领要推到 **main** 上——编排器只看得见 main，而这一趟跑在特性分支上"
    (claim,) = doc["claims"]
    assert (claim["slug"], claim["branch"], claim["run_id"]) == ("wang-garland", "feature", "42")
    assert claim["outdir"] == f"output/{_today()}/reel/wang-garland"
    assert _git(repo.work, "rev-parse", "HEAD").strip() == head, "不许动当前分支"
    assert _git(repo.work, "symbolic-ref", "HEAD").strip() == "refs/heads/feature"
    assert _git(repo.work, "status", "--porcelain").strip() == "", "不许动工作区和索引"


def test_别的slug已经probe过同一条源片_probe那一步要出声并给出目录(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo.work)
    rc = probe_claims.main(["probe-step", "--url", YT, "--slug", "wang-garland",
                            "--branch", "feature", "--run-id", "7"])
    out = capsys.readouterr().out
    assert rc == 0, "只出声不拦——会话有时就是要重 probe"
    warn = [line for line in out.splitlines() if line.startswith("::warning::")]
    assert len(warn) == 1, out
    assert f"output/{_today()}/reel/wang-garland-singapore-2026-r2" in warn[0], (
        "先例要带着可复用的目录——`output/` 不在稀疏检出里，得按 git 对象读到它")
    assert "zverev-khachanov" not in out


def test_撞车时重读main再推_两边的认领都留着(repo, monkeypatch):
    other = repo.clone("other")
    git_blobs.fetch_ref("origin", "main", cwd=other)        # other 手里的 main 是旧的
    monkeypatch.chdir(repo.work)
    assert probe_claims.main(["probe-step", "--url", YT, "--slug", "wang-garland",
                              "--branch", "feature", "--run-id", "1"]) == 0
    real = git_blobs.fetch_ref
    calls = []

    def stale_first(remote, branch, cwd=None):
        calls.append(1)
        if len(calls) > 1:
            return real(remote, branch, cwd=cwd)
        return f"refs/remotes/{remote}/{branch}"            # 第一趟不 fetch：必然被拒

    monkeypatch.setattr(git_blobs, "fetch_ref", stale_first)
    monkeypatch.setattr(probe_claims.time, "sleep", lambda s: None)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    probe_claims.push_to_main(
        KEY, lambda d: probe_claims.with_claim(d, key=KEY, url=YT, slug="wang-garland-singapore-2026-r2",
                                               branch="claude/x", run_id="2", outdir="o", now=now),
        message="t", cwd=other)
    assert len(calls) == 2, "第一趟被拒之后要重读 main 再做一遍"
    slugs = {c["slug"] for c in _remote_claims(repo.remote)["claims"]}
    assert slugs == {"wang-garland", "wang-garland-singapore-2026-r2"}, "后推的不许把先推的盖掉"


def test_probe失败只摘自己那条认领_摘空了删文件(repo, monkeypatch):
    monkeypatch.chdir(repo.work)
    for slug in ("a-b", "a-b-cup-2026"):
        assert probe_claims.main(["probe-step", "--url", YT, "--slug", slug,
                                  "--branch", "feature", "--run-id", "1"]) == 0
    assert probe_claims.main(["release", "--url", YT, "--slug", "a-b"]) == 0
    assert [c["slug"] for c in _remote_claims(repo.remote)["claims"]] == ["a-b-cup-2026"]
    assert probe_claims.main(["release", "--url", YT, "--slug", "a-b-cup-2026"]) == 0
    assert _remote_claims(repo.remote) is None


def test_认领过期不算先例():
    from datetime import datetime, timedelta, timezone
    now = datetime(2026, 9, 27, 6, 0, tzinfo=timezone.utc)
    doc = {"claims": [
        {"slug": "old", "claimed_at": (now - timedelta(days=4)).strftime("%Y-%m-%dT%H:%M:%SZ")},
        {"slug": "new", "claimed_at": (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")},
    ]}
    got = probe_claims._claim_priors(doc, ref="HEAD", now=now, days=probe_claims.DEDUPE_DAYS)
    assert [p.slug for p in got] == ["new"]


# ------------------------------------------------------------------ 编排器


def _orch():
    import orchestrate  # noqa: PLC0415
    return orchestrate


def _cand(slug, home, away):
    return {"slug": slug, "column": "reel", "score": 80, "heat": "世界前20", "level": "W500",
            "round": "R2", "home": home, "away": away, "status": "finished",
            "event": "Singapore", "year": 2026, "date": "2026-09-24"}


def _prior(slug, kind="claim"):
    return probe_claims.Prior(slug=slug, kind=kind, where=f"output/2026-09-24/reel/{slug}",
                              ref="HEAD", at="2026-09-24T09:59Z", branch="claude/x")


def test_编排器_别人已经在做这一场就不点run_借源和自己不算(capsys):
    o = _orch()
    c = _cand("wang-garland", "Xinyu Wang", "Caty Garland")
    item = [(c, YT, "youtube")]
    blocked = o.drop_already_probed(item, finder=lambda k, sn: [_prior("wang-garland-singapore-2026-r2")])
    assert blocked == [], "会话已经认领了同一条源片（slug 里带着这场的姓），编排器不许再点"
    assert "wang-garland-singapore-2026-r2" in capsys.readouterr().out
    # 前缀也认：会话写过 wangxiyu-swiatek，编排器的姓是 wang
    assert o.drop_already_probed(item, finder=lambda k, sn: [_prior("wangxiyu-garland-x")]) == []
    for harmless in ("asian-games-vs-china-open-src-wang",   # 故事片借源：不会产出这一场的赛场之上
                     "sz-sfzverev",                          # 不带这场的姓
                     "wang-garland"):                        # 自己上一趟：归 state 管
        assert o.drop_already_probed(item, finder=lambda k, sn, s=harmless: [_prior(s)]) == item, harmless


def test_编排器_同一批两个slug指着同一条源片只点全名那条(capsys):
    o = _orch()
    short = _cand("ka.-shnaider", "Pliskova Ka.", "Diana Shnaider")
    full = _cand("pliskova-shnaider", "Karolina Pliskova", "Diana Shnaider")
    other = _cand("zheng-rybakina", "Qinwen Zheng", "Elena Rybakina")
    got = o.drop_already_probed(
        [(short, YT, "youtube"), (other, "https://youtu.be/ChIOgR3JpVQ", "youtube"),
         (full, YT, "youtube")], finder=lambda k, sn: [])
    assert [c["slug"] for c, _u, _v in got] == ["pliskova-shnaider", "zheng-rybakina"]
    assert "只点全名那条" in capsys.readouterr().out


def test_编排器_查认领挂了按没做过处理并出声(capsys):
    o = _orch()
    c = _cand("wang-garland", "Xinyu Wang", "Caty Garland")

    def boom(k, sn):
        raise git_blobs.GitError("fatal: bad object")

    assert o.drop_already_probed([(c, YT, "youtube")], finder=boom) == [(c, YT, "youtube")]
    assert "::warning::" in capsys.readouterr().out, "查不了要出声，不许和「没人做过」长得一样"


def test_编排器的默认查法_稀疏检出里按HEAD的git对象读到probe目录(repo, monkeypatch):
    """编排器的检出没有 `output/`：probe 目录要按 git 对象读，认领按工作区的 data/ 读。"""
    o = _orch()
    git_blobs.fetch_ref("origin", "main", cwd=repo.work)
    _git(repo.work, "switch", "-q", "--detach", "refs/remotes/origin/main")
    assert not (repo.work / "output").exists(), "前提：output/ 不在稀疏范围里"
    monkeypatch.chdir(repo.work)
    got = o._prior_finder(KEY, ["wang", "garland"])
    assert [(p.slug, p.kind) for p in got] == [("wang-garland-singapore-2026-r2", "probe")]


def test_编排器main_去重排在配额切片之前(monkeypatch, tmp_path):
    import subprocess as sp
    o = _orch()
    monkeypatch.setattr(o, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(o, "SPECS_DIR", tmp_path / "specs")
    short = _cand("ka.-shnaider", "Pliskova Ka.", "Diana Shnaider")
    full = _cand("pliskova-shnaider", "Karolina Pliskova", "Diana Shnaider")
    other = _cand("zheng-rybakina", "Qinwen Zheng", "Elena Rybakina")
    monkeypatch.setattr(o, "build_digest", lambda today: object())
    monkeypatch.setattr(o, "candidates", lambda dig: [short, full, other])
    urls = {"Pliskova Ka.": YT, "Karolina Pliskova": YT, "Qinwen Zheng": "https://youtu.be/ChIOgR3JpVQ"}
    monkeypatch.setitem(sys.modules, "detect_highlights", type("M", (), {
        "HighlightSourceError": RuntimeError,
        "find_highlight": staticmethod(lambda h, a, e, y: (urls[h], "youtube"))})())
    monkeypatch.setattr(o, "_prior_finder", lambda k, sn: [])
    calls = []
    monkeypatch.setattr(sp, "run", lambda cmd, check=True, **kw: calls.append(cmd))
    monkeypatch.setattr(sys, "argv", ["orchestrate.py", "--apply", "--max", "2"])
    assert o.main() == 0
    slugs = [x.split("=", 1)[1] for cmd in calls for x in cmd if str(x).startswith("slug=")]
    assert slugs == ["pliskova-shnaider", "zheng-rybakina"], (
        "同一场的缩写版白占了配额，另一场被挤到下一班")


# ------------------------------------------------------------------ 工作流


def _steps(name: str) -> list[dict]:
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
    return next(iter(wf["jobs"].values()))["steps"]


def test_match_reel的probe一开跑就认领_失败摘认领_表单不加输入():
    steps = _steps("match-reel.yml")
    idx = {i: s for i, s in enumerate(steps)}

    def find(needle):
        hits = [i for i, s in idx.items() if needle in str(s.get("run", ""))]
        assert len(hits) == 1, f"{needle} 应该正好出现在一步里：{hits}"
        return hits[0]

    claim = find("probe_claims.py probe-step")
    download = find("build_match_reel.py probe")
    deps = next(i for i, s in idx.items() if s.get("name") == "装依赖")
    assert claim < deps < download, "认领要排在装依赖之前——越早认领，两边同时点的窗口越窄"
    assert "mode == 'probe'" in steps[claim]["if"]
    release = find("probe_claims.py release")
    assert "failure()" in steps[release]["if"] and "mode == 'probe'" in steps[release]["if"]
    assert "${{" not in steps[claim]["run"].split("--url")[1].split("--slug")[0], (
        "url 走 env 传，别把表单原文拼进 shell")
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "match-reel.yml").read_text(encoding="utf-8"))
    assert len(wf[True]["workflow_dispatch"]["inputs"]) <= 25, "GitHub 表单最多 25 个输入"
