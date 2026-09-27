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


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_认领过期不算先例():
    from datetime import datetime, timedelta, timezone
    now = datetime(2026, 9, 27, 6, 0, tzinfo=timezone.utc)
    doc = {"claims": [
        {"slug": "old", "claimed_at": _iso(now - timedelta(days=4)), "done_at": _iso(now - timedelta(days=4))},
        {"slug": "new", "claimed_at": _iso(now - timedelta(hours=2)), "done_at": _iso(now - timedelta(hours=1))},
    ]}
    got = probe_claims._claim_priors(doc, ref="HEAD", now=now, days=probe_claims.DEDUPE_DAYS)
    assert [p.slug for p in got] == ["new"]


def test_没标完成的认领开跑90分钟后作废_标了完成的活满三天(capsys):
    """job 被取消／超时：`release` 挂在 failure() 上不跑、`done` 也没标——认领不许把这一场压三天。"""
    from datetime import datetime, timedelta, timezone
    now = datetime(2026, 9, 27, 6, 0, tzinfo=timezone.utc)
    stale = probe_claims.CLAIM_STALE_MINUTES
    doc = {"claims": [
        {"slug": "cancelled", "claimed_at": _iso(now - timedelta(minutes=stale + 5))},
        {"slug": "running", "claimed_at": _iso(now - timedelta(minutes=stale - 5))},
        {"slug": "finished", "claimed_at": _iso(now - timedelta(hours=20)),
         "done_at": _iso(now - timedelta(hours=19))},
    ]}
    got = probe_claims._claim_priors(doc, ref="HEAD", now=now, days=probe_claims.DEDUPE_DAYS)
    assert sorted(p.slug for p in got) == ["finished", "running"]
    assert "cancelled 的认领开跑" in capsys.readouterr().out, "作废要出声，别和「没人认领」长得一样"


def test_认领时刻漏了时区_按UTC读_不许TypeError把整班带崩():
    from datetime import datetime, timedelta, timezone
    now = datetime(2026, 9, 27, 6, 0, tzinfo=timezone.utc)
    naive = (now - timedelta(minutes=10)).replace(tzinfo=None).isoformat()     # 没有 Z
    doc = {"claims": [{"slug": "naive", "claimed_at": naive}, {"slug": "junk", "claimed_at": 12345},
                      "not-a-dict", {"slug": "none"}]}
    got = probe_claims._claim_priors(doc, ref="HEAD", now=now, days=3)
    assert [p.slug for p in got] == ["naive"]
    out = probe_claims.with_claim(doc, key=KEY, url=YT, slug="x", branch="b", run_id="1",
                                  outdir="o", now=now)
    assert [c["slug"] for c in out["claims"]] == ["naive", "x"]
    # now 自己是 naive 也不许炸
    assert [p.slug for p in probe_claims._claim_priors(doc, ref="HEAD", now=now.replace(tzinfo=None),
                                                        days=3)] == ["naive"]


def test_分支上probe成功给认领标完成_main上看得见(repo, monkeypatch):
    monkeypatch.chdir(repo.work)
    assert probe_claims.main(["probe-step", "--url", YT, "--slug", "wang-garland-x",
                              "--branch", "feature", "--run-id", "1"]) == 0
    assert "done_at" not in _remote_claims(repo.remote)["claims"][0]
    assert probe_claims.main(["done", "--url", YT, "--slug", "wang-garland-x"]) == 0
    (claim,) = _remote_claims(repo.remote)["claims"]
    assert claim["done_at"], "分支上的产物 main 上看不见，只能靠这一笔证明那趟跑完了"
    # 没有这条认领（开跑那一推没推上）就不补写
    assert probe_claims.main(["done", "--url", YT, "--slug", "nobody"]) == 0
    assert [c["slug"] for c in _remote_claims(repo.remote)["claims"]] == ["wang-garland-x"]


def test_probe那一步只fetch_main一次(repo, monkeypatch):
    monkeypatch.chdir(repo.work)
    real = git_blobs.fetch_ref
    calls = []
    monkeypatch.setattr(git_blobs, "fetch_ref",
                        lambda r, b, cwd=None: calls.append(b) or real(r, b, cwd=cwd))
    assert probe_claims.main(["probe-step", "--url", YT, "--slug", "a-b",
                              "--branch", "feature", "--run-id", "1"]) == 0
    assert calls == ["main"], "查先例前取过一次，推认领的第一趟不再取"
    assert _remote_claims(repo.remote)["claims"][0]["slug"] == "a-b"


