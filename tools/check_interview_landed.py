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
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CANVAS_W, CANVAS_H = 1080, 1440
MAX_AV_DELTA = 0.30
SILENCE_FLOOR_DB = -60.0


def sh(*args: str) -> str:
    proc = subprocess.run(list(args), capture_output=True, text=True)
    if proc.returncode:
        raise SystemExit(f"命令失败：{' '.join(args)[:200]}\n{proc.stderr[-800:]}")
    return proc.stdout


def _ffprobe_float(out: str) -> float:
    """`-of csv=p=0` 拿单个字段，理论上应该是干净的一个数——**但不同 ffprobe
    版本的 csv writer 行为不一样**，撞过某个构建吐出 `291.880000,` 带一个
    尾随空字段，`float()` 直接崩（同一个坑 `check_reel_landed.py` 早修过，
    这个文件是姊妹工具，没跟着改）。只取第一个逗号前的字段，多出来的空
    尾巴丢掉。"""
    return float(out.strip().split(",")[0])


def _max_volume_db(stderr: str) -> float | None:
    """解析 volumedetect；全数字静音的 ``-inf`` 也必须能被判成不合格。"""
    found = re.search(r"max_volume:\s*(-inf|-?[\d.]+)\s*dB", stderr)
    if not found:
        return None
    return float("-inf") if found.group(1) == "-inf" else float(found.group(1))


def audio_peak_db(film: Path) -> float | None:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(film), "-vn", "-af", "volumedetect",
         "-f", "null", os.devnull], capture_output=True, text=True, check=False)
    if proc.returncode:
        return None
    return _max_volume_db(proc.stderr)


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


def _ass_body_events(ass: Path) -> dict[str, list[tuple[str, str, str]]]:
    """只取正文 EN/ZH；HEADA/HEADB/观点卡不能冒充双语字幕。"""
    out: dict[str, list[tuple[str, str, str]]] = {"EN": [], "ZH": []}
    if not ass.is_file():
        return out
    for line in ass.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        fields = line.split(",", 9)
        if len(fields) != 10:
            continue
        style = fields[3].strip()
        if style in out:
            out[style].append((fields[1].strip(), fields[2].strip(), fields[9].strip()))
    return out


def bilingual_body_ok(ass: Path, spec: dict) -> tuple[bool, str]:
    """正文英文和中文必须逐 cue 同时出现，数量与 spec.zh 一致。"""
    events = _ass_body_events(ass)
    en, zh = events["EN"], events["ZH"]
    en_times = [(a, b) for a, b, text in en if text]
    zh_times = [(a, b) for a, b, text in zh if text]
    expected = len(spec.get("zh") or [])
    ok = bool(en_times) and en_times == zh_times and len(en_times) == expected
    return ok, (f"EN {len(en_times)} / ZH {len(zh_times)} / spec.zh {expected}，"
                f"逐 cue 时间 {'一致' if en_times == zh_times else '不一致'}")


