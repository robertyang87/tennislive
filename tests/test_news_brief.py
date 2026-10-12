"""热点简报这条线的判据（CLAUDE.md：规则要落成测试）。

账号所有者 2026-08-05：「目前推送的内容还有两块，英文媒体一份中文一份，
而且也看不到具体内容……合并成一个做推送」。

⚠️ 2026-10-12 模型通道整体摘除（账号所有者：「都不留了」）：中译与要点
提炼不再发生——`build_brief` 不再收模型替身，产物只有英文标题、热度、
常青线和原文抓取记录，而且**必须在 notes 里如实写明通道已移除**。
原来钉模型调用形状／通道选择的那批判据随功能一并删除；剩下的钉：
合并成一条推送、去噪、抓正文的记录与退化出声、常青线不丢、空产自证。
"""

from pathlib import Path

from tennislive.render.newsbrief import render_brief_html
from tennislive.research.brief import (
    build_brief,
    drop_navigation,
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
    )
    assert brief.dropped_nav == ["What is the Washington schedule?"]
    assert "摘掉 1 条" in render_brief_html(brief)


# ---------------------------------------------------------------------------
# 二、抓正文：读到了哪几篇要记录，提炼已移除要说清
# ---------------------------------------------------------------------------
def test_读到正文也只是列标题_要点提炼已随模型通道移除():
    """抓取还在（读到哪几篇、`reads` 记录照旧），但**不许假装深挖过**：
    points 必须空、标题保持英文，note 和产物都要写明提炼已移除。"""
    brief = build_brief("2026-08-05", news=_DRAPER, fetch=_ok_fetch, deep=1)
    story = brief.stories[0]
    assert story.reads and all(r.ok for r in story.reads)
    assert not story.deep and story.points == ()
    assert story.title_zh == ""
    assert "要点提炼已随模型通道移除" in story.note
    assert any("模型通道已移除" in n for n in brief.notes)
    assert "模型通道已移除" in render_brief_html(brief)


def test_读不到正文要说清卡在哪():
    """抓不到和「这条本来就没内容」不许长得一样。

    ⚠️ 退化在这个仓库里出过太多次事，判据钉两头：**不许假装深挖过**
    （points 必须空），**而且要说出每一条卡在哪**（HTTP 码要在 note 里）。
    """
    brief = build_brief("2026-08-05", news=_DRAPER, fetch=_dead_fetch, deep=1)
    story = brief.stories[0]
    assert not story.deep and story.points == ()
    assert "没读到正文" in story.note and "HTTP 403" in story.note
    # 推送正文底部也要说，不能只写进 JSON——读微信的人不会去翻 JSON
    assert "没读到正文" in render_brief_html(brief)


def test_标题保持英文原样_中译已随模型通道移除():
    brief = build_brief("2026-08-05", news=_DRAPER, fetch=_dead_fetch, deep=0)
    story = brief.stories[0]
    assert story.title_zh == ""
    assert any("标题中译已随模型通道移除" in n for n in brief.notes)
    html = render_brief_html(brief)
    assert "Draper withdraws from Washington" in html


# ---------------------------------------------------------------------------
# 三、译名表（机械部分还在：扫得出、认得准、不塞不相干的人）
# ---------------------------------------------------------------------------
def test_译名表认得出标题里的人名赛事名():
    """Rybakina 会被译成「里巴金娜」，而我们自己的稿子里写着**莱巴金娜**——
    译名表本身是机械查表，模型通道没了它也还是那份口径的单一出处。"""
    glossary = build_glossary(["Rybakina eases past Ostapenko in Montreal"])
    assert glossary.get("Elena Rybakina") == "莱巴金娜"
    assert glossary.get("Jelena Ostapenko") == "奥斯塔彭科"
    line = glossary_lines(glossary)
    assert "莱巴金娜" in line and "必须" in line


def test_译名表不许把不相干的人塞进来():
    """扫出来的名字要真在这批标题里出现过——塞满一百个名字只是挤上下文。"""
    glossary = build_glossary(["Rybakina eases past Ostapenko in Montreal"])
    assert "Jannik Sinner" not in glossary
    assert len(glossary) <= 40


# ---------------------------------------------------------------------------
# 四、人工角度表没有被丢掉
# ---------------------------------------------------------------------------
def test_人工角度表要跟着热点一起出现():
    """这是简报里**唯一不是机器产的东西**，合并的时候不许顺手丢掉。

    每条角度背后都有一份能翻的规则书或史料；它原来还是深挖的输入，
    模型通道移除后只剩并排展示这一半——标签照旧分开写。
    """
    brief = build_brief("2026-08-05", news=_DRAPER, fetch=_ok_fetch, deep=1)
    story = brief.stories[0]
    assert story.known is not None and story.known.slug == "withdrawal-deadline"
    assert brief.as_dict()["stories"][0]["known_angle"]["slug"] == "withdrawal-deadline"
    html = render_brief_html(brief)
    assert "Draper withdraws from Washington" in html
    # 模型推的角度那一栏不再出现（angle 恒空）
    assert story.angle == "" and "可做的角度" not in html