def test_probe那一步什么错都只出声(repo, monkeypatch, capsys):
    """认领是告示：cat-file 解析挂了（ValueError）、坏认领（TypeError）都不许让 probe 红。"""
    monkeypatch.chdir(repo.work)

    def boom(*a, **k):
        raise ValueError("cat-file 输出对不上")

    monkeypatch.setattr(probe_claims, "find_priors", boom)
    monkeypatch.setattr(probe_claims, "push_to_main", lambda *a, **k: (_ for _ in ()).throw(TypeError("x")))
    assert probe_claims.main(["probe-step", "--url", YT, "--slug", "a-b",
                              "--branch", "feature", "--run-id", "1"]) == 0
    out = capsys.readouterr().out
    assert "这一趟**没查**：ValueError" in out and "认领没推上 main（TypeError" in out


# ------------------------------------------------------------------ git_blobs.fetch_ref


def _deep_shallow(tmp_path):
    """main 上 5 个提交的远端 ＋ 一份 `--depth=3` 的本地浅克隆（这台沙箱就是这个形状），
    本地在 main 上开了特性分支，远端 main 又往前走了一个提交。"""
    remote = tmp_path / "deep.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    seed = tmp_path / "deep-seed"
    _git(tmp_path, "init", "-q", "-b", "main", str(seed))
    _git(seed, "remote", "add", "origin", str(remote))
    for i in range(5):
        _write(seed, "n.txt", str(i))
        _git(seed, "add", "-A")
        _git(seed, "commit", "-q", "-m", f"c{i}")
    _git(seed, "push", "-q", "origin", "main")
    work = tmp_path / "deep-work"
    _git(tmp_path, "clone", "-q", "--depth=3", f"file://{remote}", str(work))
    fork = _git(work, "rev-parse", "HEAD").strip()
    _git(work, "switch", "-q", "-c", "feat")
    _write(work, "f.txt", "feat")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "feat")
    _write(seed, "n.txt", "5")
    _git(seed, "commit", "-q", "-am", "c5")
    _git(seed, "push", "-q", "origin", "main")
    assert git_blobs.is_shallow(work) and git_blobs.rev("refs/remotes/origin/main", cwd=work)
    return work, fork


def test_深的浅克隆fetch_main不许被截成一个提交(tmp_path, monkeypatch):
    """review 复现：`--depth=20` 的沙箱里 fetch 一律带 `--depth=1`，origin/main 被截成一个
    提交，`git merge-base feat origin/main` 当场返回空，下一次 rebase 就找不到分叉点。"""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    work, fork = _deep_shallow(tmp_path)
    git_blobs.fetch_ref("origin", "main", cwd=work)
    res = subprocess.run(["git", "merge-base", "feat", "refs/remotes/origin/main"], cwd=work,
                         capture_output=True, text=True)
    assert res.returncode == 0 and res.stdout.strip() == fork, (
        "origin/main 被截短了——特性分支和它找不到分叉点")
    assert int(_git(work, "rev-list", "--count", "refs/remotes/origin/main")) >= 4


def test_fetch_ref只在runner上或本地还没有这个ref时带depth1(tmp_path, monkeypatch, repo):
    work, _fork = _deep_shallow(tmp_path)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert git_blobs.fetch_depth_args("origin", "main", cwd=work) == []
    assert git_blobs.fetch_depth_args("origin", "nosuch", cwd=work) == ["--depth=1"], (
        "本地还没有这个 ref：不带 depth 会一路往回取到整条历史")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert git_blobs.fetch_depth_args("origin", "main", cwd=work) == ["--depth=1"], (
        "runner 的检出是 depth 1，要的只是最新那一个提交")
    assert git_blobs.fetch_depth_args("origin", "main", cwd=repo.seed) == [], (
        "完整克隆一律不带——带了会把它变浅")


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


