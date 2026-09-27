#!/usr/bin/env python3
"""推送到微信的那条消息的网页链接——推完就发进对话。

账号所有者 2026-09-27：「推送到微信之后，把推送到微信的那个网页链接也给我，
发到这个对话里」。链接是 PushPlus 的消息详情页
`https://www.pushplus.plus/shortMessage/<流水号>`（官方 OpenAPI 文档「消息详情」，
2026-09-27 拿两条真实流水号实测 200），国内打得开——GitHub 的 Release / Pages
他打不开，这个能。

流水号由推送那一步写进 `$RUNNER_TEMP/…receipt.json`，「记下已推送」再把它和
`message_url` 一起写进 `<outdir>/pushed.json` 和 `data/<栏目>_publish_ledger/<slug>.json`。
这个工具只读那两处，**不编链接**：没记流水号（这条机制上线前推的）就明说取不到。

    python3 tools/push_link.py --slug bu-majchrzak-hangzhou-2026-r2   # 合并后 git pull 再跑
    python3 tools/push_link.py --recent 5                             # 最近几条推送
    # 工作流里：推送后把链接写进 run 摘要
    python3 tools/push_link.py --receipt-file "$RUNNER_TEMP/x.json" --slug S --summary "$GITHUB_STEP_SUMMARY"
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from publication_ledger import read_receipt_file, receipt_fields  # noqa: E402

LEDGER_COLUMNS = ("reel", "interview", "explainer")


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def pushes(repo: Path, slug: str = "") -> list[dict]:
    """仓库里记下来的每一次推送：`{slug, column, at, receipt, message_url, source}`。

    两处来源合起来读：`pushed.json`（每个产物目录一份，重渲会换目录）和发布账本
    （跨重渲的每一次 `sent`/`accepted`）。同一个流水号只留一条。
    """
    rows: list[dict] = []
    want = slug or "*"
    for pattern, column in ((f"output/*/reel/{want}/pushed.json", "reel"),
                            (f"output/*/explainer/{want}/pushed.json", "explainer"),
                            (f"output/interviews/{want}/pushed.json", "interview")):
        for p in glob.glob(str(repo / pattern)):
            data = _load(Path(p))
            receipt = str(data.get("pushplus_receipt") or "")
            rows.append({"slug": Path(p).parent.name, "column": column,
                         "at": str(data.get("at") or ""), "receipt": receipt,
                         "message_url": str(data.get("message_url") or "")
                         or receipt_fields(receipt).get("message_url", ""),
                         "source": str(Path(p).relative_to(repo))})
    for column in LEDGER_COLUMNS:
        for p in glob.glob(str(repo / f"data/{column}_publish_ledger/{want}.json")):
            ledger = _load(Path(p))
            for row in ledger.get("attempts") or []:
                if not isinstance(row, dict) or row.get("status") not in {"sent", "accepted", "delivered"}:
                    continue
                receipt = str(row.get("pushplus_receipt") or "")
                rows.append({"slug": str(ledger.get("slug") or Path(p).stem), "column": column,
                             "at": str(row.get("at") or ""), "receipt": receipt,
                             "message_url": str(row.get("message_url") or "")
                             or receipt_fields(receipt).get("message_url", ""),
                             "source": str(Path(p).relative_to(repo))})
    seen: set[str] = set()
    out: list[dict] = []
    # 有流水号的排前面，好让同一次推送里带链接的那一笔胜出
    for row in sorted(rows, key=lambda r: (r["at"], bool(r["receipt"])), reverse=True):
        dedup = row["receipt"] or f"{row['slug']}@{row['at']}"
        if dedup in seen:
            continue
        seen.add(dedup)
        out.append(row)
    return out


def describe(row: dict) -> str:
    if row["message_url"]:
        return f"{row['at']}  {row['column']:9s} {row['slug']}\n  微信推送网页：{row['message_url']}"
    return (f"{row['at']}  {row['column']:9s} {row['slug']}\n"
            f"  ⚠️ 这一次没记流水号（{row['source']}），推送网页链接取不到——"
            "不编一个；要找就去那一趟 run 的日志里搜「[PushPlus] 收下了」")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slug", default="", help="只看这一条片子")
    ap.add_argument("--recent", type=int, default=0, help="列最近 N 次推送（不给 --slug 时默认 5）")
    ap.add_argument("--receipt-file", default="",
                    help="推送那一步写下的流水号 JSON：直接从它出链接（工作流里用）")
    ap.add_argument("--summary", default="", help="把链接追加进这个 markdown 文件（$GITHUB_STEP_SUMMARY）")
    ap.add_argument("--repo", default=".")
    args = ap.parse_args(argv)

    if args.receipt_file:
        url = receipt_fields(read_receipt_file(args.receipt_file)).get("message_url", "")
        if not url:
            print(f"::warning::{args.receipt_file} 里没有流水号，推送网页链接取不到")
            return 0
        print(f"微信推送网页：{url}")
        if args.summary:
            with open(args.summary, "a", encoding="utf-8") as fh:
                fh.write(f"\n- 📱 微信推送网页（{args.slug or '本次推送'}）：{url}\n")
        return 0

    rows = pushes(Path(args.repo), args.slug)
    if not rows:
        what = f"「{args.slug}」" if args.slug else "任何片子"
        print(f"仓库里没有{what}的推送记录（pushed.json / 发布账本都没有）。"
              "刚合并的话先 git pull 拿到「已自动推送」那个提交。")
        return 2
    limit = args.recent or (1 if args.slug else 5)
    for row in rows[:limit]:
        print(describe(row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
