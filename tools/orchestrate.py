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
    python tools/orchestrate.py --apply --max 8  # 真点 run，最多 8 场
    python tools/orchestrate.py --column reel    # 只看赛场之上
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tennislive.digest import build_digest  # noqa: E402
from tennislive.models import MatchStatus  # noqa: E402
from tennislive.render.rating import (  # noqa: E402
    TOUR_FOCUS_LEVELS, _level_of, is_upset, match_score)
from tennislive.zh import player_name_en  # noqa: E402
from tennislive.zh.terms import round_zh  # noqa: E402

# 编排器按**北京时间**的「今天」抓 digest——凌晨结束的欧美比赛在 flashscore 算
# 昨天，build_digest 自己会把昨日也并进 results，这里只负责给它「今天」这个锚点。
def _beijing_today() -> date:
    return (datetime.now(timezone.utc) + timedelta(hours=8)).date()

# 250 及以上才算「巡回赛级别」，读者认得出来（docs/columns.md 的选题门槛）。
# ⚠️ **这张表要按级别解析器的产出写，不能按档位口语写。**
# `tournament_level()`（src/tennislive/zh/tournaments.py `_resolve_level_token`）
# 吐出来的是 `ATP500/WTA500/ATP250/WTA250` 这类**全称**，从来不产裸的
# "500"/"250"——第一版这里写了裸档位名，整个 500/250 档被静默过滤，而漏掉的
# 样子和「今天没有 500/250 的候选」一模一样（实跑验证过）。所以从
# `rating.TOUR_FOCUS_LEVELS`（同一个 `_level_of` 的消费者）推导，**一个出处**，
# 只补一个它没有的 TeamCup。判据 `test_ATP500这一档不许被裸档位名静默筛掉`。
TOUR_LEVELS = frozenset(TOUR_FOCUS_LEVELS) | {"TeamCup"}
STATE_PATH = Path("data/orchestration_state.json")
SPECS_DIR = Path("specs/reels")
# 单次点 run 的上限：账号所有者 2026-08-18 定「最大任务放开到 8」——好多比赛
# 可能同时结束，3 条会让后面几场排到下一班（30 分钟后），时效性高的场次等不起。
# 8 条并发在 Actions 并发额度内（免费档默认 20 个并发 job）；错一片的风险由
# 「推微信 = 账号所有者审核通道」兜着，不在调度层再压。
DEFAULT_MAX = 8

# 「上一个比赛日的不要做了」（账号所有者 2026-08-17，CLAUDE.md 有专节）落到
# 机器上：完赛超过这个小时数的一律不入候选。20 不是拍的：flashscore 的换日
# 刀口实测在傍晚（19:10Z~22:45Z 之间日场整批翻页，CLAUDE.md「换日的那一刀
# 在傍晚」），一场球从开打到「过期」最长约一个比赛日＋夜场尾巴；20 小时
# 盖得住「昨晚夜场今早备料」，又不会把整整一天前的日场（≥24h）放进来。
FRESH_RESULT_HOURS = 20

# 调度侧热度预筛的名次线。⚠️ **必须和渲染侧 `build_match_reel.HEAT_TOP_RANK`
# 是同一个数**——两侧不同的话，调度放行的候选注定死在下游 `--dry-run` 的
# `_players_are_worth_a_reel` 闸上，白烧一趟 probe（正是这道预筛要防的事）。
# 不直接 import 是因为 orchestrate.yml 只装 `pip install -e .`，不该为一个
# 整数背上 build_match_reel 顶层依赖漂移的风险；等值由
# `test_调度侧热度线和渲染侧那道闸是同一个数` 钉住。
HEAT_TOP_RANK = 20

# 热点名单（CLAUDE.md「⭐⭐ 而热点长什么样」那节，账号所有者逐个点名的四个人）：
# 赫瓦林斯卡 Chwalinska / 霍达尔 Jodar / 伊埃拉 Eala / 丰塞卡 Fonseca。
# ⚠️ 霍达尔是 **Jodar**（Rafael Jodar，19 岁打进大师赛半决赛那位），
# **不是 Fils**——菲斯才是 Fils，按音译猜会认错人（`player_zh()` 核过：
# "Rafael Jodar"→霍达尔、"Arthur Fils"→菲斯）。按姓匹配（和 slug 同一套
# surname 提取）、小写。名单是四个已点过名的例子不是上限：不在名单上的热点
# 由人工 spec 的 `cover._heat_why` 认领（渲染侧那道闸的 ③ 出口）。
HOT_SURNAMES = frozenset({"chwalinska", "jodar", "eala", "fonseca"})

