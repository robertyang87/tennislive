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


def test_state三方合并_本趟摘掉的blocked也带过去_远端改过的听远端():
    """review：merge 只加不减——本趟把 `a-b` 放行点出去了（从 blocked 摘掉），远端那份
    还留着它，合并之后它活到 STATE_TTL_DAYS，「复查」那一行天天印一个早就点过的 slug。"""
    from merge_orchestration_state import merge_states
    entry = {"url": YT, "by": "x", "date": "2026-09-24"}
    base = {"dispatched": {}, "blocked": {"a-b": entry, "e-f": entry}}
    ours = {"dispatched": {"a-b": {"date": "2026-09-24"}}, "blocked": {"e-f": entry}}
    theirs = {"dispatched": {}, "blocked": {"a-b": entry, "e-f": entry, "g-h": entry}}
    merged = merge_states(base, ours, theirs)
    assert set(merged["blocked"]) == {"e-f", "g-h"}, "本趟摘掉的 a-b 被远端那份复活了"
    # 远端自己改过那一条（换了挡它的人）：听远端的
    changed = {**entry, "by": "y"}
    merged = merge_states(base, ours, {**theirs, "blocked": {**theirs["blocked"], "a-b": changed}})
    assert merged["blocked"]["a-b"] == changed


def test_编排器_同一条源片上的另一场不许合成一组_state里的也要对得上姓():
    """review：合组只看视频 id、不看人——合集视频里的另一场会被当成同一场挡下，
    而且挡它的 probe／认领还在，就一直挡着（`state["blocked"]` 只复查先例）。"""
    from datetime import datetime, timedelta, timezone
    o = _orch()
    a = _cand("zheng-rybakina", "Qinwen Zheng", "Elena Rybakina")
    b = _cand("wang-garland", "Xinyu Wang", "Caty Garland")
    got = o.drop_already_probed([(a, YT, "y"), (b, YT, "y")], finder=lambda k, sn: [])
    assert [c["slug"] for c, _u, _v in got] == ["zheng-rybakina", "wang-garland"], (
        "同一条合集视频上的两场，一个人都对不上，不是同一场两个 slug")
    # 编排器上一班按同一条源片点过另一场：不算「自己点过这一场」
    t0 = datetime(2026, 9, 24, 10, 0, tzinfo=timezone.utc)
    state = {"dispatched": {"zheng-rybakina": _state_entry("zheng-rybakina", t0)}}
    assert o.drop_already_probed([(b, YT, "y")], finder=lambda k, sn: [], state=state,
                                 now=t0 + timedelta(minutes=10)) == [(b, YT, "y")]
    # 对照：缩写名那一对（同一场）照旧合组、照旧认 state
    short = _cand("ka.-shnaider", "Pliskova Ka.", "Diana Shnaider")
    full = _cand("pliskova-shnaider", "Karolina Pliskova", "Diana Shnaider")
    assert [c["slug"] for c, _u, _v in o.drop_already_probed(
        [(short, YT, "y"), (full, YT, "y")], finder=lambda k, sn: [])] == ["pliskova-shnaider"]
    state = {"dispatched": {"ka.-shnaider": _state_entry("ka.-shnaider", t0)}}
    assert o.drop_already_probed([(full, YT, "y")], finder=lambda k, sn: [], state=state,
                                 now=t0 + timedelta(minutes=10)) == []


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
    for i in (release, done):
        assert '--run-id "${{ github.run_id }}"' in steps[i]["run"], (
            "摘认领／标完成要按这一趟的 run id 认——按 slug 摘会把同一个 slug 上一趟"
            "已经标完成的记录一起抹掉")
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


# ------------------------------------------------------------------ review round 1


