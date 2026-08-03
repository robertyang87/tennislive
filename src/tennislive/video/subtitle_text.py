"""烧进画面的字幕**不写标点**，全站统一。

账号所有者：「以后字幕里的尽量不要用标点符号，可以切换下一页表达。」
后来又补了一句：「字幕要应用到全局里。」——所以这条规矩不属于哪一条产线，
放在这儿给所有写 ASS 的地方共用：

| 产线 | 入口 |
|---|---|
| 知识解说片 | `video/explainer.py` 的 `_sub_display` |
| 竖版剪辑（用真实比赛画面） | 同上，`tools/build_match_reel.py` 直接调 `subtitle_cues` |
| 视频本地化 | `video/pipeline.py` 的 `render_ass` |
| 大满贯竖版 v2 | `tools/build_grand_slam_v2.py` |

**只留 `？` 和 `！`**：换页表达得了停顿，表达不了「这是一问」——末屏那一问
「你觉得合理吗」少了问号，读起来就成了陈述句。

⚠️ **去标点只作用在最后画出来的那一份。** 切子句、找断点仍然要靠原文里的
标点（见 `explainer.subtitle_lines`）；先去掉就没有断点可依，又会退回
「数满 16 个字一刀切」，把词劈成两半——「代表亚洲国家打／进大满贯」
「赢得 ATP 单／打冠军」就是那么来的。
"""

from __future__ import annotations

import re

# 掐掉两头的这些（连同空白）。
TRIM = "。，、：；,… "
# 句内的这些换成空格。
DROP = "。，、：；,…「」『』（）《》()·—"
# 映射到**空格**而不是 None（删除）：合并两个子句时中间那个句号一删，两句就
# 糊成一坨——「WC。它是谁给的」变成「WC它是谁给的」。空格不是标点。
_DROP_MAP = {ord(c): " " for c in DROP}

_WS = re.compile(r"\s+")


def drop_punctuation(text: str) -> str:
    """一行字幕 → 屏幕上真正画出来的那一份。

    换行符留着（ASS 里是 `\\N`，两行字幕靠它），只把行内的标点换成空格再收拢。
    """
    out = []
    for line in text.split("\n"):
        shown = line.strip(TRIM).translate(_DROP_MAP)
        out.append(_WS.sub(" ", shown).strip())
    return "\n".join(out)