# 去重条目的寿命。7 天后过期清掉——同一个 slug（同对手再交手、或者
# 王曦雨/王欣瑜这类同姓撞 slug）不该被一条老记录**永久**压住。
STATE_TTL_DAYS = 7


def _surname(name: str) -> str:
    """英文名取姓。名字有两种形状，姓的位置相反：

      "Alexandra Eala"   → 名在前，姓在最后一个词 → "Eala"
      "Kenin S."         → 姓在前，名缩写成首字母点 → 姓在第一个词 → "Kenin"
    ⚠️ 判据：最后一个词若是「单个字母 + 点」（缩写名的形状），就取第一个词；
    否则取最后一个词。不修这个，ESPN 缩写名会产出 `s.-e.` 这种垃圾 slug，
    同一场比赛还和全名版各得一个 slug，去重失效、dispatch 点错目录。
    """
    words = [w for w in (name or "").strip().split() if w]
    if not words:
        return ""
    last = words[-1]
    if len(last.rstrip(".")) == 1 and last.endswith("."):
        return words[0]            # 缩写名：姓在开头
    return last


def slug_for(m) -> str:
    """从两个球员的英文名取姓，拼成 slug（和 specs/reels/<slug>.json 一个形状）。"""
    return f"{_surname(m.home[0].name).lower()}-{_surname(m.away[0].name).lower()}"


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


def _stale_result(m, now: datetime) -> bool:
    """完赛超过 `FRESH_RESULT_HOURS` 的算上一个比赛日，不做。

    ⚠️ `start_utc` 缺失**不算过期**——「判不了」和「过期了」是两回事，
    缺时间就全 drop 的样子和「今天没有候选」一模一样（空结果先自证是真空）。
    """
    if m.start_utc is None:
        return False
    start = m.start_utc
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return (now - start) > timedelta(hours=FRESH_RESULT_HOURS)


def hot_enough(m) -> str:
    """调度侧热度预筛：返回命中的理由（空串＝不够热，别入候选）。

    镜像渲染侧 `build_match_reel._players_are_worth_a_reel`（中国球员 / 世界
    前 20 / 显式认领）——**两侧不是同一套的话，调度放行的候选注定死在下游
    `--dry-run` 的热度闸上，白烧一趟 probe**（W1000 R64 双无名种子 45 分就
    过打分门槛，正是这个形状）。调度侧没有 spec 可写 `cover._heat_why`，
    认领那一档换成三条机器判得动的：热点名单、轮次≥半决赛（账号所有者
    2026-08-12「半决赛级别的都要做」）、爆冷。
    """
    players = m.home + m.away
    if any((p.country or "").upper() == "CHN" for p in players):
        return "中国球员"
    if any(p.rank is not None and p.rank <= HEAT_TOP_RANK for p in players):
        return f"世界前{HEAT_TOP_RANK}"
    if any(_surname(p.name).lower() in HOT_SURNAMES for p in players):
        return "热点名单"
    if (round_zh(m.round_name) or "") in {"决赛", "半决赛"}:
        return "半决赛及以上"
    if m.status.is_final and is_upset(m):
        return "爆冷"
    return ""


def _match_date(m) -> str:
    """这场球的比赛日（UTC 日期）。没有 start_utc 就退回北京今天——
    去重键要一个日期，缺了宁可粗一点也不能没有。"""
    if m.start_utc is not None:
        return m.start_utc.date().isoformat()
    return _beijing_today().isoformat()


