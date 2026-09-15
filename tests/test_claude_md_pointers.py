"""CLAUDE.md 里那些 `📖` 指针，必须只有一种写法、真的指得到，而且子目录不许长回来。

来路（2026-09-15）：这份文件是**每次 session 无条件全量注入**的，所以它自己的
体积就是成本。上一轮切进 `.claude/skills/` 之后，量出来三类纯重复：

| | 量出来多少 |
|---|---|
| 166 条 📖 指针各自带着同一句「做这类工作前先用 Skill 工具加载它。以下是子目录，正文在 skill 里」 | 7498 字符 |
| 53 处在指针后面把自己的标题又原样印一遍 | 2009 字符 |
| **336 行纯目录标题**——它们在 skill 正文里**各有一份一字不差的拷贝** | 14900 字符 |

第三类推翻了这份文件原来那句「标题一律留在原位」（账号所有者 2026-09-15 要求）。
**留在 CLAUDE.md 的是有正文的标题；子目录归 skill 自己**——一条 skill 的目录印在
一份每次全量注入的文件里，等于为「万一要查」天天付钱，而 skill 的 `description`
和开头那张七行表已经够把人routed 过去。

这里钉四条，都窄：

1. **写法只有一种**——不许有人再把套话加回来；
2. **指针指得到**——它点名的 skill 里必须真的有这一节的标题（`test_docs_pointers.py`
   为 `docs/` 指针记过同一个形状的账：**指错比过期更坏**，读者没有第二个地方可以对）；
3. **同一个标题不许连印两遍**——那 53 处就是这么来的；
4. **纯目录标题不许长回来**——自己一行正文都没有的标题，正文必然在别处，
   那它就该待在别处。这一条是「防住那一类」，不是防那一个。

⚠️ **不扫 skill 正文里的 `📖`**：skill 是档案，里面引用别的 skill 是正常的。
⚠️ 这四条都不管「该不该搬」——那是判断题，机械挡不住（本仓库为此故意没给
几条规矩写测试）。这里只管**搬完之后的形状**。
"""

import re
from pathlib import Path

_CLAUDE_MD = Path("CLAUDE.md")
_SKILLS = Path(".claude/skills")

# 两种，仅此两种。行首行尾都钉死，否则「前面再加半句套话」照样放行。
#
# - `正文 N 行`：这一节自己的正文搬走了，去 skill 里找**这一节的标题**；
# - `以下子节正文 N 行 → 从「X」起`：这一节自己的正文还在 CLAUDE.md，搬走的是它
#   底下那几节。⚠️ 锚必须写在指针里：子目录删掉之后，「指针下面第一个标题」
#   已经不是它搬走的那一节了，靠位置推会指到隔壁去。
_POINTER = re.compile(
    r"^📖 \*\*([a-z0-9-]+)\*\* · (?:正文 (\d+) 行|以下子节正文 (\d+) 行 → 从「(.+)」起)$"
)

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


def _skill_headings(skill: str) -> set[str]:
    body = (_SKILLS / skill / "SKILL.md").read_text("utf-8")
    return {ln.lstrip("#").strip() for ln in body.split("\n") if _HEADING.match(ln)}


def test_指针只有一种写法():
    """`📖 <skill> · 正文 N 行`，或带锚的「以下子节正文」那一种。

    ⚠️ 主语没了就出声：一条指针都扫不到时这条要红，而不是安安静静放行。
    """
    ptrs = _pointers()
    assert len(ptrs) >= 100, f"只扫到 {len(ptrs)} 条 📖 指针，判据失效了"

    for i, ln in ptrs:
        assert _POINTER.match(ln), (
            f"CLAUDE.md:{i + 1} 的指针不是那两种写法之一：{ln!r}。"
            "格式是 `📖 <skill 名> · 正文 N 行`——加载 skill 这件事全文开头说过一次，"
            "**不要在每条指针后面再重复一遍**：166 条同样的套话曾经占掉 7498 字符，"
            "而这份文件每次 session 全量注入。"
        )


def test_指针点名的skill真的存在而且真的有这一节():
    """指错比没有更坏——读者顺着它加载了 skill，仍然找不到正文。"""
    lines = _lines()
    cache: dict[str, set[str]] = {}
    checked = 0

    for i, ln in _pointers():
        m = _POINTER.match(ln)
        assert m, f"CLAUDE.md:{i + 1} 写法不对，先看上一条判据"
        skill, _, _, anchor = m.groups()

        path = _SKILLS / skill / "SKILL.md"
        assert path.is_file(), f"CLAUDE.md:{i + 1} 指向 {skill}，而 {path} 不存在"

        # 「以下子节正文」搬走的是子节，要找的是指针自己写着的那个锚；
        # 普通那一种找的是它上面那个标题。
        heading = anchor if anchor is not None else _owning_heading(lines, i)
        if skill not in cache:
            cache[skill] = _skill_headings(skill)
        assert heading in cache[skill], (
            f"CLAUDE.md:{i + 1} 把「{heading}」指向 {skill}，"
            f"而 {path} 里没有这个标题。指错节比单纯过期更坏——"
            "读者顺着指针走，会带着「正文在别处」离开，而那个别处是空的。"
        )
        checked += 1

    assert checked >= 100, f"只校了 {checked} 条，判据失效了"