def test_编排器_故事片借同一条源片不许挡住这一场的赛场之上():
    """review 抓到的误拦：`-src-` 不是故事片唯一的写法。这三条都是真实 slug，都和
    同一场的赛场之上 probe 了同一条视频，slug 里都带着这场的姓、都没有 `src`——
    按「slug 里带着姓」挡，故事片先 probe 了，这一场的赛场之上三天不点。"""
    o = _orch()
    for cand, story in (
            (_cand("keys-zheng", "Madison Keys", "Qinwen Zheng"), "comebacks-zheng-keys"),
            (_cand("eala-zheng", "Alexandra Eala", "Qinwen Zheng"), "zheng-us-open-outlook-zheng"),
            (_cand("zheng-vekic", "Qinwen Zheng", "Donna Vekic"), "zheng-lanlana-hl-zheng-paris")):
        item = [(cand, YT, "youtube")]
        assert o.drop_already_probed(item, finder=lambda k, sn, s=story: [_prior(s, kind="probe")]) == item, story
    # 开头两个词正好是这两个姓，但 spec 自己说是网球有故事：也不挡
    keys = _cand("keys-zheng", "Madison Keys", "Qinwen Zheng")
    story = probe_claims.Prior(slug="zheng-keys-story", kind="probe", where="w", ref="HEAD",
                               at="2026-09-24", column="网球有故事")
    assert o.drop_already_probed([(keys, YT, "y")], finder=lambda k, sn: [story]) == [(keys, YT, "y")]


def test_编排器_有正面证据才挡_命名或栏目():
    o = _orch()
    keys = _cand("keys-zheng", "Madison Keys", "Qinwen Zheng")
    item = [(keys, YT, "youtube")]
    # 会话的命名：赢家在前 ＋ 站 ＋ 年 ＋ 轮
    assert o.drop_already_probed(item, finder=lambda k, sn: [_prior("zheng-keys-us-open-2026-r3")]) == []
    # 缩写名的自动草稿：slug 只带一个姓，但草稿自己说是赛场之上
    full = _cand("pliskova-shnaider", "Karolina Pliskova", "Diana Shnaider")
    draft = probe_claims.Prior(slug="ka.-shnaider", kind="probe", where="w", ref="HEAD",
                               at="2026-09-03", column=probe_claims.MATCH_COLUMN)
    assert o.drop_already_probed([(full, YT, "y")], finder=lambda k, sn: [draft]) == []
    # 同一条视频上的赛场之上，slug 里一个姓都不带（合集视频里的另一场）：不挡
    other = probe_claims.Prior(slug="sabalenka-x", kind="probe", where="w", ref="HEAD",
                               at="2026-09-03", column=probe_claims.MATCH_COLUMN)
    assert o.drop_already_probed([(full, YT, "y")], finder=lambda k, sn: [other]) == [(full, YT, "y")]


def test_find_priors带出先例的栏目_赛场之上和故事片分得开(repo, monkeypatch):
    """`blocks_dispatch` 靠栏目分赛场之上和故事片借源：栏目要从 spec／草稿里读出来——
    编排器的检出是稀疏的，spec 在 main 上、不在工作区里也要按 git 对象读得到。"""
    _git(repo.seed, "switch", "-q", "main")
    _write(repo.seed, "specs/reels/wang-garland-singapore-2026-r2.json",
           {"cover": {"eyebrow": "赛场之上"}})
    # 开头两个词正好是这两个姓的故事片（命名认不出来，只有栏目认得出）
    _write(repo.seed, f"output/{_today()}/reel/garland-wang-story/probe.json", {"url": YT})
    _write(repo.seed, "specs/reels/garland-wang-story.json", {"cover": {"eyebrow": "网球有故事"}})
    _git(repo.seed, "add", "-A")
    _git(repo.seed, "commit", "-q", "-m", "specs")
    _git(repo.seed, "push", "-q", "origin", "main")
    git_blobs.fetch_ref("origin", "main", cwd=repo.work)
    monkeypatch.chdir(repo.work)
    got = probe_claims.find_priors(KEY, refs=["refs/remotes/origin/main"], root=repo.work,
                                   surnames=["wang", "garland"])
    assert sorted((p.slug, p.column) for p in got) == [
        ("garland-wang-story", "网球有故事"), ("wang-garland-singapore-2026-r2", "赛场之上")]
    blocking = [p.slug for p in got if probe_claims.blocks_dispatch(p, "wang-garland", ["wang", "garland"])]
    assert blocking == ["wang-garland-singapore-2026-r2"]
    assert probe_claims.spec_column({"cover": {"eyebrow": "网球有故事"}, "_column": "reel"}) == "网球有故事"
    assert probe_claims.spec_column({"_column": "reel"}) == "赛场之上", "自动草稿只写 _column"
    assert probe_claims.spec_column({"_column": "赛场之上。讲一场对决，赢家在前。"}) == "赛场之上"
    assert probe_claims.spec_column({"cover": "x"}) == "" and probe_claims.spec_column(None) == ""


