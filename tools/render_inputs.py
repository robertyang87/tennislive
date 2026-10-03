#!/usr/bin/env python3
"""渲染输入清单：这一版成片**到底吃了 spec 里的哪些东西**。

**来路**（账号所有者 2026-09-27 在「O1 质检指纹管到哪儿」三选一里选了
「重核对，不重渲」）：质检凭证 `qc_attestation.json` 钉的是 spec 文件的**字节**
（`auto_push_gate.validate_qc`、`check_reel_landed.write_attestation`），于是渲完
之后改一句 `_why`、补一行 `push.auto`，哈希链就断，唯一的出路是再渲一趟
（7~10 分钟）——而那一趟一个像素都不会变。量出来的账（全是渲完之后的改动，
重渲出来的成片和上一版内容相同）：

    eala-jovic     85b94e74   _why / _no_repeat 里两处段号交叉引用
    mensik-tien    d338e77d   stats._winners_ue_why
    medvedev-damm  e15e73e5   push._no_auto_why → push.auto
    gauff-jovic    80bbdd1a   两段的 _score_inset_why（推送之后，链从此断着）
    （zheng-liutova 93df2572 是采访线，同一个形状，这里不管）

⚠️ **wong-paul d5bbc48c 也是「重渲了、一个像素没变」，但重核对省不掉它**：那个加错的
分钟数改在 `editorial.human_context.facts`——`editorial` 是**真字段**，只进闸
（`_validate_editorial_contract` / `ending_payoff_problem`），却在投影里。拿真提交
重放 `spec_problems`，报「渲染参数：editorial.human_context.facts[3]」，照旧走 render
（判据 `test_editorial是真字段_改里面的数照旧重渲`）。要放它，得另开一类「只进闸的
真字段」、让归类扫描像管 `push` 那样管住谁读它——没做，宁可多渲一趟。

**「发出去的必须和质检过的是同一份」这条不许松**（tennis-pipeline-ops「哈希链」
那几节）。所以不是把注解从凭证的哈希里摘掉（那是 O1 的 b 方案，账号所有者
没选），而是**渲染那一刻把「会进成片的那部分 spec」连同它引用的素材字节一起
记下来**（本文件写的 `render_inputs.json`），之后 spec 再变，拿新 spec 按同一
个口径重算一遍逐字节比：

    一处没动  → `match-reel mode=reattest`：成片还是那一份，重新出一张绑定
                新 spec 字节的凭证（`tools/reattest_check.py --apply`）
    动了一处  → 老老实实 `mode=render`

**「会进成片的那部分」怎么定**——不是靠记：

- `_` 开头的键是注解（`build_match_reel._reject_underscored_fields` 那条约定），
  **除了** `RENDER_ANNOTATIONS` 里那几个——渲染路径上真有代码拿它们决定成片
  长什么样（字幕下锚、比分板挑哪一套）；以及 `sources` 表里的键——那张表的键全是
  数据（`spec_sources` 一个都不跳），整张原样进投影
- `push` 块只进推送不进成片，整块不算；渲染路径上**只许**在
  `PUBLISH_FIELDS["push"]` 列的那几个函数里读它
- 判据 `tests/test_reattest.py::test_渲染路径读到的注解键都要归类`：从
  `build_match_reel.py` / `check_reel_landed.py` 顺着 import 走一遍，把每一处
  `x["_k"]` / `x.get("_k")` / `"_k" in x` 都抠出来，**没归类的一个都不放**。
  以后谁在渲染路径上新读一个 `_` 键，那条测试当场红，逼着人回答一句：
  「它进不进成片？」——这一问正是 O1 的 b 方案被否掉的原因（「要证明渲染器
  从不读被排除的键」），现在它是机械的
- 被读、但只进闸（raise / print）的注解归 `GATE_ANNOTATIONS`。它们的**值**不进
  指纹（dry-run 在 reattest 那一趟照样重跑那些闸），但**闸读它的那个位置上、按
  那道闸自己的口径算数的认领，之后必须仍然算数**——`build_cover` 的
  `_layout_why` / `_approved_by_user` 这类闸只在编码里跑、dry-run 够不着，删掉
  （或改成 `false` / 一串空格）就等于绕过了它。**位置**和**口径**都照闸的读法写
  （`Gate.where` / `Gate.rule`）：`segments[i]._why`、`cover.portrait._why` 这类
  同名的纯说明没有闸读，删了不算绕过；`_approved_by_user: false`、
  `_layout_why: "   "` 闸不认，也不算「还在」

**键的顺序也是渲染输入**（v2，2026-09-27 评审拦下的）：渲染器按插入顺序取「第一个」
——`sources` 的第一条就是主源片（`build_match_reel` 里 `next(iter(sources))`，
没写 `source` 的段都从它取画面）。所以投影按原顺序存、按原顺序比
（`canonical` 不排序，`diff_paths` 另报「键的顺序」），两个 spec 只差键的顺序
**不算**同一份渲染输入。宁可多判一次重渲，不去一处处证明哪张表的顺序无关紧要。

⚠️ 这个模块**只用标准库**：`auto_push_gate`（稀疏检出、只装主依赖）也要 import
它去复核重核对凭证。
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, NamedTuple

MANIFEST_NAME = "render_inputs.json"
#: v2（2026-09-27）：投影按原顺序比（见模块 docstring「键的顺序」），认领按闸的
#: 位置和口径记。v1 的清单按新口径判不了 → `reattest_check` 报「判不了」、照旧重渲。
#: ⚠️ 光靠这个数不够：下面那几张表一改（`RENDER_ANNOTATIONS` 加一个键），投影的口径
#: 就变了，而没人会记得升它——所以清单另记一份 `rules_digest()`，口径是
#: `VERSION` ＋ 那个指纹两样一起认（`same_rules`），表一变自动算「旧口径」。
VERSION = 2

#: 渲染路径上**会进成片**的 `_` 键。它们的值留在指纹里，改了就要重渲。
RENDER_ANNOTATIONS: dict[str, str] = {
    "_column": "render() 的字幕下锚按栏目走：cover.eyebrow 缺省时退到 `_column`"
               "（subtitle_bottom_for_boards 只在「赛场之上」下移）",
    "_production": "scoreboard_profile 读 `_production.event` 挑转播比分板那一套"
                   "（ATP / WTA / 金杯 / 拉沃尔杯）——直接决定贴哪块板",
}

# ── 认领「还算不算数」：照每道闸自己的读法 ────────────────────────────────────
# 闸的写法不止一种，「在不在」不是一个口径：`not cover.get(k)` 不认 `False`；
# `str(x.get(k) or "").strip()` 不认 `None` 和一串空格；`str(x.get(k, "")).strip()`
# 却认 `None`（写出来是 "None"）。认领的口径必须和闸一字不差，否则要么把闸会拒的
# spec 放过去（`_approved_by_user: false`），要么把闸会认的拦下来。


def truthy(value: Any) -> bool:
    """`not x.get(k)` / `bool(x.get(k))`：`False`、`0`、`""`、`{}` 都不算。"""
    return bool(value)


def text(value: Any) -> bool:
    """`str(x.get(k) or "").strip()`：`None` 和只有空白都不算。"""
    return bool(str(value or "").strip())


def text_str(value: Any) -> bool:
    """`str(x.get(k, "")).strip()`：键在就按 `str()` 算，`None` 写出来是 "None"。"""
    return bool(str(value).strip())


def nonblank_str(value: Any) -> bool:
    """`isinstance(why, str) and why.strip()`：非字符串一律不算。"""
    return isinstance(value, str) and bool(value.strip())


def https_url(value: Any) -> bool:
    """`str(x.get(k, "")).startswith("https://")`。"""
    return str(value).startswith("https://")


def declared_bool(value: Any) -> bool:
    """`k in x` ＋ `isinstance(x[k], bool)`：`false` 也是一句表态。"""
    return isinstance(value, bool)


def utc_time(value: Any) -> bool:
    """`reel_facts._utc(x.get(k)) is not None`：带时区的 ISO 时刻（`2026-09-18T06:50Z`）。

    没写时区、写成一句话、空串都不算——闸比不了先后的，认领也不算数。
    """
    raw = str(value or "").strip()
    if not raw:
        return False
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    return when.tzinfo is not None


def any_text_value(value: Any) -> bool:
    """`{源键: 为什么}` 这种认领表（`probe_sources.coverage_findings` 读 `_no_probe_why`）：
    至少一条理由非空才算——一张全是空白的表闸一条都不认。理由按 `probe_sources.claim_why`
    的口径取：老写法是一句话，多源的新写法是对象的 `why`（带宽高帧率，2026-09-28）。"""
    def _why(v: Any) -> str:
        return str((v.get("why") if isinstance(v, dict) else v) or "").strip()
    return isinstance(value, dict) and any(_why(v) for v in value.values())


#: `taste_gates_extra.QUOTE_KINDS` 的一份抄本（这个模块只许用标准库，import 不了它）。
#: 两边一致由 `tests/test_reattest.py::test_quote_kind的口径和闸是同一份` 钉住。
QUOTE_KINDS = frozenset({"broadcast", "ceremony"})


def quote_kind(value: Any) -> bool:
    """`seg.get("_quote_kind") not in QUOTE_KINDS`：只认那两个值，别的一律不算认领。"""
    return isinstance(value, str) and value in QUOTE_KINDS


class Gate(NamedTuple):
    """一个只进闸的注解：哪道闸、在 spec 的哪儿读、按什么口径算数。

    `where` 为空＝**不是认领**：只在备料（`promote_reel_draft`）时读、render 和
    dry-run 都不调；或者它的出现是「拒绝」而不是「放行」（`_import`）。删了不绕过
    任何闸，不记。
    ⚠️ **归类测试分不出 dry-run 闸和只在编码里跑的闸**：给一道 render 里才查的认领
    写空 `where`，测试照样绿，而重核对从此允许删掉它、那道闸不再跑（reattest 只跑
    dry-run）。只在编码里查的（`build_cover`、`reel_face_gate._claim` 这类）**必须**写 `where`。

    `where` 的写法：点分路径，`[]` 是列表里每一项、`[0]` 是第 0 项——
    `segments[].voice._why` 就是「每一段的 voice 对象里那个 `_why`」。
    `read_by` 是渲染/质检路径上**读它的函数**，测试按 import 图对账：谁新读了它，
    那条测试红，逼着回头看一眼 `where` 还对不对。
    """

    why: str
    read_by: frozenset[str]
    where: tuple[str, ...] = ()
    rule: Callable[[Any], bool] = text


def _gate(why: str, read_by: str, where: str | tuple[str, ...] = (),
          rule: Callable[[Any], bool] = text) -> Gate:
    return Gate(why, frozenset(read_by.split()),
                (where,) if isinstance(where, str) else where, rule)


#: 渲染/质检路径上被读、但**只进闸不进成片**的 `_` 键（raise 或 print）。
#: 值不进指纹；闸读它的那个位置上算数的，重核对时必须仍然算数（见模块 docstring）。
GATE_ANNOTATIONS: dict[str, Gate] = {
    "_approved_by_user": _gate("build_cover：approved_image 要有用户认领，缺了拒渲（编码里才查）",
                               "build_cover", "cover._approved_by_user", truthy),
    "_beat": _gate("promote_reel_draft.insert_chapter_cards（备料提升时读，render 不调）",
                   "insert_chapter_cards"),
    "_chapter_cards_why": _gate("promote_reel_draft.insert_chapter_cards 写它（同上）",
                                "insert_chapter_cards"),
    "_board_on_screen_why": _gate(
        "probe_board.board_findings：写着不贴、板却连着在画面里的认领（dry-run 读 probe）",
        "board_findings", "segments[]._board_on_screen_why"),
    "_claims": _gate("_absolute_claims_need_a_source：全称断言要两个不同主机的出处"
                     "（`absolute_claims.interview_problem` 是采访线的同一道闸，按模块走 "
                     "import 图被拉进来，竖版短片不调）",
                     "_absolute_claims_need_a_source interview_problem", "_claims", truthy),
    "_cover_reuse_why": _gate(
        "reel_asset_gates.cover_reuse_finding：封面照片和已发的另一条同一张的认领"
        "（也读别的 spec 的这一句，那不是本条的认领）",
        "cover_reuse_finding", "_cover_reuse_why"),
    "_dated_why": _gate("reel_facts.dated_words_problem：「网球有故事」钉在发布那一天的认领"
                        "（validate_spec，dry-run 就查）", "dated_words_problem", "_dated_why"),
    "_band_skip_why": _gate("taste_gates.story_band_problem：这一段不补信息条的认领"
                            "（validate_spec → _owner_taste，dry-run 就查）",
                            "story_band_problem", "segments[]._band_skip_why"),
    "_decider_why": _gate("reel_facts.decider_set_problem：大满贯提「决胜盘」的认领",
                          "decider_set_problem", "_decider_why"),
    "_digital_silence_why": _gate(
        "probe_audio.digital_silence_findings：按实测会漏出数字静音的认领——无旁白段，和旁白"
        "说完之后的那一截（上包络／真语音那几档，2026-09-28 起手写 spec 硬）。dry-run 读 probe"
        "（只在 mode=render 那一趟硬）；--check-narration 和 render 在 TTS 之后按真语音再判一遍；"
        "probe 没拉回来时这一层是哑的，所以记位置",
        "digital_silence_findings", "segments[]._digital_silence_why"),
    "_draft": _gate("promote_reel_draft.promote：转正时按键名比出草稿块、剥掉它（备料，render "
                    "和 dry-run 都不调）", "promote"),
    "_durations": _gate("promote_reel_draft._duration（备料时读）", "_duration"),
    "_feed_retry": _gate("promote_reel_draft.promote：转正时和 `_draft` 一起剥掉——草稿专用的"
                         "flashscore 重跑账（assemble_spec.record_feed_retry），render 和 dry-run "
                         "都不调", "promote"),
    "_cover_api": _gate("promote_reel_draft.promote：转正时和 `_draft` 一起剥掉——草稿专用的"
                        "照片接口那一档的账（refresh_reel_cover：问过的开赛时刻、下过没过的原图、"
                        "被视觉审核判掉的图、卡住的状态查没查完），render 和 dry-run 都不调", "promote"),
    "_editing_why": _gate(
        "taste_gates_extra.uses_tennistv：`_source`／`_editing_why` 里写着 Tennis TV 就要求"
        "认领 `_tennistv_trim`（dry-run）——它是**触发**不是认领，写了只会多一道闸；"
        "interview_taste_extra 是采访线同名入口，竖版短片不调",
        "uses_tennistv interview_taste_extra"),
    "_ending_order_why": _gate("taste_gates.ending_order_problem：正文没收在最晚镜头的认领"
                               "（dry-run）", "ending_order_problem",
                               "segments[]._ending_order_why"),
    "_ending_payoff_required": _gate(
        "ending_payoff_problem：冷开场要不要在正文兑现结局（true / false 都是表态）",
        "ending_payoff_problem waiting_reasons",
        "segments[0]._ending_payoff_required", declared_bool),
    "_evidence_on_screen_why": _gate("promote_reel_draft.note_evidence_on_screen（备料时读写）",
                                     "note_evidence_on_screen"),
    "_head_open_why": _gate("cold_open_problem：集锦开头恰好就是最后一球的认领",
                            "cold_open_problem", "segments[0]._head_open_why"),
    "_heard": _gate("_seg_voice：用了情绪风格要写谁听过",
                    "_seg_voice", "segments[].voice._heard"),
    "_heat_why": _gate("_players_are_worth_a_reel：热度闸的认领",
                       "_players_are_worth_a_reel", "cover._heat_why", text_str),
    "_face_check_why": _gate(
        "reel_face_gate._claim：抽帧封面认人／睁眼的认领（render 里源片到手才查，"
        "dry-run 够不着——删掉就等于绕过）", "_claim", "cover.portrait._face_check_why"),
    "_hit_data": _gate("promote_reel_draft.promote（备料提升时读）", "promote"),
    "_hook_identity_why": _gate("taste_gates_extra.hook_identity_note：钩子写身份的认领"
                                "（dry-run 只报不拦）", "hook_identity_note",
                                "cover._hook_identity_why"),
    "_hook_shape_why": _gate("taste_gates.hook_result_problem：钩子第二行不交代结果的认领"
                             "（dry-run）", "hook_result_problem", "cover._hook_shape_why"),
    "_one_of_n_why": _gate("taste_gates_extra.one_of_n：盘点跨盘的「N 个里只兑现一个」这类说法的认领"
                           "（dry-run，也随小红书正文一起查）", "_one_of_n_claimed xhs_taste_extra",
                           "_one_of_n_why"),
    "_verified_clean": _gate("taste_gates.interview_is_auto：采访 spec 人工核过的标记——有它口味闸按手写判硬，"
                             "删了就退成只报，所以要登记", "interview_is_auto", "_verified_clean", truthy),
    "_hook_term_why": _gate("taste_gates.hook_jargon_problem：钩子里用术语的认领（dry-run）",
                            "hook_jargon_problem", "cover._hook_term_why"),
    "_import": _gate("main：导入成片拒绝重渲（只在非 dry-run 时 raise）；"
                     "probe_sources.is_imported_master：导入成片不查源片 probe 覆盖（dry-run）。"
                     "带它的 spec 渲不出来（main 拒渲），所以不会出现在任何一份清单的认领里；"
                     "渲完之后再加它，只是让 dry-run 的覆盖那一层跳过——成片是渲染那一刻"
                     "过了那一层之后出的，投影没变就还是那一份", "main is_imported_master"),
    "_layout_why": _gate("build_cover：赛场之上退回 VS 版式要认领（编码里才查）",
                         "build_cover", "cover._layout_why", text_str),
    "_license": _gate("music_problem：背景音乐要写授权",
                      "music_problem", "music._license"),
    "_low_res_why": _gate("cover_photo_problem：封面低于门槛的认领",
                          "cover_photo_problem", "cover.portrait._low_res_why"),
    "_match": _gate("reel_facts 的赛果/抢十闸拿它对账、reel_asset_gates._retired 判退赛"
                    "（封面用时闸）、promote_reel_draft 的撞车键（合集源片按场次 id 分开，`_compilation_only`）、list_official_uploads "
                    "认人和开球日（dry-run 只报不拦的官方上传／封面日期报告）",
                    "verified_result_problem decider_tiebreak_problem waiting_reasons "
                    "promote _source_urls _match_keys _flashscore_id _official_wta_id _match_date _retired event_dates spec_surnames _omission_problem _verified_retirement_problem",
                    "_match", truthy),
    "_narration_why": _gate("cover_voice_matches_hook_problem：封面口播和钩子不同的认领",
                            "cover_voice_matches_hook_problem", "cover._narration_why"),
    "_old_photo_why": _gate(
        "list_official_uploads.stale_cover_problem：封面照片比源片旧、故意用当年的图的认领"
        "（dry-run 只报不拦）", "stale_cover_problem", "cover.portrait._old_photo_why"),
    "_no_probe_why": _gate(
        "probe_sources.coverage_findings：`{源键: 为什么}`，某条源认领不到 probe.json 的认领"
        "（probe_dry_run；新的手写 spec 硬；多源的认领是对象、带宽高帧率，几何预演拿它照跑）",
        "_claims", "_no_probe_why", any_text_value),
    "_numeral_display_why": _gate(
        "reel_asset_gates.numeral_display_problems：字幕数字换算半中半洋的认领",
        "numeral_display_problems", "_numeral_display_why"),
    "_no_cold_open_why": _gate("cold_open_problem：源片里没有赢球后画面的认领",
                               "cold_open_problem", "_no_cold_open_why"),
    "_photo_caption_safety": _gate("parse_segments：全屏照片字幕不遮主体的目视依据",
                                   "_one", "segments[]._photo_caption_safety", truthy),
    "_photo_source": _gate("parse_segments：全屏照片的来源（要 https）",
                           "_one", "segments[]._photo_source", https_url),
    "_quote_kind": _gate("taste_gates_extra.quote_kind_offenders：赛场之上的原声段只认"
                         "broadcast／ceremony（dry-run）", "quote_kind_offenders",
                         "segments[]._quote_kind", quote_kind),
    "_quote_skip_why": _gate("unvoiced_quote_problem：不配原声字幕的认领",
                             "unvoiced_quote_problem", "segments[]._quote_skip_why"),
    "_rechecked_at": _gate(
        "reel_facts.waiting_fact_problem / waiting_fact_stale_problem：注解里写了「要等」，"
        "回头查过的时刻（validate_spec，dry-run 就查；stale 那一半读账本）",
        "waiting_fact_problem waiting_fact_stale_problem", "_rechecked_at", utc_time),
    "_set_coverage_why": _gate("taste_gates.set_coverage_report：有一盘旁白没交代的认领"
                               "（dry-run 只报不拦）", "set_coverage_report",
                               "_set_coverage_why"),
    "_revision_request": _gate("duplicate_match_problem：同一场球重做的认领",
                               "duplicate_match_problem", "_revision_request", truthy),
    "_score_inset_why": _gate(
        "parse_segments / _seg_score_windows：比分板不回贴的认领（顶层那句是 promote "
        "写的说明，没有闸读）", "parse_segments _seg_score_windows promote",
        "segments[]._score_inset_why", text_str),
    "_short_match_why": _gate(
        "reel_asset_gates.duration_problem：封面用时短于门槛（又不是退赛）的认领",
        "duration_problem", "_short_match_why"),
    "_social_checked": _gate("taste_gates_extra.social_first_note：声明类「网球有故事」查过"
                             "X／Instagram 的认领（dry-run 只报不拦）", "social_first_note",
                             "_social_checked"),
    "_social_search": _gate(
        "reel_facts.social_search_problem：当事人声明类「网球有故事」X / Instagram 各查了什么"
        "（validate_spec，dry-run 就查；「两个平台都点到名」那一层闸自己在 dry-run 里判）",
        "social_search_problem", "_social_search", truthy),
    "_social_search_why": _gate("reel_facts.social_search_problem：标题层命中、其实不是声明类的认领",
                                "social_search_problem", "_social_search_why"),
    "_source": _gate(
        "taste_gates_extra.uses_tennistv：和 `_editing_why` 一起，写着 Tennis TV 就要求认领 "
        "`_tennistv_trim`（dry-run）——**触发**不是认领；源片本身在 `sources` / `source_url`"
        "（真字段，进投影）", "uses_tennistv interview_taste_extra"),
    "_summary_count_why": _gate(
        "taste_gates.copy_count_problem：钩子和推送标题数字对不上的认领（dry-run）。住在 "
        "`push` 块里——推送块整块不进投影、也不记认领位置（它每次都按当前 spec 现读）",
        "copy_count_problem"),
    "_tactics_why": _gate("reel_craft.shot_craft_problem：源片看不出球路的认领",
                          "shot_craft_problem", "_tactics_why"),
    "_tennistv_trim": _gate("taste_gates_extra.tennistv_trim_problem：用了 Tennis TV 源片要"
                            "写清片尾和台标怎么剪（dry-run）", "tennistv_trim_problem",
                            "_tennistv_trim"),
    "_title_term_why": _gate("taste_gates.interview_title_jargon_problem：**采访线**标题用"
                             "术语的认领——同模块被 import 图拉进来，竖版短片不调、"
                             "竖版短片的 spec 也不写它", "interview_title_jargon_problem"),
    "_topbar_format_why": _gate("_topbar_lines → tour_topline_problem：顶栏赛事行格式特例的认领",
                                "_topbar_lines", "_topbar_format_why"),
    "_topic_format_why": _gate("reel_facts.cover_topic_problem：封面副标题格式特例的认领",
                               "cover_topic_problem", "_topic_format_why"),
    "_tts_backend_why": _gate("apply_tts_backend：退回 edge-tts 的认领（后端本身是真字段 "
                              "tts_backend）", "apply_tts_backend", "_tts_backend_why",
                              nonblank_str),
    "_visual_evidence": _gate("promote_reel_draft（备料提升时读）", "waiting_reasons promote"),
    "_winners_ue_omission": _gate("winners_ue_gate：仅限已批准五期精确比赛的两行省略决定，身份/日期/比分和双方字段由原闸逐项核验",
                                "problem _omission_problem", "stats._winners_ue_omission", truthy),
    "_winners_ue_evidence": _gate("新统计卡/预检/成片QC核验完整制胜分与UE的来源、日期和列序", "problem _omission_problem", "stats._winners_ue_evidence", any_text_value),
    "_winners_ue_check": _gate("缺统计时记录真实查找状态；不构成缺项发布许可", "problem", "stats._winners_ue_check", any_text_value),
    "_winners_ue_why": _gate("taste_gates_extra.winners_ue_missing：数据图缺制胜分/UE 的认领"
                             "（dry-run）", "winners_ue_missing", "stats._winners_ue_why",
                             truthy),
    "_x_cdn_why": _gate("build_match_reel.x_cdn_source_problem：主地址只剩 X 的 CDN 直链"
                        "（帖子已删）的认领（validate_spec，dry-run 就查）",
                        "x_cdn_source_problem", "_x_cdn_why"),
    "_why": _gate("_seg_voice：改了语速/音高要写为什么。**只有 `voice._why` 有闸读**——"
                  "`segments[i]._why`、`cover.portrait._why`、`stats._why` 都是纯说明",
                  "_seg_voice", "segments[].voice._why"),
}

#: 只进推送、不进成片的真字段。整块不算渲染输入——而渲染/质检路径上**只许**在
#: 这几个函数里读它（都是措辞闸、推送元数据或备料），判据同上那条测试。
PUBLISH_FIELDS: dict[str, frozenset[str]] = {
    "push": frozenset({
        "spec_outward_text",                       # build_match_reel：全称断言闸扫的外发文字
        "push_is_auto", "push_meta",               # push_reel：推送开关与标题
        "voiced_texts", "outward_deep", "outward_flat",
        "interview_outward_texts", "title_echo_problem",   # spec_wording：措辞闸
        "waiting_reasons", "xhs_copy",             # promote_reel_draft：备料
        "statement_topic",                         # reel_facts：声明类选题认标题层（闸）
        "_obj", "shape_problem",                   # taste_gates：口味闸读推送标题（闸）
        "total_margin_problem", "summary_strip_offender", "push_summary_problem",
        "spec_taste_extra",                        # taste_gates_extra：口味闸（闸）
        "interview_taste_extra",                   # 同上，采访线入口（竖版短片不调）
    }),
}

#: 渲染写进 outdir、而且跟着提交进仓库的**由 spec 算出来的产物**。重核对要求它们
#: 和渲染那一刻逐字节相同——`poster.jpg` 是推送第一屏，`subtitles.ass` 是烧进
#: 成片的那一份（凭证本来就钉着它），换过就说明这已经不是那一次渲染的产物了。
#: 名字和 build_match_reel.POSTER_NAME / STAT_CARD_NAME 对账，判据在测试里。
ARTIFACTS = ("audio_review_binding.json", "subtitles.ass", "topbar.ass", "poster.jpg", "stat_card.jpg",
             "scoreboard_qc.json")

#: spec 里长这样的字符串当成「引用了一个本地文件」：封面照片、整屏证据图、
#: 背景音乐、抠图……它们的**字节**同样是渲染输入——同一个路径换一张图，
#: spec 一个字都不变，成片却变了（O4「自动换图」正是这个形状）。
ASSET_SUFFIXES = frozenset({
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg",
    ".mp3", ".m4a", ".wav", ".aac", ".mp4", ".mov", ".mkv", ".webm",
    ".json", ".ttf", ".otf", ".html", ".ass", ".txt",
})


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(obj: Any) -> str:
    """逐字节比较用的规范写法：**键保持原顺序**、无空白、中文原样。

    ⚠️ **不许 `sort_keys`**：渲染器按插入顺序取第一个（`sources` 的第一条是主源片，
    `build_match_reel` 里 `next(iter(sources))`），排了序，只调换两个源的 spec 就和
    原来那份写出同一串字节——重核对会把旧成片认成新 spec 的产物（2026-09-27 评审拦下的）。
    ⚠️ `1` 和 `1.0` 在这里**不相等**（写出来是两串字节）——渲染里有把数直接拼进
    滤镜图字符串的地方，宁可多判一次「要重渲」，不赌它们等价。
    """
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def is_annotation(key: object) -> bool:
    return isinstance(key, str) and key.startswith("_") and key not in RENDER_ANNOTATIONS


def project(spec: dict) -> dict:
    """spec 里**会进成片**的那部分：去掉注解键（任意深度）和只进推送的真字段。"""
    def walk(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items() if not is_annotation(k)}
        if isinstance(value, list):
            return [walk(v) for v in value]
        return value

    out = walk(spec)
    for field in PUBLISH_FIELDS:
        out.pop(field, None)
    # `sources` 是「键 → 源片」的表，**每个键都是数据**：`build_match_reel.spec_sources`
    # 不按下划线跳过，`{"_why": "…", "r1": …}` 里的 `_why` 就是第一条、就是主源片。
    # 这里不当注解剥（评审 2026-09-27：剥了之后插一句 `_why` 投影不变，主源片却换了人）。
    if isinstance(spec.get("sources"), dict) and "sources" in out:
        out["sources"] = json.loads(json.dumps(spec["sources"], ensure_ascii=False))
    return out


def _expand(node: Any, parts: list[str], path: list[str | int]) -> list[list[str | int]]:
    """把 `Gate.where` 的一条写法展开成 spec 里**真有这个键**的具体路径。"""
    if not parts:
        return [path]
    head, rest = parts[0], parts[1:]
    name, _, index = head.partition("[")
    if not isinstance(node, dict) or name not in node:
        return []
    node, path = node[name], path + [name]
    if not index:
        return _expand(node, rest, path)
    if not isinstance(node, list):
        return []
    index = index.rstrip("]")
    picks = range(len(node)) if index == "" else [int(index)]
    return [hit for i in picks if 0 <= i < len(node)
            for hit in _expand(node[i], rest, path + [i])]


def claim_paths(spec: dict) -> list[list[str | int]]:
    """渲染那一刻**闸认的**认领在哪儿：只看闸真读的位置，按那道闸自己的口径算数。

    推送块不在任何 `where` 里（它不进渲染路径）；同名的纯说明（`segments[i]._why`、
    `cover.portrait._why`）也不在——它们删了不绕过任何闸。
    """
    found: list[list[str | int]] = []
    for key, gate in GATE_ANNOTATIONS.items():
        for pattern in gate.where:
            for path in _expand(spec, pattern.split("."), []):
                if path[-1] == key and gate.rule(value_at(spec, path)[1]):
                    found.append(path)
    return found


def claim_holds(spec: Any, path: list[str | int]) -> bool:
    """渲染时记下的这条认领，在新 spec 里按同一道闸的口径还算不算数。

    表里已经没有这个键（闸撤了）就不再要求；位置没了、值闸不认了都算「没了」。
    """
    gate = GATE_ANNOTATIONS.get(str(path[-1])) if path else None
    if gate is None:
        return True
    found, value = value_at(spec, path)
    return found and gate.rule(value)


def value_at(spec: Any, path: list[str | int]) -> tuple[bool, Any]:
    node = spec
    for part in path:
        if isinstance(part, int):
            if not isinstance(node, list) or not 0 <= part < len(node):
                return False, None
        elif not isinstance(node, dict) or part not in node:
            return False, None
        node = node[part]
    return True, node


def path_str(path: list[str | int]) -> str:
    out = ""
    for part in path:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out or "(整份)"


def asset_refs(projection: dict, repo: Path) -> dict[str, str | None]:
    """投影里引用到的本地文件 → sha256（不存在记 None：「渲染那一刻没有」也是事实）。"""
    refs: dict[str, str | None] = {}

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
        elif isinstance(value, str):
            text = value.strip()
            if (not text or "\n" in text or "://" in text or len(text) > 400
                    or text.startswith("/")
                    or Path(text).suffix.lower() not in ASSET_SUFFIXES):
                return
            path = repo / text
            refs[text] = sha256_file(path) if path.is_file() else None

    walk(projection)
    return dict(sorted(refs.items()))


#: `diff_paths` 报「这张表的键换了顺序」时挂在路径末尾的标记。
ORDER = "(键的顺序)"


def diff_paths(old: Any, new: Any, path: list[str | int] | None = None) -> list[list[str | int]]:
    """两份投影哪几处不一样（逐字节口径，见 `canonical`）。

    **键的顺序算一处**：两边都有的键排列不同，就报 `<这张表>.(键的顺序)`——
    `sources` 调了个儿，主源片就换了人（模块 docstring「键的顺序」）。
    """
    path = path or []
    if isinstance(old, dict) and isinstance(new, dict):
        out: list[list[str | int]] = []
        if [k for k in old if k in new] != [k for k in new if k in old]:
            out.append(path + [ORDER])
        for key in list(old) + [k for k in new if k not in old]:
            if key not in old or key not in new:
                out.append(path + [key])
            else:
                out += diff_paths(old[key], new[key], path + [key])
        return out
    if isinstance(old, list) and isinstance(new, list):
        if len(old) != len(new):
            return [path + ["(段数/条数)"]] if path else [["(段数/条数)"]]
        out = []
        for i, (a, b) in enumerate(zip(old, new)):
            out += diff_paths(a, b, path + [i])
        return out
    return [] if canonical(old) == canonical(new) else [path]


#: `rules_digest` 拿来量口径的一份样本 spec：`sources` 里有 `_` 键且排在第一、深层
#: 注解、推送块、`1` 和 `1.0`、中文——`project` / `canonical` / `diff_paths` 哪一处
#: 的行为变了，它的投影或差异就跟着变。表里的键另外按名字进指纹（见 `rules_digest`）。
_RULES_PROBE: dict = {
    "slug": "probe",
    "sources": {"_why": "https://a.test/1", "r1": {"url": "https://b.test/2", "_note": "源"}},
    "segments": [{"start": 1, "end": 2.0, "_why": "注", "narration": "中文",
                  "voice": {"rate": "+5%", "_why": "降速"}}],
    "cover": {"eyebrow": "赛场之上", "_layout_why": "认领",
              "portrait": {"image": "assets/reel/p.jpg", "_face_check_why": "认人"}},
    "_facts": ["注解"],
}


def rules_digest() -> str:
    """这一版投影口径的指纹：**表一改就变**，不用等人想起来升 `VERSION`。

    评审 2026-09-27（第三轮）量出来的：往 `RENDER_ANNOTATIONS` 里加一个键、而不升
    `VERSION`，改之前渲、改之后才合并的片子，发布门禁拿新口径去比旧清单——旧投影里
    没有那个键、新投影里有——判「渲染输入变了」，自动链上那个 `Skip` 只印一行
    `[跳过]`，片子就**不吭声地永远不推**。现在清单记下渲染那一刻的指纹，门禁和
    `reattest_check` 认口径时连它一起比（`same_rules`），对不上就按旧口径走：普通渲染
    退回 spec 字节那一道，重核对判不了。

    进指纹的：进投影的注解键、整块剥掉的推送字段、算「引用了素材」的后缀，和
    `project` / `canonical` / `diff_paths` 在 `_RULES_PROBE` 上的行为。
    **不进的**：`GATE_ANNOTATIONS`——它只管认领，加一道闸不改投影；也正因为不进，
    兄弟分支每加一道闸，已渲片子的清单照旧有效。
    """
    probe = json.loads(json.dumps(_RULES_PROBE))
    for key in RENDER_ANNOTATIONS:
        probe[key] = probe["cover"][key] = f"值{key}"
    for key in PUBLISH_FIELDS:
        probe[key] = {"auto": True, "_why": "推送"}
    swapped = dict(probe, sources=dict(reversed(list(probe["sources"].items()))))
    shape = {
        "render_annotations": sorted(RENDER_ANNOTATIONS),
        "publish_fields": sorted(PUBLISH_FIELDS),
        "asset_suffixes": sorted(ASSET_SUFFIXES),
        "projection": canonical(project(probe)),
        "diff": [path_str(p) for p in diff_paths(project(probe), project(swapped))],
    }
    return sha256_bytes(json.dumps(shape, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def same_rules(manifest: dict) -> bool:
    """这份清单是不是按今天的口径写的：`VERSION` 和 `rules_digest()` 都对得上。"""
    return manifest.get("version") == VERSION and manifest.get("rules") == rules_digest()


def describe(path: list[str | int]) -> str:
    """把一处差异翻成「它会动到成片的哪一块」。"""
    head = path[0] if path else ""
    where = path_str(path)
    if path and path[-1] == ORDER:
        hint = ("主源片换了人——没写 source 的段都从第一条取画面"
                if path[:-1] == ["sources"] else "渲染器有按顺序取第一个的地方")
        return f"键的顺序变了（{hint}）：{where}"
    if head == "segments" and len(path) >= 2 and isinstance(path[1], int):
        n = path[1] + 1
        field = str(path[2]) if len(path) > 2 else ""
        if field == "narration":
            return f"第 {n} 段旁白（TTS＋字幕）：{where}"
        if field.startswith("quote"):
            return f"第 {n} 段原声字幕：{where}"
        if field == "voice":
            return f"第 {n} 段配音参数：{where}"
        return f"第 {n} 段画面（窗口/取景/贴图）：{where}"
    labels = {"segments": "段落结构", "cover": "封面（海报/封面口播）",
              "topbar": "顶栏", "stats": "数据统计图"}
    return f"{labels.get(str(head), '渲染参数')}：{where}"


def build(spec_path: Path, outdir: Path, film: Path, repo: Path) -> dict:
    """渲染刚结束时拍一张快照：spec 的渲染投影、引用素材、产物、成片身份。"""
    spec_bytes = spec_path.read_bytes()
    spec = json.loads(spec_bytes)
    projection = project(spec)
    artifacts = {name: sha256_file(outdir / name)
                 for name in ARTIFACTS if (outdir / name).is_file()}
    return {
        "version": VERSION,
        "rules": rules_digest(),
        "slug": str(spec.get("slug") or film.stem),
        "written_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "code_sha": os.environ.get("GITHUB_SHA", ""),
        "spec_sha256": sha256_bytes(spec_bytes),
        "film_sha256": sha256_file(film),
        "film_bytes": film.stat().st_size,
        "projection_sha256": sha256_bytes(canonical(projection).encode("utf-8")),
        "claims": claim_paths(spec),
        "assets": asset_refs(projection, repo),
        "artifacts": artifacts,
        "projection": projection,
    }


def write(outdir: Path, manifest: dict) -> str:
    path = outdir / MANIFEST_NAME
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return sha256_file(path)


def record(spec_path: Path, outdir: Path, film: Path, repo: Path) -> str:
    """渲染结束时调用：写清单，并把它的 sha 记进 `render.json`。

    ⚠️ 必须排在 `check_reel_landed` 之前（工作流里天然如此：QC 是下一步）——
    凭证要把这份清单一起钉进去，重核对才能认出「清单是这一次渲染的」。
    """
    digest = write(outdir, build(spec_path, outdir, film, repo))
    meta_path = outdir / "render.json"
    data = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    data["render_inputs_sha256"] = digest
    meta_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    print(f"[渲染输入] {outdir / MANIFEST_NAME}（sha {digest[:12]}…）："
          "spec 之后只改注解/推送字段时可以 mode=reattest，不用重渲")
    return digest


def record_best_effort(spec_path: Path, outdir: Path, film: Path, repo: Path) -> str | None:
    """`build_match_reel.main` 调的是这个：清单写不成**不许把一趟渲完的片子打红**。

    清单是给「之后只改注解时省一趟」用的，不是这一趟成片合不合格的闸——一个怪素材
    字符串让 `sha256_file` 抛个 `OSError`，就把 7~10 分钟的渲染判成失败，代价错了位
    （复审 fix 轮）。出错就警告、**什么都不留**：清单删掉、`render.json` 里那个 sha 也
    摘掉——半截留着更坏：质检会把盘上的清单钉进凭证，而 `render.json` 没钉它，发布门禁
    就报「render.json 钉的清单和凭证钉的不是同一份」、自动链只印一行 `[跳过]`。
    什么都不留，质检就不钉，门禁退回 spec 字节那一道照发；之后这一版只能 `mode=render`，
    `reattest_check` 报「判不了」（没有清单）。`KeyboardInterrupt` 这类照样往外抛。
    """
    try:
        return record(spec_path, outdir, film, repo)
    except Exception as exc:                   # noqa: BLE001 — 清单写不成不许打红成片
        _discard(outdir)
        print(f"[渲染输入] ⚠️ 清单没写成（{type(exc).__name__}: {exc}）——成片照常；"
              "这一版之后改 spec 只能 mode=render（reattest_check 会报判不了）")
        return None


def _discard(outdir: Path) -> None:
    """把 `record` 可能留下的半截收干净：清单文件、`render.json` 里钉它的那个 sha。"""
    try:
        (outdir / MANIFEST_NAME).unlink(missing_ok=True)
    except OSError as exc:
        print(f"[渲染输入] ⚠️ 半截清单删不掉：{exc}")
    meta_path = outdir / "render.json"
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
        if isinstance(data, dict) and data.pop("render_inputs_sha256", None) is not None:
            meta_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"[渲染输入] ⚠️ render.json 里的清单 sha 摘不掉：{exc}")


def spec_problems(spec_bytes: bytes, manifest: dict, *, claims: bool = True) -> list[str]:
    """新 spec 相对渲染那一刻：渲染投影和认领注解有没有变。空列表＝没变。

    不含素材字节（`asset_problems`）：`auto_push_gate` 跑在不检出 assets/ 的
    稀疏工作区里，它只复核这一半。

    `claims=False`：只比投影、不按**今天的** `Gate.rule` 重判渲染时记下的认领——发布
    门禁在 spec 字节就是渲染那一份时用（见 `auto_push_gate._validate_render_inputs`）。
    """
    try:
        spec = json.loads(spec_bytes)
    except (ValueError, UnicodeDecodeError):
        return ["spec 不是有效 JSON"]
    problems = [f"渲染输入变了——{describe(p)}"
                for p in diff_paths(manifest.get("projection"), project(spec))]
    for path in (manifest.get("claims") or []) if claims else []:
        if not claim_holds(spec, path):
            problems.append(
                f"渲染那一刻有的认领没了：{path_str(path)}"
                "（删了、或改成那道闸不认的值——`false` / 一串空格；这类认领有的闸"
                "只在编码里跑、dry-run 够不着，改掉就等于绕过它）")
    return problems


def asset_problems(spec_bytes: bytes, manifest: dict, repo: Path) -> list[str]:
    try:
        spec = json.loads(spec_bytes)
    except (ValueError, UnicodeDecodeError):
        return []                      # `spec_problems` 报「不是有效 JSON」，这里不重复
    now = asset_refs(project(spec), repo)
    then = manifest.get("assets") or {}
    return [f"引用的素材文件变了：{name}（渲染时 {str(then.get(name))[:12]}，"
            f"现在 {str(now.get(name))[:12]}）"
            for name in sorted(set(now) | set(then)) if now.get(name) != then.get(name)]
