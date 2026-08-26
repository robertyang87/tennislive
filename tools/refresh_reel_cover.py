#!/usr/bin/env python3
"""为 pending reel 重试同场官方高清封面；只在真正找到时改草稿。

赛后图片常比集锦晚几十分钟。probe 当下没图不是永久失败；本工具让定时 ready
工作流继续查 Tennis TV/WTA 官方来源。查不到返回 0 且不改文件，找到才写入，
避免每十分钟制造一笔“仍然没图”的空提交。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from assemble_spec import _surname, fetch_tennistv_cover  # noqa: E402


def refresh(draft: dict) -> tuple[dict, str]:
    portrait = (draft.get("cover") or {}).get("portrait") or {}
    if portrait.get("image") and Path(str(portrait["image"])).is_file():
        return draft, "已有封面"
    slug = str(draft.get("slug") or "").strip()
    event = str((draft.get("_production") or {}).get("event") or "").strip()
    source_url = str(draft.get("source_url") or "").strip()
    pair = (draft.get("cover") or {}).get("matchup") or []
    english = [str(p.get("name_en") or "").strip() for p in pair]
    if not slug or len(english) != 2 or not all(english):
        return draft, "草稿缺 slug/两位英文名"
    out = ROOT / "assets" / "reel" / f"{slug}-cover.jpg"

    if "tennistv.com" in urlparse(source_url).netloc.casefold():
        try:
            note = fetch_tennistv_cover(source_url, event, out)
            draft.setdefault("cover", {})["portrait"] = {
                "image": str(out.relative_to(ROOT)),
                "_portrait_why": "Tennis TV 本场官方页面关联的 ATP Media 高清图",
            }
            return draft, note
        except Exception:  # noqa: BLE001 —— 继续试 WTA 官方来源
            pass

    try:
        import requests
        from fetch_match_pbp import find_match
        from fetch_wta_cover_photo import fetch_cover

        today = date.today()
        session = requests.Session()
        event_id, year, match_id, _ = find_match(
            session, [_surname(name) for name in english],
            today - timedelta(days=7), today + timedelta(days=1))
        city = event.casefold().replace(" ", "-")
        code, note = fetch_cover(
            str(event_id), str(year), city, match_id,
            [_surname(name) for name in english], out, today)
        if code != 0:
            return draft, note
        draft.setdefault("cover", {})["portrait"] = {
            "image": str(out.relative_to(ROOT)),
            "_portrait_why": "WTA 官方赛后稿/集锦头图，定时自动补齐",
        }
        return draft, note
    except (Exception, SystemExit) as exc:  # noqa: BLE001
        return draft, f"官方封面尚未出现（{type(exc).__name__}: {exc}）"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--draft", required=True, type=Path)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    before = args.draft.read_text(encoding="utf-8")
    draft, note = refresh(json.loads(before))
    after = json.dumps(draft, ensure_ascii=False, indent=2) + "\n"
    if args.write and after != before and ((draft.get("cover") or {}).get("portrait") or {}).get(
            "image"):
        args.draft.write_text(after, encoding="utf-8")
        print(f"[found] {note}")
    else:
        print(f"[waiting] {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