def _state_entry(slug, at, video=KEY, date_="2026-09-24"):
    return {"column": "reel", "score": 80, "date": date_, "video": video,
            "dispatched_at": _iso(at)}


def test_编排器_缩写名那趟被取消_认领和state过了钟_全名那条照样点():
    """review 复现的死锁：编排器缩写名那趟被取消（63 分钟超时），`release` 挂在
    failure() 上不跑，认领和 state 条目都留着；下一班同一场冒出全名 slug，老规则
    按「slug 里带着姓」拿缩写名那条认领挡住它——两个 slug 三天里谁都不点。"""
    from datetime import datetime, timedelta, timezone
    o = _orch()
    t0 = datetime(2026, 9, 24, 10, 0, tzinfo=timezone.utc)
    full = _cand("pliskova-shnaider", "Karolina Pliskova", "Diana Shnaider")
    item = [(full, YT, "youtube")]
    claim_doc = {"claims": [{"slug": "ka.-shnaider", "branch": "main", "outdir": "o",
                             "claimed_at": _iso(t0)}]}

    def run(now):
        state = {"dispatched": {"ka.-shnaider": _state_entry("ka.-shnaider", t0)}}
        finder = lambda k, sn: probe_claims._claim_priors(claim_doc, ref="HEAD", now=now, days=3)  # noqa: E731
        return o.drop_already_probed(item, finder=finder, state=state, now=now)

    assert run(t0 + timedelta(minutes=30)) == [], "那一趟可能还在跑（30 分钟）：要挡"
    assert run(t0 + timedelta(hours=2)) == item, "认领和 state 都过了钟、probe 也没落：不许再挡"
    # 认领推不上的那趟（只有 state）：一样在钟内挡、过钟放
    for minutes, want in ((30, []), (120, item)):
        state = {"dispatched": {"ka.-shnaider": _state_entry("ka.-shnaider", t0)}}
        got = o.drop_already_probed(item, finder=lambda k, sn: [], state=state,
                                    now=t0 + timedelta(minutes=minutes))
        assert got == want, minutes
    # 那一趟真跑完了（probe.json 在 main 上）：多久以后都挡
    done = probe_claims.Prior(slug="ka.-shnaider", kind="probe", where="w", ref="HEAD", at="2026-09-24")
    state = {"dispatched": {"ka.-shnaider": _state_entry("ka.-shnaider", t0)}}
    assert o.drop_already_probed(item, finder=lambda k, sn: [done], state=state,
                                 now=t0 + timedelta(days=1)) == []
    # 同一条源片、另一天的 state 条目（再交手）不算
    state = {"dispatched": {"ka.-shnaider": _state_entry("ka.-shnaider", t0, date_="2026-09-10")}}
    assert o.drop_already_probed(item, finder=lambda k, sn: [], state=state,
                                 now=t0 + timedelta(minutes=30)) == item


