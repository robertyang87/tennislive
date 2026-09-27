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
| 赛后开麦（采访片） | `tools/build_interview_clip.py` 自己写 `Dialogue:` 行——⚠️ **还没接这儿**：中文行至今不去标点（评审 2026-09-27 量到存量 24 条 spec、972 行带全角标点），归 UI/VI 的 WP3 修 |

同一个模块里还有 `same_line_as_printed`：**念的那句和画面上印着的大字是不是同一句**
——是同一句就不另排字幕（大字已经印着了）。赛场之上的封面（钩子）、网球有故事字卡的
封面（大问题）共用这一份，见它自己的 docstring。

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


_PRINTED_VS_SPOKEN_NOISE = re.compile(r"[？！?!\s]+")
#: 汉字数字逐字映成阿拉伯数字（`八张` 的「张」不在 `_NUM_UNITS` 里，
#: `arabic_numerals` 够不着它）。两边走同一条路，所以映射本身讲不讲道理不影响判断。
_CJK_DIGITS = str.maketrans("〇零一二三四五六七八九", "01123456789")


def same_line_as_printed(spoken: str, printed: str) -> bool:
    """念的那句和画面上印着的那句大字，是不是同一句话。

    判据是「一不一样」——一样就不另排字幕（大字已经印着了），**不是**「封面一律
    不出字幕」：封面那句要是另说了一件事，它照样要有字幕，「静音刷是默认状态」。

    「一样」要按**说的是不是同一件事**判，不能按 `drop_punctuation` 之后逐字节比：
    那个函数**故意留着「？！」**（换页表达得了停顿，表达不了「这是一问」），于是
    钩子写成陈述句、旁白念成问句（`五天前出局，五天后赢了种子？`）会差一个问号，
    被判成「另说了一件事」，封面上多叠一行把钩子原样再写一遍的小字——
    `bu-lucky-loser-story` 2026-09-03 就这么渲出去过一版。所以在 `drop_punctuation`
    之上再抹掉 ？！ 和所有空白（大字的换行、标点换出来的空格）再比。

    ⚠️ 数字要先归一，**两边用同一套**：「给人看的字一律阿拉伯数字，只有 TTS 底稿
    写汉字」保证了印的写 `8张`、念的写 `八张`——逐字节比的话凡是带数字的封面都会
    多叠一行（`davis-cup-road-to-bologna` 第一趟三行字摞在一起）。

    来路：这个函数原来只长在 `tools/build_match_reel.py`（赛场之上的封面）。
    2026-09-27 UI/VI 评审量到**网球有故事字卡的封面同样印两遍**——大问题是 96px
    的大字，底下字幕又把「世界第11 为什么要打资格赛？」写了一遍
    （`fils-tokyo-qualifying`）。一条线的规矩到不了另一条线，所以搬到这个两条线
    共用的模块里；`tools/build_match_reel.py` 从这儿 import，不再另留一份。
    """
    from .explainer import arabic_numerals  # noqa: PLC0415 （explainer 反过来 import 本模块）

    def flat(text: str) -> str:
        return _PRINTED_VS_SPOKEN_NOISE.sub(
            "", drop_punctuation(arabic_numerals(str(text)))).translate(_CJK_DIGITS)

    return flat(spoken) == flat(printed.replace("\n", " "))
