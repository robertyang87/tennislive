#!/usr/bin/env python3
"""把 B 站视频的**自动帧**拼成联络表，用来判「这到底是不是场上采访」。

为什么需要它：B 站上标着「赛后采访」的东西至少混着四类——

    场上采访          球员在场上、手持话筒、背板是赛事标识
    央视混合区采访    球场外的通道/背景板，中文记者提问（标题常写「央视采访」）
    演播室口播        主持人西装站在虚拟背景前
    集锦包装片        开头演播室 + 中段比赛 + 末尾几秒采访

**标题一律分不出**，`杂草小喵` 的「赛后央视采访」和 `TennisTube` 的
「赛后采访」在字面上没有区别。只有画面能分。

好在 B 站自己生成 10×10 的雪碧预览图：

    https://api.bilibili.com/x/player/videoshot?bvid=<BV号>&cid=<cid>&index=1

**那是视频里的真实画面，up 主改不了**——和 YouTube 的 `hq1/hq2/hq3` 是
同一个性质，也是同一个用途（见 tools/verify_oncourt_sample.py 的 fetch_frames）。

两个坑，都是踩出来的：

- **雪碧图是渐进生成的。** 刚发的片子只有前几格有内容，其余是纯黑。
  直接均匀抽 5 帧会抽到 4 张黑图，然后得出「这片子没有采访画面」的结论。
  所以先按亮度筛出非黑格，再在**非黑格里**均匀抽。
- **开头那一格往往是演播室**。中文转播方的包装片都是「主持人口播 → 集锦
  → 末尾采访」，只看第一帧会把整条片子判成演播室节目。要看到最后一格。

用法：
    python tools/check_bili_frames.py BV1PL3k6WEJH
    python tools/check_bili_frames.py BV1PL3k6WEJH BV1HoKX6iEva --out /tmp/sheets
    python tools/check_bili_frames.py --unknown     # 复看判定文件里所有 bili: 的 unknown
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERDICTS = ROOT / "data" / "oncourt_verify.json"

UA = ["-H", "User-Agent: Mozilla/5.0", "-H", "Referer: https://www.bilibili.com"]
# 一格的平均亮度低于这个就当作「还没生成」。纯黑格实测均值 0–3，
# 而最暗的真实画面（夜场逆光）也在 20 以上，12 落在两者中间。
DARK = 12


def _get(url: str, binary: bool = False):
    proc = subprocess.run(["curl", "-sS", "--compressed", "--max-time", "60", *UA,
                           *(["--output", "-"] if binary else []), url],
                          capture_output=True, timeout=90)
    return proc.stdout if binary else proc.stdout.decode("utf-8", "replace")


def sprite(bvid: str) -> tuple[bytes | None, str]:
    """取一条视频的雪碧图。返回 (图, 说明)。"""
    try:
        view = json.loads(_get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"))
    except ValueError:
        return None, "view 接口没返回 JSON"
    if view.get("code") != 0:
        return None, f"view code={view.get('code')} {view.get('message')}"
    data = view["data"]
    cid, title = data["cid"], data.get("title", "")
    try:
        shot = json.loads(_get("https://api.bilibili.com/x/player/videoshot"
                               f"?bvid={bvid}&cid={cid}&index=1"))
    except ValueError:
        return None, "videoshot 接口没返回 JSON"
    imgs = ((shot.get("data") or {}).get("image") or [])
    if not imgs:
        # **空 ≠ 没有**：新投稿的雪碧图要等一会儿才生成。
        return None, "雪碧图还没生成（刚投稿的片子会这样，过几分钟再来）"
    url = imgs[0]
    if url.startswith("//"):
        url = "https:" + url
    return _get(url, binary=True), title


def sheet(raw: bytes, out: Path, picks: int = 6) -> tuple[Path, int]:
    """雪碧图 → 联络表。**只在非黑格里抽**，理由见模块注释。"""
    from PIL import Image, ImageStat

    import io
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.width // 10, im.height // 10
    cells = []
    for i in range(100):
        c = im.crop(((i % 10) * w, (i // 10) * h, (i % 10) * w + w, (i // 10) * h + h))
        if ImageStat.Stat(c.convert("L")).mean[0] > DARK:
            cells.append(c)
    if not cells:
        return out, 0
    idx = [int(k * (len(cells) - 1) / (picks - 1)) for k in range(picks)]
    cols = 3
    rows = (len(idx) + cols - 1) // cols
    canvas = Image.new("RGB", (w * cols, h * rows))
    for k, i in enumerate(idx):
        canvas.paste(cells[i], ((k % cols) * w, (k // cols) * h))
    canvas.save(out, quality=90)
    return out, len(cells)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bvids", nargs="*", help="BV 号")
    ap.add_argument("--unknown", action="store_true",
                    help="复看判定文件里所有 bili: 开头、判定为 unknown 的")
    ap.add_argument("--out", default="/tmp/bili_frames", help="联络表输出目录")
    args = ap.parse_args()

    bvids = list(args.bvids)
    if args.unknown and VERDICTS.exists():
        with VERDICTS.open(encoding="utf-8") as fh:
            for vid, v in json.load(fh)["verdicts"].items():
                if vid.startswith("bili:") and v.get("verdict") == "unknown":
                    bvids.append(vid.split(":", 1)[1])
    if not bvids:
        print("没有要看的。给 BV 号，或者用 --unknown。", file=sys.stderr)
        return 2

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    bad = 0
    for bvid in bvids:
        raw, why = sprite(bvid)
        if raw is None:
            # **取不到的也要列出来。** 只在成功时出声的检查，没法证明它真的看过。
            print(f"  ✗ {bvid}  {why}")
            bad += 1
            continue
        path, live = sheet(raw, outdir / f"{bvid}.jpg")
        if not live:
            print(f"  ✗ {bvid}  雪碧图全黑（100 格一格都没生成）")
            bad += 1
            continue
        print(f"  ✓ {bvid}  {live}/100 格有画面  →  {path}   {why[:44]}")
    if bad:
        print(f"\n{bad}/{len(bvids)} 条取不到帧——**那是「没问到」，不是「不是场上采访」**，"
              f"别据此判定。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
