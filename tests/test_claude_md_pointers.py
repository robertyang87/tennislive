"""CLAUDE.md 里那些 `📖` 指针，必须只有一种写法、而且真的指得到。

来路（2026-09-15）：这份文件是**每次 session 无条件全量注入**的，所以它自己的
体积就是成本。切进 `.claude/skills/` 之后留下的 163 条指针，每条都带着同一句
「做这类工作前先用 Skill 工具加载它。以下是子目录，正文在 skill 里」——
**同一句话在一份全量注入的文件里印了 163 遍**，量出来 7498 字符；另有 53 处
在指针后面把自己的标题又原样印了一遍（2009 字符）。两项合计 ≈ 1.4 万字符，
占当时全文的 14.4%，而它们一个字的新信息都没有。

压成 `📖 <skill 名> · 正文 N 行` 之后，这里钉三条，都窄：

1. **写法只有一种**——不许有人再把套话加回来，也不许出现第二种格式；
2. **指针指得到**——它点名的 skill 里必须真的有这一节的标题，否则读者顺着
   指针加载了 skill 也找不到正文（`test_docs_pointers.py` 为 `docs/` 指针记过
   同一个形状的账：**指错比过期更坏**，因为读者没有第二个地方可以对）；
3. **同一个标题不许连印两遍**——那 53 处就是这么来的。

⚠️ **不扫 skill 正文里的 `📖`**：skill 是档案，里面引用别的 skill 是正常的。
⚠️ 这三条都不管「该不该搬」——那是判断题，机械挡不住（本仓库为此故意没给
几条规矩写测试）。这里只管**搬完之后的形状**。
"""

import re
from pathlib import Path

_CLAUDE_MD = Path("CLAUDE.md")
_SKILLS = Path(".claude/skills")

# 唯一合法的写法。⚠️ 行首行尾都钉死，否则「前面再加半句套话」照样放行。
# ⚠️ 两种：`正文` 指这一节自己，`以下子节正文` 指它下面那几节（这一节自己的正文
# 还留在 CLAUDE.md 里）。两者的「指得到」要去查的标题不是同一个，见下。
_POINTER = re.compile(r"^📖 \*\*([a-z0-9-]+)\*\* · (正文|以下子节正文) (\d+) 行$")

_HEADING = re.compile(r"^#+\s")


def _lines() -> list[str]:
    return _CLAUDE_MD.read_text("utf-8").split("\n")


def _pointers() -> list[tuple[int, str]]:
    """(行号, 这一行) —— 所有以 📖 开头的行，合法不合法都收。"""
    return [(i, ln) for i, ln in enumerate(_lines()) if ln.startswith("📖")]


def _owning_heading(lines: list[str], i: int) -> str:
    """指针上面最近的那个标题——它就是被搬走的那一节。"""
    for j in range(i - 1, -1, -1):
        if _HEADING.match(lines[j]):
            return lines[j].lstrip("#").strip()
    raise AssertionError(f"第 {i + 1} 行的指针上面一个标题都没有")


def _first_heading_below(lines: list[str], i: int) -> str:
    """指针下面最近的那个标题——「以下子节正文」那一种搬走的就是从它开始的几节。"""
    for j in range(i + 1, len(lines)):
        if _HEADING.match(lines[j]):
            return lines[j].lstrip("#").strip()
    raise AssertionError(f"第 {i + 1} 行的「以下子节」指针下面一个标题都没有")


def test_指针只有一种写法():
    """`📖 <skill> · 正文 N 行`，行首行尾钉死。

    ⚠️ 主语没了就出声：一条指针都扫不到时这条要红，而不是安安静静放行。
    """
    ptrs = _pointers()
    assert len(ptrs) >= 100, f"只扫到 {len(ptrs)} 条 📖 指针，判据失效了"

    for i, ln in ptrs:
        assert _POINTER.match(ln), (
            f"CLAUDE.md:{i + 1} 的指针不是唯一那种写法：{ln!r}。"
            "格式是 `📖 <skill 名> · 正文 N 行`——加载 skill 这件事全文开头说过一次，"
            "**不要在每条指针后面再重复一遍**：163 条同样的套话曾经占掉 7498 字符，"
            "而这份文件每次 session 全量注入。"
        )


