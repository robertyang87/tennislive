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
            # T0 探测的搜索词要用：赛事名（剥赞助商前缀）+ 年份。
            "event": m.tournament.name,
            "year": m.start_utc.year if m.start_utc else date.today().year,
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
    # ⚠️ preview 目前只报不 dispatch（spec 还没自动生成），见 main() 的闸。
    return {"reel": "match-reel.yml", "preview": "preview-reel.yml"}.get(
        column, "match-reel.yml")


def assemble_draft(c: dict, *, skip: bool = False) -> list[str]:
    """dispatch probe 之后顺手备料。返回 notes（每句一行），失败也不抛。

    ⚠️ 只打印草稿、不落盘——正式 spec 永远人终审后自己写，落盘是 assemble_spec
    自己 `--write` 的事。备料失败（没配 key、flashscore 反查不到）都出声，
    不许把 dispatch 那一步带崩：probe 已经点下去了，备料只是顺带的便宜货。
    """
    if skip:
        return ["[assemble] 已跳过（--no-assemble）"]
    try:
        from assemble_spec import assemble
        draft = assemble(slug=c["slug"], home=c["home"], away=c["away"],
                         event=c["event"], year=c["year"], fixture="",
                         flashscore_id=None)
        return [f"[assemble] {c['slug']} 草稿备好（未落盘）", *draft["_notes"]]
    except Exception as exc:  # noqa: BLE001 —— 备料失败不许把 dispatch 带崩
        return [f"[assemble] {c['slug']} 备料没成（{type(exc).__name__}: {exc}）"
                "——不影响 probe，终审时手动补"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="真的 gh workflow run；不给就是干跑只打印")
    ap.add_argument("--max", type=int, default=DEFAULT_MAX,
                    help="单次最多点几条 run（无人值守防错一片，默认 %(default)s）")
    ap.add_argument("--column", choices=["reel", "preview"], default=None,
                    help="只看某一栏")
    ap.add_argument("--no-assemble", action="store_true",
                    help="dispatch probe 后不跑 assemble 备料（默认会跑，只打印草稿）")
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

    # **走 `find_highlight`，不要自己拼「搜一次然后挑一条」**——优先级链
    # （主路 YouTube → 备选 Tennis TV 免费短集锦）只有那一处实现，写两处必分叉，
    # 而分叉的样子是「手动跑说探到了，自动班次说没探到」。
    from detect_highlights import find_highlight, query_for

    dispatched: list[dict] = []
    for c in todo:
        wf = _workflow_for(c["column"])
        if c["column"] == "reel":
            # 完赛片（赛场之上）要集锦 URL 才能 probe——先 T0 探测。
            q = query_for(c["home"], c["away"], c["event"], c["year"])
            url, via = find_highlight(c["home"], c["away"], c["event"], c["year"])
            if not url:
                print(f"  [{c['slug']}] 集锦还没探到（{q[:40]}…），跳过，下次再探")
                continue
            # 走了哪条路要进日志：短集锦是定长 2 分半的剪短版，和 YouTube 那批
            # 2~8 分钟的不是一回事，写 spec 的人要知道自己拿到的是哪一种。
            print(f"  [{c['slug']}] 源片走 {via}")
            cmd = ["gh", "workflow", "run", wf, "--ref", "main",
                   "-f", "mode=probe", "-f", f"slug={c['slug']}", "-f", f"url={url}"]
        else:
            # 开球之前：没有单条集锦、spec 还没生成，先只报不 dispatch。
            print(f"  [{c['slug']}] 开球之前暂不自动 dispatch（spec 待生成）")
            continue
        print(f"[dispatch] {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        dispatched.append(c)
        # 备料：probe 出缩略图墙之后，草稿自动跟着备好（只打印不落盘）。手动控制
        # 途径留三处：--apply 是总开关、--no-assemble 关备料、落盘要 assemble 自己
        # 的 --write。文案那步在没配 DeepSeek key 的环境会退化出声，不静默。
        if c["column"] == "reel":
            for note in assemble_draft(c, skip=args.no_assemble):
                print(f"      {note}")
    mark_dispatched(state, dispatched)
    print(f"已点 {len(dispatched)} 条 run 并记入 state。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
