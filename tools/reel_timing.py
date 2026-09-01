"""「赛场之上」旁白时长的轻量单一事实源。"""

from __future__ import annotations

import re

SPEECH_PER_CHAR = 0.166
SPEECH_PER_PUNCT = 0.32
SPEECH_TAIL = 0.45
# ⚠️ **按词读的拉丁串比汉字便宜得多，别按字符数收费。** 2026-09-01
# `osaka-iverson-tribute` 第 ⑦ 段「造型师 Law Roach 牵的线，找的是纽约一个
# 牌子，Who Decides War。」——21 个拉丁字母按 0.166 收是 3.49 秒，而真语音
# 量出来整句只有 5.14 秒，**离线估 7.39 秒、高了 2.25 秒**，当场把
# `test_离线估旁白长度要对得上真产物` 打红（带子是 ±2.2）。
#
# 分两档是**量出来的，不是拍的**（1986 段已发实测里 65 段带拉丁字母）：
#
# | 这一类 | 怎么念 | 收费 |
# |---|---|---|
# | **全大写的缩写**（`ACE` `WTA` `ATP`）和落单的字母（`W100` 的 W） | 逐字母念 | 照 `SPEECH_PER_CHAR` |
# | **有小写的真词**（`Law` `Roach` `Who Decides War` `QueenWen` `Ace`） | 按词念 | `SPEECH_PER_LATIN` |
#
# 缩写那一档占绝大多数（60+ 段），老模型对它一直是准的（中位误差 ~0），
# 所以**不动它**；改的只是真词那一档。0.08 是拿两条真词样本扫出来的
# （`zheng-lanlana` 第 ⑨ 段 `QueenWen` 8 个字母、`osaka-iverson-tribute`
# 第 ⑦ 段 21 个字母），在 0.05~0.10 之间取「带真词的那几段最坏误差」最小的
# 那一档：改之前那 14 段最坏 2.25 秒，改之后 0.80 秒；全库中位数一动没动
# （−0.016 → −0.018），最坏那一段仍然是另一条纯中文的 2.19 秒。
#
# ⚠️ **正则跑在原文上，不是跑在去掉 `SPEECH_QUIET` 之后的 body 上**：空格
# 在 QUIET 里，先去掉的话 `Law Roach` 会粘成一个串——这一条上判不出差别
# （粘起来还是有小写），但 `WTA ACE` 粘成 `WTAACE` 之类的组合迟早会咬人。
SPEECH_PER_LATIN = 0.08
# Keep these as strings: the renderer's calibration tests concatenate them.
SPEECH_PUNCT = "，。！？、；：—…,.!?;:"
SPEECH_QUIET = "“”‘’\"'（）()《》「」 \t\n"

_LATIN_RUN = re.compile(r"[A-Za-z]+")


def latin_word_letters(text: str) -> int:
    """按词念的那些拉丁串一共多少个字母（全大写的缩写不算在内）。"""
    return sum(len(run.group(0)) for run in _LATIN_RUN.finditer(text)
               if len(run.group(0)) >= 2 and not run.group(0).isupper())


def speech_seconds(text: str) -> float:
    """按已发布成片拟合系数估算一段中文旁白的秒数。"""
    body = "".join(char for char in text if char not in SPEECH_QUIET)
    punct = sum(1 for char in body if char in SPEECH_PUNCT)
    latin = latin_word_letters(text)
    chars = len(body) - punct - latin
    if not chars and not punct and not latin:
        return 0.0
    return (chars * SPEECH_PER_CHAR + latin * SPEECH_PER_LATIN
            + punct * SPEECH_PER_PUNCT + SPEECH_TAIL)