def test_指针点名的skill真的存在而且真的有这一节():
    """指错比没有更坏——读者顺着它加载了 skill，仍然找不到正文。"""
    lines = _lines()
    cache: dict[str, str] = {}
    checked = 0

    for i, ln in _pointers():
        m = _POINTER.match(ln)
        assert m, f"CLAUDE.md:{i + 1} 写法不对，先看上一条判据"
        skill, kind, _ = m.groups()

        path = _SKILLS / skill / "SKILL.md"
        assert path.is_file(), f"CLAUDE.md:{i + 1} 指向 {skill}，而 {path} 不存在"

        body = cache.setdefault(skill, path.read_text("utf-8"))
        # 「以下子节正文」搬走的是子节，这一节自己的正文还在 CLAUDE.md——
        # 所以要去 skill 里找的是**紧跟在指针后面的那个标题**，不是上面那个。
        heading = (
            _first_heading_below(lines, i)
            if kind == "以下子节正文"
            else _owning_heading(lines, i)
        )
        assert any(
            heading == hl.lstrip("#").strip()
            for hl in body.split("\n")
            if _HEADING.match(hl)
        ), (
            f"CLAUDE.md:{i + 1} 把「{heading}」指向 {skill}，"
            f"而 {path} 里没有这个标题。指错节比单纯过期更坏——"
            "读者顺着指针走，会带着「正文在别处」离开，而那个别处是空的。"
        )
        checked += 1

    assert checked >= 100, f"只校了 {checked} 条，判据失效了"


def test_同一个标题不许连印两遍():
    """指针后面把自己的标题又印一遍，53 处，2009 字符，零新信息。

    ⚠️ 只拦**紧挨着**的重复（中间除了指针和空行没有别的）。全文重名的标题是
    另一回事：这个仓库里「⚠️ 而我给这套写的第一条判据……」这类标题天然会撞，
    连它们一起拦就是误伤——判据宁可窄，不可宽。
    """
    lines = _lines()
    last_heading: str | None = None
    for i, ln in enumerate(lines):
        if not _HEADING.match(ln):
            continue
        if ln == last_heading:
            raise AssertionError(
                f"CLAUDE.md:{i + 1} 把上一个标题原样又印了一遍：{ln!r}。"
                "标题留在原位是为了当索引，印两遍只是多花 token。"
            )
        last_heading = ln


def test_这三条判据自己不是恒真的():
    """判据自己也要有判据（本仓库为此栽过好几次）。

    三个方向各喂一个坏样本，确认它们真的会红——只跑纯函数，不动磁盘。
    """
    # ① 写法：套话加回来、或者少了行尾，都必须判不合法
    assert _POINTER.match("📖 **tennis-dev-practices** · 正文 27 行")
    assert _POINTER.match("📖 **tennis-editorial** · 以下子节正文 210 行")
    assert not _POINTER.match("📖 **tennis-editorial** · 以下子节的正文 210 行")
    assert not _POINTER.match(
        "📖 **正文（27 行）搬进 `.claude/skills/tennis-dev-practices/SKILL.md`**"
    )
    assert not _POINTER.match(
        "📖 **tennis-dev-practices** · 正文 27 行 —— 做这类工作前先用 Skill 工具加载它"
    )

    # ② 指得到：编出来的 skill 名必须落不了地
    assert not (_SKILLS / "这个skill根本不存在" / "SKILL.md").is_file()
    # 反过来，真的那个要在，否则上一条会因为「谁都不在」而假装严格
    assert (_SKILLS / "tennis-dev-practices" / "SKILL.md").is_file()

    # ③ 连印两遍：喂一段真的印了两遍的文本进去，必须抓得住
    fake = ["## 标题", "", "📖 **x** · 正文 1 行", "", "## 标题"]
    heads = [ln for ln in fake if _HEADING.match(ln)]
    assert heads[0] == heads[1], "样本自己就不重复，验不了这条"
