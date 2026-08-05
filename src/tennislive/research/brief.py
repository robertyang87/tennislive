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

import requests

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

# 返回形状交给 API 保证，不靠 prompt 里写「只返回 JSON」再自己 try/except。
# 结构化输出在 Opus 5 上是支持的，省掉一整类「模型多说了一句话导致解析失败」。
# ⚠️ DeepSeek 那条路**保证不了形状**，所以它另有一套：schema 仍然是这两份，
# 只是渲成一段「形状必须长这样」的提示塞进 prompt（`json_shape_hint`）——
# **一份 schema 两处用，别手写第二份**（「一个数写两处必分叉」）。
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
# 模型层：两条通道，跑了哪条要说出来
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Provider:
    """一条模型通道。`schema_enforced` 决定形状靠谁保证。"""

    name: str
    env: str            # 密钥的环境变量名
    default_model: str
    schema_enforced: bool
    why: str            # 打进日志用的一句话，说清这条路凭什么


# **DeepSeek 排在前面，因为账号所有者手上是这个**（2026-08-05：
# 「我没有这个〔ANTHROPIC_API_KEY〕，deepseek 的可以用么」）。两个都配了
# 就走 DeepSeek，要反过来用 `TENNISLIVE_BRIEF_PROVIDER=anthropic`。
PROVIDERS: dict[str, Provider] = {
    "deepseek": Provider(
        name="deepseek",
        env="DEEPSEEK_API_KEY",
        default_model="deepseek-v4-pro",
        schema_enforced=False,
        why="OpenAI 格式端点 + json_object 模式；形状靠 prompt 里那段 schema 例子",
    ),
    "anthropic": Provider(
        name="anthropic",
        env="ANTHROPIC_API_KEY",
        default_model="claude-opus-5",
        schema_enforced=True,
        why="官方 SDK，形状由 output_config.format 的 json_schema 保证",
    ),
}

# 两个都没配时说给人听的那句。**列全两个**——只报一个，另一个就等于不存在。
KEY_HINT = "DEEPSEEK_API_KEY 或 ANTHROPIC_API_KEY"

# ⚠️ **不走 DeepSeek 的 Anthropic 兼容端点**（`https://api.deepseek.com/anthropic`），
# 哪怕那样能让两条路共用一个 SDK、改动最小。官方文档写明了两件事，**两件都是
# 静默的**：
#
#   · `output_config` **只支持 `effort`**——也就是 `format` 那半截（json_schema）
#     会被收下然后忽略。schema 保证凭空消失，而调用方一个字都收不到
#   · 传一个它不认识的模型名，后端**自动映射成 `deepseek-v4-flash`**——
#     模型名写错不报错，只是悄悄换一个模型跑完
#
# 两条都是这个仓库里「兜底出事的时候不吭声」的标准形状，而第一条正好废掉
# 这条线唯一的形状保证。OpenAI 格式那条路的 `response_format: json_object`
# 是文档明写支持的（「guarantees the message the model generates is valid JSON」），
# 所以走它——而且它**一个新依赖都不用装**，`requests` 本来就是主依赖。
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

# 一次请求最多等多久。**这个数是按上界算的**：深挖默认全挖，`limit=12` 条
# 热点各一次调用，加一次标题中译，最坏 13 次；工作流 `timeout-minutes: 20`，
# 13 × 60s = 13 分钟，还留得下 checkout 和装依赖。
#
# 实测远没那么贵（2026-08-05 run 30982231886，`deepseek-v4-pro` 关掉思考）：
# **「生成今日简报」整步 80 秒**，里面还包着 Google News 查询、四条 RSS、
# 中文热搜和二十来次抓正文，9 次模型调用只占其中一小截。
#
# ⚠️ **别按那 80 秒往下调**：60 秒是「挂死了」的闸，不是典型耗时的余量。
# 「把慢误判成挂死，重试就从救场变成三倍的浪费」——这个仓库在 apt 那次栽过。
REQUEST_TIMEOUT = 60


