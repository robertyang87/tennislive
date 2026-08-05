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
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from .article import fetch_article, readable_url
from .glossary import build_glossary, glossary_lines
from .topic_radar import (
    Angle,
    Heat,
    cluster_headlines,
    match_angle,
    measure_heat,
    published_topics,
)

logger = logging.getLogger(__name__)

# ⚠️ **不要退回 GitHub Models。** 这条线一开始接的是
# `https://models.github.ai/inference`（`video/pipeline.py` 的字幕翻译器至今
# 还在用它），2026-08-05 实测那个端点返回：
#
#     HTTP 410  {"error":{"code":"github_models_retirement_brownout",
#                "message":"GitHub Models is temporarily unavailable
#                as part of a scheduled retirement brownout."}}
#
# 也就是**它正在退役**。接着它等于让「中译」和「要点」这两件事在上线当天
# 就静默失效——而失效的样子是「今天没有要点」，和「今天新闻少」长得一模一样。
DEFAULT_MODEL = "claude-opus-5"

# 返回形状交给 API 保证，不靠 prompt 里写「只返回 JSON」再自己 try/except。
# 结构化输出在 Opus 5 上是支持的，省掉一整类「模型多说了一句话导致解析失败」。
_TRANSLATE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "zh": {"type": "string"}},
                "required": ["id", "zh"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

_DEEP_SCHEMA = {
    "type": "object",
    "properties": {
        "title_zh": {"type": "string"},
        "points": {"type": "array", "items": {"type": "string"}},
        "why": {"type": "string"},
        "angle": {"type": "string"},
    },
    "required": ["title_zh", "points", "why", "angle"],
    "additionalProperties": False,
}

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
# 模型层
# ---------------------------------------------------------------------------
class Chat:
    """翻译和提炼要点这一步，走 Anthropic 官方 SDK。

    ⚠️ **没有密钥不抛异常**，`ready` 为假、`ask` 返回 `None`，让调用方退回
    纯标题模式**并出声**。抛的话，一次密钥没配就把整份简报废掉——而简报里
    「几家在报、中文热搜撞上什么、原文链接」这些本来都不需要模型。

    ⚠️ **`max_tokens` 要留出思考的量。** Opus 5 默认开着思考，而
    `max_tokens` 卡的是「思考 + 正文」的总和；按正文长度卡会在中途截断，
    症状是要点少一条或者最后一句话没写完。
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        client: object | None = None,
    ) -> None:
        self.api_key = (api_key or os.environ.get("ANTHROPIC_API_KEY", "")).strip()
        self.model = model or os.environ.get("TENNISLIVE_BRIEF_MODEL", DEFAULT_MODEL)
        self._client = client

    @property
    def ready(self) -> bool:
        return bool(self.api_key or self._client is not None)

    def _anthropic(self):
        if self._client is None:
            import anthropic  # 延迟导入：没配密钥的那条路不该要求装这个包

            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def ask(
        self,
        system: str,
        user: str,
        *,
        schema: dict,
        max_tokens: int = 4000,
    ) -> dict | None:
        """问一次，拿一个**符合 schema** 的对象。失败返回 None 并打日志，不抛。

        形状由 `output_config.format` 保证，不靠在 prompt 里写「只返回 JSON」
        再自己 try/except——那一路会把「模型多说了一句话」变成一次静默降级。
        """
        if not self.ready:
            return None
        try:
            response = self._anthropic().messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                # 提炼要点是抽取型任务，`low` 在 Opus 5 上足够而且便宜得多。
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": schema},
                },
                messages=[{"role": "user", "content": user}],
            )
            if response.stop_reason == "refusal":
                logger.warning("模型拒绝了这一条，跳过")
                return None
            text = next((b.text for b in response.content if b.type == "text"), "")
            data = json.loads(text)
            return data if isinstance(data, dict) else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("模型这一步没成：%s: %s", type(exc).__name__, exc)
            return None


# 返回形状由 `output_config.format` 的 schema 保证，所以这两段**只讲内容口径**，
# 不再写「只返回 JSON」——那句话在结构化输出下是多余的，而多余的格式指令会占掉
# 本来该用来说清编辑口径的位置。
_TRANSLATE_SYSTEM = (
    "你是中文体育媒体的编辑。把英文网球新闻标题译成简体中文：准确、简短、"
    "像中文标题而不是逐字直译；保留人名、赛事名、比分和数字，"
    "不补充原文没有的事实。每条按输入的 id 对应回去。"
)

_DEEP_SYSTEM = (
    "你是中文网球内容编辑。下面给你同一件事的几篇英文报道正文。"
    "只依据给到的正文写，**一个原文里没有的事实都不许加**；正文里没写的就别写。\n"
    "  title_zh：这条热点的中文标题，20 字以内，说清是谁怎么了；\n"
    "  points：3 到 5 条中文要点，每条 40 字以内，一条一个事实，"
    "有数字就带数字，别写空话；\n"
    "  why：一句话说这件事为什么值得中文读者知道，30 字以内；\n"
    "  angle：一句话给一个可做的选题角度（这条新闻底下压着的那条常青线），"
    "40 字以内；正文不足以支撑任何角度就留空字符串。\n"
    "全部用简体中文。"
)


def translate_titles(
    titles: Sequence[str],
    chat: Chat,
    *,
    batch: int = 25,
) -> tuple[dict[int, str], str]:
    """英文标题 → 中译。返回 `(下标→译文, 说明)`。

    译不出来的那些**不填**，调用方照旧显示原标题——半句机翻比原文更难读。
    说明里写清成了几条，好让「今天全是中文源」和「模型没成」分得开。
    """
    if not titles:
        return {}, "没有要译的标题"
    if not chat.ready:
        return {}, "没配 ANTHROPIC_API_KEY，标题保持英文原样"
    glossary = glossary_lines(build_glossary(list(titles)))
    out: dict[int, str] = {}
    for start in range(0, len(titles), batch):
        chunk = list(enumerate(titles))[start : start + batch]
        payload = [{"id": i, "text": t} for i, t in chunk]
        data = chat.ask(
            _TRANSLATE_SYSTEM + ("\n" + glossary if glossary else ""),
            json.dumps(payload, ensure_ascii=False),
            schema=_TRANSLATE_SCHEMA,
            max_tokens=4000,
        )
        if not data:
            continue
        for row in data.get("items") or []:
            if not isinstance(row, dict):
                continue
            try:
                idx = int(row.get("id"))
            except (TypeError, ValueError):
                continue
            text = " ".join(str(row.get("zh") or "").split())
            if text and 0 <= idx < len(titles):
                out[idx] = text
    if not out:
        return {}, f"{len(titles)} 条标题一条都没译成（模型或网络）"
    return out, f"译成 {len(out)}/{len(titles)} 条"


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
    # 不是机器产的东西**：每条角度背后都有一份能翻的规则书或史料，而模型给的
    # `angle` 是从今天这几篇正文里推的。两个都留着，标签分开写，别混成一句。
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
    chat: Chat,
    *,
    max_reads: int = MAX_READS_PER_STORY,
    fetch=None,
) -> Story:
    """抓正文 → 出中文要点。**读不到正文就不深挖**，并写明原因。"""
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
    if not chat.ready:
        story.note = "没配 ANTHROPIC_API_KEY，读到了正文但没法提炼要点"
        return story
    glossary = glossary_lines(build_glossary([h.get("title", "") for h in story.headlines]))
    data = chat.ask(
        _DEEP_SYSTEM + ("\n" + glossary if glossary else ""),
        "\n\n---\n\n".join(bodies),
        schema=_DEEP_SCHEMA,
        max_tokens=4000,
    )
    if not data:
        story.note = "读到了正文，但模型这一步没成，只列标题"
        return story
    points = tuple(
        " ".join(str(p).split())
        for p in (data.get("points") or [])
        if str(p).strip()
    )[:5]
    if not points:
        story.note = "模型没给出要点，只列标题"
        return story
    story.points = points
    story.title_zh = " ".join(str(data.get("title_zh") or "").split())
    story.why = " ".join(str(data.get("why") or "").split())
    story.angle = " ".join(str(data.get("angle") or "").split())
    read_ok = sum(1 for r in story.reads if r.ok)
    story.note = f"读了 {read_ok} 篇原文"
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
    chat: Chat | None = None,
    fetch=None,
) -> Brief:
    """今天的信号 → 一份简报。

    顺序是**先排热度再深挖**：抓正文和调模型都是要花时间的，只花在
    排在前面的那几条上。深挖失败的那条不会顶掉后面一条——它退到标题
    列表里，位置不变，因为热度排序和读没读到正文是两件事。
    """
    talker = chat or Chat()
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

    if not talker.ready:
        brief.notes.append(
            "没配 ANTHROPIC_API_KEY：这份简报只有英文标题和热度，"
            "没有中译也没有要点。配好之后重跑一次就有了。"
        )

    # `deep <= 0` = 全部深挖（默认）。切片写成 `stories[:0]` 会一条都不挖，
    # 而那和「今天没有热点」长得一模一样——所以这儿必须显式分支。
    targets = stories if deep <= 0 else stories[:deep]
    for story in targets:
        deepen(story, talker, fetch=fetch)

    # 剩下的至少给中译标题——「英文的话要有对应的中文翻译」这条对
    # 整份简报成立，不只是深挖的那几条。深挖失败退下来的也算在内。
    shallow = [s for s in stories if not s.deep]
    if shallow:
        titles = [str(s.headlines[0].get("title") or "") for s in shallow]
        zh_map, note = translate_titles(titles, talker)
        for idx, story in enumerate(shallow):
            if idx in zh_map:
                story.title_zh = zh_map[idx]
        brief.notes.append(f"标题中译：{note}")

    brief.stories = stories
    return brief
