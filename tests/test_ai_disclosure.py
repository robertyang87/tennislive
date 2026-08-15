"""AI 生成合成内容标识：**2026-08-15 起一条会发出去的正文里都不许再有它。**

⚠️⚠️ **这份判据整个翻了面。** 账号所有者 2026-08-15，贴着那一行标识说：
「**以后不要出现这些东西**」。所以下面每一条断言的方向都和 2026-08-14 那一版
相反——那一版要求「每个出口都必须带上」，这一版要求「一处都不许有」。

**旧那一版的来路留着，因为它当初不是空话**：《人工智能生成合成内容标识办法》
2025-09-01 已生效，而这个号的合成管线是真的——赛后开麦的解读卡口播走
edge-tts（`build_interview_clip.synthesize_narration`），竖版封面的人物是
rembg 抠的。这条是账号所有者的决定，不是「发现它没必要」。

**翻面之后判据的形状没变，只是主语反了**，仍然分三层：

1. **推导**（`test_不许再往发出去的文案里加AI标识`）：不维护白名单，从源码
   结构里推出「谁在把文案切成标题 + 正文」，那就是发布出口的全集——**一处都
   不许再调 `with_ai_disclosure`**。以后新开一条发布线也自动被它盖住。
2. **行为**：四条线各跑一次真函数，断言标识**没有**出现在输出里。查源码有没有
   那句调用只能防「有人把它加回来」，防不住「它换了个名字又加了一遍」。
3. **常量还在，而且遮罩那道闸照旧有效**（`test_遮标识只遮整句不遮片段`）：
   `AI_DISCLOSURE` 留着当扫描用的针，`mask_ai_disclosure` 留着——**万一有人
   手写了这句话**，卡片质检那张「不许出现生产脚手架的字」的表不该把它误判成
   违规。留着常量不等于留着行为。
"""

from __future__ import annotations

import ast
import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from tennislive.render.ai_disclosure import (
    AI_DISCLOSURE,
    has_ai_disclosure,
    mask_ai_disclosure,
)

# 「把小红书文案切成标题 + 正文」在这个仓库里只有一种写法，七处一字不差：
#     body_start = 2 if len(lines) > 1 and not lines[1].strip() else 1
# 判据就锚在这个谓词上。它**窄**：`video/pipeline.py` 切字幕 cue 用的是
# `lines[2:]`、`qa.py` 用的是 `lines[1:]`，两个都不含这个谓词，不会被误伤。
_SPLIT_MARK = "not lines[1].strip()"

# 扫哪些文件。`tools/` 只扫 push_reel——别的工具不发正文，整个 tools 扫进来
# 只会制造误伤（判据宁可窄，不可宽）。
_SOURCES = sorted((ROOT / "src" / "tennislive").rglob("*.py")) + [
    ROOT / "tools" / "push_reel.py"
]


