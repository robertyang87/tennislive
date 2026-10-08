#!/usr/bin/env python3
"""reel `--dry-run` 的素材与格式闸——只读 spec 和仓库里已经提交的文件，不联网、不碰源片。

来路是 2026-09-27 那次返工取证（账号所有者：「返工太多、素材时有缺漏」，P1）：下面每一类错，
原来都要先付一趟 render（7~15 分钟），有的甚至**合并、推送之后**才现形；而判它们
要的东西——spec 里的字、仓库里的图、发布账本——在写 spec 那一刻就全在盘上。

| 闸 | 原来在哪儿才红 | 证据 |
|---|---|---|
| ① 封面用时写成两段 `1:27` | 渲完看封面：`1:27` 被当成 1 分 27 秒，印成 `0:01` | bucsa-noskova 5bd09938（白渲一趟）；shelton-alcaraz 70573150（推送之后才改） |
| ② 赛场之上没带数据统计图 | **合并之后**的 auto-push-reel（`push_reel` 要 `stat_card.jpg`） | hu-kopriva run 35950951376 → 6a84ed2f 补图重渲；zheng-you e8b3257a |
| ③ 引用的图解不开／国旗换算不出 | render 末尾渲数据图那一步；渲封面那一步 | zheng-you 4d35f28f / aedb4504（`wta-322451.png` 坏块，两趟白渲）；wong-vallejo run 36259013573（`PRY`） |
| ④ 封面照片是已经发出去的另一条用过的 | 推送之后账号所有者「换一张封面吧」 | wang-prozorova 9f1169aa（借了同站 wang-garland 那张）→ 81ec82b4 重渲重推 |
| ⑥ 字幕里的数字换算半截 | 渲完抽帧才看见 | bu-majchrzak 288ed727「四分之一决赛」；本模块量出来的「7比6比四」 |

⑤（推送标题的字数闸）不在 `spec_asset_problems` 里：它要 `.xhs.txt` 的路径，接在
dry-run 那一段（`push_copy_check`），调的是 `push_reel.prepare_copy`——和 runner 上
`production_preflight`（`push_reel.py --stage check`）是**同一个函数**，本地和远端不再分叉。

⚠️ **哪些硬、哪些只报**（仓库的老规矩：手写 spec 硬，自动产的 spec 只报
——那一头没人写 `_why`，硬了会把自动链卡成「今天没有候选」）：

- ①②③ 对**所有** spec 都硬：它们不是判断题，是**必然发生的失败**——用时印错、
  推送闸拒发、图解不开，谁写的 spec 都一样；自动链的 `promote_reel_draft` 本来就
  在 `waiting_reasons` 里要求 stats 和头像，放到这儿不会多卡一条
- ④⑥ 手写硬、自动只报

每一道都有认领口（`_why`），已经发出去的存量挂在 `data/legacy_reel_asset_gates.json`，
**只许减不许加**，自检在 `tests/test_reel_asset_gates.py`。
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / "specs" / "reels"
#: 「发没发过」的三个出处。⚠️ 函数的默认参数一律写 None、**调用那一刻**才读这几个名字
#: （`publication_record`）——原来绑在 `def` 的默认值上，测试 monkeypatch 模块属性、
#: 设环境变量都够不着，`_empty_reel_ledger` 钉空了 `reel_facts` 那一半，这一半照读真账本。
LEDGER = ROOT / "data" / "reel_publish_ledger"
OUTPUT = ROOT / "output"
#: 账本（2026-08-24 起）之前发的 125 条，从 `output/*/reel/*/pushed.json` 冻成的一张表。
#: runner 的稀疏检出不带 `output/`（cone 模式 add 那 278 个 pushed.json 会连同目录产物
#: 342 MB 一起拉回来），没有这张表，runner 上的封面复用闸就看不见这批：同栏目借它们的
#: 封面照样放行（复审 2026-09-27：借 noskova-tauson 封面的新 spec，本地硬红、runner 放行）。
#: 08-24 起每次推送都同时写账本，所以这张表不会再长。对账见
#: `test_账本之前发的那批冻成表_和pushed_json逐条对得上`。
PRE_LEDGER = ROOT / "data" / "reel_pushed_before_ledger.json"
LEGACY_PATH = ROOT / "data" / "legacy_reel_asset_gates.json"

sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

#: 一场打满的职业比赛最短也有半小时上下；2026-09-27 全库 179 条写了 `data:` 用时的
#: spec，最短的是 3565 秒（59 分钟）。20 分钟以下只有两种可能：退赛／不战而胜，或者
#: 「时:分」被读成了「分:秒」——后者正是 `1:27` → 87 秒的那一类。
MIN_MATCH_SECONDS = 20 * 60
_TWO_PART = re.compile(r"\d+:\d{2}")
_IMAGE = re.compile(r"\.(png|jpe?g|webp)$", re.I)


def _auto(spec: dict) -> bool:
    return (spec.get("_production") or {}).get("status") == "ready_for_render"


@functools.lru_cache(maxsize=1)
def _legacy_doc() -> dict:
    # ⚠️ 读不到就当没有存量：finalize-reel / reel-model-benchmark 的稀疏检出里没有
    # `data/`，不接住的话 promote → validate_spec 在这儿抛 FileNotFoundError，每一条
    # 人工 finalize 的草稿都红（复查在不带 data/ 的检出里复现）。validate_spec 路径上
    # 另外四张存量表（legacy_cover_topic / fullbleed / topline / unvoiced_quote）都是
    # 这么接的。
    try:
        return json.loads(LEGACY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def legacy(kind: str) -> frozenset[str]:
    """`no_stats` / `cover_reuse` / `numeral_display` 三张存量表。只许减不许加。"""
    return frozenset(_legacy_doc().get(kind) or ())


# ─────────────────────────────────────────────────────────── ① 封面用时 ──

def _retired(spec: dict) -> bool:
    """这场是退赛／不战而胜：封面 `result` 或 `_match` 的赛果写着。"""
    from reel_facts import _RETIRED  # noqa: PLC0415

    match = spec.get("_match") if isinstance(spec.get("_match"), dict) else {}
    texts = [(spec.get("cover") or {}).get("result"), match.get("winner_result"),
             match.get("loser_result"), match.get("status")]
    return any(_RETIRED.search(str(text)) for text in texts if text)


def duration_problem(spec: dict) -> str | None:
    """封面比分板上的用时：**只看 `data:` 写死的那一种**，真接口要联网，照旧归渲染。

    `versus_poster._duration_seconds` 读两段式 `a:b` 一律当「分:秒」——它还要读
    官方接口给的值，那边的两段式确实可能是分秒，所以**解析器不动**；动的是
    spec 这一头：手写的用时不许写两段式，写 `1:27:00` 或秒数。
    """
    source = ((spec.get("cover") or {}).get("scoreboard") or {}).get("duration_source")
    if not isinstance(source, dict):
        return None
    url = str(source.get("url") or "").strip()
    if not url.startswith("data:"):
        return None
    import versus_poster as vp  # noqa: PLC0415

    try:
        with urllib.request.urlopen(url) as response:  # noqa: S310 - 上面只放行 data:
            payload = json.loads(response.read().decode("utf-8"))
    except (ValueError, OSError) as exc:
        return f"封面用时 `cover.scoreboard.duration_source.url` 的 data: 解不出 JSON：{exc}"
    match_id = str(source.get("match_id") or "").strip()
    if match_id and isinstance(payload, dict) and isinstance(payload.get("matches"), list):
        payload = next((row for row in payload["matches"]
                        if str(row.get("MatchID") or row.get("matchId") or "") == match_id), {})
    raw = vp._find_duration(payload, str(source.get("field") or "").strip() or None)  # noqa: SLF001
    if isinstance(raw, str) and _TWO_PART.fullmatch(raw.strip()):
        return (f"封面用时写成了两段式 {raw.strip()!r}：比分板的解析器把两段一律读成「分:秒」"
                f"（`1:27` → 87 秒，印成 0:01——bucsa-noskova 5bd09938 就是这么白渲一趟的）。\n"
                f"手写的用时写成 `{raw.strip()}:00`（时:分:秒）或者秒数。")
    seconds = vp._duration_seconds(raw)  # noqa: SLF001
    if seconds is None:
        return (f"封面用时 data: 里找不到能读的用时（field={source.get('field')!r}）："
                "渲封面那一步一样会停，先补上。")
    if (seconds < MIN_MATCH_SECONDS and not _retired(spec)
            and not str(spec.get("_short_match_why") or "").strip()):
        return (f"封面用时解出来只有 {seconds} 秒（{seconds // 60} 分钟）：一场打完的比赛"
                f"不会短于 {MIN_MATCH_SECONDS // 60} 分钟，多半是「时:分」被读成了「分:秒」。\n"
                "退赛／不战而胜在 `cover.result` 里带上「退赛」／Ret.；真是这么短就在 spec 顶层"
                "写 `_short_match_why` 说清出处。")
    return None


# ─────────────────────────────────────────────────────── ② 数据统计图 ──

def stats_card_problem(spec: dict, *, legacy_set: frozenset[str] | None = None) -> str | None:
    """「赛场之上」必须带 `stats`，两边都要有头像——和推送那道闸同一条规矩。

    ⚠️ **`_no_stats_why` 在这儿不算数，这是有意的，不是替账号所有者做选择。**
    那个认领口是 2026-08-14 为「WTA 巡回赛查不到制胜分／UE，别硬凑一张缺项的图」
    开的；**2026-08-25 账号所有者定了「赛场之上的微信推送必须带全场技术统计图」**
    （`push_reel` 里那条注释，e8b3257a），`push_reel` 从那天起缺 `stat_card.jpg`
    就拒发、不认任何认领。后定的那条是真正拦人的那一道，而两条同时活着的结果是：
    认领了 `_no_stats_why` 的 spec 一路绿到合并，然后在 auto-push-reel 上红——
    hu-kopriva-chengdu-2026-r1（run 35950951376）就是这么合并之后重渲的。
    所以 dry-run、`tests/test_reel_editorial.py`、推送三处现在是同一条规矩：
    查不到制胜分／UE 就少画那两行（`render_stat_card` 只画有数的行），图照样要有。
    """
    cover = spec.get("cover") or {}
    if str(cover.get("eyebrow") or "").strip() != "赛场之上" or not spec.get("segments"):
        return None
    if str(spec.get("slug") or "") in (legacy("no_stats") if legacy_set is None else legacy_set):
        return None
    from team_exhibition_scope import video_without_tour_stats
    if video_without_tour_stats(spec):
        return None
    stats = spec.get("stats")
    if not isinstance(stats, dict) or not stats:
        return ("「赛场之上」推微信必须带全场技术统计图（push_reel：缺 stat_card.jpg 就拒发），"
                "而这条 spec 没有 `stats`——render 会绿、合并会绿，auto-push-reel 才红，"
                "那时候就得重渲一趟（hu-kopriva 6a84ed2f）。\n"
                "补 `stats.a` / `stats.b`（`tools/match_stat_hooks.py --from-spec` 机器抄；"
                "查不到制胜分／UE 就不写那两项）。⚠️ `_no_stats_why` 过不了推送那道闸。")
    missing = [side for side in ("a", "b")
               if not isinstance(stats.get(side), dict) or not stats[side].get("headshot")]
    if missing:
        return (f"`stats.{'/'.join(missing)}` 缺 `headshot`：数据统计图渲到那一侧就停。"
                "`python3 tools/headshot_index.py <spec> --write`，ATP 球员用 "
                "`tools/fetch_official_headshot.py atp <名> --id <ID> --via <赛事域名>`。")
    return None


# ────────────────────────────────────────────────────────── ③ 图片解码 ──

def _images_in(node: object, where: str = "") -> list[tuple[str, str]]:
    """spec 里所有指向仓库文件的图片路径（`_` 开头的注解不算，URL 和占位符不算）。

    不按字段名列清单：新加一个带图的字段（`portrait_above`、`inset.image`）不会漏。
    """
    out: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str) and key.startswith("_"):
                continue
            out += _images_in(value, f"{where}.{key}" if where else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            out += _images_in(value, f"{where}[{index}]")
    elif isinstance(node, str):
        text = node.strip()
        if _IMAGE.search(text) and not re.match(r"^(?:[a-z]+:|<)", text, re.I):
            out.append((where, text))
    return out


def _flag_paths(spec: dict) -> list[tuple[str, str | None, str]]:
    """比分板和数据统计图上那两面矩形国旗：(位置, 旗子文件或 None, 国别码)。

    和 `versus_poster._score_flag` 同一条换算；只在真的会画旗的时候查
    （赛场之上写了 `cover.result`，或者带了 `stats`）。
    """
    cover = spec.get("cover") or {}
    draws = ((str(cover.get("eyebrow") or "").strip() == "赛场之上"
              and str(cover.get("result") or "").strip()) or spec.get("stats"))
    if not draws:
        return []
    from tennislive.zh.countries import country_iso2  # noqa: PLC0415

    out = []
    for index, meta in enumerate(cover.get("matchup") or []):
        if not isinstance(meta, dict) or meta.get("country") is None:
            continue                       # 缺键由渲染那头报；null ＝ 中立身份，不画旗
        codes = meta["country"] if isinstance(meta["country"], list) else [meta["country"]]
        for code in codes:
            iso2 = country_iso2(str(code))
            path = f"assets/flags/{iso2.lower()}.png" if iso2 else None
            out.append((f"cover.matchup[{index}].country", path, str(code)))
    return out


def image_load_problem(path: Path) -> str | None:
    """**解到最后一个字节**，不只是读文件头——`Image.open` 只读头，坏块照样 open 得开。

    JPEG 用 draft（1/8 缩放）解：熵编码仍然从头解到尾，截断照样报，
    而 22 MB 的封面原图从 0.7 秒降到 0.3 秒。
    """
    from PIL import Image  # noqa: PLC0415

    try:
        with Image.open(path) as image:
            if image.format == "JPEG":
                image.draft("RGB", (max(1, image.size[0] // 8), max(1, image.size[1] // 8)))
            image.load()
    except Exception as exc:  # noqa: BLE001 - 任何解码错误都是这道闸要报的
        return f"{type(exc).__name__}: {exc}"
    return None


def image_problems(spec: dict, *, root: Path = ROOT) -> list[str]:
    """spec 引用的每一张图（封面、头像、贴图、国旗）都要在、都要解得开。"""
    problems = []
    seen: set[str] = set()
    targets = list(_images_in(spec))
    for where, rel, code in _flag_paths(spec):
        if rel is None:
            problems.append(f"{where}={code!r} 换算不出 ISO2，比分板上那面国旗画不出来"
                            "（写 IOC 三字码，查不到国别就写 null）")
            continue
        targets.append((where, rel))
    for where, rel in targets:
        if rel in seen:
            continue
        seen.add(rel)
        path = root / rel
        if not path.is_file():
            problems.append(f"`{where}` 指的 {rel} 不在仓库里")
            continue
        broken = image_load_problem(path)
        if broken:
            problems.append(f"`{where}` 指的 {rel} 解不开（{broken}）——换一张完整的图"
                            "（zheng-you 那次是半截 PNG，渲出来是「上半张脸」）")
    return problems


# ────────────────────────────────────────────────────────── ④ 封面复用 ──

def _cover_photos(spec: dict) -> list[str]:
    """封面上那张**照片**（抠图和头像本来就是反复用的，不算）。"""
    cover = spec.get("cover") or {}
    out = []
    for key in ("portrait", "portrait_above"):
        block = cover.get(key)
        if isinstance(block, dict) and block.get("image"):
            out.append(str(block["image"]))
    for side in ("top", "bottom"):
        block = (cover.get("versus") or {}).get(side)
        if isinstance(block, dict) and block.get("image"):
            out.append(str(block["image"]))
    if cover.get("approved_image"):
        out.append(str(cover["approved_image"]))
    return out


def publication_record() -> tuple[Path, Path | None, Path | None]:
    """「发没发过」这一刻读哪儿：`(发布账本目录, 产物根目录或 None, 账本之前那批的冻结表或 None)`。

    设了 `TENNISLIVE_REEL_LEDGER_DIR`（`tests/conftest.py::_empty_reel_ledger`，
    和 `reel_facts.REEL_LEDGER_DIR` 认的是同一个变量）＝**整份发布记录钉成那个目录**：
    账本读它，产物目录里的 `pushed.json` 和冻结表都不再认——那是同一份记录的老出处，
    只钉账本不钉它们，推送落一个 `pushed.json` 照样能把测试打红。生产上没人设它。
    每次调用现读环境变量（不在 import 时读）：`build_match_reel.py render --dry-run`
    子进程继承得到，进程内 `monkeypatch.setenv` 也立刻生效。
    """
    pinned = os.environ.get("TENNISLIVE_REEL_LEDGER_DIR")
    if pinned:
        return Path(pinned), None, None
    return LEDGER, OUTPUT, PRE_LEDGER


def _record(ledger: Path | None, output: Path | None,
            pre_ledger: Path | None = None) -> tuple[Path, Path | None, Path | None]:
    """显式传进来的出处优先；没传的那几个按 `publication_record()` 现取。"""
    default_ledger, default_output, default_pre = publication_record()
    return (default_ledger if ledger is None else Path(ledger),
            default_output if output is None else Path(output),
            default_pre if pre_ledger is None else Path(pre_ledger))


def pre_ledger_pushes(path: Path | None = None) -> dict[str, str]:
    """冻结表里的 `{slug: 第一次发出去的时刻}`；表不在（finalize-reel 那种不带 `data/`
    的稀疏检出）就当空表——和存量豁免表一个口径，不许抛。"""
    path = PRE_LEDGER if path is None else Path(path)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    pushes = doc.get("pushes") if isinstance(doc, dict) else None
    return {str(k): str(v) for k, v in pushes.items()} if isinstance(pushes, dict) else {}


def _published(ledger: Path, output: Path | None,
               pre_ledger: Path | None = None) -> dict[str, str]:
    """每条已经发出去的片子 → **第一次**发出去的时刻（ISO 字符串，UTC）。

    三个出处取早的那个：发布账本（`data/reel_publish_ledger/`，2026-08-24 起才有）、
    产物目录里的 `pushed.json`（更早的那批只有它），以及那批冻成的表（`PRE_LEDGER`，
    runner 上没有 `output/` 时靠它）。只认账本不认老出处的话，08-24 之前发的片子全是
    「没发过」——量出来的第一个误报就是这个形状：wangxiyu-keys（08-20 发）被判成
    「借了 asiad-2026-women-draw（09-27 发）的图」，方向整个反了。
    不缓存：全库一遍 30 毫秒，缓存了反而会在账本变了之后读旧的；要连着判很多条的
    （全库扫描），自己算一次、经 `cover_reuse_finding(published=…)` 传进去。
    """
    first: dict[str, str] = {}

    def note(slug: str, at: object) -> None:
        if isinstance(at, str) and at.strip():
            first[slug] = min(first.get(slug, at), at)

    for path in sorted(Path(ledger).glob("*.json")) if Path(ledger).is_dir() else ():
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for attempt in doc.get("attempts") or []:
            if isinstance(attempt, dict) and attempt.get("status") == "sent":
                note(path.stem, attempt.get("at"))
    pushed = Path(output) if output is not None else None
    for path in pushed.glob("*/reel/*/pushed.json") if pushed and pushed.is_dir() else ():
        try:
            note(path.parent.name, json.loads(path.read_text(encoding="utf-8")).get("at"))
        except (ValueError, AttributeError):
            continue
    if pre_ledger is not None:
        for slug, at in pre_ledger_pushes(pre_ledger).items():
            note(slug, at)
    return first


def first_sent(slug: str, *, ledger: Path | None = None, output: Path | None = None,
               pre_ledger: Path | None = None) -> str | None:
    """这条片子**第一次**发出去的时刻（没发过就是 None）。"""
    return _published(*_record(ledger, output, pre_ledger)).get(slug)


def _sha(path: Path) -> str:
    stat = path.stat()
    return _sha_cached(path, stat.st_size, stat.st_mtime_ns)


@functools.lru_cache(maxsize=4096)
def _sha_cached(path: Path, size: int, mtime_ns: int) -> str:
    # 大小和修改时间进缓存键：同一路径换了内容，不会拿到旧哈希
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cover_reuse_problem(spec: dict, *, specs: Path | None = None,
                        ledger: Path | None = None, root: Path = ROOT,
                        output: Path | None = None, pre_ledger: Path | None = None,
                        legacy_set: frozenset[str] | None = None) -> str | None:
    """见 `cover_reuse_finding`；只要文案，不分栏目。"""
    found = cover_reuse_finding(spec, specs=specs, ledger=ledger, root=root,
                                output=output, pre_ledger=pre_ledger, legacy_set=legacy_set)
    return found[0] if found else None


def cover_reuse_finding(spec: dict, *, specs: Path | None = None,
                        ledger: Path | None = None, root: Path = ROOT,
                        output: Path | None = None, pre_ledger: Path | None = None,
                        legacy_set: frozenset[str] | None = None,
                        published: dict[str, str] | None = None,
                        ) -> tuple[str, bool] | None:
    """封面照片和另一条**已经发出去**的片子是同一张（按路径，或者按内容哈希）。

    账号所有者看 wang-prozorova 第一版时要「换一张封面吧」：那张是同站
    `wang-garland-singapore-2026-r2` 已经推过的（9f1169aa → 81ec82b4，重渲重推）。
    判据只认**比我先发出去**的那一条——我先发、别人后借我的图，不是我的错；
    显式的重做（`revision_of` 互指）也不算。比内容先比文件大小，大小一样才算哈希。
    `published` 给了就不再读发布记录（全库扫描算一次传进来；`ledger`／`output`／
    `pre_ledger` 这时不起作用）。
    """
    slug = str(spec.get("slug") or "")
    claimed = legacy("cover_reuse") if legacy_set is None else legacy_set
    if str(spec.get("_cover_reuse_why") or "").strip() or slug in claimed:
        return None
    mine = {rel: root / rel for rel in _cover_photos(spec) if (root / rel).is_file()}
    if not mine:
        return None
    by_size: dict[int, list[Path]] = {}
    for path in mine.values():
        by_size.setdefault(path.stat().st_size, []).append(path)
    if published is None:
        published = _published(*_record(ledger, output, pre_ledger))
    my_sent = published.get(slug)
    mine_col = str((spec.get("cover") or {}).get("eyebrow") or "")
    # 跨栏目的命中先记着、接着往下找：按文件名排在前面的恰好是一条跨栏目的，不许把
    # 后面那条同栏目的盖掉（a-story 先发、b-reel 后发、我是赛场之上——该硬红的被降成只报）
    cross: tuple[str, bool] | None = None
    for other_path in sorted(Path(SPECS if specs is None else specs).glob("*.json")):
        other_slug = other_path.stem
        their_sent = published.get(other_slug)
        if other_slug == slug or not their_sent or (my_sent and my_sent <= their_sent):
            continue
        try:
            other = json.loads(other_path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if spec.get("revision_of") == other_slug or other.get("revision_of") == slug:
            continue
        if not my_sent and (other_slug in claimed
                            or str(other.get("_cover_reuse_why") or "").strip()):
            # 我查不到自己发没发过（哪条流水线既没 output/ 也没冻结表），而它自己认领了
            # 「借图」——借的多半就是我这张。不跳过的话，重渲 wangxiyu-keys（08-20 发）
            # 会被 asiad-2026-women-draw（09-27 发、已认领）反咬一口。
            continue
        for rel in _cover_photos(other):
            path = root / rel
            same = rel in mine
            if not same and path.is_file():
                size = path.stat().st_size
                same = any(_sha(path) == _sha(candidate)
                           for candidate in by_size.get(size, ()))
            if same:
                # 第二个值＝同一栏目。CLAUDE.md「同一件事，不同栏目各讲一次不算重复」：
                # 存量 7 次命中里 6 次是网球有故事借同一个人的赛场之上封面，唯一的证据
                # （wang-prozorova「换一张封面吧」）是同栏目同站——跨栏目只报不拦。
                their_col = str((other.get("cover") or {}).get("eyebrow") or "")
                found = (f"封面照片 {rel} 已经在 `{other_slug}` 上发出去过（{their_sent}）——"
                         "读者刷到的是同一张图。换一张这一场自己的图（官方图库／抽帧，见 "
                         "tennis-cover-photos）；真要沿用（同一个人的系列、按要求重做）就在 "
                         "spec 顶层写 `_cover_reuse_why` 说清为什么。",
                         mine_col == their_col)
                if found[1]:
                    return found
                cross = cross or found
                break
    return cross


# ─────────────────────────────────────────────────────── ⑥ 字幕里的数字 ──

_NUM = "〇零一二三四五六七八九十百千两"
#: 两个比分连着写，没有标点隔开：「七比六六比四」→ 换算成「7比6比四」——屏幕上是一个
#: 不存在的比分，还丢了一个数。换算那一步两边都换（`X比Y`），所以换完之后「比」挨着
#: 汉字数字只可能是粘连的残渣。改法是在旁白里加个顿号（「七比六、六比四」）：
#: 字幕同一行印成「7比6 6比4」，TTS 也多一个停顿。
_SCORE_CHAIN = re.compile(rf"\d+比\d+比|\d比[{_NUM}]|[{_NUM}]比\d")
#: 同一个数一半阿拉伯、一半中文——换算规则少接了一种结构
#: （`tennislive.video.numeral_halves` 接住的那三种，和 288ed727 之前的「四分之一决赛」）。
_HALF_NUMBER = re.compile(
    rf"[{_NUM}]+个?小时\d|\d+小时[{_NUM}]+分"
    rf"|\d+月[{_NUM}]+[号日]|[{_NUM}]+月\d+[号日]"
    rf"|\d+胜[{_NUM}]+负|[{_NUM}]+胜\d+负"
    rf"|[{_NUM}]+分之[{_NUM}]+决赛"
)
#: 兜底：汉字数字和阿拉伯数字直接贴在一起（「3盘二」「二3」）——换算只换了一半的
#: 通用形状，上面两条认不出的新结构落在这儿。两个口子是量出来的：「抢七7比5」
#: （抢七是术语）和「1000八强」（N 强是轮次名，归轮次那条规矩管）。
_DIGIT_TOUCH = re.compile(rf"(?<![抢第{_NUM}])[{_NUM}]+\d|\d[{_NUM}]+(?![强{_NUM}])")


def _displayed_narrations(spec: dict) -> list[tuple[str, str]]:
    """会被排成字幕的中文旁白：(位置, 原文)。原声段（`quote`）是手写双语，不过换算。"""
    out = []
    for index, seg in enumerate(spec.get("segments") or [], 1):
        if not isinstance(seg, dict) or seg.get("quote"):
            continue
        text = str(seg.get("narration") or "")
        if text.strip():
            out.append((f"第 {index} 段", text))
    return out


def numeral_display_problems(spec: dict, *,
                             legacy_set: frozenset[str] | None = None) -> list[str]:
    """把每段旁白过一遍**字幕真正会画出来的样子**（`subtitle_lines` → `_sub_display`），
    找换算换坏了的数字。

    量过全库才定的范围（2026-09-27，305 条 reel spec、12407 行字幕）：字幕里剩下的
    汉字数字有 7371 处，绝大多数是**故意留的**（序数「第二盘」631 处、「第X个」490、
    「这一局」、「一发」、「抢七」、「三成」……），拿「剩下汉字数字就红」当闸是一堵
    天天误报的墙。所以只抓**换错了**的——转换成功了、只是转了一半：

    - **两个比分粘成一个**：「六比三七比五」→「6比7比五」。12 条已发片子 13 处印着错比分
      （最狠的一条是「4比6比6比2」）；改法是旁白里断开（「六比三、七比五」）
    - **同一个数半中半洋**：「两小时四十分钟」→「两小时40分钟」。这一类是换算规则
      漏接的结构，量出来 98 条 spec、127 处；2026-09-27 在 `numeral_halves` 里补上之后
      存量 0 处。这道闸留着，是为了下一种没接住的结构（像 288ed727 的「四分之一决赛」）
      在 dry-run 就红，而不是渲完抽帧才看见
    - **汉字数字贴着阿拉伯数字**：上面两条的通用兜底（存量 0 处）

    认领口 `_numeral_display_why`（spec 顶层）；已发的挂在 `numeral_display` 那张表里。
    """
    if str(spec.get("_numeral_display_why") or "").strip():
        return []
    if str(spec.get("slug") or "") in (legacy("numeral_display") if legacy_set is None
                                        else legacy_set):
        return []
    from tennislive.video.explainer import readable, subtitle_lines  # noqa: PLC0415

    problems = []
    for where, text in _displayed_narrations(spec):
        for start, end, shown in subtitle_lines(readable(text)):
            hit = _SCORE_CHAIN.search(shown)
            if hit:
                problems.append(
                    f"{where}字幕会印成「{shown}」——旁白「{text[start:end]}」里两个比分"
                    f"连着写，换算把它们粘成了一个错比分（{hit.group(0)}）。两个比分之间加个"
                    "顿号或逗号（「六比三、七比五」）。")
                continue
            hit = _HALF_NUMBER.search(shown) or _DIGIT_TOUCH.search(shown)
            if hit:
                problems.append(
                    f"{where}字幕会印成「{shown}」——同一个数一半阿拉伯一半中文"
                    f"（{hit.group(0)}）。这是 `arabic_numerals` 没接住的结构，去"
                    "`src/tennislive/video/numeral_halves.py` 补上，"
                    "别为了它改旁白（TTS 那一份本来就该写汉字）。")
    return problems


# ─────────────────────────────────────────────────────────── ⑤ 推送标题 ──

def beijing_today() -> str:
    return datetime.now(timezone(timedelta(hours=8))).date().isoformat()


def push_copy_check(copy_path: Path, *, date: str | None = None) -> tuple[str, str, str | None]:
    """和 runner 上 `production_preflight` 同一个函数：`push_reel.prepare_copy`。

    返回 `(标题, 去掉标题的正文, 问题)`；问题为 None 就是过了。日期和 preflight 一样
    取北京时间今天——标题里那格日期占的字位跟着它变。不传的话 `headline` 从 outdir
    里找日期，本地和 runner 的 dry-run 都是 `--outdir /tmp/dryrun`，找不到，每一趟都
    退回占位标题，字数闸就一次都没跑过（这正是 2026-09-27 取证抓到的那个洞：
    medvedev-royer 抄一份把 `push.summary` 写到 26 字位，dry-run 退出 0，
    `push_reel.py --stage check` 退出 1）。

    ⚠️ 栏目跟着 spec 的 `cover.eyebrow`（`column_of`），和真推送一样；runner 上那步
    preflight 写死了 `--column 赛场之上`，对「网球有故事」少算一个字——这儿更严，不更松。
    """
    import push_reel  # noqa: PLC0415

    try:
        _column, title, body = push_reel.prepare_copy(
            Path(copy_path), OUTPUT / "preflight", date=date or beijing_today())
    except SystemExit as exc:
        return "", "", str(exc)
    return title, body, None


# ──────────────────────────────────────────────────────────────── 汇总 ──

def spec_asset_problems(spec: dict, *, at_render: bool = True,
                        ) -> tuple[list[str], list[str]]:
    """`validate_spec` 只接这一刀：返回 `(硬的, 只报的)`。

    `at_render=False` 是 `validate_spec(allow_published_legacy=True)` 那个全仓离线盘点口径：
    **不问「发没发过」**——封面复用④整道跳过。它读发布账本和 `pushed.json`，而一次推送
    落账就能改它的判词（一条还没发的 spec 撞上刚发出去的同一张图）：全库扫描读它，
    auto-push 那个账本提交在 main 上跑 CI 就红——和 `reel_facts.time_sensitive_gate`
    的 `at_render` 是同一个理由。④ 在全库那一层由 `tests/test_reel_asset_gates.py` 自己兜。
    """
    hard: list[str] = []
    soft: list[str] = []
    duration = duration_problem(spec)
    if duration:
        hard.append(duration)
    stats = stats_card_problem(spec)
    if stats:
        hard.append(stats)
    hard += image_problems(spec)
    reuse = cover_reuse_finding(spec) if at_render else None
    judged = numeral_display_problems(spec)
    if reuse and reuse[1]:
        judged = [reuse[0]] + judged
    elif reuse:
        soft.append("（跨栏目，只报）" + reuse[0])
    (soft if _auto(spec) else hard).extend(judged)
    return hard, soft
