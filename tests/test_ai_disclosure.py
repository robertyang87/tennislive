"""AI 生成合成内容标识：每一条会发出去的正文都必须带上它。

来路 2026-08-14：《人工智能生成合成内容标识办法》2025-09-01 已生效，
《互联网信息服务深度合成管理规定》同样适用。这个号的旁白全部是合成语音
（edge-tts / Azure / MiniMax），竖版封面的人物是 rembg 抠出来的——而在这一天
之前，specs、渲染路径、推送正文、`xhs.txt` 里**一个字的声明都没有**。
账号 2026-08-06 已经被视频号处理过一次，带着未声明的合成管线属于会直接导致
停摆的那一类风险。

这份判据分三层，缺一层都会退回「写了不等于跑过」：

1. **推导**（`test_把文案切成标题正文的路径都要带AI标识`）：不维护白名单，
   从源码结构里推出「谁在把文案切成标题 + 正文」，那就是发布出口的全集。
2. **行为**：三条线各跑一次真函数，断言标识真的出现在输出里。查源码有没有
   那句调用只能防「有人把它删了」，防不住「它从来没工作过」。
3. **不被自己人拦下**（`test_合规标识不会被生产描述那道闸拦下来`）：标识里
   写着「AI 生成」，而卡片质检有一张禁用词表正好收着这四个字。
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
    DISCLOSURE_COST,
    has_ai_disclosure,
    mask_ai_disclosure,
    with_ai_disclosure,
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


def test_把文案切成标题正文的路径都要带AI标识():
    """凡是把小红书文案切成标题 + 正文的地方，都是一个会把正文发出去的出口。

    **自己推导，不维护白名单**：这个仓库为「手写名单会在删掉一条线的当天变成
    FileNotFoundError」栽过（`test_every_workflow_that_commits_generated_files_has_a_size_gate`），
    也为「伪装成推导的白名单」栽过（那条把两种拼法硬编码进了正则）。以后新开
    一条发布线，只要它也要把文案拆成标题和正文，这条判据就会替人记得。
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

    missing = sorted(
        name for name, code in splitters.items()
        if "with_ai_disclosure(" not in code
    )
    assert not missing, (
        "这些地方把文案切成标题+正文发出去了，却没加 AI 生成合成内容标识：\n  "
        + "\n  ".join(missing)
        + "\n加一句 `text = with_ai_disclosure(text)` 在切之前——"
        "标识是法规要求的，不是可选装饰。")


def test_标识排在末尾的tag之前否则会被cut_at_tags砍掉():
    """标识写在 tag 后面会被 `cut_at_tags` 整段砍掉，**而且不吭声**。

    `cut_at_tags` 的判据是「最后一个 `#` 标签所在的行就是终点，后面的一概
    不发」——它就是为了拦住写给下一个人的备注跟着正文进微信而存在的。所以
    标识必须插在那串 tag **之前**，而不是 append 到末尾。
    """
    import contextlib
    import io

    from push_reel import cut_at_tags

    text = "标题\n\n正文第一段。\n\n正文第二段。\n\n#网球 #网球时差"
    out = with_ai_disclosure(text)
    assert has_ai_disclosure(out)
    lines = out.splitlines()
    assert lines.index(AI_DISCLOSURE) < max(
        i for i, ln in enumerate(lines) if "#" in ln
    ), f"标识排到 tag 后面去了：\n{out}"
    # 真跑一次 cut_at_tags——查位置只能防「顺序写反了」，防不住这条链上
    # 别的地方又把它吃掉。
    with contextlib.redirect_stdout(io.StringIO()):
        assert has_ai_disclosure(cut_at_tags(out)), "标识被 cut_at_tags 砍掉了"

    # 没有 tag 的文案就落在最末尾；空文案不凭空造一段（没有正文就没有要标识
    # 的内容，而 push_reel.main 对空文案本来就会当场报错）。
    assert with_ai_disclosure("标题\n\n只有正文").endswith(AI_DISCLOSURE)
    assert with_ai_disclosure("  ") == "  "


def test_标识是幂等的():
    """两个 stage 会让同一段文字先后过两次，印两遍就是「同一段印两遍」那个老毛病。"""
    once = with_ai_disclosure("标题\n\n正文。\n\n#网球")
    assert with_ai_disclosure(once) == once
    assert once.count(AI_DISCLOSURE) == 1


def test_标识本身的措辞不许退回去():
    """措辞的三个约束，改哪一个都要先读一遍 `ai_disclosure` 的 docstring。"""
    # ①「AI 生成」是办法和 GB 45438-2025 的原词。换成「AI 辅助生成」之类不含
    #   这个子串的写法，下面那条「不被生产描述闸拦下来」的判据就再也验不到
    #   它想验的东西，会变成一条恒真的绿灯。
    assert "AI 生成" in AI_DISCLOSURE
    # ② 旁白是主要事实（这个号的旁白全部是合成语音），而且排在画面前面。
    assert "合成语音" in AI_DISCLOSURE
    assert AI_DISCLOSURE.index("旁白") < AI_DISCLOSURE.index("画面")
    # ③ 短。它占掉的每一个字都从小红书正文 1000 字的平台预算里出。
    assert DISCLOSURE_COST == len(AI_DISCLOSURE) + 2
    assert len(AI_DISCLOSURE) <= 60, f"标识 {len(AI_DISCLOSURE)} 字，太长了"
    # 不许带 `#`：tag 数是有上限的（知识帖 3~5、reel 最多 5），标识多带一个
    # 就会把别人的 tag 挤掉，而那不报错。
    assert "#" not in AI_DISCLOSURE
    # 小红书正文是纯文本，markdown 记号粘过去会原样露出来。
    assert not any(mark in AI_DISCLOSURE for mark in ("**", "`", "|", "[", "]"))


