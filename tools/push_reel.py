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
import json
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


def wait_for_copy_page(url: str, expect: str = "", *, attempts: int = 30,
                       delay: float = 20.0, timeout: int = 15) -> None:
    """等 Pages 把**这一版**的复制页发出来，等不到就别推。

    `expect` 传这一版的标题：**只查 200 是不够的**。这个 URL 上一版就存在，
    Pages 还没重新发布时照样立刻返回 200，于是探活一次就过、推送照发，
    人点开复制到的还是上一版的标题和正文（2026-07-28 就是这么翻的车）。
    「打得开」是信号，「内容是这一版」才是产物。

    提交完到 Pages 重新发布之间有一两分钟，所以要等；但**等不到就必须报错**，
    不能带着一个指向旧内容的按钮把消息发出去——微信那条消息发出去就收不回来了。

    **预算给足。** 原来是 12 次 × 15 秒 = 3 分钟，2026-07-29 王欣瑜那条就是这么
    黄的：十二次全 404、exit 1、微信一个字没发出去，而复制页在这一步放弃之后
    才发布出来（我在沙箱里探到 200，内容正是那一版）。**「等不到」和「没等够」
    长得一模一样**，而两边的代价完全不对称——多等几分钟只是让 runner 空转，
    等不够就是整条推送作废、六分钟的渲染白跑。现在 30 次 × 20 秒 = 10 分钟。
    上限 `min(30, …)` 也跟着提到 60，否则环境变量调不上去。
    """
    attempts = max(1, min(60, int(os.environ.get("TENNISLIVE_COPYPAGE_ATTEMPTS",
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


def spec_of(copy_path: Path) -> dict:
    """`specs/reels/<slug>.xhs.txt` 旁边那份 `<slug>.json`。"""
    slug = copy_path.name.split(".")[0]
    spec = copy_path.parent / f"{slug}.json"
    if not spec.is_file():
        raise SystemExit(f"找不到 {spec}，取不到栏目名和推送元数据。要么放好 spec，"
                         "要么在命令行上把每一项都显式传齐")
    return json.loads(spec.read_text(encoding="utf-8"))


# 推送元数据里能从 spec 自己算出来的那几项，命令行只作覆盖。
_META_FIELDS = ("matchup", "score", "event", "summary", "lead")


def push_meta(copy_path: Path) -> dict:
    """推送元数据的出处是 spec，不是命令行。

    **对阵和比分本来就在 spec 里**：海报的两个名字读 `cover.versus.names`，
    比分读 `cover.result`。而工作流一直让人在 `--matchup "黄泽林 vs 布鲁克斯比"
    --score "6-1 7-5"` 里把同样两件事再打一遍——`column_of` 那条注释讲的
    「栏目只有一个出处」，在这两项上一直没做。

    两处写的代价不是抽象的：**这个工作流的输入默认值是上一条片子的**
    （`伊埃拉 vs 郑钦文` / `郑钦文首轮出局`），漏传一项就会拿另一场球的
    标题把这条片子发出去，而微信那条消息发出去就收不回来。

    还有一层：复制页（`--stage page`）和微信正文（`--stage push`）现在分在
    两次 run 里跑，`wait_for_copy_page(expect=title)` 要求两次算出**同一句
    标题**。从 spec 读就必然相同；靠人两次都把同样的参数敲对，不必然。

    `summary` / `lead` 是这条片子的编辑决定，算不出来，写在 spec 的 `push`
    块里。缺了不报错——没有 `summary` 就退回「对阵 + 比分」，那是 `headline`
    本来就支持的写法。
    """
    spec = spec_of(copy_path)
    cover = spec.get("cover") or {}
    names = [str(n).strip() for n in
             ((cover.get("versus") or {}).get("names") or []) if str(n).strip()]
    meta = {
        "matchup": " vs ".join(names[:2]) if len(names) >= 2 else "",
        "score": str(cover.get("result") or "").strip(),
        "event": "",
        "summary": "",
        "lead": "",
    }
    block = spec.get("push") or {}
    if not isinstance(block, dict):
        raise SystemExit(f"{copy_path.parent}/{copy_path.name.split('.')[0]}.json "
                         "的 push 不是一个对象")
    # `_` 开头的是写给下一个人的备注（仓库里到处都是 `_why`），不是字段。
    # 认不出来的字段要报错：写成 `sumary` 悄悄不生效，标题就退回「对阵 + 比分」，
    # 而那和「这条片子本来就没写 summary」长得一模一样。
    unknown = {k for k in block if not k.startswith("_")} - set(_META_FIELDS)
    if unknown:
        raise SystemExit(f"spec 的 push 块里有认不出来的字段：{sorted(unknown)}\n"
                         f"只认这几项：{list(_META_FIELDS)}")
    meta.update({k: str(v).strip() for k, v in block.items()
                 if not k.startswith("_")})
    return meta


def resolve_meta(copy_path: Path, args) -> dict:
    """spec 打底，命令行覆盖，**覆盖了要出声**。

    命令行留着是为了临时改一句标题不用先改 spec 再提交。但它一旦生效，
    复制页那次和推送那次就可能算出不同的标题（两次 run 之间参数敲得不一样），
    `wait_for_copy_page` 会等一句永远不出现的话——所以每次覆盖都印出来，
    真出这事的时候日志里看得见是谁改的。
    """
    meta = push_meta(copy_path)
    for field in _META_FIELDS:
        value = str(getattr(args, field, "") or "").strip()
        if value and value != meta[field]:
            print(f"[元数据] --{field} 覆盖了 spec：「{meta[field]}」→「{value}」")
            meta[field] = value
    if not (meta["matchup"] or meta["summary"]):
        raise SystemExit(
            "标题末尾那一格是空的：spec 里既没有 cover.versus.names（对阵），"
            "也没有 push.summary（一句话概括）。补一个再推——"
            "不带对阵的标题让人看不出这是哪一场。")
    return meta


def column_of(copy_path: Path) -> str:
    """栏目名从 spec 的 `cover.eyebrow` 读，别在命令行上另写一遍。

    **原来这儿默认 `赛场之上`，而工作流一个字都没传**——于是休伊特那条
    「网球有故事」的片子，海报台头印着网球有故事，微信标题却写赛场之上。
    同一条推送里两个栏目名，而推送发出去就收不回来。

    这是「栏目决定封面模板」那条的另一半：**栏目只有一个出处**，海报和标题
    都从它来。读不到就报错——悄悄退回一个默认值，正是上面那个错本身。
    """
    eyebrow = str((spec_of(copy_path).get("cover") or {})
                  .get("eyebrow", "")).strip()
    if not eyebrow:
        raise SystemExit(f"{copy_path} 对应 spec 的 cover.eyebrow 是空的——"
                         "海报台头印什么，标题就该写什么，这一个值两处共用")
    return eyebrow


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


def cut_at_tags(copy_text: str) -> str:
    """**文案到 tag 那一行为止，后面的一概不发。**

    账号所有者：「推送的正文复制文案里有不需要的东西，**tag 之后就不要了**」。

    `wong-brooksby.xhs.txt` 末尾挂着一段「素材来源（写给下一个人）」——写给
    仓库里的下一个人的备注，471 字，跟着正文一起进了微信推送和复制页。而复制页
    正是账号所有者往小红书粘贴的那个出口，等于把内部备忘发给读者。

    tag 行是小红书文案天然的结尾，判据不用另定：**最后一个 `#` 标签所在的行
    就是终点**。后面无论写了什么（素材来源、待办、分隔线），都是仓库的事。

    砍掉的**要打印出来**，不能默默吃掉——「兜底出事的时候不吭声」是这个仓库
    反复踩的那个坑。真有一天正文被误判砍掉，日志里看得见砍了什么。
    """
    lines = copy_text.splitlines()
    last = max((i for i, ln in enumerate(lines)
                if hashtag_count(ln)), default=-1)
    if last < 0 or not "\n".join(lines[last + 1:]).strip():
        return copy_text.strip()
    dropped = "\n".join(lines[last + 1:]).strip()
    head = dropped.splitlines()[0][:40]
    print(f"[文案] tag 之后还有 {len(dropped)} 字，不发：「{head}…」")
    return "\n".join(lines[:last + 1]).strip()


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
    ap.add_argument("--column", default="",
                    help="栏目名。默认不传——从 spec 的 cover.eyebrow 读，"
                         "海报印的是哪个栏目，标题就写哪个")
    # 这五项默认从 spec 读（对阵和比分就是海报用的那两个值，见 `push_meta`），
    # 命令行只作临时覆盖。原来 `--matchup` 是必填，于是工作流给它挂了个
    # 上一条片子的默认值——漏传一次就拿另一场球的标题发出去。
    ap.add_argument("--matchup", default="",
                    help="对阵，如「锦织圭 vs 商竣程」。默认取 cover.versus.names")
    ap.add_argument("--score", default="",
                    help="赛果，赢家在前。默认取 cover.result")
    ap.add_argument("--event", default="", help="赛事与轮次，如「华盛顿 ATP500 首轮」")
    ap.add_argument("--summary", default="",
                    help="一句话概括赛果，给了就顶掉标题末尾的「对阵 + 比分」")
    ap.add_argument("--lead", default="", help="正文那一句")
    ap.add_argument("--copy", required=True, help="小红书文案文件")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    # **两个 stage 共用这一处读**：复制页（`--stage page`）和微信正文
    # （`--stage push`）必须是同一段字，否则推送里印的和复制页里粘到的对不上。
    # 所以收口也收在这儿，别在下游各切一次。
    copy_text = cut_at_tags(Path(args.copy).read_text(encoding="utf-8"))
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
    meta = resolve_meta(Path(args.copy), args)
    title = headline(outdir, args.column or column_of(Path(args.copy)),
                     meta["matchup"], meta["score"], meta["event"],
                     meta["summary"])
    copy_text = f"{title}\n\n{copy_text}"
    page = outdir / "copy.html"
    copy_url = copy_page_url(outdir)

    if args.stage == "page":
        # **它不依赖成片**，只依赖 spec 里的文案和标题——所以这一步可以（而且
        # 应该）排在渲染**之前**跑并当场提交：Pages 的发布就和七分钟的渲染
        # 并行了。原来它排在渲染之后，提交完 Pages 才开始发布，推送那一步于是
        # 原地探 404 探掉四分钟（run 30624808733：连续 12 次 404，第 13 次才中）。
        page.parent.mkdir(parents=True, exist_ok=True)
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