def _pick_provider(env: dict) -> Provider:
    """选一条通道。**选错要报错，不许静静地换一条。**"""
    forced = (env.get("TENNISLIVE_BRIEF_PROVIDER") or "").strip().lower()
    if forced:
        if forced not in PROVIDERS:
            # 拼错了就当场报错。退回另一条通道等于用一个不是他要的模型
            # 跑完整份简报，而日志上和「他本来就想用这条」一模一样。
            raise ValueError(
                f"TENNISLIVE_BRIEF_PROVIDER={forced!r} 不认识，"
                f"只有 {'/'.join(PROVIDERS)}"
            )
        return PROVIDERS[forced]
    for provider in PROVIDERS.values():
        if (env.get(provider.env) or "").strip():
            return provider
    # 一个都没配：仍然要给一个 Provider（`ready` 为假，只用来取名字），
    # 而「没配」这件事由 `KEY_HINT` 把两个名字都说出来。
    return PROVIDERS["deepseek"]


def _skeleton(node: dict):
    """把 JSON Schema 渲成一个「长这样」的例子。

    DeepSeek 的 json_object 模式官方要求两件事：prompt 里出现 json 这个词，
    **并且给一个例子**。例子从 schema 现渲——手写第二份必分叉，而分叉的那天
    模型会照着旧形状回，解析不报错，只是字段对不上。
    """
    kind = node.get("type")
    if kind == "object":
        return {k: _skeleton(v) for k, v in (node.get("properties") or {}).items()}
    if kind == "array":
        return [_skeleton(node.get("items") or {"type": "string"})]
    if kind in ("integer", "number"):
        return 0
    if kind == "boolean":
        return False
    return "字符串"


def json_shape_hint(schema: dict) -> str:
    """给保证不了形状的通道用的那段提示。"""
    return (
        "只输出一个 json 对象，不要写解释，不要用代码块包起来。"
        "形状必须和下面这个例子一模一样，只把值换成真实内容：\n"
        + json.dumps(_skeleton(schema), ensure_ascii=False)
    )