def _code_without_docstrings(func: ast.FunctionDef) -> str:
    """函数体的源码，**注释和 docstring 都不算**。

    这个仓库的注释正是教训的存放处，`ai_disclosure` 那几处注释里就写着被测的
    谓词和函数名——连注释一起扫，「把坑记下来」会被判成「又踩了这个坑」，
    或者反过来制造一次假绿。`ast.unparse` 天然丢掉注释，docstring 是
    Constant 节点要自己摘。

    ⚠️ **翻面之后这一条更要紧了**：现在扫的是「有没有人把它加回来」，而
    `pushmsg` / `knowledge` / `push_reel` 的 docstring 里全都写着
    「原来会补一行 AI 生成合成内容标识，2026-08-15 起不补了」——
    连 docstring 一起扫，这几处会被判成「又加回来了」。
    """
    body = list(func.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    stripped = ast.Module(body=body, type_ignores=[])
    return ast.unparse(stripped) if body else ""


def _copy_splitters() -> dict[str, str]:
    """推导出所有「把文案切成标题 + 正文」的函数：{ 文件:函数名 -> 去注释源码 }。"""
    found: dict[str, str] = {}
    for path in _SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            code = _code_without_docstrings(node)
            if _SPLIT_MARK in code:
                found[f"{path.relative_to(ROOT)}::{node.name}"] = code
    return found


def test_不许再往发出去的文案里加AI标识():
    """账号所有者 2026-08-15：「以后不要出现这些东西」。

    **推导，不维护白名单**——和翻面之前同一个手法，只是断言反了：凡是把文案
    切成标题 + 正文的地方都是一个发布出口，**一处都不许再往里插标识**。
    以后新开一条发布线，只要它也这么切，这条判据就会替人记得。

    ⚠️ **`with_ai_disclosure` 这个函数已经删掉了**，所以这里同时扫函数名和
    常量名：只扫函数名的话，有人手写 `text += AI_DISCLOSURE` 就绕过去了。
    """
    splitters = _copy_splitters()
    # 判据自己的判据：主语没了要出声，而不是变成一条恒真的绿灯。今天是七处，
    # 分布在 pushmsg / knowledge / cli / push_reel 四个文件里。
    assert len(splitters) >= 6, (
        f"只推导出 {len(splitters)} 处切法：{sorted(splitters)}。"
        "谓词大概变了，判据要跟着主语走")
    assert len({key.split("::")[0] for key in splitters}) >= 4, (
        f"切法只落在 {sorted({k.split('::')[0] for k in splitters})} 里，"
        "推导范围大概缩了")

    added = sorted(
        name for name, code in splitters.items()
        if "with_ai_disclosure(" in code or "AI_DISCLOSURE" in code
    )
    assert not added, (
        "这些发布出口又往正文里加 AI 生成合成内容标识了：\n  "
        + "\n  ".join(added)
        + "\n账号所有者 2026-08-15 明确要求不要出现——"
        "要加回来是他改主意，不是谁读到这段觉得该加。")


def test_那个函数确实删掉了而不是留着一个空壳():
    """⚠️ **留一个「返回原文」的 `with_ai_disclosure` 是最坏的做法**：函数名在
    说它会加标识，行为却不加——下一个人读到调用点会以为标识还在，而它不在。
    这个仓库为「名字和行为对不上」栽过（`_push` 那个键名、`mode=push` 那个
    不发微信的绿 run）。要撤就整个撤掉。
    """
    import tennislive.render.ai_disclosure as mod

    assert not hasattr(mod, "with_ai_disclosure"), \
        "`with_ai_disclosure` 还在——撤掉行为就该把函数一起撤掉，别留空壳"
    assert not hasattr(mod, "DISCLOSURE_COST"), \
        "`DISCLOSURE_COST` 还在——标识不占正文预算了，这个数留着只会误导算账的人"
    # 常量和遮罩留着是**故意的**，见模块 docstring 第 3 条
    assert AI_DISCLOSURE and callable(mask_ai_disclosure) and callable(has_ai_disclosure)


def test_四条发布线的正文里都没有AI标识(tmp_path, monkeypatch):
    """行为层：四条线各跑一次真函数，标识必须**没有**出现在输出里。

    上面那条推导判据查的是「源码里有没有那个名字」，它防不住「换个写法又加了
    一遍」——这个仓库为 `_cut_person(source, …)` 那种「合并了、写进文档了、
    还带着测试，可它一次都没跑起来过」栽过一次，反过来也一样。
    """
    from push_reel import build_html

    from tennislive.render.knowledge import knowledge_push_html_from_parts
    from tennislive.render.pushmsg import to_copy_page

    text = "8.15 赛场之上 | 某人赢了\n\n正文第一段。\n\n正文第二段。\n\n#网球 #网球时差"

    # ① 复制页——四条线共用的那个出口，也是文案真正被粘进小红书的地方
    page = to_copy_page(text)
    assert AI_DISCLOSURE not in page, "复制页里又出现了 AI 标识"
    # 判据自己的判据：正文得真的进去了，否则「没有标识」可能只是页面是空的
    assert "正文第一段。" in page, "复制页里连正文都没有，这条断言什么都没验到"

    # ② 知识帖 / 解说片的微信正文（解说片的 explainer_push_html 委托给它）
    body = knowledge_push_html_from_parts(
        date=date(2026, 8, 15),
        image_urls=[],
        xhs_text=text,
        copy_url="https://example.invalid/copy.html",
    )
    assert AI_DISCLOSURE not in body, "知识帖 / 解说片的微信正文里又出现了 AI 标识"
    assert "正文第一段。" in body

    # ③ 竖版短片 / 采访的微信正文
    reel = build_html(
        "https://example.invalid/a.mp4",
        "https://example.invalid/copy.html",
        "",
        text,
        "",
        column="赛场之上",
    )
    assert AI_DISCLOSURE not in reel, "竖版短片的微信正文里又出现了 AI 标识"
    assert "正文第一段。" in reel

    # ④ 内容雷达——**唯一**一条不经过那个共用出口的推送路径，漏掉它前三条
    #    都是绿的，而它发出去的正文里标识照旧在
    from tennislive import cli
    from tennislive.publish import pushplus

    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        pushplus, "push",
        lambda title, body, **kw: sent.append((title, body)),
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"items": [{
            "title": "某人赢了",
            "text": "某人赢了\n\n正文第一段。\n\n#网球",
            "cards": [],
        }]}, ensure_ascii=False),
        encoding="utf-8",
    )
    assert cli.cmd_publish_flash(
        type("Args", (), {"manifest": str(manifest)})()
    ) == 0
    assert sent, "没发出去，这条判据什么都没验到"
    assert AI_DISCLOSURE not in sent[0][1], "内容雷达的微信正文里又出现了 AI 标识"