def bilingual_lead_ok(ass: Path, spec: dict) -> tuple[bool, str]:
    """冷开场的原解说也必须逐 cue 中英成对，不能只验采访正文。"""
    expected = len(((spec.get("lead_in") or {}).get("subs") or []))
    if expected == 0:
        return False, "spec.lead_in.subs 为空"
    events = _ass_body_events(ass)
    en, zh = events["EN"], events["ZH"]
    en_times = [(a, b) for a, b, text in en if text]
    zh_times = [(a, b) for a, b, text in zh if text]
    ok = en_times == zh_times and len(en_times) == expected
    return ok, (f"EN {len(en_times)} / ZH {len(zh_times)} / lead_in.subs {expected}，"
                f"逐 cue 时间 {'一致' if en_times == zh_times else '不一致'}")


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

    v_dur = _ffprobe_float(sh("ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=duration",
                     "-of", "csv=p=0", str(film)))
    a_dur = _ffprobe_float(sh("ffprobe", "-v", "error", "-select_streams", "a:0",
                     "-show_entries", "stream=duration",
                     "-of", "csv=p=0", str(film)))
    ok = abs(v_dur - a_dur) <= MAX_AV_DELTA
    bad += 0 if ok else 1
    print(f"[{'ok' if ok else '不合格'}] 画面 {v_dur:.2f}s / 音轨 {a_dur:.2f}s"
          f"（绝对差必须 ≤ {MAX_AV_DELTA:.2f}s）")

    # “有音轨、时长也对”仍可能整条是 anullsrc。赛场之上真实出过 -91 dB 的
    # 成片：ffprobe、码率和时长全部正常，只有波形能看出声音被补位静音盖掉。
    peak = audio_peak_db(film)
    ok = peak is not None and peak > SILENCE_FLOOR_DB
    bad += 0 if ok else 1
    peak_text = "探测失败" if peak is None else f"{peak:.1f} dBFS"
    print(f"[{'ok' if ok else '不合格'}] 音轨峰值 {peak_text}"
          f"（必须高于 {SILENCE_FLOOR_DB:.0f} dBFS，防整条数字静音）")

    ok = ass_has_dialogue(ass)
    bad += 0 if ok else 1
    print(f"[{'ok' if ok else '不合格'}] 字幕 {'有 Dialogue' if ok else '空 / 无'}")

    ok, detail = bilingual_body_ok(ass, spec)
    bad += 0 if ok else 1
    print(f"[{'ok' if ok else '不合格'}] 正文双语字幕 {detail}")

    lead_ass = film.parent / "_lead.ass"
    ok, detail = bilingual_lead_ok(lead_ass, spec)
    bad += 0 if ok else 1
    print(f"[{'ok' if ok else '不合格'}] 冷开场原解说双语字幕 {detail}")

    meta = film.parent / "render.json"
    if meta.is_file():
        data = json.loads(meta.read_text(encoding="utf-8"))
        rec = float(data.get("film_seconds") or 0)
        ok = rec and abs(v_dur - rec) < 1.0
        bad += 0 if ok else 1
        print(f"[{'ok' if ok else '不合格'}] 片长 vs render.json film_seconds"
              f"（实测 {v_dur:.2f}s / 记录 {rec:.2f}s）")
    return bad


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_attestation(film: Path, spec_path: Path, spec: dict,
                      ass: Path, outdir: Path) -> Path:
    """L0/L2 全绿后落不可变发布凭证；自动推送只认这份凭证。"""
    from interview_source_gate import validate_source_contract  # noqa: PLC0415

    source_attestation = validate_source_contract(spec)
    payload = {
        "status": "pass",
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "slug": spec["slug"],
        "match_id": spec["match"]["id"],
        "requested_content_type": spec["requested_content_type"],
        "source_attestation_sha256": source_attestation,
        "spec_sha256": _sha256(spec_path),
        "ass_sha256": _sha256(ass),
        "lead_ass_sha256": _sha256(outdir / "_lead.ass"),
        "film_sha256": _sha256(film),
        "film_bytes": film.stat().st_size,
        "checks": {
            "canvas": [CANVAS_W, CANVAS_H],
            "max_av_delta_s": MAX_AV_DELTA,
            "silence_floor_db": SILENCE_FLOOR_DB,
            "bilingual_body_cues": len(_ass_body_events(ass)["EN"]),
            "bilingual_lead_cues": len(_ass_body_events(outdir / "_lead.ass")["EN"]),
        },
    }
    path = outdir / "qc_attestation.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(f"[QC] 发布凭证 → {path}（film {payload['film_sha256'][:12]}…）")
    return path


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
    ap.add_argument("--write-attestation", action="store_true",
                    help="全部检查通过后写 qc_attestation.json")
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
        if bad == 0 and args.write_attestation:
            from interview_source_gate import (  # noqa: PLC0415
                SourceContractError,
                validate_source_contract,
            )
            try:
                validate_source_contract(spec)
            except SourceContractError as exc:
                print(f"[不合格] L0 内容身份：{exc}")
                bad += 1
            else:
                write_attestation(film, spec_path, spec, ass, outdir)
    else:
        print(f"[离线模式] 没给 --film，只查仓库证据（{outdir}）")
        bad = check_offline(spec, outdir)

    print(f"\n共 {bad} 项不合格")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