def test_复姓_小词_连字符_撇号的姓也认得出开头那一对():
    """review：`leads_with_pair` 只认开头两个整词／前缀，复姓全认不出——会话的 spec 还没上
    main（栏目看不到）时，编排器照样再 probe 一遍。235 份带 name_en 的已发赛场之上 spec
    里约 8% 是这种。左边是编排器手里的两个人（flashscore／ESPN 两种写法），右边是会话的 slug。"""
    o = _orch()
    cases = [
        (("Alexander Zverev", "Alex de Minaur"), "zverev-deminaur-laver-cup-2026"),
        (("Zverev A.", "De Minaur A."), "zverev-de-minaur-laver-cup-2026"),
        (("Stefanos Tsitsipas", "Felix Auger-Aliassime"), "tsitsipas-auger-aliassime-x-2026-r2"),
        (("Karolina Muchova", "Jessica Bouzas Maneiro"), "muchova-bouzas-bjk-cup-2026-sf"),
        (("Muchova K.", "Bouzas Maneiro J."), "muchova-bouzas-bjk-cup-2026-sf"),
        (("Joao Fonseca", "Botic van de Zandschulp"), "fonseca-van-de-zandschulp"),
        (("Taylor Fritz", "Christopher O'Connell"), "fritz-oconnell"),
        (("Taylor Fritz", "Christopher O'Connell"), "fritz-o-connell-x"),
    ]
    for (home, away), slug in cases:
        c = _cand("x-y", home, away)
        names = o._pair_names(c)
        assert probe_claims.leads_with_pair(names, slug), (names, slug)
        assert probe_claims.blocks_dispatch(_prior(slug), "x-y", names), (names, slug)
        assert o.drop_already_probed([(c, YT, "y")], finder=lambda k, sn, s=slug: [_prior(s)]) == [], slug
    # review 的原始复现：只给一个词的姓（`surname_en`）——小词 ＋ 姓照样认得出
    for names, slug in ((["zverev", "minaur"], "zverev-deminaur-laver-cup-2026"),
                        (["zverev", "minaur"], "zverev-de-minaur-laver-cup-2026"),
                        (["tsitsipas", "auger-aliassime"], "tsitsipas-auger-aliassime-x-2026-r2"),
                        (["fonseca", "zandschulp"], "fonseca-van-de-zandschulp"),
                        (["fritz", "o'connell"], "fritz-oconnell")):
        assert probe_claims.blocks_dispatch(_prior(slug), "-".join(names), names), (names, slug)
    # 只有 muchova-bouzas 靠一个词认不出（slug 里压根没有 maneiro）——编排器要给整个姓
    assert not probe_claims.leads_with_pair(["muchova", "maneiro"], "muchova-bouzas-bjk-cup-2026-sf")
    assert probe_claims.family_name("Bouzas Maneiro J.") == "Bouzas Maneiro"
    assert probe_claims.family_name("Ka. Pliskova") == "Pliskova"
    assert probe_claims.family_name("Alex de Minaur") == "de Minaur"
    # 放宽不许放到故事片上：「以姓结尾」要求前面那截全是小词
    for names, story in ((["keys", "zheng"], "comebacks-zheng-keys"),
                         (["eala", "zheng"], "zheng-us-open-outlook-zheng"),
                         (["zheng", "vekic"], "zheng-lanlana-hl-zheng-paris"),
                         (["keys", "zheng"], "backzheng-keys"),
                         (["minaur", "zverev"], "zverev-cup-minaur")):
        assert not probe_claims.leads_with_pair(names, story), (names, story)


def test_同一个slug重probe_上一趟的完成记录不许被抹掉():
    """review 复现（纯函数）：with_claim(run 1) → with_done → with_claim(run 2) →
    without_claim 得 None，40 分钟后 `_claim_priors` 返回 []——会话第一趟 probe 的目录只在
    它的分支上，编排器就把这一场再 probe 一遍。会话重 probe 很常见（第二趟带 --scorebox）。"""
    from datetime import datetime, timedelta, timezone
    t0 = datetime(2026, 9, 27, 6, 0, tzinfo=timezone.utc)
    slug = "wang-garland-singapore-2026-r2"

    def claim(doc, run, at):
        return probe_claims.with_claim(doc, key=KEY, url=YT, slug=slug, branch="claude/x",
                                       run_id=run, outdir=f"o/{run}", now=at)

    doc = claim(None, "1", t0)
    doc = probe_claims.with_done(doc, slug=slug, run_id="1", now=t0 + timedelta(minutes=5))
    doc = claim(doc, "2", t0 + timedelta(minutes=30))
    assert [(c["run_id"], bool(c.get("done_at"))) for c in doc["claims"]] == [("1", True), ("2", False)]

    def seen(d, minutes):
        return [p.slug for p in probe_claims._claim_priors(
            d, ref="HEAD", now=t0 + timedelta(minutes=minutes), days=3)]

    # 第二趟失败被摘：摘的是它自己那条，上一趟的完成记录还在
    released = probe_claims.without_claim(doc, slug=slug, run_id="2")
    assert released is not None and seen(released, 70) == [slug]
    # 第二趟被取消（摘不了也标不了）：它自己的那条作废，上一趟的照样挡
    assert seen(doc, 30 + probe_claims.CLAIM_STALE_MINUTES + 10) == [slug]
    # 第二趟跑完：它接替上一趟的完成记录（产物目录以最新这趟为准），不越积越多
    done2 = probe_claims.with_done(doc, slug=slug, run_id="2", now=t0 + timedelta(minutes=40))
    assert [(c["run_id"], c["outdir"]) for c in done2["claims"]] == [("2", "o/2")]
    # 别的 run 的 done／release 碰不到这一趟
    assert probe_claims.with_done(doc, slug=slug, run_id="9", now=t0) == doc
    assert probe_claims.without_claim(doc, slug=slug, run_id="9") == doc
    # 没给 run id（老调用）：摘这个 slug 还没完成的，完成的照样不动
    assert [c["run_id"] for c in probe_claims.without_claim(doc, slug=slug)["claims"]] == ["1"]


