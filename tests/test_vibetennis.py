"""vibetennis 栏目：登记、spec 合同、标题规则、发布门禁。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "vibetennis"))
sys.path.insert(0, str(ROOT / "tools"))

import importlib  # noqa: E402

# 仓库内的模块（tools/vibetennis/），不是第三方包——按名字现取，免得被当成依赖
common = importlib.import_module("common")
publish_gate = importlib.import_module("publish_gate")

SPECS = sorted((ROOT / "specs/vibetennis").glob("*.json"))


def test_栏目登记在栏目文档里():
    doc = (ROOT / "docs/columns.md").read_text(encoding="utf-8")
    assert "| **vibetennis** |" in doc, "栏目表里没有 vibetennis 那一行"
    assert (ROOT / "docs/vibetennis.md").is_file()
    assert (ROOT / "skills/vibetennis-production/SKILL.md").is_file()


def test_至少有一条spec_而且每条都自洽():
    assert SPECS, "specs/vibetennis/ 是空的"
    for path in SPECS:
        spec = json.loads(path.read_text(encoding="utf-8"))
        assert common.spec_problems(spec, path.stem) == [], path.name
        assert path.with_suffix(".xhs.txt").is_file(), f"{path.name} 缺文案"
        cover = spec["cover"]
        src = cover["script"] if cover.get("layout") == "custom" else cover["portrait"]["image"]
        assert (ROOT / src).is_file(), f"{path.name} 的封面来源 {src} 不在"


def test_spec合同会拦住竖屏和空出处():
    spec = json.loads(SPECS[0].read_text(encoding="utf-8"))
    bad = json.loads(json.dumps(spec))
    bad["film"]["canvas"] = [1080, 1440]
    bad["editorial"]["sources"] = []
    problems = common.spec_problems(bad, spec["slug"])
    assert any("16:9" in p for p in problems)
    assert any("出处" in p for p in problems)


def test_标题规则认得这个栏目():
    sys.path.insert(0, str(ROOT / "src"))
    from tennislive.render.copy_title import (  # noqa: PLC0415
        copy_title, make_copy_title, validate_copy_title)

    # 所有者 2026-10-31：vibetennis 按集数命名 EPNN.vibetennis|主题，不写日期
    assert make_copy_title("10.30", "vibetennis", "现场更快", episode=1) == "EP01.vibetennis|现场更快"
    assert make_copy_title("10.31", "vibetennis", "上旋下坠",
                           slug="vibetennis-topspin-magnus-2026") == "EP03.vibetennis|上旋下坠"
    assert copy_title("EP02.vibetennis｜电子司线") == "EP02.vibetennis|电子司线"
    assert validate_copy_title("EP02.vibetennis|电子司线", require_prefix=True)
    with pytest.raises(SystemExit):
        make_copy_title("10.30", "vibetennis", "网球为什么现场更快", episode=1)   # 超 20 字要报错，不许截断
    with pytest.raises(SystemExit):
        validate_copy_title("10.30vibetennis|现场更快", require_prefix=True)   # 旧的日期格式不再认
    with pytest.raises(SystemExit):
        make_copy_title("10.30", "vibetennis", "现场更快", slug="vibetennis-not-registered")
    # 别的栏目照旧是日期
    assert make_copy_title("10.30", "赛场之上", "郑钦文胜").startswith("10.30赛场之上|")


def test_集数表连续且每条spec都登记了():
    table = json.loads((ROOT / "data/vibetennis_episodes.json").read_text(encoding="utf-8"))
    episodes = {k: v for k, v in table.items() if not k.startswith("_")}
    assert sorted(episodes.values()) == list(range(1, len(episodes) + 1))
    assert {p.stem for p in SPECS} <= set(episodes)


def test_每条spec的发布标题和正文都过得了推送那几道闸():
    push_reel = importlib.import_module("push_reel")

    for path in SPECS:
        out = Path("output/2026-10-30/vibetennis") / path.stem
        column, title, body = push_reel.prepare_copy(path.with_suffix(".xhs.txt"), out)
        assert column == "vibetennis"
        assert title.startswith("EP") and ".vibetennis|" in title and len(title) <= 20
        assert body.strip()
        # 所有者 2026-10-31：这一栏必带 #vibe知识大赏，不带两个中国赛季活动 tag
        assert "#vibe知识大赏" in body and "#网球时差" in body
        assert "#网球中国赛季来了" not in body and "#网球时间到" not in body


def test_门禁只认这一栏的路径形状():
    assert common.RENDER_JSON.match("output/2026-10-30/vibetennis/x-y/render.json")
    assert not common.RENDER_JSON.match("output/2026-10-30/reel/x-y/render.json")


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def test_没有质检凭证就不发(tmp_path):
    repo = _repo(tmp_path)
    slug = "demo-ep"
    out = repo / "output/2026-10-30/vibetennis" / slug
    out.mkdir(parents=True)
    (out / "render.json").write_text("{}", encoding="utf-8")
    (repo / "specs/vibetennis").mkdir(parents=True)
    (repo / f"specs/vibetennis/{slug}.json").write_text('{"push":{"auto":true}}', encoding="utf-8")
    (repo / f"specs/vibetennis/{slug}.xhs.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    with pytest.raises(publish_gate.Skip, match="qc_attestation"):
        publish_gate.wants_auto_push(repo, slug, out.relative_to(repo))


def test_一趟两条一条都不发(tmp_path, monkeypatch):
    monkeypatch.setattr(publish_gate, "wants_auto_push", lambda *a: None)
    with pytest.raises(SystemExit):
        publish_gate.pick(["output/2026-10-30/vibetennis/a/render.json",
                           "output/2026-10-30/vibetennis/b/render.json"], tmp_path)


def _cover_revision_repo(tmp_path: Path, *, parent="a" * 32, extra_rows=()):
    """一条已推过、准备只换封面重推的最小仓库。"""
    import hashlib
    repo = _repo(tmp_path)
    slug = "demo-ep"
    out = repo / "output/2026-10-30/vibetennis" / slug
    out.mkdir(parents=True)
    sha = lambda b: hashlib.sha256(b).hexdigest()  # noqa: E731
    film = "f" * 64
    (out / "poster.jpg").write_bytes(b"new-cover")
    archived = {"at": "2026-10-30T14:38:29Z", "run": "https://x/runs/1",
                "pushplus_receipt": "a" * 32}
    raw = (json.dumps(archived) + "\n").encode()
    (out / "pushed_original.json").write_bytes(raw)
    rows = [{"key": f"pushplus:vibetennis:{slug}:{film}", "fingerprint": film, "status": "sent",
             **archived}, *extra_rows]
    led = repo / "data/vibetennis_publish_ledger" / f"{slug}.json"
    led.parent.mkdir(parents=True)
    led.write_text(json.dumps({"slug": slug, "channel": "pushplus", "attempts": rows}), encoding="utf-8")
    manifest = {"version": 1, "kind": "cover-correction", "slug": slug, "revision_id": "cover-v2",
                "film_sha256": film, "poster_sha256": sha(b"new-cover"), "parent_receipt": parent,
                "previous_pushed": {"path": "pushed_original.json", "sha256": sha(raw)}}
    (out / "publication_revision.json").write_text(json.dumps(manifest), encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    return repo, slug, out.relative_to(repo), film


def test_只换封面的修订单用海报指纹记账(tmp_path):
    repo, slug, out, film = _cover_revision_repo(tmp_path)
    fp = publish_gate.revision_fingerprint(repo, slug, out, film)
    assert fp.startswith("cover-revision:") and fp != film


def test_修订单的父回执不是最近一次已发就不发(tmp_path):
    repo, slug, out, film = _cover_revision_repo(tmp_path, parent="b" * 32)
    with pytest.raises(publish_gate.Skip, match="parent_receipt|归档回执"):
        publish_gate.revision_fingerprint(repo, slug, out, film)


def test_同一张封面发过了就不再发(tmp_path):
    import hashlib
    poster_fp = "cover-revision:" + hashlib.sha256(b"new-cover").hexdigest()
    later = {"key": f"pushplus:vibetennis:demo-ep:{poster_fp}", "fingerprint": poster_fp,
             "status": "sent", "at": "2026-10-30T16:00:00Z", "run": "https://x/runs/2",
             "pushplus_receipt": "c" * 32}
    repo, slug, out, film = _cover_revision_repo(tmp_path, extra_rows=[later])
    with pytest.raises(publish_gate.Skip, match="parent_receipt"):
        publish_gate.revision_fingerprint(repo, slug, out, film)


def test_修订单不许换成片(tmp_path):
    repo, slug, out, _ = _cover_revision_repo(tmp_path)
    with pytest.raises(publish_gate.Skip, match="成片"):
        publish_gate.revision_fingerprint(repo, slug, out, "e" * 64)


def test_推送按钮写横版_别的栏目不变():
    push = importlib.import_module("push")
    from tennislive.render import push_style as ps
    html = f'<p>x</p><a href="u">{ps.VIDEO_BUTTON_TEXT}</a>'
    out = push.landscape_button(html)
    assert "▶ 打开横版成片" in out and "竖版" not in out
    assert ps.VIDEO_BUTTON_TEXT == "▶ 打开竖版成片", "共用模板（其他栏目）的按钮文字不该被改"
    with pytest.raises(SystemExit):
        push.landscape_button("<p>没有按钮</p>")
