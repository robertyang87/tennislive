"""热点简报这条线的判据（CLAUDE.md：规则要落成测试）。

账号所有者 2026-08-05：「目前推送的内容还有两块，英文媒体一份中文一份，
而且也看不到具体内容……合并成一个做推送，英文的话要有对应的中文翻译，
主要能深入挖掘热点」。

四条要求各自钉住：

| 要求 | 判据 |
|---|---|
| 合并成一个 | `test_一天只发一条推送` + `test_老那两条推送不许回来` |
| 英文要有中译 | `test_没深挖的那些也要给中译标题` |
| 看得到具体内容 | `test_深挖要出中文要点而且只能来自抓到的正文` |
| 深入挖掘 | 同上 + `test_读不到正文就不深挖而且要说清卡在哪` |

外加两条这个仓库的老账：**退化要出声**、**判据宁可窄不可宽**。
"""

import json
from pathlib import Path

import pytest

from tennislive.render.newsbrief import render_brief_html
from tennislive.research.brief import (
    DEEPSEEK_URL,
    _DEEP_SCHEMA,
    _TRANSLATE_SCHEMA,
    KEY_HINT,
    PROVIDERS,
    REQUEST_TIMEOUT,
    Chat,
    build_brief,
    drop_navigation,
    json_shape_hint,
)
from tennislive.research.glossary import build_glossary, glossary_lines


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _workflow(name: str) -> str:
    return (Path(".github/workflows") / name).read_text(encoding="utf-8")


