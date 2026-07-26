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

WANT_VOICE = "zh-CN-YunjianNeural"  # 云健
WANT_RATE = "+22%"


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
