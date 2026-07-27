#!/usr/bin/env python3
"""把巡回赛的**场上赛后采访**持续收进 data/oncourt_interviews.json。

**只收一类：赛后直接在场上接受采访**——主持人拿麦上场问两三个问题、
球员站着答，通常 40 秒到 4 分钟。其余两类默认不收：

- **颁奖礼致辞 / 冠军演讲**（`Championship Speech`、`Trophy Ceremony`）：
  也在场上，但是"讲"不是"接受采访"。要的话加 `--include-ceremony`。
- **媒体间发布会**（`Press Conference`）：完全不同的素材，另有 ASAP Sports
  的人工文字稿，见 docs/post-match-interview-sources.md。永远不收。

判类型有个顺序陷阱：`post-match ceremony`（法网 18–23 分钟的完整颁奖礼）
和 `post-match interview`（温网场上那 3 分钟）只差一个词，**必须先判
ceremony 再判 oncourt**，否则颁奖礼会被当成场上采访收进来。

**源分三类，只盯赛事官方会漏掉一大半**（这条是被打回来一次才补上的）：

- **转播方**：Eurosport Tennis 一家 78 条，比任何赛事方都多，而且更长
  （2–5 分钟，保留了主持人完整提问）
- **团体赛**：United Cup 56、Laver Cup 26、Davis Cup 12，每场都发
- **赛事方**：四大满贯、罗马、巴黎，以及 Dubai Duty Free（ATP 500，逐轮 45 条）

**找新源不要猜频道句柄，用搜索反推**——我猜错过四个（蒙特卡洛、迈阿密、
加拿大、Queen's），而一轮搜索找出了四个根本没想到的源：

    yt-dlp "ytsearch12:on-court interview tennis 2026" \
      --flat-playlist --print "%(channel)s ||| %(title)s"

按频道汇总一看，谁在发一目了然。

**空结果要自证是真空**（吃过三次亏，见 CLAUDE.md）。这里把三种"看起来一样"
的空结果分开报，绝不混为一谈：

- `handle-error`：一条视频都没取到 —— 频道句柄写错了，不是频道没内容
- `no-match`：取到了 N 条但没有一条命中 —— 这才是真的这批里没有
- `rate-limited`：yt-dlp 报 429 —— 被限流，跟"没有"毫无关系

还有一种更隐蔽的：**取样窗口太浅造成的假阴性**。澳网在 1 月，七月里扫近
100 条会一条都搜不到，看着就像"澳网不发采访"。所以 scan_depth 逐源可配，
建基线时给到 600–800。

**但那是建基线用的，日常跑不该再刷历史。** 两种模式分开：

    日常（默认）  每源 60 条    27 个源约 1 分钟   —— 新内容永远在最前面
    --full        注册表 600–800   十几分钟      —— 重建基线 / 新增源时才用

60 条足够覆盖一天的更新：即使大满贯期间，单个频道一天也发不到 60 条。

用法：
    # 日常增量（工作流每天跑的就是这个）
    python tools/collect_oncourt_interviews.py

    # 看看会收什么，不落库
    python tools/collect_oncourt_interviews.py --dry-run

    # 重建基线 / 新增源后补历史
    python tools/collect_oncourt_interviews.py --full

    # 只扫某几个源（按名字子串匹配）
    python tools/collect_oncourt_interviews.py --only "Tennis Channel" Rome

    # 连颁奖礼致辞一起收
    python tools/collect_oncourt_interviews.py --include-ceremony

被跳过的会按类型汇总打印出来 —— 不列的话，"这周只有 3 条"看着像没比赛，
其实是二十条致辞被默默筛掉了。

退出码 0＝跑完（哪怕有源失败）；2＝所有源都没取到东西，说明是环境问题
（限流 / 断网）而不是"这周没有比赛"。
"""

from __future__ import annotations

import argparse
import html
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

# 日常模式的扫描深度。注册表里的 scan_depth（600–800）是**建基线**用的，
# 每天拿它重刷一遍整个历史既慢又没意义——新内容永远在最前面。
# 60 条足够覆盖一天的更新：即使大满贯期间，单个频道一天也发不到 60 条。
# 重建基线或新增源时加 --full 才走深的那套。
DAILY_DEPTH = 60


def load_sources() -> dict:
    with SOURCES.open(encoding="utf-8") as fh:
        return json.load(fh)


def compile_rules(cfg: dict) -> dict[str, list]:
    return {
        "oncourt": [re.compile(p, re.I) for p in cfg["patterns_oncourt"]],
        "ceremony": [re.compile(p, re.I) for p in cfg.get("patterns_ceremony", [])],
        "maybe": [re.compile(p, re.I) for p in cfg.get("patterns_maybe", [])],
        "exclude": [re.compile(p, re.I) for p in cfg.get("exclude", [])],
        "tennis": [re.compile(p, re.I) for p in cfg.get("tennis_markers", [])],
    }