def _yaml_only(text: str) -> str:
    """去掉整行注释再扫。

    工作流的注释正是这个仓库记教训的地方——这份工作流的注释里就写着
    「原来这儿是两步」和那两条老推送的名字。连注释一起扫，「把坑记下来」
    会被判成「又踩了这个坑」。同一个错这个仓库犯过五次。
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def _news(*rows):
    return [
        {"kind": "official-news", "source": s, "title": t, "url": u}
        for s, t, u in rows
    ]


_DRAPER = _news(
    ("ATP Tour", "Draper withdraws from Washington with elbow injury", "https://a/1"),
    ("Sky Sports", "Draper withdraws citing elbow injury before US Open", "https://b/1"),
)


class _Stub(Chat):
    """不联网的模型替身。`reply` 决定它返回什么，`None` 表示这次没成。"""

    def __init__(self, reply=None, *, ready=True):
        super().__init__(api_key="t" if ready else "")
        self._reply = reply
        self.prompts: list[tuple[str, str]] = []

    def ask(self, system, user, **kw):
        if not self.ready:
            return None
        self.prompts.append((system, user))
        if callable(self._reply):
            return self._reply(system, user)
        return self._reply


def _deep_reply(system, user):
    if "title_zh" in system:
        return {
            "title_zh": "德雷珀因肘伤退出华盛顿",
            "points": ["他称伤病是一场完美风暴", "目标是美网复出"],
            "why": "前世界第四的复出时间表",
            "angle": "退赛的截止日和罚则",
        }
    return {"items": [{"id": 0, "zh": "某条中译标题"}]}


def _ok_fetch(url):
    return ("Draper said the injuries were a perfect storm. " * 20, "读到 8 段")


def _dead_fetch(url):
    return ("", "取不到（HTTP 403）")


# ---------------------------------------------------------------------------
# 一、去噪：官网导航页不是新闻
# ---------------------------------------------------------------------------
def test_官网导航页要摘掉而真新闻不许误伤():
    """2026-08-02 那天 8 条候选里 3 条是 ATP 官网的常青导航页。

    ⚠️ **判据宁可窄，不可宽**（这个仓库同一天犯过四次）。下面那张
    「不许误伤」的表比上面那张更重要：扩大化的判据不吭声——它不会告诉你
    「我拦错了」，只会让真新闻一条条消失，而空产看起来和「今天没新闻」
    一模一样。
    """
    nav = [
        "What is the Washington schedule?",
        "What is the Montreal schedule?",
        "What were the Washington tennis results?",
        "Who is playing in the Cincinnati draw?",
        "How to watch the US Open on TV?",
    ]
    # ⚠️ 这张表比上面那张重要，而且**每一条都要各自扛住一个放宽方向**——
    # 第一版六条全是「随便找的真新闻」，把「必须问号结尾」那一条整个删掉
    # 之后**测试照样绿**：那六条要么不以疑问词开头、要么不含导航名词，
    # 一条都没走到那个分支上。**判据自己也要有判据**，见下面的注释。
    real = [
        # ↓ 只有「必须问号结尾」那一条救得了它们：疑问词开头 + 导航名词，
        #   但它们是特写报道，不是导航页
        "How the Cincinnati draw opened up for Alcaraz",
        "What the new prize money means for qualifiers",
        # ↓ 只有「必须疑问词开头」那一条救得了它：是问句 + 导航名词
        "Is the Cincinnati draw the toughest of the year?",
        # ↓ 只有「必须含导航名词」那一条救得了它：疑问词开头的问句
        "What did Draper say about his elbow?",
        # ↓ 普通真新闻，任何一条放宽都不该碰它们
        "Washington schedule shaken up as three seeds withdraw",
        "US Open prize money rises to a record $90 million",
    ]
    kept, dropped = drop_navigation(
        _news(*[("ATP Tour", t, f"https://x/{i}") for i, t in enumerate(nav + real)])
    )
    assert sorted(d["title"] for d in dropped) == sorted(nav)
    assert sorted(k["title"] for k in kept) == sorted(real)


def test_摘掉的导航页要列进产物():
    """只返回「留下的」那份，正则写宽把真新闻摘光会长得和「今天没新闻」一样。

    这就是仓库里「检查工具要把不合格的也列出来」——只在成功时出声的检查，
    没法证明它真的看过。
    """
    brief = build_brief(
        "2026-08-05",
        news=_news(("ATP Tour", "What is the Washington schedule?", "https://a/1")),
        chat=_Stub(ready=False),
    )
    assert brief.dropped_nav == ["What is the Washington schedule?"]
    assert "摘掉 1 条" in render_brief_html(brief)


# ---------------------------------------------------------------------------
# 二、深挖：要点只能来自抓到的正文
# ---------------------------------------------------------------------------
def test_深挖要出中文要点而且只能来自抓到的正文():
    brief = build_brief(
        "2026-08-05", news=_DRAPER, chat=_Stub(_deep_reply), fetch=_ok_fetch, deep=1
    )
    story = brief.stories[0]
    assert story.deep
    assert story.title_zh == "德雷珀因肘伤退出华盛顿"
    assert story.points == ("他称伤病是一场完美风暴", "目标是美网复出")
    assert story.note == "读了 2 篇原文"
    html = render_brief_html(brief)
    assert "他称伤病是一场完美风暴" in html
    assert "前世界第四的复出时间表" in html


def test_喂给模型的是正文不是标题():
    """「深挖」的全部含义就是这一条：真的把原文读进去了。"""
    chat = _Stub(_deep_reply)
    build_brief("2026-08-05", news=_DRAPER, chat=chat, fetch=_ok_fetch, deep=1)
    deep_calls = [u for s, u in chat.prompts if "title_zh" in s]
    assert deep_calls, "根本没走深挖那一步"
    assert "perfect storm" in deep_calls[0], "喂过去的不是抓到的正文"


def test_读不到正文就不深挖而且要说清卡在哪():
    """抓不到和「这条本来就没内容」不许长得一样。

    ⚠️ 退化在这个仓库里出过太多次事，判据钉两头：**不许假装深挖过**
    （points 必须空），**而且要说出每一条卡在哪**（HTTP 码要在 note 里）。
    """
    brief = build_brief(
        "2026-08-05", news=_DRAPER, chat=_Stub(_deep_reply), fetch=_dead_fetch, deep=1
    )
    story = brief.stories[0]
    assert not story.deep and story.points == ()
    assert "没读到正文" in story.note and "HTTP 403" in story.note
    # 推送正文底部也要说，不能只写进 JSON——读微信的人不会去翻 JSON
    assert "没读到正文" in render_brief_html(brief)


def test_模型这一步没成也要出声():
    brief = build_brief(
        "2026-08-05", news=_DRAPER, chat=_Stub(None), fetch=_ok_fetch, deep=1
    )
    story = brief.stories[0]
    assert not story.deep
    assert "模型这一步没成" in story.note


def test_模型没给要点就不算深挖():
    """`points` 空却把 `title_zh` 填上，会渲出一条**有标题没内容**的深挖块。"""
    brief = build_brief(
        "2026-08-05",
        news=_DRAPER,
        chat=_Stub({"title_zh": "标题在", "points": [], "why": "", "angle": ""}),
        fetch=_ok_fetch,
        deep=1,
    )
    assert not brief.stories[0].deep
    assert "没给出要点" in brief.stories[0].note


# ---------------------------------------------------------------------------
# 三、英文一律带中译
# ---------------------------------------------------------------------------
def test_没深挖的那些也要给中译标题():
    """「英文的话要有对应的中文翻译」对**整份简报**成立，不只是深挖那几条。"""
    chat = _Stub(lambda s, u: {"items": [{"id": 0, "zh": "德雷珀退出华盛顿"}]})
    brief = build_brief("2026-08-05", news=_DRAPER, chat=chat, fetch=_dead_fetch, deep=0)
    story = brief.stories[0]
    assert story.title_zh == "德雷珀退出华盛顿"
    html = render_brief_html(brief)
    # 中文在前、英文原标题在后——原标题不是给人读的，是核实用的
    assert html.index("德雷珀退出华盛顿") < html.index("Draper withdraws from Washington")


def test_没配密钥这件事要出声不能默默退回英文():
    """没配密钥的简报没有中译也没有要点，而它看起来和「今天新闻少」一样。

    ⚠️ **两种情形分开验，因为它们由不同的那句话兜着**。第一版只验了「有热点」
    那种，而那时 `translate_titles` 自己也会写一句带密钥名字的 note——
    于是把 `build_brief` 里那句整个拆掉，**测试照样绿**。零热点那天没有标题
    要译，那句就是唯一的出声点，也正是最需要它的那天（什么都没有的简报）。

    ⚠️ **两个密钥名都要报出来**。只说 ANTHROPIC 的话，手上只有 DeepSeek 的人
    读到的是「我要去申请一个 Anthropic 的密钥」——而他其实什么都不缺。
    """
    for name in ("DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY"):
        assert name in KEY_HINT, "两条通道都要在「没配」那句话里报出来"

    with_stories = build_brief("2026-08-05", news=_DRAPER, chat=_Stub(ready=False))
    assert any(KEY_HINT in n for n in with_stories.notes)
    assert KEY_HINT in render_brief_html(with_stories)

    empty = build_brief("2026-08-05", news=[], chat=_Stub(ready=False))
    assert any(KEY_HINT in n for n in empty.notes), (
        "一条热点都没有的那天，没配密钥这件事就没人说了"
    )
    assert KEY_HINT in render_brief_html(empty)


def test_译名表要进prompt不许让模型自己译人名():
    """Rybakina 会被译成「里巴金娜」，而我们自己的稿子里写着**莱巴金娜**。

    仓库里「人名不要手打，先查仓库里的译名表」那条规矩，在机器翻译这儿
    换了个人踩：模型每次的译法还可能不一样。所以译名当硬约束塞进 prompt。
    """
    glossary = build_glossary(["Rybakina eases past Ostapenko in Montreal"])
    assert glossary.get("Elena Rybakina") == "莱巴金娜"
    assert glossary.get("Jelena Ostapenko") == "奥斯塔彭科"
    line = glossary_lines(glossary)
    assert "莱巴金娜" in line and "必须" in line

    chat = _Stub(lambda s, u: {"items": [{"id": 0, "zh": "莱巴金娜横扫奥斯塔彭科"}]})
    build_brief(
        "2026-08-05",
        news=_news(
            ("BBC", "Rybakina eases past Ostapenko in Montreal", "https://c/1"),
            ("ESPN", "Rybakina downs Ostapenko in Montreal opener", "https://d/1"),
        ),
        chat=chat,
        deep=0,
    )
    assert any("莱巴金娜" in s for s, _ in chat.prompts), "译名表没进 prompt"


def test_译名表不许把不相干的人塞进prompt():
    """扫出来的名字要真在这批标题里出现过——塞满一百个名字只是挤上下文。"""
    glossary = build_glossary(["Rybakina eases past Ostapenko in Montreal"])
    assert "Jannik Sinner" not in glossary
    assert len(glossary) <= 40


# ---------------------------------------------------------------------------
# 四、人工角度表没有被丢掉
# ---------------------------------------------------------------------------
def test_人工角度表要跟着热点一起出现():
    """这是简报里**唯一不是机器产的东西**，合并的时候不许顺手丢掉。

    每条角度背后都有一份能翻的规则书或史料；模型给的 `angle` 是从今天这
    几篇正文里推的。两个都留，标签分开写。
    """
    brief = build_brief(
        "2026-08-05", news=_DRAPER, chat=_Stub(_deep_reply), fetch=_ok_fetch, deep=1
    )
    story = brief.stories[0]
    assert story.known is not None and story.known.slug == "withdrawal-deadline"
    html = render_brief_html(brief)
    assert "底下压着的常青线" in html
    assert story.known.question in html
    # 模型推的角度和人工表的角度要分得开
    assert "可做的角度" in html and "核实：" in html


# ---------------------------------------------------------------------------
# 五、空产要自证
# ---------------------------------------------------------------------------
def test_空产要分得清是没热点还是抓取全挂了():
    empty = build_brief("2026-08-05", news=[], chat=_Stub(ready=False))
    assert any("一条新闻都没抓到" in n for n in empty.notes)

    lonely = build_brief(
        "2026-08-05",
        news=_news(("ATP Tour", "Draper withdraws from Washington", "https://a/1")),
        chat=_Stub(ready=False),
    )
    assert any("没聚出任何热点簇" in n for n in lonely.notes)
    # 两句话必须不同——都写「今天没热点」就等于没自证
    assert empty.notes[0] != lonely.notes[0]


# ---------------------------------------------------------------------------
# 六、工作流：合并的全部意义在于只剩一条推送
# ---------------------------------------------------------------------------
def test_一天只发一条推送():
    body = _yaml_only(_workflow("news-brief.yml"))
    # 失败告警那条不算——它发的是「跑挂了」，不是内容
    steps = [s for s in body.split("\n      - name: ") if "pushplus.plus/send" in s]
    content_pushes = [s for s in steps if "failure()" not in s]
    assert len(content_pushes) == 1, (
        f"发内容的推送有 {len(content_pushes)} 步——合并的全部意义就是这里只剩一条"
    )


def test_老那两条推送不许回来():
    """判据钉在**产物名**上，不是步骤名：改个步骤名就绕过去的判据等于没装。"""
    body = _yaml_only(_workflow("news-brief.yml"))
    assert "flash_radar_push.html" not in body
    assert "topic_radar_push.html" not in body
    assert "brief_push.html" in body


def test_简报不许再装Chromium和中文字体():
    """它一张图都不出。原来那一分半是给 flash-radar 的草稿卡装的。"""
    body = _yaml_only(_workflow("news-brief.yml"))
    for heavy in ("playwright install", "fonts-noto-cjk", "webrender"):
        assert heavy not in body, f"简报不渲图，不该装 {heavy}"


def test_停掉的定时不许自己回来():
    """2026-08-02 账号所有者停的是定时；这次改的是内容形态，不是那个决定。"""
    body = _yaml_only(_workflow("news-brief.yml"))
    assert "cron:" not in body, "定时是 2026-08-02 明确停掉的，要恢复得先问"
    assert "workflow_dispatch:" in body, "手动入口不许跟着一起摘掉"


def test_简报要在推送之前提交进仓库():
    """老账：推送正文里的每个链接，指向的文件都必须在推送之前进仓库。

    这条简报的正文是**整段渲在消息里**的，不靠链接；但产物仍要先落库，
    不然「本次推了什么」事后查不到。
    """
    body = _yaml_only(_workflow("news-brief.yml"))
    assert body.index("git commit") < body.index("pushplus.plus/send")


def test_稀疏检出那一格要在生成之前加回来():
    """`sparse-checkout add` 会把 HEAD 上那一版先铺回工作区——排在生成后面
    会拿旧内容盖掉刚生成的。"""
    body = _yaml_only(_workflow("news-brief.yml"))
    assert body.index("git sparse-checkout add") < body.index("tennislive brief")
    assert "git add --sparse" in body, "裸的 git add 在稀疏模式下只警告、退出码 0"


# ---------------------------------------------------------------------------
# 七、真正发出去的那次调用长什么样
# ---------------------------------------------------------------------------
class _FakeMessages:
    """记下 `messages.create` 收到的参数，并按 `reply` 造一个响应。"""

    def __init__(self, reply):
        self._reply = reply
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self._reply, Exception):
            raise self._reply
        return self._reply


class _FakeClient:
    def __init__(self, reply):
        self.messages = _FakeMessages(reply)


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, text, stop_reason="end_turn"):
        self.content = [_Block(text)]
        self.stop_reason = stop_reason


def test_发出去的那次调用要带schema和模型():
    """⚠️ 这条盯的是**真的调用出去的那次**，不是我们自己的封装。

    仓库里「写了不等于跑过」栽过太多次（`_cut_person(source, …)` 那条路
    带着测试合并了，一次都没跑起来过）。沙箱里没有密钥、发不出真请求，
    所以退而求其次：喂一个假 client，把参数形状钉住。
    """
    client = _FakeClient(_Response('{"title_zh": "标题", "points": ["一条"],'
                                   ' "why": "", "angle": ""}'))
    chat = Chat(client=client)
    # 喂进来的 client 是 Anthropic SDK 的形状，它自己就声明了走哪条通道
    assert chat.provider.name == "anthropic"

    out = chat.ask("系统提示", "正文", schema={"type": "object"})

    assert out == {"title_zh": "标题", "points": ["一条"], "why": "", "angle": ""}
    (call,) = client.messages.calls
    assert call["model"] == PROVIDERS["anthropic"].default_model == "claude-opus-5"
    # 形状交给 API 保证，不是靠 prompt 里写「只返回 JSON」再自己兜
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["output_config"]["format"]["schema"] == {"type": "object"}
    # ⚠️ Opus 5 默认开着思考，而 max_tokens 卡的是「思考 + 正文」的总和。
    # 按正文长度卡会在中途截断，症状是要点少一条——不报错。
    assert call["max_tokens"] >= 4000
    # 这几个参数在 Opus 5 上会 400，别让它们混进来
    for banned in ("temperature", "top_p", "top_k"):
        assert banned not in call, f"{banned} 在 Opus 5 上会 400"


# ---------------------------------------------------------------------------
# 七之二、DeepSeek 那条通道
# ---------------------------------------------------------------------------
class _FakeResponse:
    def __init__(self, payload, status=200, text=""):
        self._payload = payload
        self.status_code = status
        self.text = text or json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload


class _FakePost:
    """记下 `requests.post` 收到的参数。"""

    def __init__(self, payload, *, status=200, text=""):
        self._payload = payload
        self._status = status
        self._text = text
        self.calls: list[dict] = []

    def __call__(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return _FakeResponse(self._payload, self._status, self._text)


def _content(text):
    return {"choices": [{"message": {"content": text}}]}


def test_DeepSeek那次调用要带json模式和形状例子而且关掉思考():
    """账号所有者 2026-08-05：「我没有这个〔ANTHROPIC_API_KEY〕，deepseek 的可以用么」。

    ⚠️ **这条通道保证不了形状**，所以官方文档那三条要求缺一不可：
    `response_format` 要设、prompt 里要出现 json 这个词**并且给一个例子**、
    `max_tokens` 要够（不然 JSON 会从中间截断）。三条各自钉一句。
    """
    post = _FakePost(_content('{"title_zh": "标题", "points": ["一条"]}'))
    chat = Chat(provider="deepseek", api_key="k", post=post)
    out = chat.ask("系统提示", "正文", schema=_DEEP_SCHEMA)

    assert out == {"title_zh": "标题", "points": ["一条"]}
    (call,) = post.calls
    assert call["url"] == DEEPSEEK_URL
    assert call["headers"]["Authorization"] == "Bearer k"
    assert call["timeout"] == REQUEST_TIMEOUT

    body = call["json"]
    assert body["model"] == PROVIDERS["deepseek"].default_model
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_tokens"] >= 1000, "给小了 JSON 会从中间截断，而那不报错"
    # ⚠️ **思考默认是开的**（v4 两个型号都是），而 max_tokens 卡的是总和。
    # 翻译和抽取用不上思考，关掉之后 Opus 5 上栽过的那个坑就不存在了。
    assert body["thinking"] == {"type": "disabled"}

    system = body["messages"][0]["content"]
    assert "系统提示" in system, "内容口径那段被形状提示挤掉了"
    assert "json" in system, "DeepSeek 官方要求：prompt 里必须出现 json 这个词"
    assert "title_zh" in system, "官方还要求给一个例子，而例子要从 schema 现渲"


def test_形状例子是从schema现渲的不是手写第二份():
    """一份 schema 两处用。手写第二份必分叉，而分叉那天模型会照旧形状回——
    **解析不报错**，只是字段对不上，退化成「模型没给出要点」。"""
    hint = json_shape_hint(_DEEP_SCHEMA)
    example = json.loads(hint.split("\n")[-1])
    assert sorted(example) == sorted(_DEEP_SCHEMA["properties"]), (
        "例子里的字段要跟着 schema 走，往 schema 里加一个字段它就该跟着出现"
    )
    assert isinstance(example["points"], list), "数组字段要渲成数组"

    nested = json.loads(json_shape_hint(_TRANSLATE_SCHEMA).split("\n")[-1])
    assert nested == {"items": [{"id": 0, "zh": "字符串"}]}, "嵌套的形状也要渲对"


def test_DeepSeek报错和空正文都要出声(caplog):
    """两条降级路径都要返回 None 并说清卡在哪。

    ⚠️ 空正文那条是**官方文档自己记着的已知问题**（「the API may occasionally
    return empty content」）。不单独出声的话，它和「模型答不上来」长得一模一样。

    ⚠️ caplog 收在 WARNING——那两句告警就是 WARNING，收在 ERROR 上根本进不了
    caplog（本仓库栽过一次：坏代码 + 错档位，测试照样绿）。
    """
    refused = Chat(
        provider="deepseek",
        api_key="k",
        post=_FakePost({}, status=402, text='{"error":{"message":"余额不足"}}'),
    )
    with caplog.at_level("WARNING"):
        assert refused.ask("s", "u", schema=_DEEP_SCHEMA) is None
    # 状态码和响应体都要在，只报一个码等于让下一个人再跑一趟才知道为什么
    assert any("402" in r.getMessage() for r in caplog.records)
    assert any("余额不足" in r.getMessage() for r in caplog.records)

    caplog.clear()
    empty = Chat(provider="deepseek", api_key="k", post=_FakePost(_content("")))
    with caplog.at_level("WARNING"):
        assert empty.ask("s", "u", schema=_DEEP_SCHEMA) is None
    assert any("空正文" in r.getMessage() for r in caplog.records)


def test_不许改走DeepSeek的Anthropic兼容端点():
    """看着能让两条路共用一个 SDK，**而它废掉的正好是形状保证**。

    官方文档写明两件事，两件都是静默的：`output_config` 只支持 `effort`
    （`format` 那半截收下就忽略），模型名不认识就自动映射成
    `deepseek-v4-flash`。所以判据钉在 URL 上。

    ⚠️ **扫之前要去掉整行注释**——上面那段教训就写在 `brief.py` 的注释里，
    连注释一起扫会把「把坑记下来」判成「又踩了这个坑」。这个仓库犯过五次。
    """
    source = Path("src/tennislive/research/brief.py").read_text(encoding="utf-8")
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    assert "api.deepseek.com/anthropic" not in code
    assert "/chat/completions" in code


# ---------------------------------------------------------------------------
# 七之三、选哪条通道是显式的，而且要说出来
# ---------------------------------------------------------------------------
def test_选哪条通道由密钥决定而且可以显式指定():
    assert Chat(env={"DEEPSEEK_API_KEY": "d"}).provider.name == "deepseek"
    assert Chat(env={"ANTHROPIC_API_KEY": "a"}).provider.name == "anthropic"

    both = {"DEEPSEEK_API_KEY": "d", "ANTHROPIC_API_KEY": "a"}
    assert Chat(env=both).provider.name == "deepseek", "两个都配走 DeepSeek"
    forced = Chat(env={**both, "TENNISLIVE_BRIEF_PROVIDER": "anthropic"})
    assert forced.provider.name == "anthropic", "显式指定要盖过密钥的顺序"

    assert not Chat(env={}).ready, "一个都没配就不该 ready"


def test_通道名写错要当场报错不许静静换一条():
    """⚠️ 环境里**有一个能用的密钥**，所以静静退回另一条通道完全看不出来——
    日志上和「他本来就想用这条」一模一样，而跑完整份简报的是另一个模型。"""
    with pytest.raises(ValueError, match="deepsek"):
        Chat(env={"TENNISLIVE_BRIEF_PROVIDER": "deepsek", "DEEPSEEK_API_KEY": "d"})


def test_显式给空密钥不许落回环境变量():
    """`Chat(api_key="")` 是显式的「没有密钥」。

    落回环境变量的话，同一条测试在沙箱（有密钥）和 CI（没有）上走的是两条路，
    **而两边都绿**——本仓库为这个专门写过一条 autouse fixture。
    """
    assert not Chat(api_key="", env={"DEEPSEEK_API_KEY": "d"}).ready


def test_跑了哪条通道要写进产物():
    """和「图片通道 pushplus / jsdelivr」同一条：判据是**走了哪条**，
    不是「配了什么」。一个月后有人问「这份简报的要点是谁写的」，
    答案要在当天的产物里。"""
    chat = _Stub(_deep_reply)
    brief = build_brief(
        "2026-08-05", news=_DRAPER, chat=chat, fetch=_ok_fetch, deep=1
    )
    assert f"模型通道 {chat.channel}" in brief.notes
    assert chat.model in chat.channel and chat.provider.name in chat.channel
    assert f"模型通道 {chat.channel}" in render_brief_html(brief)


def test_两个模型密钥都要传进工作流():
    """⚠️ 扫之前先去掉整行注释：新加的那段注释里两个名字都写着，
    连注释一起扫会制造**假绿**——漏传一个照样过。"""
    body = _yaml_only(_workflow("news-brief.yml"))
    for name in ("DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY"):
        assert name + ": ${{ secrets." + name + " }}" in body, f"{name} 没传进去"


def test_模型拒绝或抛异常都不许把整份简报带下去(caplog):
    """两条降级路径都要返回 None 并出声，而不是抛给调用方。

    ⚠️ **拒绝那一支要喂「带内容的拒绝」**。第一版喂的是空 content，
    而空串本来就会在 `json.loads` 那儿抛、被兜住返回 None——于是把
    `stop_reason == "refusal"` 整个拆掉，**测试照样绿**。真正只有这道闸
    拦得住的是「拒绝了但仍带着半截文本」：那半截能解析成合法 JSON，
    不拦就会被当成一条正常要点用上去。

    ⚠️ caplog 收在 WARNING —— 那句告警就是 WARNING，收在 ERROR 上它
    根本进不了 caplog（本仓库栽过一次：坏代码 + 错档位，测试照样绿）。
    """
    partial = _Response('{"title_zh": "半截", "points": ["不该被用上"]}',
                        stop_reason="refusal")
    refused = Chat(client=_FakeClient(partial))
    with caplog.at_level("WARNING"):
        assert refused.ask("s", "u", schema={"type": "object"}) is None
    assert any("拒绝" in r.message for r in caplog.records)

    caplog.clear()
    broke = Chat(client=_FakeClient(RuntimeError("网络挂了")))
    with caplog.at_level("WARNING"):
        assert broke.ask("s", "u", schema={"type": "object"}) is None
    assert any("没成" in r.message for r in caplog.records)


def test_没配密钥就不该去构造SDK客户端():
    """没装 anthropic 的机器上，跑一趟没密钥的简报不许因为 import 就崩。"""
    chat = Chat(api_key="")
    assert not chat.ready
    assert chat.ask("s", "u", schema={"type": "object"}) is None


# ---------------------------------------------------------------------------
# 八、深挖不按名次砍
# ---------------------------------------------------------------------------
_TWO_STORIES = _news(
    ("ATP Tour", "Draper withdraws from Washington with elbow injury", "https://a/1"),
    ("Sky Sports", "Draper withdraws citing elbow injury before US Open", "https://b/1"),
    ("BBC Sport", "Rybakina eases past Ostapenko in Montreal opener", "https://c/1"),
    ("ESPN", "Rybakina downs Ostapenko at the Montreal opener", "https://d/1"),
)


def test_默认全部深挖不按名次砍():
    """账号所有者 2026-08-05：「不要限制只有一条」。

    第一版按 `stories[:5]` 砍，那是**版面判断替编辑判断做了决定**——
    排第 6 的没被深挖，不是因为它不值得，只是因为它排第 6。
    """
    brief = build_brief(
        "2026-08-05", news=_TWO_STORIES, chat=_Stub(_deep_reply), fetch=_ok_fetch
    )
    assert len(brief.stories) == 2, "这批数据本来就该聚出两簇，判据的前提没了"
    assert all(s.deep for s in brief.stories), "默认应该全挖，不该按名次砍"


def test_给了deep就按热度取前几条():
    """收口的能力要留着——`--deep N` 仍然按热度取前 N 条。"""
    brief = build_brief(
        "2026-08-05", news=_TWO_STORIES, chat=_Stub(_deep_reply),
        fetch=_ok_fetch, deep=1,
    )
    assert [s.deep for s in brief.stories] == [True, False]


def test_deep等于0不许被切片吃成一条都不挖():
    """⚠️ `stories[:0]` 是空列表——如果用切片表达「不限」，会一条都不挖，
    而那和「今天没有热点」长得一模一样。所以必须显式分支。"""
    from tennislive.research.brief import DEFAULT_DEEP

    assert DEFAULT_DEEP == 0, "0 是「全部」的哨兵值"
    brief = build_brief(
        "2026-08-05", news=_TWO_STORIES, chat=_Stub(_deep_reply),
        fetch=_ok_fetch, deep=0,
    )
    assert sum(1 for s in brief.stories if s.deep) == 2