def test_同一个标题不许连印两遍():
    """指针后面把自己的标题又印一遍，53 处，2009 字符，零新信息。

    ⚠️ 只拦**紧挨着**的重复。全文重名的标题是另一回事：这个仓库里
    「⚠️ 而我给这套写的第一条判据……」这类标题天然会撞，连它们一起拦就是误伤
    ——判据宁可窄，不可宽。
    """
    last_heading: str | None = None
    for i, ln in enumerate(_lines()):
        if not _HEADING.match(ln):
            continue
        if ln == last_heading:
            raise AssertionError(
                f"CLAUDE.md:{i + 1} 把上一个标题原样又印了一遍：{ln!r}。"
                "印两遍只是多花 token。"
            )
        last_heading = ln


def test_纯目录标题不许长回来():
    """自己一行正文都没有的标题，正文必然在别处，那它就该待在别处。

    2026-09-15 删掉 336 行这样的标题（14900 字符，占当时全文 19.9%），
    它们在 skill 正文里**各有一份一字不差的拷贝**——印在一份每次全量注入的文件里
    等于为「万一要查」天天付钱。

    ⚠️ 带 `📖` 指针的标题**不算**纯目录：指针那一行就是它的正文，它交代了
    正文去了哪个 skill，那是每次都该看见的路标。
    """
    lines = _lines()
    empty: list[tuple[int, str]] = []
    for i, ln in enumerate(lines):
        if not _HEADING.match(ln):
            continue
        end = next(
            (j for j in range(i + 1, len(lines)) if _HEADING.match(lines[j])), len(lines)
        )
        if not "".join(lines[i + 1 : end]).strip():
            empty.append((i + 1, ln))

    assert not empty, (
        "CLAUDE.md 里又出现了自己一行正文都没有的标题："
        + "；".join(f"第 {n} 行 {h!r}" for n, h in empty[:5])
        + "。子目录归 skill 自己——它的 `description` 和本文开头那张七行表已经够把人"
        "引过去，把目录再抄一份进这份**每次全量注入**的文件，是在为「万一要查」天天付钱。"
    )

    # 主语没了就出声：标题全没了的话上面那条会假装严格。
    assert sum(1 for ln in lines if _HEADING.match(ln)) >= 100, "标题数不对，判据失效了"


def test_这几条判据自己不是恒真的():
    """判据自己也要有判据（本仓库为此栽过好几次）。

    四个方向各喂一个坏样本，确认它们真的会红——只跑纯函数，不动磁盘。
    """
    # ① 写法：套话加回来、或者少了行尾，都必须判不合法
    assert _POINTER.match("📖 **tennis-dev-practices** · 正文 27 行")
    assert _POINTER.match("📖 **tennis-editorial** · 以下子节正文 210 行 → 从「⭐ 改法」起")
    assert not _POINTER.match(
        "📖 **正文（27 行）搬进 `.claude/skills/tennis-dev-practices/SKILL.md`**"
    )
    assert not _POINTER.match(
        "📖 **tennis-dev-practices** · 正文 27 行 —— 做这类工作前先用 Skill 工具加载它"
    )
    # 「以下子节」少了锚，必须判不合法——锚正是子目录删掉之后唯一的落点
    assert not _POINTER.match("📖 **tennis-editorial** · 以下子节正文 210 行")

    # ② 指得到：编出来的 skill 名必须落不了地；真的那个要在，否则上一条假装严格
    assert not (_SKILLS / "这个skill根本不存在" / "SKILL.md").is_file()
    assert (_SKILLS / "tennis-dev-practices" / "SKILL.md").is_file()

    # ③ 连印两遍：喂一段真的印了两遍的文本进去，必须抓得住
    fake = ["## 标题", "", "📖 **x** · 正文 1 行", "", "## 标题"]
    heads = [ln for ln in fake if _HEADING.match(ln)]
    assert heads[0] == heads[1], "样本自己就不重复，验不了这条"

    # ④ 纯目录：一个标题紧跟着另一个标题，就是没有正文
    seq = ["### 只有标题", "#### 又一个标题", "有正文了"]
    assert _HEADING.match(seq[0]) and _HEADING.match(seq[1]), "样本验不了这条"
