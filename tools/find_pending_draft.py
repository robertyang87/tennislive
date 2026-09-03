#!/usr/bin/env python3
"""开工之前先查：这一场球自动链是不是已经 probe 过、草稿卡在哪儿。

来路（2026-09-03 全库 review）：最近发出的 30 条「赛场之上」里 29 条是会话
手写的 spec，而编排器在旁边为同一批比赛跑了 57 次 probe、留下 49 份 pending
草稿——两条路互不复用。`zverev-sonego` 那一场同一天里 `output/2026-09-02/reel/`
下躺着两个目录（`zverev-sonego` 是自动链的，`zverev-sonego-us-open-2026-r1`
是会话的），同一条 1080p 源片下了两遍、缩略图墙拼了两遍、逐分和统计各查了
一遍。probe 那一趟 3~5 分钟，是整条快路里最贵的一步。

用法（按两个姓认，别按 slug 猜——草稿的 slug 是短的）::

    python3 tools/find_pending_draft.py --who Wu,Duckworth
    python3 tools/find_pending_draft.py --slug zverev-sonego

打出来的每一行都是产物路径，不是推断：草稿文件、它的源片、已落库的
probe 目录（缩略图墙 / 切点 / 死球 / 静音区都在里面）、结构化赛果和统计
在不在、封面落没落、以及 `promote_reel_draft.waiting_reasons` 报的卡点。
找到了就**接着用**：`assemble_spec` 产的 `_match` / `stats` / `_hit_data` /
`_turning_points` 直接搬进正式 spec，probe 目录直接指给 `--dry-run`。

退出码：0 找到；2 没有——**没有也要出声**，「没找到」和「没查」在会话里
长得一模一样。
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PENDING = ROOT / "specs" / "reels" / "pending"


def _surnames(draft: dict) -> list[str]:
    out = []
    for p in (draft.get("cover") or {}).get("matchup") or []:
        en = str(p.get("name_en") or "").strip().lower()
        if en:
            out.append(en.split()[-1])
    return out


def _slug_words(slug: str) -> set[str]:
    return set(re.split(r"[-_.]+", slug.lower()))


def matches(draft: dict, slug: str, who: list[str], want_slug: str) -> bool:
    """按**整个姓**认，不按子串——第一版 `n in w` 让 slug 里的单字母 `j`
    命中了 `Nothing`，于是随便两个姓都能「找到」`bublik-j.j.`。"""
    if want_slug:
        return want_slug.lower() in slug.lower()
    names = {n for n in set(_surnames(draft)) | _slug_words(slug) if len(n) >= 2}
    return all(w.lower() in names for w in who)


def probe_dirs(slug: str) -> list[Path]:
    hits = [Path(p).parent for p in glob.glob(str(ROOT / "output" / "*" / "reel" / slug / "probe.json"))]
    return sorted(hits)


def waiting(draft: dict) -> list[str]:
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import promote_reel_draft  # noqa: E402
    except Exception as exc:  # pragma: no cover - 环境缺依赖时别把查找一起带崩
        return [f"（waiting_reasons 跑不起来：{type(exc).__name__}: {exc}）"]
    with redirect_stdout(io.StringIO()):
        try:
            return list(promote_reel_draft.waiting_reasons(draft))
        except Exception as exc:
            return [f"（waiting_reasons 崩了：{type(exc).__name__}: {exc}）"]


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def report(path: Path, draft: dict) -> None:
    slug = draft.get("slug") or path.name.replace(".draft.json", "")
    prod = draft.get("_production") or {}
    match = draft.get("_match") or {}
    cover = draft.get("cover") or {}
    portrait = (cover.get("portrait") or {}).get("image")
    print(f"=== {_rel(path)}")
    print(f"    slug {slug} · received_at {prod.get('received_at') or '?'} · "
          f"event {prod.get('event') or '?'} round {prod.get('round') or '（空）'} court {prod.get('court') or '（空）'}")
    print(f"    源片 {draft.get('source_url') or '?'}")
    dirs = probe_dirs(slug)
    if dirs:
        for d in dirs:
            sheets = len(glob.glob(str(d / "contact_*.jpg")))
            print(f"    probe ✅ {_rel(d)}（缩略图墙 {sheets} 张）")
    else:
        print("    probe ❌ 没有落库的 probe.json（这一场还得自己 probe）")
    print(f"    赛果 {match.get('status') or '（无）'}"
          + (f"：{match.get('winner')} {match.get('winner_result')} {match.get('loser')}" if match.get('winner') else "")
          + f" · 统计 {'✅' if draft.get('stats') else '❌'} · 狠数据 {'✅' if draft.get('_hit_data') else '❌'}"
          + f" · 转折点 {'✅' if draft.get('_turning_points') else '❌'}")
    print(f"    封面 {'✅ ' + str(portrait) if portrait and Path(str(portrait)).is_file() else '❌ 官方实拍还没落'}")
    reasons = waiting(draft)
    print(f"    promote 卡点 {len(reasons)} 条" + (f"：{'；'.join(reasons[:4])}{'…' if len(reasons) > 4 else ''}" if reasons else "——可以直接转正"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--who", default="", help="两个姓，逗号分隔（英文，按 name_en 的姓认）")
    ap.add_argument("--slug", default="", help="按草稿 slug 的子串认")
    args = ap.parse_args()
    who = [w.strip() for w in args.who.split(",") if w.strip()]
    if not who and not args.slug:
        ap.error("要么 --who A,B 要么 --slug")
    found = 0
    for path in sorted(PENDING.glob("*.draft.json")):
        try:
            draft = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"⚠️ {path.name} 读不出来：{exc}")
            continue
        if matches(draft, path.name.replace(".draft.json", ""), who, args.slug):
            report(path, draft)
            found += 1
    if not found:
        print(f"pending 里没有匹配 {who or args.slug} 的草稿（扫了 {len(list(PENDING.glob('*.draft.json')))} 份）——"
              "这一场自动链没 probe 过，或者草稿已经清掉；自己 probe 之前先 `ls output/*/reel/` 再确认一次")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