def candidates(digest) -> list[dict]:
    """扫 digest，返回过门槛的候选（按分降序）。只认单打巡回赛级别。

    ⚠️ 只扫 results（完赛）+ schedule（未开赛），**不扫 live**——进行中的比赛
    既不能复盘也不能前瞻，别给一场正在打的比赛发内容。
    """
    out = []
    now = datetime.now(timezone.utc)
    for m in digest.results + digest.schedule:
        if _level_of(m) not in TOUR_LEVELS:
            continue
        if len(m.home) != 1 or len(m.away) != 1:
            continue                      # 双打/团队赛不做（选题优先级规矩）
        if m.status.is_final and _stale_result(m, now):
            continue                      # 上一个比赛日的不做
        heat = hot_enough(m)
        if not heat:
            continue                      # 调度侧热度预筛，见 hot_enough
        score = match_score(m)
        if score < 38:                    # 和内容雷达同一道热度门槛
            continue
        out.append({
            "slug": slug_for(m),
            "column": route(m),
            "score": score,
            "heat": heat,
            "level": _level_of(m),
            "round": m.round_name or "",
            # ⚠️ 缩写名还原成全名再往下传——detect_highlights 的搜索词和
            # assemble 的译名都要全名，缩写（Kovacevic A.）直接拿去搜会搜错。
            "home": player_name_en(m.home[0].name),
            "away": player_name_en(m.away[0].name),
            "status": str(m.status),
            # T0 探测的搜索词要用：赛事名（剥赞助商前缀）+ 年份。
            "event": m.tournament.name,
            "year": m.start_utc.year if m.start_utc else date.today().year,
            # 去重用的比赛日：state 里按它分辨「同一场」和「同对手再交手」。
            "date": _match_date(m),
        })
    # 同一场比赛会在 digest 里出现两次（一个源给全名、一个源给缩写），slug_for
    # 归一之后两者同 slug。按 slug 去重，**优先留全名版**——home/away 名字越长、
    # 越不含缩写点的那条才是 assemble 和 detect_highlights 要的全名。
    dedup: dict[str, dict] = {}

    def _fuller(a: dict, b: dict) -> dict:
        key = lambda x: (len(x["home"]) + len(x["away"])
                         - (x["home"].count(".") + x["away"].count(".")))
        return a if key(a) >= key(b) else b

    for c in out:
        prev = dedup.get(c["slug"])
        dedup[c["slug"]] = c if prev is None else _fuller(prev, c)
    return sorted(dedup.values(), key=lambda c: c["score"], reverse=True)


def load_state() -> dict:
    """读 state 并顺手做过期清理：条目超过 `STATE_TTL_DAYS` 天就清掉。

    ⚠️ **键仍然是裸 slug，不带日期**——match-reel.yml 的失败自愈步骤
    （probe 失败把 slug 从 state 摘掉那段）按裸 slug 查，改键格式会把那条
    路打哑（「SLUG 不在 state 里」恒真）。「同对手再交手」靠条目里的
    `date` 字段分辨，见 `dispatch_plan`。
    """
    if not STATE_PATH.is_file():
        return {"dispatched": {}}
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    cutoff = date.today() - timedelta(days=STATE_TTL_DAYS)
    kept: dict = {}
    for slug, entry in (state.get("dispatched") or {}).items():
        try:
            d = date.fromisoformat(str((entry or {}).get("date", "")))
        except ValueError:
            print(f"[state] {slug} 的 date 读不出来，按过期清掉")
            continue
        if d >= cutoff:
            kept[slug] = entry
    state["dispatched"] = kept
    return state


def _same_match_day(a: str | None, b: str | None) -> bool:
    """两个比赛日算不算「同一场」的日期。±1 天算同一场——跨午夜的夜场在
    两个源/两次扫描里会落到相邻两天；真正的「同对手再交手」（换一站）至少
    隔好几天。读不出日期按「同一场」处置（宁可漏点一条，别重复点 run）。"""
    try:
        da = date.fromisoformat(str(a))
        db = date.fromisoformat(str(b))
    except ValueError:
        return True
    return abs((da - db).days) <= 1


def _already_specced(slug: str) -> Path | None:
    """人工会话可能已经做过这一场：正式 spec、pending 候车室、pending 草稿，
    任一存在就不用再 dispatch probe 备料。"""
    for p in (SPECS_DIR / f"{slug}.json",
              SPECS_DIR / "pending" / f"{slug}.json",
              SPECS_DIR / "pending" / f"{slug}.draft.json"):
        if p.is_file():
            return p
    return None


def _specced_surname_pairs() -> dict[frozenset[str], Path]:
    """扫一遍 `specs/reels/*.json`，从 `cover.matchup` 里认出「这两个姓已经
    有人做过」——**不按文件名**，按比赛双方的姓（不分先后）。

    ⚠️ **`_already_specced` 只按裸 slug（`slug_for(m)` 生成的
    `<home姓>-<away姓>`）比对，而人工 spec 的文件名几乎从不长这样**——
    这个仓库自己的命名习惯是赢家在前（不是 home/away 顺序），还常常带赛事
    轮次后缀（`-cincinnati-2026-sf` 这类）。2026-08-23 干跑就实测撞上了：
    `gauff-bejlek-cincinnati-2026-sf.json` 刚合并进 main，`--dry-run` 还是
    把「贝莱克 vs 高芙」报成一条全新候选（`slug_for` 拼出来的是
    `bejlek-gauff`，和真实文件名一个字都对不上）。`--apply` 真跑起来的话，
    这就是一次白白的重复 dispatch——而且不报错，看起来和「这是条新比赛」
    一模一样。

    所以再加一层**按姓的集合**去比对，姓来自 `cover.matchup[].name_en`
    ——`name` 那一栏是中文（"高芙"这种），`_surname()` 是按英文名的空格/
    缩写规则写的，拿中文喂它只会取整个中文名当"姓"，没用也不会错判，
    干脆只认 `name_en`。只扫 `specs/reels/`——`pending/` 那两处仍然靠
    `_already_specced` 的精确文件名，草稿本来就该按 orchestrator 自己
    生成的 slug 存放。
    """
    out: dict[frozenset[str], Path] = {}
    for p in sorted(SPECS_DIR.glob("*.json")):
        try:
            spec = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        matchup = (spec.get("cover") or {}).get("matchup") or []
        surnames = set()
        for m in matchup:
            if not isinstance(m, dict):
                continue
            sn = _surname(str(m.get("name_en") or "")).lower()
            if sn:
                surnames.add(sn)
        if len(surnames) == 2:
            out[frozenset(surnames)] = p
    return out