def test_编排器_被挡下的候选记进state_下一班不再跑find_highlight(monkeypatch, tmp_path):
    """review：被挡下的候选每 10 分钟一班都重跑一遍 yt-dlp 搜索 ＋ vet。记进
    `state["blocked"]`，下一班拿缓存的源片只复查先例；挡它的没了就照常点。"""
    import datetime as dt
    import json as _json
    import subprocess as sp
    o = _orch()
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(o, "STATE_PATH", state_file)
    monkeypatch.setattr(o, "SPECS_DIR", tmp_path / "specs")
    today = dt.date.today().isoformat()
    monkeypatch.setattr(o, "build_digest", lambda d: object())
    monkeypatch.setattr(o, "candidates", lambda dig: [
        {**_cand("wang-garland", "Xinyu Wang", "Caty Garland"), "date": today}])
    searches = []
    monkeypatch.setitem(sys.modules, "detect_highlights", type("M", (), {
        "HighlightSourceError": RuntimeError,
        "find_highlight": staticmethod(lambda h, a, e, y: searches.append(h) or (YT, "youtube"))})())
    priors = [_prior("wang-garland-singapore-2026-r2")]
    monkeypatch.setattr(o, "_prior_finder", lambda k, sn: list(priors))
    calls = []
    monkeypatch.setattr(sp, "run", lambda cmd, check=True, **kw: calls.append(cmd))
    monkeypatch.setattr(sys, "argv", ["orchestrate.py", "--apply"])

    class Clock(dt.datetime):                               # 每班之间过十分钟
        t = [dt.datetime.now(dt.timezone.utc)]

        @classmethod
        def now(cls, tz=None):
            cls.t[0] += dt.timedelta(minutes=10)
            return cls.t[0]

    monkeypatch.setattr(o, "datetime", Clock)

    assert o.main() == 0 and calls == [] and len(searches) == 1
    saved = _json.loads(state_file.read_text(encoding="utf-8"))
    assert saved["blocked"]["wang-garland"]["url"] == YT
    assert saved["blocked"]["wang-garland"]["by"] == "wang-garland-singapore-2026-r2"
    assert "wang-garland" not in saved["dispatched"], "挡下不是点过：dashboard 按 dispatched 数"
    before = state_file.read_bytes()

    assert o.main() == 0 and calls == []
    assert len(searches) == 1, "下一班又探了一遍源片"
    assert state_file.read_bytes() == before, "挡它的没变：state 不许每班都改（每班都要提交）"

    priors.clear()                                          # 那一趟被摘了／作废了
    assert o.main() == 0 and len(searches) == 1
    assert [x for cmd in calls for x in cmd if str(x).startswith("url=")] == [f"url={YT}"]
    saved = _json.loads(state_file.read_text(encoding="utf-8"))
    assert "wang-garland" not in saved["blocked"]
    assert saved["dispatched"]["wang-garland"]["video"] == KEY, "记下视频 id，下一班换个 slug 也认得出"
    assert saved["dispatched"]["wang-garland"]["dispatched_at"]


def test_state三方合并带上本趟新挡下的候选():
    sys.path.insert(0, str(ROOT / "tools"))
    from merge_orchestration_state import merge_states
    base = {"dispatched": {}}
    ours = {"dispatched": {}, "blocked": {"a-b": {"url": YT, "by": "x"}}}
    theirs = {"dispatched": {"c-d": {"date": "2026-09-24"}}}
    merged = merge_states(base, ours, theirs)
    assert merged["blocked"] == {"a-b": {"url": YT, "by": "x"}} and "c-d" in merged["dispatched"]


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
    assert steps[claim].get("continue-on-error") is True, (
        "认领是告示：2 分钟超时或脚本没接住的异常不许让 probe 红")
    release = find("probe_claims.py release")
    assert "failure()" in steps[release]["if"] and "mode == 'probe'" in steps[release]["if"]
    done = find("probe_claims.py done")
    commit = next(i for i, s in idx.items() if s.get("name") == "提交产物")
    assert done > commit, "产物推上分支之后才能说「跑完了」"
    cond = steps[done]["if"]
    assert "success()" in cond and "mode == 'probe'" in cond and "ref_name != 'main'" in cond, (
        "分支上 probe 成功才标完成——main 上的 probe.json 自己看得见")
    assert steps[done].get("continue-on-error") is True
    assert "${{" not in steps[claim]["run"].split("--url")[1].split("--slug")[0], (
        "url 走 env 传，别把表单原文拼进 shell")
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "match-reel.yml").read_text(encoding="utf-8"))
    assert len(wf[True]["workflow_dispatch"]["inputs"]) <= 25, "GitHub 表单最多 25 个输入"


# ------------------------------------------------------------------ 完成的认领也有钟
# 账号所有者 2026-09-27 选定：标了完成的认领，完成之后 20 小时里 main 上还没有这个
# slug 的正式 spec，就不再挡编排器（和比赛日那道新鲜窗同一个数）。