def test_三条线发出去的正文都带AI标识():
    """行为层：三条线各跑一次真函数，标识必须真的出现在输出里。

    上面那条推导判据查的是「源码里有没有那句调用」，它防不住「它从来没工作
    过」——这个仓库为 `_cut_person(source, …)` 那种「合并了、写进文档了、
    还带着测试，可它一次都没跑起来过」栽过一次。
    """
    from push_reel import build_html

    from tennislive.render.knowledge import knowledge_push_html_from_parts
    from tennislive.render.pushmsg import to_copy_page

    text = "8.14 赛场之上 | 某人赢了\n\n正文第一段。\n\n正文第二段。\n\n#网球 #网球时差"

    # 复制页——四条线共用的那个出口，也是文案真正被粘进小红书的地方。
    page = to_copy_page(text)
    assert AI_DISCLOSURE in page, "复制页里没有 AI 标识"

    # 知识帖 / 解说片的微信正文（解说片的 explainer_push_html 委托给它）。
    body = knowledge_push_html_from_parts(
        date=date(2026, 8, 14),
        image_urls=[],
        xhs_text=text,
        copy_url="https://example.invalid/copy.html",
    )
    assert AI_DISCLOSURE in body, "知识帖 / 解说片的微信正文里没有 AI 标识"

    # 竖版短片 / 采访的微信正文。
    reel = build_html(
        "https://example.invalid/a.mp4",
        "https://example.invalid/copy.html",
        "",
        text,
        "",
        column="赛场之上",
    )
    assert AI_DISCLOSURE in reel, "竖版短片的微信正文里没有 AI 标识"


def test_内容雷达那条线的微信正文也带AI标识(tmp_path, monkeypatch):
    """内容雷达不走 `to_copy_page`，正文直接从 package.json 的 `text` 出。

    单独验一次是因为它是**唯一**一条不经过那个共用出口的推送路径——漏掉它，
    上面那两条判据都是绿的，而它发出去的正文一个字的标识都没有。
    """
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
    assert AI_DISCLOSURE in sent[0][1], "内容雷达的微信正文里没有 AI 标识"


def test_合规标识不会被生产描述那道闸拦下来():
    """卡片质检那张禁用词表收着「AI 生成」——而那正是标识必须用的词。

    ⚠️ 这张表**没有删**：它拦的「生产脚手架的字漏到卡片上」仍然该拦。收窄的
    办法是**先把标识那句话遮掉再扫**，和译名那条判据「先把文中所有规范名遮
    掉，再找剩下的近似串」是同一个手法。

    判据钉两头，少一头都不成立：
      - 标识本身不许被拦（不然合规动作被判成违规内容）；
      - 真正的脚手架词照旧要被拦（不然这次收窄等于把闸拆了）。
    """
    from tennislive.render.knowledge_visual_qa import (
        FORBIDDEN_PRODUCTION_LABELS,
        _production_label_hit,
    )

    # 前提：这句标识**确实**撞在表上——不撞的话这条判据什么都没验到。
    assert any(label in AI_DISCLOSURE for label in FORBIDDEN_PRODUCTION_LABELS), (
        "标识里已经不含禁用词了，这条判据成了恒真的绿灯。"
        "要么把措辞改回办法的原词，要么把这条判据一起撤掉")

    assert _production_label_hit(f"温网的草是黑麦草。{AI_DISCLOSURE}") == "", (
        "合规标识被生产描述那道闸拦下来了")
    # 卡片上的可见文字会被 `_visible_blocks` 归一化空白，遮的时候也要按归一化
    # 之后的样子遮。
    assert _production_label_hit(" ".join(AI_DISCLOSURE.split())) == ""

    # 另一头：真正的脚手架词照旧拦得住，包括和标识出现在同一屏的时候。
    assert _production_label_hit("本卡片由程序生成") == "程序生成"
    assert _production_label_hit(f"{AI_DISCLOSURE} 本卡片由程序生成") == "程序生成"
    assert _production_label_hit("这张图是 AI 生成的占位图") == "AI 生成"


def test_遮标识只遮整句不遮片段():
    """判据宁可窄，不可宽——遮得太宽会把真该拦的词一起放过去。"""
    assert mask_ai_disclosure("AI 生成").strip() == "AI 生成"
    assert mask_ai_disclosure(AI_DISCLOSURE).strip() == ""


@pytest.mark.parametrize("path", ["src/tennislive/render/ai_disclosure.py"])
def test_标识只有一处出处(path):
    """措辞写两处必分叉，而分叉的样子是「同一天发出去的两条片子说法不一样」。"""
    hits = [
        p for p in _SOURCES
        if "AI 生成合成内容标识：" in p.read_text(encoding="utf-8")
    ]
    assert [p.relative_to(ROOT).as_posix() for p in hits] == [path], (
        f"标识的措辞出现在 {[p.name for p in hits]}，它只该有一处出处")