def is_tennis(title: str, rules: dict[str, list]) -> bool:
    """标题里有没有网球标记。只用于综合体育频道。

    起因是一次真实污染：Amazon Prime Video Sport 深扫 500 条命中 25 条
    `post-match interview`，**全是 UEFA 欧冠的足球采访**。
    `post-match interview` 是通用体育说法，在综合频道上不区分项目。

    `on-court interview` 本身是网球术语，不受影响——所以这道闸只对
    打了 `require_tennis` 的源生效，别全局开，那会误伤只写
    `Player On-Court Interview | Final | Rome 2026` 却没写 tennis 的条目。
    """
    return any(p.search(title) for p in rules["tennis"])


def classify(title: str, rules: dict[str, list]) -> str | None:
    """一条标题是哪一类：oncourt / ceremony / maybe / excluded / None。

    - `oncourt`：**赛后直接在场上接受采访** —— 主持人拿麦上场问、球员站着答。
      这是默认唯一收的一类。
    - `ceremony`：颁奖礼致辞、冠军演讲、晚宴致辞。是"讲"不是"接受采访"，
      默认不收。
    - `maybe`：各赛事自己的叫法（上海 `Reacts After`、马德里西语
      `Entrevista con`），既分不出场上还是媒体间，也分不出采访还是致辞。
    - `excluded`：命中了模式却不是赛后讲话的（播客、赛前预热）。

    顺序有讲究：ceremony 先于 oncourt 判。罗马的 `Trophy & Speech` 和温网的
    `Final Post-Match Interview` 都可能同时沾到两边的词，先判 ceremony
    才不会把颁奖礼误收成场上采访。
    """
    if any(p.search(title) for p in rules["ceremony"]):
        hit = "ceremony"
    elif any(p.search(title) for p in rules["oncourt"]):
        hit = "oncourt"
    elif any(p.search(title) for p in rules["maybe"]):
        hit = "maybe"
    else:
        return None
    if any(p.search(title) for p in rules["exclude"]):
        return "excluded"
    return hit


def load_store() -> dict:
    if not STORE.exists():
        return {"items": {}}
    with STORE.open(encoding="utf-8") as fh:
        return json.load(fh)