def test_完成的认领20小时没有正式spec就不再挡(capsys):
    from datetime import datetime, timedelta, timezone

    import promote_reel_draft  # noqa: PLC0415
    now = datetime(2026, 9, 27, 11, 0, tzinfo=timezone.utc)
    slug = "wu-shang-hangzhou-2026-r2"

    def doc(hours):
        return {"claims": [{"slug": slug, "claimed_at": _iso(now - timedelta(hours=hours, minutes=12)),
                            "done_at": _iso(now - timedelta(hours=hours))}]}

    def got(d, has_spec):
        return [p.slug for p in probe_claims._claim_priors(d, ref="HEAD", now=now, days=3,
                                                            has_spec=has_spec)]

    on_main = lambda s: s == slug  # noqa: E731
    missing = lambda s: False  # noqa: E731
    assert got(doc(21), on_main) == [slug], "完成的认领 ＋ main 上有正式 spec：照旧挡"
    assert got(doc(19), missing) == [slug], "完成 19 小时、还没 spec：还在窗里，挡"
    capsys.readouterr()
    assert got(doc(21), missing) == [], "完成 21 小时、main 上还没 spec：不再挡"
    assert "不再挡这一场" in capsys.readouterr().out, "放行要出声，别和「没人认领」长得一样"
    assert got(doc(21), None) == [slug], "查不了 spec（没给 has_spec）就照旧挡，不许因为没查就放行"
    # 没标完成的那条钟（90 分钟）不受影响
    running = {"claims": [{"slug": slug, "claimed_at": _iso(now - timedelta(minutes=30))}]}
    assert got(running, missing) == [slug]
    # 三处是同一个数：调度侧新鲜窗、草稿侧新鲜窗、完成认领的钟
    o = _orch()
    assert (timedelta(hours=probe_claims.DONE_CLAIM_SPEC_HOURS)
            == timedelta(hours=o.FRESH_RESULT_HOURS) == promote_reel_draft.PENDING_MAX_AGE)


def test_完成的认领过了20小时_编排器按main上有没有正式spec决定挡不挡(repo, monkeypatch, capsys):
    """走真的 `find_priors`（按 git 对象读 main 上的认领和 spec）＋ `blocks_dispatch`。
    编排器工作区和 main 上是同一份认领文件——「不再挡」那一句只许印一次。"""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    slug = "garland-wang-singapore-2026-r2"
    _git(repo.seed, "switch", "-q", "main")
    _write(repo.seed, probe_claims.claim_path(KEY), {"video_key": KEY, "claims": [
        {"slug": slug, "branch": "claude/x", "outdir": f"output/x/reel/{slug}",
         "claimed_at": _iso(now - timedelta(hours=21, minutes=10)),
         "done_at": _iso(now - timedelta(hours=21))}]})
    _git(repo.seed, "add", "-A")
    _git(repo.seed, "commit", "-q", "-m", "claim")
    _git(repo.seed, "push", "-q", "origin", "main")
    git_blobs.fetch_ref("origin", "main", cwd=repo.work)
    monkeypatch.chdir(repo.work)

    def blocking():
        priors = probe_claims.find_priors(KEY, refs=["refs/remotes/origin/main"], root=repo.work,
                                          surnames=["wang", "garland"], now=now)
        return [p.slug for p in priors if p.slug == slug
                and probe_claims.blocks_dispatch(p, "wang-garland", ["wang", "garland"])]

    _write(repo.work, probe_claims.claim_path(KEY), json.loads(
        (repo.seed / probe_claims.claim_path(KEY)).read_text(encoding="utf-8")))
    capsys.readouterr()
    assert blocking() == [], "完成 21 小时、main 上没有正式 spec：编排器照常点"
    said = capsys.readouterr().out.count("不再挡这一场")
    assert said == 1, f"工作区和 main 各读一遍同一个认领，「不再挡」印了 {said} 遍"
    _write(repo.seed, probe_claims.FORMAL_SPEC.format(slug), {"cover": {"eyebrow": "赛场之上"}})
    _git(repo.seed, "add", "-A")
    _git(repo.seed, "commit", "-q", "-m", "spec")
    _git(repo.seed, "push", "-q", "origin", "main")
    git_blobs.fetch_ref("origin", "main", cwd=repo.work)
    assert blocking() == [slug], "正式 spec 落在 main 上了：这一场有人做完了，照旧挡"



# 评审 2026-09-27 的两条 nit：
# 1. `has_spec` 原来用 `cat-file blob` 查存在——部分克隆（`--filter=blob:none`）里 blob
#    要懒取，懒取不到（断网、远端换了）就读成「没 spec」、把认领放掉，和「查不了 spec
#    就照旧挡」正相反。改成 `ls-tree`（树在本地），git 出错一律照旧挡
# 2. 原来只认认领自己的 slug：spec 另起了名（先 probe 短 slug）就会被放掉。现在
#    `sources` 里挂着这条源片的**赛场之上**正式 spec 也算；故事片借源不算


