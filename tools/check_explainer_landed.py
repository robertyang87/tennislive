#!/usr/bin/env python3
"""这一版成片到底落库了没有——查产物本身，不查信号。

判断一次 Actions 生成有没有真的落地，间接信号全部骗过人：

- **提交信息**：每次生成的 commit message 一字不差，grep 到了什么也说明不了。
- **文件路径变了**：一个在改动之前开跑、改动之后才落库的 run 也会让路径变化，
  它推上去的是旧内容，检查却报绿。
- **逐字节比对**：太严。CI 和沙箱的 PNG 编码有时差几千字节（7586726 / 7586670），
  内容一模一样也报红，于是判据永远不会绿，看起来和「还没落地」一样。

所以这里做两件事，都直接看产物：

1. **文案**：给定的句子在不在 —— 而且**不指定文件**，整个目录里的文本一起找，
   并报出它在哪个文件里命中。踩过这个坑：封面那句只出现在 `wechat_title.txt`，
   我拿它去 `xiaohongshu.txt` 里找，报了「尚未落地」，其实早就落好了。
2. **画面**：取某一屏的一条横带算平均色，和本地渲染的同一条带比。编码差异不影响
   平均色，换没换图一比就知道（换过图的偏差在 45～70，同图在 0.1 以内）。

用法：
    # 只查文案（已经落库的那一版，从 git ref 读）
    python tools/check_explainer_landed.py zheng-eala --says 钦文还在打 祝钦文好运
    # 刚渲完、还没提交的这一版（从工作区读）——工作流里的闸走的是这条
    python tools/check_explainer_landed.py --local output/2026-08-14/explainer/hawkeye \
        hawkeye --says 球压没压线
    # 连画面一起查（先在本地渲一份做参照）
    python tools/check_explainer_landed.py --local output/2026-08-14/explainer/zheng-eala \
        zheng-eala --says 祝钦文好运 --slide 5 --against /tmp/ze/slide_05.png

退出码 0＝全部对上；2＝有对不上的。缺什么、差多少都打印出来。

⚠️ **`--says` 喂每屏的小标，别喂旁白原文。** 字幕（`.ass`）去过标点
（「字幕里不写标点」那条规矩）也换过数字（`arabic_numerals`），词边界
（`.words.json`）本来就不含标点——**旁白原文因此几乎搜不到**，而搜不到报出来是
「★ 一个文件都没有」，**和「这一版没落库」长得一模一样**，正是这个脚本存在的
全部理由要防的东西。

2026-08-14 拿存量 39 条 deck、243 屏量过（不是推的）：

    每屏小标         命中 241 / 243   两条落差都是脚本后来改过（drift）
    旁白前 14 字     含标点的 228 条命中 7；不含标点的 15 条也只命中 7

小标不带句末标点，而且 `copy.html` / `push.html` / `xiaohongshu.txt` 三份文案
里都有，所以它是这条线上唯一稳的那个抓手。
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# 产物目录用的是工作流里的 `TZ=Asia/Shanghai date +%F`，不是本机日期。
# 沙箱跑在 UTC，所以每天 16:00 UTC 之后两者差一天——查 2026-07-26 查了半天
# 「产物还没落库」，其实它安安静静躺在 2026-07-27 里。空结果先自证是真空。
def _outdir_date() -> str:
    return datetime.now(timezone(timedelta(hours=8))).date().isoformat()

# ⚠️ `.ass` 是 2026-08-03 补的：字幕**就是烧在画面上的那行字**，是「这一版
# 落没落库」最直接的证据，而它以前一直不在这张表里——查一句只出现在字幕里的
# 话，报出来是「★ 一个文件都没有」，和「没落库」一模一样。
TEXT_SUFFIXES = (".txt", ".html", ".json", ".md", ".ass")
# 取哪一条横带：上下各留出一截，避开页眉和底部文字块。
BAND = (0.05, 0.55, 0.95, 0.80)
TOLERANCE = 0.02  # 网格距离，不是色差


def _git(ref: str, rel: str) -> bytes:
    return subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:{rel}"],
                          capture_output=True).stdout


def _ls(ref: str, d: str) -> list[str]:
    out = subprocess.run(["git", "-C", str(REPO), "ls-tree", "--name-only", f"{ref}:{d}"],
                         capture_output=True).stdout.decode()
    return [line.strip() for line in out.splitlines() if line.strip()]


def _grid(im, n: int = 48) -> list[float]:
    """把整屏降成 n×n 的 RGB 网格。

    原来这里取的是某一条横带的平均色。那个判据两次给出假绿：连败那一屏从
    文字表格换成条形图、又换了配色，整屏平均亮度几乎没变，判据看不出差别，
    照样报「已落地」。平均值对版式不敏感——降成网格再比才看得见谁在哪儿。

    按 RGB 存，不转灰度。转灰度又栽了一次：连败图那两版差别主要在颜色（莎粉
    换成中性白），而这两个颜色压在深绿底上**亮度几乎相同**，灰度网格读不出换色。
    """
    g = im.convert("RGB").resize((n, n))
    return [v / 255 for v in g.tobytes()]


def _dist(a: list[float], b: list[float]) -> float:
    return (sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)) ** 0.5


def _reader(args):
    """产物从哪儿读——git ref 上那一版，还是工作区里刚渲完的这一版。

    ⚠️ **两条路问的是两个问题，不能混。** git ref 那条回答「已经落库的那一版
    是不是这一版」（本文件开头那几条教训说的就是它）；`--local` 那条回答
    「刚渲完的这一版本身合不合格」。

    `--local` 是 2026-08-14 把这个脚本接进 `explainer.yml` 时补的，**没有它
    这道闸装不上**：闸必须排在提交之前（进了 main，`publish pushplus` 就会把
    它发到微信，而消息发出去收不回来），可那一刻 outdir 一个字节都还没进 git，
    拿默认的 `origin/main` 去查，报出来是「在 origin/main 上还不存在」——
    **那句话的意思是「还没提交」，不是「不合格」**。

    返回 (这一版在哪儿, 列文件, 读一个文件)。
    """
    if args.local:
        root = Path(args.local)

        def ls() -> list[str]:
            return sorted(p.name for p in root.iterdir()) if root.is_dir() else []

        def read(name: str) -> bytes:
            p = root / name
            return p.read_bytes() if p.is_file() else b""

        return f"{root}（工作区）", ls, read

    outdir = f"output/{args.date}/explainer/{args.slug}"
    return (f"{outdir}（{args.ref}）",
            lambda: _ls(args.ref, outdir),
            lambda name: _git(args.ref, f"{outdir}/{name}"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    ap.add_argument("--says", nargs="*", default=[], help="必须出现在产物里的句子")
    ap.add_argument("--date", default=_outdir_date())
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--slide", type=int, help="要比对画面的那一屏序号，如 5")
    ap.add_argument("--against", help="本地渲染的同一屏 PNG，作为参照")
    ap.add_argument("--not-this", dest="not_this",
                    help="上一版的同一屏 PNG。给了它，判据必须先证明分得清新旧")
    ap.add_argument("--local", default="",
                    help="改读工作区里的这个 outdir（渲完还没提交时用），"
                         "如 output/2026-08-14/explainer/hawkeye")
    args = ap.parse_args()

    # **什么都不查的检查报绿，和它查过了长得一模一样。** 不给 `--says` 也不给
    # `--slide` 时，下面两段全被跳过，只剩「目录非空」——那不是一道闸，是一盏
    # 恒亮的绿灯。接进工作流的当天就得防住这个：谁把 `--says` 那一串漏了，
    # 这一步照样 0 退出，而「查过了」这三个字会被记到这条片子头上。
    if not args.says and args.slide is None:
        print("★ 既没给 --says 也没给 --slide，这一趟什么都没查——不算「已落地」")
        return 2

    where, ls, read = _reader(args)
    names = ls()
    if not names:
        # ⚠️ 「还没提交」和「不合格」必须分得开，所以两条路各说各的话。
        print(f"{where} 是空的" if args.local else f"{where} 上还不存在（可能只是还没提交）")
        return 2

    # 把目录里所有文本读成一份，记住每句话是在哪个文件里命中的。
    #
    # ⚠️ **`.ass` 要先剥掉 `{...}` 样式标签再搜。** 字幕里的数字单独套一档
    # 更大的字号（`世界第{\fs78}15{\fs68}`，见 CLAUDE.md「数字和汉字看着不像
    # 一家」），于是**标签夹在词中间**，裸的子串搜索必然搜不到——
    # 2026-08-03 查 special-exempt 时「世界第 15」明明烧在画面上，
    # 这里报的却是「★ 一个文件都没有」。**那和「这一版没落库」长得一模一样**，
    # 而这个脚本存在的全部理由就是回答后面那个问题。
    def _searchable(name: str, raw: str) -> str:
        if name.endswith(".ass"):
            return re.sub(r"\{[^{}]*\}", "", raw)
        if name.endswith(".words.json"):
            # 词边界事件是**按词切开的**（`"世界"`,`"第十五"`），整句在原始
            # JSON 里根本不连续。拼回去才搜得到——这是旁白**念出来**的那一份，
            # 和字幕那一份不同（字幕过了 `arabic_numerals`：念「第十五」，
            # 屏幕上是「第 15」）。两份都留着，才分得清是文案错还是渲染错。
            try:
                return raw + "\n" + "".join(e.get("text", "") for e in json.loads(raw))
            except (ValueError, AttributeError, TypeError):
                return raw
        return raw

    texts = {n: _searchable(n, read(n).decode("utf-8", "replace"))
             for n in names if n.endswith(TEXT_SUFFIXES)}
    bad = 0
    for phrase in args.says:
        where = [n for n, t in texts.items() if phrase in t]
        print(f"  「{phrase}」 → {'／'.join(where) if where else '★ 一个文件都没有'}")
        bad += not where

    if args.slide is not None and args.against:
        from PIL import Image
        # 卡片 2026-07-29 起存 JPEG，之前发的是 PNG——两个后缀都试，
        # 否则查旧成片会误报「还没落库」。
        raw = b""
        for suffix in (".jpg", ".png"):
            raw = read(f"slide_{args.slide:02d}{suffix}")
            if raw:
                break
        if not raw:
            # ⚠️ **2026-08-13 起幻灯不再进 git**（成片走 Release，`archive-media`
            # 把历史 mp4/jpg 一起清了）。所以在 git ref 那条路上这一句**必然**
            # 出现，而它的意思是「没东西可验」，不是「这一版不合格」——量过：
            # `origin/main` 上 `slide_*.jpg` 和 `*.mp4` 各 0 个。
            # 要比画面就在渲完当场用 `--local` 比，那时它还在工作区。
            print(f"  slide_{args.slide:02d}.[jpg|png] 取不到"
                  + ("" if args.local else
                     "——幻灯 2026-08-13 起不进 git 了，比画面请用 --local 在渲完当场比"))
            return 2
        repo = _grid(Image.open(io.BytesIO(raw)))
        new = _grid(Image.open(args.against))
        d_new = _dist(repo, new)
        if args.not_this:
            # 判据必须先证明自己分得清新旧。分不清就报错——一个连两版都区分不了
            # 的检查，报绿说明不了任何事情。这一条是两次假绿换来的。
            old = _grid(Image.open(args.not_this))
            d_old, spread = _dist(repo, old), _dist(new, old)
            print(f"  第 {args.slide} 屏 与新版距离 {d_new:.4f} · 与旧版距离 {d_old:.4f}"
                  f" · 新旧本身相差 {spread:.4f}")
            # 只做排序，不设绝对阈值。CI 与沙箱渲染同一版的差距（字体微调、
            # 抗锯齿）本身就有 0.02 上下，和"换了配色"的差距一个量级——拿绝对
            # 阈值卡会把已经落地的新版判成没落地，这个红报过一次。
            if spread < 0.008:
                print("  ★ 新旧两版本身几乎一样，这个判据分不出来，不作数"); bad += 1
            elif d_new >= d_old * 0.85:
                print("  ★ 仓库里更像旧版，或两者分不清"); bad += 1
            else:
                print("  ✓ 仓库更接近新版（这一步只排序；最终以亲眼看为准）")
        else:
            print(f"  第 {args.slide} 屏 与本地渲染距离 {d_new:.4f}（阈值 {TOLERANCE}）")
            bad += d_new >= TOLERANCE

    print("已落地" if not bad else f"有 {bad} 项对不上")
    return 0 if not bad else 2


if __name__ == "__main__":
    sys.exit(main())