def dispatch_plan(cands: list[dict], state: dict) -> list[dict]:
    """过滤已 dispatch 的和已有 spec 的，返回「真正要点 run」的那几条。

    去重键是 slug ＋ 比赛日期（state 条目里的 `date`）：同 slug 但日期差了
    不止一天，就是**同对手再交手**（或同姓撞 slug），不许被老条目永久压住
    ——老版本按裸 slug 永久去重，`date` 字段写了从来没读过。

    ⚠️ **按姓的集合再查一遍，不止查裸 slug。** `_already_specced` 只认
    orchestrator 自己生成的那个 slug（home 姓-away 姓），而人工/AI 会话
    起的文件名几乎从不长这样——赢家在前、常带赛事轮次后缀。裸 slug 查不到
    不等于真没人做过，`_specced_surname_pairs()` 从每条 spec 的
    `cover.matchup` 里认人，跟文件名怎么起无关。

    ⚠️ **这一层不比对日期**（`_specced_surname_pairs` 没有日期可比——spec
    本身不存这个字段）。风险是这两位球员真的**短期内又打了一场**会被误判
    成"已经做过"而漏掉——但这个风险比"重复 dispatch 同一场"小得多（同一
    对手短期内再碰头本来就罕见），而且和上面 `_same_match_day` 那句
    "读不出日期按同一场处置，宁可漏点一条，别重复点 run"是同一个偏向，
    不是这次新引入的判断。
    """
    done = state.get("dispatched", {})
    specced_pairs = _specced_surname_pairs()
    fresh = []
    for c in cands:
        entry = done.get(c["slug"])
        if entry is not None and _same_match_day(entry.get("date"), c.get("date")):
            continue
        spec = _already_specced(c["slug"])
        if spec is not None:
            print(f"  [{c['slug']}] 已有 spec（{spec}），人工大概已经做过，跳过")
            continue
        pair = frozenset({_surname(c.get("home", "")).lower(),
                          _surname(c.get("away", "")).lower()})
        by_pair = specced_pairs.get(pair) if len(pair) == 2 else None
        if by_pair is not None:
            print(f"  [{c['slug']}] 这两位选手已经有 spec（{by_pair}，"
                  "文件名不一样但是同一对球员），跳过")
            continue
        fresh.append(c)
    return fresh


