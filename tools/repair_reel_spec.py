#!/usr/bin/env python3
"""render 红了之后，把**确定性的判据文本**回喂 DeepSeek，有界地修一轮自动 spec。

来路：无人值守链的墙钟大头不是渲染（单趟 ~8.5 分钟），是 **QC 打回之后等一个
会话来改的空档**——zheng-burel 那条 QC 18:47 打回、19:25 才有修复提交，空转
38 分钟，而三次打回里两次（静音类）的修法完全是机械的：把窗口收到静音区之前，
或把旁白删短。这一步把「等会话」换成「模型按判据修一轮 → 机械复检 → 重新派
render」，和 #599（MiniMax 机械证据自修一轮）/#601（DeepSeek 算术反馈重试）
是同一个形状，只是推广到了渲后。

**有界**体现在五层，缺一层都是往内容里放开一个口子：

1. **只动自动 spec**（``_production.status == "ready_for_render"``）——手写
   spec 是人的编辑决定，自动改等于替人改稿。
2. **只允许两类编辑**：段窗口 start/end 移动，和旁白**只删不改写**。删字用
   逐字符子序列判定（`deletion_only`）：删掉整句/整个从句能过，改写或新增
   哪怕一个字都过不了——所以模型不可能借「修一下」发明新事实（这个仓库的
   头号红线）。`quote` 段一个字段都不许动：它的双语字幕钉在真实时刻上，
   窗口一动全部错位。
3. **判据先过内容类过滤**（`CONTENT_CLASS`）：下载失败、apt 超时这类环境错
   不是窗口/旁白能修的，喂给模型只会产出一次无意义的编辑。
4. **最多 2 轮**（``_production.qc_repair_attempts``，写进 spec 一起提交，
   跨 run 生效），修不好就还给会话——自动循环永远要有一个数字上限。
5. **修完先过同一套本地闸再落盘**：dry-run 子进程 ＝ validate_spec ＋ 措辞
   seat ＋ probe 层（含 #617 的静音预判）。过不了闸的修订一个字节都不写。

工具自己**永远 exit 0**（skip/waiting 是正常结果不是故障）；工作流靠
`git diff` 判断有没有真的修出一版来决定 commit + 重新 dispatch。
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

MAX_ATTEMPTS = 2

#: 判据文本里值得回喂的行。全量日志几百行（逐秒响度表），模型不需要也装不下。
SALIENT = re.compile(
    r"不合格|硬伤|哑场|静音|装不下|超出|窗口|旁白|ReelError|SystemExit"
    r"|::error|Error|错误")

#: 只有**内容类**失败才值得回喂：窗口/旁白/静音/时长这一族。下载失败、
#: 依赖装不上这类环境错，改 spec 修不了——喂给模型只会拿回一次无意义编辑。
#: ⚠️ 只认**失败专属**的标记：QC 的失败行带方括号（`[不合格]`），而它的
#: 绿灯总结行「共 0 项不合格」不带——认裸的「不合格」会在「render 全绿、
#: 死在后面 push/commit 步」的 run 上把一份全绿日志喂给模型。
CONTENT_CLASS = re.compile(
    r"\[不合格\]|必红|大概率红|哑场|装不下|超出源片|数字静音|ReelError")

SCHEMA = {
    "type": "object",
    "properties": {
        "fixable": {"type": "boolean"},
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "narration": {"type": "string"},
                },
            },
        },
        "note": {"type": "string"},
    },
    "required": ["fixable", "note"],
}

SYSTEM = """你是网球短视频流水线的机械修复器。一条视频 spec 在渲染/质检时被
确定性的判据打回了，你要做**最小的机械修订**让它过闸。

铁律（违反任何一条，你的输出会被整体丢弃）：
- 只允许两类编辑：调整某段的 start/end（秒，浮点），或**删短**某段旁白。
- 旁白只删不改写：修订后的旁白必须是原文**按顺序删掉若干字符**得到的
  （删掉整句、整个从句可以；改写、换词、新增任何一个字都不行）。
- 段的数量、顺序不许变；带 quote 的段一个字段都不许动。
- 窗口不许超出该段源片的总长；窗口要装得下旁白（旁白估秒数已给出）。
- 尽量把窗口边界收在 scene_cuts（镜头切点）或 point_ends（死球时刻）上。
- 判据说某几秒撞上源片静音区：优先把窗口收到静音区之前结束；旁白盖得住的
  部分不用动。
- 判据说旁白装不下：优先延长窗口（不越界、不进静音区），其次删短旁白。
- 修不了（判据和窗口/旁白无关，或怎么改都顾此失彼）就 fixable=false，
  note 里说一句为什么——诚实的放弃比一次凑数的编辑好。