def _lapsed_claim(repo, monkeypatch, slug: str):
    """工作区里一条 21 小时前标完成的认领；返回 (往 main 推一个文件, 编排器挡不挡这一场)。"""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    _git(repo.seed, "switch", "-q", "main")
    git_blobs.fetch_ref("origin", "main", cwd=repo.work)
    monkeypatch.chdir(repo.work)
    _write(repo.work, probe_claims.claim_path(KEY), {"video_key": KEY, "claims": [
        {"slug": slug, "branch": "claude/x", "outdir": f"output/x/reel/{slug}",
         "claimed_at": _iso(now - timedelta(hours=21, minutes=10)),
         "done_at": _iso(now - timedelta(hours=21))}]})

    def push(rel: str, body) -> None:
        if body is None:
            _git(repo.seed, "rm", "-q", rel)
        else:
            _write(repo.seed, rel, body)
            _git(repo.seed, "add", "-A")
        _git(repo.seed, "commit", "-q", "-m", rel)
        _git(repo.seed, "push", "-q", "origin", "main")
        git_blobs.fetch_ref("origin", "main", cwd=repo.work)

    def blocking() -> list[str]:
        priors = probe_claims.find_priors(KEY, refs=["refs/remotes/origin/main"], root=repo.work,
                                          surnames=["wang", "garland"], now=now)
        return [p.slug for p in priors if p.slug == slug
                and probe_claims.blocks_dispatch(p, "wang-garland", ["wang", "garland"])]

    assert blocking() == [], "前提自证：main 上什么 spec 都没有时，过了 20 小时放行"
    return push, blocking


def test_完成认领查正式spec_部分克隆懒取不到blob也照旧挡(repo, monkeypatch):
    slug = "garland-wang"
    push, blocking = _lapsed_claim(repo, monkeypatch, slug)
    push(probe_claims.FORMAL_SPEC.format(slug), {"cover": {"eyebrow": "赛场之上"}})
    _git(repo.work, "remote", "set-url", "origin", str(repo.remote.parent / "gone.git"))
    assert git_blobs.show("refs/remotes/origin/main", probe_claims.FORMAL_SPEC.format(slug),
                          cwd=repo.work) is None, "前提自证：blob 懒取不到（不然测的不是这条路）"
    assert blocking() == [slug], "blob 取不回来不等于 spec 不在：树里有就照旧挡"


def test_完成认领查正式spec_另起名的同一场赛场之上也算_故事片借源不算(repo, monkeypatch):
    slug = "garland-wang"
    push, blocking = _lapsed_claim(repo, monkeypatch, slug)
    story = "wang-garland-src-comebacks"
    push(probe_claims.FORMAL_SPEC.format(story),
         {"cover": {"eyebrow": "网球有故事"}, "sources": {"a": {"url": YT}}})
    assert blocking() == [], "故事片借同一条源片不是这一场的赛场之上：过了 20 小时照样放"
    formal = "wang-garland-singapore-2026-r2"
    push(probe_claims.FORMAL_SPEC.format(formal),
         {"cover": {"eyebrow": "赛场之上"}, "source_url": f"https://youtu.be/{KEY}?si=x"})
    assert blocking() == [slug], "赛场之上的正式 spec 另起了名、源片是同一条：这一场做完了，照旧挡"
    other = "wang-garland-singapore-2026-sf"
    push(probe_claims.FORMAL_SPEC.format(formal), None)
    push(probe_claims.FORMAL_SPEC.format(other),
         {"cover": {"eyebrow": "赛场之上"}, "sources": {"a": {"url": "https://youtu.be/uuLC8AhqDx0"}}})
    assert blocking() == [], "同两个人的另一场（源片不同）不算这一场做完了"


def test_完成认领查正式spec_git出错照旧挡(repo, monkeypatch, capsys):
    slug = "garland-wang"
    _push, blocking = _lapsed_claim(repo, monkeypatch, slug)
    real_ls_tree = git_blobs.ls_tree

    def broken(ref, pathspecs, cwd=None):
        if any(p.startswith("specs/") for p in pathspecs):
            raise git_blobs.GitError("git ls-tree 失败（128）：模拟")
        return real_ls_tree(ref, pathspecs, cwd=cwd)

    monkeypatch.setattr(git_blobs, "ls_tree", broken)
    capsys.readouterr()
    assert blocking() == [slug], "查不了 spec 在不在：照旧挡，不许因为「没查成」就放行"
    assert "照旧挡" in capsys.readouterr().out, "照旧挡要出声"
