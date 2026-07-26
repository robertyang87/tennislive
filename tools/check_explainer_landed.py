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
    # 只查文案
    python tools/check_explainer_landed.py zheng-eala --says 钦文还在打 祝钦文好运
    # 连画面一起查（先在本地渲一份做参照）
    python tools/check_explainer_landed.py zheng-eala --says 祝钦文好运 \
        --slide 5 --against /tmp/ze/slide_05.png

退出码 0＝全部对上；2＝有对不上的。缺什么、差多少都打印出来。
"""

from __future__ import annotations

import argparse
import io
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

TEXT_SUFFIXES = (".txt", ".html", ".json", ".md")
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
    args = ap.parse_args()

    outdir = f"output/{args.date}/explainer/{args.slug}"
    names = _ls(args.ref, outdir)
    if not names:
        print(f"{outdir} 在 {args.ref} 上还不存在")
        return 2

    # 把目录里所有文本读成一份，记住每句话是在哪个文件里命中的。
    texts = {n: _git(args.ref, f"{outdir}/{n}").decode("utf-8", "replace")
             for n in names if n.endswith(TEXT_SUFFIXES)}
    bad = 0
    for phrase in args.says:
        where = [n for n, t in texts.items() if phrase in t]
        print(f"  「{phrase}」 → {'／'.join(where) if where else '★ 一个文件都没有'}")
        bad += not where

    if args.slide is not None and args.against:
        from PIL import Image
        raw = _git(args.ref, f"{outdir}/slide_{args.slide:02d}.png")
        if not raw:
            print(f"  slide_{args.slide:02d}.png 还没落库"); return 2
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
