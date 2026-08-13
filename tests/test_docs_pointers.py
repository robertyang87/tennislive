"""`docs/` 里指向 CLAUDE.md 的那些指针，必须指得到、而且不能说反话。

来路（2026-08-13）：`docs/columns.md` 有两行和 CLAUDE.md 直接打架——

    整改期的新片先 render 和人工验收，不自动推微信；得到账号所有者认可后再恢复常规发布
    流程。详细执行闸门和示例见 `CLAUDE.md` 的「平台整改后的『赛场之上』」章节。

而 CLAUDE.md「片子做完就合并、就推微信，不要再问一遍」那节里，这条例外
**2026-08-07 就已经解除**了（账号所有者：「我可以在推微信后再去确认审核」）。

两个毛病，第二个比第一个坏：

1. **口径过期**：文档还在说不自动推微信，而产物早就一边倒——`match_review` 那批
   spec 里 23 条写着 `push.auto: true`，18 条落了 `pushed.json`，日期全在 08-08
   ~ 08-13，也就是撤销之后。**悬空的只是文档，不是实际做法。**
2. **指针指错节**：`columns.md` 点名的「平台整改后的『赛场之上』」在 CLAUDE.md
   里连同子节共 66 行，当天扫过——`推微信 / 验收 / 撤销 / 解除 / 不自动 / auto`
   六个词**命中数全是 0**。顺着这个指针走的人根本拿不到「已解除」，只会带着上面
   那句过期的话离开。**指错节比单纯过期更坏**：它给出一个错答案，而读者没有第二个
   地方可以对。

所以这里钉两条，都窄：

- 划掉的记录之外，`docs/` 不许再有「不自动推微信」这句**活的**主张；
- `docs/` 里凡是写成「见 `CLAUDE.md`「X」那节」的指针，X 必须真的是 CLAUDE.md
  的一个**标题**。

⚠️ **只扫 `docs/`，不扫 CLAUDE.md。** CLAUDE.md:69-72 自己就写着「原来的做法是
……**不自动推微信**」——那是记教训的地方，连它一起扫，「把坑记下来」就会被判成
「又踩了这个坑」（本仓库同一个错犯过五次，见 CLAUDE.md「判据扫得太宽」那节）。

⚠️ **划掉的原话不算数，但也不删。** 仓库惯例是「原话一个字不删，在它下面加标注 +
指向新口径」（`MIN_OURS_RATIO` 那条、「ATP 源片卡在人工供片」那条都是这么写的）。
所以判据不是「这三个字不许出现」，是「**不许作为活的主张出现**」——扫之前先把
`~~...~~` 剥掉，和扫工作流之前先 `_yaml_only` 去掉整行注释是同一个手法。
"""

import re
from pathlib import Path

_DOCS = sorted(Path("docs").glob("*.md"))

# 划掉的记录。跨行，所以要 DOTALL。
_STRUCK = re.compile(r"~~.+?~~", re.DOTALL)

# 「见 `CLAUDE.md`「X」那节」这一种、且只有这一种。
#
# ⚠️ 判据宁可窄，不可宽：末尾那个「节」是必需的。docs 里还有好几处
# 「`CLAUDE.md` 那条「……」正好管它」「CLAUDE.md 里「……」那条」——那些引的是
# 一句话不是一节，标题里当然找不到，连它们一起扫就是误伤。实测这条正则在
# **25** 份 docs（`docs/*.md`，2026-08-13 数的）上只抓到本次修复写下的那两个
# 指针，三种近似写法一个都不沾。⚠️ 这里原来写的是 24，复查时数出来是 25——
# 下面 `scanned >= 20` 那句盯的是「扫到了没有」，盯不住这个基数写错，
# 所以口径写在这儿：`sorted(Path("docs").glob("*.md"))`，不递归子目录。
_POINTER = re.compile(
    r"`CLAUDE\.md`\s*(?:的|里|中)?\s*「([^「」]+)」\s*(?:那一?节|这一?节|章节)"
)

# 已解除的那条例外的原话特征。**不扫「整改期」三个字**——它在
# 「『赛场之上』的整改内容合同」那一节里是合法的、而且现在仍然有效。
_REVOKED_CLAIM = "不自动推微信"


def _strip_struck(text: str) -> str:
    """把划掉的记录剥掉，只留还在生效的正文。"""
    return _STRUCK.sub("", text)


def _claude_md_headings() -> list[str]:
    return [
        line.lstrip("#").strip()
        for line in Path("CLAUDE.md").read_text("utf-8").splitlines()
        if line.startswith("#")
    ]


