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
