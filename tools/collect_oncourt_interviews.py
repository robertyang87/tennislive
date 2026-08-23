#!/usr/bin/env python3
"""把巡回赛的**场上赛后采访**持续收进 data/oncourt_interviews.json。

**只收一类：赛后直接在场上接受采访**——主持人拿麦上场问两三个问题、
球员站着答，通常 40 秒到 4 分钟。

而且必须是**赛事官方那一场**（ATP / WTA / 四大满贯）。账号所有者的原话：
「要 atp 和 wta 或者大满贯官方的场上采访」。这句话排掉的是一整类看着很像、
判据却过不了的东西——**中国转播商的记者在球场上做的采访**：

    腾讯体育在温网草地上问王欣瑜        在场上 ✓  赛后 ✓  转播画质 ✓  但不是官方那场
    咪咕/央视在华盛顿场边问王欣瑜        同上
    央视在法网 BNP PARIBAS 背景板前      连场上都不是，是混合区

判据落在**话筒**上，和 `Lilli Tagger Champion Prague 2026` 那条一样：
官方场上采访是 `WTA TOUR` / `ATP` / 赛事自己的话筒旗（黑底白字，常挂赞助商
方块），面向全场观众；转播商那种举的是自家台标牌（`腾讯体育`、`CCTV`），
是给自己频道做的独家。**光看「人在不在球场上」分不出来，得看话筒。**

顺带一层：那类采访基本是**中文进行的**，而这个库是英语学习素材。

其余两类默认不收：

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

**但这句查询词本身会骗人，而且骗得很像「真的没有」。** 找 Edimator 的替代者
时我拿它扫了六组泛化措辞（`on-court interview WTA 2026`、`post match
interview WTA 500 2026`…），108 条命中里**一条 Edimator 都没有**——而它库里
躺着 158 条，正是要找的那种号。原因是 **YouTube 搜索按标题字面匹配**，
而这类号用的是自己的固定句式：

    <球员> interview after <轮次> win at <年份> <赛事>

换成这个句式一搜，第一条就是它。所以：

- **查询词要照目标的句式写**，不是照你想找的"概念"写
- **每一轮都放一个已知非空的对照查询**（比如
  `interview after 1st round win at 2025 Citi Open` 必出 Edimator）。
  对照组不出来，这一轮的零就不算数——**和 B 站那个金丝雀是同一个道理**，
  只不过这里骗人的不是限流，是措辞

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
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "data" / "oncourt_sources.json"
STORE = ROOT / "data" / "oncourt_interviews.json"
VERDICTS = ROOT / "data" / "oncourt_verify.json"

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

# tennistv 的 `videoType=interviews` 里混着发布会，用时长切开：
# 场上采访 40 秒–4 分钟，发布会 6 分钟起。这个界是从 Tennis TV 那批
# `Reacts To…` 上量出来的（Madrid 10:06 是发布会、Rome 3:34 是场上），
# 实测混进来的 12 条全在 7–23 分钟，界划在 6 分钟不会误伤。
TENNISTV_MAX_SECS = 360


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


def compile_allow(cfg: dict) -> dict[str, list]:
    """每个源自己的**白名单**：这个源上，标题长这样就算场上采访。

    为什么需要它，而不是把写法加进全局 `patterns_oncourt`：
    官方赛事频道的标题往往**极简**，`Filip Misolic Interview - Nordea Open 2025`
    ——只有一个光秃秃的 `interview`。把 `\\binterview\\b` 加进全局，
    发布会、播客、专访会一起灌进来；但在巴斯塔德自己的频道里，
    27 条带 interview 的条目抽 8 条看帧全在红土场上，那就是安全的。

    **和 assume_oncourt 的区别**：assume_oncourt 是整个频道照单全收，
    Nordea 那样 300 条里混着 16 秒 Hot shot 的频道会被灌爆（实测多收 273 条）。
    白名单只放标题对得上的那部分。

    白名单**不豁免 exclude 和 deny_ids**——两道出口闸照旧。
    """
    return {name: [re.compile(p, re.I) for p in pats]
            for name, pats in cfg.get("allow_by_source", {}).items()}


def compile_deny(cfg: dict) -> dict[str, list]:
    """每个源自己的标题黑名单。**现在是空的，而且应该保持空的。**

    留着这个口子只是为了以后真出现「标题层面能干净切开」的源。但法网和巴黎
    大师赛这两个源已经证明了：**同一个频道里同一个词，可以指两件事**。

      - 法网按年份切（2024 的 post-match 一律当发布会），61 条错杀 4 条
      - 巴黎按「不写 on-court 就剔」切，25 条错杀 7 条

    分不出来就逐条看画面，记进 `deny_ids`。别再往这里加正则。
    """
    return {name: [re.compile(p, re.I) for p in pats]
            for name, pats in cfg.get("deny_by_source", {}).items()}


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


def _tail_interview(row: dict, cfg: dict) -> bool:
    """这条集锦的**尾巴上接没接场上采访**——判据是时长，不是标题。

    这是这套东西里最反直觉的一条，也是把 WTA 那一侧从零救回来的那条。
    我一直把 `@wta` 记成「只有集锦，场上采访 0」，深扫 800 条也确实一条
    带 interview 的标题都没有。**但采访根本不在标题里，它在片子后半段。**

    `@wta` 的逐场集锦是**固定格式**的。100 条实测，时长分布是干净的双峰：

        285–310 秒   66 条   纯集锦（这个格式卡得极死，绝大多数是 306–310）
        ── 空档 ──          310 到 333 之间一条都没有
        333–648 秒   33 条   集锦 + 赛后场上采访

    逐帧验过：309/310/310 那几条的 75% 处还在比赛里；333 是红色 DC Open
    话筒旗、339 是 `WTA TOUR` 黑话筒旗加烧录条
    `SARA BEJLEK — ADVANCES TO THE 2ND ROUND`、360/422/447 同样是采访。

    ⚠️ **hq3 只到 75%，够不着短尾巴。** 353 秒那条在 75% 处仍是比赛画面——
    那不是反证，只说明它的采访不足全长的四分之一。所以**别拿"帧里没看到"
    去否定时长判据**，两者的分辨率不一样。

    ⚠️ 也**不是每个赢家都有**：伊拉胜郑钦文那场是 310 秒，没有尾巴。
    这个判据回答的是"这条片子里有没有"，不是"这场比赛做没做"。

    界划在 320：落在实测那个 23 秒宽的空档正中间。改它要重新量分布，
    别按比例推。
    """
    secs = row.get("duration_s")
    if not secs or secs < cfg.get("min_secs", 320):
        return False
    title = row.get("title", "")
    if (bad := cfg.get("exclude_pat")) and re.search(bad, title):
        # **长 ≠ 有尾巴。** 两类东西会混进来，长的理由完全不同：
        #   `… Cincinnati Finał Full Match | WTA Match Highlights`  6235 秒——
        #       标题结尾照样是 Match Highlights，实际是整场录播（录播尾巴上
        #       不接采访，那是另一条实测结论）
        #   `Day 2 in Memphis with Sonmez, Stephens & more | …`     1464 秒——
        #       塞了一整天的比赛
        return False
    return bool(re.search(cfg["title_pat"], title))


def load_store() -> dict:
    if not STORE.exists():
        return {"items": {}}
    with STORE.open(encoding="utf-8") as fh:
        return json.load(fh)


def scan_tennistv(url: str, _depth: int) -> tuple[list[dict], str]:
    """tennistv.com 的媒体库——不是 YouTube，得单独抓。

    这是唯一系统性覆盖 **ATP 250** 场上采访的来源。实测 20 条里 16 条
    `entitlement:free`、4 条 `freemium`，premium 一条都没有。
    Tennis TV 的 YouTube 频道是 0 条场上采访，东西全在站上，两者别搞混。

    ⚠️ **但「entitlement:free」不等于「拿得到视频」，这句我先前写错过。**
    原文写的是「**不在付费墙后面**」——那是我从 `free` 这个字面推的，没验。
    实际：页面挂着 Cleeng（订阅 SDK）和身份 SDK，播放器是 JS 起的；
    拿标准客户端去取，yt-dlp 的 TennisTV 提取器直接回

        This video is only available for registered users.

    `free` / `freemium` / `premium` 是**他们账号体系内部的档位**，不是
    「匿名可取」。**元数据（标题、轮次、时长、赛事）照常公开可抓，那部分
    没变**；变的是「视频文件能不能拿到」的结论——那需要账号，绕开它的做法
    不做。要 ATP 侧的画面，只能人自己开账号看。

    页面是服务端渲染，条目以 JSON 内嵌在 HTML 里，字段齐全：
    `videoType`（interviews / preview）、`metadataRound`（R1/QF/SF/Final）、
    `durationMins`+`durationSecs`、`entitlement`、`metadataSeries`（250/500…）。
    **`videoType` 比标题可靠得多**——标题是编辑体（"Merida Elated to Win First
    ATP Tour Title"），看不出格式；videoType 直接说了。

    **库页只给 20 条最新，按赛事的页面才是完整的**——这是找了很久才发现的：

        /library/interviews              20 条最新，所有赛事共享名额
        /tournaments/422_2025/cincinnati 那一届的全部，42 条

    差别有多大：辛辛那提在库页里常年 0–1 条，赛事页有 42 条。之前断言
    「七个大师赛官方不发场上采访」就是因为只看了库页和 YouTube 频道，
    没想到 tennistv 按赛事另有一套完整的页。实测各届都有 40+：
    迈阿密 45、马德里 44、辛辛那提 42、印第安维尔斯 42、蒙特卡洛 41、
    罗马 41、巴黎 41、加拿大 40、上海 40、华盛顿 25。

    赛事页的 URL 必须用 `{id}_{年}/{slug}` 形式，光写 slug 只对往年有效
    （`citi-open-2025` 通，`citi-open-2026` 404）。ID 没有公开索引页
    （索引是 JS 渲染的），所以维护在注册表的 url 字段里，逗号分隔。
    """
    urls = [u.strip() for u in url.split(",") if u.strip()]
    raw = ""
    for u in urls:
        try:
            proc = subprocess.run(
                ["curl", "-sS", "--max-time", "40", "-H", "User-Agent: Mozilla/5.0", u],
                capture_output=True, text=True, timeout=60,
            )
        except subprocess.TimeoutExpired:
            continue
        raw += proc.stdout
    if not raw:
        return [], "error: 全部页面都没取到"

    rows = []
    seen_ids: set[str] = set()
    for blob in re.findall(r'\{[^{}]*"title"\s*:\s*"[^"]{4,120}"[^{}]*\}', raw):
        try:
            o = json.loads(blob)
        except ValueError:
            continue
        if o.get("videoType") != "interviews" or not o.get("metadataRound"):
            # preview（赛前）和没有轮次的特写不是赛后采访。
            continue
        secs_chk = int(o.get("durationMins") or 0) * 60 + int(o.get("durationSecs") or 0)
        if secs_chk >= TENNISTV_MAX_SECS:
            # `videoType=interviews` 里混着发布会。判据是时长：场上采访
            # 40 秒–4 分钟，发布会 6 分钟起。实测混进来的 12 条全在 7–23 分钟，
            # 而且多是两人同台（`Sinner & Lehecka React To Miami Final` 23:11），
            # 那只可能是媒体间——场上不会让两个人一起站着答。
            continue
        vid = str(o.get("videoId"))
        if vid in seen_ids:
            continue
        seen_ids.add(vid)
        secs = int(o.get("durationMins") or 0) * 60 + int(o.get("durationSecs") or 0)
        rows.append({
            "id": f"tennistv:{vid}",
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


# slug 里 `_digital-download_m50936` 这一截是 WTA 发行系统的资产编号，
# 对我们没用，但**不能在正则里把 `_` 排除掉**——见 `_WTA_SLUG` 下面那条注释。
_WTA_TAIL = re.compile(r"_digital[-_]download.*$|_m\d{4,}$")
# **`_` 必须在字符类里。** 少了它，`..._digital-download_m50936` 会在下划线处
# 截断，拼出来的 URL 一律 404 —— 而 WTA 的场上采访 slug **全部**带这个后缀，
# 于是整个源一条都收不到。这不是「条目被下架了」，是 URL 被我拼断了。
_WTA_SLUG = re.compile(r"/videos/(\d+)/([a-z0-9_\-]{6,})")
_WTA_IS_INTERVIEW = re.compile(r"(?:post-match|on-court)-interview")

# 列表页是**滚动窗口**（`/videos` 约 60 条、`/videos/interviews` 恰好 10 条，
# 翻页参数服务端直接忽略），一条采访赶上出片密集的那半天就会被挤出窗口，
# 之后永远取不到。兜底是顺着 ID 往回扫——ID 是按发布时间递增的。
# 900 是倒推出来的，不是拍的：实测华盛顿周 ID 走 ~670/天，两次 cron
# 之间最长的一档是 03:00→21:00 的 18 小时 ≈ 500，留 1.8 倍余量。
WTA_SWEEP_BACK = 900
WTA_SWEEP_JOBS = 12
# 未发布的 ID 不返回 404，而是回退到站点通名——**软 404，得按标题认**。
_WTA_MISS_TITLE = "Women's Tennis Association - Official"


def _wta_page(vid: str) -> str | None:
    """取一条 WTA 视频详情页。

    **用不带 slug 的 `/videos/<id>`**：站点自己的 canonical 就是这个形式，
    而且它不会因为 slug 解析错就整条丢掉。`--compressed` 是必须的——
    一页 178 KB，压完 20 KB，一轮扫 900 个差了 140 MB。
    """
    try:
        proc = subprocess.run(
            ["curl", "-sS", "--compressed", "--max-time", "25",
             "-H", "User-Agent: Mozilla/5.0", f"https://www.wtatennis.com/videos/{vid}"],
            capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired:
        return None      # 超时是「没问过」，不是「不存在」
    return proc.stdout or None


def _wta_item(vid: str) -> dict | None:
    """详情页 → 一条采访候选；不是采访 / 取不到就返回 None。

    页面自带三样别处拿不到的东西：`titleUrlSegment`（完整 slug，自证赛事+
    轮次+球员）、`uploadDate`（**库里第一批真发布时间**）、`duration`。
    """
    raw = _wta_page(vid)
    if not raw:
        return None
    m = re.search(r'<meta property="og:title" content="([^"]*)"', raw)
    if not m or m.group(1).startswith(_WTA_MISS_TITLE):
        return None
    headline = m.group(1)
    # 一页里 `titleUrlSegment` 出现多次（封面图一份、视频一份）。**全收**，
    # 只要有一份是采访就算——只取第一份的话，封面用 Getty 图的条目会漏。
    segs = re.findall(r"titleUrlSegment&quot;:&quot;([a-z0-9_\-]{4,160})&quot;", raw)
    slug = next((s for s in segs if _WTA_IS_INTERVIEW.search(s)), None)
    if not slug:
        return None
    d = re.search(r'"duration":\s*"PT(?:(\d+)M)?(?:(\d+)S)?"', raw)
    dt = re.search(r'"uploadDate":\s*"([0-9T:\-Z]+)"', raw)
    return {"vid": vid, "slug": slug, "headline": headline,
            "secs": (int(d.group(1) or 0) * 60 + int(d.group(2) or 0)) if d else None,
            "published": dt.group(1) if dt else None}


def _wta_row(it: dict) -> dict:
    """把 slug 拆成条目。slug 自己写死了四要素，不靠标题猜。

        athens-post-match-interview-final-barbora-krejcikova-english_digital-download_m50936
        └赛事┘ └──────类型──────┘ └轮次┘ └────球员────┘ └语言┘ └───发行编号───┘
    """
    slug = it["slug"]
    core = _WTA_TAIL.sub("", slug)
    m = re.match(r"([a-z0-9_\-]+?)-(?:post-match|on-court)-interview-"
                 r"(final|sf|qf|r\d+|semi\w*|quarter\w*)?-?(.*)", core)
    # `queen_s-post-match-interview-r16-...` 里的下划线是 WTA 自己的写法，
    # 拼回标题时当成撇号去掉，别留成「Queen S」。
    event = (m.group(1).replace("_", "").replace("-", " ").title() if m else "")
    rnd = (m.group(2) or "") if m else ""
    who = (m.group(3) or "").replace("-english", "").replace("-", " ").title() if m else ""
    return {
        "id": f"wta:{it['vid']}",
        # slug 拼回可读标题：轮次和赛事都塞进去，下游的轮次解析才认得出
        "title": f"{who} Post-Match Interview | {rnd.upper()} | {event}".replace("|  |", "|"),
        "duration_s": it["secs"],
        "published": it["published"],
        "channel": "WTA (wtatennis.com)",
        "page_url": f"https://www.wtatennis.com/videos/{it['vid']}/{slug}",
        "round": rnd,
    }


def scan_wta(url: str, _depth: int) -> tuple[list[dict], str]:
    """wtatennis.com 的视频——WTA 那边对应 tennistv.com 的东西。

    两步：先读列表页拿到**当前最新的 ID**，再从那儿往回扫 `WTA_SWEEP_BACK`
    个 ID。只读列表页是不够的，理由见 `WTA_SWEEP_BACK` 上面那段。

    **收上来的一律是候选，不是场上采访。** 实测五条 `post-match-interview`
    里四条是 `WTA MEDIA` 深色背景板的坐访（便服、领夹麦、赛事台卡），
    只有雅典决赛那条真在场上。slug 分不出这两类，所以这个源登记
    `review_each`，看过画面才逐条放行——见注册表的 `_allow_ids_note`。

    **产量本来就低，这是 WTA 的出片规律，不是采集漏了。** 实测柏林决赛日
    那 280 个 ID 里只有 1 条采访，其余全是集锦；见到的是女王杯 R16、
    柏林 SF/F、雅典 F ——**基本只做到半决赛和决赛**。首轮的场上采访是
    **发生了但不发视频**：WTA 自己的战报写着「In her on-court interview,
    Samsonova stated: ...」（2026 华盛顿首轮），而同一天 wtatennis.com、
    @wta、Tennis Channel 上一条对应的视频都没有。

    **Brightcove 那条路走不通**：WTA 的视频托管在 Brightcove（account
    6041795521001），播放器 config 里能拿到 policy key，但目录搜索接口返回
    `ACCESS_DENIED` —— 那是 WTA 设的访问策略，只允许按 ID 播放单条，
    不允许列目录。不绕。
    """
    seen: set[str] = set()
    listed: set[str] = set()
    for page in ("videos", "videos/interviews", "videos/press-conferences"):
        try:
            proc = subprocess.run(
                ["curl", "-sS", "--compressed", "--max-time", "30",
                 "-H", "User-Agent: Mozilla/5.0", f"https://www.wtatennis.com/{page}"],
                capture_output=True, text=True, timeout=50)
        except subprocess.TimeoutExpired:
            continue
        for vid, slug in _WTA_SLUG.findall(proc.stdout):
            seen.add(vid)
            if _WTA_IS_INTERVIEW.search(slug):
                listed.add(vid)
    if not seen:
        return [], "error: 列表页一个视频链接都没取到"

    top = max(int(v) for v in seen)
    todo = sorted({str(v) for v in range(top - WTA_SWEEP_BACK, top + 1)} | listed)
    with ThreadPoolExecutor(WTA_SWEEP_JOBS) as ex:
        items = [it for it in ex.map(_wta_item, todo) if it]
    return [_wta_row(it) for it in items], f"ok（扫 {len(todo)} 个 ID）"


# ---------------------------------------------------------------- 哔哩哔哩

BILI_API = "https://api.bilibili.com/x/web-interface/wbi/search/type"
# 两次查询之间的间隔。**这是从限流实测倒推的，不是拍的**：连发四次之后
# 接口开始返回空列表，等 90 秒恢复。20 秒是留了余量的稳态节奏。
BILI_GAP_S = 20
# **金丝雀查询**：一个已知长期非空的词。见 `_bili_search` 上面那段。
BILI_CANARY = "网球 赛后采访"
CN_PLAYERS = ROOT / "data" / "cn_players.json"


def _bili_search(keyword: str) -> list[dict] | None:
    """搜一次。返回条目列表；**取不到就返回 None，绝不返回空列表**。

    这个区分是这个源的全部要害。B 站搜索接口被限流时返回的是

        {"code": 0, "message": "OK", "data": {"result": []}}

    ——**状态码是成功的，列表是空的**，和「这个词真的没有视频」一模一样。
    实测：同一个词几分钟前返回 8 条，连发几次之后返回 0 条，等 90 秒
    再查返回 20 条。仓库里栽过三次的「空结果 ≠ 不存在」，在这里连
    `code != 0` 这根救命稻草都没有。

    所以调用方必须靠 `_bili_alive()` 的金丝雀来判断这一轮到底算不算数。
    """
    url = (f"{BILI_API}?search_type=video&order=pubdate"
           f"&keyword={urllib.parse.quote(keyword)}")
    try:
        proc = subprocess.run(
            ["curl", "-sS", "--compressed", "--max-time", "25",
             "-H", "User-Agent: Mozilla/5.0",
             "-H", "Referer: https://www.bilibili.com", url],
            capture_output=True, text=True, timeout=45)
        data = json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, ValueError):
        return None
    if data.get("code") != 0:
        return None
    return (data.get("data") or {}).get("result") or []


def _bili_alive() -> bool:
    """金丝雀：一个已知长期非空的词还出不出结果。

    出——这一轮的空结果是真空；不出——被限流了，这一轮所有的零都不算数。
    **这就是「空结果先自证是真空」做成机制的样子**，不靠人记得去对一下。
    """
    return bool(_bili_search(BILI_CANARY))


def _bili_keywords() -> list[str]:
    """通用搜索词，登记在注册表的 `keywords` 字段里。"""
    for s in load_sources()["sources"]:
        if s.get("fetch") == "bilibili":
            return list(s.get("keywords") or [])
    return []


def _bili_row(r: dict) -> dict:
    """搜索结果 → 条目。标题里的 `<em>` 高亮标记要去掉。"""
    title = html.unescape(re.sub(r"<[^>]+>", "", r.get("title") or ""))
    mins, _, secs = (r.get("duration") or "0:0").partition(":")
    return {
        "id": f"bili:{r.get('bvid')}",
        "title": title,
        "duration_s": int(mins or 0) * 60 + int(secs or 0),
        "published": r.get("pubdate"),
        "channel": f"bilibili / {r.get('author')}",
        "page_url": f"https://www.bilibili.com/video/{r.get('bvid')}",
        "uploader": r.get("author"),
    }


def scan_bilibili(url: str, _depth: int) -> tuple[list[dict], str]:
    """B 站搜索——**中国球员那一档在别处根本拿不到的东西**。

    为什么值得单开一路：2026 华盛顿王欣瑜首轮赢球，做了场上采访
    （画面里她在场上、肩搭毛巾、手持话筒，背板 `WTA 500` / `MDE.TENNIS`
    / `TENNIS Channel`），但 wtatennis.com、@wta、Tennis Channel 的 YouTube、
    赛事官方频道**一条都没发**。唯一露头的地方是 B 站上中文转播方的赛事
    集锦包装片。而中国球员正是推送最看重的一档。

    找到的搬运号：`杂草小喵`（王欣瑜专号）、`TennisTube`、`网球视频尽快更新`、
    `爱网球的小土豆`、`北京网球教练张扬`、`家豹养成日志`。

    **按关键词搜，不按 UP 主枚举**：`x/space/wbi/arc/search` 返回
    `-403 访问权限不足`（要 WBI 签名 / cookie），搜索接口不用。

    两个坑：

    - **限流的空结果长得跟「没有」一模一样**，连 `code` 都是 0。所以每轮
      先放金丝雀，见 `_bili_search`。
    - **收上来的一律是候选**。B 站上的「赛后采访」至少有四类混在一起：
      场上采访、**央视/中文记者的混合区采访**（`杂草小喵` 的标题里直接写着
      「央视采访」）、演播室口播、集锦包装。标题分不出，只有画面能分——
      所以这个源和 wtatennis.com 一样登记 `review_each`。
      好在 B 站自己生成 10×10 的雪碧预览图（`x/player/videoshot`），
      **那是视频里的真实画面、up 主改不了**，正好是 YouTube `hq1/hq2/hq3`
      在 B 站这边的对应物。见 `tools/check_bili_frames.py`。
    """
    # **关键词不放在 `url` 字段里。** 每个源的 url 必须是个真地址，
    # 那条不变式挡过好几次「句柄写错了」（见 test_sources_registry_is_sane），
    # 为了省一个字段把它废掉不值当。
    words = list(_bili_keywords())
    if CN_PLAYERS.exists():
        with CN_PLAYERS.open(encoding="utf-8") as fh:
            words += [f"{p['zh']} 采访" for p in json.load(fh)["players"]]

    if not _bili_alive():
        return [], "rate-limited"

    rows: dict[str, dict] = {}
    for i, w in enumerate(words):
        if i:
            time.sleep(BILI_GAP_S)
        got = _bili_search(w)
        if got is None:
            return list(rows.values()), f"error: 第 {i + 1} 个词取不到（已收 {len(rows)}）"
        for r in got:
            if r.get("bvid"):
                rows[r["bvid"]] = _bili_row(r)
    # **收尾再放一次金丝雀。** 中途被限流的话，后面那些词的零是假的——
    # 只在开头查一次，会把「扫到一半被掐」报成「后面那些词没有内容」。
    if not _bili_alive():
        return list(rows.values()), f"rate-limited（中途被掐，已收 {len(rows)}）"
    return list(rows.values()), f"ok（{len(words)} 个词）"


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
    allow = compile_allow(cfg)
    deny = compile_deny(cfg)
    deny_ids = set(cfg.get("deny_ids", []))
    # 人工看图结论比标题/频道规则更硬。旧版只把 oncourt verdict 当“应该在库里”
    # 的正向证据，却没有把 press/ceremony/other 从库存中清出去；于是两条已经
    # 明确判错的素材仍带着 kind=oncourt 供下游选片。每轮都把非 oncourt 结论
    # 合并进出口黑名单，同时清理历史库存，规则才既管未来也管现在。
    try:
        verdicts = json.loads(VERDICTS.read_text(encoding="utf-8")).get("verdicts") or {}
    except (OSError, ValueError):
        verdicts = {}
    rejected_by_verdict = {
        vid for vid, verdict in verdicts.items()
        if verdict.get("verdict") not in ("oncourt", "unknown")
    }
    deny_ids |= rejected_by_verdict
    # `allow_ids` 是 `deny_ids` 的对称面，只对 `review_each` 的源起作用：
    # 那类源默认不收，看过画面确认在场上的才逐条放行。
    allow_ids = set(cfg.get("allow_ids", []))
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
    purged = sorted(set(known) & rejected_by_verdict)
    for vid in purged:
        known.pop(vid, None)
    new_items: dict[str, dict] = {}
    report: list[tuple[str, str, int, int, int, int]] = []
    dropped: list[tuple[str, str]] = []
    # review_each 的源里还没看过画面的，攒起来写进判定文件当队列。
    pending: dict[str, dict] = {}
    skipped: list[tuple[str, str, str]] = []
    any_fetched = False

    for src in sources:
        fetch = {"tennistv": scan_tennistv, "wta": scan_wta,
                 "bilibili": scan_bilibili}.get(src.get("fetch"), scan)
        depth = src.get("scan_depth", 150) if args.full else min(
            args.daily_depth, src.get("scan_depth", 150))
        rows, status = fetch(src["url"], depth)
        if rows:
            any_fetched = True

        fresh = n_oncourt = n_skipped = 0
        for r in rows:
            # tennistv 的 videoType=interviews + 有轮次，已经等价于场上采访，
            # 不能再拿标题正则去筛——它的标题是编辑体，一条都匹配不上。
            # assume_oncourt：整个频道都是场上采访，标题却不含 on-court /
            # post-match 字样。`Tennis Interviews` 就是这样——它写
            # `Lilli Tagger Champion Prague 2026`，靠标题正则一条都收不到，
            # 而它 234 条里覆盖了马德里 31、迈阿密 17、印第安维尔斯 9，
            # 全是官方缺口。这类源按源判，不按标题判。
            if (tail := src.get("tail_interview")) and _tail_interview(r, tail):
                # **采访藏在集锦片子的后半段里。** 判据是时长，见 `_tail_interview`。
                kind = "oncourt"
                r["tail_interview"] = True
            elif src.get("review_each"):
                # **这个源的 slug 分不出场合，只有画面能分。** wtatennis.com 的
                # `*-post-match-interview-*` 五条里四条是 `WTA MEDIA` 深色背景板的
                # 坐访（便服、领夹麦、赛事台卡），只有雅典决赛那条是真在场上
                # （WTA TOUR 手持话筒、球网、看台）。slug 里没有任何字段能分开这两类，
                # `-english` 两边都有。所以默认不算，看过图进 allow_ids 才算。
                # 反过来做（默认算、逐条拉黑）就是在没人看之前先把背景板推给读者。
                kind = "oncourt" if r["id"] in allow_ids else "maybe"
            elif r["id"].startswith("tennistv:") or src.get("assume_oncourt"):
                kind = "oncourt"
            elif any(p.search(r["title"]) for p in allow.get(src["name"], ())):
                # 按源的白名单：官方赛事频道标题太简，全局模式够不着。
                kind = "oncourt"
            else:
                kind = classify(r["title"], rules)
            if kind is None:
                continue
            # 综合体育频道要过网球闸：那里的 post-match interview 会命中
            # 足球、橄榄球等所有项目。被这道闸挡掉的也计进 dropped 报出来。
            if src.get("require_tennis") and not is_tennis(r["title"], rules):
                dropped.append((src["name"], f"[非网球] {r['title']}"))
                continue
            # 单源黑名单。有的官方频道把**发布会**也写成 post-match interview，
            # 标题正则永远分不出来——只有画面能分。这里放的是看图确认过的形状。
            if any(p.search(r["title"]) for p in deny.get(src["name"], ())):
                dropped.append((src["name"], f"[发布会] {r['title']}"))
                continue
            # 逐条拉黑。标题连**同一个源内部**都分不出来的时候，只剩这条路：
            # 巴黎大师赛有三条一字不差都叫 `Jannik Sinner post-match interview`，
            # 两条在场上、一条在媒体背景板前。写正则必错——我写过一版，
            # 25 条一起剔，其中 7 条是真场上的。
            if r["id"] in deny_ids:
                dropped.append((src["name"], f"[发布会·逐条确认] {r['title']}"))
                continue
            if kind == "excluded":
                # 被挡掉的也要报出来——只报通过的，没法证明筛子是对的。
                dropped.append((src["name"], r["title"]))
                continue
            if kind not in keep:
                # 是赛后讲话，但不是要的那一类（致辞 / 分不出场合）。
                n_skipped += 1
                skipped.append((src["name"], kind, r["title"]))
                if src.get("review_each"):
                    # **待看图的要留下来，不能每轮跑完就丢。** 报告里那一行
                    # 下一轮就没了，而 review_each 的源本来就指望人回来看画面；
                    # 记进判定文件的 unknown 档，才有一个能被 --recheck-unknown
                    # 接上的持久队列。
                    pending[r["id"]] = {
                        "verdict": "unknown", "title": r["title"],
                        "source": src["name"], "page_url": r.get("page_url", ""),
                    }
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
    if not args.dry_run and (any_fetched or purged):
        known.update(new_items)
        STORE.parent.mkdir(parents=True, exist_ok=True)
        with STORE.open("w", encoding="utf-8") as fh:
            json.dump({"items": known}, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        wrote = True
        if pending:
            # 已经有判定的不覆盖——人看过的结论比这里的 unknown 硬。
            with VERDICTS.open(encoding="utf-8") as fh:
                data = json.load(fh)
            fresh_q = {k: v for k, v in pending.items() if k not in data["verdicts"]}
            if fresh_q:
                data["verdicts"].update(fresh_q)
                with VERDICTS.open("w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=2)
                    fh.write("\n")

    if purged:
        print(f"[库存清理] 按人工 verdict 移除 {len(purged)} 条非场上采访："
              + "、".join(purged))

    # 报告：成功的和失败的都列出来。只在成功时出声的检查，没法证明它真的看过。
    mode = "全量（重扫历史）" if args.full else f"日常（每源 {args.daily_depth} 条）"
    print(f"模式：{mode}　收的类型：{'、'.join(sorted(keep))}\n")
    print(f"{'源':<34} {'状态':<20} {'取到':>5} {'场上':>5} {'跳过':>5} {'新增':>5}")
    print("-" * 82)
    for name, status, got, oncourt, skip, fresh in report:
        print(f"{name:<34} {status:<20} {got:>5} {oncourt:>5} {skip:>5} {fresh:>5}")

    # **判据是前缀，不是全等。** 状态里允许带括号说明（`ok（扫 906 个 ID）`），
    # 全等比对会把一个刚收了 5 条的源列进「没取到内容」，然后建议「换个时间再跑」。
    ok = lambda s: s.startswith("ok")            # noqa: E731
    bad = [r for r in report if not ok(r[1])]
    if bad:
        print("\n没取到内容的源（**不代表它们没有采访**）：")
        for name, status, *_ in bad:
            hint = {
                "handle-error": "句柄可能写错了，去 YouTube 搜赛事全名核对",
                }.get(status, "网络/限流，换个时间再跑")
            print(f"  - {name}：{status} —— {hint}")

    empty = [r for r in report if ok(r[1]) and r[3] == 0 and r[4] == 0]
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
