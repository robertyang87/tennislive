"""英文名取姓——全仓库**只有这一份**（review 路线 ⑥ 第一刀，2026-09-03）。

在这之前 `_surname` 在 `orchestrate.py` 里**定义了两遍**（第 93 行和第 362 行，
后一份静默盖掉前一份，两份的缩写规则还不一样），`assemble_spec` /
`prepare_alignment` 各抄一份「取最后一个词」的——而那一份对 feed 里的缩写名
是错的：`Gorzny S.` / `Bu Y.` / `Wolf J.J.` 是「姓 ＋ 名首字母加点」，姓在**第一个**词，
取最后一个词拿到的是 `S.`，反查 flashscore 当然查空（2026-09-03 干跑里三条就是
这么空的）。

规矩一条：**最后一个词以 `.` 收尾（缩写名的形状）且不止一个词，姓在第一个词；
否则姓在最后一个词。**
"""
from __future__ import annotations


def surname_en(name: str) -> str:
    words = [w for w in str(name or "").strip().split() if w]
    if not words:
        return ""
    if words[-1].endswith(".") and len(words) >= 2:
        return words[0]
    return words[-1]


def _name_tokens(text: str) -> list[str]:
    import unicodedata  # noqa: PLC0415

    plain = "".join(c for c in unicodedata.normalize("NFKD", str(text or ""))
                    if not unicodedata.combining(c))
    return [t for t in plain.casefold().replace("-", " ").replace(".", " ").split() if t]


def name_fits(given: str, side: str) -> bool:
    """`given`（「Xiyu Wang」或只给姓「wang」）是不是 feed 里这一边（「Wang Xiy.」）。

    **按整词比，不按子串比**（2026-10-12 `wangxiyu-wangxinyu-wuhan-2026-r1`：两个姓都是
    「wang」，`"wang" in "sawangkaew joint"` 成立，自动草稿的统计配到了 Sawangkaew/Joint）。
    至少一个词完全相同；给出的每个词都要在这一边找到前缀相容的词——缩写名 `Xiy.`／`F.`
    认得出，而「Xinyu」对不上「Xiy.」，同姓的两个人分得开。"""
    want, have = _name_tokens(given), _name_tokens(side)
    if not want or not have or not set(want) & set(have):
        return False
    return all(any(h.startswith(w) or w.startswith(h) for h in have) for w in want)


def pair_fits(names: list[str], home: str, away: str) -> bool:
    """两个名字分别落在**两边**（任一顺序）；不是两个名字时退回「每个都落在某一边」。"""
    if len(names) == 2:
        a, b = names
        return ((name_fits(a, home) and name_fits(b, away))
                or (name_fits(a, away) and name_fits(b, home)))
    return all(name_fits(n, home) or name_fits(n, away) for n in names)