只输出一个 json 对象：fixable（布尔）、segments（和原 spec 等长的数组，每项
只写 start/end/narration 里**你改了的**字段，没改的段给空对象 {}）、note
（一句话说明改了什么、为什么能过闸）。"""


def salient_findings(text: str, limit: int = 6000) -> str:
    """从整份失败日志里抽出值得回喂的行 + 结尾现场，去重保序。"""
    lines = [line for line in text.splitlines() if SALIENT.search(line)]
    tail = text.splitlines()[-40:]
    merged = "\n".join(dict.fromkeys([*lines, *tail]))
    return merged[-limit:]


def deletion_only(original: str, revised: str) -> bool:
    """revised 是不是 original 按顺序删字符得到的（子序列判定）。"""
    it = iter(original)
    return all(ch in it for ch in revised)


def probe_facts(outdir: Path) -> str:
    """probe.json 里模型需要的机械事实，压成一段紧凑文本。"""
    path = outdir / "probe.json"
    if not path.is_file():
        return "（没有 probe 事实——窗口只能保守小动）"
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = [f"源片总长 {data.get('duration')}s"]
    cuts = data.get("scene_cuts") or []
    if cuts:
        rows.append("scene_cuts（镜头切点，秒）：" +
                    " ".join(f"{float(c):.1f}" for c in cuts[:80]))
    ends = data.get("point_ends") or []
    if ends:
        rows.append("point_ends（死球时刻，秒）：" +
                    " ".join(f"{float(p):.1f}" for p in ends[:80]))
    silent = data.get("silent_audio")
    if silent:
        rows.append("silent_audio（源片静音区，秒）：" +
                    " ".join(f"[{float(a):.1f},{float(b):.1f}]"
                             for a, b in silent))
    elif silent == []:
        rows.append("silent_audio：量过，源片没有静音区")
    return "\n".join(rows)


def segment_brief(spec: dict) -> str:
    """每段的窗口、旁白和离线估秒数——模型据此算「装不装得下」。"""
    from reel_timing import speech_seconds  # noqa: PLC0415

    rows = []
    for index, seg in enumerate(spec.get("segments") or []):
        if seg.get("image"):
            rows.append(f"段{index}：整屏证据卡（seconds={seg.get('seconds')}），不许动")
            continue
        window = float(seg.get("end", 0)) - float(seg.get("start", 0))
        line = (f"段{index}：window {seg.get('start')}–{seg.get('end')}"
                f"（{window:.2f}s）")
        if seg.get("quote"):
            line += "，quote 段（不许动）"
        narration = str(seg.get("narration") or "").strip()
        if narration:
            est = speech_seconds(narration) + float(
                (seg.get("voice") or {}).get("lead_pause") or 0.0)
            line += f"，旁白估 {est:.2f}s（±1.64）：{narration}"
        else:
            line += "，无旁白（纯现场声）"
        rows.append(line)
    return "\n".join(rows)


def apply_bounded(spec: dict, model_segments: list) -> tuple[dict | None, str]:
    """把模型输出**有界地**套到 spec 副本上。返回 (新 spec 或 None, 说明)。"""
    segments = spec.get("segments") or []
    if not isinstance(model_segments, list) or len(model_segments) != len(segments):
        return None, f"段数不符：spec {len(segments)} 段，模型给了 " \
                     f"{len(model_segments) if isinstance(model_segments, list) else '非数组'}"
    revised = copy.deepcopy(spec)
    changed = []
    for index, (seg, patch) in enumerate(zip(revised["segments"], model_segments)):
        if not isinstance(patch, dict) or not patch:
            continue
        if seg.get("quote"):
            return None, f"段{index} 是 quote 段（字幕钉在真实时刻上），不许动"
        if seg.get("image"):
            return None, f"段{index} 是整屏证据卡，不许动"
        for key in patch:
            if key not in {"start", "end", "narration"}:
                return None, f"段{index} 出现越权字段 {key!r}"
        if "narration" in patch:
            original = str(seg.get("narration") or "")
            new = str(patch["narration"])
            if not deletion_only(original, new):
                return None, f"段{index} 旁白不是「只删不改写」（出现了原文没有的字）"
            if original.strip() and not new.strip():
                return None, f"段{index} 旁白被删空了——有旁白的段不许变成纯现场声"
            if new != original:
                seg["narration"] = new
                changed.append(f"段{index} 旁白删短")
        try:
            start = float(patch.get("start", seg["start"]))
            end = float(patch.get("end", seg["end"]))
        except (TypeError, ValueError, KeyError):
            return None, f"段{index} 的 start/end 不是数"
        if end - start < 1.0:
            return None, f"段{index} 窗口被改到 {end - start:.2f}s，短得没有意义"
        if (start, end) != (float(seg["start"]), float(seg["end"])):
            seg["start"], seg["end"] = round(start, 2), round(end, 2)
            changed.append(f"段{index} 窗口 → {seg['start']}–{seg['end']}")
    if not changed:
        return None, "模型一处都没改"
    return revised, "；".join(changed)


def local_gate(spec: dict, slug: str) -> str | None:
    """修订版先过同一套本地闸（dry-run 子进程）。返回失败摘要或 None。

    子进程跑的是生产入口本身（validate_spec + 措辞 seat + probe 层含静音预判），
    不另抄一份判据——查的东西和跑的东西必须是同一份。
    """
    with tempfile.TemporaryDirectory() as tmp:
        spec_path = Path(tmp) / f"{slug}.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "tools/build_match_reel.py", "render",
                 "--dry-run", "--spec", str(spec_path),
                 "--outdir", str(Path(tmp) / "dry")],
                capture_output=True, text=True, cwd=ROOT, timeout=180)
        except subprocess.TimeoutExpired:
            # 闸跑不完当闸红处理——修不修得成要有一个确定答案，不许带崩工具
            return "本地闸（dry-run 子进程）180 秒没跑完，按闸红处理"
    if proc.returncode == 0:
        return None
    return (proc.stdout + proc.stderr)[-1200:]


def repair(spec_path: Path, findings_text: str, outdir: Path,
           write: bool) -> str:
    """一轮有界修复。返回给日志的一句话结论（工具本身永远 exit 0）。"""
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    production = spec.get("_production") or {}
    if production.get("status") != "ready_for_render":
        return "[skip] 不是自动 spec（_production.status != ready_for_render），留给会话"
    attempts = int(production.get("qc_repair_attempts") or 0)
    if attempts >= MAX_ATTEMPTS:
        return f"[skip] 已自动修过 {attempts} 轮还红，不再自动改，留给会话"

    findings = salient_findings(findings_text)
    if not CONTENT_CLASS.search(findings):
        return "[skip] 判据不是窗口/旁白/静音类（多半是环境错），改 spec 修不了"

    from tennislive.research.brief import Chat  # noqa: PLC0415
    chat = Chat()
    if not chat.ready:
        return "[skip] 没配 DEEPSEEK_API_KEY / ANTHROPIC_API_KEY，退化出声"
    print(f"通道 {chat.channel}；第 {attempts + 1}/{MAX_ATTEMPTS} 轮自动修复")

    user = (f"被打回的判据（确定性输出，逐行是真的）：\n{findings}\n\n"
            f"当前 segments：\n{segment_brief(spec)}\n\n"
            f"源片机械事实：\n{probe_facts(outdir)}\n")
    answer = chat.ask(SYSTEM, user, schema=SCHEMA, max_tokens=2400)
    if not isinstance(answer, dict):
        return "[skip] 模型这步没成（见日志），本轮不修"
    if not answer.get("fixable"):
        return f"[skip] 模型判定修不了：{answer.get('note', '')}"

    revised, detail = apply_bounded(spec, answer.get("segments") or [])
    if revised is None:
        return f"[skip] 模型输出越界，整体丢弃：{detail}"

    slug = str(spec.get("slug") or spec_path.stem)
    failure = local_gate(revised, slug)
    if failure:
        return f"[skip] 修完仍过不了本地闸，不落盘。闸的原话：\n{failure}"

    revised.setdefault("_production", {})["qc_repair_attempts"] = attempts + 1
    revised["_production"]["qc_repair_note"] = (
        f"第 {attempts + 1} 轮判据回喂自动修复：{detail}。模型说明：{answer.get('note', '')}")
    if write:
        spec_path.write_text(
            json.dumps(revised, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        return f"[repaired] {detail}（已写回 {spec_path}，本地闸全过）"
    return f"[repaired dry-run] {detail}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--spec", required=True, type=Path)
    ap.add_argument("--findings", required=True, type=Path,
                    help="捕获的失败日志（dry-run/render/QC 的 tee 输出）")
    ap.add_argument("--outdir", required=True, type=Path,
                    help="本 slug 的产物目录（读 probe.json 的机械事实）")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    print(repair(args.spec, args.findings.read_text(encoding="utf-8"),
                 args.outdir, args.write))
    return 0


if __name__ == "__main__":
    sys.exit(main())
