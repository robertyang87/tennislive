#!/usr/bin/env python3
"""哪条片子用的是哪个声音——读产物，不靠推理。

每段旁白的 mp3 生成完就被工作流删掉了（体积），mp4 里也读不出语音名。所以
`generate_explainer_video` 会在成片旁边落一个 `narration.json`，把**实际用的**
voice / rate / pitch 记下来；这个脚本就是去读它。

为什么非要落这么一个文件：推理链断过一次。工作流里写死了一个旧的 `--voice`
每次都传，代码里换默认值等于没换，三条片子用着被替换掉的声音发了出去，
几天后翻运行日志才发现。「传了什么参数」和「用了什么声音」是两件事。

用法：
    python tools/check_explainer_voice.py hawkeye masters-format roof
    python tools/check_explainer_voice.py --date 2026-07-26 --ref origin/main hawkeye
    python tools/check_explainer_voice.py --local output/2026-07-26/explainer hawkeye

不合格的、没落库的一律打印出来。只在成功时出声的检查，没法证明它真的看过。
"""

from __future__ import annotations

import argparse
import json
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

# **期望值只有一个出处：代码里的默认值。**
#
# ⚠️ 这两个数原来是抄在这儿的字面量（`zh-CN-YunjianNeural` / **`+28%`**），
# 而语速 2026-08-03 已经从 +28% 定回 **+22%**（账号所有者听完 special-exempt：
# 「语速太快了」，见 `explainer.DEFAULT_RATE` 上面那段实测）。
# 抄的那份没跟着改，于是这个脚本对**今天每一条新片子**都会报「✗ 与期望不符」。
# 量过存量：29 份已落库的 `narration.json` 里 **19 份是 +22%**、10 份是 +28%
# ——2026-08-14 要把它接进 `explainer.yml` 当闸，照原样装上去就是一条**常年红**，
# 而一条常年红的检查和没有检查是同一个毛病。
#
# 「一个数写两处必分叉」，所以直接读代码里那份。⚠️ **不许 try/except 退回字面量**：
# 悄悄退回去的话，「期望值取自代码」和「期望值又停在某一版」在日志上一模一样。
from tennislive.video.explainer import DEFAULT_RATE, DEFAULT_VOICE  # noqa: E402

WANT_VOICE = DEFAULT_VOICE  # 云健
WANT_RATE = DEFAULT_RATE


def _read(slug: str, args) -> dict | None:
    rel = f"{args.local}/{slug}/narration.json" if args.local else (
        f"output/{args.date}/explainer/{slug}/narration.json")
    if args.local:
        p = REPO / rel
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
    out = subprocess.run(["git", "-C", str(REPO), "show", f"{args.ref}:{rel}"],
                         capture_output=True)
    return json.loads(out.stdout) if out.stdout else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slugs", nargs="+")
    ap.add_argument("--date", default=_outdir_date())
    ap.add_argument("--ref", default="origin/main", help="从哪个 git ref 读产物")
    ap.add_argument("--local", default="", help="改读本地目录，如 output/2026-07-26/explainer")
    ap.add_argument("--voice", default=WANT_VOICE)
    ap.add_argument("--rate", default=WANT_RATE)
    args = ap.parse_args()

    ok = 0
    for slug in args.slugs:
        meta = _read(slug, args)
        if meta is None:
            print(f"  {slug:18} 没有 narration.json（还没生成，或是这个改动之前的旧成片）")
            continue
        hit = meta.get("voice") == args.voice and meta.get("rate") == args.rate
        ok += hit
        print(f"  {slug:18} voice={meta.get('voice')} rate={meta.get('rate')} "
              f"pitch={meta.get('pitch')} 段数={meta.get('segments')} "
              f"{'✓' if hit else '✗ 与期望不符'}")

    print(f"{ok}/{len(args.slugs)} 条确认为 {args.voice} {args.rate}")
    return 0 if ok == len(args.slugs) else 2


if __name__ == "__main__":
    sys.exit(main())
