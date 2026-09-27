"""赛后开麦成片**拼了哪几段**：出片时记进 `render.json`，L2 闸照着 spec 核。

## 来路

`render()` 里有两条「出不来就退回」的路，而它们**都是绿着退的**：

- `_takeaway_voice` 合不出口播 → 退回**数字静音**的收尾卡（`build_interview_clip`
  那句「口播合不出来，退回静音卡」）。账号所有者对这张卡的要求原话是「**但要有配音**」，
  而静音那一版前 10.8 秒峰值 −91 dB——`interview-clip.yml` 装 `edge-tts` 那一段注释
  记着它真出过一次，run 照样绿。
- `_build_outro` 渲不出来 → 返回 None，**这条片子没有品牌片尾**。

两条退路本身是对的（配音／片尾不该拖垮整条片子），错在**退了之后没人知道**：
`render.json` 只记 `film_sha256` / `film_seconds`，`check_interview_landed` 只量整条片子的
峰值——收尾卡那 6 秒是 −91 dB，整条的峰值照样 −10 dB，L2 全绿、自动推送照发。
（「赛场之上」那条线是对照组：`render.json` 记着 `outro_seconds`，`check_reel_landed` 核它。）

## 怎么记、怎么核

- 出片时（concat 之前）把拼接清单里每一段的**角色、时长、音轨峰值**记进
  `render.json["assembly"]`——峰值是**量出来的**，不是「调没调合成」的信号
- `check_interview_landed --film` 照 spec 核：写了收尾卡（`takeaway.close` / `open`）
  就必须有那一段、而且不是数字静音；品牌片尾那一段必须在
- 真是有意不要：`_takeaway_silent_why` / `_no_outro_why` 认领（目前全库 0 处）
- 没有 `assembly` 记录的成片（不是当前 `render()` 出的）→ 不合格，fail closed
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

SILENCE_FLOOR_DB = -60.0      # 和 check_interview_landed / check_reel_landed 同一条线

#: 拼接清单里的文件名 → 角色（文件名由 `build_interview_clip.render` 定）
ROLES = {
    "_cover.mp4": "cover",
    "_takeaway_open.mp4": "takeaway_open",
    "_lead.mp4": "lead_in",
    "_body.mp4": "body",
    "_trail.mp4": "trail_in",
    "_takeaway_close.mp4": "takeaway_close",
    "_outro.mp4": "outro",
}
#: 这几段要量音轨——都是我们自己合的声音，静音就是退路走过了
VOICED = ("takeaway_open", "takeaway_close", "outro")


def _seconds(path: Path) -> float | None:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=False, timeout=120)
    try:
        return round(float(proc.stdout.strip().split()[0]), 3)
    except (ValueError, IndexError):
        return None


def _peak_db(path: Path) -> float | None:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-vn", "-af", "volumedetect",
         "-f", "null", os.devnull], capture_output=True, text=True, check=False,
        timeout=300)
    found = re.search(r"max_volume:\s*(-inf|-?[\d.]+)\s*dB", proc.stderr)
    if not found:
        return None
    return -999.0 if found.group(1) == "-inf" else float(found.group(1))


def inventory(parts: list[Path]) -> list[dict]:
    """拼接清单 → [{role, file, seconds, peak_db?}]。量不到的记 None，不猜。"""
    out = []
    for p in parts:
        role = ROLES.get(p.name, p.name)
        row = {"role": role, "file": p.name, "seconds": _seconds(p)}
        if role in VOICED:
            row["peak_db"] = _peak_db(p)
        out.append(row)
    return out


def record(parts: list[Path], outdir: Path) -> dict:
    """量完写进 `render.json["assembly"]`（合并写，不覆盖别的键），返回写进去的那份。"""
    assembly = {"parts": inventory(parts)}
    path = outdir / "render.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    data["assembly"] = assembly
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    shown = []
    for row in assembly["parts"]:
        peak = row.get("peak_db")
        shown.append(row["role"] if peak is None else f"{row['role']}({peak:.0f}dB)")
    print(f"[拼接清单] {'、'.join(shown)} → {path.name}")
    return assembly


def problems(spec: dict, render_meta: dict) -> list[str]:
    """照 spec 核 `render.json["assembly"]` → 不合格项（空＝合格）。不跑 ffmpeg。"""
    assembly = (render_meta or {}).get("assembly")
    if not isinstance(assembly, dict) or not isinstance(assembly.get("parts"), list):
        return ["render.json 没记这条成片拼了哪几段（`assembly`）——不是当前 `render()` "
                "出的片，解读卡口播和品牌片尾在不在无从核对"]
    parts = {row.get("role"): row for row in assembly["parts"] if isinstance(row, dict)}
    bad = []
    for which in ("open", "close"):
        if not ((spec.get("takeaway") or {}).get(which)):
            continue
        role = f"takeaway_{which}"
        row = parts.get(role)
        if row is None:
            bad.append(f"spec 写了 `takeaway.{which}`，成片里却没有这张卡")
            continue
        peak = row.get("peak_db")
        if (peak is None or peak <= SILENCE_FLOOR_DB) \
                and not str(spec.get("_takeaway_silent_why") or "").strip():
            shown = "量不到" if peak is None else f"峰值 {peak:.0f} dB"
            bad.append(f"`takeaway.{which}` 那张卡{shown}——口播没合上，退回了静音卡"
                       "（「但要有配音」）。多半是 edge-tts 没装或连不上，看 render 那步的"
                       "「[解读卡] … 口播合不出来」；真要静音写 `_takeaway_silent_why`")
    outro = parts.get("outro")
    if (outro is None or not (outro.get("seconds") or 0) > 0) \
            and not str(spec.get("_no_outro_why") or "").strip():
        bad.append("成片没有品牌片尾——`_build_outro` 渲不出来时会静静返回 None，"
                   "看 render 那步的「[片尾] 渲不出来」；真要不带写 `_no_outro_why`")
    return bad
