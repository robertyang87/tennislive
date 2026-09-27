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
    wong-paul      d5bbc48c   _facts 里一个加错的分钟数
    medvedev-damm  e15e73e5   push._no_auto_why → push.auto
    gauff-jovic    80bbdd1a   两段的 _score_inset_why（推送之后，链从此断着）
    （zheng-liutova 93df2572 是采访线，同一个形状，这里不管）

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
  长什么样（字幕下锚、比分板挑哪一套）
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


class Gate(NamedTuple):
    """一个只进闸的注解：哪道闸、在 spec 的哪儿读、按什么口径算数。

    `where` 为空＝**不是认领**：只在备料（`promote_reel_draft`）时读、render 和
    dry-run 都不调；或者它的出现是「拒绝」而不是「放行」（`_import`）。删了不绕过
    任何闸，不记。

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
    "_claims": _gate("_absolute_claims_need_a_source：全称断言要两个不同主机的出处",
                     "_absolute_claims_need_a_source", "_claims", truthy),
    "_decider_why": _gate("reel_facts.decider_set_problem：大满贯提「决胜盘」的认领",
                          "decider_set_problem", "_decider_why"),
    "_durations": _gate("promote_reel_draft._duration（备料时读）", "_duration"),
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
    "_hit_data": _gate("promote_reel_draft.promote（备料提升时读）", "promote"),
    "_import": _gate("main：导入成片拒绝重渲（只在非 dry-run 时 raise）——它是「拒绝」"
                     "不是「放行」，删了不绕过任何闸", "main"),
    "_layout_why": _gate("build_cover：赛场之上退回 VS 版式要认领（编码里才查）",
                         "build_cover", "cover._layout_why", text_str),
    "_license": _gate("music_problem：背景音乐要写授权",
                      "music_problem", "music._license"),
    "_low_res_why": _gate("cover_photo_problem：封面低于门槛的认领",
                          "cover_photo_problem", "cover.portrait._low_res_why"),
    "_match": _gate("reel_facts 的赛果/抢十闸拿它对账、promote_reel_draft 的撞车键",
                    "verified_result_problem decider_tiebreak_problem waiting_reasons "
                    "promote _source_urls _match_keys", "_match", truthy),
    "_narration_why": _gate("cover_voice_matches_hook_problem：封面口播和钩子不同的认领",
                            "cover_voice_matches_hook_problem", "cover._narration_why"),
    "_no_cold_open_why": _gate("cold_open_problem：源片里没有赢球后画面的认领",
                               "cold_open_problem", "_no_cold_open_why"),
    "_photo_caption_safety": _gate("parse_segments：全屏照片字幕不遮主体的目视依据",
                                   "_one", "segments[]._photo_caption_safety", truthy),
    "_photo_source": _gate("parse_segments：全屏照片的来源（要 https）",
                           "_one", "segments[]._photo_source", https_url),
    "_quote_skip_why": _gate("unvoiced_quote_problem：不配原声字幕的认领",
                             "unvoiced_quote_problem", "segments[]._quote_skip_why"),
    "_revision_request": _gate("duplicate_match_problem：同一场球重做的认领",
                               "duplicate_match_problem", "_revision_request", truthy),
    "_score_inset_why": _gate(
        "parse_segments / _seg_score_windows：比分板不回贴的认领（顶层那句是 promote "
        "写的说明，没有闸读）", "parse_segments _seg_score_windows promote",
        "segments[]._score_inset_why", text_str),
    "_tactics_why": _gate("reel_craft.shot_craft_problem：源片看不出球路的认领",
                          "shot_craft_problem", "_tactics_why"),
    "_topbar_format_why": _gate("_topbar_lines → tour_topline_problem：顶栏赛事行格式特例的认领",
                                "_topbar_lines", "_topbar_format_why"),
    "_topic_format_why": _gate("reel_facts.cover_topic_problem：封面副标题格式特例的认领",
                               "cover_topic_problem", "_topic_format_why"),
    "_tts_backend_why": _gate("apply_tts_backend：退回 edge-tts 的认领（后端本身是真字段 "
                              "tts_backend）", "apply_tts_backend", "_tts_backend_why",
                              nonblank_str),
    "_visual_evidence": _gate("promote_reel_draft（备料提升时读）", "waiting_reasons promote"),
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
    }),
}

#: 渲染写进 outdir、而且跟着提交进仓库的**由 spec 算出来的产物**。重核对要求它们
#: 和渲染那一刻逐字节相同——`poster.jpg` 是推送第一屏，`subtitles.ass` 是烧进
#: 成片的那一份（凭证本来就钉着它），换过就说明这已经不是那一次渲染的产物了。
#: 名字和 build_match_reel.POSTER_NAME / STAT_CARD_NAME 对账，判据在测试里。
ARTIFACTS = ("subtitles.ass", "topbar.ass", "poster.jpg", "stat_card.jpg",
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


def spec_problems(spec_bytes: bytes, manifest: dict) -> list[str]:
    """新 spec 相对渲染那一刻：渲染投影和认领注解有没有变。空列表＝没变。

    不含素材字节（`asset_problems`）：`auto_push_gate` 跑在不检出 assets/ 的
    稀疏工作区里，它只复核这一半。
    """
    try:
        spec = json.loads(spec_bytes)
    except (ValueError, UnicodeDecodeError):
        return ["spec 不是有效 JSON"]
    problems = [f"渲染输入变了——{describe(p)}"
                for p in diff_paths(manifest.get("projection"), project(spec))]
    for path in manifest.get("claims") or []:
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