# ---------------------------------------------------------------------------
# 五、空产要自证
# ---------------------------------------------------------------------------
def test_空产要分得清是没热点还是抓取全挂了():
    empty = build_brief("2026-08-05", news=[])
    assert any("一条新闻都没抓到" in n for n in empty.notes)

    lonely = build_brief(
        "2026-08-05",
        news=_news(("ATP Tour", "Draper withdraws from Washington", "https://a/1")),
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


def test_不发微信那一趟也要出声():
    """`push=false` 只跳过发消息，而**跳过这件事必须留一行日志**。

    2026-08-05 加这个开关，是因为「⚠️ 判据只在发布路径上才走得到，它就永远
    验不了」：改了口径想看一眼产物长什么样，原来只能真发一条微信，
    而那条消息发出去收不回来。同一天为此发了三条几乎一样的推送。

    ⚠️ **判据的重点是「装在哪」，不是「有没有」**。写成步骤级的
    `if: inputs.push == 'true'` 行为完全一样，可**被跳过的步骤根本不进日志**
    ——那正是 `mode=push` 那次栽的坑（27 秒、绿的、什么都没发，日志里
    一个字都没说）。所以判断必须在 `run:` 里面，而且要 echo 一句。
    """
    text = _yaml_only(_workflow("news-brief.yml"))

    # ① 开关在，而且**默认是发**——默认改成 false 等于把这条线静默停产
    assert "\n      push:\n" in text, "没有 push 这个开关"
    # ⚠️ 按**缩进**收这一块，别按 `split("\n      ")` 切——`inputs` 底下的字段
    # 是 8 格，第一刀就会切在 `description` 上，于是永远看不到 `default`。
    block: list[str] = []
    for line in text.split("\n      push:\n", 1)[1].splitlines():
        if line.strip() and not line.startswith("        "):
            break
        block.append(line)
    switch = "\n".join(block)
    assert 'default: "true"' in switch, f"push 的默认值必须是 true，实际是：{switch}"

    # ② 不许写在步骤的 `if:` 上——那样跳过就不留痕迹
    on_if = [
        line for line in text.splitlines()
        if line.lstrip().startswith("if:") and "inputs.push" in line
    ]
    assert not on_if, f"push 判断写在了 if: 上，跳过时不留日志：{on_if}"

    # ③ 那一支要 echo 出来
    step = [s for s in text.split("\n      - name: ") if "pushplus.plus/send" in s
            and "failure()" not in s][0]
    assert "inputs.push" in step, "推送步骤里没有这个开关"
    branch = step.split("inputs.push", 1)[1].split("fi", 1)[0]
    assert "echo" in branch and "不发微信" in branch, "跳过发送时没有留下任何一行说明"


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
# 七、抓正文不按名次砍
# ---------------------------------------------------------------------------
_TWO_STORIES = _news(
    ("ATP Tour", "Draper withdraws from Washington with elbow injury", "https://a/1"),
    ("Sky Sports", "Draper withdraws citing elbow injury before US Open", "https://b/1"),
    ("BBC Sport", "Rybakina eases past Ostapenko in Montreal opener", "https://c/1"),
    ("ESPN", "Rybakina downs Ostapenko at the Montreal opener", "https://d/1"),
)


def test_默认全部抓正文不按名次砍():
    """账号所有者 2026-08-05：「不要限制只有一条」。

    第一版按 `stories[:5]` 砍，那是**版面判断替编辑判断做了决定**——
    排第 6 的没被读，不是因为它不值得，只是因为它排第 6。
    （模型通道移除后，「深挖」只剩抓正文记录这一半，口径不变。）
    """
    brief = build_brief("2026-08-05", news=_TWO_STORIES, fetch=_ok_fetch)
    assert len(brief.stories) == 2, "这批数据本来就该聚出两簇，判据的前提没了"
    assert all(s.reads for s in brief.stories), "默认应该全抓，不该按名次砍"


def test_给了deep就按热度取前几条():
    """收口的能力要留着——`--deep N` 仍然按热度取前 N 条抓正文。"""
    brief = build_brief(
        "2026-08-05", news=_TWO_STORIES, fetch=_ok_fetch, deep=1,
    )
    assert [bool(s.reads) for s in brief.stories] == [True, False]


def test_deep等于0不许被切片吃成一条都不抓():
    """⚠️ `stories[:0]` 是空列表——如果用切片表达「不限」，会一条都不抓，
    而那和「今天没有热点」长得一模一样。所以必须显式分支。"""
    from tennislive.research.brief import DEFAULT_DEEP

    assert DEFAULT_DEEP == 0, "0 是「全部」的哨兵值"
    brief = build_brief(
        "2026-08-05", news=_TWO_STORIES, fetch=_ok_fetch, deep=0,
    )
    assert sum(1 for s in brief.stories if s.reads) == 2
