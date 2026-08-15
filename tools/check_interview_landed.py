#!/usr/bin/env python3
"""采访片落库之后，直接查产物本身——interview 线一直缺的那道 L2 成片闸。

三条生产线共用同一把尺（docs/qa-contract.md §三 成片落地闸）。之前采访片渲完
直接进推送、没人验，出问题只有等账号所有者回头翻微信才发现；reel 线有
`check_reel_landed`，explainer 线有 `check_explainer_landed`，就 interview 空着。

核心不变量（和 check_reel_landed 同源，只是采访片没有「无解说段现场声」这一说
——采访片从头到尾是原声 + 双语字幕）：

  1. 分辨率 1080×1440（采访片画布，build_interview_clip.CANVAS_W/H）
  2. 音画等长（画面 ≥ 音轨，音轨别比画面短——短了就是结尾没声音）
  3. 字幕有字（.ass 里真有 Dialogue 行；只查有 / 没有，不查切行——切行是
     `check_human_quote` / 字宽闸的事，在渲染前就已经验过了）

用法：
    python tools/check_interview_landed.py --slug shang-rublev-mtl2026-r2
    python tools/check_interview_landed.py --film 路径.mp4 --slug x

⚠️ 成片 mp4 现在在 Release 上（不在 git 里）。不给 --film 时只查仓库里的
证据（render.json 有没有 video_url / .ass 有没有字 / spec 的 zh 有没有内容），
并在输出里**说清哪些没判**——「没判」和「判了没问题」要分得开。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

CANVAS_W, CANVAS_H = 1080, 1440


def sh(*args: str) -> str:
    proc = subprocess.run(list(args), capture_output=True, text=True)
    if proc.returncode:
        raise SystemExit(f"命令失败：{' '.join(args)[:200]}\n{proc.stderr[-800:]}")
    return proc.stdout


def outdir_for(slug: str) -> Path:
    # 采访片产物直接挂在 output/interviews/<slug>/ 下，**没有日期层**（和 reel 线
    # 的 output/<日期>/reel/<slug> 不同——两条线产物目录形状不一样，别照抄）。
    return Path(__file__).resolve().parents[1] / "output" / "interviews" / slug


def ass_has_dialogue(ass: Path) -> bool:
    """字幕文件里真有 Dialogue 行。只查有/没有——切行、宽窄不在这一层。"""
    if not ass.is_file():
        return False
    for line in ass.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip().startswith("Dialogue:"):
            return True
    return False


def check_film(film: Path, spec: dict, ass: Path) -> int:
    """给 --film 时，量成片本身。返回不合格项数。"""
    bad = 0
    size = sh("ffprobe", "-v", "error", "-select_streams", "v:0",
              "-show_entries", "stream=width,height",
              "-of", "csv=p=0:s=x", str(film)).strip().split("x")[:2]
    w, h = int(size[0]), int(size[1])
    ok = (w, h) == (CANVAS_W, CANVAS_H)
    bad += 0 if ok else 1
    print(f"[{'ok' if ok else '不合格'}] 分辨率 {w}×{h}（要 {CANVAS_W}×{CANVAS_H}）")

    v_dur = float(sh("ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=duration",
                     "-of", "csv=p=0", str(film)).strip())
    a_dur = float(sh("ffprobe", "-v", "error", "-select_streams", "a:0",
                     "-show_entries", "stream=duration",
                     "-of", "csv=p=0", str(film)).strip())
    ok = v_dur - a_dur < 1.0
    bad += 0 if ok else 1
    print(f"[{'ok' if ok else '不合格'}] 画面 {v_dur:.2f}s / 音轨 {a_dur:.2f}s"
          f"（音轨比画面短过 1s 就是结尾没声音）")

    ok = ass_has_dialogue(ass)
    bad += 0 if ok else 1
    print(f"[{'ok' if ok else '不合格'}] 字幕 {'有 Dialogue' if ok else '空 / 无'}")

    meta = film.parent / "render.json"
    if meta.is_file():
        data = json.loads(meta.read_text(encoding="utf-8"))
        rec = float(data.get("film_seconds") or 0)
        ok = rec and abs(v_dur - rec) < 1.0
        bad += 0 if ok else 1
        print(f"[{'ok' if ok else '不合格'}] 片长 vs render.json film_seconds"
              f"（实测 {v_dur:.2f}s / 记录 {rec:.2f}s）")
    return bad


def check_offline(spec: dict, outdir: Path) -> int:
    """不给 --film 时，只查仓库里留得下的证据。返回不合格项数。"""
    bad = 0
    meta = outdir / "render.json"
    if meta.is_file():
        data = json.loads(meta.read_text(encoding="utf-8"))
        url = data.get("video_url") or ""
        nbytes = int(data.get("video_bytes") or 0)
        ok = bool(url) and nbytes > 0
        bad += 0 if ok else 1
        print(f"[{'ok' if ok else '不合格'}] 成片在 Release 上"
              f"（{nbytes / 1e6:.1f} MB，url {'有' if url else '无'}）")
    else:
        print("[跳过] 没有 render.json，成片落没落 Release 无从得知")
    ass = outdir / f"{spec['slug']}.ass"
    ok = ass_has_dialogue(ass)
    bad += 0 if ok else 1
    print(f"[{'ok' if ok else '不合格'}] 字幕 {'有 Dialogue' if ok else '空 / 无'}（{ass.name}）")
    zh = spec.get("zh") or []
    ok = bool(zh)
    bad += 0 if ok else 1
    print(f"[{'ok' if ok else '不合格'}] spec.zh {'有 ' + str(len(zh)) + ' 行' if ok else '空'}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--film", help="本地成片路径（给就量分辨率/音画，不给只查证据）")
    args = ap.parse_args()

    outdir = outdir_for(args.slug)
    spec_path = Path(__file__).resolve().parents[1] / "specs" / "interviews" / f"{args.slug}.json"
    if not spec_path.is_file():
        print(f"[不合格] 找不到 spec {spec_path}")
        return 1
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    ass = outdir / f"{args.slug}.ass"

    if args.film:
        film = Path(args.film)
        if not film.is_file():
            print(f"[不合格] 找不到成片 {film}")
            return 1
        print(f"成片 {film}（{film.stat().st_size / 1e6:.1f} MB）")
        bad = check_film(film, spec, ass)
    else:
        print(f"[离线模式] 没给 --film，只查仓库证据（{outdir}）")
        bad = check_offline(spec, outdir)

    print(f"\n共 {bad} 项不合格")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
