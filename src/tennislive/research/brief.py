"""**一份简报，一条推送。**

在这之前，场外新闻这条线一天发**两条**微信，而且两条都读不出内容：

| 原来 | 里面是什么 | 毛病 |
|---|---|---|
| 「场外网球快讯候选」 | 8 条**英文标题** + 链接 | 全英文；想知道发生了什么得逐条点开 |
| 「今日选题候选」 | 撞上人工角度表的簇；撞不上就空 | 2026-08-02 实测 **0 个**，正文只剩一栏中文热词 |

两条合起来的信息量，等于一份英文标题列表。而**热度本身是有的**——同一天
中文平台上「郑钦文资格赛出局」58 万热度，英文那边 35 条官方新闻聚出 4 个簇，
只是全都停在标题层，一条正文都没读过。

所以这条线现在做三件原来没做的事：

1. **合成一条**。同一天的东西没有理由发两遍——判据是「读者要不要在两条
   消息之间自己做拼接」，而他不该做。
2. **英文一律带中译**。深挖的给中文标题 + 中文要点，没挖成的（读不到正文、
   或者显式 `--deep N` 收了口）至少给中译标题；原标题留在下面一行，
   因为核实要用它。
3. **深挖到正文**。热点把原文抓下来（`research/article.py`），让模型出
   **中文要点 + 为什么值得做 + 可做的角度**——「看不到具体内容」说的就是
   这一步原来根本不存在。**默认全挖**（`--deep 0`），不按名次砍。

三条硬约定，每条都是仓库里已经栽过的坑换了件衣服：

- ⚠️ **译名不交给模型判断**。先扫出这批标题里认识的人名赛事名，把译法
  当硬约束塞进 prompt（`research/glossary.py`）。不然 Rybakina 会变成
  「里巴金娜」，而我们自己的稿子里写着**莱巴金娜**。
- ⚠️ **每一层退化都要出声**。没配 token、抓不到正文、模型返回不合法，
  三种都不许静静地退回标题列表——`Brief.notes` 逐条记下来，推送底部
  照实印出来。这个仓库里「兜底出事的时候不吭声」已经栽过太多次。
- ⚠️ **不补事实**。要点只许来自抓到的正文；一条正文都没读到的热点
  **不进深挖区**，退到标题列表里去，并注明为什么。宁可少给一条，
  也别给一条编出来的。

⚠️ **2026-10-12 模型通道整体摘除**（账号所有者：「都不留了」）。本模块只保留
聚类、热度、常青线匹配与原文抓取记录；中译与要点提炼不再发生，产物 notes
里会如实写明。下面三条里涉及模型的部分是当时的设计史，不再是现行行为。
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from .article import fetch_article, readable_url
from .topic_radar import (
    Angle,
    Heat,
    cluster_headlines,
    match_angle,
    measure_heat,
    published_topics,
)

logger = logging.getLogger(__name__)

# 深挖几条。**0 = 全部**，这是默认——账号所有者 2026-08-05：「不要限制只有一条」。
#
# 第一版是 5（按「微信一屏能扫完」定的），可那是**版面判断替编辑判断做了决定**：
# 排第 6 的热点没被深挖，不是因为它不值得，只是因为它排第 6。而真正该决定
# 「挖不挖」的东西已经有了——聚不成簇的进不来，读不到正文的自己会退回标题层。
#
# 想收就 `--deep N`，仍然按热度取前 N 条。
DEFAULT_DEEP = 0
# 一条热点最多读几篇原文。同一件事读两三家就够交叉印证，读满一簇只是把
# 同样的话读五遍，还要多花几次抓取。
MAX_READS_PER_STORY = 3

# ---------------------------------------------------------------------------
# 去噪：官方站的导航页会混进新闻 feed
# ---------------------------------------------------------------------------
# 2026-08-02 那天 8 条候选里有 3 条是这个：
#     What is the Washington schedule?
#     What is the Montreal schedule?
#     What were the Washington tennis results?
# 全是 ATP 官网为搜索引擎做的常青导航页，天天在，且**永远不是新闻**。
#
# ⚠️ **判据宁可窄，不可宽**（本仓库同一天犯过四次）。只认这一个形状：
# 疑问词开头 **且** 以问号收尾 **且** 句中带一个导航名词。少任何一条都
# 不拦——「How Sinner beat Alcaraz」没有问号，是真报道，必须留住。
_NAV_QUESTION = re.compile(
    r"^\s*(what|who|when|where|how|which)\b.*\b("
    r"schedule|schedules|draw|draws|results|seeds|prize\s*money|entry\s*list|"
    r"order\s+of\s+play|watch|stream|live\s*scores|tv\s*channel"
    r")\b.*\?\s*$",
    re.I,
)


def drop_navigation(signals: Sequence[dict]) -> tuple[list[dict], list[dict]]:
    """把官方站的常青导航页从新闻里摘出来。

    返回 `(留下的, 摘掉的)`——**两个都要返回**。只返回留下的那份，
    「今天没有导航页」和「正则写错把新闻全摘了」就长得一模一样，
    而这正是仓库里「检查工具要把不合格的也列出来」说的事。
    """
    kept: list[dict] = []
    dropped: list[dict] = []
    for sig in signals:
        title = str(sig.get("title") or "")
        (dropped if _NAV_QUESTION.match(title) else kept).append(sig)
    return kept, dropped


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Read:
    """读过的一篇原文。"""

    title: str
    source: str
    url: str
    ok: bool
    note: str


@dataclass
class Story:
    """一条热点。深挖过的带 `points`，没深挖的只有译名。"""

    headlines: list[dict]
    heat: Heat
    title_zh: str = ""
    points: tuple[str, ...] = ()
    why: str = ""
    angle: str = ""
    reads: list[Read] = field(default_factory=list)
    note: str = ""
    # 撞上人工角度表的那一条（`topic_radar.ANGLES`）。**这是这份简报里唯一
    # 不是机器产的东西**：每条角度背后都有一份能翻的规则书或史料。
    # ⚠️ 它是**深挖的输入**，不只是产物里并排的另一栏——`deepen()` 会把它喂进
    # system prompt（`known_angle_hint`），模型写 `angle` 时顺着它展开。
    # 两栏仍然都留着、标签分开写：一栏是人写的规则，一栏是接到今天这条新闻上
    # 的具体说法，别混成一句。
    known: Angle | None = None
    known_done_on: str = ""     # 这条角度以前做过没有，做过就填发布日期

    @property
    def deep(self) -> bool:
        return bool(self.points)

    @property
    def sources(self) -> list[str]:
        return sorted({str(h.get("source") or "") for h in self.headlines if h.get("source")})

    def as_dict(self) -> dict:
        return {
            "title_zh": self.title_zh,
            "deep": self.deep,
            "points": list(self.points),
            "why": self.why,
            "angle": self.angle,
            "note": self.note,
            "known_angle": (
                {
                    "slug": self.known.slug,
                    "label": self.known.label,
                    "evergreen": self.known.evergreen,
                    "source": self.known.source,
                    "question": self.known.question,
                    "done_on": self.known_done_on,
                }
                if self.known
                else None
            ),
            "sources": self.sources,
            "heat": self.heat.as_dict(),
            "headlines": [
                {
                    "title": str(h.get("title") or ""),
                    "source": str(h.get("source") or ""),
                    "url": str(h.get("url") or ""),
                }
                for h in self.headlines
            ],
            "reads": [
                {"url": r.url, "source": r.source, "ok": r.ok, "note": r.note}
                for r in self.reads
            ],
        }


@dataclass
class Brief:
    """今天这一份简报。"""

    date: str
    stories: list[Story] = field(default_factory=list)
    zh_hot: list[dict] = field(default_factory=list)
    zh_scanned: int = 0
    source_status: dict = field(default_factory=dict)
    news_count: int = 0
    dropped_nav: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def deep_stories(self) -> list[Story]:
        return [s for s in self.stories if s.deep]

    @property
    def brief_stories(self) -> list[Story]:
        return [s for s in self.stories if not s.deep]

    def as_dict(self) -> dict:
        return {
            "date": self.date,
            "news_count": self.news_count,
            "zh_scanned": self.zh_scanned,
            "source_status": self.source_status,
            # 摘掉的导航页要留在产物里：正则写宽了会把真新闻摘掉，
            # 而那种错**只有把摘掉的列出来**才看得见。
            "dropped_nav": self.dropped_nav,
            "notes": self.notes,
            "deep": len(self.deep_stories),
            "count": len(self.stories),
            "stories": [s.as_dict() for s in self.stories],
            "zh_hot": self.zh_hot,
        }


# ---------------------------------------------------------------------------
# 深挖
# ---------------------------------------------------------------------------
def deepen(
    story: Story,
    *,
    max_reads: int = MAX_READS_PER_STORY,
    fetch=None,
) -> Story:
    """抓正文并记录读到了哪几篇。**读不到正文就只列标题**，并写明原因。

    ⚠️ 要点提炼原来在这一步调模型（`Chat.ask`）——2026-10-12 模型通道整体
    摘除后，这一步只做抓取与记录：读到了正文也在 note 里说清「提炼已移除」，
    不许假装深挖过。"""
    reader = fetch or fetch_article
    bodies: list[str] = []
    # **先挑读得到的那几条**。Google News 的包装页返回 200、解出 0 段，
    # 和「这家有付费墙」长得一模一样——不先筛掉的话，一簇里前三条正好都是
    # 包装页时，这条热点就白白丢了深挖，而原因还会被记成「抓取失败」。
    readable = [h for h in story.headlines if readable_url(str(h.get("url") or ""))]
    if not readable:
        story.note = (
            "这一簇只有 Google News 的包装链接，读不到正文"
            "（ATP/WTA 官网没有能用的 RSS，见 research/newsfeeds.py）"
        )
        return story
    for head in readable[:max_reads]:
        url = str(head.get("url") or "")
        source = str(head.get("source") or "")
        title = str(head.get("title") or "")
        text, note = reader(url)
        story.reads.append(Read(title=title, source=source, url=url, ok=bool(text), note=note))
        if text:
            bodies.append(f"【{source}】{title}\n{text}")
    if not bodies:
        # 一篇都没读到：退回标题层，但**要说出每一条卡在哪**——
        # 「抓不到」和「这条本来就没内容」不能长得一样。
        why = "；".join(f"{r.source} {r.note}" for r in story.reads) or "没有可读的链接"
        story.note = f"没读到正文，只列标题（{why}）"
        return story
    read_ok = sum(1 for r in story.reads if r.ok)
    story.note = f"读了 {read_ok} 篇原文；要点提炼已随模型通道移除，只列标题"
    return story


def build_brief(
    date_iso: str,
    *,
    news: Sequence[dict],
    trend_signals: Sequence[dict] = (),
    zh_signals: Sequence[dict] = (),
    zh_scanned: int = 0,
    source_status: dict | None = None,
    prev_slugs: Sequence[str] = (),
    deep: int = DEFAULT_DEEP,
    limit: int = 12,
    min_sources: int = 2,
    fetch=None,
) -> Brief:
    """今天的信号 → 一份简报。

    顺序是**先排热度再深挖**：抓正文要花时间，只花在
    排在前面的那几条上。深挖失败的那条不会顶掉后面一条——它退到标题
    列表里，位置不变，因为热度排序和读没读到正文是两件事。
    """
    brief = Brief(date=date_iso, source_status=dict(source_status or {}), zh_scanned=zh_scanned)
    brief.zh_hot = [dict(h) for h in zh_signals]

    kept, dropped = drop_navigation(news)
    brief.news_count = len(kept)
    brief.dropped_nav = [str(d.get("title") or "") for d in dropped]

    clusters = cluster_headlines(list(kept), min_sources=min_sources)
    if not clusters:
        # 空产要自证：分清「今天没新闻」和「有新闻但没聚成簇」。
        brief.notes.append(
            f"{len(kept)} 条新闻没聚出任何热点簇"
            f"（要 {min_sources} 家报同一件事才算一簇）"
            if kept
            else "今天一条新闻都没抓到——先看 source_status 那几行"
        )

    done = published_topics()
    stories: list[Story] = []
    for group in clusters:
        known = match_angle(group)
        heat = measure_heat(
            group,
            trend_signals=list(trend_signals),
            zh_signals=list(zh_signals),
            previous_slugs=list(prev_slugs),
            slug=known.slug if known else "",
        )
        stories.append(
            Story(
                headlines=list(group),
                heat=heat,
                known=known,
                known_done_on=done.get(known.slug, "") if known else "",
            )
        )
    stories.sort(key=lambda s: -s.heat.score)
    stories = stories[:limit]

    # 模型通道已于 2026-10-12 整体摘除（账号所有者：「都不留了」）：
    # 这份简报只有标题、热度和常青线，没有中译也没有要点——写进产物，
    # 别让读到的人以为是今天新闻少。
    brief.notes.append(
        "模型通道已移除：这份简报只有英文标题、热度和常青线，"
        "没有中译也没有要点。"
    )

    # `deep <= 0` = 全部深挖（默认）。切片写成 `stories[:0]` 会一条都不挖，
    # 而那和「今天没有热点」长得一模一样——所以这儿必须显式分支。
    targets = stories if deep <= 0 else stories[:deep]
    for story in targets:
        deepen(story, fetch=fetch)

    # 标题中译原来在这一步走模型——已随模型通道移除，标题保持英文原样。
    if any(not s.deep for s in stories):
        brief.notes.append("标题中译已随模型通道移除，标题保持英文原样")

    brief.stories = stories
    return brief
