#!/usr/bin/env python3
"""源片地址和 probe／cookies 表单的入参自检——**第一步就红，别等源片下完**。

2026-09-28 返工审计（三条线 09-20~09-28 的 82 趟失败 run）里，有三趟红得毫无必要，
全是**表单填错了**，却都要等到装完依赖、起完 PO token、真去下载那一刻才报：

| run | 表单 | 红在哪儿、报的是什么 |
|---|---|---|
| 36304133786 | `mode=probe`，`url` 空着，`slug` 还是表单默认 `eala-zheng` | 第 1.4 分钟，`curl: (3) URL rejected: Malformed input`——看不出是「没填」 |
| 35478525370 | `mode=cookies`，`url` 填的是 `ytsearch8:Davis Cup 2026 …` 搜索词 | 搜出 0 条，报「没下到媒体流，原因见下面的格式表」——看着像 cookie 坏了 |
| 36331431180 / 36333879418 | `--scorebox 98,920,519,1029`（1080p 量的框）配一条 720p 源 | 源片下完才炸（cv2 `!_src.empty()` / ReelError），整趟 probe 产物一个字节没提交 |

前两类表单本身就能判，**一行字符串检查**；第三类要源片的高度，下完才知道——
那一半在 `build_match_reel.fit_scorebox_to_frame`（按高度缩放，缩不进就退回猜的框），
这儿只管格式（写成 `x0,y0,x1,y1`、`x0<x1`、`y0<y1`），格式错的照样第一步红。

⚠️ **只用标准库**：工作流在 `actions/setup-python` 和装依赖**之前**跑它（系统
python3），越早红越便宜。`build_match_reel.py` 也从这儿 import X 地址那两个判断
（`is_x_status_url` / `is_x_cdn_url`）——同一个判断只许有一份。

用法::

    python3 tools/source_url_check.py --mode probe --url URL --slug SLUG [--scorebox B]
    python3 tools/source_url_check.py --mode cookies --url URL
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/match-reel.yml"

#: `x.com/<账号>/status/<数字>`（也认 twitter.com / mobile.twitter.com / 带 `/video/1` 尾巴的）
_X_STATUS = re.compile(r"^/[A-Za-z0-9_]{1,50}/status/\d{5,25}(?:/(?:video|photo)/\d+)?/?$")
_X_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com",
            "mobile.twitter.com", "mobile.x.com"}
#: X 的视频 CDN：`video.twimg.com/amplify_video/<媒体 id>/vid/...mp4`、`ext_tw_video/...`
_X_CDN_HOSTS = {"video.twimg.com"}
#: yt-dlp 的搜索前缀（`ytsearch8:…`、`ytsearchdate:…`、`scsearch:…`）——它是查询词，不是一条视频
_SEARCH_PREFIX = re.compile(r"^[a-z]{2,12}search[a-z]*\d*:", re.IGNORECASE)


def is_x_status_url(url: str) -> bool:
    """X 的帖子地址。下载那一刻交给 yt-dlp 现解出 CDN 直链（见 `build_match_reel.download`）。"""
    parsed = urlparse(str(url or "").strip())
    return (parsed.scheme in ("http", "https")
            and parsed.netloc.lower() in _X_HOSTS
            and bool(_X_STATUS.match(parsed.path)))


def is_x_cdn_url(url: str) -> bool:
    """X 的视频 CDN 直链（`video.twimg.com/...`）。**它会失效**：jl-lc-eurosport /
    jl-tabilo-bag（run 36231247557 / 36231253272）两条 1920×1080 直链
    `curl: (22) … 403`，2026-09-28 沙箱复测仍是 403，而同一批另外两条直链是 206。"""
    parsed = urlparse(str(url or "").strip())
    return parsed.scheme in ("http", "https") and parsed.netloc.lower() in _X_CDN_HOSTS


def url_problem(url: str, *, allow_empty: bool = False) -> str | None:
    """这串东西是不是一个能交给下载器的 http(s) 地址。是就返回 None。"""
    text = str(url or "")
    if not text.strip():
        return None if allow_empty else "`url` 是空的——probe 要下的源片地址没填"
    if _SEARCH_PREFIX.match(text.strip()):
        return (f"`url` 是 yt-dlp 的搜索词（{text.strip()[:80]}），不是一条视频——"
                "搜到 0 条和「被挡了」长得一模一样；先在本地搜出那条视频的 watch 地址再填")
    if text != text.strip() or any(ch.isspace() for ch in text):
        return f"`url` 里有空白字符（{text!r}）——多半是把标题或两个地址一起粘进来了"
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return f"`url` 不是 http(s) 地址（{text[:80]}）"
    return None


def scorebox_problem(scorebox: str) -> str | None:
    """`--scorebox` 的**格式**：四个非负整数 `x0,y0,x1,y1`，x0<x1、y0<y1。空串＝没给，合法。

    格式之外的「框落在画面外」要源片高度才判得了，那一半在
    `build_match_reel.fit_scorebox_to_frame`（下完源片之后、量死球之前）。"""
    text = str(scorebox or "").strip()
    if not text:
        return None
    parts = [p.strip() for p in text.split(",")]
    try:
        box = [int(p) for p in parts]
    except ValueError:
        box = []
    if len(box) != 4 or any(v < 0 for v in box):
        return f"`scorebox` 要写成 x0,y0,x1,y1（源片像素、非负整数），给的是「{text}」"
    if box[0] >= box[2] or box[1] >= box[3]:
        return f"`scorebox` {text}：要 x0<x1、y0<y1（左上角在前、右下角在后）"
    return None


def form_default(field: str, workflow_text: str | None = None) -> str | None:
    """match-reel.yml 表单里 `field` 这一项的 `default:`。纯文本解析，不引 yaml
    （第一步跑在装依赖之前）。判据 `test_表单默认slug读的就是yml里那一份` 拿 yaml 对账。"""
    text = workflow_text if workflow_text is not None else WORKFLOW.read_text(encoding="utf-8")
    inputs = text.split("\n    inputs:\n", 1)[-1].split("\npermissions:", 1)[0]
    block = re.search(rf"^      {re.escape(field)}:\n((?:        .*\n|\s*\n)+)", inputs, re.M)
    if not block:
        return None
    m = re.search(r'^        default:\s*"?([^"\n]*)"?\s*$', block.group(1), re.M)
    return m.group(1) if m else None


def probe_problems(url: str, slug: str, scorebox: str = "", *,
                   default_slug: str | None = None) -> list[str]:
    """mode=probe 的表单：地址要填、要是地址；slug 不许还是表单默认值；框格式要对。"""
    out = []
    problem = url_problem(url)
    if problem:
        out.append(problem)
    if default_slug and str(slug).strip() == default_slug:
        out.append(
            f"`slug` 还是表单默认值「{default_slug}」——那是 2026-07 已经发过的老片子"
            f"（specs/reels/{default_slug}.json），probe 产物会落到它名下。"
            "按 <姓>-<姓>-<赛事>-<年>-<轮次> 起一个这场球自己的 slug")
    box = scorebox_problem(scorebox)
    if box:
        out.append(box)
    return out


def probe_warnings(url: str) -> list[str]:
    """不拦、但要出声的：X 的 CDN 直链会失效。"""
    if is_x_cdn_url(url):
        return ["`url` 是 X 的 CDN 直链（video.twimg.com）——这种链接会失效（审计里两条 403）。"
                "下次填 x.com/<账号>/status/<id> 帖子地址，下载那一刻由 yt-dlp 现解，"
                "竖版也拿得到原画（见 tennis-media-sources「X 和 Instagram 是第一手源」）"]
    return []


def cookies_problems(url: str) -> list[str]:
    """mode=cookies：`url` 可以空（用自检的默认视频），填了就必须是一条视频的地址。"""
    problem = url_problem(url, allow_empty=True)
    return [problem] if problem else []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--mode", required=True, choices=["probe", "cookies"])
    ap.add_argument("--url", default="")
    ap.add_argument("--slug", default="")
    ap.add_argument("--scorebox", default="")
    args = ap.parse_args(argv)
    if args.mode == "probe":
        problems = probe_problems(args.url, args.slug, args.scorebox,
                                  default_slug=form_default("slug"))
        for warning in probe_warnings(args.url):
            print(f"::warning::{warning}")
    else:
        problems = cookies_problems(args.url)
    for problem in problems:
        print(f"::error::{problem}")
    if problems:
        print(f"表单自检没过（mode={args.mode}）：{len(problems)} 处——"
              "这一趟不装依赖、不下源片，第一步就停。")
        return 1
    print(f"表单自检通过（mode={args.mode}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