def test_正文的一千字上限整个归正文自己():
    """标识撤掉之后，小红书那 1000 字**不用再扣 47 字**。

    ⚠️ 这一条不是走过场：预算的口径改了而报错文本没跟着改的话，作者会看到一个
    对不上自己字数的数字，然后去怀疑闸坏了（那正是 2026-08-14 加标识时专门写
    进报错里的那笔账）。现在那笔账没了，报错里也不该再提它。
    """
    from push_reel import BODY_MAX, split_copy

    # 正好压线：1000 字的正文该过
    body_ok = "标" * BODY_MAX
    _, got = split_copy(f"标题\n\n{body_ok}")
    assert len(got) == BODY_MAX

    with pytest.raises(SystemExit) as e:
        split_copy("标题\n\n" + "标" * (BODY_MAX + 1))
    msg = str(e.value)
    assert "AI 标识" not in msg, "报错里还在算标识那 47 字，而它已经不占预算了"
    assert str(BODY_MAX) in msg


def test_遮标识只遮整句不遮片段():
    """⚠️ **这一条翻面之后仍然要留着，主语没变。**

    标识不再自动加了，但**有人手写这句话**的可能性还在（比如照着旧文案抄）。
    卡片质检那张禁用词表收着「AI 生成」四个字——不遮的话，一句合规声明会被判成
    「生产脚手架的字漏到卡片上」。遮罩本身没有任何副作用，撤掉它才要理由。

    判据宁可窄，不可宽——遮得太宽会把真该拦的词一起放过去。
    """
    assert mask_ai_disclosure("AI 生成").strip() == "AI 生成"
    assert mask_ai_disclosure(AI_DISCLOSURE).strip() == ""


def test_合规标识不会被生产描述那道闸拦下来():
    """接上一条：真拿质检那道闸跑一遍，两头都要成立。

    - 手写的标识不许被拦（不然一句合规声明被判成违规内容）；
    - 真正的脚手架词照旧要被拦（不然这次收窄等于把闸拆了）。
    """
    from tennislive.render.knowledge_visual_qa import (
        FORBIDDEN_PRODUCTION_LABELS,
        _production_label_hit,
    )

    # 前提：这句标识**确实**撞在表上——不撞的话这条判据什么都没验到
    assert any(label in AI_DISCLOSURE for label in FORBIDDEN_PRODUCTION_LABELS), (
        "标识里已经不含禁用词了，这条判据成了恒真的绿灯")

    assert _production_label_hit(f"温网的草是黑麦草。{AI_DISCLOSURE}") == ""
    assert _production_label_hit(" ".join(AI_DISCLOSURE.split())) == ""

    # 另一头：真正的脚手架词照旧拦得住，包括和标识出现在同一屏的时候
    assert _production_label_hit("本卡片由程序生成") == "程序生成"
    assert _production_label_hit(f"{AI_DISCLOSURE} 本卡片由程序生成") == "程序生成"
    assert _production_label_hit("这张图是 AI 生成的占位图") == "AI 生成"


@pytest.mark.parametrize("path", ["src/tennislive/render/ai_disclosure.py"])
def test_标识只有一处出处(path):
    """措辞写两处必分叉。**撤掉行为之后这条更要紧**：常量只该活在那一个模块里，
    谁把这句话抄进别的文件，就是绕开了上面那条「不许再加」的判据。
    """
    hits = [
        p for p in _SOURCES
        if "AI 生成合成内容标识：" in p.read_text(encoding="utf-8")
    ]
    assert [p.relative_to(ROOT).as_posix() for p in hits] == [path], (
        f"标识的措辞出现在 {[p.name for p in hits]}，它只该有一处出处")
