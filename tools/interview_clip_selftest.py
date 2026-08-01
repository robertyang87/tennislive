#!/usr/bin/env python3
"""不联网、不用 runner，把「赛后开麦」整条出片路径走一遍。**推之前跑它。**

## 为什么有这个东西

2026-08-01 这条线连推七趟才出片，六趟死在环境上。**不是运气差，是算术**：
`render` 的关键路径要三样沙箱没有的东西——YouTube 访问（本机 IP 被挡）、
干净的 runner（沙箱什么都装着）、secret。于是唯一的验证方式是「推上去看」，
而**第一个失败会把后面所有步骤挡住**，每趟只暴露一个问题。N 个问题串在一条
路上就是 N 趟，一趟五到十分钟。

真正的错不是那六个 bug，是**每次只做点对点修复，没有防住那一类**。
那一类的解法就一句话：**把「只有 runner 上才跑得到的那段」在本地跑一遍**。

做法只有两条，都不需要网：

- **下载那一步用现成的文件顶掉**（`render()` 会复用已存在的 `source.mp4`），
  所以合成一段同样长的视频塞进去就行
- **依赖照工作流那行原样在干净 venv 里装**（`--venv`），而不是在什么都装着的
  沙箱里试——`fonts-noto-core`、`chrome-linux64`、`PIL` 三个都是这么漏的

实测：这个脚本十分钟能建起来，六个问题里五个它当场能抓到。只有
「yt-dlp 把源片落成 `.mkv`」那个真的非 runner 不可（要看 YouTube 实际给
什么编码）。

## 它检查什么

**查产物，不查信号**——不看「跑完了没报错」，看成片本身：

    画布 1080×1440   帧率 25   音轨 aac/48000/2ch   时长 ≈ 采访长度 + 封面

## 用法

    PYTHONPATH=src python tools/interview_clip_selftest.py \
        --spec specs/interviews/eala-svitolina-dc2026-qf.json

    # 连依赖一起验（第一次慢几分钟，装的是工作流那一行）
    ... --venv /tmp/clipvenv
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

WORKFLOW = ROOT / ".github" / "workflows" / "interview-clip.yml"


def _pip_line() -> str:
    """从工作流里抠出那行 `pip install`——**别在这儿另写一份**。

    两处各写一份必分叉，而分叉的表现是「本地全绿、runner 上 ModuleNotFound」。
    """
    import yaml

    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in (wf.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            for ln in str(step.get("run") or "").splitlines():
                if "pip install" in ln and not ln.lstrip().startswith("#"):
                    return ln.strip()
    raise SystemExit(f"{WORKFLOW} 里找不到 pip install 那行")


def make_venv(path: Path) -> Path:
    """干净 venv + 工作流那行原样装。返回它的 python。"""
    if not (py := path / "bin" / "python").exists():
        print(f"建 venv：{path}")
        subprocess.run([sys.executable, "-m", "venv", str(path)], check=True)
    line = _pip_line()
    print(f"照工作流装：{line}")
    subprocess.run(f"{path}/bin/{line}", shell=True, check=True, cwd=ROOT)
    subprocess.run([str(py), "-m", "playwright", "install", "chromium"], check=False)
    return py


def synth_source(dest: Path, seconds: float) -> Path:
    """合成一段 720p 源片顶掉下载。

    ⚠️ **要等 `ffprobe` 读得动才算生成完。** 踩过：生成和渲染拆成两个后台
    任务，文件还没写完就开跑，得到 `moov atom not found`——测试脚手架自己的
    问题，却长得像代码的问题。
    """
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
         "-t", f"{seconds:.1f}", "-c:v", "libx264", "-preset", "ultrafast",
         "-crf", "32", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2",
         str(dest)], check=True, timeout=900)
    probe(dest)          # 读得动才算写完
    return dest


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,r_frame_rate,codec_name,sample_rate,channels,duration",
         "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True, timeout=120).stdout
    d = json.loads(out)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), {})
    return {"w": v["width"], "h": v["height"], "fps": v["r_frame_rate"],
            "acodec": a.get("codec_name"), "arate": a.get("sample_rate"),
            "ach": a.get("channels"), "dur": float(d["format"]["duration"]),
            "vdur": float(v["duration"]), "adur": float(a["duration"])}


def run(spec_path: Path, venv: Path | None) -> int:
    py = make_venv(venv) if venv else Path(sys.executable)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    # 预检那段一字不改地跑一遍——**它是工作流的第 6 步，不是这儿另写的**
    print("\n—— 预检 ——")
    pre = ROOT / "tools" / "_selftest_preflight.py"
    pre.write_text(
        "import shutil, sys\n"
        f"sys.path.insert(0, {str(ROOT / 'tools')!r})\n"
        f"sys.path.insert(0, {str(ROOT / 'src')!r})\n"
        "from build_interview_clip import _chromium, _en_width, _zh_width\n"
        "assert shutil.which('ffmpeg'), '没有 ffmpeg'\n"
        "print('Chromium:', _chromium())\n"
        "print(f\"字宽 en={_en_width('respect'):.1f} zh={_zh_width('网球'):.1f}\")\n"
        "from tennislive.render.webcards import _font_css\n"
        "assert 'TL Display SC' in _font_css(), '得意黑没内嵌进来'\n"
        "print('字体 CSS 就绪')\n", encoding="utf-8")
    try:
        subprocess.run([str(py), str(pre)], check=True, cwd=ROOT, timeout=600)
    finally:
        pre.unlink(missing_ok=True)

    print("\n—— 切行 / 核对表 ——")
    for stage in ("subs", "sheet"):
        subprocess.run([str(py), "tools/build_interview_clip.py",
                        "--spec", str(spec_path), "--stage", stage],
                       check=True, cwd=ROOT, timeout=600,
                       env={"PYTHONPATH": "src", "PATH": __import__("os").environ["PATH"]})

    print("\n—— 出片（合成源片顶掉下载）——")
    work = Path(tempfile.mkdtemp(prefix="clip-selftest-"))
    try:
        synth_source(work / "source.mp4", spec["end"] + 10)
        shutil.copy(ROOT / "output" / "interviews" / spec["slug"]
                    / f"{spec['slug']}.ass", work)
        code = (
            f"import json, pathlib, sys\n"
            f"sys.path.insert(0, {str(ROOT / 'tools')!r})\n"
            f"sys.path.insert(0, {str(ROOT / 'src')!r})\n"
            "import build_interview_clip as clip\n"
            f"spec = json.loads(pathlib.Path({str(spec_path)!r}).read_text())\n"
            f"w = pathlib.Path({str(work)!r})\n"
            "out = clip.render(spec, w / (spec['slug'] + '.ass'), w)\n"
            "print('成片', out)\n")
        subprocess.run([str(py), "-c", code], check=True, cwd=ROOT, timeout=1800)

        got = probe(work / f"{spec['slug']}.mp4")
        from build_interview_clip import CANVAS_H, CANVAS_W, COVER_SECONDS

        want_dur = spec["end"] - spec["start"] + (
            COVER_SECONDS if spec.get("cover") else 0)
        checks = [
            ("画布", (got["w"], got["h"]), (CANVAS_W, CANVAS_H)),
            ("帧率", got["fps"], "25/1"),
            ("音轨编码", got["acodec"], "aac"),
            ("采样率", got["arate"], "48000"),
            ("声道", got["ach"], 2),
        ]
        bad = [f"{n}：{g} ≠ {w}" for n, g, w in checks if g != w]
        if abs(got["dur"] - want_dur) > 0.05:
            bad.append(f"时长：{got['dur']:.2f}s ≠ {want_dur:.2f}s")
        av_delta = abs(got["vdur"] - got["adur"])
        if av_delta > 0.05:
            bad.append(f"A/V 时差：{av_delta:.3f}s > 0.050s")
        qa_path = work / "audio-qa.json"
        if not qa_path.exists():
            bad.append("缺 audio-qa.json")
            qa = {}
        else:
            qa = json.loads(qa_path.read_text(encoding="utf-8"))
            expected_status = "pass" if spec.get("cover") else "not_applicable"
            if qa.get("status") != expected_status or qa.get("role") != "speech":
                bad.append(f"音频 QA 不合格：{qa}")
            if spec.get("cover"):
                joins = qa.get("joins") or []
                if len(joins) != 1 or joins[0].get("mode") != "declick":
                    bad.append(f"封面→人声不是唯一 20ms de-click：{joins}")
                elif (joins[0].get("fade_out") != 0.02
                      or joins[0].get("fade_in") != 0.02):
                    bad.append(f"封面→人声 de-click 不是 20ms：{joins[0]}")
        print("\n—— 查产物 ——")
        for n, g, w in checks:
            print(f"  {'✅' if g == w else '❌'} {n} {g}")
        print(f"  {'✅' if abs(got['dur'] - want_dur) <= 0.05 else '❌'} "
              f"时长 {got['dur']:.2f}s（期望 {want_dur:.2f}s）")
        print(f"  {'✅' if av_delta <= 0.05 else '❌'} A/V 时差 {av_delta:.3f}s")
        print(f"  {'✅' if qa.get('status') in {'pass', 'not_applicable'} else '❌'} "
              "结构化音频 QA")
        if bad:
            raise SystemExit("成片不合格：\n  " + "\n  ".join(bad))
        print("\n✅ 整条路走通了。剩下**只有 runner 上才验得了**的两件事："
              "真去下 YouTube 源片、把成片提交回仓库。")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=re.sub(r"\n\n.*", "", __doc__ or "",
                                                    flags=re.S))
    ap.add_argument("--spec", required=True)
    ap.add_argument("--venv", help="干净 venv 的路径；给了就照工作流那行装一遍")
    a = ap.parse_args()
    return run(Path(a.spec), Path(a.venv) if a.venv else None)


if __name__ == "__main__":
    sys.exit(main())
