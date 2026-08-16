#!/usr/bin/env python3
"""无人值守编排器：扫赛果/焦点场 → 打分路由 → 去重 → 并行 dispatch 生产工作流。

这是「半小时出片协议」（docs/thirty-minute-pipeline.md）里一直缺的那层
**检测 + 路由**。之前热点/赛果扫到了，「做哪条」仍靠人决定、手动 dispatch；
这个工具把这一层机械化：

  1. `build_digest()` 拉今日赛果 + 近期赛程
  2. `rating.match_score()` 打分，过门槛且 ≥250 的入选
  3. 完赛 → 赛场之上（reel）；未开赛的焦点场 → 开球之前（preview）
  4. 去重：`data/orchestration_state.json` 记已 dispatch 过的 slug，不重复点
  5. 默认 `--dry-run` 只打印计划；`--apply` 才真的 `gh workflow run`（一场一个
     run，GitHub Actions 按 slug 分组并发，天然并行）

口径（账号所有者 2026-08-15 定）：无人值守，全自动推微信，推完再看。

用法：
    python tools/orchestrate.py                  # 干跑，打印今天该做哪几条
    python tools/orchestrate.py --apply --max 3  # 真点 run，最多 3 场
    python tools/orchestrate.py --column reel    # 只看赛场之上
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tennislive.digest import build_digest  # noqa: E402
from tennislive.models import MatchStatus  # noqa: E402
from tennislive.render.rating import _level_of, match_score  # noqa: E402

# 250 及以上才算「巡回赛级别」，读者认得出来（docs/columns.md 的选题门槛）。
TOUR_LEVELS = frozenset({"GS", "M1000", "W1000", "500", "250", "Finals", "TeamCup"})
STATE_PATH = Path("data/orchestration_state.json")
# 单次点 run 的上限：无人值守 + 批量发微信，错一次错一片——先压着，跑稳再放宽。
DEFAULT_MAX = 3


def slug_for(m) -> str:
    """从两个球员的英文名取姓，拼成 slug（和 specs/reels/<slug>.json 一个形状）。

    名字形如 "Alexandra Eala" → 取最后一个词 "eala"；"Qinwen Zheng" → "zheng"。
    两个都取不到姓时退回整个名字，slug 只做目录名，不必严格等于译名。
    """
    def last(name: str) -> str:
        words = (name or "").strip().split()
        return (words[-1] if words else name).lower()
    return f"{last(m.home[0].name)}-{last(m.away[0].name)}"


def route(m) -> str:
    """完赛 → 赛场之上（reel）；未开赛 → 开球之前（preview）。

    赛后开麦（interview）不在这一层：它走采访源检测（oncourt-interviews），
    二期再并进来——采访片依赖「采访视频上线」，和「赛果出来」是两个钟。
    ⚠️ 进行中（live）的比赛**不该被路由**——它既不是能复盘的完赛，也不是
    能前瞻的未开赛。`candidates()` 里已把它排除，这里返回空串。
    """
    if m.status.is_final:
        return "reel"
    if m.status == MatchStatus.SCHEDULED:
        return "preview"
    return ""


def candidates(digest) -> list[dict]:
    """扫 digest，返回过门槛的候选（按分降序）。只认单打巡回赛级别。

    ⚠️ 只扫 results（完赛）+ schedule（未开赛），**不扫 live**——进行中的比赛
    既不能复盘也不能前瞻，别给一场正在打的比赛发内容。
    """
    out = []
    for m in digest.results + digest.schedule:
        if _level_of(m) not in TOUR_LEVELS:
            continue
        if len(m.home) != 1 or len(m.away) != 1:
            continue                      # 双打/团队赛不做（选题优先级规矩）
        score = match_score(m)
        if score < 38:                    # 和内容雷达同一道热度门槛
            continue
        out.append({
            "slug": slug_for(m),
            "column": route(m),
            "score": score,
            "level": _level_of(m),
            "round": m.round_name or "",
            "home": m.home[0].name,
            "away": m.away[0].name,
            "status": str(m.status),
        })
    out.sort(key=lambda c: c["score"], reverse=True)
    return out


def load_state() -> dict:
    if STATE_PATH.is_file():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"dispatched": {}}


def dispatch_plan(cands: list[dict], state: dict) -> list[dict]:
    """过滤已 dispatch 的，返回「真正要点 run」的那几条。"""
    done = state.get("dispatched", {})
    fresh = [c for c in cands if c["slug"] not in done]
    return fresh


def mark_dispatched(state: dict, dispatched: list[dict]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    for c in dispatched:
        state.setdefault("dispatched", {})[c["slug"]] = {
            "column": c["column"],
            "score": c["score"],
            "date": date.today().isoformat(),
        }
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                          encoding="utf-8")


def _workflow_for(column: str) -> str:
    # 赛场之上（reel）走 match-reel.yml；开球之前（preview）走**独立的**
    # preview-reel.yml——账号所有者 08-08 定了「单独走一条管线」，不和
    # match-reel（赛场之上那条）混，也不走 explainer（卡片视频）。
    # ⚠️ preview-reel.yml 还没建（preview_beats.py 还缺 assemble/CLI），
    # 建好之前编排器对 preview 只 print 计划、点 run 会失败——见 main() 的闸。
    return {"reel": "match-reel.yml", "preview": "preview-reel.yml"}.get(
        column, "match-reel.yml")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="真的 gh workflow run；不给就是干跑只打印")
    ap.add_argument("--max", type=int, default=DEFAULT_MAX,
                    help="单次最多点几条 run（无人值守防错一片，默认 %(default)s）")
    ap.add_argument("--column", choices=["reel", "preview"], default=None,
                    help="只看某一栏")
    args = ap.parse_args()

    dig = build_digest()
    cands = candidates(dig)
    if args.column:
        cands = [c for c in cands if c["column"] == args.column]
    state = load_state()
    todo = dispatch_plan(cands, state)[: args.max]

    if not cands:
        print("今天没有过门槛的候选（≥250 单打、分 ≥38）。")
        return 0
    print(f"{len(cands)} 条候选（门槛之上），其中 {len(todo)} 条还没 dispatch：")
    for c in cands:
        mark = "→ 点 run" if c in todo else "  （已做过）"
        print(f"  [{c['column']:8}] {c['score']:3}分  {c['slug']:30} "
              f"{c['home']} vs {c['away']}{mark}")

    if not args.apply:
        print("\n这是干跑。要真点 run 加 --apply。")
        return 0

    if not todo:
        print("没有新场次要 dispatch。")
        return 0

    import subprocess
    for c in todo:
        wf = _workflow_for(c["column"])
        cmd = ["gh", "workflow", "run", wf, "--ref", "main",
               "-f", f"mode=probe", "-f", f"slug={c['slug']}"]
        print(f"[dispatch] {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
    mark_dispatched(state, todo)
    print(f"已点 {len(todo)} 条 run 并记入 state。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
