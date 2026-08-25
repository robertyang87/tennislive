#!/usr/bin/env python3
"""T0 探测：一场比赛打完，自动探测官方集锦视频的 YouTube URL。

这是「半小时出片协议」最前端一直缺的那一步——之前集锦上线后，账号所有者要
自己去 YouTube 搜 URL，再填进 match-reel 的 probe。这个工具把「搜」这一步
机械化，编进编排器之后，赛果一出来就能自动拿 URL → dispatch probe。

⚠️ 探测 = 拿 YouTube 搜索当信号源，**不是官方来源**：它只能回答「搜到一条像
集锦的结果」或「还没搜到」。搜到不代表就是官方集锦（可能是自媒体搬运），
「没搜到」也不代表不存在（可能是标题没带球员姓、或晚几分钟才传）。所以
产出的 URL 要交给人/下游 probe 再核一眼，别当成「官方集锦已上线」的铁证。

用法：
    python tools/detect_highlights.py --home Eala --away Pegula --event Washington --year 2026
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from oncourt_hunt import short_event  # noqa: E402

# 集锦标题里的关键词。宁可漏（"没搜到"）也不要错（拿一条无关视频当集锦）。
HIGHLIGHT_HINTS = re.compile(
    r"highlight|集锦|extended|full match|全场|highlights", re.I)

# 单场集锦的标题形状：`X vs Y …`。Day N 合集、球员特辑、Best points 这类
# 没有 ` vs `——合集切不出连续窗口，根本不能当源片（CLAUDE.md「合集不算一条源」）。
VS_RE = re.compile(r"\bvs\b", re.I)

# 官方频道白名单（小写比对）。三大官方之外还认**赛事自己的官方频道**
# （频道名里含赛事简称的每个词，如 `Cincinnati Open`）——那一档每站一个名字，
# 列不成常量，见 `channel_ok`。搬运号一律不收（CLAUDE.md「搬运号不算」）。
OFFICIAL_CHANNELS = frozenset({"atp tour", "tennis tv", "wta"})

# 超过 12 分钟按「Day N 合集 / 多场混剪」拒：官方单场集锦是 2~8 分钟，
# 12 分钟档的全是把好几场拼在一起的当日汇总（实测 Day 5 合集 12:03）。
MAX_HIGHLIGHT_SECONDS = 12 * 60

# 账号所有者 2026-08-18 定死：「视频一定要选 1080p 及以上的清晰度，
# 如果没有的话就等」——不分巡回赛、不分渠道的硬门槛。
MIN_SOURCE_HEIGHT = 1080


class HighlightSourceError(RuntimeError):
    """集锦搜索源不可用，而不是“搜索正常但还没有结果”。"""


def _cookie_args() -> list[str]:
    """Actions secret 落成文件后统一传给搜索和元数据探测。"""
    path = (os.environ.get("YT_COOKIES") or "").strip()
    return ["--cookies", path] if path and Path(path).is_file() else []


def query_for(home: str, away: str, event: str, year: int) -> str:
    """拼搜索词：两个球员姓 + 赛事简称 + 年份 + highlights。

    用姓不写全名——YouTube 标题里通常只有姓（`Eala vs Pegula`），写全名反而
    命中率低。赛事走 `short_event`（剥赞助商前缀）。
    """
    surname = lambda n: (n or "").strip().split()[-1]  # noqa: E731
    return f"{surname(home)} {surname(away)} {short_event(event)} {year} highlights"


def _opt(v: str | None) -> str | None:
    """yt-dlp `--print` 对缺字段吐 `NA`，当成「不知道」而不是一个值。"""
    v = (v or "").strip()
    return v if v and v != "NA" else None


def _dur(v: str | None) -> float | None:
    v = _opt(v)
    if v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def search(query: str, per: int = 6, timeout: int = 120) -> list[tuple]:
    """yt-dlp 的 ytsearch 拿 (title, url, channel, duration) 列表。

    正常空结果返回 []；超时、yt-dlp 非零退出和没安装都抛
    `HighlightSourceError`——它们是「搜索源不可用」，不是「集锦还没传」。
    编排器会让其他比赛继续探测/派发，再把整班标红并告警，既不互相阻塞，
    也不把基础设施故障伪装成安静的空结果。

    channel/duration 用同一次 `--print` 顺手带出来（flat 模式拿不到的字段是
    `NA`，解析成 None，留给 `vet_candidate` 对最终候选单独补一枪）。
    """
    try:
        proc = subprocess.run(
            ["yt-dlp", "--flat-playlist",
             *_cookie_args(),
             "--print", "%(title)s ||| %(webpage_url)s ||| %(channel)s ||| %(duration)s",
             f"ytsearch{max(1, min(per, 20))}:{query}"],
            capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise HighlightSourceError(
            "yt-dlp 没装——这不是「集锦还没发」，是环境错了：探测会每一班都"
            "安静地零候选。工作流里要 pip install \"yt-dlp[default]\""
            "（[default] 不能省，见 CLAUDE.md 装 yt-dlp 那条）。") from None
    except subprocess.TimeoutExpired as exc:
        raise HighlightSourceError(
            f"YouTube 搜索超过 {timeout}s——这是源站/网络故障，不是「集锦还没发」"
        ) from exc
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()
        tail = detail[-1][:300] if detail else "无 stderr"
        raise HighlightSourceError(
            f"YouTube 搜索失败（yt-dlp exit {proc.returncode}: {tail}）——"
            "这是源站/网络故障，不是「集锦还没发」")
    out = []
    for line in proc.stdout.strip().split("\n"):
        if " ||| " not in line:
            continue
        parts = line.split(" ||| ")
        if len(parts) < 2:
            continue
        title, url = parts[0].strip(), parts[1].strip()
        channel = _opt(parts[2]) if len(parts) > 2 else None
        duration = _dur(parts[3]) if len(parts) > 3 else None
        out.append((title, url, channel, duration))
    return out


def channel_ok(channel: str | None, event: str = "") -> bool:
    """频道在不在官方白名单：三大官方（`OFFICIAL_CHANNELS`）＋赛事自己的
    官方频道（频道名就是赛事简称，如 `Cincinnati Open`）。

    Merely *containing* the event word is not proof: ``Cincinnati Tennis Fan``
    must not inherit official status from the word Cincinnati.
    """
    c = (channel or "").strip().lower()
    if not c:
        return False
    if c in OFFICIAL_CHANNELS:
        return True
    tokens = lambda value: {  # noqa: E731
        w for w in re.findall(r"[a-z0-9]+", short_event(value).lower())
        if w not in {"official", "channel", "tv", "youtube"}
    }
    ev, channel_name = tokens(event or ""), tokens(channel)
    return bool(ev) and channel_name == ev


def pick_highlight(results: list[tuple], home: str, away: str,
                   event: str = "", year: int | None = None) -> str | None:
    """从搜索结果里挑一条像本场集锦的。判据**宁可窄**：标题要带集锦关键词、
    带两位球员的姓、带 ` vs `（单场的形状），**而且是这一站这一年的**——
    都满足才收（「没搜到」好过「拿错」）。

    ⚠️ **`event` / `year` 这两道是 2026-08-16 补的，补之前它真的拿错过一条。**
    实跑「商竣程 vs 索内戈 / Cincinnati / 2026」，它探回来的是

        Bublik Headlines; Sonego vs Shang; Khachanov & More | **Hong Kong 2026 Day 4** Highlights

    ——两位球员的姓都在、`Highlights` 也在，于是过关；而它是**另一站、另一个
    月份的当日综述片**，根本不是这场球。⚠️ **后果不是探不到，是探到一条错的**：
    编排器会拿这个 URL 去 dispatch probe，整条片子照着一场不相干的比赛渲出来，
    而记分条上写的是 Hong Kong——**流水线上没有任何一步会拦它**，只有人打开看
    才发现。

    两个不给的时候退回老行为（只查姓 + 关键词），因为**这个函数的老调用方
    不知道赛事**；生产路径 `find_highlight()` 一律把两个都传进来。

    条目可以是 (title, url) 或 (title, url, channel, duration)——搜索现在
    顺手带 channel/duration，**知道就当场筛**（搬运号 / Day N 合集），
    不知道（flat 模式给 NA）留给 `vet_candidate` 对最终候选补一枪。
    """
    hn = (home or "").strip().split()[-1].lower()
    an = (away or "").strip().split()[-1].lower()
    # 赛事名可能是多词的（`Hong Kong`），逐词都要在标题里——`short_event` 已经
    # 把赞助商前缀剥掉了，剩下的就是地名。
    ev = [w for w in short_event(event or "").lower().split() if w]
    for item in results:
        title, url = item[0], item[1]
        channel = item[2] if len(item) > 2 else None
        duration = item[3] if len(item) > 3 else None
        t = title.lower()
        if not (HIGHLIGHT_HINTS.search(t) and hn in t and an in t):
            continue
        if not VS_RE.search(title):
            continue                      # 没有 ` vs ` 的是合集/特辑，不是单场
        if ev and not all(w in t for w in ev):
            continue
        if year is not None and str(year) not in t:
            continue
        if channel is not None and not channel_ok(channel, event):
            continue                      # 认得出频道而不是官方 → 搬运号
        if duration is not None and duration > MAX_HIGHLIGHT_SECONDS:
            continue                      # 12 分钟以上按合集拒
        return url
    return None


def probe_meta(url: str, timeout: int = 120) -> tuple | None:
    """对最终候选跑一次 `yt-dlp --print`，拿 (channel, duration, height)。

    flat-playlist 搜索拿不到 height（channel/duration 也可能是 NA），所以
    选中之后要单独补一枪。⚠️ 会间歇性撞「Sign in to confirm you're not a
    bot」，重试一次通常就过（CLAUDE.md「要重试才算查过」）；两次都失败返回
    None——「探不到元数据」和「元数据不合格」是两回事，调用方分开处置。
    ⚠️ `--js-runtimes node` 不能省：runner 上不带它拿不到格式表
    （CLAUDE.md「记得带 --js-runtimes node」）。
    """
    cmd = ["yt-dlp", "--skip-download", "--js-runtimes", "node",
           *_cookie_args(),
           "--print", "%(channel)s ||| %(duration)s ||| %(height)s"
                      " ||| %(formats.:.height)s", url]
    for _ in range(2):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=timeout)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
        if proc.returncode != 0:
            continue
        line = proc.stdout.strip().split("\n")[-1] if proc.stdout.strip() else ""
        if " ||| " not in line:
            continue
        parts = line.split(" ||| ")
        ladder = _ladder(parts[3]) if len(parts) > 3 else []
        # ⚠️ **取整条格式表的最高档，不是默认选中那一档。**
        # `%(height)s` 报的是默认 format 选择器挑中的那一档；换个 player
        # client（有没有 cookies、有没有 PO token 都会换）挑法就变，同一条
        # 视频能报出完全不同的数。而这道闸问的是「这条源**有没有** 1080p」，
        # 那是格式表的属性，不是选中项的属性。取 max 两头都不亏：真有 1080p
        # 就认得出，格式表本来就被截断了 max 也还是低档，不会假装有。
        best = max(ladder) if ladder else None
        sel = _dur(parts[2]) if len(parts) > 2 else None
        height = best if best is not None else sel
        return (_opt(parts[0]), _dur(parts[1]), height, ladder)
    return None


def _ladder(v: str | None) -> list[float]:
    """`%(formats.:.height)s` 打出来的那串高度，解成一列数。

    yt-dlp 把列表渲成 `[360, 720, 1080]` 或 `[None, 360, ...]`（纯音频没有
    height）。**解不出来返回空列表，不抛**——它是诊断料，不许把探测带崩。
    """
    out: list[float] = []
    for tok in re.findall(r"\d+(?:\.\d+)?", _opt(v) or ""):
        try:
            out.append(float(tok))
        except ValueError:
            continue
    return out


def vet_candidate(url: str, event: str = "") -> tuple[str, str]:
    """终审最终候选：官方频道 / 时长 / 1080p。返回 (verdict, 一句人话)。

    verdict 三态，处置各不相同：
      ok      —— 用它
      reject  —— 这条本身不能用（搬运号 / 合集），照旧走备选链
      wait    —— **有集锦但先不用**（只有 720p / 元数据探不到），下一班再探。
                 ⚠️ 「有集锦但只有 NNNp，等 1080p」和「还没探到」必须是两句
                 不同的话——一个是等，一个是没有，读日志的人要分得开。
    """
    meta = probe_meta(url)
    if meta is None:
        return "wait", (f"  [vet] {url} 元数据探不到（重试过一次）——"
                        "先不用，下一班再探（这不是「还没探到集锦」）")
    channel, duration, height = meta[0], meta[1], meta[2]
    ladder = meta[3] if len(meta) > 3 else []
    if channel is not None and not channel_ok(channel, event):
        return "reject", (f"  [vet] {url} 频道「{channel}」不在官方白名单，"
                          "搬运号不用（三大官方 / 赛事官方频道才算）")
    if duration is not None and duration > MAX_HIGHLIGHT_SECONDS:
        return "reject", (f"  [vet] {url} 时长 {duration:.0f}s 超过 "
                          f"{MAX_HIGHLIGHT_SECONDS}s，像 Day N 合集不是单场集锦")
    if height is None or height < MIN_SOURCE_HEIGHT:
        got = f"{height:.0f}p" if height is not None else "读不出分辨率"
        # ⚠️ **把整条格式表打出来，别只报一个数。** 2026-08-25 撞到的：同一条
        # 视频（`Tvnwn11S4zo`），runner 上两趟相隔 35 分钟都报 360p，而沙箱
        # 同一时段读到 1080p——**「这条源真的只有 360p」和「我们这台机器只看得
        # 见 360p」在一个数上长得一模一样**，而两者的处置完全相反（一个是等，
        # 一个是这条链断了）。格式表分得开：只有 [360] 是被截断，
        # [144,240,360,720,1080] 里挑出 360 才是选择器的问题。
        rung = ("、".join(f"{h:.0f}p" for h in sorted(set(ladder)))
                if ladder else "读不出格式表")
        return "wait", (f"  [vet] {url} **有集锦但只有 {got}，等 1080p**"
                        "——这不是「还没探到」，是「先不用」（账号所有者 "
                        f"2026-08-18：没有 1080p 就等），下一班再探。"
                        f"整条格式表：{rung}"
                        "（只有低档 = 这台机器看不全，不是源片只有这些）")
    return "ok", ""


def tennistv_fallback(home: str, away: str, *, pages: int = 3) -> str | None:
    """YouTube 没搜到时，去 Tennis TV 的**免费短集锦**里找这一场。

    ⚠️ 这条只对 **ATP** 有货（Tennis TV 是 ATP 的平台），WTA 场次必然返回 None
    ——那不是故障，是这条源本来的覆盖范围。

    判据和 `pick_highlight` 一样**宁可窄**：slug 里要同时出现两位球员的姓。
    Tennis TV 的 slug 是 `<城市>-<年>-<轮次>-<甲>-<乙>-short-highlights`，
    姓的顺序按 ATP 的排法，和我们的 home/away 不一定一致，所以只查「都在」，
    不查先后。

    ⚠️ **取的是最近 N 页，不是全库**：这个函数服务的是「一场球刚打完」那一刻，
    而全库 58000 条翻不动。默认 3×100 条，够盖住好几天。
    """
    hn = (home or "").strip().split()[-1].lower()
    an = (away or "").strip().split()[-1].lower()
    if not hn or not an:
        return None
    try:
        from tennistv_catalog import (  # noqa: PLC0415
            TAG_SHORT_HIGHLIGHTS, is_real_short_highlight, rows, video_url,
        )
        items = rows(tag_ids=str(TAG_SHORT_HIGHLIGHTS), pages=pages)
    except (Exception, SystemExit) as exc:
        # 备选源失败不拖垮整批，但必须写 source-warning；否则它和
        # 「最近几页正常查完、没有这一场」长得一模一样。主路 YouTube 的
        # 故障由 HighlightSourceError 触发整班告警，Tennis TV 只作 ATP 备选，
        # 这里保留降级而不让 WTA 因一个不适用的备选源变红。
        #
        # ⚠️ **`SystemExit` 要单独列出来**：它继承的是 `BaseException` 不是
        # `Exception`，光写 `except Exception` 接不住。而 `tennistv_catalog._get`
        # 在接口回 HTML（参数名写错会 400）时抛的正是 `SystemExit`——那是给
        # 命令行准备的「说人话再退出」，被当成库用的时候就成了一颗炸弹。
        # 判据抓到过这个洞。
        print(f"  [source-warning] Tennis TV 备选源不可用（{type(exc).__name__}: "
              f"{exc}）——这不是『最近几页没有这一场』", file=sys.stderr)
        return None
    for item in items:
        if not is_real_short_highlight(item):
            continue
        slug = str(item.get("titleUrlSegment") or "").lower()
        if hn in slug and an in slug:
            return video_url(item)
    return None


def find_highlight(home: str, away: str, event: str, year: int,
                   *, per: int = 6) -> tuple[str | None, str]:
    """按账号所有者定的顺序找这一场的源片，返回 `(url, 走的哪条路)`。

        主路   YouTube（ATP Tour / Tennis TV / 赛事自己的官方频道都在搜索里）
        备选   Tennis TV 的免费短集锦
        都没有 → (None, "")

    ⚠️ **优先级链只有这一处实现。** 编排器和命令行都走它——写两处必分叉，
    而分叉的样子是「手动跑说探到了，自动班次说没探到」。

    挑中的 YouTube 候选要过 `vet_candidate` 终审（官方频道/时长/1080p）：
    reject（搬运号/合集）→ 这条本身不能用，照旧走备选链；
    **wait（720p / 元数据探不到）→ 直接返回 (None, "")，不退备选**——
    这一场明明有 YouTube 集锦、只是还不到 1080p，退到 Tennis TV 的 2 分半
    剪短版等于把「等 1080p」这道硬门槛悄悄换成一条更短的路；cron 30 分钟
    一班，等下一班就好。
    """
    url = pick_highlight(search(query_for(home, away, event, year), per=per),
                         home, away, event, year)
    if url:
        verdict, why = vet_candidate(url, event)
        if verdict == "ok":
            return url, "youtube"
        print(why)
        if verdict == "wait":
            return None, ""
        # verdict == "reject" → 继续走备选链
    url = tennistv_fallback(home, away)
    return (url, "tennistv-short") if url else (None, "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--home", required=True)
    ap.add_argument("--away", required=True)
    ap.add_argument("--event", required=True, help="赛事名，如 Washington")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--per", type=int, default=6)
    ap.add_argument("--no-fallback", action="store_true",
                    help="只探 YouTube，不查 Tennis TV 短集锦")
    args = ap.parse_args()

    q = query_for(args.home, args.away, args.event, args.year)
    print(f"搜索词：{q}")
    if args.no_fallback:
        # 和生产路径同一套闸（event/year/vet），只是不退备选——别让 CLI
        # 这条路悄悄放过生产路径会拦的候选。
        url = pick_highlight(search(q, per=args.per), args.home, args.away,
                             args.event, args.year)
        if url:
            verdict, why = vet_candidate(url, args.event)
            if verdict != "ok":
                print(why)
                url = None
        via = "youtube"
    else:
        url, via = find_highlight(args.home, args.away, args.event, args.year,
                                  per=args.per)
    if url:
        # **走了哪条路要说出来**，和「图片通道 pushplus / jsdelivr」同一条：
        # 一个月后有人问「这条片子的源是哪来的」，答案在当天的日志里。
        print(f"探到（{via}）：{url}")
        if via == "tennistv-short":
            print("  ⚠️ 这是 Tennis TV 的**免费短集锦**（定长 2 分半左右，"
                  "是被剪短的那一版）——YouTube 上没搜到这一场才走的它。")
        return 0
    print("还没探到：YouTube 没有一条同时带集锦关键词和两位球员姓，"
          "Tennis TV 最近几页的免费短集锦里也没有这一场。")
    print("集锦可能还没传，或标题写法对不上——晚几分钟再探。"
          "⚠️ WTA 场次没有 Tennis TV 这条备选，只有 YouTube 一条路。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
