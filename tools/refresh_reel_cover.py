#!/usr/bin/env python3
"""为 pending reel 重试同场官方高清封面；只在真正找到时改草稿。

赛后图片常比集锦晚几十分钟。probe 当下没图不是永久失败；本工具让定时 ready
工作流继续查 Tennis TV/WTA 官方来源。查不到返回 0 且不改文件，找到才写入，
避免每十分钟制造一笔“仍然没图”的空提交。

⭐⭐ 2026-09-28 起**第一档是 ATP Media／WTA 照片接口**（`cover_upgrade.pick_for_draft`，和 O4 同一套
机器闸：EXIF 拍摄时刻绑场次、全名、两人同框、发布限制、铺满不放大、认人、睁眼、钩子带）。封面时效实测：
10 条抽帧首推里 6 条，首推之前这两个接口里就有主角对的官方原图。每一班（10 分钟）都再查一遍，直到有；
**查不到从来不拦**——照原来那两条路（Tennis TV 页头图、WTA 赛后稿）接着走，和改之前一样。

已经有封面的只在一种情况下换：**这张封面被视觉审核判过、没过、而且不会重审**（`_visual_evidence`
的 `cover_image` 就是它、`status` 不是 pass、`retryable` 是 false）——草稿卡死在这张图上，换一张只会解开，
不会让一条本来要走的片子晚走。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from assemble_spec import _surname, fetch_tennistv_cover  # noqa: E402


def stuck_on_cover(draft: dict) -> bool:
    """草稿是不是**卡死在现在这张封面上**：视觉审核审过的就是它、没过、不会重审。"""
    portrait = (draft.get("cover") or {}).get("portrait") or {}
    visual = draft.get("_visual_evidence") if isinstance(draft.get("_visual_evidence"), dict) else {}
    return bool(portrait.get("image") and visual
                and visual.get("cover_image") == portrait.get("image")
                and visual.get("status") != "pass" and visual.get("visual_status") != "error"
                and visual.get("retryable") is False)


def official_api_cover(draft: dict, *, now: datetime | None = None, pick=None,
                       write: bool = True) -> tuple[dict, str] | None:
    """照片接口那两档（`cover_upgrade.pick_for_draft`）：全过闸就把**原图字节**写成
    `assets/reel/<slug>-cover.jpg`（不重编码，「封面图一律存原图」）、portrait 换成它；没有返回 None。
    `write=False`（不带 `--write` 的试跑）：只报，不写图。"""
    import cover_upgrade  # noqa: PLC0415

    slug = str(draft.get("slug") or "").strip()
    if not slug:
        return None
    got = (pick or cover_upgrade.pick_for_draft)(draft, now or datetime.now(timezone.utc))
    for line in got.get("report") or []:
        print(line)
    chosen = got.get("chosen")
    if not chosen:
        return None
    blob = chosen["blob"]
    if blob[:3] != b"\xff\xd8\xff":
        print(f"[照片接口] {slug} 挑中的不是 JPEG，不重编码也存不成 -cover.jpg，这一班不用")
        return None
    out = ROOT / "assets" / "reel" / f"{slug}-cover.jpg"
    if write:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blob)
    portrait = {"image": str(out.relative_to(ROOT)), **(got.get("portrait") or {})}
    portrait["_portrait_why"] = str(portrait.pop("_why", "")) or "照片接口官方原图"
    draft.setdefault("cover", {})["portrait"] = portrait
    c = chosen["candidate"]
    return draft, f"照片接口官方原图 {c.channel} #{c.item_id}（{c.filename}）"


def needs_official_pick(draft: dict, now: datetime | None = None) -> bool:
    """这份草稿这一班要不要跑照片接口那一档（工作流据此决定装不装认人的依赖、拉不拉模型）：
    编排器的新鲜草稿，还没有封面，或者卡死在现在这张封面上。"""
    from promote_reel_draft import PENDING_MAX_AGE  # noqa: PLC0415

    prod = draft.get("_production") if isinstance(draft.get("_production"), dict) else {}
    if prod.get("kind") != "orchestrated_reel":
        return False
    try:
        got = datetime.fromisoformat(str(prod.get("received_at") or "").replace("Z", "+00:00"))
    except ValueError:
        return False
    if got.tzinfo is None or (now or datetime.now(timezone.utc)) - got > PENDING_MAX_AGE:
        return False
    portrait = (draft.get("cover") or {}).get("portrait") or {}
    has = bool(portrait.get("image") and Path(str(portrait["image"])).is_file())
    return not has or stuck_on_cover(draft)


def refresh(draft: dict, *, now: datetime | None = None, pick=None,
            write: bool = True) -> tuple[dict, str]:
    portrait = (draft.get("cover") or {}).get("portrait") or {}
    has = bool(portrait.get("image") and Path(str(portrait["image"])).is_file())
    if has and not stuck_on_cover(draft):
        return draft, "已有封面"
    try:
        found = official_api_cover(draft, now=now, pick=pick, write=write)
    except (Exception, SystemExit) as exc:  # noqa: BLE001 —— 这一档炸了照原来的路走
        print(f"[照片接口] 没查成（{type(exc).__name__}: {exc}）——照原来的路走")
        found = None
    if found:
        return found
    if has:
        return draft, "已有封面（卡在视觉审核上；照片接口这一班也没有能换的）"
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
    ap.add_argument("--draft", type=Path)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--need-faces", nargs="*", type=Path, metavar="DRAFT",
                    help="印 true/false：这几份草稿里有没有这一班要跑照片接口那一档的（工作流据此装认人依赖）")
    args = ap.parse_args()
    if args.need_faces is not None:
        need = False
        for path in args.need_faces:
            try:
                need = need or needs_official_pick(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        print("true" if need else "false")
        return 0
    if args.draft is None:
        ap.error("要 --draft")
    before = args.draft.read_text(encoding="utf-8")
    draft, note = refresh(json.loads(before), write=args.write)
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