def scan_tennistv(url: str, _depth: int) -> tuple[list[dict], str]:
    """tennistv.com 的媒体库——不是 YouTube，得单独抓。

    这是唯一系统性覆盖 **ATP 250** 场上采访的来源，而且**不在付费墙后面**：
    实测 20 条里 16 条 `entitlement:free`、4 条 `freemium`（注册即可），
    premium 一条都没有。Tennis TV 的 YouTube 频道深扫 800 条是 0 条场上采访，
    东西全在站上，两者别搞混。

    页面是服务端渲染，条目以 JSON 内嵌在 HTML 里，字段齐全：
    `videoType`（interviews / preview）、`metadataRound`（R1/QF/SF/Final）、
    `durationMins`+`durationSecs`、`entitlement`、`metadataSeries`（250/500…）。
    **`videoType` 比标题可靠得多**——标题是编辑体（"Merida Elated to Win First
    ATP Tour Title"），看不出格式；videoType 直接说了。

    只给 20 条最新且翻页参数无效（page/offset/p 都返回同一批），
    所以按周跑正好——一个赛事周产出的采访远少于 20 条。
    """
    try:
        proc = subprocess.run(
            ["curl", "-sS", "--max-time", "40", "-H", "User-Agent: Mozilla/5.0", url],
            capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        return [], "error: 超时"
    raw = proc.stdout
    if not raw:
        return [], f"error: 空响应 {(proc.stderr or '')[:40]}"

    rows = []
    for blob in re.findall(r'\{[^{}]*"title"\s*:\s*"[^"]{4,120}"[^{}]*\}', raw):
        try:
            o = json.loads(blob)
        except ValueError:
            continue
        if o.get("videoType") != "interviews" or not o.get("metadataRound"):
            # preview（赛前）和没有轮次的特写不是赛后采访。
            continue
        secs = int(o.get("durationMins") or 0) * 60 + int(o.get("durationSecs") or 0)
        rows.append({
            "id": f"tennistv:{o.get('videoId')}",
            "title": html.unescape(o.get("title", "")),
            "duration_s": secs or None,
            "channel": "Tennis TV (tennistv.com)",
            "page_url": "https://www.tennistv.com" + (o.get("videoUrl") or ""),
            "round": o.get("metadataRound"),
            "series": o.get("metadataSeries") or "",
            "entitlement": o.get("entitlement") or "",
        })
    if not rows:
        return [], "no-entries"
    return rows, "ok"


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
    ap.add_argument("--full", action="store_true",
                    help="用注册表里的 scan_depth（600–800）重扫全部历史。"
                         "只在重建基线或新增源时用——日常跑不需要。")
    ap.add_argument("--daily-depth", type=int, default=DAILY_DEPTH,
                    help=f"日常模式每源扫多少条（默认 {DAILY_DEPTH}）")
    ap.add_argument("--include-ceremony", action="store_true",
                    help="连颁奖礼致辞、冠军演讲一起收（默认只收场上接受采访那一类）")
    ap.add_argument("--include-maybe", action="store_true",
                    help="连分不出场合的也收（上海 Reacts After、马德里西语那批）")
    args = ap.parse_args()

    cfg = load_sources()
    rules = compile_rules(cfg)
    keep = {"oncourt"}
    if args.include_ceremony:
        keep.add("ceremony")
    if args.include_maybe:
        keep.add("maybe")
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
    skipped: list[tuple[str, str, str]] = []
    any_fetched = False

    for src in sources:
        fetch = scan_tennistv if src.get("fetch") == "tennistv" else scan
        depth = src.get("scan_depth", 150) if args.full else min(
            args.daily_depth, src.get("scan_depth", 150))
        rows, status = fetch(src["url"], depth)
        if rows:
            any_fetched = True

        fresh = n_oncourt = n_skipped = 0
        for r in rows:
            # tennistv 的 videoType=interviews + 有轮次，已经等价于场上采访，
            # 不能再拿标题正则去筛——它的标题是编辑体，一条都匹配不上。
            kind = "oncourt" if r["id"].startswith("tennistv:") else classify(r["title"], rules)
            if kind is None:
                continue
            # 综合体育频道要过网球闸：那里的 post-match interview 会命中
            # 足球、橄榄球等所有项目。被这道闸挡掉的也计进 dropped 报出来。
            if src.get("require_tennis") and not is_tennis(r["title"], rules):
                dropped.append((src["name"], f"[非网球] {r['title']}"))
                continue
            if kind == "excluded":
                # 被挡掉的也要报出来——只报通过的，没法证明筛子是对的。
                dropped.append((src["name"], r["title"]))
                continue
            if kind not in keep:
                # 是赛后讲话，但不是要的那一类（致辞 / 分不出场合）。
                n_skipped += 1
                skipped.append((src["name"], kind, r["title"]))
                continue
            if kind == "oncourt":
                n_oncourt += 1
            if r["id"] in known or r["id"] in new_items:
                continue
            new_items[r["id"]] = {
                **r,
                "url": r.pop("page_url", None) or f"https://www.youtube.com/watch?v={r['id']}",
                "source": src["name"],
                "tier": src.get("tier", ""),
                "kind": kind,
                # 搬运号的条目要一路带着标记，别在下游混进官方源里。
                **({"unofficial": True} if src.get("unofficial") else {}),
            }
            fresh += 1

        report.append((src["name"], status, len(rows), n_oncourt, n_skipped, fresh))

    # **先落库，再打印。** 顺序反过来吃过亏：报告有几十行，下游一个
    # `| head -30` 就会把进程 SIGPIPE 掉，报告看着跑完了，产物根本没写。
    # 查产物不查信号——那次就是被完整的报告骗了。
    wrote = False
    if not args.dry_run and any_fetched:
        known.update(new_items)
        STORE.parent.mkdir(parents=True, exist_ok=True)
        with STORE.open("w", encoding="utf-8") as fh:
            json.dump({"items": known}, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        wrote = True

    # 报告：成功的和失败的都列出来。只在成功时出声的检查，没法证明它真的看过。
    mode = "全量（重扫历史）" if args.full else f"日常（每源 {args.daily_depth} 条）"
    print(f"模式：{mode}　收的类型：{'、'.join(sorted(keep))}\n")
    print(f"{'源':<34} {'状态':<20} {'取到':>5} {'场上':>5} {'跳过':>5} {'新增':>5}")
    print("-" * 82)
    for name, status, got, oncourt, skip, fresh in report:
        print(f"{name:<34} {status:<20} {got:>5} {oncourt:>5} {skip:>5} {fresh:>5}")

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

    print(f"\n新增 {len(new_items)} 条，已知 {len(known)} 条。")
    for it in list(new_items.values())[:20]:
        mins = f"{it['duration_s'] // 60}:{it['duration_s'] % 60:02d}" if it["duration_s"] else "?"
        mark = "?" if it["kind"] == "maybe" else " "
        print(f" {mark}[{it['source']}] {mins:>6}  {it['title']}")
    if len(new_items) > 20:
        print(f"  …… 另有 {len(new_items) - 20} 条")

    # 跳过的按类型汇总。不列出来的话，"这周只有 3 条"看着像没比赛，
    # 其实是二十条致辞被默默筛掉了。
    if skipped:
        by_kind: dict[str, int] = {}
        for _src, kind, _title in skipped:
            by_kind[kind] = by_kind.get(kind, 0) + 1
        desc = {"ceremony": "颁奖礼致辞 / 冠军演讲（是『讲』不是『接受采访』）",
                "maybe": "分不出场合（上海 Reacts After、马德里西语那批）"}
        print(f"\n按类型跳过 {len(skipped)} 条：")
        for kind, n in sorted(by_kind.items()):
            flag = "--include-ceremony" if kind == "ceremony" else "--include-maybe"
            print(f"  - {kind} {n} 条：{desc.get(kind, '')}　要的话加 {flag}")

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
    elif wrote:
        print(f"\n已写入 {STORE.relative_to(ROOT)}（共 {len(known)} 条）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