class Chat:
    """翻译和提炼要点这一步。两条通道二选一，见 `PROVIDERS`。

    ⚠️ **没有密钥不抛异常**，`ready` 为假、`ask` 返回 `None`，让调用方退回
    纯标题模式**并出声**。抛的话，一次密钥没配就把整份简报废掉——而简报里
    「几家在报、中文热搜撞上什么、原文链接」这些本来都不需要模型。

    ⚠️ **`max_tokens` 和思考的关系，两条通道都咬过一次。** Opus 5 默认开着
    思考，而 `max_tokens` 卡的是「思考 + 正文」的总和；DeepSeek v4 两个型号
    **同样默认开思考**。Anthropic 那条留足额度（4000），DeepSeek 那条直接
    `thinking: disabled`——翻译和抽取不需要思考，关掉之后 `max_tokens` 才
    只算正文，那个坑就不存在了。
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        client: object | None = None,
        post=None,
        env: dict | None = None,
    ) -> None:
        environ = os.environ if env is None else env
        if provider:
            if provider not in PROVIDERS:
                raise ValueError(f"没有 {provider!r} 这条通道，只有 {'/'.join(PROVIDERS)}")
            self.provider = PROVIDERS[provider]
        elif client is not None:
            # 喂进来的 client 是 Anthropic SDK 那个形状（`.messages.create`），
            # 所以它自己就声明了走哪条路。
            self.provider = PROVIDERS["anthropic"]
        else:
            self.provider = _pick_provider(environ)
        # ⚠️ `api_key=""` 是**显式的「没有密钥」**，不许落回环境变量。
        # 原来写的是 `api_key or environ.get(...)`，于是环境里有密钥时
        # `Chat(api_key="")` 会突然变成 ready——测试在沙箱和 CI 上跑的是
        # 两条路，而两边都绿（本仓库栽过一次，见 conftest 那条 autouse）。
        raw = api_key if api_key is not None else environ.get(self.provider.env, "")
        self.api_key = (raw or "").strip()
        self.model = (
            model
            or (environ.get("TENNISLIVE_BRIEF_MODEL") or "").strip()
            or self.provider.default_model
        )
        self._client = client
        self._post = post

    @property
    def ready(self) -> bool:
        return bool(self.api_key or self._client is not None)

    @property
    def channel(self) -> str:
        """打进日志和推送底部的那一行：**跑的到底是哪条**。

        和 `prepare_image_delivery` 那句「图片通道 pushplus / jsdelivr」
        同一个形状——判据不是「配了什么」，是「走了哪条」。
        """
        return f"{self.provider.name} · {self.model}"

    # -- Anthropic ---------------------------------------------------------
    def _anthropic(self):
        if self._client is None:
            import anthropic  # 延迟导入：没配密钥的那条路不该要求装这个包

            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def _ask_anthropic(self, system, user, *, schema, max_tokens) -> dict | None:
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
        return json.loads(next((b.text for b in response.content if b.type == "text"), ""))

    # -- DeepSeek ----------------------------------------------------------
    def _ask_deepseek(self, system, user, *, schema, max_tokens) -> dict | None:
        send = self._post or requests.post
        response = send(
            DEEPSEEK_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    # 形状保证不了，就把 schema 渲成例子一起发过去。
                    {"role": "system", "content": system + "\n" + json_shape_hint(schema)},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
                # ⚠️ **思考默认是开的**（v4 两个型号都是）。翻译和抽取用不上，
                # 关掉之后 `max_tokens` 只算正文，也省一大截 token。
                "thinking": {"type": "disabled"},
            },
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code >= 400:
            # 把响应体带上：4xx 的原因（密钥错、余额不足、模型名不对）全写在
            # 里面，只报一个状态码等于让下一个人再跑一趟才知道为什么。
            logger.warning(
                "DeepSeek 拒了这次请求：HTTP %s %s",
                response.status_code,
                str(response.text)[:300],
            )
            return None
        payload = response.json()
        choices = payload.get("choices") or [{}]
        text = str((choices[0].get("message") or {}).get("content") or "").strip()
        if not text:
            # 官方文档自己记着这个已知问题（「the API may occasionally return
            # empty content」）。不单独出声的话，它和「模型答不上来」长得一样。
            logger.warning("DeepSeek 返回了空正文（官方已知问题），本次跳过")
            return None
        return json.loads(text)

    # -- 对外 --------------------------------------------------------------
    def ask(
        self,
        system: str,
        user: str,
        *,
        schema: dict,
        max_tokens: int = 4000,
    ) -> dict | None:
        """问一次，拿一个符合 `schema` 的对象。失败返回 None 并打日志，不抛。"""
        if not self.ready:
            return None
        try:
            if self.provider.schema_enforced:
                data = self._ask_anthropic(
                    system, user, schema=schema, max_tokens=max_tokens
                )
            else:
                data = self._ask_deepseek(
                    system, user, schema=schema, max_tokens=max_tokens
                )
            return data if isinstance(data, dict) else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("模型这一步没成：%s: %s", type(exc).__name__, exc)
            return None


# 这两段**只讲内容口径**，一个字都不谈返回格式——格式那半截由 `ask()` 按通道
# 自己接上去（Anthropic 走 schema，DeepSeek 走 `json_shape_hint` 渲出来的例子）。
# 分开写是为了**别在两条通道上各维护一份格式指令**：口径改一次，两条一起改。
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
    "  angle：这条新闻是**哪条规则、机制或先例**的一个实例——"
    "说出那条规则本身（叫什么、怎么算、几次、什么时候失效），"
    "而不是「从这件事看某某现象」这种感想。40 字以内。"
    "⚠️ **这一栏是给编辑看的选题建议，不是发给读者的事实**，"
    "所以规则本身可以用你已有的网球规则知识，不必出现在上面的正文里；"
    "但**不许给这条新闻编造正文里没有的情节**——"
    "规则可以是你的知识，**把规则套在谁身上必须来自正文**。"
    "确实想不出对得上的规则就留空字符串。\n"
    "全部用简体中文。"
)
# ⚠️ **`angle` 那一句的口径 2026-08-05 收紧过一次，别退回去。**
# 原来写的是「一句话给一个可做的选题角度」，第一趟真 run 八条全有，但长这样：
#
#     从德雷珀反复受伤看现代网球高强度对球员身体的消耗
#
# 那是**话题方向**，不是「这条新闻是哪条规则的一个实例」。这条线上真正做成
# 片子的那几个选题（保护排名、特殊豁免、外卡、退赛截止日）之所以立得住，
# 是因为背后**有一本能翻的规则书**——几次、怎么算、什么时候失效。
#
# 所以宁可留空：**空是信号，感想是噪音**。
#
# ⚠️ **而第一版收紧过头了，两条指令互相打架。** 同一段里还写着「只依据给到的
# 正文写，一个原文里没有的事实都不许加」——可「保护排名能用几次」这种规则
# **本来就不在新闻正文里**。模型老实照办，2026-08-05 第二趟真 run（run
# 30985906287）**十条里九条 `angle` 留空**。那不是「今天没有值得做的角度」，
# 是这个字段被这两条指令夹死了；空成这样和字段坏掉长得一模一样。
#
# 分界划在**这一栏给谁看**：`points` 是印给读者的，所以「不补事实」寸步不让；
# `angle` 是给编辑的选题建议，规则知识本来就该调用得上——不许编的是**这条
# 新闻的情节**，不是规则本身。
#
# 判据摆得出来：改之前十条留空九条，改之后应当明显多于一条；而
# `points` 那一栏照旧只许来自抓到的正文（那条有测试钉着）。
#
# ⚠️ 这条**没有测试，是故意的**（和「最硬的那个事实放第 ① 屏」同一个理由）：
# 判断题机械挡不住。硬凑一个「angle 里必须出现『规则』二字」的判据，模型
# 照着凑一句就过了，而那会制造「已经守住了」的错觉，比没有更糟。
#
# ⚠️⚠️ **而放松之后的第三趟 run 才照出真正的毛病：答案早就算出来了，没喂给它。**
# run 30988... 那趟 `angle` 回到 5/10 有内容，判据是过了，可第 1 条长这样：
#
#     德雷珀蒙特利尔站复出落泪伤退
#       常青线（人工角度表匹配到的）：保护排名
#       angle（模型写的）：球员**持外卡参赛**后伤病复发……符合 ATP 外卡规则
#
# 四条 points、四条原标题里**一个「外卡」都没有**——他是直入签表的前世界第四。
# 模型给这条新闻编了个前提，而这正是我保留的那半条明令禁止的。
#
# 更刺眼的是：**对的那条线就在同一个 Story 对象上**（`match_angle` 在
# `build_brief` 第一轮循环里就算完了，排在深挖之前），「因骨挫伤退出温网后
# 首次参赛、近一年排名大幅下滑」正是保护排名的教科书场景。模型没看见它，
# 于是自己联想了一条。
#
# 所以修法不是再调 prompt 的松紧，是 `known_angle_hint()`——**把已经算出来的
# 那条线喂进去**。又一次「排查工具写出来了不等于用过了」，只不过这次没被用上
# 的是这份简报里唯一不是机器产的东西（每条常青线背后都有一本能翻的规则书）。


def known_angle_hint(known: Angle | None) -> str:
    """把匹配到的常青线喂给模型，让 `angle` 顺着它写。

    ⚠️ **这一段必须真的进 system prompt**，不能只是算出来放在 `Story` 上——
    产物里印着「常青线：保护排名」而模型写着外卡，两栏各说各的，看起来
    像「模型有别的想法」，其实是它根本没收到。
    """
    if known is None:
        return ""
    return (
        "\n\n【这条新闻，我们的人工角度表已经撞上一条常青线】\n"
        f"{known.label}：{known.evergreen}\n"
        "angle 那一栏就顺着这条线写：把这条规则和上面正文里的具体情节接起来，"
        "别另找一条。这条线是人写的、背后有一本能翻的规则书，"
        "比你现推的可靠。真觉得它对不上这条新闻，才留空。"
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
        return {}, f"没配 {KEY_HINT}，标题保持英文原样"
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
        story.note = f"没配 {KEY_HINT}，读到了正文但没法提炼要点"
        return story
    glossary = glossary_lines(build_glossary([h.get("title", "") for h in story.headlines]))
    data = chat.ask(
        _DEEP_SYSTEM
        + known_angle_hint(story.known)
        + ("\n" + glossary if glossary else ""),
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

    # **跑了哪条通道要写进产物**，不是「配了什么」。和「图片通道 pushplus /
    # jsdelivr」同一条：一个月后有人问「这份简报的要点是谁写的」，答案要在
    # 当天的产物里，而不是靠回忆当时哪个 secret 配着。
    if talker.ready:
        logger.info("模型通道 %s", talker.channel)
        brief.notes.append(f"模型通道 {talker.channel}")
    else:
        brief.notes.append(
            f"没配 {KEY_HINT}：这份简报只有英文标题和热度，"
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