def _normalise(name: str) -> str:
    """指针写在「」里，所以嵌套的书名号退成了『』；标题里是「」。"""
    return name.replace("『", "「").replace("』", "」")


def _peer_headings(body: str) -> list[str]:
    """切出来的这段里，除首行外还有几个**同级或更高级**的标题。

    ⚠️ 这就是「切过界了」的判据，而且它是反向验证逼出来的。原来我写的是
    `len(body) < len(整份文件)`——**那条太松，当场被骗过去**：把
    `_section_body` 的内层边界拆掉之后，它切出来的是「标题一直到文件末尾」，
    长度 228047 < 229308，**旧判据照样放行**，六条测试全绿。而那种 body 里
    裹着后面 22 个同级标题，「指到真讲推送的那一节」就成了恒真——随便指一个
    靠前的章节都能把推送那节的正文一起吞进来。

    **一段切干净的正文里，不可能出现第二个同级标题。** 这条抓得住。
    """
    lines = body.splitlines()
    level = len(lines[0]) - len(lines[0].lstrip("#"))
    return [
        line for line in lines[1:]
        if line.startswith("#") and len(line) - len(line.lstrip("#")) <= level
    ]


def _section_body(name: str) -> str | None:
    """CLAUDE.md 里那一节的正文（含子节，到下一个同级或更高级标题为止）。

    ⚠️ 必须真的**切一节**出来，判据是 `_peer_headings`（一节里不许有第二个同级
    标题），不是「切出来的比整份文件短」。后者反向验证时当场被骗过去了：边界一拆，
    它切的是「标题一直到文件末尾」，仍然比整份短，而下面那条「指到真讲推送的
    那一节」就此恒真——**随便指一个靠前的章节都能把推送那节的正文吞进来**。
    """
    lines = Path("CLAUDE.md").read_text("utf-8").splitlines()
    want = _normalise(name)
    for i, line in enumerate(lines):
        if not line.startswith("#") or want not in line.lstrip("#").strip():
            continue
        level = len(line) - len(line.lstrip("#"))
        for j in range(i + 1, len(lines)):
            nxt = lines[j]
            if nxt.startswith("#") and len(nxt) - len(nxt.lstrip("#")) <= level:
                return "\n".join(lines[i:j])
        return "\n".join(lines[i:])
    return None


def test_剥划线这件事本身不许是空转():
    """判据自己的判据。

    上面那条「不自动推微信」的检查是在**剥完划线之后**的文本上做的，所以剥这一步
    有两个方向的坏：剥不动 → 划掉的记录也被判成活主张（误伤，留不住来路）；
    剥过头 → 整份文本被吃掉，那条检查变成一盏恒真的绿灯。两头都验一次。
    """
    got = _strip_struck("留着 ~~划掉的~~ 也留着")
    assert "划掉的" not in got, "剥不动：划掉的记录会被当成活的主张"
    assert "留着" in got and "也留着" in got, "剥过头：把没划掉的正文也吃了"

    # 跨行的也要剥得掉——本次修复划掉的那一句正好跨行。
    assert "掉" not in _strip_struck("头 ~~划\n掉~~ 尾")


def test_栏目文档不许再说整改期不推微信():
    """2026-08-07 撤销之后，`docs/` 里不许再有活的「不自动推微信」。

    ⚠️ 划掉的原话不算——记录要留，口径以划线后面那段为准。
    """
    scanned = 0
    for path in _DOCS:
        raw = path.read_text("utf-8")
        scanned += 1
        assert _REVOKED_CLAIM not in _strip_struck(raw), (
            f"{path} 还在说「{_REVOKED_CLAIM}」，而这条例外 2026-08-07 就解除了"
            "（账号所有者：「我可以在推微信后再去确认审核」）。"
            "要留这句来路就用 ~~划掉~~，别让它作为活的主张站着。"
        )

    assert scanned >= 20, f"只扫到 {scanned} 份 docs，判据失效了"


def test_指向CLAUDE_md章节的指针必须指得到():
    """写成「见 `CLAUDE.md`「X」那节」的，X 必须真的是 CLAUDE.md 的一个标题。

    这条拦的是 2026-08-13 查出来的那个错：`columns.md` 把读者指向「平台整改后的
    『赛场之上』」去找推送口径，而那一节 66 行里一个字都没提推送。
    """
    headings = _claude_md_headings()
    assert headings, "CLAUDE.md 一个标题都没解析出来，判据失效了"

    found: list[tuple[Path, str]] = []
    for path in _DOCS:
        for name in _POINTER.findall(path.read_text("utf-8")):
            found.append((path, name))

    # 主语没了就出声，而不是变成一条恒真的绿灯：有人把指针改成别的写法，
    # 这条会红，而不是安安静静什么都不校。
    assert found, "docs 里一个 CLAUDE.md 章节指针都没扫到，判据失效了"

    for path, name in found:
        want = _normalise(name)
        assert any(want in h for h in headings), (
            f"{path} 指向 CLAUDE.md 的「{name}」，而 CLAUDE.md 没有这个标题。"
            "指错节比单纯过期更坏——读者会带着错口径离开。"
        )


