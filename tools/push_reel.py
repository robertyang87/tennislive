#!/usr/bin/env python3
"""把竖版短片推到微信：成片链接 + 小红书标题文案（整段可复制）。

三件事是踩过坑之后定的：

- **复制页要在提交之前写，所以这个脚本分两段跑**。`--stage page` 只把
  `copy.html` 落进 outdir，由工作流的提交步骤带进仓库；`--stage push`（默认）
  才发微信。之前两件事挤在同一步里，而那一步排在提交**之后**——文件只存在于
  runner 的工作区，从来没被 commit 过，GitHub Pages 自然是 404
  （run 30342567879：推送步骤 success，链接打开 404）。**又一次「查信号不查产物」**

- **成片优先走 jsDelivr，超过 20 MB 只能回 raw**。`github.com/<repo>/raw/...`
  会 302 到 raw.githubusercontent.com，国内没有 CDN，下载慢——所以能走 jsDelivr
  就走。但 **jsDelivr 对单文件卡 20 MB**，超了直接
  `403 File size exceeded the configured limit of 20 MB`；1080×1920 / crf 18
  的七十秒成片是 35 MB，一次都过不去。`wait_for_images` 于是二十次探活全失败，
  整条推送被取消（run 30339377013）。**慢链接也比 403 强**，所以按文件大小选：
  ≤20 MB 用 jsDelivr，超了用 raw。别为了迁就 CDN 去压成片的画质
- **同一份文案只印一遍**。之前给推送加"可复制文案"时，正文印一遍、灰底复制块
  又印一遍，字符串断言全过，人一看整页才发现。所以正文只讲片子，
  文案只在复制块里出现一次

用法（两段，中间隔着工作流的 git commit）：

    python tools/push_reel.py --stage page --outdir output/2026-07-28/reel/… \\
        --matchup "锦织圭 vs 商竣程" --copy specs/reels/nishikori-shang.xhs.txt
    # …提交产物…
    python tools/push_reel.py --outdir output/2026-07-28/reel/… \\
        --matchup "锦织圭 vs 商竣程" --copy specs/reels/nishikori-shang.xhs.txt
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennislive.publish.pushplus import push  # noqa: E402
from tennislive.render.hashtags import (  # noqa: E402
    MAX_HASHTAGS,
    hashtag_count,
)
from tennislive.render.pushmsg import _PAGES, to_copy_page  # noqa: E402

REPO = os.environ.get("GITHUB_REPOSITORY", "robertyang87/tennislive")
# 日期从 outdir 里取（output/YYYY-MM-DD/...），别另传一个参数——两处日期
# 迟早会对不上，而目录名是产物自己的位置，不会说谎。
_DATE_IN_PATH = re.compile(r"/(\d{4})-(\d{2})-(\d{2})/")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
# jsDelivr 的 /gh/ 单文件上限。超过就是 403，不是慢，是打不开。
JSDELIVR_MAX_BYTES = 20 * 1024 * 1024
# 标题**整句**的上限，单位是小红书字位（全角 1、半角 0.5）。标题是给人扫的，
# 不是给人读的——和「卡片上每条不超过 16 字」同一个道理。
TITLE_MAX = 20
# 末尾那一格自己还有个上限，比整句更紧：前面的日期和栏目已经占掉七个多字位。
SUMMARY_MAX = 13
# 封面海报的文件名，和 `build_match_reel.POSTER_NAME` 是同一个。推送正文的
# 第一屏就是它——**没有它的推送只有两个按钮，看不出这是谁打谁**。
POSTER_NAME = "poster.jpg"


def video_url(outdir: Path, name: str) -> str:
    """成片链接：够小走 jsDelivr（国内快），超 20 MB 只能回 raw。"""
    size = (outdir / name).stat().st_size
    path = f"{outdir.as_posix()}/{name}"
    if size <= JSDELIVR_MAX_BYTES:
        return f"https://cdn.jsdelivr.net/gh/{REPO}@{BRANCH}/{path}"
    print(f"[链接] 成片 {size / 1e6:.1f} MB 超过 jsDelivr 的 20 MB 上限，改用 raw")
    return f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{path}"


def copy_page_url(outdir: Path) -> str:
    """复制页由 GitHub Pages 提供——raw 和 jsDelivr 都按纯文本发 .html，
    点开是一屏源码，按钮和 JS 都不会生效。"""
    return f"{_PAGES}/{outdir.as_posix()}/copy.html"


def wait_for_copy_page(url: str, expect: str = "", *, attempts: int = 12,
                       delay: float = 15.0, timeout: int = 15) -> None:
    """等 Pages 把**这一版**的复制页发出来，等不到就别推。

    `expect` 传这一版的标题：**只查 200 是不够的**。这个 URL 上一版就存在，
    Pages 还没重新发布时照样立刻返回 200，于是探活一次就过、推送照发，
    人点开复制到的还是上一版的标题和正文（2026-07-28 就是这么翻的车）。
    「打得开」是信号，「内容是这一版」才是产物。

    提交完到 Pages 重新发布之间有一两分钟，所以要等；但**等不到就必须报错**，
    不能带着一个指向旧内容的按钮把消息发出去——微信那条消息发出去就收不回来了。
    """
    attempts = max(1, min(30, int(os.environ.get("TENNISLIVE_COPYPAGE_ATTEMPTS",
                                                 attempts))))
    delay = max(0.0, min(60.0, float(os.environ.get(
        "TENNISLIVE_COPYPAGE_RETRY_SECONDS", delay))))
    want = html.escape(expect.strip())
    last = ""
    for attempt in range(attempts):
        try:
            response = requests.get(url, timeout=timeout,
                                    headers={"Cache-Control": "no-cache"})
            if response.status_code != 200:
                last = f"HTTP {response.status_code}"
            elif want and want not in response.text:
                # **这一支就是那次翻车**：URL 上一版就存在，Pages 还没重新发布，
                # 200 立刻到手（日志「第 1 次探活拿到 200」），推送照发，
                # 人点开复制到的还是上一版的标题和正文。
                last = "打得开，但还是上一版的内容（Pages 尚未重新发布）"
            else:
                print(f"[复制页] 第 {attempt + 1} 次探活：已是这一版的内容")
                return
        except requests.RequestException as exc:  # 网络抖动也算没起来
            last = f"{type(exc).__name__}: {exc}"
        print(f"[复制页] 第 {attempt + 1}/{attempts} 次探活 {last}，{delay:.0f}s 后重试")
        if attempt + 1 < attempts:
            time.sleep(delay)
    raise SystemExit(
        f"复制页 {url} 没等到这一版（{last}）。两种可能：copy.html 没被提交进仓库"
        "（它必须由 --stage page 在提交步骤之前写出来），或者 Pages 迟迟没发布。"
    )


def headline(outdir: Path, column: str, matchup: str, score: str = "",
             event: str = "", summary: str = "") -> str:
    """`7.28 赛场之上 | 华盛顿 ATP500 首轮 | 锦织圭 2:1 商竣程`。

    末尾那一格有两种写法，按这条片子哪种更说得清选：

    - **对阵 + 比分**（默认）。给了赛果就把「vs」换成比分——网球的写法本来就是
      赢家在前、比分居中，谁赢了不用再猜；没给赛果（比如赛前前瞻）就保留「vs」
    - **一句话概括赛果**（传 `summary`）。比分说不清的时候用，例如退赛、
      三盘大战里的某个转折、或者一条不以胜负为重点的片子

    两道字数闸门，超了直接报错，别让它悄悄溜出去：末尾那一格 `SUMMARY_MAX`，
    整句 `TITLE_MAX`（见 `_fits`）。**讲不完的不要硬塞进标题**——用 `--lead`
    放到正文第一行去详细概括，那儿有的是地方。
    """
    found = _DATE_IN_PATH.search(f"/{outdir.as_posix()}/")
    if not found:
        raise SystemExit(f"从 {outdir} 里取不到日期，目录该长成 output/YYYY-MM-DD/…")
    _, month, day = found.groups()
    if summary.strip():
        pair = summary.strip()
        if len(pair) > SUMMARY_MAX:
            raise SystemExit(
                f"标题末尾那句 {len(pair)} 字，超过 {SUMMARY_MAX} 字：{pair}\n"
                "标题是给人扫的，不是给人读的——提炼到一个最硬的事实上。"
            )
    else:
        pair = matchup.replace(" vs ", f" {score} ") if score and " vs " in matchup \
            else (f"{matchup} {score}".strip() if score else matchup)
    parts = [f"{int(month)}.{int(day)} {column}"]
    if event:
        parts.append(event)
    parts.append(pair)
    return _fits(" | ".join(parts))


def _fits(title: str) -> str:
    """标题**整句**不超过 20 个汉字，超了直接报错。

    账号所有者的原话：「标题控制在 20 个汉字内，言简意赅直达重点，精炼内容。
    讲不完的放到副标题，可以放到正文第一行，详细总结概括。」

    所以这里卡的是**整句**，不是末尾那一格——以前只卡 `summary` 的 20 字，
    前面还挂着日期、栏目、赛事轮次，加起来 25 个字位，通知栏里根本读不完。

    量的是**小红书的字位**（`xhs_title_len`：全角记 1，半角记 0.5），不是
    `len()`。「7.29 」五个半角只占 2.5 个字位，按 `len()` 算会白白吃掉两格。
    两处用同一把尺，标题才不会在这儿过、到小红书又超。

    讲不完的那半句交给 `--lead`——它就印在正文第一行，位置正好。
    """
    from tennislive.render.xiaohongshu import xhs_title_len  # noqa: PLC0415

    width = xhs_title_len(title)
    if width > TITLE_MAX:
        raise SystemExit(
            f"标题 {width:g} 个字位，超过 {TITLE_MAX}：{title}\n"
            f"（半角算半个字位；日期+栏目已经占掉 "
            f"{xhs_title_len(title.split(' | ')[0]) + 1.5:g} 个）\n"
            "标题只留最硬的那个结果，剩下的用 --lead 放到正文第一行去详细概括。")
    return title


def split_copy(copy_text: str) -> tuple[str, str]:
    """文案的第一行是标题，空一行之后是正文——和 `to_copy_page` 同一套切法。

    两处必须用同一套，否则推送里印的和复制页里复制到的会不是同一段。
    """
    lines = copy_text.splitlines()
    title = lines[0].strip() if lines else ""
    start = 2 if len(lines) > 1 and not lines[1].strip() else 1
    return title, "\n".join(lines[start:]).strip()


def poster_url(outdir: Path, name: str = POSTER_NAME) -> str:
    """封面海报的图片链接。海报只有几百 KB，稳走 jsDelivr。"""
    return f"https://cdn.jsdelivr.net/gh/{REPO}@{BRANCH}/{outdir.as_posix()}/{name}"


def build_html(video_url: str, copy_url: str, lead: str, copy_text: str,
               poster: str = "") -> str:
    """推送正文，**版式照着知识解说那条推送**（账号所有者指定的参照）：

        白卡（顶上一条 #ff2442 红边）
          台头小药丸  →  大标题
          海报，**铺满整卡宽，左右不留白边**
          「图片没显示？点此打开原图」
          「👇 正文全文如下，长按整段即可复制」
          正文（pre-wrap，一整段）
          ── 分隔线 ──
          ▶ 打开竖版成片
          分别复制标题 / 正文
          图片长按保存

    两处和参照不同，都是这条线自己的教训：

    - **海报要铺满**。参照里那几张 slide 是 3:4 的卡片图，缩在 16px 内边距里
      正好；海报是这条片子的第一眼，账号所有者的原话是「海报要铺满全屏的」。
      所以白卡的 `padding` 拆开写——文字块各自带左右内边距，海报单独一行
      顶到卡边。用负 margin 抵消内边距在微信里不可靠，**结构上让它没有内边距**
    - **同一段只印一遍**。以前正文印一遍、灰底复制块又印一遍，字符串断言全过，
      人一看整页才发现。「分开复制」交给复制页——微信里放不了能点的 JS 按钮
    """
    title, body = split_copy(copy_text)
    pad = "padding:0 16px"
    # **导语给空就不占那一行。** 详细概括现在写在文案正文的第一行（账号所有者的
    # 要求：标题精炼，讲不完的放正文第一行详细总结），导语再印一遍同样的意思
    # 就是「同一段印两遍」那个老毛病。
    lead_el = (f'<div style="font-size:15px;line-height:1.8;color:#25342e;'
               f'margin:0 0 14px">{html.escape(lead.strip())}</div>'
               if lead.strip() else "")
    img = ""
    if poster:
        img = (f'<img src="{poster}" width="100%" alt="{html.escape(title)}"'
               f' referrerpolicy="no-referrer"'
               f' style="width:100%;display:block;margin:0 0 10px">'
               f'<div style="text-align:center;margin:0 0 16px;{pad}">'
               f'<a href="{poster}" style="color:#087747;font-size:13px;'
               f'text-decoration:none">封面没显示？点此打开原图</a></div>')

    def btn(url: str, text: str, bg: str, fg: str = "#ffffff") -> str:
        return (f'<a href="{url}" style="display:block;background-color:{bg};'
                f'color:{fg};text-align:center;text-decoration:none;'
                f'font-weight:bold;padding:13px 16px;border-radius:6px;'
                f'margin:0 0 7px">{text}</a>')

    return f"""<div style="background-color:#f6f7f4;color:#17251f;padding:12px 10px;\
font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">
<div style="max-width:680px;margin:0 auto;background-color:#ffffff;\
border-top:5px solid #ff2442;padding:18px 0 22px">
<div style="{pad}"><div style="display:inline-block;background-color:#e7f5ea;\
color:#087747;font-size:12px;font-weight:bold;padding:4px 8px;border-radius:4px">\
赛场之上</div>
<div style="font-size:23px;line-height:1.38;font-weight:800;color:#102d23;\
margin:10px 0 14px">{html.escape(title)}</div></div>
{img}
<div style="{pad}">
{lead_el}
<div style="color:#7a8580;font-size:12px;margin:0 0 8px">\
👇 正文全文如下，长按整段即可复制</div>
<div style="font-size:15px;line-height:1.85;white-space:pre-wrap;\
word-break:break-word;margin:0 0 4px">{html.escape(body)}</div>
<div style="border-top:1px solid #e6ebe8;margin:18px 0 12px"></div>
{btn(video_url, "▶ 打开竖版成片", "#102d23")}
{btn(copy_url, "分别复制标题 / 正文", "#ff2442")}
<div style="text-align:center;color:#7a8580;font-size:12px">图片长按保存</div>
</div></div></div>"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stage", choices=("page", "push"), default="push",
                    help="page=只写复制页（须排在 git commit 之前）；push=发微信")
    ap.add_argument("--outdir", required=True, help="成片所在目录（仓库相对路径）")
    ap.add_argument("--video", default=None, help="成片文件名，默认取目录里唯一的 mp4")
    ap.add_argument("--column", default="赛场之上", help="栏目名")
    ap.add_argument("--matchup", required=True, help="对阵，如「锦织圭 vs 商竣程」")
    ap.add_argument("--score", default="", help="赛果，如「6-7(3) 6-3 6-4」，赢家在前")
    ap.add_argument("--event", default="", help="赛事与轮次，如「华盛顿 ATP500 首轮」")
    ap.add_argument("--summary", default="",
                    help="一句话概括赛果，给了就顶掉标题末尾的「对阵 + 比分」")
    ap.add_argument("--lead", default="", help="正文那一句")
    ap.add_argument("--copy", required=True, help="小红书文案文件")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    copy_text = Path(args.copy).read_text(encoding="utf-8").strip()
    if not copy_text:
        raise SystemExit("文案是空的")
    # **正文里的 tag 最多五个**，和知识帖那条线共用同一个上限。
    # reel 的文案是手写的 spec，不像知识帖那样过 `limit_hashtags`，所以在这儿
    # 拦一道——**发出去就收不回来**，宁可在推送之前报错。
    tags = hashtag_count(copy_text)
    if tags > MAX_HASHTAGS:
        raise SystemExit(
            f"{args.copy} 里有 {tags} 个 tag，超过 {MAX_HASHTAGS} 个。\n"
            "删到五个以内再推——留最能被搜到的那几个（人名、赛事、账号）。")

    # 格式化标题（`7.28 赛场之上 | 华盛顿 ATP500 首轮 | 锦织圭 2:1 商竣程`）
    # **就是这条帖子的标题**：微信通知栏、推送正文顶部、复制页那一格，三处同一句。
    # 代价是它比小红书 20 字的上限长，发小红书时要自己删短；文案里原来那句钩子
    # 退成正文第一行。这是口径选择，不是 bug——问过了，选的就是这样。
    title = headline(outdir, args.column, args.matchup, args.score, args.event,
                     args.summary)
    copy_text = f"{title}\n\n{copy_text}"
    page = outdir / "copy.html"
    copy_url = copy_page_url(outdir)

    if args.stage == "page":
        page.write_text(to_copy_page(copy_text), encoding="utf-8")
        print(f"已写复制页：{page}（{len(copy_text)} 字）\n  发布后是 {copy_url}\n"
              "  这一步必须排在 git commit 之前，否则它进不了仓库。")
        return 0

    name = args.video
    if not name:
        mp4s = sorted(p.name for p in outdir.glob("*.mp4"))
        if len(mp4s) != 1:
            raise SystemExit(f"{outdir} 里有 {len(mp4s)} 个 mp4，用 --video 指明是哪个")
        name = mp4s[0]
    if not (outdir / name).is_file():
        raise SystemExit(f"找不到成片 {outdir / name}")
    if not page.is_file():
        raise SystemExit(f"{page} 不在——先跑一次 --stage page，且要排在提交之前")

    # 查产物，不查信号：Pages 真的把它发出来了才发微信。
    wait_for_copy_page(copy_url, title)

    url = video_url(outdir, name)
    # 海报没进仓库就别硬塞一个链接进去——那就是「推送正文里的每个链接，
    # 指向的文件都必须在推送之前进仓库」那条踩过两次的规矩。缺了就退回无图版，
    # 并且**说出来**，别让它悄悄少一屏。
    poster = ""
    if (outdir / POSTER_NAME).is_file():
        poster = poster_url(outdir)
    else:
        print(f"[封面] {outdir / POSTER_NAME} 不在，这次推送没有海报那一屏")
    body = build_html(url, copy_url, args.lead, copy_text, poster)
    push(title, body, asset_dir=outdir)
    print(f"已推送：{title}\n  成片 {url}\n  复制页 {copy_url}\n"
          f"  文案 {len(copy_text)} 字")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
