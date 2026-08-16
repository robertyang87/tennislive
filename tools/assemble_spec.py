#!/usr/bin/env python3
"""备料批处理：把一场球能机器化的 spec 编辑内容一次性备齐，写成草稿。

无人值守链现在断在「probe 出缩略图墙 → 人写 spec」这一段。工具都齐了但没人
把它们串起来，于是写一条 spec 要人分别去跑：

    find_match_stats_fs --players      反查 flashscore id
    match_stat_hooks --stats-block     数据图 stats.a / stats.b
    match_stat_hooks                   狠数据候选（总分差/一发摆动/破发点/连续保发/H2H）
    find_turning_points                转折局候选
    draft_spec                         钩子/论点/beats/旁白/场外切口

本工具把这五件批处理成 `specs/reels/<slug>.draft.json`，供人终审。

⚠️ **只备料，不判稿**：窗口（segments 的 start/end/cx）仍由人从缩略图墙定——
转折局是「第几盘第几局」，映射到视频秒要另写对照，选段错位质检未必拦得住，
这一步不抢。封面（cover.portrait 官方实拍）也留人：`fetch_wta_cover_photo`
要 WTA 的 MatchID/tournament id，不在本工具输入里。

⚠️ **每一层退化都出声**（仓库里「兜底出事不吭声」栽过太多次）：反查不到 id、
stats 块缺必填项、狠数据算不出、没配 DeepSeek key——各自在 notes 里写一句，
草稿仍会写出「能备到的那部分」，缺的留给终审补。**不因为一块失败就把整份丢掉。**

用法：
    python tools/assemble_spec.py --slug eala-ruse --home "Alexandra Eala" \
        --away "Elena-Gabriela Ruse" --event "Cincinnati" --year 2026 \
        --fixture "北京时间 8 月 15 日，WTA1000 辛辛那提第二轮"

    # 已知 flashscore id 就直接给，跳过反查：
    python tools/assemble_spec.py --slug eala-ruse --flashscore-id 4CYI9Ick \
        --home "Alexandra Eala" --away "Elena-Gabriela Ruse" ...

产出 specs/reels/<slug>.draft.json，字段：
    _draft: true          —— 草稿标记；validate_spec 只认 <slug>.json，不会误读
    _match.flashscore_id  —— 反查或给定
    cover.matchup         —— player_zh 译名 + 英文名
    stats                 —— stats.a / stats.b（数据图直接粘）
    editorial             —— draft_spec 的 hook/question/thesis/beats/human_context/narration
    _hit_data             —— 狠数据候选（不是判定）
    _turning_points       —— 转折局候选（不是判定）
    _notes                —— 每个环节的成败，一个字不省
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fetch_match_stats_fs import StatsError, find_match  # noqa: E402
from match_feed import fs_feed, points  # noqa: E402
from match_stat_hooks import collect, stats_block  # noqa: E402
from find_turning_points import _label, rank_games  # noqa: E402
from tennislive.research.brief import Chat  # noqa: E402
from tennislive.zh import player_zh  # noqa: E402
from draft_spec import draft_editorial  # noqa: E402

TURNING_POINT_TOP = 5
DRAFT_SUFFIX = ".draft.json"


def _surname(full: str) -> str:
    """英文全名取最后一个词当姓。反查 flashscore 用它（find_match 按片段匹配）。"""
    words = (full or "").strip().split()
    return words[-1] if words else full


def resolve_match_id(home: str, away: str) -> str | None:
    """按两个球员姓反查 flashscore id。查不到返回 None（不抛，调用方出声）。"""
    try:
        mid, _, _ = find_match([_surname(home), _surname(away)])
        return mid or None
    except StatsError:
        return None


def matchup_order(home: str, away: str, flashscore_id: str) -> list[tuple[str, str]]:
    """matchup 顺序必须跟 flashscore 的 home/away 一致，不是跟命令行传参顺序。

    判据（CLAUDE.md「stats.a 跟 cover.matchup[0] 不是 feed 的 home/away」）：
    `stats_block` 的 a/b 按 flashscore 的 home/away（SH/SI）排，而
    `render_stat_card` 的 a 对应 `cover.matchup[0]`——所以 matchup 顺序也必须按
    flashscore 的 home/away 排。人传 `--home B --away A` 时若照抄，数据图会把
    a 的数字挂在 B 名下、b 的数字挂在 A 名下，**把赢家印成输家**，四道闸一道
    都不响。

    实现：读 `df_hh_1` 的 FH/FK（home/away 英文全名），拿它把两个输入归位。
    读不到就退回命令行顺序（出声，别静默）。
    """
    try:
        body = fs_feed("df_hh_1", flashscore_id)
        # ⚠️ 别只 split("~")[0]：FH/FK 在「Last matches」那条记录里（第一条是
        # SA÷N 的计数行），从整份 body 里找才稳。
        f = dict(re.findall(r"(F[HK])÷([^¬]*)", body))
        fs_home, fs_away = f.get("FH", ""), f.get("FK", "")
    except Exception:  # noqa: BLE001 —— 网络失败就退回命令行顺序
        fs_home = fs_away = ""
    if not fs_home or not fs_away:
        return [(home, player_zh(home)), (away, player_zh(away))]
    # 按「谁的姓出现在 flashscore 的 home 里」归位，而不是按整名相等——feed 是
    # 「Baez S.」缩写，命令行是「Sebastian Baez」，整名对不上。
    def side_is(fs_name: str, full: str) -> bool:
        return _surname(full).casefold() in fs_name.casefold()

    ordered = []
    for fs_name in (fs_home, fs_away):
        if side_is(fs_name, home):
            ordered.append((home, player_zh(home)))
        elif side_is(fs_name, away):
            ordered.append((away, player_zh(away)))
    if len(ordered) == 2:
        return ordered
    return [(home, player_zh(home)), (away, player_zh(away))]


def facts_text(hit_data: list[dict]) -> str:
    """把狠数据候选拼成一段喂给 draft_spec 的 facts。"""
    if not hit_data:
        return ""
    return "\n".join(f"- {c.get('label', '')}: {c.get('detail', '')}" for c in hit_data)


def assemble(*, slug: str, home: str, away: str, event: str, year: int,
             fixture: str, flashscore_id: str | None,
             captions_path: str | None = None,
             cuts_path: str | None = None) -> dict:
    notes: list[str] = []
    draft: dict = {
        "_draft": True,
        "slug": slug,
        "_column": "reel",
        "cover": {
            "matchup": [
                {"name": player_zh(home), "name_en": home},
                {"name": player_zh(away), "name_en": away},
            ],
        },
    }

    # ① flashscore id：给了就用，没给就反查。
    mid = flashscore_id or resolve_match_id(home, away)
    if mid:
        draft["_match"] = {"flashscore_id": mid}
        notes.append(f"flashscore id：{mid}"
                     + ("（给定）" if flashscore_id else "（按球员姓反查）"))
        # ⚠️ 拿到 id 就立刻重排 matchup——stats.a 跟的是 flashscore 的 home，
        # 而 render_stat_card 的 a 跟 cover.matchup[0]，顺序不一致数据图会
        # 把赢家印成输家（CLAUDE.md 记过的坑）。
        ordered = matchup_order(home, away, mid)
        if [x[1] for x in ordered] != [player_zh(home), player_zh(away)]:
            notes.append("matchup 按 flashscore home/away 重排："
                         + " vs ".join(x[1] for x in ordered))
        draft["cover"]["matchup"] = [
            {"name": zh, "name_en": en} for en, zh in ordered]
    else:
        notes.append("⚠️ 没反查到 flashscore id——stats 块 / 狠数据 / 转折局"
                     "都依赖它，这三块本轮跳过。用 tools/match_feed.py find 拿到 id "
                     "后补进 _match.flashscore_id 重跑。")

    if mid:
        # ② stats 块（数据图）。
        try:
            blk = stats_block(mid)
        except Exception as exc:  # noqa: BLE001 —— 网络/格式都别拖垮整份草稿
            notes.append(f"⚠️ stats 块没成（{type(exc).__name__}: {exc}）")
            blk = None
        if blk is not None:
            draft["stats"] = {"a": blk["a"], "b": blk["b"]}
            if blk["_missing_required"]:
                notes.append("⚠️ stats 块必填项没解出来："
                             + "、".join(blk["_missing_required"]))
            notes.append("制胜分/非受迫失误：" + (
                "这场有，已填进 stats" if blk["_has_winners_ue"]
                else "接口里没有——照 render_stat_card 的 OPTIONAL_FIELDS 留空"))

        # ③ 狠数据候选。
        try:
            hit = collect(mid, player_zh(home), player_zh(away))
            draft["_hit_data"] = hit["candidates"]
            draft["_durations"] = hit["durations"]
            notes.append(f"狠数据候选 {len(hit['candidates'])} 条"
                         + ("" if hit["candidates"] else "（分盘统计字段可能没铺全）"))
        except Exception as exc:  # noqa: BLE001
            notes.append(f"⚠️ 狠数据没成（{type(exc).__name__}: {exc}）")

        # ④ 转折局候选。
        try:
            ranked = rank_games(points(mid))
            draft["_turning_points"] = [
                {"label": _label(g, player_zh(home), player_zh(away)),
                 "density": g["density"], "tags": g["tags"]}
                for g in ranked[:TURNING_POINT_TOP]
            ]
            notes.append(f"转折局候选 {len(ranked)} 局，取前 {TURNING_POINT_TOP}")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"⚠️ 转折局没成（{type(exc).__name__}: {exc}）")

    # ⑤ 文案（DeepSeek）。facts 用上面算出的狠数据候选喂。
    chat = Chat()
    if not chat.ready:
        notes.append("⚠️ 没配 DEEPSEEK_API_KEY / ANTHROPIC_API_KEY，文案跳过——"
                     "钩子/论点/beats/旁白留给终审手写。")
    else:
        notes.append(f"文案通道 {chat.channel}")
        draft["editorial"] = draft_editorial(
            chat, home=home, away=away, event=event, year=year,
            fixture=fixture, facts=facts_text(draft.get("_hit_data", [])))
        if draft["editorial"] is None:
            draft.pop("editorial", None)
            notes.append("⚠️ 文案这一步没成（模型或网络），editorial 留空")

    # ⑥ 窗口起草（DeepSeek 读字幕+切点）。只在给了 captions + cuts（probe 产物）
    #    时才跑——probe 之前这两个文件不存在，跳过并在 notes 出声。
    if captions_path and cuts_path:
        try:
            from draft_segments import _read_captions, _read_cuts, draft_segments
            caps = _read_captions(Path(captions_path))
            cuts = _read_cuts(Path(cuts_path))
            if not caps:
                notes.append("⚠️ captions 是空的，窗口起草跳过（退回人工）")
            elif not chat.ready:
                notes.append("⚠️ 没配 key，窗口起草跳过")
            else:
                beats = "\n".join(
                    (draft.get("editorial") or {}).get("beats", []))
                seg = draft_segments(chat, captions_text=caps, cuts=cuts,
                                     beats=beats, home=player_zh(home),
                                     away=player_zh(away))
                if seg and seg.get("segments"):
                    draft["segments"] = seg["segments"]
                    notes.append(f"窗口起草 {len(seg['segments'])} 段"
                                 + (f"，拦掉 {seg.get('_dropped', 0)} 段废窗口"
                                    if seg.get("_dropped") else ""))
                else:
                    notes.append("⚠️ 窗口起草没成（模型或全被闸拦掉），segments 留空")
        except Exception as exc:  # noqa: BLE001 —— 窗口起草失败不拖垮整份草稿
            notes.append(f"⚠️ 窗口起草没成（{type(exc).__name__}: {exc}）")
    else:
        notes.append("⚠️ 没给 captions/cuts（probe 还没落库），窗口起草跳过——"
                     "等 probe 完成后再补跑")

    draft["_notes"] = notes
    return draft


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--home", required=True, help="英文全名，如 Alexandra Eala")
    ap.add_argument("--away", required=True, help="英文全名，如 Elena-Gabriela Ruse")
    ap.add_argument("--event", default="")
    ap.add_argument("--year", type=int, default=0)
    ap.add_argument("--fixture", default="", help="赛前信息，进文案 prompt")
    ap.add_argument("--flashscore-id", default=None,
                    help="已知 flashscore id 就跳过反查")
    ap.add_argument("--captions", default=None,
                    help="probe 产出的 captions.txt（给了就跑窗口起草）")
    ap.add_argument("--cuts", default=None,
                    help="probe.json（读 scene_cuts，配 --captions 用）")
    ap.add_argument("--write", action="store_true",
                    help="把草稿落盘到 specs/reels/<slug>.draft.json；不给就只打印")
    args = ap.parse_args()

    draft = assemble(slug=args.slug, home=args.home, away=args.away,
                     event=args.event, year=args.year, fixture=args.fixture,
                     flashscore_id=args.flashscore_id,
                     captions_path=args.captions, cuts_path=args.cuts)

    print(json.dumps(draft, ensure_ascii=False, indent=2))
    if not args.write:
        print("\n（干跑，没落盘。要写进仓库加 --write。）")
        return 0

    outdir = Path(__file__).resolve().parent.parent / "specs" / "reels"
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{args.slug}{DRAFT_SUFFIX}"
    out.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n草稿 → {out}")
    print("\n窗口（segments）和封面（cover.portrait 官方实拍）留给终审补，"
          "见草稿 _notes 里每个环节的成败。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