def mark_dispatched(state: dict, dispatched: list[dict]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    for c in dispatched:
        state.setdefault("dispatched", {})[c["slug"]] = {
            "column": c["column"],
            "score": c["score"],
            # ⚠️ 记**比赛日期**不是 dispatch 日期——`dispatch_plan` 按它分辨
            # 「同一场」和「再交手」；记今天的话，跨午夜的场次下一班就对不上、
            # 同一场重复点 run。
            "date": c.get("date") or date.today().isoformat(),
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
    """⚠️ 已弃用：备料职责移到了 probe 工作流的「自动备料写 spec 草稿」步骤
    （那儿有 captions + DeepSeek key + 能写盘），编排器不再本地跑 assemble。

    留着这个函数是为了不破坏它名下三条测试的历史判据——「备料失败不许把
    dispatch 带崩」这条规矩仍然成立，只是执行点换到了 probe 工作流里。
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
                    help="dispatch probe 时不传 home/away，跳过工作流里的自动备料写草稿")
    args = ap.parse_args()

    dig = build_digest(_beijing_today())
    cands = candidates(dig)
    if args.column:
        cands = [c for c in cands if c["column"] == args.column]
    state = load_state()
    fresh = dispatch_plan(cands, state)

    if not cands:
        print("今天没有过门槛的候选（≥250 单打、本比赛日、热度预筛、分 ≥38）。")
        return 0
    print(f"{len(cands)} 条候选（门槛之上），其中 {len(fresh)} 条还没 dispatch：")
    for c in cands:
        mark = "→ 点 run" if c in fresh else "  （已做过）"
        print(f"  [{c['column']:8}] {c['score']:3}分  {c['slug']:30} "
              f"{c['home']} vs {c['away']}{mark}")

    if not args.apply:
        print("\n这是干跑。要真点 run 加 --apply。")
        return 0

    for c in fresh:
        if c["column"] != "reel":
            # 开球之前：没有单条集锦、spec 还没生成，先只报不 dispatch。
            print(f"  [{c['slug']}] 开球之前暂不自动 dispatch（spec 待生成）")
    reel_todo = [c for c in fresh if c["column"] == "reel"]
    if not reel_todo:
        print("没有新场次要 dispatch。")
        return 0

    import subprocess
    from concurrent.futures import ThreadPoolExecutor

    # **走 `find_highlight`，不要自己拼「搜一次然后挑一条」**——优先级链
    # （主路 YouTube → 备选 Tennis TV 免费短集锦）只有那一处实现，写两处必分叉，
    # 而分叉的样子是「手动跑说探到了，自动班次说没探到」。
    from detect_highlights import find_highlight

    # ⚠️ **探测并行，dispatch 串行。** 探测是 IO 密集（yt-dlp 搜索 + Tennis TV
    # 翻页，一场可能几秒到十几秒），多场串行探测会线性累加，比赛时效性高的
    # 时候这就是延迟。并行探测把 N 场的探测时间压成「最慢那一场」。
    # dispatch 保持串行——gh workflow run 本身快（1~2 秒），而且要顺序写 state、
    # 顺序点 run，并行 dispatch 反而容易撞 concurrency 和 state 写入。
    def _probe(c: dict) -> tuple[dict, str | None, str]:
        url, via = find_highlight(c["home"], c["away"], c["event"], c["year"])
        return c, url, via

    with ThreadPoolExecutor(max_workers=min(8, len(reel_todo))) as pool:
        results = list(pool.map(_probe, reel_todo))

    # ⚠️ **配额切片要排在「真的会 dispatch」的过滤之后**——老版本先切
    # `[:max]` 再逐条跳过探不到源的，探不到的白占配额，探得到的反而排不进。
    dispatchable: list[tuple[dict, str, str]] = []
    for c, url, via in results:
        if not url:
            print(f"  [{c['slug']}] 集锦还没探到，跳过，下次再探")
            continue
        dispatchable.append((c, url, via))
    overflow = len(dispatchable) - args.max
    if overflow > 0:
        skipped = "、".join(c["slug"] for c, _u, _v in dispatchable[args.max:])
        print(f"  超出本班配额（--max {args.max}）的 {overflow} 条留给下一班：{skipped}")

    dispatched: list[dict] = []
    for c, url, via in dispatchable[: args.max]:
        wf = _workflow_for(c["column"])
        # 走了哪条路要进日志：短集锦是定长 2 分半的剪短版，和 YouTube 那批
        # 2~8 分钟的不是一回事，写 spec 的人要知道自己拿到的是哪一种。
        print(f"  [{c['slug']}] 源片走 {via}")
        cmd = ["gh", "workflow", "run", wf, "--ref", "main",
               "-f", "mode=probe", "-f", f"slug={c['slug']}", "-f", f"url={url}"]
        # home/away/event/year 传给 probe，触发工作流里的「自动备料写 spec 草稿」。
        # --no-assemble 就不传这几个，probe 只出缩略图墙不备料——手动控制开关。
        if not args.no_assemble:
            cmd += ["-f", f"home={c['home']}", "-f", f"away={c['away']}",
                    "-f", f"event={c['event']}", "-f", f"year={c['year']}"]
        print(f"[dispatch] {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        # ⚠️ **每条 dispatch 成功立即落盘**，不是循环完再记：第 N 条 gh 失败时
        # 前 N-1 条已经点出去了——攒到最后一次性记的话，一条失败就让之前全部
        # 失忆，下一班同一场 probe 重复点。state 提交回仓库仍在工作流末尾一次。
        dispatched.append(c)
        mark_dispatched(state, [c])
        # 备料不再在编排器本地跑——它没有 captions（probe 还没落库）也没 DeepSeek
        # key。probe 工作流里已经有「自动备料写 spec 草稿」一步（有 captions + key
        # + 能写盘），编排器只负责 dispatch probe 并把 home/away/event/year 传进去。
    print(f"已点 {len(dispatched)} 条 run 并记入 state。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
