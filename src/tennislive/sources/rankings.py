"""ATP/WTA 单打世界排名。

⚠️ **2026-08-25 整条重写，因为它已经全线取不到，而且没人看得见。**

原来走 ESPN（`site.api.espn.com/.../rankings`）——**runner 和沙箱都 403**
（三次独立观察）。于是每个球员的 `Player.rank` 都是 `None`，而
`render/rating.py` 的 `match_score()` 里 `top_rank<=10` / `<=30` / 爆冷判定
（`w.rank - l.rank >= 30`）全靠它：**自动选题一直在没有排名这一维的情况下
打分**。排名又是 CLAUDE.md 选题优先级里②档（世界前 20）唯一的判据。

⚠️⚠️ **而换源只修了一半——第二个断点在名字上。** 当天量的：一份真实
digest 里 348 名球员，**251 名（72%）的名字是 flashscore 的 `Gauff C.` 形状**，
ATP 那半边更是 **127/128 全是缩写**。而榜单给的是全名，`norm_name("gauff c.")`
永远匹配不上 `norm_name("coco gauff")`。**只换源的话，ATP 的 rank 照样全是
None，而它看起来完全像修好了**——又一次「兜底出事的时候不吭声」。

所以现在是两件事一起做：**能取到的源** ＋ **认得出缩写的匹配**。

源（都实测过，每条都带榜单日期，排名是快照不是常量）：

    WTA  api.wtatennis.com/tennis/players/ranked   ← 官方，带 firstName/lastName
         ⚠️ 参数少一个就 400：`metric=SINGLES` 和空的 `name=` 都不能省
    ATP  tennisexplorer.com/ranking/atp-men/       ← 官方那条 atptour.com 恒 403
         ⚠️ 姓从 **URL slug** 取，不从文本里猜词序：文本是「姓… 名」，而
         「Cerundolo Juan Manuel」按「最后一个词是名」会切成「Manuel」。
         slug 推出来的姓再拿「文本以它开头」自证，150 条里 149 条中。
    WTA 兜底  tennisexplorer.com/ranking/wta-women/（官方接口万一也倒了）
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from .base import SourceError, make_session

logger = logging.getLogger(__name__)

WTA_API = ("https://api.wtatennis.com/tennis/players/ranked"
           "?page={page}&pageSize={size}&type=rankSingles&sort=asc"
           "&name=&metric=SINGLES")
TE_URL = "https://www.tennisexplorer.com/ranking/{board}/"
# 取到 300 名够用：`match_score` 最深只看到 30，爆冷判定要 30 名的差距。
# 再深就是给 tennisexplorer 多打几次请求，换不回任何判断力。
DEPTH = 300
# tennisexplorer 一页 50 条；WTA 官方一页最多 100。
TE_PAGE = 50
WTA_PAGE = 100


@dataclass
class RankEntry:
    rank: int
    name: str
    previous: int | None = None
    points: float | None = None
    trend: str | None = None       # "+2" / "-1" / "-"
    player_id: str | None = None
    # ⚠️ 结构化的姓/名，**匹配缩写靠它**。两个源的词序是反的（WTA 官方给
    # 「名 姓」，tennisexplorer 给「姓 名」），所以在解析那一步就拆开，
    # 不留给下游去猜——猜词序在「Auger Aliassime Felix」上必错。
    surname: str = ""
    given: str = ""

    @property
    def move(self) -> int:
        """排名变化：正数为上升。`render/cards.py` 和 `webcards.py` 画箭头用。

        ⚠️ **换源之后 `previous` 恒为 None，所以这里恒为 0（不画箭头）。**
        两个新源都给不出上一期名次：WTA 官方有个 `movement` 字段，但它的正负
        口径没有文档——而这个仓库为「没有文档的枚举码宁可交叉验证也别信数字
        表面顺序」栽过（`Winner` 那次按 1/2 猜，把退赛场次的赢家全判反了）。
        猜错的箭头和对的长得一模一样，所以宁可不画。真要它就另拉一期历史榜单
        自己比，那是另一件事。
        """
        if self.previous is None or self.previous <= 0:
            return 0
        return self.previous - self.rank


@dataclass
class Rankings:
    atp: list[RankEntry] = field(default_factory=list)
    wta: list[RankEntry] = field(default_factory=list)
    # 榜单日期。排名是快照不是常量——写进 spec 之前要知道是哪一期的。
    atp_at: str | None = None
    wta_at: str | None = None

    @property
    def is_empty(self) -> bool:
        return not (self.atp or self.wta)


def norm_name(name: str) -> str:
    """匹配键：小写 + 去重音 + 连字符当空格 + 归一空白。

    ⚠️ 连字符必须归一成空格：tennisexplorer 的 slug 给出「carreno busta」，
    而它的文本写「Carreno-Busta」——150 条抽样里唯一那条没自证成功的就是它。
    """
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = folded.replace("-", " ").replace("'", " ")
    return " ".join(folded.strip().lower().split())


def abbrev_key(name: str) -> str | None:
    """把 flashscore 的 `Gauff C.` / `Wang Xiy.` / `Liang E. S.` 归一成匹配键。

    形状是「姓… 名的缩写.」——**结尾带点的那几个词是名**，前面全是姓。
    不带点就不是缩写形状，返回 None（那是全名，走 `norm_name` 那条路）。

    ⚠️ 缩写不一定只有一个字母：同名同姓要区分时 flashscore 会写
    `Wang Xin.` / `Wang Xiy.`（王欣瑜 / 王曦雨）——按「取首字母」处理会把
    这两个人合成一个，而**把排名安到错的人头上比留空糟得多**。
    """
    raw = [p for p in name.replace(".", ". ").split() if p.strip()]
    tail = []
    while raw and raw[-1].endswith("."):
        tail.insert(0, raw.pop())
    if not tail or not raw:
        return None
    surname = norm_name(" ".join(raw))
    given = " ".join(norm_name(t.rstrip(".")) for t in tail).strip()
    if not surname or not given:
        return None
    return f"{surname} {given}"


def _entry_keys(entry: RankEntry) -> list[str]:
    """一条榜单给出的全部匹配键：全名、反序全名、以及各档缩写。"""
    keys: list[str] = []
    full = norm_name(entry.name)
    if full:
        keys.append(full)
    sur = norm_name(getattr(entry, "surname", "") or "")
    giv = norm_name(getattr(entry, "given", "") or "")
    if not (sur and giv) and full:
        # ⚠️ **没有结构化姓名时要退回老行为**：ESPN 时代只有一个全名字符串，
        # `rank_map` 靠「反转词序」兼容「姓 名」和「名 姓」两种写法，而
        # `tools/assemble_spec.py` 的测试至今喂的就是这种最小形状。
        # 去掉这一支等于把一批调用方静默打哑——它们不会报错，只会查不到。
        words = full.split()
        if 2 <= len(words) <= 3:
            keys.append(" ".join(reversed(words)))
        # 猜一个「最后一个词是姓」的口径去生成缩写键。猜错了也不会给出错答案：
        # 撞键的在 `rank_map` 里一律删掉，只会少一个键，不会多一个错的。
        if len(words) >= 2:
            sur, giv = words[-1], " ".join(words[:-1])
    if sur and giv:
        keys.append(f"{giv} {sur}")
        keys.append(f"{sur} {giv}")
        words = giv.split()
        # ① 名的前 1~3 个字母：盖住 `Gauff C.` / `Wang Xin.` / `Wang Xiy.`
        for n in (1, 2, 3):
            if len(words[0]) >= n:
                keys.append(f"{sur} {words[0][:n]}")
        # ② 每个名各取首字母：盖住 `Liang E. S.`（名是「En Shuo」）
        if len(words) > 1:
            keys.append(f"{sur} " + " ".join(w[0] for w in words))
    return keys


def rank_map(entries: list[RankEntry] | Rankings) -> dict[str, int]:
    """姓名 → 排名 的查找表，喂给 `digest.apply_rankings`。

    ⚠️ **撞键的一律删掉，不是「先来的赢」。** `Wang X.` 可能是王欣瑜也可能是
    王曦雨；`setdefault` 会静静挑排名靠前的那个，而那正是 CLAUDE.md 里
    「同一站两个中国选手都姓 Wang」栽过的坑——**把排名安到错的人头上，
    在产物上和安对了长得一模一样**。留空至少是诚实的。
    """
    if isinstance(entries, Rankings):
        entries = entries.atp + entries.wta
    hits: dict[str, set[int]] = {}
    for entry in entries:
        for key in _entry_keys(entry):
            hits.setdefault(key, set()).add(entry.rank)
    return {k: next(iter(v)) for k, v in hits.items() if len(v) == 1}


# ── 取数 ────────────────────────────────────────────────────────────────

def _fetch_wta(session, timeout: int) -> tuple[list[RankEntry], str | None]:
    out: list[RankEntry] = []
    at: str | None = None
    for page in range(max(1, DEPTH // WTA_PAGE)):
        resp = session.get(WTA_API.format(page=page, size=WTA_PAGE), timeout=timeout)
        if resp.status_code != 200:
            raise SourceError(f"HTTP {resp.status_code}")
        rows = resp.json()
        if not rows:
            break
        for row in rows:
            p = row.get("player") or {}
            name = p.get("fullName") or ""
            if not name or not row.get("ranking"):
                continue
            at = at or row.get("rankedAt")
            out.append(RankEntry(
                rank=int(row["ranking"]), name=name,
                points=row.get("points"),
                player_id=str(p.get("id") or "") or None,
                surname=p.get("lastName") or "", given=p.get("firstName") or ""))
    return out, at


_TE_ROW = re.compile(
    r'<td class="rank first"[^>]*>\s*(\d+)\.?\s*</td>.*?'
    r'<a href="/player/([^"]*?)/?">([^<]+)</a>', re.S)
_TE_HASH = re.compile(r"^[0-9a-f]{5}$")
_TE_DATE = re.compile(r"(\d{1,2}\.\d{1,2}\.\d{4})")


def _te_split(slug: str, text: str) -> tuple[str, str]:
    """从 slug 推姓、从文本减出名。**推完要自证**：文本必须以这个姓开头。

    自证不过就退回「最后一个词是名」——那条对多数人成立，只在
    「Cerundolo Juan Manuel」这类两段名上会切错，比整条丢掉强。
    """
    parts = [p for p in slug.split("-") if p]
    if len(parts) > 1 and _TE_HASH.fullmatch(parts[-1]):
        parts = parts[:-1]
    surname = norm_name(" ".join(parts))
    whole = norm_name(text)
    if surname and whole.startswith(surname):
        return surname, whole[len(surname):].strip()
    words = whole.split()
    return (" ".join(words[:-1]), words[-1]) if len(words) > 1 else (whole, "")


def _fetch_te(session, board: str, timeout: int) -> tuple[list[RankEntry], str | None]:
    out: list[RankEntry] = []
    at: str | None = None
    for page in range(1, max(1, DEPTH // TE_PAGE) + 1):
        url = TE_URL.format(board=board) + ("" if page == 1 else f"?page={page}")
        resp = session.get(url, timeout=timeout)
        if resp.status_code != 200:
            raise SourceError(f"HTTP {resp.status_code}")
        rows = _TE_ROW.findall(resp.text)
        if not rows:
            # ⚠️ 抠不出行**不等于**「榜单是空的」——多半是版式变了。出声，
            # 别让它退化成一份安静的空榜单（那和 403 长得一模一样）。
            raise SourceError(f"{board} 第 {page} 页一行都没抠出来，版式可能变了")
        if at is None:
            m = _TE_DATE.search(resp.text)
            at = m.group(1) if m else None
        for rank, slug, text in rows:
            surname, given = _te_split(slug, text)
            out.append(RankEntry(rank=int(rank), name=text.strip(),
                                 surname=surname, given=given))
    return out, at


def fetch_rankings(timeout: int = 30) -> Rankings:
    """取两个巡回赛的单打排名；一边失败不拖累另一边。

    ⚠️ 排名是 enrichment：一份残缺的榜单**永远不许**挡住内容包。
    """
    session = make_session()
    result = Rankings()

    try:
        result.wta, result.wta_at = _fetch_wta(session, timeout)
        logger.info("WTA 排名 %d 条（%s，官方接口）", len(result.wta), result.wta_at)
    except Exception as exc:  # noqa: BLE001
        logger.warning("WTA 官方排名抓取失败: %s，退回 tennisexplorer", exc)
        try:
            result.wta, result.wta_at = _fetch_te(session, "wta-women", timeout)
            logger.info("WTA 排名 %d 条（%s，tennisexplorer 兜底）",
                        len(result.wta), result.wta_at)
        except Exception as exc2:  # noqa: BLE001
            logger.warning("WTA 排名两条路都失败: %s", exc2)

    try:
        result.atp, result.atp_at = _fetch_te(session, "atp-men", timeout)
        logger.info("ATP 排名 %d 条（%s，tennisexplorer）",
                    len(result.atp), result.atp_at)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ATP 排名抓取失败: %s", exc)
    return result
