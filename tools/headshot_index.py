#!/usr/bin/env python3
"""数据统计图要的圆形头像（`stats.a/b.headshot`）——**机械地补上**，别等人。

来路（2026-09-03 全库 review 顺手量的）：`specs/reels/pending/` 里 49 份自动草稿
**全部**带 `stats`、**没有一份**带 `headshot`。而 `render_stat_card.build` 缺
headshot 是 SystemExit，`build_match_reel.render` 末尾那次「渲给推送用」的数据图
不兜这个错——也就是说**任何一份自动草稿一旦转正、渲到最后一步都会红**。唯一发
出去的那条自动片（medvedev-damm）是人手补的头像。自动链里没有任何工具写过这个
字段（`grep headshot tools/assemble_spec.py tools/promote_reel_draft.py` 零命中）。

两条路，按顺序：

1. **已发 spec 里认过的人直接复用**——`index_from_specs()` 从 `specs/reels/*.json`
   推「中文名 → 头像文件」。⚠️ 推导规则和
   `tests/test_match_reel.py::test_数据图的头像和matchup里的名字必须是同一个人`
   **同一条**（`stats.a` ↔ `cover.matchup[0]`、`b` ↔ `[1]`，双打列表不进表）：
   那条判据保证同一张脸只挂一个名，所以这张索引反过来查也是唯一的。
2. **WTA 按名字现抓**（`fetch_official_headshot.fetch_wta`，api.wtatennis.com 的
   按姓搜索接口 + 官方 blob）。ATP 没有按名字的接口、要事先知道 ID 和一个能连通
   的赛事镜像域名——机械补不了，**留空并出声**，promote 那头的闸会把草稿留在
   waiting，报错正文里写着手动那条命令。

⚠️ 「补不上」和「没补」在产物上长得一模一样（都是没有 headshot 键），所以
`resolve_headshots` 每一侧都要在 notes 里说一句它走了哪条路。
"""
from __future__ import annotations

import collections
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
FORMAL = ROOT / "specs" / "reels"


def index_from_specs(specs_dir: Path = FORMAL) -> dict[str, str]:
    """中文名 → 头像相对路径（仓库根起），从已发 spec 推，不维护名单。

    同一个名字在多条 spec 里挂过不同文件（换过一版头像）时取最常见的那一份。
    """
    seen: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for path in sorted(Path(specs_dir).glob("*.json")):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        stats = spec.get("stats") or {}
        names = [m.get("name") for m in ((spec.get("cover") or {}).get("matchup") or [])]
        if len(names) != 2:
            continue
        for key, idx in (("a", 0), ("b", 1)):
            shot = (stats.get(key) or {}).get("headshot")
            if isinstance(shot, list) or not shot or not names[idx]:
                continue
            seen[str(names[idx]).strip()][str(shot)] += 1
    return {name: files.most_common(1)[0][0] for name, files in seen.items()}


def _default_fetch_wta(name_en: str) -> str:
    # 单元测试一律不许摸网（tests/conftest.py 的 autouse fixture 把它设成 0）——
    # 和 TENNISLIVE_SLAM_FEED 同一个形状；抓不到走「留空出声」那条路。
    if os.environ.get("TENNISLIVE_HEADSHOT_FETCH") == "0":
        raise RuntimeError("TENNISLIVE_HEADSHOT_FETCH=0：这台机器不许现抓头像")
    from fetch_official_headshot import fetch_wta  # noqa: PLC0415
    dest = fetch_wta(name_en)
    return dest.resolve().relative_to(ROOT).as_posix()


def resolve_headshots(draft: dict, *, index: dict[str, str] | None = None,
                      fetch_wta=None, root: Path = ROOT) -> list[str]:
    """给 `draft["stats"]["a"/"b"]` 补 `headshot`，返回 notes（每一侧一句）。

    只补缺的；已经写了的一个字不动。索引查不到就试 WTA 现抓；再不成留空出声。
    """
    stats = draft.get("stats") or {}
    matchup = ((draft.get("cover") or {}).get("matchup") or [])
    if not stats or len(matchup) != 2:
        return []
    if index is None:
        index = index_from_specs()
    fetch = fetch_wta or _default_fetch_wta
    notes: list[str] = []
    for key, idx in (("a", 0), ("b", 1)):
        side = stats.get(key)
        if not isinstance(side, dict) or side.get("headshot"):
            continue
        meta = matchup[idx] or {}
        name = str(meta.get("name") or "").strip()
        name_en = str(meta.get("name_en") or "").strip()
        hit = index.get(name)
        if hit and (root / hit).is_file():
            side["headshot"] = hit
            notes.append(f"头像 stats.{key}（{name}）：已发 spec 里认过，复用 {hit}")
            continue
        if not name_en:
            notes.append(f"⚠️ 头像 stats.{key}（{name}）：没有英文名，WTA 按名字抓不了")
            continue
        try:
            path = fetch(name_en)
        except (SystemExit, Exception) as exc:  # noqa: BLE001 —— 抓不到不拖垮草稿
            notes.append(
                f"⚠️ 头像 stats.{key}（{name} / {name_en}）：索引里没有，WTA 按名字也"
                f"没抓到（{type(exc).__name__}: {str(exc)[:80]}）。ATP 球员要手动："
                f"PYTHONPATH=src python3 tools/fetch_official_headshot.py atp "
                f"\"{name_en}\" --id <ID> --via https://www.mubadaladcopen.com，"
                f"再把路径写进 stats.{key}.headshot")
            continue
        side["headshot"] = str(path)
        notes.append(f"头像 stats.{key}（{name}）：WTA 官方现抓 {path}")
    return notes


def missing_headshots(draft: dict) -> list[str]:
    """哪几侧的 `stats.*.headshot` 还空着（promote 的闸读这个）。"""
    stats = draft.get("stats") or {}
    return [key for key in ("a", "b")
            if isinstance(stats.get(key), dict) and not stats[key].get("headshot")]


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="给一份草稿补数据图头像")
    ap.add_argument("draft", type=Path)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    d = json.loads(args.draft.read_text(encoding="utf-8"))
    for line in resolve_headshots(d):
        print(line)
    if args.write:
        args.draft.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
