"""`tools/find_pending_draft.py`：会话开工前先看 pending 草稿，别把同一场球再 probe 一遍。"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location("find_pending_draft", ROOT / "tools" / "find_pending_draft.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _draft(a: str, b: str) -> dict:
    return {"cover": {"matchup": [{"name_en": a}, {"name_en": b}]}}


def _ago(hours: float) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_按两个姓认整词不认子串():
    t = _tool()
    d = _draft("Alexander Zverev", "Lorenzo Sonego")
    assert t.matches(d, "zverev-sonego", ["Zverev", "Sonego"], "")
    assert t.matches(d, "zverev-sonego", ["sonego", "ZVEREV"], ""), "大小写和顺序都不该影响"
    # 第一版的坑：`bublik-j.j.` 切出单字母 `j`，`j in "nothing"` 为真，随便两个姓都命中
    assert not t.matches(_draft("Alexander Bublik", "J.J. Wolf"), "bublik-j.j.", ["Nobody", "Nothing"], "")
    assert not t.matches(d, "zverev-sonego", ["Zverev", "Wolf"], ""), "两个姓要都对得上"
    assert t.matches(d, "zverev-sonego", [], "zver"), "--slug 按子串认"


def test_没找到要出声并且退出码是2(tmp_path, monkeypatch, capsys):
    t = _tool()
    monkeypatch.setattr(t, "PENDING", tmp_path)
    (tmp_path / "x-y.draft.json").write_text(json.dumps(_draft("A X", "B Y")), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["find_pending_draft", "--who", "Nobody,Nothing", "--no-refs"])
    assert t.main() == 2
    out = capsys.readouterr().out
    assert "没有匹配" in out and "扫了 1 份" in out, "「没找到」要说清扫了几份，别和「没查」长得一样"


def test_找到了要把probe目录和卡点一起打出来(tmp_path, monkeypatch, capsys):
    t = _tool()
    monkeypatch.setattr(t, "PENDING", tmp_path)
    monkeypatch.setattr(t, "probe_dirs", lambda slug: [ROOT / "output" / "2026-09-02" / "reel" / slug])
    monkeypatch.setattr(t, "waiting", lambda d: ["赛果源缺 round，不能猜顶栏/比分板"])
    d = _draft("Alexander Zverev", "Lorenzo Sonego")
    d.update({"slug": "zverev-sonego", "source_url": "https://youtu.be/abc", "stats": {"a": {}},
              "_match": {"status": "result_verified", "winner": "兹维列夫", "winner_result": "6-4 3-6 6-3", "loser": "索内戈"},
              "_production": {"received_at": _ago(2), "event": "US Open"}})
    (tmp_path / "zverev-sonego.draft.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["find_pending_draft", "--who", "Zverev,Sonego", "--no-refs"])
    assert t.main() == 0
    out = capsys.readouterr().out
    for needle in ("probe ✅", "output/2026-09-02/reel/zverev-sonego", "result_verified", "6-4 3-6 6-3",
                   "统计 ✅", "缺 round", "youtu.be/abc"):
        assert needle in out, needle


# ---------------------------------------------------------------------------
# P6（2026-09-27）：工作区里的 pending 只是三处里的一处——还要翻 origin/main 和
# 最近动过的 origin/* 分支，并把各处的封面按像素排。来路：putintseva-bencic 的
# 草稿里早就躺着一张 Getty 本场实拍（56e113c3），会话 22 分钟后的正式 spec
# （2fa95f43）删了那份草稿、用了一张小得多的特写，重渲一趟才换回来。


def _git(cwd, *args):
    import os
    import subprocess
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    import git_blobs  # noqa: PLC0415
    res = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                         env={**os.environ, **git_blobs.BOT_ENV})
    assert res.returncode == 0, res.stderr
    return res.stdout


def _png(path, w, h):
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (w, h), (40, 90, 40)).save(path)


def _spec(slug, names, image, url="https://www.youtube.com/watch?v=FCgBoA8IDOc", fs=""):
    d = {"slug": slug, "source_url": url,
         "cover": {"matchup": [{"name_en": n} for n in names], "portrait": {"image": image}}}
    if fs:
        d["_match"] = {"flashscore_id": fs}
    return json.dumps(d)


def _origin_world(tmp_path):
    """一个「远端」：main 上有自动链的草稿（大封面），另一条分支上有一份只活在
    PR 里的正式 spec；本地仓库 fetch 过它们，工作区里是会话自己那份（小封面）。"""
    remote = tmp_path / "remote"
    _git(tmp_path, "init", "-q", "-b", "main", str(remote))
    (remote / "specs" / "reels" / "pending").mkdir(parents=True)
    (remote / "specs/reels/pending/putintseva-bencic.draft.json").write_text(
        _spec("putintseva-bencic", ["Yulia Putintseva", "Belinda Bencic"], "assets/reel/big.jpg"), encoding="utf-8")
    _png(remote / "assets/reel/big.jpg", 1600, 1200)
    # 两个姓都带着、却不是这一场的双打——不许被认成同一场
    (remote / "specs/reels/putintseva-x-doubles.json").write_text(
        _spec("putintseva-x-doubles", ["Yulia Putintseva / A B", "Belinda Bencic / C D"],
              "assets/reel/huge.jpg", url="https://youtu.be/zzzzzzzzzzz"), encoding="utf-8")
    _png(remote / "assets/reel/huge.jpg", 4000, 3000)
    _git(remote, "add", "-A")
    _git(remote, "commit", "-q", "-m", "auto draft")
    _git(remote, "switch", "-q", "-c", "claude/pr-only")
    (remote / "specs/reels/swiatek-bouzkova-us-open-2026-r3.json").write_text(
        _spec("swiatek-bouzkova-us-open-2026-r3", ["Iga Swiatek", "Marie Bouzkova"], "assets/reel/sb.jpg",
              url="https://youtu.be/0x6WoB4W8bI", fs="AbCd1234"), encoding="utf-8")
    _png(remote / "assets/reel/sb.jpg", 800, 600)
    _git(remote, "add", "-A")
    _git(remote, "commit", "-q", "-m", "pr only")
    _git(remote, "switch", "-q", "main")
    local = tmp_path / "local"
    _git(tmp_path, "clone", "-q", str(remote), str(local))
    (local / "specs/reels/putintseva-bencic-us-open-2026-r1.json").write_text(
        _spec("putintseva-bencic-us-open-2026-r1", ["Yulia Putintseva", "Belinda Bencic"], "assets/reel/small.jpg"),
        encoding="utf-8")
    _png(local / "assets/reel/small.jpg", 600, 800)
    return local


def test_翻origin上的草稿_封面比工作区spec用的那张大就喊出来(tmp_path, monkeypatch, capsys):
    t = _tool()
    local = _origin_world(tmp_path)
    monkeypatch.setattr(t, "ROOT", local)
    refs = t.recent_refs(cwd=local)
    assert refs[0] == "refs/remotes/origin/main" and "refs/remotes/origin/claude/pr-only" in refs
    hits = t.ref_hits(refs, ["Putintseva", "Bencic"], set(), set(), cwd=local)
    assert [h.path for h in hits] == ["specs/reels/pending/putintseva-bencic.draft.json"], (
        "双打那份两个姓都带着，却不是这一场")
    assert hits[0].cover_px == (1600, 1200)
    t.report_refs(hits, t.local_cover(["Putintseva", "Bencic"], set(), set()))
    out = capsys.readouterr().out
    assert "::warning::有一张更大的封面" in out and "assets/reel/big.jpg 1600×1200" in out
    assert "assets/reel/small.jpg（600×800）" in out


def test_只活在PR分支上的spec按视频id和flashscore_id都认得出(tmp_path, monkeypatch):
    t = _tool()
    local = _origin_world(tmp_path)
    monkeypatch.setattr(t, "ROOT", local)
    refs = t.recent_refs(cwd=local)
    by_url = t.ref_hits(refs, [], {"0x6WoB4W8bI"}, set(), cwd=local)
    assert [(h.path, h.refs, h.by) for h in by_url] == [(
        "specs/reels/swiatek-bouzkova-us-open-2026-r3.json",
        ["refs/remotes/origin/claude/pr-only"], "视频 id")], "那份 spec 只在 PR 分支上——工作区和 main 都没有"
    by_fs = t.ref_hits(refs, [], set(), {"AbCd1234"}, cwd=local)
    assert [h.by for h in by_fs] == ["flashscore id"]


def test_fetch挂了要说可能是旧的_照样按本地已有的origin查(tmp_path, monkeypatch, capsys):
    t = _tool()
    local = _origin_world(tmp_path)
    monkeypatch.setattr(t, "ROOT", local)
    monkeypatch.setattr(t, "PENDING", tmp_path / "none")
    _git(local, "remote", "set-url", "origin", str(tmp_path / "gone"))
    monkeypatch.setattr("sys.argv", ["find_pending_draft", "--url", "https://youtu.be/0x6WoB4W8bI"])
    assert t.main() == 0
    out = capsys.readouterr().out
    assert "fetch origin 失败" in out and "swiatek-bouzkova-us-open-2026-r3" in out


def _commit(repo, msg, when=None):
    import os
    env = {}
    if when:
        env = {"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
    import subprocess
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    import git_blobs  # noqa: PLC0415
    _git(repo, "add", "-A")
    res = subprocess.run(["git", "commit", "-q", "-m", msg], cwd=repo, capture_output=True, text=True,
                         env={**os.environ, **git_blobs.BOT_ENV, **env})
    assert res.returncode == 0, res.stderr


def _exit_world(tmp_path):
    """远端 main 上只有两人**上一次交手**的老 spec（半年前的提交）；会话自己的分支
    `claude/mine` 上有它刚推上去的那份。工作区停在 `claude/mine`。"""
    remote = tmp_path / "remote"
    _git(tmp_path, "init", "-q", "-b", "main", str(remote))
    (remote / "specs/reels").mkdir(parents=True)
    (remote / "specs/reels/putintseva-bencic-2026-03.json").write_text(
        _spec("putintseva-bencic-2026-03", ["Yulia Putintseva", "Belinda Bencic"], "assets/reel/old.jpg",
              url="https://youtu.be/oldoldoldol"), encoding="utf-8")
    _commit(remote, "old meeting", when="2026-03-01T00:00:00Z")
    _git(remote, "switch", "-q", "-c", "claude/mine")
    (remote / "specs/reels/putintseva-bencic-us-open-2026-r1.json").write_text(
        _spec("putintseva-bencic-us-open-2026-r1", ["Yulia Putintseva", "Belinda Bencic"], "assets/reel/mine.jpg"),
        encoding="utf-8")
    _commit(remote, "mine")
    _git(remote, "switch", "-q", "main")
    local = tmp_path / "local"
    _git(tmp_path, "clone", "-q", str(remote), str(local))
    _git(local, "switch", "-q", "claude/mine")
    return local


def test_退出码_老交手和自己分支上的那份只列不算找到(tmp_path, monkeypatch, capsys):
    """review：`found += _refs_section(...)` 只要 origin/* 上有任何一份就返回 0——包括
    半年前那一场和会话自己刚推上去的那份；而 CLAUDE.md 说退出码 2 是「没有」。"""
    t = _tool()
    local = _exit_world(tmp_path)
    monkeypatch.setattr(t, "ROOT", local)
    monkeypatch.setattr(t, "PENDING", tmp_path / "none")
    monkeypatch.setattr("sys.argv", ["find_pending_draft", "--who", "Putintseva,Bencic", "--no-fetch"])
    assert t.main() == 2, "只有老交手和自己分支上的那份：没有能接着用的"
    out = capsys.readouterr().out
    assert "putintseva-bencic-2026-03.json" in out and "多半是两人上一次交手" in out, "照样要列出来"
    assert "putintseva-bencic-us-open-2026-r1.json" in out and "当前分支自己推上去的" in out
    # 同一份 spec 换个人来查（不在那条分支上）：它就是别人做的，算找到
    _git(local, "switch", "-q", "-c", "claude/other")
    monkeypatch.setattr("sys.argv", ["find_pending_draft", "--who", "Putintseva,Bencic", "--no-fetch"])
    assert t.main() == 0


def test_网球有故事的spec不拿来比封面(tmp_path, monkeypatch, capsys):
    """matchup 正好是这两个人的故事片，封面讲的是另一件事——不许喊「更大的封面」。"""
    t = _tool()
    local = _origin_world(tmp_path)
    remote = tmp_path / "remote"
    (remote / "specs/reels/putintseva-bencic-rivalry.json").write_text(json.dumps({
        "slug": "putintseva-bencic-rivalry",
        "cover": {"eyebrow": "网球有故事", "portrait": {"image": "assets/reel/story.jpg"},
                  "matchup": [{"name_en": "Yulia Putintseva"}, {"name_en": "Belinda Bencic"}]}}), encoding="utf-8")
    _png(remote / "assets/reel/story.jpg", 5000, 4000)
    _git(remote, "add", "-A")
    _git(remote, "commit", "-q", "-m", "story")
    _git(local, "fetch", "-q", "origin")
    monkeypatch.setattr(t, "ROOT", local)
    hits = t.ref_hits(t.recent_refs(cwd=local), ["Putintseva", "Bencic"], set(), set(), cwd=local)
    story = [h for h in hits if h.slug == "putintseva-bencic-rivalry"]
    assert story and story[0].column == "网球有故事"
    t.report_refs(hits, t.local_cover(["Putintseva", "Bencic"], set(), set()))
    out = capsys.readouterr().out
    (warn,) = [line for line in out.splitlines() if line.startswith("::warning::有一张更大的封面")]
    assert "story.jpg" not in warn, "故事片的 5000×4000 被当成同一场更大的封面"
    assert "assets/reel/big.jpg 1600×1200" in warn, "赛场之上草稿里那张更大的照样要喊"
    assert "网球有故事，不是赛场之上" in out


def test_pending里的老草稿只列不算找到_退出码2(tmp_path, monkeypatch, capsys):
    """review 复现：`--who Swiatek,Zheng` 退出码 0，靠的是 9/07 那份
    `swiatek-zheng.draft.json`——它自己的 promote 卡点写着「自动草稿已超过 20 小时」，
    同一份输出里 origin/* 那一段也说「都不算能接着用的」。pending 里躺着一百多份，
    大半是几周前的，同两个人再交手就撞上。和 origin/* 那一半同一把尺子：`REF_DAYS` 天。"""
    t = _tool()
    monkeypatch.setattr(t, "PENDING", tmp_path)
    monkeypatch.setattr(t, "probe_dirs", lambda slug: [])
    monkeypatch.setattr(t, "waiting", lambda d: ["自动草稿已超过 20 小时，不再生产上一比赛日内容"])
    old = _draft("Iga Swiatek", "Qinwen Zheng")
    old["_production"] = {"received_at": _ago(24 * (t.REF_DAYS + 17))}
    (tmp_path / "swiatek-zheng.draft.json").write_text(json.dumps(old), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["find_pending_draft", "--who", "Swiatek,Zheng", "--no-refs"])
    assert t.main() == 2, "只有几周前那份老草稿：没有能接着用的"
    out = capsys.readouterr().out
    assert "swiatek-zheng.draft.json" in out, "老草稿照样要列出来"
    assert "老草稿" in out and "不算能接着用的" in out
    assert "没有匹配" not in out, "匹配到了，只是老——别说成「没有匹配」"
    # 同一个文件换成这一个比赛日的：算找到
    old["_production"] = {"received_at": _ago(3)}
    (tmp_path / "swiatek-zheng.draft.json").write_text(json.dumps(old), encoding="utf-8")
    assert t.main() == 0
    # 没有 received_at（手写的草稿）：按 HEAD 上最近一次提交认；没提交过的算刚写的
    del old["_production"]
    (tmp_path / "swiatek-zheng.draft.json").write_text(json.dumps(old), encoding="utf-8")
    assert t.main() == 0
