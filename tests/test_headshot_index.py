"""数据图头像机械补齐（tools/headshot_index.py）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import headshot_index as hi  # noqa: E402


def _write_spec(d: Path, slug: str, names, shots):
    (d / f"{slug}.json").write_text(json.dumps({
        "cover": {"matchup": [{"name": names[0]}, {"name": names[1]}]},
        "stats": {"a": {"headshot": shots[0]}, "b": {"headshot": shots[1]}},
    }, ensure_ascii=False), encoding="utf-8")


def test_索引从已发spec推_规则和头像判据同一条(tmp_path):
    """a ↔ matchup[0]、b ↔ matchup[1]；双打列表不进表；换过版本取最常见。"""
    _write_spec(tmp_path, "x", ["甲", "乙"], ["h/a.png", "h/b.jpg"])
    _write_spec(tmp_path, "y", ["乙", "丙"], ["h/b.jpg", "h/c.jpg"])
    _write_spec(tmp_path, "z", ["乙", "丁"], ["h/b-old.jpg", ["h/d1.jpg", "h/d2.jpg"]])
    idx = hi.index_from_specs(tmp_path)
    assert idx == {"甲": "h/a.png", "乙": "h/b.jpg", "丙": "h/c.jpg"}


def test_真库的索引够大而且每个文件都在():
    idx = hi.index_from_specs()
    assert len(idx) >= 100, f"判据失效了：只推出 {len(idx)} 个名字"
    gone = [p for p in idx.values() if not (ROOT / p).is_file()]
    assert not gone, gone[:5]


def test_补头像_复用优先_WTA现抓兜底_ATP留空出声(tmp_path):
    (tmp_path / "h").mkdir()
    (tmp_path / "h" / "a.png").write_bytes(b"x")
    index = {"甲": "h/a.png"}
    calls = []

    def fetch(name_en):
        calls.append(name_en)
        if name_en == "Player B":
            return "assets/players/headshots/wta-1.jpg"
        raise SystemExit("WTA 球员库里搜不到")

    draft = {"cover": {"matchup": [{"name": "甲", "name_en": "Player A"},
                                   {"name": "乙", "name_en": "Player B"}]},
             "stats": {"a": {"pts_won": 1}, "b": {"pts_won": 2}}}
    notes = hi.resolve_headshots(draft, index=index, fetch_wta=fetch, root=tmp_path)
    assert draft["stats"]["a"]["headshot"] == "h/a.png"
    assert draft["stats"]["b"]["headshot"] == "assets/players/headshots/wta-1.jpg"
    assert calls == ["Player B"], "索引命中的不许再去网上抓"
    assert any("复用" in n for n in notes) and any("现抓" in n for n in notes)
    assert hi.missing_headshots(draft) == []
    # ATP：索引没有、WTA 搜不到 → 留空、出声、给手动命令
    draft = {"cover": {"matchup": [{"name": "丙", "name_en": "Player C"},
                                   {"name": "乙", "name_en": "Player B"}]},
             "stats": {"a": {"pts_won": 1}, "b": {"pts_won": 2, "headshot": "keep.jpg"}}}
    notes = hi.resolve_headshots(draft, index=index, fetch_wta=fetch, root=tmp_path)
    assert "headshot" not in draft["stats"]["a"] and hi.missing_headshots(draft) == ["a"]
    assert draft["stats"]["b"]["headshot"] == "keep.jpg", "已经写了的一个字不动"
    assert any("fetch_official_headshot.py atp" in n and "Player C" in n for n in notes)


def test_assemble在stats块之后补头像且失败不拖垮草稿():
    src = (ROOT / "tools" / "assemble_spec.py").read_text(encoding="utf-8")
    i_stats = src.index('draft["stats"] = {"a": blk["a"], "b": blk["b"]}')
    i_head = src.index("resolve_headshots(draft)")
    assert i_stats < i_head
