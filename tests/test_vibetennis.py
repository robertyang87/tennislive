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

import common  # noqa: E402
import publish_gate  # noqa: E402

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
        image = ROOT / spec["cover"]["portrait"]["image"]
        assert image.is_file(), f"{path.name} 的封面素材 {image} 不在"


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
    from tennislive.render.copy_title import make_copy_title  # noqa: PLC0415

    assert make_copy_title("10.30", "vibetennis", "现场更快") == "10.30vibetennis|现场更快"
    with pytest.raises(SystemExit):
        make_copy_title("10.30", "vibetennis", "网球为什么现场更快")   # 超 20 字要报错，不许截断


def test_每条spec的发布标题和正文都过得了推送那几道闸():
    import push_reel  # noqa: PLC0415

    for path in SPECS:
        out = Path("output/2026-10-30/vibetennis") / path.stem
        column, title, body = push_reel.prepare_copy(path.with_suffix(".xhs.txt"), out)
        assert column == "vibetennis"
        assert title.startswith("10.30vibetennis|") and len(title) <= 20
        assert body.strip()


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