def test_同一个slug重probe_命令行按run_id摘和标(repo, monkeypatch):
    monkeypatch.chdir(repo.work)
    for run in ("1", "2"):
        assert probe_claims.main(["probe-step", "--url", YT, "--slug", "a-b",
                                  "--branch", "feature", "--run-id", run]) == 0
        if run == "1":
            assert probe_claims.main(["done", "--url", YT, "--slug", "a-b", "--run-id", "1"]) == 0
    assert probe_claims.main(["release", "--url", YT, "--slug", "a-b", "--run-id", "2"]) == 0
    (claim,) = _remote_claims(repo.remote)["claims"]
    assert claim["run_id"] == "1" and claim["done_at"], "第二趟失败把第一趟的完成记录一起摘了"


def test_作废的认领一次查找只报一次(repo, capsys):
    """review：编排器按工作区和 HEAD 各读一遍同一个认领文件，每条作废的认领印两遍。"""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    stale = now - timedelta(minutes=probe_claims.CLAIM_STALE_MINUTES + 30)
    _write(repo.seed, probe_claims.claim_path(KEY),
           {"claims": [{"slug": "ka.-shnaider", "claimed_at": _iso(stale), "outdir": "o"}]})
    _git(repo.seed, "add", "-A")
    _git(repo.seed, "commit", "-q", "-m", "stale claim")
    capsys.readouterr()
    got = probe_claims.find_priors(KEY, refs=["HEAD"], root=repo.seed, surnames=["pliskova", "shnaider"],
                                   now=now, cwd=repo.seed)
    assert all(p.kind != "claim" for p in got)
    out = capsys.readouterr().out
    assert out.count("ka.-shnaider 的认领开跑") == 1, out


def test_main上的probe第一次push之前先重放_不白撞一次认领那一笔(tmp_path):
    """review：开跑那一步刚往 main 推过认领，`提交产物` 的第一次 `git push origin HEAD:main`
    必然被拒，要白走一趟 fetch ＋ 重放 ＋ 5~14 秒的 sleep——编排器的 probe 全跑在 main 上。
    这里把那一步的 shell 原样拿来跑：远端 main 在检出之后多了一笔认领。"""
    step = next(s for s in _steps("match-reel.yml") if s.get("name") == "提交产物")
    script = step["run"]
    for k, v in {"${{ steps.paths.outputs.outdir }}": "output/2026-09-27/reel/a-b",
                 "${{ github.event.inputs.slug }}": "a-b",
                 "${{ github.event.inputs.mode }}": "probe",
                 "${{ github.ref_name }}": "main"}.items():
        script = script.replace(k, v)
    assert "${{" not in script
    remote = tmp_path / "r.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    seed = tmp_path / "s"
    _git(tmp_path, "init", "-q", "-b", "main", str(seed))
    _write(seed, "tools/check_staged_file_sizes.py", "")
    _write(seed, "data/keep.txt", "x")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", "seed")
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-q", "origin", "main")
    work = tmp_path / "w"
    _git(tmp_path, "clone", "-q", f"file://{remote}", str(work))
    # 开跑那一步（别的检出）往 main 推了认领
    _write(seed, probe_claims.claim_path(KEY), {"claims": [{"slug": "a-b"}]})
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", "probe: 认领源片")
    _git(seed, "push", "-q", "origin", "main")
    _write(work, "output/2026-09-27/reel/a-b/probe.json", {"url": YT})
    res = subprocess.run(["bash", "-eo", "pipefail", "-c", script], cwd=work, capture_output=True,
                         text=True, env={**os.environ, **git_blobs.BOT_ENV}, timeout=120)
    log = res.stdout + res.stderr
    assert res.returncode == 0, log
    assert "push 被拒" not in log, "第一次 push 还是撞在认领那一笔上：\n" + log
    files = _git(remote, "ls-tree", "-r", "--name-only", "main")
    assert probe_claims.claim_path(KEY) in files and "output/2026-09-27/reel/a-b/probe.json" in files
