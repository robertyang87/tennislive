#!/usr/bin/env python3
"""为 pending reel 重试同场官方高清封面；只在真正找到时改封面。

赛后图片常比集锦晚几十分钟。probe 当下没图不是永久失败；本工具让定时 ready
工作流继续查 Tennis TV/WTA 官方来源。查不到返回 0、封面不动；不制造每十分钟一笔
“仍然没图”的空提交（草稿只在**学到新东西**时才写：见下面 `_cover_api`）。

⭐⭐ 2026-09-28 起**第一档是 ATP Media／WTA 照片接口**（`cover_upgrade.pick_for_draft`，和 O4 同一套
机器闸：EXIF 拍摄时刻绑场次、全名、两人同框、发布限制、铺满不放大、认人、睁眼、钩子带）。封面时效实测：
10 条抽帧首推里 6 条，首推之前这两个接口里就有主角对的官方原图。每一班（10 分钟）都再查一遍，直到有；
**还没封面的草稿查不到从来不拦**——照原来那两条路（Tennis TV 页头图、WTA 赛后稿）接着走，和改之前一样。
⚠️ **已经有封面的草稿不是「和改之前一样」**：基线从不碰已有的封面，这一档会换掉**视觉审核因为封面判没过**
的那张（见下面「卡在视觉审核上的那张」）——只有这一种，封面判过了、别的没过的一律不动。

## 有墙钟上限（2026-09-28 复审 BLOCKING）

原来这一档没有任何时间上限：flashscore `dc_1` 走 `match_feed._get` 的 3 × 40 秒、照片接口每页／每个头
40 秒、每张原图 60 秒、最多 10 张——flashscore 挂住时一份草稿 128.7 秒、照片接口挂住时 80.1 秒（复审实测），
一班最多 18 份，冲过 job 的 15 分钟，落库和派发 render 那两步不跑，**封面早就好了的草稿也一起挡住**。现在：
- `--api-budget N`：这一份的总账 N 秒（`official_photo_apis.Budget`），每个请求的超时不超过剩下的；工作流按
  和 `FEED_RETRY_BUDGET` 同一个 `$SECONDS` 钟给（`COVER_API_DEADLINE`／`COVER_API_PER_DRAFT`），过了就
  `--no-api`（只走原来那两条路），外面再包一层 `timeout`
- flashscore 只试一次、10 秒；问到的开赛／结束记进草稿 `_cover_api.times`，下一班不再问
- 男女认不出的不查；认得出的**只跑一档**（`cover_upgrade.resolve_tour`：原来 52/129 份草稿两档都跑）

## 卡在视觉审核上的那张（2026-09-28 复审 BLOCKING）

已经有封面的只在一种情况下换：**这张封面被视觉审核判过、没过、不会重审，而且没过的理由里有封面**（`_visual_evidence`
的 `cover_image` 就是它、`status` 不是 pass、`retryable` 是 false、`problems` 里有一条说的是封面——`cover_problems`）。
⚠️ 最后那个条件是 FIX ROUND 2 补的：原来不看理由，`badosa-gauff` 封面审过了、只有结尾窗口不过，照样被换图，
换上的接口图下一班审过了又因为同一个结尾窗口进 `rejected`，一张接一张换到候选用完（`stuck_on_cover` 的注释）。原来这里写着「换一张只会解开」——
**对照片接口挑的那张不成立**：挑图不记得被判掉的是哪张，每一班重挑同一张（medvedev-royer 回放：第 2~4 班
都是 #4582136、草稿一个字节不变），也不再走 Tennis TV 那条路。现在：
- 照片接口挑的封面在 portrait 里记 `_source_url`；卡住时它进 `_cover_api.rejected`，挑图时排除
- 照片接口这一班没有别的能换、而卡住的正是照片接口那张：**接着走原来那两条路**（Tennis TV 页头图／WTA 赛后稿）
  ——改之前第一班就会走到那儿
- 卡住的这个状态已经完整查过一遍、没有能换的（`_cover_api.stuck_checked`）：不再每一班查、不再要认人依赖

## `_cover_api`：草稿里这一档自己的账（转正时剥掉，`promote_reel_draft`）

    {"times": {"flashscore_id", "start_utc", "end_utc", "source"},   # 问过一次就不再问
     "tried": [URL…],       # 下过、闸没过、结论确定（图本身的毛病）——不再下（复审 nit：bondar-birrell 每班 5.8 MB）
     "rejected": [URL…],    # 视觉审核判过没过的照片接口图——不再挑
     "stuck_checked": "…",  # 卡住的哪个状态已经完整查过（`stuck_key`）
     "replaced_under": "…"} # 换图时挂着的那份审核结论（`input_sha256`）——结论没变就是新图还没审，不算卡住

这几样变了才写草稿（每一样都有上限：times 一次、tried／rejected 随候选数、stuck_checked 随卡住的次数）。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from assemble_spec import _surname, fetch_tennistv_cover  # noqa: E402

#: 草稿里照片接口那一档自己的账（见模块 docstring）
API_STATE = "_cover_api"
#: `tried` 最多记多少条（同一个人同一站的候选一般不到 20 张）
TRIED_MAX = 60


#: 视觉审核（`analyze_reel_visuals.clean_report`）在没有封面时写的那一句
NO_COVER_PROBLEM = "没有官方高清封面候选"


def cover_problems(visual: dict | None) -> list[str]:
    """视觉审核的 `problems` 里**说的是封面**的那几条：开头是「封面」（同场／旧图、置信度、证据、人物、情绪——
    `clean_report` 的封面那一段全是这么开头的），或者 `NO_COVER_PROBLEM`。

    冷开场／结尾窗口、缺某一段证据、双语字幕（`main` 追加的那几句）都不算——**换封面解不开它们**。
    判据 `test_视觉审核只判了窗口没判封面_不算卡在封面上`：拿 `clean_report` 真出的每一种话钉住这个分界。"""
    if not isinstance(visual, dict):
        return []
    return [p for p in visual.get("problems") or []
            if isinstance(p, str) and (p.startswith("封面") or p.strip() == NO_COVER_PROBLEM)]


def stuck_on_cover(draft: dict) -> bool:
    """草稿是不是**卡死在现在这张封面上**：视觉审核审过的就是它、没过、不会重审，**而且没过的理由里有封面**
    （`cover_problems`）。

    ⚠️⚠️ 最后那半句是 2026-09-28 复审 FIX ROUND 2 的 BLOCKING：原来只看「没过、不重审」，**不看没过的是什么**——
    `badosa-gauff` 的视觉审核把封面判过了（same_match、高芙、winner_celebration、0.88），唯一一条是
    「ending 必须是 3-30 秒的完整收官窗口」，也被当成卡在封面上：照片接口把审过的 WTA 赛后稿头图换掉（同一个路径），
    下一班重审过了封面、结尾窗口照旧不过，于是刚审过的那张接口图又进 `rejected`、再换下一张——每换一次重审一次模型
    （冷开场／结尾的结论跟着重掷）、往 main 提交一张 4.7~9.6 MB（复审量的）的原图，直到候选用完；中途哪次重掷过了，转正的是
    排在后面的那张。改之前的基线从不碰已有的封面。25 份被判「卡住」的草稿里 3 份（badosa-gauff、sabalenka-pegula、
    sabalenka-townsend）一条封面问题都没有、13 份封面和别的一起没过。

    ⚠️ 换图写的是**同一个路径**（`assets/reel/<slug>-cover.jpg`），`cover_image == image` 认不出审的是不是
    这一张：刚换上、还没重审（这一班审核那一步挂了）的时候，旧结论还挂着。换图时记下当时那份结论的
    `input_sha256`（`_cover_api.replaced_under`）——结论还是那一份，就是**还没审**，不是卡住（不然下一班
    会把没审过的新图记进 `rejected`）。"""
    portrait = (draft.get("cover") or {}).get("portrait") or {}
    visual = draft.get("_visual_evidence") if isinstance(draft.get("_visual_evidence"), dict) else {}
    stuck = bool(portrait.get("image") and visual
                 and visual.get("cover_image") == portrait.get("image")
                 and visual.get("status") != "pass" and visual.get("visual_status") != "error"
                 and visual.get("retryable") is False
                 and cover_problems(visual))
    state = api_state(draft)
    if stuck and "replaced_under" in state and str(visual.get("input_sha256") or "") == state["replaced_under"]:
        return False
    return stuck


def stuck_key(draft: dict) -> str:
    """卡住的是**哪个状态**：这张封面（照片接口的记原图 URL）＋ 审它的那一批字节（`input_sha256`）。
    换了图、重审过，键就变了，照片接口那一档会再查一遍。"""
    portrait = (draft.get("cover") or {}).get("portrait") or {}
    visual = draft.get("_visual_evidence") if isinstance(draft.get("_visual_evidence"), dict) else {}
    return (f"{portrait.get('_source_url') or portrait.get('image') or ''}"
            f"#{visual.get('input_sha256') or ''}")


def api_state(draft: dict) -> dict:
    got = draft.get(API_STATE)
    return dict(got) if isinstance(got, dict) else {}


def _api_sourced(portrait: dict) -> bool:
    import cover_upgrade  # noqa: PLC0415

    return str(portrait.get("_portrait_why") or "").startswith(cover_upgrade.AUTO_DRAFT_WHY_PREFIX)


def official_api_cover(draft: dict, *, now: datetime | None = None, pick=None, write: bool = True,
                       budget: float | None = None, tried=(), rejected=(),
                       known_times: dict | None = None) -> tuple[tuple[dict, str] | None, dict]:
    """照片接口那一档（`cover_upgrade.pick_for_draft`）：全过闸就把**原图字节**写成
    `assets/reel/<slug>-cover.jpg`（不重编码，「封面图一律存原图」）、portrait 换成它（记 `_source_url`）。
    返回 ((草稿, 说明) 或 None, pick 的结果)。`write=False`（不带 `--write` 的试跑）：只报，不写图。"""
    import cover_upgrade  # noqa: PLC0415

    slug = str(draft.get("slug") or "").strip()
    if not slug:
        return None, {}
    kw = {"budget": budget, "tried": tried, "rejected": rejected, "known_times": known_times}
    if pick is None:
        got = cover_upgrade.pick_for_draft(draft, now or datetime.now(timezone.utc), **kw)
    else:
        got = pick(draft, now or datetime.now(timezone.utc), **kw)
    for line in got.get("report") or []:
        print(line)
    chosen = got.get("chosen")
    if not chosen:
        return None, got
    blob = chosen["blob"]
    if blob[:3] != b"\xff\xd8\xff":
        print(f"[照片接口] {slug} 挑中的不是 JPEG，不重编码也存不成 -cover.jpg，这一班不用")
        return None, got
    out = ROOT / "assets" / "reel" / f"{slug}-cover.jpg"
    if write:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blob)
    portrait = {"image": str(out.relative_to(ROOT)), **(got.get("portrait") or {})}
    portrait["_portrait_why"] = str(portrait.pop("_why", "")) or cover_upgrade.AUTO_DRAFT_WHY_PREFIX
    portrait.setdefault("_source_url", chosen["candidate"].url)
    draft.setdefault("cover", {})["portrait"] = portrait
    c = chosen["candidate"]
    return (draft, f"照片接口官方原图 {c.channel} #{c.item_id}（{c.filename}）"), got


def needs_official_pick(draft: dict, now: datetime | None = None) -> bool:
    """这份草稿这一班要不要跑照片接口那一档（工作流据此决定装不装认人的依赖、拉不拉模型）：
    编排器的新鲜草稿、这一档查得了（`cover_upgrade.draft_api_blocker`：不联网），而且还没有封面，
    或者卡死在现在这张封面上、这个卡住的状态还没完整查过（`_cover_api.stuck_checked`）。"""
    from promote_reel_draft import PENDING_MAX_AGE  # noqa: PLC0415

    import cover_upgrade  # noqa: PLC0415

    now = now or datetime.now(timezone.utc)
    prod = draft.get("_production") if isinstance(draft.get("_production"), dict) else {}
    if prod.get("kind") != "orchestrated_reel":
        return False
    try:
        got = datetime.fromisoformat(str(prod.get("received_at") or "").replace("Z", "+00:00"))
    except ValueError:
        return False
    if got.tzinfo is None or now - got > PENDING_MAX_AGE:
        return False
    portrait = (draft.get("cover") or {}).get("portrait") or {}
    has = bool(portrait.get("image") and Path(str(portrait["image"])).is_file())
    if has and not stuck_on_cover(draft):
        return False
    if has and api_state(draft).get("stuck_checked") == stuck_key(draft):
        return False
    return not cover_upgrade.draft_api_blocker(draft, now)


def slugs_with_probe() -> set[str] | None:
    """HEAD 上落了 probe 证据的 slug（工作流循环里同一个判法：`output/<日>/reel/<slug>/probe.json`）——
    循环会跳过没有 probe 的草稿，`--need-faces` 也不为它们装依赖。git 不可用返回 None（不过滤）。"""
    import re  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    try:
        out = subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD", "--", "output"],
                             cwd=ROOT, capture_output=True, text=True, timeout=60, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return {m.group(1) for m in re.finditer(r"^output/[^/]+/reel/([^/]+)/probe\.json$", out, re.M)}


def refresh(draft: dict, *, now: datetime | None = None, pick=None, write: bool = True,
            api: bool = True, budget: float | None = None) -> tuple[dict, str]:
    portrait = (draft.get("cover") or {}).get("portrait") or {}
    has = bool(portrait.get("image") and Path(str(portrait["image"])).is_file())
    stuck = has and stuck_on_cover(draft)
    if has and not stuck:
        return draft, "已有封面"
    state = api_state(draft)
    rejected = [str(u) for u in state.get("rejected") or [] if u]
    from_api = stuck and _api_sourced(portrait)
    if from_api and portrait.get("_source_url") and str(portrait["_source_url"]) not in rejected:
        rejected.append(str(portrait["_source_url"]))
    key = stuck_key(draft) if stuck else ""
    skip = ("这一班照片接口的时间预算用完了（--no-api）" if not api else
            "卡住的这张已经完整查过一遍照片接口、没有别的能换" if stuck and state.get("stuck_checked") == key
            else "")
    found, got = None, {}
    if skip:
        print(f"[照片接口] {draft.get('slug')}：不查——{skip}")
    else:
        try:
            found, got = official_api_cover(
                draft, now=now, pick=pick, write=write, budget=budget,
                tried=list(state.get("tried") or []), rejected=rejected,
                known_times=state.get("times"))
        except (Exception, SystemExit) as exc:  # noqa: BLE001 —— 这一档炸了照原来的路走
            print(f"[照片接口] 没查成（{type(exc).__name__}: {exc}）——照原来的路走")
    # 学到的记下来：问到的开赛／结束、下过没过的、被判掉的、卡住的这个状态查完了
    if got.get("times") and not state.get("times"):
        state["times"] = got["times"]
    tried = list(dict.fromkeys([*(state.get("tried") or []), *(got.get("tried") or [])]))[-TRIED_MAX:]
    if tried:
        state["tried"] = tried
    if rejected:
        state["rejected"] = rejected
    if stuck and not found and got.get("complete"):
        state["stuck_checked"] = key
    if found:
        state.pop("stuck_checked", None)
        visual = draft.get("_visual_evidence") if isinstance(draft.get("_visual_evidence"), dict) else {}
        state["replaced_under"] = str(visual.get("input_sha256") or "")
    if state != api_state(draft):
        draft[API_STATE] = state
    if found:
        return found
    if stuck and not from_api:
        return draft, ("已有封面（卡在视觉审核上；照片接口" + (f"这一班没查：{skip}" if skip else "这一班也没有能换的")
                       + "）")
    # 没封面，或者卡在**照片接口挑的那张**上：原来那两条路接着走（改之前第一班就会走到这儿）
    before = dict(portrait)
    draft, note = old_paths(draft)
    after = (draft.get("cover") or {}).get("portrait") or {}
    if after != before:
        # 换上了原来那条路的图：挂着的审核结论（如果有）是换图之前的，新这张还没审（`stuck_on_cover`）
        visual = draft.get("_visual_evidence") if isinstance(draft.get("_visual_evidence"), dict) else {}
        draft[API_STATE] = {**api_state(draft), "replaced_under": str(visual.get("input_sha256") or "")}
    return draft, note


def old_paths(draft: dict) -> tuple[dict, str]:
    """2026-09-28 之前就有的那两条路：Tennis TV 页头图（源片是 tennistv 的）、WTA 赛后稿／集锦头图。"""
    slug = str(draft.get("slug") or "").strip()
    event = str((draft.get("_production") or {}).get("event") or "").strip()
    source_url = str(draft.get("source_url") or "").strip()
    pair = (draft.get("cover") or {}).get("matchup") or []
    english = [str(p.get("name_en") or "").strip() for p in pair]
    if not slug or len(english) != 2 or not all(english):
        return draft, "草稿缺 slug/两位英文名"
    out = ROOT / "assets" / "reel" / f"{slug}-cover.jpg"

    if "tennistv.com" in urlparse(source_url).netloc.casefold():
        try:
            note = fetch_tennistv_cover(source_url, event, out)
            draft.setdefault("cover", {})["portrait"] = {
                "image": str(out.relative_to(ROOT)),
                "_portrait_why": "Tennis TV 本场官方页面关联的 ATP Media 高清图",
            }
            return draft, note
        except Exception:  # noqa: BLE001 —— 继续试 WTA 官方来源
            pass

    try:
        import requests
        from fetch_match_pbp import find_match
        from fetch_wta_cover_photo import fetch_cover

        today = date.today()
        session = requests.Session()
        event_id, year, match_id, _ = find_match(
            session, [_surname(name) for name in english],
            today - timedelta(days=7), today + timedelta(days=1))
        city = event.casefold().replace(" ", "-")
        code, note = fetch_cover(
            str(event_id), str(year), city, match_id,
            [_surname(name) for name in english], out, today)
        if code != 0:
            return draft, note
        draft.setdefault("cover", {})["portrait"] = {
            "image": str(out.relative_to(ROOT)),
            "_portrait_why": "WTA 官方赛后稿/集锦头图，定时自动补齐",
        }
        return draft, note
    except (Exception, SystemExit) as exc:  # noqa: BLE001
        return draft, f"官方封面尚未出现（{type(exc).__name__}: {exc}）"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--draft", type=Path)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--need-faces", nargs="*", type=Path, metavar="DRAFT",
                    help="印 true/false：这几份草稿里有没有这一班要跑照片接口那一档的（工作流据此装认人依赖）")
    ap.add_argument("--api-budget", type=float, default=None, metavar="SECONDS",
                    help="照片接口那一档这一份最多花多少秒（flashscore、翻页、读头、下原图一起算）")
    ap.add_argument("--no-api", action="store_true",
                    help="这一班不查照片接口（工作流的整班预算用完了），只走原来那两条路")
    args = ap.parse_args()
    if args.need_faces is not None:
        probed = slugs_with_probe()
        need = False
        for path in args.need_faces:
            try:
                draft = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if probed is not None and str(draft.get("slug") or "") not in probed:
                continue            # 循环里「没有已落库 probe 证据」的这一班跳过，不为它装依赖
            if needs_official_pick(draft):
                need = True
                break
        print("true" if need else "false")
        return 0
    if args.draft is None:
        ap.error("要 --draft")
    before = args.draft.read_text(encoding="utf-8")
    old = json.loads(before)
    draft, note = refresh(json.loads(before), write=args.write, api=not args.no_api,
                          budget=args.api_budget)
    changed = draft != old
    # 按**内容**比，不按字节比：原来的文件格式和 json.dumps 不一样时，字节比会把「什么都没变」也写一遍
    if args.write and changed:
        args.draft.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cover_changed = ((draft.get("cover") or {}).get("portrait") or {}) != (
        (old.get("cover") or {}).get("portrait") or {})
    if cover_changed:
        print(f"[found] {note}")
    else:
        print(f"[waiting] {note}" + ("（照片接口那一档的账更新了）" if changed and args.write else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