def test_章节指针是在标题里找不是在全文里找():
    """判据自己的判据（第二条）。

    ⚠️ 这条检查最容易写坏的方式是拿 `name in claude_md_全文` 去判——那几乎恒真：
    章节名本来就会在正文里被反复引用（本次修复写下的那两个指针，自己就出现在
    `columns.md` 和 CLAUDE.md 的正文里）。所以必须只在**标题行**里找，
    而且要证明它真的会否掉一个不存在的名字。
    """
    headings = _claude_md_headings()
    bogus = "这一节根本不存在只是拿来验判据的"
    assert not any(bogus in h for h in headings), "判据连编出来的名字都放行"

    # 反过来：真标题要找得到，否则上面那条会因为「谁都找不到」而假装严格。
    assert any("片子做完就合并" in h for h in headings), "真标题都找不到，判据失效了"

    # 正文里有、标题里没有的字符串，必须被否掉——这一条才是「只在标题里找」
    # 和「在全文里找」的分界。
    body_only = "我可以在推微信后再去确认审核"
    assert body_only in Path("CLAUDE.md").read_text("utf-8"), "样本选错了，正文里没有这句"
    assert not any(body_only in h for h in headings), (
        "判据在全文里找，不是在标题里找——那样任何一句正文都能冒充章节名"
    )


def test_讲推送的那个指针要指到真讲推送的那一节():
    """`columns.md` 至少要有一个指针，**指到的那一节真的在讲推送**。

    这条才是 2026-08-13 那个 bug 的正面判据。原来那个指针**解析得开**——
    「平台整改后的『赛场之上』」确实是 CLAUDE.md 的一个真标题，所以上面那条
    「指得到」检查放它过去了；坏在**指到的地方答不了这个问题**：那一节连同子节
    66 行，一个「推微信」都没有（当天量的）。所以判据不能停在「标题存在」，
    要走进那一节的正文里看。

    ⚠️ **不写死章节名**（那就成了会过期的白名单）：改天 CLAUDE.md 重排、
    标题改名，只要 `columns.md` 的指针跟着改到真讲推送的那一节，这条照旧绿。
    """
    doc = Path("docs/columns.md").read_text("utf-8")
    names = _POINTER.findall(doc)
    assert names, "columns.md 一个 CLAUDE.md 章节指针都没有，判据失效了"

    hits = []
    for name in names:
        body = _section_body(name)
        if body is None:
            continue
        # 判据自己的判据：真的切了**一节**出来，没把后面的章节一起裹进来。
        # 裹进来的话这条检查就是一盏恒真的绿灯（见 `_peer_headings` 的注释，
        # 那个洞是反向验证当场抓出来的）。
        peers = _peer_headings(body)
        assert not peers, f"「{name}」切过界了，裹进了 {len(peers)} 个同级标题：{peers[:2]}"
        if "推微信" in body:
            hits.append(name)

    assert hits, (
        "columns.md 里没有任何一个指针指到真讲推送的那一节——"
        f"现有的指针是 {names}，它们指到的正文里都没有「推微信」。"
        "推送口径就此没有出口，读者只能从整改内容合同那节里猜。"
    )


def test_切章节这件事本身不许恒真():
    """判据自己的判据（第三条）：`_section_body` 要真的会否掉、也真的会切。"""
    assert _section_body("这一节根本不存在只是拿来验判据的") is None, "编出来的章节名也切得出东西"

    body = _section_body("片子做完就合并、就推微信，不要再问一遍")
    assert body and "推微信" in body, "真章节切不出正文，判据失效了"
    # ⚠️ 这里原来写的是 `len(body) < len(整份文件)`，反向验证时被骗过去了：
    # 切到文件末尾同样满足它。真正的判据是「一节里不许有第二个同级标题」。
    assert not _peer_headings(body), "切过界了：把后面的章节也裹进来了"

    # 而且要真的分得开两节：内容合同那节**不**讲推送，正是本次 bug 的形状。
    contract = _section_body("平台整改后的「赛场之上」")
    assert contract, "内容合同那节找不到，样本选错了"
    assert "推微信" not in contract, (
        "内容合同那节现在讲推送了？那本次修复的前提变了，这条判据要重写"
    )
