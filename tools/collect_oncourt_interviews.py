#!/usr/bin/env python3
"""把巡回赛的**场上**赛后采访与冠军致辞持续收进 data/oncourt_interviews.json。

只收场上那一类：赢球后还在场上对着观众讲的（on-court interview）、决赛后的
颁奖礼致辞（championship / finalist speech、trophy ceremony）。媒体间的新闻
发布会不在此列——那类有 ASAP Sports 的人工文字稿，来源和用法都不同，
见 docs/post-match-interview-sources.md。

**为什么不是一个赛事一个频道**：ATP/WTA 各有六十来站，250 级别的赛事大多
没有自己的 YouTube 频道。实扫发现 Tennis Channel 一家就覆盖了全巡回赛的
冠军/亚军致辞（近 250 条里命中 16 项赛事，Kitzbuhel、Gstaad、Bastad、
Prague、Athens 这些小站只有它有），所以它是主源，各赛事自己的频道是补充。

**空结果要自证是真空**（吃过三次亏，见 CLAUDE.md）。这里把三种"看起来一样"
的空结果分开报，绝不混为一谈：

- `handle-error`：一条视频都没取到 —— 频道句柄写错了，不是频道没内容
- `no-match`：取到了 N 条但没有一条命中 —— 这才是真的这批里没有
- `rate-limited`：yt-dlp 报 429 —— 被限流，跟"没有"毫无关系

还有一种更隐蔽的：**取样窗口太浅造成的假阴性**。澳网在 1 月，七月里扫近
100 条会一条都搜不到，看着就像"澳网不发采访"。所以 scan_depth 逐源可配，
澳网那条特意调到 400。

用法：
    # 扫一遍，只打印不落库
    python tools/collect_oncourt_interviews.py --dry-run

    # 扫一遍并把新条目并进 data/oncourt_interviews.json
    python tools/collect_oncourt_interviews.py

    # 只扫某几个源（按名字子串匹配）
    python tools/collect_oncourt_interviews.py --only "Tennis Channel" Rome

退出码 0＝跑完（哪怕有源失败）；2＝所有源都没取到东西，说明是环境问题
（限流 / 断网）而不是"这周没有比赛"。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "data" / "oncourt_sources.json"
STORE = ROOT / "data" / "oncourt_interviews.json"

# yt-dlp 单源超时。频道扫 400 条时会比较久。
TIMEOUT = 300
# 429 退避阶梯。实测连续第 4 次才成功过，别只重试一次。
BACKOFF = [0, 20, 45, 90]

FIELD_SEP = " ||| "


def load_sources() -> dict:
    with SOURCES.open(encoding="utf-8") as fh:
        return json.load(fh)


def compile_rules(cfg: dict) -> tuple[list, list, list]:
    return (
        [re.compile(p, re.I) for p in cfg["patterns"]],
        [re.compile(p, re.I) for p in cfg.get("patterns_maybe", [])],
        [re.compile(p, re.I) for p in cfg.get("exclude", [])],
    )


def classify(title: str, patterns, maybes, excludes) -> str | None:
    """一条标题归到哪一档：confident / maybe / excluded / None（压根没命中）。

    confident 的标题自己说明了场合（on-court / trophy / speech）；
    maybe 是各赛事自己的叫法（上海的 `Reacts After`、马德里的西语
    `Entrevista con`），能确定是赛后讲话但分不出在场上还是媒体间；
    excluded 是命中了模式却不是赛后讲话的（播客、赛前预热）。
    """
    if any(p.search(title) for p in patterns):
        hit = "confident"
    elif any(p.search(title) for p in maybes):
        hit = "maybe"
    else:
        return None
    if any(p.search(title) for p in excludes):
        return "excluded"
    return hit


def load_store() -> dict:
    if not STORE.exists():
        return {"items": {}}
    with STORE.open(encoding="utf-8") as fh:
        return json.load(fh)


def scan(url: str, depth: int) -> tuple[list[dict], str]:
    """扫一个频道。返回 (条目列表, 状态)。

    状态取值 ok / handle-error / rate-limited / error:<摘要>。
    **不吞 stderr** —— 429 和"频道是空的"在 stdout 上长得一模一样，
    唯一能分开它们的信息全在 stderr 里。
    """
    last_err = ""
    for wait in BACKOFF:
        if wait:
            time.sleep(wait)
        try:
            proc = subprocess.run(
                [
                    "yt-dlp", "--flat-playlist",
                    "--playlist-end", str(depth),
                    "--print", FIELD_SEP.join(
                        f"%({k})s" for k in ("id", "title", "duration", "channel")
                    ),
                    url,
                ],
                capture_output=True, text=True, timeout=TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            last_err = f"超时（{TIMEOUT}s）"
            continue

        err = proc.stderr or ""
        if "429" in err or "Too Many Requests" in err:
            last_err = "429 限流"
            continue

        rows = []
        for line in proc.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split(FIELD_SEP)
            if len(parts) < 4:
                continue
            vid, title, dur, channel = parts[0], parts[1], parts[2], parts[3]
            rows.append({
                "id": vid.strip(),
                "title": title.strip(),
                "duration_s": int(float(dur)) if dur.replace(".", "").isdigit() else None,
                "channel": channel.strip(),
            })

        if not rows:
            # 一条都没取到：句柄写错了，还是频道真空？yt-dlp 对不存在的
            # 句柄也返回 0 条且不报错，所以这里只能报"疑似句柄错"，
            # 不能报"这个频道没有采访"。
            return [], "handle-error"
        return rows, "ok"

    return [], f"rate-limited（{last_err}）" if "429" in last_err else f"error: {last_err}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写 data/oncourt_interviews.json")
    ap.add_argument("--only", nargs="*", default=None, help="只扫名字含这些子串的源")
    args = ap.parse_args()

    cfg = load_sources()
    patterns, maybes, excludes = compile_rules(cfg)
    sources = cfg["sources"]
    if args.only:
        needles = [s.lower() for s in args.only]
        sources = [s for s in sources if any(n in s["name"].lower() for n in needles)]
        if not sources:
            print(f"没有源匹配 {args.only}", file=sys.stderr)
            return 2

    store = load_store()
    known = store["items"]
    new_items: dict[str, dict] = {}
    report: list[tuple[str, str, int, int, int, int]] = []
    dropped: list[tuple[str, str]] = []
    any_fetched = False

    for src in sources:
        rows, status = scan(src["url"], src.get("scan_depth", 150))
        if rows:
            any_fetched = True

        fresh = n_conf = n_maybe = 0
        for r in rows:
            conf = classify(r["title"], patterns, maybes, excludes)
            if conf is None:
                continue
            if conf == "excluded":
                # 被挡掉的也要报出来——只报通过的，没法证明筛子是对的。
                dropped.append((src["name"], r["title"]))
                continue
            if conf == "confident":
                n_conf += 1
            else:
                n_maybe += 1
            if r["id"] in known or r["id"] in new_items:
                continue
            new_items[r["id"]] = {
                **r,
                "url": f"https://www.youtube.com/watch?v={r['id']}",
                "source": src["name"],
                "tier": src.get("tier", ""),
                "confidence": conf,
            }
            fresh += 1

        report.append((src["name"], status, len(rows), n_conf, n_maybe, fresh))

    # 报告：成功的和失败的都列出来。只在成功时出声的检查，没法证明它真的看过。
    print(f"{'源':<34} {'状态':<20} {'取到':>5} {'确定':>5} {'待定':>5} {'新增':>5}")
    print("-" * 82)
    for name, status, got, conf, maybe, fresh in report:
        print(f"{name:<34} {status:<20} {got:>5} {conf:>5} {maybe:>5} {fresh:>5}")

    bad = [r for r in report if r[1] != "ok"]
    if bad:
        print("\n没取到内容的源（**不代表它们没有采访**）：")
        for name, status, *_ in bad:
            hint = {
                "handle-error": "句柄可能写错了，去 YouTube 搜赛事全名核对",
                }.get(status, "网络/限流，换个时间再跑")
            print(f"  - {name}：{status} —— {hint}")

    empty = [r for r in report if r[1] == "ok" and r[3] == 0 and r[4] == 0]
    if empty:
        print("\n取到了内容但一条没命中（这批里确实没有，属正常）：")
        for name, _s, got, *_ in empty:
            print(f"  - {name}：扫了 {got} 条")

    n_maybe_total = sum(1 for v in new_items.values() if v["confidence"] == "maybe")
    print(f"\n新增 {len(new_items)} 条（确定 {len(new_items) - n_maybe_total}，"
          f"待定 {n_maybe_total}），已知 {len(known)} 条。")
    for it in list(new_items.values())[:15]:
        mins = f"{it['duration_s'] // 60}:{it['duration_s'] % 60:02d}" if it["duration_s"] else "?"
        mark = "?" if it["confidence"] == "maybe" else " "
        print(f" {mark}[{it['source']}] {mins:>6}  {it['title']}")
    if len(new_items) > 15:
        print(f"  …… 另有 {len(new_items) - 15} 条")
    if n_maybe_total:
        print(f"\n带 ? 的 {n_maybe_total} 条是**待定**：标题能确定是赛后球员讲话，"
              "但分不出在场上还是媒体间，人工看一眼再归类。")

    if dropped:
        print(f"\n命中了模式但被 exclude 挡掉的 {len(dropped)} 条"
              "（列出来是为了能发现筛子筛错）：")
        for name, title in dropped[:10]:
            print(f"  - [{name}] {title}")
        if len(dropped) > 10:
            print(f"  …… 另有 {len(dropped) - 10} 条")

    if not any_fetched:
        print("\n所有源都没取到东西——这是环境问题（限流/断网），不是『这周没比赛』。",
              file=sys.stderr)
        return 2

    if args.dry_run:
        print("\n--dry-run：没有写入。")
        return 0

    known.update(new_items)
    STORE.parent.mkdir(parents=True, exist_ok=True)
    with STORE.open("w", encoding="utf-8") as fh:
        json.dump({"items": known}, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"\n已写入 {STORE.relative_to(ROOT)}（共 {len(known)} 条）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
