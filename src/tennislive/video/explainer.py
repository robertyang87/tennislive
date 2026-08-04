"""AI-narrated knowledge explainer video — image-first, for topics photos can't
easily carry.

Some knowledge topics are abstract (how Hawk-Eye works): there is no
licensable, high-relevance photo of "electronic line calling", so the strict
photo deck can't publish them. A short narrated video fits them: it explains
rather than illustrates.

The video walks an arc the audience can follow — background, how it works,
where it stands today — in as many beats as the story needs; more beats means
more pictures, which is what carries an explainer.

Each beat is one 3:4 brand card whose HERO is a real, verified, licensed photo
(or, where no fitting photo exists, an original labelled schematic — clearly a
diagram, never fabricated footage). Over the image sit a short title and 2-3
distilled key lines; the full explanation is spoken by a Chinese TTS voice, so
the slide is the skeleton and the narration is the flesh.

Two rules the photos must hold to:
  - the hero must match what its beat claims (a Wimbledon grass frame cannot
    illustrate "only Roland-Garros still keeps human line judges"), and
  - which tournament a frame shows comes from the source's own description and
    categories, never from our reading of the pixels.

The 3:4 card is centred on a 9:16 video canvas with brand bands. Provenance is
recorded in assets/explainer/<slug>/credits.json, not painted on the frame.
"""

from __future__ import annotations

import base64
import html
import json
import mimetypes
import os
import re
import shutil
import subprocess
import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence
from ..cdn import jsdelivr_base
from .subtitle_text import DROP as SUB_DROP, TRIM as SUB_TRIM, drop_punctuation

# The card/image keeps the brand 3:4 (1080x1440); the video canvas is 9:16
# (1080x1920) with that 3:4 card centred on brand-colour bands.
W, H = 1080, 1440  # slide / image (3:4)
VIDEO_W, VIDEO_H = 1080, 1920  # video canvas (9:16)
_BAND_COLOR = "0x061c14"
# 卡片在 9:16 画布上的位置。原来是上下居中（黑边各 240px），字幕只能挤在最底下，
# 而那正是小红书/抖音盖住文案和按钮的地方。把卡片抬高，下边条从 240 变成 384：
# 字幕贴在这条宽边的顶部，底部 240px 留给 app 的界面，画面一个像素也没被压。
CARD_H = VIDEO_W * 4 // 3           # 3:4 的卡在 1080 宽下有多高
# 卡片在画布上**居中**。一度把它抬到 CARD_TOP=88 好在下面腾地方放字幕，结果
# 卡片顶上那行「网球时差 · 开球之前」钻进了 app 顶部的返回键/状态栏里——
# 上下各 240px 的对称留白就是躲开两头 UI 的，动它得不偿失。
CARD_TOP = (VIDEO_H - CARD_H) // 2  # = 240
# 卡上的文字块（小标 / 大标题 / 要点 / 末屏那一问）离卡片下沿留这么多。
# 原来 120px；为了在卡片内部腾一条给字幕先抬到 300px，**抬过头了**——整摞字被推高，
# 要点块压在人物胸口和球拍上，字幕底下却空出 132px 卡片 + 240px 黑边。
# 230px 是渲三档比出来的：文字整体下移 50px，画面主体让出来，字幕下面仍留 78px。
CARD_COPY_BOTTOM = 230

_REPO = Path(__file__).resolve().parents[3]
_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "robertyang87/tennislive")
_PAGES_URL = os.environ.get(
    "TENNISLIVE_PAGES_URL",
    "https://{}.github.io/{}".format(*_REPOSITORY.split("/", 1)),
).rstrip("/")


# 卡片截图的 JPEG 质量。82 是下限（深绿底上的浅色小字开始出现块状噪点），
# 86 与无损 PNG 逐像素比过看不出差别。改这个数要重新渲一屏文字最密的
# 示意图，放大对比，别按比例推。
_SLIDE_JPEG_QUALITY = 86


class _Unset:
    """「这个参数没传」的哨兵，用来和「传了 None」区分开。

    复制页的 URL 上，两者含义相反：没传＝调用方没探过，按老规矩自己拼一个；
    传 None＝调用方探过了、链接取不到，别放那个按钮。用 None 当默认值就把
    这两件事压成一件，「没探」会被当成「探过了没有」，按钮无声消失。
    """


_UNSET = _Unset()


class ExplainerVideoError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExplainerSegment:
    kind: str  # cause / mechanism / today
    label: str  # 前因后果 / 技术原理 / 当今现状
    title: str  # short on-screen caption
    narration: str  # full spoken text (TTS only)
    image: str = ""  # repo-relative photo path; "" -> use `diagram`
    credit: str = ""  # provenance for records; never painted on the frame
    # 2-3 distilled key lines shown on-screen. The narration says it in full;
    # these give the eye the skeleton (dates, numbers, the verdict) so the
    # viewer can follow with the sound off or read along with it.
    points: tuple[str, ...] = ()
    # Original SVG used when no photo can honestly carry the beat. Drawing
    # our own is the only truthful option for a moment nobody holds a
    # licensable frame of: it states the date, place and players outright
    # and imitates no real footage.
    diagram: str = ""
    # A closing question on the final beat: a short explainer earns its
    # reach in the comments, so end by asking rather than concluding.
    question: str = ""
    # 封面上那两行小字，只有「开球之前」有：
    #     7.30  09:00  ATP250 洛斯卡沃斯  16 强
    #     黄泽林  VS  莱赫奇卡
    # 赛前片的封面被单独截图转发时，大问题本身说不清「哪一场、几点」——
    # 这两行把比赛坐标钉在同一屏上。由 `_fixture_lines()` 从结构化字段拼出来，
    # 不手写，免得日期和轮次在几处各写各的。
    fixture: tuple[str, ...] = ()
    # 封面大标题底下的一行小字，用来给标题里的缩写或行话当场作注。
    # 和 `fixture` 分开是因为那一路被钉死给「开球之前」了（常青栏目的封面
    # 不该印比赛坐标），而作注这件事和赛前片没关系。
    # **加在最后**：`_SCRIPTS` 里的 beat 是按位置解包的，插中间会整体错位。
    gloss: str = ""


# Original, labelled schematic for the "how Hawk-Eye works" beat — clearly a
# diagram (cameras triangulating the ball), not fabricated footage.
_HAWKEYE_DIAGRAM = """
<svg viewBox="0 0 900 660" xmlns="http://www.w3.org/2000/svg">
  <!-- Court drawn to the real 78x36 ft proportions: doubles lines, singles
       lines, service boxes, centre marks and the net across the middle, so it
       reads as a tennis court rather than a plain rectangle. -->
  <rect x="90" y="150" width="720" height="332" rx="4"
        fill="rgba(55,226,154,.07)" stroke="#37e29a" stroke-width="4"/>
  <line x1="90" y1="191" x2="810" y2="191" stroke="#37e29a" stroke-width="3"/>
  <line x1="90" y1="441" x2="810" y2="441" stroke="#37e29a" stroke-width="3"/>
  <line x1="256" y1="191" x2="256" y2="441" stroke="#37e29a" stroke-width="3"/>
  <line x1="644" y1="191" x2="644" y2="441" stroke="#37e29a" stroke-width="3"/>
  <line x1="256" y1="316" x2="644" y2="316" stroke="#37e29a" stroke-width="3"/>
  <line x1="90" y1="308" x2="90" y2="324" stroke="#37e29a" stroke-width="4"/>
  <line x1="810" y1="308" x2="810" y2="324" stroke="#37e29a" stroke-width="4"/>
  <line x1="450" y1="132" x2="450" y2="500" stroke="#dff3e8" stroke-width="6"/>
  <g stroke="#dff3e8" stroke-width="3" opacity=".75">
    <line x1="450" y1="150" x2="450" y2="482" stroke-dasharray="3 9"/>
  </g>
  <circle cx="450" cy="132" r="7" fill="#dff3e8"/>
  <circle cx="450" cy="500" r="7" fill="#dff3e8"/>
  <!-- cameras ringing the court, triangulating one bounce -->
  <g fill="#9fb4aa">
    <circle cx="150" cy="86" r="12"/><circle cx="450" cy="62" r="12"/>
    <circle cx="750" cy="86" r="12"/><circle cx="846" cy="316" r="12"/>
    <circle cx="750" cy="548" r="12"/><circle cx="450" cy="572" r="12"/>
    <circle cx="150" cy="548" r="12"/><circle cx="54" cy="316" r="12"/>
  </g>
  <g stroke="#c6f65a" stroke-width="2" stroke-dasharray="5 7" opacity=".75">
    <line x1="150" y1="86" x2="690" y2="420"/><line x1="450" y1="62" x2="690" y2="420"/>
    <line x1="750" y1="86" x2="690" y2="420"/><line x1="846" y1="316" x2="690" y2="420"/>
    <line x1="150" y1="548" x2="690" y2="420"/><line x1="54" y1="316" x2="690" y2="420"/>
  </g>
  <path d="M300 250 Q520 300 676 408" fill="none" stroke="#ffe08a"
        stroke-width="3" stroke-dasharray="3 8"/>
  <circle cx="690" cy="420" r="13" fill="#c6f65a" stroke="#fff" stroke-width="3"/>
  <text x="450" y="628" text-anchor="middle" fill="#e7f3ec"
        font-size="30" font-weight="700">8–12 台摄像机 · 三角测量落点</text>
</svg>
"""

# The 2004 US Open quarter-final has no freely-licensed photograph (Commons
# categories and file search, Openverse, the Wikipedia articles' own image
# lists, official media and Flickr all come back empty). Rather than run a
# near-miss frame under it, beat 1 draws the incident itself: a ball down
# inside the line, called out.
_MISCALL_DIAGRAM = """
<svg viewBox="0 0 900 660" xmlns="http://www.w3.org/2000/svg">
  <rect x="90" y="60" width="720" height="320" rx="10" fill="rgba(55,226,154,.07)"
        stroke="rgba(55,226,154,.4)" stroke-width="3"/>
  <line x1="90" y1="380" x2="810" y2="380" stroke="#ffffff" stroke-width="12"/>
  <text x="112" y="106" fill="#9fb4aa" font-size="26" font-weight="700">界内</text>
  <text x="112" y="432" fill="#9fb4aa" font-size="26" font-weight="700">界外</text>
  <path d="M250 120 Q360 230 430 330" fill="none" stroke="#ffe08a"
        stroke-width="4" stroke-dasharray="4 10" opacity=".85"/>
  <circle cx="438" cy="344" r="26" fill="#c6f65a" stroke="#ffffff" stroke-width="4"/>
  <line x1="472" y1="344" x2="556" y2="344" stroke="#c6f65a" stroke-width="3"/>
  <text x="568" y="355" fill="#c6f65a" font-size="29" font-weight="800">球压线 · 界内</text>
  <g transform="translate(450,486)">
    <rect x="-150" y="-40" width="300" height="76" rx="38"
          fill="rgba(255,90,106,.16)" stroke="#ff5a6a" stroke-width="4"/>
    <text x="0" y="13" text-anchor="middle" fill="#ff5a6a"
          font-size="37" font-weight="800">判罚：OUT</text>
  </g>
  <text x="450" y="614" text-anchor="middle" fill="#e7f3ec"
        font-size="31" font-weight="700">2004 美网 1/4 决赛 · 小威 vs 卡普里亚蒂</text>
</svg>
"""


# The subject of this beat is a calendar, not a place — no photograph shows
# "seven of nine events grew to twelve days". Draw it instead, and label it.
_MASTERS_FORMAT_DIAGRAM = """
<svg viewBox="0 0 900 660" xmlns="http://www.w3.org/2000/svg">
  <text x="70" y="58" fill="#9fb4aa" font-size="27" font-weight="700">赛期</text>
  <text x="70" y="118" fill="#e7f3ec" font-size="30" font-weight="700">过去</text>
  <rect x="200" y="92" width="182" height="38" rx="6" fill="rgba(55,226,154,.35)"
        stroke="#37e29a" stroke-width="3"/>
  <text x="398" y="120" fill="#37e29a" font-size="29" font-weight="800">7 天</text>
  <text x="70" y="196" fill="#e7f3ec" font-size="30" font-weight="700">现在</text>
  <rect x="200" y="170" width="312" height="38" rx="6" fill="rgba(198,246,90,.30)"
        stroke="#c6f65a" stroke-width="3"/>
  <text x="528" y="198" fill="#c6f65a" font-size="29" font-weight="800">12 天</text>

  <line x1="70" y1="250" x2="830" y2="250" stroke="rgba(159,180,170,.35)" stroke-width="2"/>

  <text x="70" y="308" fill="#9fb4aa" font-size="27" font-weight="700">正赛签表</text>
  <text x="248" y="312" fill="#e7f3ec" font-size="44" font-weight="800">56</text>
  <text x="320" y="312" fill="#9fb4aa" font-size="36" font-weight="700">&#8594;</text>
  <text x="378" y="312" fill="#c6f65a" font-size="44" font-weight="800">96</text>
  <text x="452" y="312" fill="#9fb4aa" font-size="25" font-weight="700">人（2025 起）</text>

  <line x1="70" y1="352" x2="830" y2="352" stroke="rgba(159,180,170,.35)" stroke-width="2"/>

  <text x="70" y="412" fill="#9fb4aa" font-size="27" font-weight="700">九站大师赛</text>
  <g>
    <rect x="70"  y="446" width="72" height="52" rx="7" fill="rgba(198,246,90,.32)" stroke="#c6f65a" stroke-width="3"/>
    <rect x="156" y="446" width="72" height="52" rx="7" fill="rgba(198,246,90,.32)" stroke="#c6f65a" stroke-width="3"/>
    <rect x="242" y="446" width="72" height="52" rx="7" fill="rgba(198,246,90,.32)" stroke="#c6f65a" stroke-width="3"/>
    <rect x="328" y="446" width="72" height="52" rx="7" fill="rgba(198,246,90,.32)" stroke="#c6f65a" stroke-width="3"/>
    <rect x="414" y="446" width="72" height="52" rx="7" fill="rgba(198,246,90,.32)" stroke="#c6f65a" stroke-width="3"/>
    <rect x="500" y="446" width="72" height="52" rx="7" fill="rgba(198,246,90,.32)" stroke="#c6f65a" stroke-width="3"/>
    <rect x="586" y="446" width="72" height="52" rx="7" fill="rgba(198,246,90,.32)" stroke="#c6f65a" stroke-width="3"/>
    <rect x="672" y="446" width="72" height="52" rx="7" fill="none" stroke="#9fb4aa" stroke-width="3" stroke-dasharray="6 6"/>
    <rect x="758" y="446" width="72" height="52" rx="7" fill="none" stroke="#9fb4aa" stroke-width="3" stroke-dasharray="6 6"/>
  </g>
  <text x="70"  y="540" fill="#c6f65a" font-size="26" font-weight="800">7 站已改 12 天</text>
  <text x="600" y="540" fill="#9fb4aa" font-size="26" font-weight="700">2 站仍一周</text>
  <text x="450" y="614" text-anchor="middle" fill="#e7f3ec"
        font-size="29" font-weight="700">仍为一周的是：巴黎 · 蒙特卡洛</text>
</svg>
"""


# The whole argument of the "ten women's champions, five men's" deck is two
# lists side by side, and no photograph can hold two lists. Drawing it is not
# a fallback here — it *is* the evidence: ten rows of ten names against ten
# rows that collapse into five blocks. Every name is the champion the year's
# own Wikipedia article names (2016-2026; 2020 was cancelled, so ten).
_TEN_CHAMPIONS_DIAGRAM = """
<svg viewBox="0 0 900 700" xmlns="http://www.w3.org/2000/svg">
  <text x="70"  y="66" fill="#9fb4aa" font-size="26" font-weight="700">年份</text>
  <text x="196" y="66" fill="#c6f65a" font-size="27" font-weight="800">女单冠军</text>
  <text x="560" y="66" fill="#37e29a" font-size="27" font-weight="800">男单冠军</text>
  <line x1="70" y1="86" x2="830" y2="86" stroke="rgba(159,180,170,.35)" stroke-width="2"/>

  <g fill="rgba(231,243,236,.04)">
    <rect x="60" y="104" width="780" height="46"/>
    <rect x="60" y="196" width="780" height="46"/>
    <rect x="60" y="288" width="780" height="46"/>
    <rect x="60" y="380" width="780" height="46"/>
    <rect x="60" y="472" width="780" height="46"/>
  </g>

  <g fill="#9fb4aa" font-size="25" font-weight="700">
    <text x="70" y="136">2016</text>
    <text x="70" y="182">2017</text>
    <text x="70" y="228">2018</text>
    <text x="70" y="274">2019</text>
    <text x="70" y="320">2021</text>
    <text x="70" y="366">2022</text>
    <text x="70" y="412">2023</text>
    <text x="70" y="458">2024</text>
    <text x="70" y="504">2025</text>
    <text x="70" y="550">2026</text>
  </g>

  <g fill="#c6f65a">
    <circle cx="178" cy="129" r="5"/><circle cx="178" cy="175" r="5"/>
    <circle cx="178" cy="221" r="5"/><circle cx="178" cy="267" r="5"/>
    <circle cx="178" cy="313" r="5"/><circle cx="178" cy="359" r="5"/>
    <circle cx="178" cy="405" r="5"/><circle cx="178" cy="451" r="5"/>
    <circle cx="178" cy="497" r="5"/><circle cx="178" cy="543" r="5"/>
  </g>
  <g fill="#e7f3ec" font-size="27" font-weight="700">
    <text x="198" y="138">小威</text>
    <text x="198" y="184">穆古鲁扎</text>
    <text x="198" y="230">科贝尔</text>
    <text x="198" y="276">哈勒普</text>
    <text x="198" y="322">巴蒂</text>
    <text x="198" y="368">莱巴金娜</text>
    <text x="198" y="414">万卓索娃</text>
    <text x="198" y="460">克雷吉茨科娃</text>
    <text x="198" y="506">斯瓦泰克</text>
    <text x="198" y="552">诺斯科娃</text>
  </g>

  <!-- One box per man, spanning the years he held it: four boxes for
       Djokovic's four, two apiece for Alcaraz and Sinner. -->
  <g fill="rgba(55,226,154,.16)" stroke="#37e29a" stroke-width="3">
    <rect x="540" y="108" width="290" height="38" rx="7"/>
    <rect x="540" y="154" width="290" height="38" rx="7"/>
    <rect x="540" y="200" width="290" height="176" rx="7"/>
    <rect x="540" y="384" width="290" height="84" rx="7"/>
    <rect x="540" y="476" width="290" height="84" rx="7"/>
  </g>
  <g fill="#e7f3ec" font-size="27" font-weight="700" text-anchor="middle">
    <text x="685" y="136">穆雷</text>
    <text x="685" y="182">费德勒</text>
    <text x="685" y="297">德约科维奇 ×4</text>
    <text x="685" y="435">阿尔卡拉斯 ×2</text>
    <text x="685" y="527">辛纳 ×2</text>
  </g>

  <line x1="70" y1="584" x2="830" y2="584" stroke="rgba(159,180,170,.35)" stroke-width="2"/>
  <text x="198" y="634" fill="#c6f65a" font-size="33" font-weight="800">女单 10 个人</text>
  <text x="560" y="634" fill="#37e29a" font-size="33" font-weight="800">男单 5 个人</text>
  <text x="450" y="682" text-anchor="middle" fill="#9fb4aa"
        font-size="24" font-weight="700">2016-2026 共十届，2020 年停办</text>
</svg>
"""


# Two closures, both for "insufficient light", both in the first week of July,
# fifty minutes apart on the clock. No photograph can hold two timestamps side
# by side, so the argument is drawn: one axis, two markers, and the rule's own
# wording underneath. Only times confirmed on the record are plotted — the
# Sinner closure has no published clock time, so it is named in the narration
# instead of guessed at here.
_ROOF_DIAGRAM = """
<svg viewBox="0 0 900 620" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="40" text-anchor="middle" fill="#9fb4aa"
        font-size="27" font-weight="700">同样是「光线不足」，关顶时间差了 50 分钟</text>

  <line x1="90" y1="330" x2="810" y2="330" stroke="#9fb4aa" stroke-width="4"/>
  <g fill="#9fb4aa" font-size="24" font-weight="700" text-anchor="middle">
    <text x="90"  y="380">19:00</text>
    <text x="450" y="380">20:00</text>
    <text x="810" y="380">21:00</text>
  </g>
  <g stroke="#9fb4aa" stroke-width="3">
    <line x1="90" y1="316" x2="90" y2="344"/>
    <line x1="450" y1="316" x2="450" y2="344"/>
    <line x1="810" y1="316" x2="810" y2="344"/>
  </g>

  <!-- 2026-07-07, Djokovic v Auger-Aliassime: 19:40, before the third set -->
  <line x1="330" y1="168" x2="330" y2="330" stroke="#c6f65a" stroke-width="5"/>
  <circle cx="330" cy="330" r="13" fill="#c6f65a"/>
  <text x="330" y="152" text-anchor="middle" fill="#c6f65a"
        font-size="40" font-weight="800">19:40</text>
  <text x="330" y="110" text-anchor="middle" fill="#e7f3ec"
        font-size="25" font-weight="700">2026 · 德约 对 阿利亚西姆</text>
  <text x="330" y="204" text-anchor="middle" fill="#9fb4aa"
        font-size="23" font-weight="700">1/4 决赛，第三盘开始前</text>

  <!-- 2025-07-07, Dimitrov v Sinner: 20:30, after the second set -->
  <line x1="630" y1="330" x2="630" y2="470" stroke="#37e29a" stroke-width="5"/>
  <circle cx="630" cy="330" r="13" fill="#37e29a"/>
  <text x="630" y="516" text-anchor="middle" fill="#37e29a"
        font-size="40" font-weight="800">20:30</text>
  <text x="630" y="552" text-anchor="middle" fill="#e7f3ec"
        font-size="25" font-weight="700">2025 · 迪米特洛夫 对 辛纳</text>
  <text x="630" y="586" text-anchor="middle" fill="#9fb4aa"
        font-size="23" font-weight="700">第四轮，第二盘打完</text>

  <path d="M330 264 L630 264" stroke="#e7f3ec" stroke-width="3" stroke-dasharray="8 8"/>
  <text x="480" y="252" text-anchor="middle" fill="#e7f3ec"
        font-size="27" font-weight="800">相差 50 分钟</text>
</svg>
"""


# The whole point of the ball-change beat is that 7 and 9 are different
# numbers and the missing two games happened before the match started. A
# photograph of balls cannot say that; three rows of game boxes can, with the
# warm-up drawn as part of the first row.
_BALL_CHANGE_DIAGRAM = """
<svg viewBox="0 0 900 620" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="42" text-anchor="middle" fill="#9fb4aa"
        font-size="27" font-weight="700">一场比赛里，球什么时候换</text>

  <!-- first set of balls: the warm-up is drawn inside the row, because that
       is exactly where the two "missing" games went -->
  <rect x="70" y="96" width="118" height="58" rx="9" fill="none"
        stroke="#9fb4aa" stroke-width="3" stroke-dasharray="7 7"/>
  <text x="129" y="133" text-anchor="middle" fill="#9fb4aa"
        font-size="25" font-weight="700">热身</text>
  <g fill="rgba(55,226,154,.30)" stroke="#37e29a" stroke-width="3">
    <rect x="202" y="96" width="52" height="58" rx="8"/>
    <rect x="260" y="96" width="52" height="58" rx="8"/>
    <rect x="318" y="96" width="52" height="58" rx="8"/>
    <rect x="376" y="96" width="52" height="58" rx="8"/>
    <rect x="434" y="96" width="52" height="58" rx="8"/>
    <rect x="492" y="96" width="52" height="58" rx="8"/>
    <rect x="550" y="96" width="52" height="58" rx="8"/>
  </g>
  <text x="628" y="133" fill="#e7f3ec" font-size="30" font-weight="800">7 局</text>
  <text x="716" y="133" fill="#c6f65a" font-size="29" font-weight="800">→ 换球</text>

  <!-- second and third sets: nine clean games each -->
  <g fill="rgba(198,246,90,.28)" stroke="#c6f65a" stroke-width="3">
    <rect x="70"  y="266" width="52" height="58" rx="8"/>
    <rect x="128" y="266" width="52" height="58" rx="8"/>
    <rect x="186" y="266" width="52" height="58" rx="8"/>
    <rect x="244" y="266" width="52" height="58" rx="8"/>
    <rect x="302" y="266" width="52" height="58" rx="8"/>
    <rect x="360" y="266" width="52" height="58" rx="8"/>
    <rect x="418" y="266" width="52" height="58" rx="8"/>
    <rect x="476" y="266" width="52" height="58" rx="8"/>
    <rect x="534" y="266" width="52" height="58" rx="8"/>
  </g>
  <text x="612" y="303" fill="#e7f3ec" font-size="30" font-weight="800">9 局</text>
  <text x="700" y="303" fill="#c6f65a" font-size="29" font-weight="800">→ 换球</text>

  <g fill="rgba(198,246,90,.28)" stroke="#c6f65a" stroke-width="3">
    <rect x="70"  y="392" width="52" height="58" rx="8"/>
    <rect x="128" y="392" width="52" height="58" rx="8"/>
    <rect x="186" y="392" width="52" height="58" rx="8"/>
    <rect x="244" y="392" width="52" height="58" rx="8"/>
    <rect x="302" y="392" width="52" height="58" rx="8"/>
    <rect x="360" y="392" width="52" height="58" rx="8"/>
    <rect x="418" y="392" width="52" height="58" rx="8"/>
    <rect x="476" y="392" width="52" height="58" rx="8"/>
    <rect x="534" y="392" width="52" height="58" rx="8"/>
  </g>
  <text x="612" y="429" fill="#e7f3ec" font-size="30" font-weight="800">9 局</text>
  <text x="700" y="429" fill="#c6f65a" font-size="29" font-weight="800">→ 换球</text>

  <text x="70" y="192" fill="#9fb4aa" font-size="23" font-weight="700">第一批球从热身就开始磨</text>
  <text x="70" y="500" fill="#9fb4aa" font-size="23" font-weight="700">之后每一批都是净打九局</text>
  <text x="450" y="572" text-anchor="middle" fill="#e7f3ec"
        font-size="30" font-weight="800">首次 7 局，此后每 9 局</text>
</svg>
"""


# The whole argument of the shot-clock deck is *when the twenty-five seconds
# start*, and that is invisible: no photograph distinguishes a clock that
# began at the umpire's call from one that began the instant the point ended.
# Two axes, same length, different starting gun.
_SHOT_CLOCK_DIAGRAM = """
<svg viewBox="0 0 900 640" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="40" text-anchor="middle" fill="#9fb4aa"
        font-size="27" font-weight="700">25 秒没变，变的是从哪一秒开始数</text>

  <!-- 2018-2025: the clock is started by the chair umpire, after the call -->
  <text x="70" y="112" fill="#e7f3ec" font-size="27" font-weight="800">2018 起</text>
  <circle cx="150" cy="168" r="11" fill="#9fb4aa"/>
  <text x="150" y="146" text-anchor="middle" fill="#9fb4aa"
        font-size="22" font-weight="700">一分结束</text>
  <line x1="150" y1="168" x2="300" y2="168" stroke="#9fb4aa" stroke-width="4"
        stroke-dasharray="7 7"/>
  <text x="225" y="204" text-anchor="middle" fill="#9fb4aa"
        font-size="21" font-weight="700">掌声 · 主裁报分</text>
  <circle cx="300" cy="168" r="11" fill="#37e29a"/>
  <rect x="300" y="150" width="470" height="36" rx="8"
        fill="rgba(55,226,154,.28)" stroke="#37e29a" stroke-width="3"/>
  <text x="535" y="176" text-anchor="middle" fill="#37e29a"
        font-size="26" font-weight="800">25 秒</text>
  <text x="790" y="176" fill="#9fb4aa" font-size="22" font-weight="700">发球</text>

  <line x1="70" y1="250" x2="830" y2="250" stroke="rgba(159,180,170,.35)" stroke-width="2"/>

  <!-- 2026 ATP: automatic, and it starts at the point, not at the call -->
  <text x="70" y="308" fill="#e7f3ec" font-size="27" font-weight="800">2026 · ATP</text>
  <circle cx="150" cy="364" r="11" fill="#c6f65a"/>
  <text x="150" y="342" text-anchor="middle" fill="#c6f65a"
        font-size="22" font-weight="700">一分结束</text>
  <rect x="150" y="346" width="470" height="36" rx="8"
        fill="rgba(198,246,90,.28)" stroke="#c6f65a" stroke-width="3"/>
  <text x="385" y="372" text-anchor="middle" fill="#c6f65a"
        font-size="26" font-weight="800">25 秒</text>
  <text x="640" y="372" fill="#9fb4aa" font-size="22" font-weight="700">发球</text>
  <text x="150" y="416" fill="#9fb4aa" font-size="21" font-weight="700">全自动起算，不等报分</text>

  <path d="M300 214 L300 330" stroke="#ff5a6a" stroke-width="3" stroke-dasharray="7 7"/>
  <path d="M150 214 L150 330" stroke="#ff5a6a" stroke-width="3" stroke-dasharray="7 7"/>
  <text x="225" y="452" text-anchor="middle" fill="#ff5a6a"
        font-size="25" font-weight="800">少掉的就是这一段</text>

  <line x1="70" y1="490" x2="830" y2="490" stroke="rgba(159,180,170,.35)" stroke-width="2"/>
  <text x="70" y="548" fill="#9fb4aa" font-size="24" font-weight="700">超时罚则</text>
  <text x="240" y="548" fill="#e7f3ec" font-size="25" font-weight="800">第一次警告</text>
  <text x="440" y="548" fill="#9fb4aa" font-size="30" font-weight="700">&#8594;</text>
  <text x="490" y="548" fill="#ff5a6a" font-size="25" font-weight="800">之后每次罚掉一个一发</text>
  <text x="450" y="604" text-anchor="middle" fill="#e7f3ec"
        font-size="24" font-weight="700">大满贯此前是 20 秒，2018 年起统一为 25 秒</text>
</svg>
"""


# A preview, not an explainer, so the argument is a comparison across three
# years: two ranking lines that swap places, hung on the one match these two
# have already played. Nobody holds a photograph of a ranking, and the Asian
# Games semi-final is not in any reachable free archive either, so the beat
# that carries both is drawn.
_ZHENG_EALA_DIAGRAM = """
<svg viewBox="0 0 900 640" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="40" text-anchor="middle" fill="#e7f3ec"
        font-size="30" font-weight="800">三年里，两条线换了位置</text>

  <line x1="286" y1="76" x2="338" y2="76" stroke="#e0938f" stroke-width="7"/>
  <text x="348" y="85" fill="#e7f3ec" font-size="25" font-weight="800">郑钦文</text>
  <line x1="496" y1="76" x2="548" y2="76" stroke="#a8cf7d" stroke-width="7"/>
  <text x="558" y="85" fill="#e7f3ec" font-size="25" font-weight="800">伊埃拉</text>

  <g stroke="rgba(159,180,170,.18)" stroke-width="2">
    <line x1="150" y1="150" x2="810" y2="150"/>
    <line x1="150" y1="252" x2="810" y2="252"/>
    <line x1="150" y1="386" x2="810" y2="386"/>
  </g>
  <g fill="#9fb4aa" font-size="21" font-weight="700" text-anchor="end">
    <text x="138" y="157">第 4</text>
    <text x="138" y="259">第 28</text>
    <text x="138" y="393">第 100</text>
  </g>

  <line x1="150" y1="470" x2="810" y2="470" stroke="rgba(159,180,170,.40)" stroke-width="3"/>
  <g fill="#9fb4aa" font-size="22" font-weight="700" text-anchor="middle">
    <text x="200" y="504">2023</text>
    <text x="400" y="504">2024</text>
    <text x="600" y="504">2025</text>
    <text x="782" y="504">现在</text>
  </g>

  <path d="M200 440 L612 424" fill="none" stroke="#a8cf7d" stroke-width="5"
        stroke-dasharray="9 9" opacity=".45"/>
  <path d="M612 424 L782 252" fill="none" stroke="#a8cf7d" stroke-width="8"/>
  <circle cx="612" cy="424" r="9" fill="#a8cf7d"/>
  <circle cx="782" cy="252" r="14" fill="#a8cf7d" stroke="#061c14" stroke-width="4"/>
  <text x="602" y="452" text-anchor="end" fill="#9fb4aa"
        font-size="21" font-weight="700">2025 年 3 月 · 第 140</text>
  <text x="762" y="232" text-anchor="end" fill="#e7f3ec"
        font-size="27" font-weight="800">第 28 · 生涯新高</text>

  <path d="M200 214 L678 150" fill="none" stroke="#e0938f" stroke-width="8"/>
  <path d="M678 150 L752 430" fill="none" stroke="#e0938f" stroke-width="8"/>
  <path d="M752 430 L782 402" fill="none" stroke="#e0938f" stroke-width="8"/>
  <circle cx="200" cy="214" r="9" fill="#e0938f"/>
  <circle cx="678" cy="150" r="14" fill="#e0938f" stroke="#061c14" stroke-width="4"/>
  <circle cx="752" cy="430" r="8" fill="#e0938f" opacity=".55"/>
  <circle cx="782" cy="402" r="14" fill="#e0938f" stroke="#061c14" stroke-width="4"/>
  <text x="214" y="250" fill="#9fb4aa" font-size="21" font-weight="700">2023 年底 · 第 15</text>
  <text x="678" y="126" text-anchor="middle" fill="#e7f3ec"
        font-size="27" font-weight="800">生涯最高 第 4</text>
  <text x="782" y="456" text-anchor="middle" fill="#e7f3ec"
        font-size="26" font-weight="800">跌出前 100</text>

  <text x="450" y="572" text-anchor="middle" fill="#e7f3ec"
        font-size="25" font-weight="800">线尾那一小段，是两周前的雅典八强</text>
  <text x="450" y="612" text-anchor="middle" fill="#9fb4aa"
        font-size="20" font-weight="700">7 月 27 日是两人第二次交手 · 标注点均为公开排名</text>
</svg>
"""

# A losing streak is the one thing in this deck no photograph can hold: it is
# not a moment, it is the absence of moments. Drawing it also puts the two
# facts that matter side by side — her last win and the start of the streak
# happened at the same tournament, one round apart.
_VENUS_STREAK_DIAGRAM = """
<svg viewBox="0 0 900 580" xmlns="http://www.w3.org/2000/svg">
  <text x="52" y="44" fill="#e7f3ec" font-size="38" font-weight="800">那场胜利之后，十一连败</text>
  <text x="52" y="80" fill="#a9bcb2" font-size="23" font-weight="700">条长＝这一场她拿到的局数占比</text>

  <text x="450" y="110" text-anchor="middle" fill="#a9bcb2"
        font-size="21" font-weight="700">一半</text>
  <line x1="450" y1="120" x2="450" y2="368" stroke="rgba(199,216,208,.5)"
        stroke-width="2" stroke-dasharray="7 7"/>

  <text x="52" y="164" fill="#e7f3ec" font-size="30" font-weight="800">2025.7.22 华盛顿首轮</text>
  <text x="848" y="164" text-anchor="end" fill="#a8cf7d" font-size="30" font-weight="800">6-3 6-4</text>
  <rect x="52" y="180" width="796" height="44" rx="22" fill="rgba(231,243,236,.10)"/>
  <rect x="52" y="180" width="503" height="44" rx="22" fill="#a8cf7d"/>

  <text x="52" y="300" fill="#e7f3ec" font-size="30" font-weight="800">2026.1 奥克兰 · 利内特</text>
  <text x="848" y="300" text-anchor="end" fill="#e7f3ec" font-size="30" font-weight="800">4-6 6-4 2-6</text>
  <rect x="52" y="316" width="796" height="44" rx="22" fill="rgba(231,243,236,.10)"/>
  <rect x="52" y="316" width="341" height="44" rx="22" fill="rgba(231,243,236,.42)"/>

  <text x="52" y="410" fill="#a9bcb2" font-size="24" font-weight="700">
    这是有公开比分的几场里，她咬得最紧的一场
  </text>
  <text x="52" y="444" fill="#a9bcb2" font-size="24" font-weight="700">
    其余各场——辛辛那提、美网、澳网、迈阿密、洪堡——均止步首轮
  </text>

  <rect x="40" y="478" width="820" height="80" rx="14"
        fill="none" stroke="rgba(231,243,236,.6)" stroke-width="3" stroke-dasharray="10 8"/>
  <text x="64" y="516" fill="#e7f3ec" font-size="30" font-weight="800">2026.7.27 华盛顿首轮</text>
  <text x="64" y="546" fill="#a9bcb2" font-size="22" font-weight="700">又是这一站</text>
  <text x="832" y="532" text-anchor="end" fill="#e7f3ec" font-size="46" font-weight="800">？</text>
</svg>
"""

# 「一百二十八个签位怎么分」这件事没有任何一张照片能表达：签表照片能证明
# 某一行写着 WC（那一屏就用照片），但拍不出 104/16/8 这个比例，更拍不出
# 「换成 108+12 或 112+8，外卡那一栏纹丝不动」。规则书 Z.2.e 的构成表本身
# 就是一张图，画出来比念三串数字快得多。
#
# 一屏一个强调色：只有外卡那一段给品牌绿，其余两段一律中性半透明白，靠
# 长度说话；条上一个字都不写，算式写在条的上一行。
_DRAW_SPLIT_DIAGRAM = """
<svg viewBox="0 0 900 580" xmlns="http://www.w3.org/2000/svg">
  <text x="52" y="46" fill="#e7f3ec" font-size="38" font-weight="800">128 个签位，规则书给了三种分法</text>
  <text x="52" y="82" fill="#a9bcb2" font-size="24" font-weight="700">条长＝签位数　绿色＝外卡</text>

  <line x1="795" y1="104" x2="795" y2="474" stroke="rgba(199,216,208,.55)"
        stroke-width="2" stroke-dasharray="8 8"/>

  <text x="52" y="152" fill="#e7f3ec" font-size="30" font-weight="800">直接进入 104　＋　资格赛 16　＋　外卡 8</text>
  <rect x="52"  y="164" width="641" height="54" rx="10" fill="rgba(231,243,236,.34)"/>
  <rect x="701" y="164" width="89"  height="54" rx="10" fill="rgba(231,243,236,.15)"
        stroke="rgba(231,243,236,.34)" stroke-width="1.5"/>
  <rect x="800" y="164" width="48"  height="54" rx="10" fill="#a8cf7d"/>

  <text x="52" y="272" fill="#e7f3ec" font-size="30" font-weight="800">直接进入 108　＋　资格赛 12　＋　外卡 8</text>
  <rect x="52"  y="284" width="666" height="54" rx="10" fill="rgba(231,243,236,.34)"/>
  <rect x="726" y="284" width="64"  height="54" rx="10" fill="rgba(231,243,236,.15)"
        stroke="rgba(231,243,236,.34)" stroke-width="1.5"/>
  <rect x="800" y="284" width="48"  height="54" rx="10" fill="#a8cf7d"/>

  <text x="52" y="392" fill="#e7f3ec" font-size="30" font-weight="800">直接进入 112　＋　资格赛 8　＋　外卡 8</text>
  <rect x="52"  y="404" width="690" height="54" rx="10" fill="rgba(231,243,236,.34)"/>
  <rect x="750" y="404" width="40"  height="54" rx="10" fill="rgba(231,243,236,.15)"
        stroke="rgba(231,243,236,.34)" stroke-width="1.5"/>
  <rect x="800" y="404" width="48"  height="54" rx="10" fill="#a8cf7d"/>

  <text x="52" y="514" fill="#a9bcb2" font-size="25" font-weight="700">
    前两栏一直在变，外卡那一栏三种分法都是 8
  </text>
  <text x="52" y="550" fill="#a9bcb2" font-size="25" font-weight="700">
    资格赛签表另发 8–9 张；一届大满贯发出去的外卡，三十张出头
  </text>
</svg>
"""

# 「空出来的位置给谁」——**照片讲不清的那一类**：它是一条按时刻分岔的流程，
# 不是一个能被拍下来的瞬间。两条路的判据是同一个时刻（资格赛打完那一刻正赛空没空），
# 所以画成一条主干往下分叉。一屏一个强调色：只有「抽签」那一支给品牌绿。
_LUCKY_LOSER_PICK_DIAGRAM = """
<svg viewBox="0 0 900 580" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">资格赛打完那一刻，正赛空没空</text>

  <path d="M450 70 L450 150 M210 150 L690 150 M210 150 L210 190 M690 150 L690 190"
        stroke="#9fb4aa" stroke-width="4" fill="none"/>

  <text x="210" y="232" text-anchor="middle" fill="#9fb4aa"
        font-size="28" font-weight="700">还没空出来</text>
  <text x="690" y="232" text-anchor="middle" fill="#c6f65a"
        font-size="28" font-weight="700">已经空着了</text>
  <text x="210" y="282" text-anchor="middle" fill="#e7f3ec"
        font-size="33" font-weight="800">按排名排队</text>
  <text x="690" y="282" text-anchor="middle" fill="#e7f3ec"
        font-size="33" font-weight="800">前两名抽签</text>

  <rect x="96"  y="316" width="228" height="54" rx="10" fill="rgba(231,243,236,.34)"/>
  <rect x="96"  y="384" width="228" height="54" rx="10" fill="rgba(231,243,236,.12)"
        stroke="rgba(231,243,236,.30)" stroke-width="1.5"/>
  <rect x="96"  y="452" width="228" height="54" rx="10" fill="rgba(231,243,236,.12)"
        stroke="rgba(231,243,236,.30)" stroke-width="1.5"/>
  <text x="210" y="552" text-anchor="middle" fill="#9fb4aa"
        font-size="27" font-weight="700">排最前的那个进</text>

  <rect x="576" y="316" width="106" height="54" rx="10" fill="rgba(231,243,236,.12)"
        stroke="#c6f65a" stroke-width="2"/>
  <rect x="698" y="316" width="106" height="54" rx="10" fill="rgba(231,243,236,.12)"
        stroke="#c6f65a" stroke-width="2"/>
  <path d="M629 378 L690 430 M751 378 L690 430" stroke="#9fb4aa"
        stroke-width="3" fill="none" stroke-dasharray="7 7"/>
  <rect x="637" y="436" width="106" height="54" rx="10" fill="#c6f65a"/>
  <text x="690" y="552" text-anchor="middle" fill="#c6f65a"
        font-size="27" font-weight="700">抽中的那个进</text>
</svg>
"""

# 「大满贯七轮，第四轮到顶」——同样拍不出来：它是一个**没有发生过**的纪录。
# 条上一个字都不写（轮次标在条的上一行），一屏一个强调色。
_LUCKY_LOSER_WALL_DIAGRAM = """
<svg viewBox="0 0 900 520" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">大满贯打七轮，他们最远只到第四轮</text>
  <text x="450" y="90" text-anchor="middle" fill="#9fb4aa"
        font-size="27" font-weight="700">绿色＝有人到过　空格＝至今没有人</text>

  <g fill="#9fb4aa" font-size="26" font-weight="700" text-anchor="middle">
    <text x="118" y="186">首轮</text>
    <text x="228" y="186">2 轮</text>
    <text x="338" y="186">3 轮</text>
    <text x="448" y="186">4 轮</text>
    <text x="562" y="186">8 强</text>
    <text x="672" y="186">4 强</text>
    <text x="782" y="186">决赛</text>
  </g>

  <rect x="68"  y="206" width="100" height="88" rx="12" fill="#c6f65a"/>
  <rect x="178" y="206" width="100" height="88" rx="12" fill="#c6f65a"/>
  <rect x="288" y="206" width="100" height="88" rx="12" fill="#c6f65a"/>
  <rect x="398" y="206" width="100" height="88" rx="12" fill="#c6f65a"/>
  <rect x="512" y="206" width="100" height="88" rx="12" fill="rgba(231,243,236,.10)"
        stroke="rgba(231,243,236,.34)" stroke-width="2"/>
  <rect x="622" y="206" width="100" height="88" rx="12" fill="rgba(231,243,236,.10)"
        stroke="rgba(231,243,236,.34)" stroke-width="2"/>
  <rect x="732" y="206" width="100" height="88" rx="12" fill="rgba(231,243,236,.10)"
        stroke="rgba(231,243,236,.34)" stroke-width="2"/>

  <line x1="505" y1="190" x2="505" y2="310" stroke="#e7f3ec"
        stroke-width="4" stroke-dasharray="10 8"/>
  <text x="505" y="352" text-anchor="middle" fill="#e7f3ec"
        font-size="31" font-weight="800">这条线还没人越过</text>

  <text x="450" y="430" text-anchor="middle" fill="#9fb4aa"
        font-size="27" font-weight="700">摸到第 4 轮的：1995 诺曼 · 2023 阿瓦涅相</text>
  <text x="450" y="472" text-anchor="middle" fill="#9fb4aa"
        font-size="27" font-weight="700">2025 利斯 · 2025 谢拉 · 2026 德容</text>
</svg>
"""


#: 「保护排名」到底替你做什么、不替你做什么。这件事没有任何一张照片能表达——
#: 它是一张权限表，不是一个瞬间。两栏对照，只给"能用"那一栏上品牌绿。
_PR_SCOPE_DIAGRAM = """
<svg viewBox="0 0 900 520" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">它替你报名，别的一概不管</text>
  <text x="450" y="90" text-anchor="middle" fill="#9fb4aa"
        font-size="27" font-weight="700">绿色＝可以用它　空格＝一律按真实排名</text>

  <text x="245" y="156" text-anchor="middle" fill="#c6f65a"
        font-size="30" font-weight="800">能用</text>
  <text x="655" y="156" text-anchor="middle" fill="#9fb4aa"
        font-size="30" font-weight="800">不能用</text>

  <rect x="70" y="182" width="350" height="76" rx="12" fill="#c6f65a"/>
  <text x="245" y="230" text-anchor="middle" fill="#0d2a1c"
        font-size="29" font-weight="800">报名正赛</text>
  <rect x="70" y="272" width="350" height="76" rx="12" fill="#c6f65a"/>
  <text x="245" y="320" text-anchor="middle" fill="#0d2a1c"
        font-size="29" font-weight="800">报名资格赛</text>
  <rect x="70" y="362" width="350" height="76" rx="12" fill="#c6f65a"/>
  <text x="245" y="410" text-anchor="middle" fill="#0d2a1c"
        font-size="29" font-weight="800">特殊豁免位</text>

  <rect x="480" y="182" width="350" height="76" rx="12" fill="rgba(231,243,236,.10)"
        stroke="rgba(231,243,236,.34)" stroke-width="2"/>
  <text x="655" y="230" text-anchor="middle" fill="#e7f3ec"
        font-size="29" font-weight="800">种子</text>
  <rect x="480" y="272" width="350" height="76" rx="12" fill="rgba(231,243,236,.10)"
        stroke="rgba(231,243,236,.34)" stroke-width="2"/>
  <text x="655" y="320" text-anchor="middle" fill="#e7f3ec"
        font-size="29" font-weight="800">幸运落败者顺位</text>
  <rect x="480" y="362" width="350" height="76" rx="12" fill="rgba(231,243,236,.10)"
        stroke="rgba(231,243,236,.34)" stroke-width="2"/>
  <text x="655" y="410" text-anchor="middle" fill="#e7f3ec"
        font-size="29" font-weight="800">你的世界排名</text>

  <text x="450" y="490" text-anchor="middle" fill="#9fb4aa"
        font-size="27" font-weight="700">ATP 规则书原话：for Entry, Not Seeding</text>
</svg>
"""

#: 26 周为什么不能拆。两截各自量、各自不够，而合计比门槛还多——
#: 这个"加起来够了却一分不算"只有并排画出来才一眼看得懂。
#: 横轴 0–32 周映射到 x 150–780，即 1 周 ≈ 19.7px；26 周落在 x=662。
_PR_GAP_DIAGRAM = """
<svg viewBox="0 0 900 560" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="48" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">26 周必须是连着的一段</text>
  <text x="450" y="92" text-anchor="middle" fill="#9fb4aa"
        font-size="27" font-weight="700">虚线＝门槛　中网那两场把它切成了两截</text>

  <text x="60" y="162" fill="#9fb4aa" font-size="27" font-weight="700">温网结束 → 中网复出</text>
  <rect x="60" y="180" width="211" height="86" rx="12" fill="rgba(231,243,236,.18)"
        stroke="rgba(231,243,236,.38)" stroke-width="2"/>
  <text x="291" y="236" fill="#e7f3ec" font-size="30" font-weight="800">10.7 周</text>

  <text x="60" y="322" fill="#9fb4aa" font-size="27" font-weight="700">中网结束 → 多哈复出</text>
  <rect x="60" y="340" width="357" height="86" rx="12" fill="rgba(231,243,236,.18)"
        stroke="rgba(231,243,236,.38)" stroke-width="2"/>
  <text x="437" y="396" fill="#e7f3ec" font-size="30" font-weight="800">18.1 周</text>

  <line x1="572" y1="150" x2="572" y2="446" stroke="#e7f3ec"
        stroke-width="4" stroke-dasharray="10 8"/>
  <text x="572" y="484" text-anchor="middle" fill="#e7f3ec"
        font-size="30" font-weight="800">26 周</text>

  <text x="450" y="538" text-anchor="middle" fill="#c6f65a"
        font-size="32" font-weight="800">两截加起来 28.8 周，一分不算</text>
</svg>
"""


#: 手术之后那个春天，德约科维奇的排名一路往下。照片拍不出「排名」，
#: 而这条片子的第一段全靠这个数字的分量——12 年来第一次跌出前 20。
_MIDDLE_FALL_DIAGRAM = """
<svg viewBox="0 0 900 520" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">手术之后的那个春天</text>
  <text x="450" y="90" text-anchor="middle" fill="#9fb4aa"
        font-size="27" font-weight="700">他的世界排名，2018 年 2 月到 5 月</text>

  <polyline points="120,160 300,160 300,250 520,250 520,340 780,340"
            fill="none" stroke="#c6f65a" stroke-width="7"
            stroke-linejoin="round" stroke-linecap="round"/>
  <circle cx="120" cy="160" r="11" fill="#c6f65a"/>
  <circle cx="300" cy="250" r="11" fill="#c6f65a"/>
  <circle cx="520" cy="340" r="11" fill="#c6f65a"/>
  <circle cx="780" cy="340" r="13" fill="#c6f65a"/>

  <text x="120" y="140" fill="#e7f3ec" font-size="29" font-weight="800">第 14</text>
  <text x="300" y="300" fill="#e7f3ec" font-size="29" font-weight="800">第 18</text>
  <text x="540" y="392" fill="#e7f3ec" font-size="29" font-weight="800">第 22</text>

  <text x="120" y="440" fill="#9fb4aa" font-size="26" font-weight="700">2 月动刀</text>
  <text x="272" y="440" fill="#9fb4aa" font-size="26" font-weight="700">马德里</text>
  <text x="492" y="440" fill="#9fb4aa" font-size="26" font-weight="700">罗马</text>

  <text x="450" y="496" text-anchor="middle" fill="#e7f3ec"
        font-size="31" font-weight="800">上一次跌出前 20，是 2006 年 10 月</text>
</svg>
"""

#: 两条轨迹并排。这是整条片子的论点，而且**没有任何一张照片能表达**——
#: 它要同时呈现两个人、四年时间，以及「中段重叠」这件事本身。
#: 一屏一个强调色：回来的那条给品牌绿，没回来的那条留中性白。
_MIDDLE_SAME_DIAGRAM = """
<svg viewBox="0 0 900 500" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">两条路，前半段一模一样</text>
  <text x="450" y="90" text-anchor="middle" fill="#9fb4aa"
        font-size="27" font-weight="700">横轴＝手术之后过了多久</text>

  <rect x="96" y="126" width="212" height="286" rx="14"
        fill="rgba(231,243,236,.10)" stroke="rgba(231,243,236,.30)" stroke-width="2"/>
  <text x="202" y="176" text-anchor="middle" fill="#e7f3ec"
        font-size="28" font-weight="800">这一段</text>
  <text x="202" y="214" text-anchor="middle" fill="#e7f3ec"
        font-size="28" font-weight="800">分不出来</text>

  <polyline points="120,340 200,398 292,376 470,254 700,220 812,220"
            fill="none" stroke="#c6f65a" stroke-width="7"
            stroke-linejoin="round" stroke-linecap="round"/>
  <text x="612" y="166" fill="#c6f65a" font-size="30" font-weight="800">德约科维奇</text>
  <text x="612" y="202" fill="#c6f65a" font-size="26" font-weight="700">拿了温网</text>

  <polyline points="120,340 200,398 294,380 434,326 566,356 700,414 812,420"
            fill="none" stroke="rgba(231,243,236,.62)" stroke-width="7"
            stroke-dasharray="14 10" stroke-linejoin="round" stroke-linecap="round"/>
  <text x="640" y="326" fill="#e7f3ec" font-size="30" font-weight="800">锦织圭</text>
  <text x="640" y="362" fill="#9fb4aa" font-size="26" font-weight="700">再没回去</text>

  <text x="112" y="466" fill="#9fb4aa" font-size="26" font-weight="700">动刀</text>
  <text x="424" y="466" fill="#9fb4aa" font-size="26" font-weight="700">半年</text>
  <text x="676" y="466" fill="#9fb4aa" font-size="26" font-weight="700">三四年</text>
</svg>
"""


#: 老规矩里的「打够了就可以少打」——2022 版 ATP 规则书 1.08，逐字：
#: `A player's number of ATP Tour Masters 1000 commitment tournaments shall be
#: reduced by one (1) tournament for reaching each of the following milestones:
#: 600 matches / 12 years of service / 30 years of age`，接着一句
#: `If all three (3) conditions are met then the player has a complete exemption`。
#: **注意最后一档不是 8−3＝5，是直接归零**——这个跳跃是文字列不出来的，
#: 三根条一比就看见：前两档只少一站，第三档整条空掉。
#: 几何：横轴 0–8 站映射到 x 250–810，即 1 站 = 70px。
_EXEMPTION_LADDER_DIAGRAM = """
<svg viewBox="0 0 900 560" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">打够了，就可以少打</text>
  <text x="450" y="92" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">三条里程碑：正赛 600 场　服务 12 年　年满 30 岁</text>

  <text x="250" y="136" fill="#9fb4aa" font-size="24" font-weight="700">本来要打的 8 站</text>

  <text x="60" y="196" fill="#9fb4aa" font-size="28" font-weight="700">达成 1 条</text>
  <rect x="250" y="154" width="500" height="62" rx="10" fill="rgba(231,243,236,.08)"
        stroke="rgba(231,243,236,.22)" stroke-width="2"/>
  <rect x="250" y="154" width="438" height="62" rx="10" fill="rgba(231,243,236,.32)"/>
  <text x="870" y="196" text-anchor="end" fill="#e7f3ec"
        font-size="30" font-weight="800">7 站</text>

  <text x="60" y="294" fill="#9fb4aa" font-size="28" font-weight="700">达成 2 条</text>
  <rect x="250" y="252" width="500" height="62" rx="10" fill="rgba(231,243,236,.08)"
        stroke="rgba(231,243,236,.22)" stroke-width="2"/>
  <rect x="250" y="252" width="375" height="62" rx="10" fill="rgba(231,243,236,.32)"/>
  <text x="870" y="294" text-anchor="end" fill="#e7f3ec"
        font-size="30" font-weight="800">6 站</text>

  <text x="60" y="392" fill="#c6f65a" font-size="28" font-weight="800">三条全占</text>
  <rect x="250" y="350" width="500" height="62" rx="10" fill="none"
        stroke="#c6f65a" stroke-width="3" stroke-dasharray="12 9"/>
  <text x="870" y="392" text-anchor="end" fill="#c6f65a"
        font-size="30" font-weight="800">0 站</text>

  <text x="450" y="470" text-anchor="middle" fill="#9fb4aa"
        font-size="25" font-weight="700">2023 年起 ATP 取消了这套，只有 2022 年底前挣到的人还留着</text>
  <text x="450" y="532" text-anchor="middle" fill="#c6f65a"
        font-size="32" font-weight="800">可它管的是「用不用报名」</text>
</svg>
"""


#: 缺席强制大师赛的奖金池扣减阶梯（ATP 2026 规则书 1.08.H.1.f 的那张表）。
#: 照片拍不出「罚了多少」，而这条片子的全部落点就是那个数。
#: 深色＝无论如何都要扣的，浅色＝到场做推广活动能拿回来的——规则书给的三档是
#: 缺 1 站 25%→12.5%（做 1 次）、缺 2 站 50%→25%（做 2 次）、缺 3 站 75%→50%，
#: 缺 4 站及以上一律 100% 且没有减免。**浅色那截越往下越短，到第四行归零**，
#: 这一层「越躲越买不回来」是文字列不出来的，画出来才一眼看见。
#: 几何：横轴 0–100% 映射到 x 210–730，即 1% = 5.2px。
_MANDATORY_BILL_DIAGRAM = """
<svg viewBox="0 0 900 570" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">缺席强制赛，奖金池扣多少</text>
  <text x="450" y="92" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">深色＝一定要扣的　浅色＝到场做推广能拿回来的</text>

  <text x="60" y="212" fill="#9fb4aa" font-size="28" font-weight="700">缺 1 站</text>
  <rect x="210" y="170" width="65" height="62" rx="10" fill="rgba(231,243,236,.30)"/>
  <rect x="275" y="170" width="65" height="62" rx="10" fill="rgba(231,243,236,.10)"
        stroke="rgba(231,243,236,.30)" stroke-width="2" stroke-dasharray="8 6"/>
  <text x="870" y="212" text-anchor="end" fill="#e7f3ec"
        font-size="30" font-weight="800">−25%</text>

  <text x="60" y="296" fill="#9fb4aa" font-size="28" font-weight="700">缺 2 站</text>
  <rect x="210" y="254" width="130" height="62" rx="10" fill="rgba(231,243,236,.30)"/>
  <rect x="340" y="254" width="130" height="62" rx="10" fill="rgba(231,243,236,.10)"
        stroke="rgba(231,243,236,.30)" stroke-width="2" stroke-dasharray="8 6"/>
  <text x="870" y="296" text-anchor="end" fill="#e7f3ec"
        font-size="30" font-weight="800">−50%</text>

  <text x="60" y="380" fill="#9fb4aa" font-size="28" font-weight="700">缺 3 站</text>
  <rect x="210" y="338" width="260" height="62" rx="10" fill="rgba(231,243,236,.30)"/>
  <rect x="470" y="338" width="130" height="62" rx="10" fill="rgba(231,243,236,.10)"
        stroke="rgba(231,243,236,.30)" stroke-width="2" stroke-dasharray="8 6"/>
  <text x="870" y="380" text-anchor="end" fill="#e7f3ec"
        font-size="30" font-weight="800">−75%</text>

  <text x="60" y="464" fill="#9fb4aa" font-size="28" font-weight="700">缺 4 站</text>
  <rect x="210" y="422" width="520" height="62" rx="10" fill="rgba(231,243,236,.30)"/>
  <text x="870" y="464" text-anchor="end" fill="#e7f3ec"
        font-size="30" font-weight="800">−100%</text>

  <text x="450" y="548" text-anchor="middle" fill="#c6f65a"
        font-size="32" font-weight="800">排名那一笔记 0，推广活动一分赎不回</text>
</svg>
"""


#: 三条报名截止线。条文写在两本规则书里（WTA 2026 第三节、ATP 2026 的 7.03），
#: 大满贯六周、巡回赛正赛四周、资格赛三周——**条越长＝要提前越久报名**。
#: 照片拍不出「一条画在六周之前的线」，而这条片子的全部落点就是那条线。
#: 几何：赛事周周一钉在 x=800，往左每周 90px。
_ENTRY_DEADLINE_DIAGRAM = """
<svg viewBox="0 0 900 500" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">名单在开赛前多久就定了</text>
  <text x="450" y="90" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">条越长＝要提前越久报名</text>

  <text x="60" y="176" fill="#c6f65a" font-size="28" font-weight="800">大满贯正赛</text>
  <rect x="260" y="140" width="540" height="54" rx="10" fill="rgba(198,246,90,.26)"
        stroke="#c6f65a" stroke-width="2"/>
  <text x="272" y="176" fill="#c6f65a" font-size="30" font-weight="800">6 周</text>

  <text x="60" y="266" fill="#9fb4aa" font-size="28" font-weight="700">巡回赛正赛</text>
  <rect x="440" y="230" width="360" height="54" rx="10" fill="rgba(231,243,236,.28)"/>
  <text x="452" y="266" fill="#e7f3ec" font-size="30" font-weight="800">4 周</text>

  <text x="60" y="356" fill="#9fb4aa" font-size="28" font-weight="700">资格赛</text>
  <rect x="530" y="320" width="270" height="54" rx="10" fill="rgba(231,243,236,.28)"/>
  <text x="542" y="356" fill="#e7f3ec" font-size="30" font-weight="800">3 周</text>

  <line x1="800" y1="120" x2="800" y2="394" stroke="#e7f3ec" stroke-width="3"/>
  <text x="800" y="112" text-anchor="end" fill="#9fb4aa"
        font-size="24" font-weight="700">赛事周周一</text>

  <text x="450" y="472" text-anchor="middle" fill="#c6f65a"
        font-size="32" font-weight="800">之后涨的用不上，跌的也不还</text>
</svg>
"""


#: 2026 美网那张名单在 7 月 20 日那天的样子。一条排名轴、一道直入线、三个点——
#: 「差了 22 位」和「差了 46 位」这种距离感，文字列不出来，画出来一眼就看见。
#: 几何：排名 1 在 x=180，排名 160 在 x=820，即 1 位 = 4.025px。
_ENTRY_CUTLINE_DIAGRAM = """
<svg viewBox="0 0 900 470" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">7 月 20 日那天的男子名单</text>
  <text x="450" y="90" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">虚线左边直入正赛，右边不在名单上</text>

  <line x1="180" y1="250" x2="820" y2="250" stroke="rgba(231,243,236,.30)" stroke-width="4"/>
  <text x="180" y="300" text-anchor="middle" fill="#9fb4aa" font-size="24" font-weight="700">第 1</text>

  <line x1="582" y1="150" x2="582" y2="330" stroke="#c6f65a"
        stroke-width="4" stroke-dasharray="11 8"/>
  <text x="582" y="138" text-anchor="middle" fill="#c6f65a"
        font-size="30" font-weight="800">直入线 101</text>

  <circle cx="582" cy="250" r="12" fill="#c6f65a"/>
  <text x="560" y="300" text-anchor="end" fill="#e7f3ec" font-size="24" font-weight="700">科梅萨尼亚</text>

  <circle cx="671" cy="250" r="12" fill="rgba(231,243,236,.72)"/>
  <text x="671" y="358" text-anchor="middle" fill="#e7f3ec" font-size="26" font-weight="800">郑钦文 123</text>

  <circle cx="768" cy="250" r="12" fill="rgba(231,243,236,.72)"/>
  <text x="768" y="300" text-anchor="middle" fill="#e7f3ec" font-size="26" font-weight="800">德雷珀 147</text>

  <text x="450" y="440" text-anchor="middle" fill="#c6f65a"
        font-size="32" font-weight="800">名单只认这一天的排名</text>
</svg>
"""


#: 同一周、同一片大陆的两站，种子表并排。**这一屏要一眼推翻的是「低级别对手更强」**——
#: ATP250 的 8 号种子比挑战赛的 1 号种子还高 36 位。照片拍不出「一张签表有多深」。
#: 几何：排名 1 在 x=150，排名 160 在 x=830，即 1 位 = 4.25px。
_CLIMB_FIELD_DIAGRAM = """
<svg viewBox="0 0 900 540" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">同一周，两站的种子有多强</text>
  <text x="450" y="90" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">左边＝排名越高　每条的两端是 1 号种子和 8 号种子</text>

  <text x="60" y="164" fill="#c6f65a" font-size="27" font-weight="800">ATP250 洛斯卡沃斯</text>
  <line x1="197" y1="196" x2="435" y2="196" stroke="#c6f65a" stroke-width="9" stroke-linecap="round"/>
  <circle cx="197" cy="196" r="10" fill="#c6f65a"/><circle cx="435" cy="196" r="10" fill="#c6f65a"/>
  <text x="197" y="234" text-anchor="middle" fill="#c6f65a" font-size="25" font-weight="800">12</text>
  <text x="435" y="234" text-anchor="middle" fill="#c6f65a" font-size="25" font-weight="800">67</text>

  <text x="60" y="288" fill="#9fb4aa" font-size="27" font-weight="700">挑战赛 125 温哥华</text>
  <line x1="583" y1="320" x2="783" y2="320" stroke="rgba(231,243,236,.72)" stroke-width="9" stroke-linecap="round"/>
  <circle cx="583" cy="320" r="10" fill="rgba(231,243,236,.72)"/><circle cx="783" cy="320" r="10" fill="rgba(231,243,236,.72)"/>
  <text x="583" y="358" text-anchor="middle" fill="#e7f3ec" font-size="25" font-weight="800">103</text>
  <text x="783" y="358" text-anchor="middle" fill="#e7f3ec" font-size="25" font-weight="800">150</text>

  <line x1="435" y1="180" x2="435" y2="336" stroke="rgba(198,246,90,.45)"
        stroke-width="3" stroke-dasharray="9 7"/>
  <line x1="583" y1="180" x2="583" y2="336" stroke="rgba(231,243,236,.35)"
        stroke-width="3" stroke-dasharray="9 7"/>
  <text x="509" y="410" text-anchor="middle" fill="#e7f3ec"
        font-size="27" font-weight="800">差 36 位</text>
  <text x="509" y="446" text-anchor="middle" fill="#9fb4aa"
        font-size="24" font-weight="700">两条中间没有交叠</text>

  <text x="450" y="512" text-anchor="middle" fill="#c6f65a"
        font-size="32" font-weight="800">低级别的对手，其实没有更强</text>
</svg>
"""


#: 兑换率。同样是「赢五场」，在挑战赛换 125 分，而在 ATP250 只要赢两场就有 100。
#: 这一层是纯算术，照片讲不出来。条越长＝分越多；括号里是要赢几场。
#: 几何：0–260 分映射到 x 300–830，即 1 分 ≈ 2.04px。
_CLIMB_POINTS_DIAGRAM = """
<svg viewBox="0 0 900 520" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">同样的力气，换来的分不一样</text>
  <text x="450" y="90" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">条越长＝分越多　左边括号里是要赢几场</text>

  <text x="60" y="176" fill="#9fb4aa" font-size="26" font-weight="700">挑战赛 125 冠军（赢 5 场）</text>
  <rect x="300" y="196" width="255" height="52" rx="10" fill="rgba(231,243,236,.30)"/>
  <text x="573" y="234" fill="#e7f3ec" font-size="29" font-weight="800">125 分</text>

  <text x="60" y="300" fill="#c6f65a" font-size="26" font-weight="800">ATP250 四强（赢 2 场）</text>
  <rect x="300" y="320" width="204" height="52" rx="10" fill="rgba(198,246,90,.30)"
        stroke="#c6f65a" stroke-width="2"/>
  <text x="522" y="358" fill="#c6f65a" font-size="29" font-weight="800">100 分</text>

  <text x="60" y="424" fill="#9fb4aa" font-size="26" font-weight="700">挑战赛输第一轮</text>
  <rect x="300" y="444" width="6" height="52" rx="3" fill="rgba(231,243,236,.30)"/>
  <text x="324" y="482" fill="#e7f3ec" font-size="29" font-weight="800">0 分</text>
</svg>
"""


#: 钱。ATP 从 2024 年起给前 250 设了保底（图上是 2025 年的档），
#: 而打一年的开销从最省的四万到带教练的二十万。**地板确实修了，只是只够一个人站**——
#: 这个「够不够」是两条数叠在一起才看得见的，列成文字看不出来。
#: 几何：0–20 万美元映射到 x 300–830，即 1 万美元 = 26.5px。
_CLIMB_MONEY_DIAGRAM = """
<svg viewBox="0 0 900 540" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">地板修了，只是只够一个人站</text>
  <text x="450" y="90" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">单位：万美元／年　保底档位为 2025 年口径</text>

  <text x="60" y="176" fill="#c6f65a" font-size="26" font-weight="800">排名 176–250 保底</text>
  <rect x="300" y="196" width="265" height="52" rx="10" fill="rgba(198,246,90,.30)"
        stroke="#c6f65a" stroke-width="2"/>
  <text x="583" y="234" fill="#c6f65a" font-size="29" font-weight="800">10 万</text>

  <text x="60" y="290" fill="#9fb4aa" font-size="26" font-weight="700">最省的一年</text>
  <rect x="300" y="310" width="106" height="46" rx="9" fill="rgba(231,243,236,.28)"/>
  <text x="424" y="344" fill="#e7f3ec" font-size="27" font-weight="800">4 万</text>

  <text x="60" y="382" fill="#9fb4aa" font-size="26" font-weight="700">常见开销（不带教练）</text>
  <rect x="300" y="402" width="186" height="46" rx="9" fill="rgba(231,243,236,.28)"/>
  <text x="504" y="436" fill="#e7f3ec" font-size="27" font-weight="800">7 万</text>

  <text x="60" y="474" fill="#9fb4aa" font-size="26" font-weight="700">带教练和体能师</text>
  <rect x="300" y="494" width="530" height="30" rx="8" fill="none"
        stroke="rgba(231,243,236,.55)" stroke-width="3" stroke-dasharray="12 8"/>
  <text x="560" y="516" text-anchor="middle" fill="#e7f3ec" font-size="26" font-weight="800">20 万</text>
</svg>
"""


#: 保护排名的额度表。两档、四个数，而**关键是那个「或」**——两个上限同时在倒计时，
#: 谁先到算谁。照片没法表达「两个计时器并排跑」，所以画。
#: 几何：两档各占一行，站数用格子（数得出来），月数用一根横条（时间是连续的）。
_PR_ALLOWANCE_DIAGRAM = """
<svg viewBox="0 0 900 520" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">停多久，给多少</text>
  <text x="450" y="90" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">两个上限同时在走，谁先到算谁</text>

  <text x="52" y="168" fill="#9fb4aa" font-size="27" font-weight="700">停 6–12 个月</text>
  <g fill="rgba(198,246,90,.30)" stroke="#c6f65a" stroke-width="2">
    <rect x="270" y="140" width="34" height="38" rx="6"/>
    <rect x="312" y="140" width="34" height="38" rx="6"/>
    <rect x="354" y="140" width="34" height="38" rx="6"/>
    <rect x="396" y="140" width="34" height="38" rx="6"/>
    <rect x="438" y="140" width="34" height="38" rx="6"/>
    <rect x="480" y="140" width="34" height="38" rx="6"/>
    <rect x="522" y="140" width="34" height="38" rx="6"/>
    <rect x="564" y="140" width="34" height="38" rx="6"/>
    <rect x="606" y="140" width="34" height="38" rx="6"/>
  </g>
  <text x="660" y="168" fill="#c6f65a" font-size="30" font-weight="800">9 站</text>
  <text x="52" y="232" fill="#9fb4aa" font-size="27" font-weight="700">或者</text>
  <rect x="270" y="204" width="370" height="38" rx="10" fill="rgba(198,246,90,.30)"
        stroke="#c6f65a" stroke-width="2"/>
  <text x="660" y="232" fill="#c6f65a" font-size="30" font-weight="800">9 个月</text>

  <line x1="52" y1="286" x2="848" y2="286" stroke="rgba(231,243,236,.22)" stroke-width="2"/>

  <text x="52" y="356" fill="#9fb4aa" font-size="27" font-weight="700">停 12 个月以上</text>
  <g fill="rgba(231,243,236,.26)">
    <rect x="270" y="328" width="34" height="38" rx="6"/>
    <rect x="312" y="328" width="34" height="38" rx="6"/>
    <rect x="354" y="328" width="34" height="38" rx="6"/>
    <rect x="396" y="328" width="34" height="38" rx="6"/>
    <rect x="438" y="328" width="34" height="38" rx="6"/>
    <rect x="480" y="328" width="34" height="38" rx="6"/>
    <rect x="522" y="328" width="34" height="38" rx="6"/>
    <rect x="564" y="328" width="34" height="38" rx="6"/>
    <rect x="606" y="328" width="34" height="38" rx="6"/>
    <rect x="648" y="328" width="34" height="38" rx="6"/>
    <rect x="690" y="328" width="34" height="38" rx="6"/>
    <rect x="732" y="328" width="34" height="38" rx="6"/>
  </g>
  <text x="786" y="356" fill="#e7f3ec" font-size="30" font-weight="800">12 站</text>
  <text x="52" y="420" fill="#9fb4aa" font-size="27" font-weight="700">或者</text>
  <rect x="270" y="392" width="496" height="38" rx="10" fill="rgba(231,243,236,.26)"/>
  <text x="786" y="420" fill="#e7f3ec" font-size="30" font-weight="800">12 个月</text>

  <text x="450" y="492" text-anchor="middle" fill="#c6f65a"
        font-size="32" font-weight="800">每个大满贯，还只能用一次</text>
</svg>
"""


#: 商竣程那两段空白，以及中间那次「冻结」。这一屏要讲的是**时间被按了暂停**——
#: 一根从左走到右的钟，中间挖掉一段。文字排不出「挖掉」这个动作，所以画。
#: 几何：2025-07-28 复出在 x=110，39 周走完在 x=790，即 1 周 ≈ 17.4px。
_PR_FREEZE_DIAGRAM = """
<svg viewBox="0 0 900 480" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">那 9 个月的钟，可以按暂停</text>
  <text x="450" y="90" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">再伤停满 3 个月，剩下的原样留着</text>

  <text x="110" y="160" fill="#9fb4aa" font-size="24" font-weight="700">复出</text>
  <text x="110" y="188" fill="#e7f3ec" font-size="26" font-weight="800">2025.7</text>
  <rect x="110" y="210" width="412" height="46" rx="10" fill="rgba(231,243,236,.26)"/>
  <text x="316" y="296" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">走掉约 30 周</text>

  <rect x="530" y="210" width="120" height="46" rx="10" fill="none"
        stroke="#c6f65a" stroke-width="3" stroke-dasharray="10 8"/>
  <text x="590" y="160" text-anchor="middle" fill="#c6f65a"
        font-size="24" font-weight="700">再伤，冻结</text>
  <text x="590" y="188" text-anchor="middle" fill="#c6f65a"
        font-size="26" font-weight="800">2026.2</text>
  <text x="590" y="296" text-anchor="middle" fill="#c6f65a"
        font-size="26" font-weight="800">停 5 个月</text>

  <rect x="658" y="210" width="132" height="46" rx="10" fill="rgba(231,243,236,.26)"/>
  <text x="790" y="160" text-anchor="end" fill="#9fb4aa" font-size="24" font-weight="700">接着走</text>
  <text x="790" y="188" text-anchor="end" fill="#e7f3ec" font-size="26" font-weight="800">2026.7</text>
  <text x="724" y="296" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">还剩约 9 周</text>

  <text x="450" y="392" text-anchor="middle" fill="#e7f3ec"
        font-size="28" font-weight="800">最多冻两次</text>
  <text x="450" y="452" text-anchor="middle" fill="#c6f65a"
        font-size="30" font-weight="800">而那三年的总时效，一天都不会停</text>
</svg>
"""


#: 「能用来干嘛」那一屏。三件能做、两件不能做——**照片没法表达一条禁令**，
#: 所以画。左右两栏对照，能做的给强调色，不能做的压成中性并划一道斜杠。
#: 「代价」那一屏。这一屏讲的是**他没打**——而没打是拍不出来的：
#: 一张空球场证明不了「本可以站上去的人选择了不站」。CLAUDE.md 那条
#: 「示意图的触发条件是照片讲不清，不是照片找不到」，这里是最干净的一例。
#:
#: 画出来才看得见的那件事：**整届温网（6.30–7.13）正好占满这段等待的最后 13 天。**
#: 六个月满在 7 月 13 日，而温网决赛也是 7 月 13 日——他要是打了，
#: 断的是终点线前的最后十三天。日期两头都核过（维基 2025 温网 30 June – 13 July）。
_PR_BLANK_DIAGRAM = """
<svg viewBox="0 0 900 470" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">温网开赛那天，他还差 13 天</text>
  <text x="450" y="90" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">门槛：连续 6 个月不打任何比赛，表演赛也算</text>

  <text x="615" y="156" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">法网 5.25</text>
  <text x="615" y="188" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">缺席</text>
  <line x1="615" y1="204" x2="615" y2="248" stroke="#9fb4aa" stroke-width="3"/>

  <text x="784" y="156" text-anchor="middle" fill="#c6f65a"
        font-size="26" font-weight="800">温网 6.30</text>
  <text x="784" y="188" text-anchor="middle" fill="#c6f65a"
        font-size="26" font-weight="800">他能打，没打</text>
  <line x1="784" y1="204" x2="784" y2="248" stroke="#c6f65a" stroke-width="3"/>

  <rect x="90" y="248" width="720" height="52" rx="10" fill="rgba(231,243,236,.18)"/>
  <rect x="758" y="248" width="52" height="52" rx="10" fill="rgba(198,246,90,.85)"/>

  <text x="90" y="346" fill="#9fb4aa" font-size="26" font-weight="700">2025.1.13</text>
  <text x="90" y="378" fill="#9fb4aa" font-size="26" font-weight="700">澳网首轮，停赛前最后一场</text>
  <text x="810" y="346" text-anchor="end" fill="#e7f3ec"
        font-size="26" font-weight="800">7.13</text>
  <text x="810" y="378" text-anchor="end" fill="#e7f3ec"
        font-size="26" font-weight="800">六个月满</text>

  <text x="450" y="446" text-anchor="middle" fill="#c6f65a"
        font-size="30" font-weight="800">整届温网，正好压在最后 13 天里</text>
</svg>
"""


_PR_USE_DIAGRAM = """
<svg viewBox="0 0 900 470" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">它只管进门，不管座次</text>

  <text x="60" y="120" fill="#c6f65a" font-size="28" font-weight="800">能用来</text>
  <g font-size="27" font-weight="700" fill="#e7f3ec">
    <rect x="60" y="140" width="360" height="52" rx="10" fill="rgba(198,246,90,.26)"
          stroke="#c6f65a" stroke-width="2"/>
    <text x="80" y="174" fill="#c6f65a">进正赛</text>
    <rect x="60" y="204" width="360" height="52" rx="10" fill="rgba(198,246,90,.26)"
          stroke="#c6f65a" stroke-width="2"/>
    <text x="80" y="238" fill="#c6f65a">进资格赛</text>
    <rect x="60" y="268" width="360" height="52" rx="10" fill="rgba(198,246,90,.26)"
          stroke="#c6f65a" stroke-width="2"/>
    <text x="80" y="302" fill="#c6f65a">占特殊豁免位</text>
  </g>

  <text x="480" y="120" fill="#9fb4aa" font-size="28" font-weight="800">不能用来</text>
  <g font-size="27" font-weight="700">
    <rect x="480" y="140" width="360" height="52" rx="10" fill="rgba(231,243,236,.16)"/>
    <text x="500" y="174" fill="#9fb4aa">当种子</text>
    <line x1="496" y1="166" x2="824" y2="166" stroke="rgba(159,180,170,.75)" stroke-width="2"/>
    <rect x="480" y="204" width="360" height="52" rx="10" fill="rgba(231,243,236,.16)"/>
    <text x="500" y="238" fill="#9fb4aa">排幸运落败者顺位</text>
    <line x1="496" y1="230" x2="824" y2="230" stroke="rgba(159,180,170,.75)" stroke-width="2"/>
  </g>

  <text x="450" y="392" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">这个数＝停赛后头 3 个月排名的平均值</text>
  <text x="450" y="446" text-anchor="middle" fill="#c6f65a"
        font-size="30" font-weight="800">抽签还是按你真实的排名摆</text>
</svg>
"""


#: 「同一场雨，两个城市的日程对不上」——**照片讲不了这件事**：一张雨的照片
#: 只能说华盛顿下雨了，说不了「而加拿大那边资格赛已经打完」。跨城市、跨日期的
#: 关系正是「照片讲不清」那一档（跟保护排名那条的「温网正好压在最后 13 天」同族）。
#: 日期是北京时间，四天的场次数由 `fetch_day` 核过（见 docs/rain-delay-research.md 第七节）。
_SE_CHAIN_DIAGRAM = """
<svg viewBox="0 0 900 500" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">同一场雨，两个城市的日程对不上</text>
  <text x="450" y="88" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">北京时间</text>

  <g text-anchor="middle" fill="#9fb4aa" font-size="27" font-weight="700">
    <text x="255" y="132">8 月 1 日</text>
    <text x="427" y="132">8 月 2 日</text>
    <text x="599" y="132">8 月 3 日</text>
    <text x="771" y="132">8 月 4 日</text>
  </g>

  <text x="40" y="200" fill="#e7f3ec" font-size="28" font-weight="800">华盛顿</text>
  <g font-size="26" font-weight="700" text-anchor="middle" fill="#e7f3ec">
    <rect x="180" y="158" width="150" height="64" rx="10" fill="rgba(231,243,236,.16)"/>
    <text x="255" y="198">半决赛</text>
    <rect x="352" y="158" width="150" height="64" rx="10" fill="rgba(231,243,236,.16)"/>
    <text x="427" y="198">决赛遇雨</text>
    <rect x="524" y="158" width="150" height="64" rx="10" fill="rgba(231,243,236,.16)"/>
    <text x="599" y="198">还没打完</text>
    <rect x="696" y="158" width="150" height="64" rx="10" fill="rgba(231,243,236,.16)"/>
    <text x="771" y="198">周一补打</text>
  </g>

  <text x="40" y="352" fill="#e7f3ec" font-size="28" font-weight="800">加拿大站</text>
  <g font-size="26" font-weight="700" text-anchor="middle">
    <rect x="180" y="310" width="150" height="64" rx="10" fill="rgba(198,246,90,.26)"
          stroke="#c6f65a" stroke-width="2"/>
    <text x="255" y="350" fill="#c6f65a">资格赛</text>
    <rect x="352" y="310" width="150" height="64" rx="10" fill="rgba(198,246,90,.26)"
          stroke="#c6f65a" stroke-width="2"/>
    <text x="427" y="350" fill="#c6f65a">资格赛</text>
    <rect x="524" y="310" width="150" height="64" rx="10" fill="rgba(231,243,236,.16)"/>
    <text x="599" y="350" fill="#e7f3ec">正赛首轮</text>
    <rect x="696" y="310" width="150" height="64" rx="10" fill="rgba(231,243,236,.16)"/>
    <text x="771" y="350" fill="#e7f3ec">正赛首轮</text>
  </g>

  <path d="M180 288 L180 268 L502 268 L502 288" stroke="#c6f65a"
        stroke-width="3" fill="none"/>
  <text x="341" y="256" text-anchor="middle" fill="#c6f65a"
        font-size="25" font-weight="700">这两天打完，过期不补</text>

  <text x="450" y="442" text-anchor="middle" fill="#e7f3ec"
        font-size="31" font-weight="800">还在华盛顿打的人，赶不上加拿大的资格赛</text>
</svg>
"""


#: 「一个位置」——留出来的席位拍不出来。96 是大师赛正赛的签表人数，
#: 一格一个名额、只有一格是亮的，「整站只有一个」这句话就不用读者做除法。
#: ⚠️ 故意不画「直接入围/资格赛/外卡各多少」——那几个数没核到，
#: 而画上去就是替签表声明了一件没核过的事。
_SE_SLOT_DIAGRAM = """
<svg viewBox="0 0 900 490" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">大师赛九十六个正赛名额</text>
  <text x="450" y="88" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">一格＝一个名额　亮的那格＝特殊豁免</text>

  <g fill="rgba(231,243,236,.20)">
    <rect x="69"  y="120" width="42" height="34" rx="6"/>
    <rect x="117" y="120" width="42" height="34" rx="6"/>
    <rect x="165" y="120" width="42" height="34" rx="6"/>
    <rect x="213" y="120" width="42" height="34" rx="6"/>
    <rect x="261" y="120" width="42" height="34" rx="6"/>
    <rect x="309" y="120" width="42" height="34" rx="6"/>
    <rect x="357" y="120" width="42" height="34" rx="6"/>
    <rect x="405" y="120" width="42" height="34" rx="6"/>
    <rect x="453" y="120" width="42" height="34" rx="6"/>
    <rect x="501" y="120" width="42" height="34" rx="6"/>
    <rect x="549" y="120" width="42" height="34" rx="6"/>
    <rect x="597" y="120" width="42" height="34" rx="6"/>
    <rect x="645" y="120" width="42" height="34" rx="6"/>
    <rect x="693" y="120" width="42" height="34" rx="6"/>
    <rect x="741" y="120" width="42" height="34" rx="6"/>
    <rect x="789" y="120" width="42" height="34" rx="6"/>

    <rect x="69"  y="162" width="42" height="34" rx="6"/>
    <rect x="117" y="162" width="42" height="34" rx="6"/>
    <rect x="165" y="162" width="42" height="34" rx="6"/>
    <rect x="213" y="162" width="42" height="34" rx="6"/>
    <rect x="261" y="162" width="42" height="34" rx="6"/>
    <rect x="309" y="162" width="42" height="34" rx="6"/>
    <rect x="357" y="162" width="42" height="34" rx="6"/>
    <rect x="405" y="162" width="42" height="34" rx="6"/>
    <rect x="453" y="162" width="42" height="34" rx="6"/>
    <rect x="501" y="162" width="42" height="34" rx="6"/>
    <rect x="549" y="162" width="42" height="34" rx="6"/>
    <rect x="597" y="162" width="42" height="34" rx="6"/>
    <rect x="645" y="162" width="42" height="34" rx="6"/>
    <rect x="693" y="162" width="42" height="34" rx="6"/>
    <rect x="741" y="162" width="42" height="34" rx="6"/>
    <rect x="789" y="162" width="42" height="34" rx="6"/>

    <rect x="69"  y="204" width="42" height="34" rx="6"/>
    <rect x="117" y="204" width="42" height="34" rx="6"/>
    <rect x="165" y="204" width="42" height="34" rx="6"/>
    <rect x="213" y="204" width="42" height="34" rx="6"/>
    <rect x="261" y="204" width="42" height="34" rx="6"/>
    <rect x="309" y="204" width="42" height="34" rx="6"/>
    <rect x="357" y="204" width="42" height="34" rx="6"/>
    <rect x="405" y="204" width="42" height="34" rx="6"/>
    <rect x="501" y="204" width="42" height="34" rx="6"/>
    <rect x="549" y="204" width="42" height="34" rx="6"/>
    <rect x="597" y="204" width="42" height="34" rx="6"/>
    <rect x="645" y="204" width="42" height="34" rx="6"/>
    <rect x="693" y="204" width="42" height="34" rx="6"/>
    <rect x="741" y="204" width="42" height="34" rx="6"/>
    <rect x="789" y="204" width="42" height="34" rx="6"/>

    <rect x="69"  y="246" width="42" height="34" rx="6"/>
    <rect x="117" y="246" width="42" height="34" rx="6"/>
    <rect x="165" y="246" width="42" height="34" rx="6"/>
    <rect x="213" y="246" width="42" height="34" rx="6"/>
    <rect x="261" y="246" width="42" height="34" rx="6"/>
    <rect x="309" y="246" width="42" height="34" rx="6"/>
    <rect x="357" y="246" width="42" height="34" rx="6"/>
    <rect x="405" y="246" width="42" height="34" rx="6"/>
    <rect x="453" y="246" width="42" height="34" rx="6"/>
    <rect x="501" y="246" width="42" height="34" rx="6"/>
    <rect x="549" y="246" width="42" height="34" rx="6"/>
    <rect x="597" y="246" width="42" height="34" rx="6"/>
    <rect x="645" y="246" width="42" height="34" rx="6"/>
    <rect x="693" y="246" width="42" height="34" rx="6"/>
    <rect x="741" y="246" width="42" height="34" rx="6"/>
    <rect x="789" y="246" width="42" height="34" rx="6"/>

    <rect x="69"  y="288" width="42" height="34" rx="6"/>
    <rect x="117" y="288" width="42" height="34" rx="6"/>
    <rect x="165" y="288" width="42" height="34" rx="6"/>
    <rect x="213" y="288" width="42" height="34" rx="6"/>
    <rect x="261" y="288" width="42" height="34" rx="6"/>
    <rect x="309" y="288" width="42" height="34" rx="6"/>
    <rect x="357" y="288" width="42" height="34" rx="6"/>
    <rect x="405" y="288" width="42" height="34" rx="6"/>
    <rect x="453" y="288" width="42" height="34" rx="6"/>
    <rect x="501" y="288" width="42" height="34" rx="6"/>
    <rect x="549" y="288" width="42" height="34" rx="6"/>
    <rect x="597" y="288" width="42" height="34" rx="6"/>
    <rect x="645" y="288" width="42" height="34" rx="6"/>
    <rect x="693" y="288" width="42" height="34" rx="6"/>
    <rect x="741" y="288" width="42" height="34" rx="6"/>
    <rect x="789" y="288" width="42" height="34" rx="6"/>

    <rect x="69"  y="330" width="42" height="34" rx="6"/>
    <rect x="117" y="330" width="42" height="34" rx="6"/>
    <rect x="165" y="330" width="42" height="34" rx="6"/>
    <rect x="213" y="330" width="42" height="34" rx="6"/>
    <rect x="261" y="330" width="42" height="34" rx="6"/>
    <rect x="309" y="330" width="42" height="34" rx="6"/>
    <rect x="357" y="330" width="42" height="34" rx="6"/>
    <rect x="405" y="330" width="42" height="34" rx="6"/>
    <rect x="453" y="330" width="42" height="34" rx="6"/>
    <rect x="501" y="330" width="42" height="34" rx="6"/>
    <rect x="549" y="330" width="42" height="34" rx="6"/>
    <rect x="597" y="330" width="42" height="34" rx="6"/>
    <rect x="645" y="330" width="42" height="34" rx="6"/>
    <rect x="693" y="330" width="42" height="34" rx="6"/>
    <rect x="741" y="330" width="42" height="34" rx="6"/>
    <rect x="789" y="330" width="42" height="34" rx="6"/>
  </g>

  <rect x="453" y="204" width="42" height="34" rx="6" fill="#c6f65a"/>

  <text x="450" y="416" text-anchor="middle" fill="#c6f65a"
        font-size="32" font-weight="800">整站就这一个</text>
  <text x="450" y="466" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">500 赛也是 1 个　250 赛和挑战赛 2 个</text>
</svg>
"""


#: 「认不认雨」——两本规则书的条文差别，照片没有语法去表达。
#: 左边给强调色，因为这一屏的落点是「WTA 那本把天气写进了条文」。
_SE_BOOKS_DIAGRAM = """
<svg viewBox="0 0 900 520" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">同一件事，两本规则书写得不一样</text>

  <text x="250" y="110" text-anchor="middle" fill="#c6f65a"
        font-size="32" font-weight="800">WTA</text>
  <rect x="60" y="130" width="380" height="284" rx="14"
        fill="rgba(198,246,90,.16)" stroke="#c6f65a" stroke-width="2"/>
  <text x="250" y="186" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">条文原文里就有</text>
  <text x="250" y="242" text-anchor="middle" fill="#c6f65a"
        font-size="40" font-weight="800">因天气</text>
  <line x1="110" y1="282" x2="390" y2="282" stroke="rgba(198,246,90,.45)" stroke-width="2"/>
  <text x="250" y="330" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">而且</text>
  <text x="250" y="382" text-anchor="middle" fill="#e7f3ec"
        font-size="31" font-weight="800">进了决赛就够格</text>

  <text x="650" y="110" text-anchor="middle" fill="#9fb4aa"
        font-size="32" font-weight="800">ATP</text>
  <rect x="460" y="130" width="380" height="284" rx="14" fill="rgba(231,243,236,.14)"/>
  <text x="650" y="186" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">全文找不到</text>
  <text x="650" y="242" text-anchor="middle" fill="#9fb4aa"
        font-size="40" font-weight="800">天气</text>
  <line x1="520" y1="282" x2="780" y2="282" stroke="rgba(159,180,170,.4)" stroke-width="2"/>
  <text x="650" y="330" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">靠这个定义兜住</text>
  <text x="650" y="382" text-anchor="middle" fill="#e7f3ec"
        font-size="31" font-weight="800">开始或恢复一场比赛</text>

  <text x="450" y="484" text-anchor="middle" fill="#e7f3ec"
        font-size="30" font-weight="800">两场决赛分属两个协会，条文不能混着讲</text>
</svg>
"""


#: 「一小时」——一段倒计时拍不出来。**两条按同一把尺子画**：赛事那头准备两天
#: （48 小时 = 576px，12px/小时），球员这头只有 1 小时 = 12px。那道细缝就是论点，
#: 所以不许为了「看得清」把它画粗——那样就成了「条形图上写字」那一类的谎。
_SE_HOUR_DIAGRAM = """
<svg viewBox="0 0 900 502" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">那头准备两天，你这头只有一小时</text>
  <text x="450" y="88" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">两条按同一把尺子画</text>

  <text x="60" y="162" fill="#9fb4aa" font-size="27" font-weight="700">赛事那头</text>
  <rect x="60" y="182" width="576" height="60" rx="10" fill="rgba(231,243,236,.28)"/>
  <text x="656" y="224" fill="#e7f3ec" font-size="36" font-weight="800">48 小时</text>
  <text x="60" y="284" fill="#9fb4aa" font-size="26" font-weight="700">周三、周四列名单，监督挨个联系</text>

  <text x="60" y="376" fill="#c6f65a" font-size="27" font-weight="800">你这头</text>
  <rect x="60" y="396" width="12" height="60" rx="3" fill="#c6f65a"/>
  <path d="M82 426 L640 426" stroke="rgba(198,246,90,.45)" stroke-width="2"
        fill="none" stroke-dasharray="8 8"/>
  <text x="656" y="438" fill="#c6f65a" font-size="36" font-weight="800">1 小时</text>
  <text x="60" y="498" fill="#9fb4aa" font-size="26" font-weight="700">赢下那场决定性的球之后</text>
</svg>
"""


_ACADEMY_COUNT_DIAGRAM = """
<svg viewBox="0 0 900 470" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" fill="#e7f3ec"
        font-size="36" font-weight="800">同时进前一百的学院球员</text>
  <text x="450" y="88" text-anchor="middle" fill="#9fb4aa"
        font-size="26" font-weight="700">一格＝一个人　亮的那格＝八月三日新增</text>

  <text x="90" y="168" fill="#9fb4aa" font-size="28" font-weight="700">6 月 9 日</text>
  <g fill="rgba(231,243,236,.22)">
    <rect x="300" y="140" width="60" height="44" rx="8"/>
    <rect x="368" y="140" width="60" height="44" rx="8"/>
    <rect x="436" y="140" width="60" height="44" rx="8"/>
    <rect x="504" y="140" width="60" height="44" rx="8"/>
    <rect x="572" y="140" width="60" height="44" rx="8"/>
    <rect x="640" y="140" width="60" height="44" rx="8"/>
  </g>
  <text x="740" y="172" fill="#e7f3ec" font-size="32" font-weight="800">6</text>
  <text x="300" y="222" fill="#9fb4aa" font-size="26" font-weight="700">学院发公告：史上第一次</text>

  <line x1="300" y1="266" x2="820" y2="266" stroke="rgba(231,243,236,.18)" stroke-width="2"/>

  <text x="90" y="336" fill="#9fb4aa" font-size="28" font-weight="700">8 月 3 日</text>
  <g fill="rgba(231,243,236,.22)">
    <rect x="300" y="308" width="60" height="44" rx="8"/>
    <rect x="368" y="308" width="60" height="44" rx="8"/>
    <rect x="436" y="308" width="60" height="44" rx="8"/>
    <rect x="504" y="308" width="60" height="44" rx="8"/>
    <rect x="572" y="308" width="60" height="44" rx="8"/>
    <rect x="640" y="308" width="60" height="44" rx="8"/>
  </g>
  <rect x="708" y="308" width="60" height="44" rx="8" fill="#c6f65a"/>
  <text x="800" y="340" fill="#c6f65a" font-size="32" font-weight="800">7</text>
  <text x="300" y="390" fill="#e7f3ec" font-size="26" font-weight="700">黄泽林进前一百　八周之后</text>

  <text x="450" y="444" text-anchor="middle" fill="#9fb4aa"
        font-size="24" font-weight="700">第七个是我们按学院自己的口径数的</text>
</svg>
"""


# ⚠️ 轴上标不标名字，卡在译名上，不卡在版面上：
#   · 四个展开讲的都在译名表里（伊埃拉／兰达卢塞／黄泽林／鲁德），标名字
#   · 穆纳尔中文维基学院页写「豪梅·穆纳尔」，但表里没有——**只标年纪不标名**
#   · 西埃拉查不到中文源；科尔涅耶娃两个源两种写法（维基「阿林娜·科尔涅耶娃」／
#     百度「阿丽娜·科尔涅娃」）——同样不标名
#   · **科尔涅耶娃到学院的年纪根本没查到**，所以她不在轴上，单独standing在右边打问号。
#     把「没查到」画出来，比把她悄悄漏掉诚实（CLAUDE.md：空结果先自证是真空）
# ⚠️ 中文维基那页把伊埃拉写成「亚历克莎·埃亚拉」——**别照抄**。仓库早就把
#   埃亚拉改成伊埃拉了，译名表说了算。
def _academy_span_diagram() -> str:
    """入校时间轴，点上是本人的官方头像。

    ⚠️ 横轴是**入校那一年**，不是入校年纪。原来按年纪排，伊埃拉 13 岁排最左，
    读起来就是「她最早来的」——**而最早的是穆纳尔（2017）**。账号所有者点出来的。

    ⚠️ 头像**等距排一行、各自引线到自己真实的年份位置**，不直接压在轴上：
    穆纳尔 2017 和伊埃拉 2018 在轴上只隔 82px，头像挨着放必然叠。
    引线按年份单调排列所以不会交叉，版面松了而轴仍然诚实。

    头像出处见 assets/explainer/nadal-academy/faces/credits.json：四男是 ATP
    官方头像（赛事域名镜像，总站 403），伊埃拉裁自仓库里那张 WTA 官方抠图
    （wta-330332，id 与 WTA API 查到的一致）。
    """
    import base64

    root = Path(__file__).resolve().parents[3] / "assets/explainer/nadal-academy/faces"
    def uri(name: str) -> str:
        raw = (root / f"{name}.jpg").read_bytes()
        return "data:image/jpeg;base64," + base64.b64encode(raw).decode()

    # (头像位置, 真实年份位置, 名字, 年纪, 文件名)
    people = [
        (90,  80,  "穆纳尔",   "20 岁", "munar"),
        (235, 162, "伊埃拉",   "13 岁", "eala"),
        (380, 224, "鲁德",     "19 岁", "ruud"),
        (525, 326, "兰达卢塞", "14 岁", "landaluce"),
        (670, 408, "黄泽林",   "17 岁", "wong"),
    ]
    defs, art = [], []
    for ax, tx, name, age, key in people:
        defs.append(f'<clipPath id="c{key}"><circle cx="{ax}" cy="150" r="46"/></clipPath>')
        defs.append(f'<image id="i{key}" href="{uri(key)}" x="{ax-46}" y="104" '
                    f'width="92" height="92" clip-path="url(#c{key})"/>')
        art.append(
            f'<use href="#i{key}"/>'
            f'<circle cx="{ax}" cy="150" r="46" fill="none" stroke="#c6f65a" stroke-width="3"/>'
            f'<text x="{ax}" y="230" text-anchor="middle" fill="#e7f3ec" '
            f'font-size="25" font-weight="800">{name}</text>'
            f'<text x="{ax}" y="260" text-anchor="middle" fill="#c6f65a" '
            f'font-size="23" font-weight="800">{age}</text>'
            f'<line x1="{ax}" y1="272" x2="{tx}" y2="318" '
            f'stroke="rgba(231,243,236,.30)" stroke-width="2"/>'
            f'<circle cx="{tx}" cy="330" r="13" fill="#c6f65a"/>'
        )
    return (
        '<svg viewBox="0 0 900 500" xmlns="http://www.w3.org/2000/svg">'
        + "<defs>" + "".join(defs) + "</defs>"
        + '<text x="450" y="42" text-anchor="middle" fill="#e7f3ec" font-size="34" '
          'font-weight="800">他们哪一年到的学院</text>'
        + '<text x="450" y="80" text-anchor="middle" fill="#9fb4aa" font-size="24" '
          'font-weight="700">横轴＝入校那一年　名字底下＝当时多大</text>'
        + '<line x1="60" y1="330" x2="800" y2="330" stroke="rgba(231,243,236,.28)" stroke-width="3"/>'
        + "".join(art)
        + '<circle cx="757" cy="330" r="10" fill="rgba(231,243,236,.34)"/>'
        + '<text x="757" y="306" text-anchor="middle" fill="#9fb4aa" font-size="20" '
          'font-weight="700">21 岁</text>'
        + '<g fill="#9fb4aa" font-size="22" font-weight="700" text-anchor="middle">'
          '<text x="80" y="372">2017</text><text x="193" y="372">2018</text>'
          '<text x="326" y="372">2020</text><text x="408" y="372">2021</text>'
          '<text x="757" y="372">2025</text></g>'
        + '<circle cx="855" cy="330" r="10" fill="none" stroke="rgba(231,243,236,.34)" '
          'stroke-width="2" stroke-dasharray="4 4"/>'
        + '<text x="855" y="306" text-anchor="middle" fill="#9fb4aa" font-size="26" '
          'font-weight="800">?</text>'
        + '<text x="855" y="372" text-anchor="middle" fill="#9fb4aa" font-size="18" '
          'font-weight="700">没查到</text>'
        + '<text x="450" y="432" text-anchor="middle" fill="#e7f3ec" font-size="27" '
          'font-weight="800">同一年到的两个人，一个 13 岁，一个 19 岁</text>'
        + '<text x="450" y="470" text-anchor="middle" fill="#9fb4aa" font-size="23" '
          'font-weight="700">公告里都算「学院培养的」</text>'
        + "</svg>"
    )


_ACADEMY_SPAN_DIAGRAM = _academy_span_diagram()


_SCRIPTS: dict[str, tuple[tuple, ...]] = {
    # 纳达尔学院。引子是学院自己 2026-06-09 那份「六人同时进前 100」的公告，
    # 而它八周就过时了。⚠️ 详讲四个、七个都上时间轴——账号所有者 2026-08-04：
    # 「只讲最出名的就好」「没关系啊，可以出现在时间轴，只是不展开讲而已」。
    # 边界划在「展开不展开」，不是「出不出现」：跨度要靠点多才看得出来。
    "nadal-academy": (
        (
            "cause",
            "那份公告",
            "六个人，八周之后不对了",
            "二零二六年六月九号，一所网球学院发了一份公告。"
            "史上第一次，同时有六名学院培养的球员，进入 ATP 和 WTA 前一百。"
            "六个人，来自六个国家。"
            # ⚠️ 这句是全片的支点，而且是点开原文确认过的：那篇公告通篇没有定义
            # developed at the Academy 是什么意思，也没分「住了七年的」和「来集训一周的」。
            "公告里没有说，什么叫学院培养的。"
            "八周之后，这个数字不对了。",
            "",
            "示意图 · 网球时差绘制",
            (
                "6 月 9 日 学院宣布六人同时进前 100",
                "史上第一次 公告里这么写",
                "八周之后 这个数字不对了",
            ),
            _ACADEMY_COUNT_DIAGRAM,
        ),
        (
            "cause",
            "同一个周一",
            "两个第一，隔着半个地球",
            "八月三号，星期一。"
            # ⚠️ 取**官方排名**第 91，不取实时排名第 90。两者是两个口径不是两个版本：
            # 实时是 7/31 打进半决赛当下的，官方是这个周一更新的。而「第一个进前 100
            # 的香港人」本来就是按官方榜说的。
            "那天更新的 ATP 排名里，黄泽林排第九十一。"
            "一九七三年有排名以来，代表中国香港进前一百的，他是第一个。"
            "同一个周一，华盛顿的女单决赛因为下雨，拖到这天才打完。"
            "伊埃拉逆转佩古拉，四比六、六比四、六比零。"
            # ⚠️ 措辞：账号所有者 2026-08-04 确认「生涯首冠，应该是 WTA 巡回赛级别的」。
            # 她此前有两个 WTA125（瓜达拉哈拉、伯明翰），但那是低于巡回赛的独立一档，
            # 不计进这本账——英文媒体也这么分。
            "生涯首冠，也是菲律宾的第一个 WTA 巡回赛冠军。"
            "两个第一，隔着半个地球。"
            "而这两个人，出自同一所学校。",
            "",
            "示意图 · 网球时差绘制",
            (
                "8 月 3 日 黄泽林进 ATP 前 100",
                "同一个周一 伊埃拉拿下生涯首冠",
                "同一所学校 马略卡岛，马纳科尔",
            ),
            _ACADEMY_COUNT_DIAGRAM,
        ),
        (
            "mechanism",
            "十三岁",
            "伊埃拉从马尼拉搬过去，一住七年",
            "伊埃拉是十三岁去的。"
            "那年她在法国赢了一站世界少年赛，学院的人主动找上门。"
            "他们给了她一份奖学金。"
            "她从马尼拉搬到马略卡岛，一住七年。"
            "二零二三年毕业，典礼上的主礼嘉宾是斯瓦泰克。"
            "她管那个地方叫第二个家。",
            "",
            "示意图 · 网球时差绘制",
            (
                "13 岁 从马尼拉搬到马略卡岛",
                "奖学金 学院主动找上门",
                "住了七年 2023 年毕业",
            ),
            _ACADEMY_SPAN_DIAGRAM,
        ),
        (
            "mechanism",
            "十四岁和十七岁",
            "一个从马德里，一个从香港",
            "兰达卢塞去的时候十四岁，从马德里。"
            "两年之后，他拿下美网青少年男单冠军。"
            "黄泽林去的时候十七岁。"
            "他跟父母说，不去西班牙，他成不了职业球员。"
            # ⚠️ 这个细节是全片最好的一个，值得留。它把两条线接起来：
            # 八月三号那两个「第一」，其实是同一间宿舍里出来的。
            "他刚到那年，帮他适应的人是伊埃拉。",
            "",
            "示意图 · 网球时差绘制",
            (
                "兰达卢塞 14 岁去，16 岁拿美网青少年冠军",
                "黄泽林 17 岁去，不去就成不了职业球员",
                "刚到那年 是伊埃拉帮他适应的",
            ),
            _ACADEMY_SPAN_DIAGRAM,
        ),
        (
            "mechanism",
            "十九岁",
            "鲁德去的时候，已经是职业球员",
            "鲁德到马纳科尔那年，十九岁。"
            "那时候他已经是职业球员了。"
            # ⚠️ 父子同姓，所以这儿必须写全名。译名表里「鲁德」是卡斯珀·鲁德，
            # 只写姓会指错人——而这一段的全部重量就在「父亲还是他主教练」这句上。
            "他父亲克里斯蒂安·鲁德打过职业，最高世界第三十九。"
            "到今天，父亲还是他的主教练。"
            "他不是去被人培养的。他是把那儿当基地。"
            "挪威一年里能在室外打球的日子有限，网球的底子也薄。"
            "现在他世界第十四，打过三次大满贯决赛。",
            "",
            "示意图 · 网球时差绘制",
            (
                "19 岁 去的时候已经是职业球员",
                "他的主教练 父亲克里斯蒂安·鲁德，至今",
                "不是去被培养 是把那儿当基地",
            ),
            _ACADEMY_SPAN_DIAGRAM,
        ),
        (
            "today",
            "同一栏",
            "十三岁和十九岁，写在一起",
            "所以那份公告里的六个人，是这样凑起来的。"
            # ⚠️ 「同一年」是把轴按入校年份重排之后才掉出来的：伊埃拉 2018 年去，
            # 鲁德 2018 年 9 月去。按年纪排的那一版看不见这件事——而它正是全片的论点。
            "伊埃拉和鲁德，是同一年到的。"
            "一个十三岁，拿着奖学金，住了七年。"
            "一个十九岁，带着自己的父亲去落脚。"
            "在那张表上，他们是同一栏。"
            "学院培养的，这五个字没有定义。"
            "八月三号之后，这一栏又多了一个人。"
            "那么，十三岁去和二十一岁去，能算同一所学校教出来的吗？",
            "",
            "示意图 · 网球时差绘制",
            (
                "同一年到的 伊埃拉 13 岁，鲁德 19 岁",
                "一个拿奖学金住了七年 一个带着父亲来落脚",
                "同一栏 「学院培养的」没有定义",
            ),
            _ACADEMY_SPAN_DIAGRAM,
            "十三岁去和二十一岁去，能算同一所学校教出来的吗？",
        ),
    ),
    # 特殊豁免。⚠️ 片子里出现的每个人都是真的，每件事都真发生过——
    # 账号所有者 2026-08-03：「不要用写这些假设，普通人看不懂，就用实际举例。」
    # 上一版写过一张「如果决赛里有个低排名球员会怎样」的推演表，整张删了。
    "special-exempt": (
        (
            "day",
            "那一天",
            "两场决赛，一场都没打完",
            "八月二号，华盛顿下了一整天雨。"
            "男单决赛，弗里茨对霍达尔。女单决赛，佩古拉对伊埃拉。"
            "两场决赛，一场都没打完。"
            # ⚠️ 原来写「佩古拉六比四、一比二领先」——**错的**。比分记法是佩古拉在前，
            # `6-4、1-2` 是「赢了第一盘，第二盘一比二落后」，写成「领先」等于说她两盘都领先。
            "中断的时候，佩古拉拿下了第一盘，六比四；第二盘打到一比二。"
            "晚上九点零六分，官方宣布顺延到周一。"
            "而那时候，加拿大站的资格赛两天前就打完了。正赛第一轮，已经打到第三天。"
            # ⚠️ 霍达尔写 15。`lookup_player_meta`（ESPN 榜单）报的 24 是**上一周
            # 的快照**——账号所有者 2026-08-03 确认「现在他的排名是 15，24 是上周的」，
            # 和维基那条「Highest/Current No. 15 (3 August 2026)」对得上。
            # 上一版为了绕开这个分歧写了「世界前二十五」，那是**把两个源对半退成
            # 一个范围**——分歧的正解是查清哪个新，不是取一个两边都成立的说法。
            "这四个人没事。佩古拉世界第三，伊埃拉第二十八。弗里茨是三号种子。"
            "霍达尔十九岁，世界第十五，刚打进生涯第一个五百赛决赛。"
            "他们的排名都够直接进正赛，不需要去打任何资格赛。",
            "",
            "示意图 · 网球时差绘制",
            (
                "8 月 2 日 两场决赛都没打完",
                "顺延到周一 当地中午恢复",
                "而加拿大站 资格赛两天前已结束",
            ),
            _SE_CHAIN_DIAGRAM,
        ),
        (
            "slot",
            "一个位置",
            "不用打资格赛，直接进正赛",
            "那换一个人呢。排名低一档，必须先打资格赛的那种。"
            # ⚠️ 「被这场雨卡在」被切成 `雨卡｜在`。换成主动句，「雨」后面跟「会」就不黏了。
            "这场雨会把他卡在两个城市之间。"
            "上一站还没打完，下一站的资格赛已经开始了。"
            "规则给这件事留了一个位置，叫特殊豁免。"
            "正赛里专门留出来的一个席位。发给谁？"
            "发给那个还在上一站打球、赶不上这一站资格赛的人。"
            "一站赛事，只有一个。大师赛一个，五百赛一个。"
            "只有二百五十赛和挑战赛，给两个。",
            "",
            "示意图 · 网球时差绘制",
            (
                "特殊豁免 正赛里留出的一个席位",
                "发给谁 还在上一站打，来不了资格赛",
                "有几个 大师赛和 500 赛各 1 个",
            ),
            _SE_SLOT_DIAGRAM,
        ),
        (
            "rain",
            "认不认雨",
            "WTA 那本，把「天气」写进了条文",
            # ⚠️ 「两本规则书写得不一样」被切成 `规则｜书写｜得`——**「书写」念成 shūxiě，
            # 意思全变**。逗号把边界钉死，这儿本来也该停。
            "那雨算不算数。两本规则书，写得不一样。"
            "WTA 那本，直接写进了资格条款。"
            "她的比赛因为天气改期，撞上资格赛第一天，就够格。"
            "而且还有一条更松的——只要进了决赛，够格，不用赢。"
            "ATP 那本，没写天气这两个字。它绕了一圈。"
            "所谓还在比赛，指的是那一天的赛程里，开始或者恢复一场比赛。"
            # ⚠️ 原来写「恢复。就这两个字，…」——配音上是个好节拍，但「恢复」只有两个字，
            # 不跨句合并之后它自己占一行，会一闪而过（test_字幕里不写标点 抓到）。
            # **短子句利于停顿、却低于字幕最短行**，这两头要一起满足。
            "恢复这两个字，正好把被雨中断、次日接着打的情形盖住了。"
            "两场决赛归两个协会管，条文不一样，别混着讲。",
            "",
            "示意图 · 网球时差绘制",
            (
                "WTA 条文里直接写着「因天气」",
                "而且 进了决赛就够格，不用赢",
                "ATP 靠「或恢复一场比赛」的定义",
            ),
            _SE_BOOKS_DIAGRAM,
        ),
        (
            "bu",
            "中国球员",
            "上海那张外卡，后来改成了豁免",
            "这条规则，中国球员用过。"
            "二〇二四年上海大师赛，布云朝克特拿到的是一张外卡。"
            "后来改成了特殊豁免，理由白纸黑字写着：他在北京还没打完。"
            "而那个北京是这样的。"
            "他先赢了商竣程，拿下生涯第一个五百赛级别的胜利；"
            "接着爆冷六号种子穆塞蒂，打进生涯第一个五百赛 1/4 决赛；"
            # ⚠️ 「第一个前十胜」被切成 `前｜十胜`——「十胜」是个假词。摊开写。
            "再掀翻四号种子、世界第六的卢布列夫，生涯第一次赢下世界前十。"
            # 长定语后置：「第一个在这个级别打进半决赛的中国男子球员」念起来 23 字
            # 一口气，把主语挪到句末就断得开了。
            "这个级别打进半决赛的中国男子球员，他是第一个。",
            "assets/explainer/special-exempt/bu_beijing_2024_qf.jpg",
            "Tennis TV 官方集锦画面 · 2024 年中国公开赛，布云朝克特对卢布列夫",
            (
                "2024 上海 外卡改成特殊豁免",
                "理由 他在北京还没打完",
                "那个北京 胜卢布列夫，首进半决赛",
            ),
            "",
        ),
        (
            "hour",
            "一小时",
            "赢了球，六十分钟内要打这个电话",
            "拿到它没有那么容易。流程是这样的。"
            "本周三、周四，球员关系部门先列一张表，把下周可能够格的人都写上。"
            "表交给这些人当前所在赛事的监督，监督再挨个联系，问他有没有兴趣。"
            "而球员这一头，有一道很硬的线。"
            "赢下那场决定性的比赛之后，一小时之内，"
            "必须联系监督或者球员关系部门，确认接受。"
            "没打这个电话，就从名单上拿掉。"
            "那一小时里，他刚打完一场球。",
            "",
            "示意图 · 网球时差绘制",
            (
                "周三周四 名单列出来，挨个打电话",
                "赢球之后 1 小时内必须确认接受",
                "没确认 从名单上拿掉",
            ),
            _SE_HOUR_DIAGRAM,
        ),
        (
            "cazaux",
            "最好的一次",
            "靠这一个位置，打进生涯第一个决赛",
            "那这个位置能换来什么。"
            "二〇二五年七月，卡佐在格施塔德，打进生涯第一个巡回赛半决赛。"
            "第二轮赢了四号种子埃切维里，半决赛输给二号种子布勃利克。"
            "七月二十一号，他重回世界前一百。"
            # ⚠️ 原来写「靠特殊豁免进的基茨比厄尔正赛」，切出来是 `豁免进` 和
            # `基茨｜比｜厄尔｜正｜赛`——「进」黏进「豁免」，赛事名被劈成三段、
            # 中间那个「比」独立成词。给名字两边留逗号，动词挪走。
            "下一周到了基茨比厄尔，他进正赛靠的就是特殊豁免。"
            "第二轮赢了七号种子科梅萨尼亚，1/4 决赛赢了斯特鲁夫，"
            "半决赛赢了同胞林德克内希。生涯第一个巡回赛决赛。"
            "七月二十八号，他回到了前七十五。"
            "决赛他又输给了布勃利克。连续两周，输给同一个人。"
            "十月他拿下济南公开赛冠军，第一次进入世界前六十。",
            "assets/explainer/special-exempt/cazaux_kitzbuhel_2025_sf.jpg",
            "Tennis TV 官方集锦画面 · 2025 年基茨比厄尔半决赛，卡佐对林德克内希",
            (
                "上一周 格施塔德半决赛，重回前 100",
                "下一周 靠豁免进正赛，打进决赛",
                "两周之后 世界第 75",
            ),
            "",
            "整站只留一个位置。第二个赶不上的人呢？",
        ),
    ),
    "pr-allowance": (
        (
            "count",
            "答案",
            "九站，或者九个月",
            "先给答案。ATP 规则书第九章 F 节写得很具体：停赛六个月以上、不满十二个月，"
            "保护排名给你九站，或者九个月；停满十二个月以上，给十二站或者十二个月。"
            "注意中间那个「或者」——它不是让你二选一，是两个上限同时在倒计时，"
            "谁先到算谁。九站还没用完，九个月到了，凭证一样作废。"
            "另外还有一条：每个大满贯只能用它进一次。"
            "所以这不是一张年卡，是一张按次数和按天数同时计费的票。",
            "",
            "示意图 · 网球时差绘制",
            (
                "6–12 个月 9 站或 9 个月",
                "12 个月以上 12 站或 12 个月",
                "两个上限 谁先到算谁",
            ),
            _PR_ALLOWANCE_DIAGRAM,
        ),
        (
            "use",
            "能干嘛",
            "它只管进门，不管座次",
            "那这张凭证到底能用来做什么。条文列了三件：进正赛、进资格赛、"
            "占特殊豁免位。就这三件，一件不多。"
            "紧接着的一句是禁止：不能用来定种子，也不能用来排幸运落败者的顺位。"
            "换句话说，它把你放进签表，然后就撒手了——你还是那个第二百七十位，"
            "抽签时按真实排名摆，第一轮就可能撞上头号种子。"
            "还有一层容易搞错：这个数不是你受伤那天的排名，"
            "而是停赛之后头三个月排名的平均值。",
            "",
            "示意图 · 网球时差绘制",
            (
                "能用 正赛 资格赛 特殊豁免",
                "不能用 种子 幸运落败者顺位",
                "数值 停赛后头 3 个月的均值",
            ),
            _PR_USE_DIAGRAM,
        ),
        (
            "burn",
            "怎么烧",
            "进了签表，就扣掉一站",
            "那九站怎么算。规则书那一行的原文是「用保护排名参赛的头九站」，"
            "括号里特意排除了两种：拿外卡进的，和按当时真实排名直接入围的，都不占额度。"
            "但反过来更要命——只要你的名字进了签表，这一站就扣掉了，不看输赢。"
            "条文里还补了一句：在赛地退赛并领了奖金，同样算一站。"
            "七月二十七号华盛顿，商竣程复出第一场，对锦织圭，三盘打了两个多小时，"
            "中间还叫了一次医疗暂停，最后七比六、三比六、四比六输掉。"
            "那一站，额度照扣。",
            "assets/explainer/pr-allowance/shang_washington_2026_set3.jpg",
            "ATP Tour 官方集锦画面 · 2026 年 7 月 27 日华盛顿首轮，"
            "商竣程决胜盘 3-5，记分条自证赛事与比分",
            (
                "外卡和直入 不占额度",
                "进了签表 就算一站",
                "赛地退赛领奖金 也算",
            ),
            "",
        ),
        (
            "price",
            "代价",
            "为了够到它，先放弃一站温网",
            "凭证不是白给的。门槛写在同一节的第一款：连续六个月不参加任何比赛，"
            "表演赛也算在内。也就是说，你想拿到它，得先把空白拉得更长。"
            "二〇二五年一月十三号，澳网首轮，那是他停赛前的最后一场。"
            "之后是右脚第五跖骨的手术，医生取出碎骨、切断了一半肌腱。"
            "恢复不到位，他缺席法网；而那年温网，他其实站得上场。"
            "把日子摆出来就知道这一刀有多贴身：六个月满，是七月十三号；"
            "而温网六月三十号开赛，七月十三号决赛——整届温网，正好压在最后十三天里。"
            "打，凭证就没了；不打，就得看着它整整两周从眼前过去。他选择不打。"
            "七月二十八号多伦多，他回来了，首轮输给达克沃斯。"
            "而九个月那个上限，条文算的是「复出后打的第一场比赛」——"
            "所以倒计时从这天起走，哪怕这一站他首轮就输了。",
            "",
            "示意图 · 网球时差绘制",
            (
                "门槛 连续 6 个月不比赛",
                "六个月满 2025.7.13",
                "而温网 6.30 开赛，7.13 决赛",
            ),
            _PR_BLANK_DIAGRAM,
        ),
        (
            "freeze",
            "暂停键",
            "再伤一次，剩下的能冻住",
            "钟走到一半又伤了怎么办。规则书第五款叫再伤保护：复出之后再次受伤，"
            "可以申请把剩下的站数和周数冻结起来，条件是这次至少要停满三个月，"
            "而且申请要在这三个月里交上去。复出时，冻结那一刻还剩多少，就还是多少。"
            "最多冻两次。二〇二六年二月迪拜之后，商竣程的脚伤又犯了，一停五个月——"
            "从时间上看，这正好越过了三个月那道门槛。"
            "但暂停键按不住最外面那口钟：条文另有一条三年总时效，从停赛前最后一场算起，三年内不激活就作废。"
            "规则书里专门有个案例框写这个——冻结之后剩下的周数越过三年线的，不许延用。"
            "所以冻的是站数和月数，不是那三年。"
            "不过有一层要说清楚：他本人有没有提交这份申请、ATP 有没有批，"
            "都没有公开记录，上面这些是照着条文算出来的。",
            "",
            "示意图 · 网球时差绘制",
            (
                "再停满 3 个月 可申请冻结",
                "最多 冻两次 剩多少还是多少",
                "⚠️ 冻不住 那 3 年总时效",
            ),
            _PR_FREEZE_DIAGRAM,
        ),
        (
            "record",
            "最好的一次",
            "第 957 名，用它拿了大满贯",
            "那靠这张凭证，能打出多好的成绩。答案比想象的极端。"
            "二〇一七年一月，斯蒂芬斯做了脚部手术，停赛十一个月；"
            "五月开始训练，温网复出，用的就是保护排名。"
            "美网系列赛开始时，她的世界排名是第九百五十七。"
            "多伦多四强、辛辛那提四强，排名一路冲到第八十三；"
            "而美网，是她复出后的第五站——六比三、六比零击败凯斯，捧起了奖杯。"
            "史上第一个用保护排名拿到大满贯的球员。"
            "她那一档给十二站，她只花掉五站。"
            "还有一件事：她当年也是脚。",
            "assets/explainer/pr-allowance/stephens_usopen_2017_trophy.jpg",
            "The Canadian Press 经媒体转载 · 2017 年 9 月 9 日美网女单决赛，斯蒂芬斯捧杯",
            (
                "2017 美网 复出后第 5 站",
                "赛季初世界第 957",
                "史上第一个用 PR 拿大满贯",
            ),
            "",
        ),
        (
            "now",
            "此刻",
            "世界第 270，站在大师赛正赛里",
            "八月二号，蒙特利尔大师赛正赛首轮，商竣程六比三、六比三赢了巴列霍，"
            "一小时二十一分钟。这是他伤停之后的第一场胜利——上一次赢球，还要追到一月十九号的澳网。"
            "他现在的世界排名是第二百七十，而这是一站大师赛的正赛。"
            "两个数放在一起就能看出那张凭证在做什么：它把他从报名这一关送进来，"
            "剩下的还得自己打。次轮他对十号种子卢布列夫。"
            "他还说了后面的计划：辛辛那提、一站挑战赛，然后美网。"
            "生涯最高第四十七，那是二〇二四年十月的事。",
            "assets/explainer/pr-allowance/shang_montreal_2026_r1.jpg",
            "Tennis Canada 官方集锦画面 · 2026 年 8 月 2 日蒙特利尔正赛首轮，"
            "商竣程第二盘握拳，记分条自证赛事与比分",
            (
                "8 月 2 日蒙特利尔 6-3 6-3",
                "伤停后第一胜 上一胜在 1 月",
                "世界第 270 生涯最高第 47",
            ),
            "",
            "伤没好利索就上场，额度照扣——那到底该不该上？",
        ),
    ),
    "challenger-climb": (
        (
            "field",
            "同一周",
            "对手其实没有更强",
            "先把一个直觉拆掉。很多人以为低级别难打，是因为那一档的人更凶。"
            "七月最后一周有两站同时开打，隔着一千多公里，都是室外硬地：墨西哥的洛斯卡沃斯，"
            "ATP 二百五十；加拿大的温哥华，挑战赛一百二十五。"
            "洛斯卡沃斯的一号种子是世界第十二的莱赫奇卡，八号种子是第六十七的沙波瓦洛夫。"
            "温哥华的一号种子是第一百零三的邦齐，八号种子第一百五十。"
            "洛斯卡沃斯的八号种子，比温哥华的一号种子还高三十六位，两条线中间没有交叠。"
            "女子那边同一周也一样：孟菲斯 WTA 二百五十的八号种子是第五十九，"
            "温哥华 WTA 一百二十五的一号种子是第一百一十。"
            "所以纸面上，低级别的对手不是更强，是更弱。",
            "",
            "示意图 · 网球时差绘制",
            (
                "ATP250 种子 12 到 67",
                "挑战赛 种子 103 到 150",
                "两条线 中间没有交叠",
            ),
            _CLIMB_FIELD_DIAGRAM,
        ),
        (
            "points",
            "兑换率",
            "赢五场，换不到赢两场",
            "那难在哪。先看积分表。挑战赛一百二十五的冠军，要从第一轮赢到最后，"
            "五场球，一百二十五分。同一周在洛斯卡沃斯，只要赢两场进四强，就是一百分。"
            "再往下更狠：挑战赛五十的冠军，同样赢五场，五十分；"
            "而在一千赛赢一场球，也是五十分。"
            "还有一条写在积分表下面的注：挑战赛、五百赛、二百五十赛，输掉第一轮零分；"
            "而大满贯和九十六签的一千赛，输第一轮还有十分。"
            "所以在低级别，你不是赢得少，是同样的力气换回来的东西少。",
            "",
            "示意图 · 网球时差绘制",
            (
                "挑战赛冠军 赢 5 场 125 分",
                "ATP250 四强 赢 2 场 100 分",
                "挑战赛输首轮 0 分",
            ),
            _CLIMB_POINTS_DIAGRAM,
        ),
        (
            "door",
            "那道门",
            "第 103 名进不去那一站",
            "第二层是门。邦齐世界第一百零三，在温哥华是一号种子；"
            "而同一周的洛斯卡沃斯，八号种子已经是第六十七，三张外卡里还有迪米特洛夫。"
            "第一百零三这个排名，在那一站连正赛都够不着。"
            "所以「更难」的其实不是温哥华那一站，是你根本进不去洛斯卡沃斯。"
            "再看看温哥华那张三十二人的签表里都坐着谁：波皮林，世界第一百零四，"
            "两年前刚拿过蒙特利尔大师赛的冠军，这次靠一张外卡来打挑战赛；"
            "张之臻，第一百五十八，曾经打到过世界前三十；还有人用保护排名来打这一站。"
            "往上爬的人和刚掉下来的人，挤在同一张签表里。"
            "所以打起来不轻松是真的——只是原因不是这一档的人更强。",
            "assets/explainer/challenger-climb/popyrin_usopen_2023.jpg",
            "Wikimedia Commons · CC BY-SA 4.0 · 2023 年美网首轮，波皮林",
            (
                "第 103 在温哥华是 1 号种子",
                "同一周洛斯卡沃斯 进不去正赛",
                "掉下来的和爬上去的 同一张签表",
            ),
        ),
        (
            "floor",
            "地板",
            "有保底，但只够一个人",
            "第三层是钱。这里有个反直觉的地方：地板是有的。"
            "ATP 从二零二四年起有一个叫 Baseline 的保底计划，按二零二五年的档位："
            "世界前一百保三十万美元，一百零一到一百七十五保二十万，"
            "一百七十六到二百五十保十万。二零二五年实际补出去两百多万美元。"
            "住宿也不用自己掏——规则书写着挑战赛必须给正赛球员提供免费房间，"
            "最少五晚，含早餐，资格赛和幸运落败者也有。"
            "可是打一年要花多少：最省的走法四万美元，常见的核心开销七万往上，"
            "带一个教练加一个体能师，能到二十万。"
            "十万的地板减掉七万，税前剩三万；带教练那一档直接是净亏。"
            "而规则书那句免费住宿写得很清楚：每位球员一间双床房，"
            "第三个人住进去的钱，球员自己付。"
            "地板保住的是「一个人打」，保不住「带一个人打」。",
            "",
            "示意图 · 网球时差绘制",
            (
                "176–250 保底 10 万美元",
                "最省 4 万 常见 7 万+",
                "带教练 20 万 直接净亏",
            ),
            _CLIMB_MONEY_DIAGRAM,
        ),
        (
            "gap",
            "另一半",
            "女子那边没有这块地板",
            "最后说一件容易被漏掉的事。二零一三年有过一个被反复引用的数字："
            "那一年能靠打球收支平衡的男子只有三百三十六人，女子两百五十三人。"
            "那是十三年前的数，今天不能直接拿来用——因为这项运动自己发现了问题，"
            "并且动了手：二零二四年，ATP 修了那块地板。"
            "可女子那边，到今天也没有一个对应的保底收入计划。"
            "WTA 有的是产假基金，最长十二个月带薪，三百多人符合条件，人人同额——"
            "那是另一件很重要的事，但它不是收入的下限。"
            "郑钦文现在世界第一百二十三。同样的排名放在男子那边，"
            "对应的是那条二十万美元的线。",
            "assets/explainer/protected-ranking/zheng_athens_qf_2026.jpg",
            "athens-open.com 官方图库 Day 7 · 2026 雅典站八强，郑钦文负克雷吉茨科娃",
            (
                "2013 年 只有 336 男 253 女平衡",
                "2024 年 ATP 修了地板",
                "女子 至今没有对应的保底",
            ),
            None,
            "地板只够一个人站的时候，天赋和钱，哪个先用完？",
        ),
    ),
    "entry-deadline": (
        (
            "lines",
            "那一天",
            "美网的名单，七月二十号就锁上了",
            "先看一个日期。二〇二六年美网的正赛名单，不是开赛前定的，是七月二十号定的。"
            "条文写在规则书里：大满贯正赛的报名截止，是正赛开始那一周的周一往前推六周。"
            "美网正赛八月三十号开打，正赛周的周一是八月三十一号，往前推六周，正好是七月二十号，"
            "那天美东下午五点名单锁上。"
            "这条线不是一根，是三根：巡回赛的正赛提前四周，资格赛提前三周。"
            "ATP 那本写成天数——正赛二十八天，资格赛二十一天，算下来一模一样。"
            "而美网的资格赛八月二十四号才开打。也就是说，从锁名单到打球，中间隔着整整六周的比赛。",
            "",
            "示意图 · 网球时差绘制",
            (
                "大满贯正赛 提前 6 周",
                "巡回赛正赛 4 周 资格赛 3 周",
                "美网锁在 7 月 20 日",
            ),
            _ENTRY_DEADLINE_DIAGRAM,
        ),
        (
            "cut",
            "直入线",
            "男子第 101，女子第 102",
            "那天的名单长什么样。男子的直入线落在第一百零一位，最后一个直接进正赛的是"
            "阿根廷人科梅萨尼亚，世界第一百零一；女子的线在第一百零二。"
            "线右边的名字里有两个我们熟悉的：郑钦文，世界第一百二十三，差二十二位；"
            "德雷珀，世界第一百四十七，差四十六位。"
            "德雷珀今年只打了十三场巡回赛正赛——手臂伤缺了澳网，法网前伤了膝盖，"
            "伊斯特本复出打进四强，然后手臂又把温网缺掉了。"
            "这里有个反直觉的地方：他就算在蒙特利尔和辛辛那提连赢，八月底排名回到一百以内，"
            "那张名单也不会为他改一个字。他还是得打资格赛，或者等一张外卡。"
            "之后涨的用不上，跌的也不还——这条线只认那一天的那个数。",
            "",
            "示意图 · 网球时差绘制",
            (
                "男子直入线 101 女子 102",
                "郑钦文 123 差 22 位",
                "德雷珀 147 差 46 位",
            ),
            _ENTRY_CUTLINE_DIAGRAM,
        ),
        (
            "pass",
            "有凭证的",
            "商竣程够着了那条线",
            "但线右边也不是没人进得去。那张名单上，男子有三个人是靠保护排名进的正赛，"
            "商竣程是其中之一——全场就三个。女子那边有五个。"
            "保护排名不是外卡，它是那张用旧排名报名的凭证：真实排名该掉照掉，"
            "但报名的时候可以拿它去够那条线。我们上一期讲过这套规则，"
            "商竣程是真正用上了它的那个人。",
            "assets/explainer/shang-nishikori/shang_ao2026.jpg",
            "美联社 · 2026 年 1 月 19 日，澳网首轮，商竣程正手击球",
            (
                "男子靠保护排名进的 3 人",
                "商竣程是其中之一",
                "女子那边 5 人",
            ),
        ),
        (
            "fail",
            "够不上的",
            "同一条线的另一边",
            "郑钦文没有这张凭证。规则要求连续停赛二十六周，而她去年九月硬撑着打了中网那两场，"
            "把一整段停赛切成了两截，两截各自都不够。"
            "所以七月二十号那天，她只有一个真实排名可用，一百二十三。"
            "于是同一条线上，两个中国球员落在了两边：一个拿着凭证进了正赛，"
            "一个要靠外卡或者资格赛。"
            "这条线不讲道理，也不讲人情，它只认那一天的那个数。"
            "而画这条线的理由其实很实在：赛事要提前排签表、订机票、卖门票，"
            "总得有个时刻说「就这些人了」。",
            "assets/explainer/protected-ranking/zheng_athens_qf_2026.jpg",
            "athens-open.com 官方图库 Day 7 · 2026 雅典站八强，郑钦文负克雷吉茨科娃",
            (
                "26 周必须是连着的一段",
                "她那两截各自都不够",
                "7 月 20 日 只有真实排名可用",
            ),
            None,
            "一条画在六周之前的线，该不该为伤病让一步？",
        ),
    ),
    "mandatory-1000": (
        (
            "now",
            "这一周",
            "五个大师赛全赢，第六个没去",
            "先看这一周。八月一号，加拿大大师赛在蒙特利尔开打，签表上没有辛纳，"
            "没有德约科维奇，也没有阿尔卡拉斯——男子网球最大的三个名字，一个都不在。"
            "辛纳今年把打过的每一个大师赛都赢了：印第安维尔斯、迈阿密、蒙特卡洛、"
            "马德里、罗马，五个，一个不落。他是网球史上第一个赢下赛季前四站大师赛的人，"
            "也是第一个拿到五连冠的。三周前他刚在温网卫冕。第六个大师赛，他没去。"
            "五月的法网次轮，他在场上抽了筋——那是这套赛程压在身上的分量。",
            "assets/explainer/masters-format/sinner.jpg",
            "FFT / Roland-Garros 官方 · 2026 年 5 月 28 日，法网次轮，辛纳抽筋后独自站在场上",
            (
                "2026 五个大师赛 他五个全赢",
                "第六个 蒙特利尔 他没去",
                "图为 5 月法网次轮 他抽了筋",
            ),
        ),
        (
            "rule",
            "规则书",
            "自动，而且不可申诉",
            "不去要付什么。大师赛是强制的，一年八站，规则书里管这叫 Mandatory。"
            "二〇二六年 ATP 官方规则书第八章写着：从大师赛正赛退赛的球员，"
            "一律记一次排名处罚——原话是，处罚自动生效，而且不可申诉。"
            "这里有个差别很多人搞反了：五百赛是有出路的，完成推广活动、"
            "停赛满三十天、或者符合育儿身份豁免，都能把这次处罚拿掉；"
            "大师赛这几条一条都没有。伤病本身也免不掉它。"
            "德约科维奇今年三十九岁。七月的温网，他和阿利亚西姆在八强打了五小时"
            "十五分钟，是这项赛事历史上最长的一场八强战；他赢了，然后成为公开赛"
            "年代第二年长的温网四强，只排在一九七四年的罗斯沃尔后面。"
            "这样一个人，也没去蒙特利尔。",
            "assets/explainer/masters-format/djokovic.jpg",
            "AELTC / Jon Super · 2026 年 7 月 8 日，温网八强，德约科维奇胜阿利亚西姆后",
            (
                "大师赛 一年 8 站 强制",
                "原话 自动 不可申诉",
                "39 岁打进温网四强 他也没去",
            ),
        ),
        (
            "waiver",
            "老规矩",
            "打够了，就可以少打",
            "那有没有人可以不打。有——但那是一套已经取消了的老规矩。"
            "二〇二二年版规则书第一点零八条写着三条里程碑：正赛单打满六百场、"
            "十二年服务、年满三十岁，都以承诺年一月一号为准；每达成一条，"
            "强制大师赛就少打一站。三条全占，条文的原话是完全豁免——"
            "注意这一档不是八减三等于五，是直接归零，一站都不用打。"
            "服务年的算法也写死了：第一个打满十二站有积分赛事的自然年，算第一年。"
            "后来 ATP 把这套换成了现在的奖金池扣减制，二〇二二年十二月三十一号"
            "之后就不再发新的；在那之前已经挣到、并且选择保留的人，"
            "继续按二〇二二年那本书走。德约科维奇按这三条早就够了。",
            "",
            "示意图 · 网球时差绘制",
            (
                "600 场 12 年 30 岁 各减一站",
                "三条全占 直接归零",
                "2023 年起取消 老人还留着",
            ),
            _EXEMPTION_LADDER_DIAGRAM,
        ),
        (
            "list",
            "名单",
            "它管的是报不报名，不管报了不去",
            "那为什么这次救不了他。因为豁免管的是「你用不用报名」，"
            "不管「你报了名又不去」。规则书第九章第三节，承诺球员和非承诺球员"
            "两段里写着同一句话：一旦你被接受进正赛——直入、资格赛出线、"
            "特殊豁免、幸运落败者，或者接受了一张外卡——这一站的成绩就计入排名，"
            "不管你打没打。同一段还给出唯一的出口：从来没在原始报名名单上的那一站，"
            "不记零，而是让你其他成绩多算一个。"
            "阿尔卡拉斯今年一月还在墨尔本举奖杯，之后右手腕伤了，法网、温网、"
            "蒙特利尔，他一站的名单都没进过——所以这些站在他排名里不记零。"
            "辛纳和德约科维奇都在蒙特利尔的报名名单上，然后退了赛。"
            "想省下那个零，得一开始就别报。",
            "assets/explainer/mandatory-1000/alcaraz_ao_2026.jpg",
            "Tensionado · Wikimedia Commons · CC0 · 2026 年 1 月，阿尔卡拉斯澳网夺冠",
            (
                "被接受进正赛 打没打都记",
                "没进过名单 那一站不记 0",
                "阿尔卡拉斯没报 辛纳德约报了",
            ),
        ),
        (
            "bill",
            "账单",
            "一共三笔，最疼的那笔赎不回",
            "那具体是哪几笔。第一笔是排名：那一站记零分，这一笔不可赎回。"
            "第二笔是奖金池：大师赛和年终总决赛共用一个两千一百五十万美元的固定奖金池，"
            "缺一站扣百分之二十五，缺两站扣一半，缺三站扣四分之三，缺四站以上清零。"
            "这一笔可以赎——到现场做一次推广活动，扣减从百分之二十五减到十二点五。"
            "但规则书在同一段里写死了：推广活动不解除排名处罚，而且最多只能赎回二十万美元。"
            "第三笔是罚款，只罚周五截止之后才退的，他们提前一周就说了，这一笔是零。",
            "",
            "示意图 · 网球时差绘制",
            (
                "排名 记 0 不可赎",
                "奖金池 缺 1 站 −25%",
                "到场做推广 减到 −12.5%",
            ),
            _MANDATORY_BILL_DIAGRAM,
        ),
        (
            "zero",
            "多伦多",
            "这个零，顶掉去年那个零",
            "那这个零有多疼。去年的加拿大站在多伦多，这三个人也都没去，那一站记的也是零。"
            "而世界排名是五十二周滚动的：今年这一站的成绩顶掉去年这一站的成绩，"
            "零顶掉零——这次的排名处罚落在辛纳身上，一分不差。"
            "不过判去年那次，得用去年那本书。二〇二五年版的规则书里，这一条后面"
            "还跟着半句：并且停赛下一站大师赛。那半句在实际操作里可以申诉掉——"
            "辛纳去年退了多伦多，照样打了辛辛那提，还打进决赛。"
            "而到了二〇二六年这一本，那半句干脆没了；今年反倒新开了两个豁免口，"
            "育儿身份，和连着缺两站以上可以申请抹掉零分，这两条去年一条都没有。"
            "在大家一起退赛的这一年，条文本身比去年松。",
            "assets/explainer/mandatory-1000/sobeys_stadium_2025.jpg",
            "加拿大网球协会官方 · 2025 年加拿大大师赛，多伦多 Sobeys Stadium 中心球场航拍",
            (
                "去年记 0 今年还是 0 一分不差",
                "2025 版还写着 停赛下一站",
                "2026 版这半句没了",
            ),
        ),
        (
            "stand",
            "另一个 39 岁",
            "一个用掉外卡来了，一个撤了名字",
            "加拿大人是做过努力的。去年那站在温网结束后两周就开打，今年他们把开赛"
            "推到了三周之后，就是为了给球员留出恢复的时间，赛事方原本预计今年的"
            "退赛会少一些。结果一样。赛事总监泰特罗在声明里说：我们尊重他们的决定，"
            "也理解在这样的赛程下，球员的健康必须放在第一位；但这几年退赛的频率，"
            "对这项运动来说是个更大的问题——大师赛是巡回赛的旗舰，"
            "球迷理应看到世界上最好的球员在场上。"
            "这一站还来了另一个三十九岁的人。孟菲尔斯，世界第二百二十六，"
            "今年是他的告别赛季，靠一张外卡进的正赛，第十五次打加拿大站。"
            "他说，能最后一次回来，我很高兴。"
            "两个同岁的人，一个用掉一张外卡来了，一个把名字从签表上撤了。"
            "这不是谁对谁错——是「强制」这两个字，标错了价。",
            "assets/explainer/mandatory-1000/monfils_montreal_2026.jpg",
            "加拿大大师赛官方 · 2026 年 8 月，蒙特利尔，孟菲尔斯抵达赛场",
            (
                "今年推到温网后 3 周 还是没来",
                "孟菲尔斯 39 岁 世界第 226",
                "告别赛季 靠外卡进正赛",
            ),
            None,
            "是罚得太轻，还是这两周本来就太长？",
        ),
    ),
    "comeback-middle": (
        (
            "knife",
            "动刀",
            "三十岁的德约科维奇，决定开刀",
            "先看二〇一八年一月。德约科维奇在澳网第四轮输给郑泫，那是他肘伤"
            "反复之后的第一次复出，打得很挣扎。半个月后他做了一个决定：动刀。"
            "手术在二月，动的是右肘。那之前他已经因为这个肘停了半年，"
            "整个二〇一七年下半年都没打。",
            "assets/explainer/comeback-middle/djokovic_ao_2018.jpg",
            "Joshua Sadli · Wikimedia Commons · CC BY-SA 2.0 · 2018 年 1 月 15 日，墨尔本",
            (
                "2017 下半年 停了半年",
                "2018 年 2 月 右肘手术",
                "手术前已是 12 座大满贯",
            ),
        ),
        (
            "spring",
            "那个春天",
            "输给世界第 109，跌出前 20",
            "然后是那个春天。三月印第安维尔斯，他第二轮输给世界第一百零九位的"
            "丹尼尔太郎；四月巴塞罗那，第二轮输给克利赞；五月马德里，第二轮输给"
            "埃德蒙德，排名跌到第十八，是十二年来最低。罗马之后再跌到第二十二——"
            "上一次跌出前二十，还是二〇〇六年十月。六月法网八强，他输给了"
            "世界第七十二位的切基纳托。那时候几乎所有人都认为，他回不来了。",
            "",
            "示意图 · 网球时差绘制",
            (
                "印第安维尔斯 负世界第 109",
                "马德里之后 跌到第 18",
                "罗马之后 第 22",
            ),
            _MIDDLE_FALL_DIAGRAM,
        ),
        (
            "five-months",
            "五个月后",
            "德约科维奇拿了温网，又拿美网",
            "手术之后第五个月，温网决赛，他六比二、六比二、七比六击败安德森，"
            "那是他两年来第一个大满贯。两个月后美网决赛，六比三、七比六、六比三"
            "击败德尔波特罗。同一年年底，他回到世界第一。从跌出前二十到重回第一，"
            "中间隔了七个月。",
            "assets/explainer/comeback-middle/djokovic_usopen_2018.jpg",
            "Carine06 · Wikimedia Commons · CC BY-SA 2.0 · 2018 年 8 月 28 日，美网",
            (
                "温网决赛 6-2 6-2 7-6",
                "美网决赛 6-3 7-6 6-3",
                "同年年底 重回世界第 1",
            ),
        ),
        (
            "another",
            "另一个春天",
            "同一个部位，几乎同一台手术",
            "现在换一个人。二〇一九年十月，锦织圭做了右肘手术，清掉两块骨刺——"
            "和德约科维奇同一个部位，几乎同一台手术。他当时世界排名第八，"
            "生涯最高到过第四，打进过美网决赛。这台手术让他停了十个月。"
            "复出前他感染了新冠，复出后又伤了肩。",
            "assets/explainer/shang-nishikori/nishi_2014.jpg",
            "Tennis.jp 现场报道 · 2014 年美网男单决赛，锦织圭",
            (
                "2019 年 10 月 清两块骨刺",
                "手术时 世界第 8",
                "停了 10 个月",
            ),
        ),
        (
            "same",
            "中段",
            "锦织圭也曾看起来要回来了",
            "关键在后面。二〇二一年，锦织圭打进法网第四轮、东京奥运会八强、"
            "华盛顿四强——那是他两年来第一个巡回赛四强，看起来真的要回来了。"
            "奥运八强那场的对手，正是德约科维奇：六比二、六比〇，七十一分钟。"
            "两条路在那天碰了一下，然后各走各的。半年后锦织圭做了左髋手术，"
            "整个二〇二二赛季报销，直到二〇二三年六月才重返巡回赛，再没回到前列。"
            "所以分岔不在肘：德约科维奇身上只有那一处，而锦织圭那之后还有新冠、"
            "肩伤、髋部手术。两个春天摆在一起看，前半段真的一模一样——"
            "当时谁也分不出来，包括他们自己。",
            "",
            "示意图 · 网球时差绘制",
            (
                "2021 年 奥运八强 负德约科维奇",
                "2022 年 1 月 左髋手术",
                "分岔不在肘 在肘之外",
            ),
            _MIDDLE_SAME_DIAGRAM,
        ),
        # 落到一个**正在发生**的例子上。账号所有者定的口径：**只陈述事实和现状**，
        # 不给判断、不给倾向——因为这条片子的全部结论就是「中段判断不了」，
        # 那么对一个还在中段里的人下判断，等于自己拆自己的台。
        (
            "now",
            "这一年",
            "一年之后，郑钦文在打资格赛",
            "最后说一个正在发生的。二〇二五年七月，郑钦文做了右肘手术，"
            "清掉一块压迫神经的游离碎骨。手术之前一个月，她的世界排名是第四，"
            "生涯最高。到二〇二六年八月，整整一年过去，她排在第一百二十三位。"
            "八月一日，多伦多资格赛首轮，她三比六、四比六输给世界第七十八位的"
            "塔拉鲁迪——那是她二〇二三年一月以来第一次打资格赛。"
            "以上就是全部的事实。她在哪一段，现在没有人知道。",
            "assets/explainer/protected-ranking/zheng_athens_qf_2026.jpg",
            "athens-open.com 官方图库 Day 7 · 2026 雅典站八强，郑钦文",
            (
                "2025 年 7 月 右肘手术",
                "术前第 4 一年后第 123",
                "8 月 1 日 资格赛首轮出局",
            ),
            None,
            "一年过去了，你觉得郑钦文还能打回来吗？",
        ),
    ),
    "protected-ranking": (
        (
            "now",
            "一年之后",
            "世界第 123，够不上美网那条线",
            "先看现在。郑钦文的世界排名是第一百二十三。美网正赛的直入线七月二十号"
            "锁定，大约在前一百零四，她差了将近二十位。七月十七号雅典站八强，"
            "四比六、四比六负于克雷吉茨科娃，那是锁线之前最后的机会。十天后她"
            "出现在华盛顿的签表里，靠的是一张外卡。而一年前的六月，她是世界第四。",
            "assets/explainer/protected-ranking/zheng_athens_qf_2026.jpg",
            "athens-open.com 官方图库 Day 7 · 2026 雅典站八强，郑钦文负克雷吉茨科娃",
            (
                "世界第 123 生涯最高第 4",
                "美网直入线 约前 104",
                "华盛顿那张签表 靠外卡",
            ),
        ),
        (
            "scope",
            "保护什么",
            "它替你报名，不替你保排名",
            "伤停这么久，规则里不是有保护排名吗。有，但这四个字翻拧了。"
            "ATP 规则书正文里它的名字是 Entry Protection，进赛保护。"
            "它给你的是一张用来报名的旧排名：报正赛、报资格赛、占特殊豁免位，都算数。"
            "剩下的一概不管——不算种子，不算幸运落败者的顺位，更不会让你的世界排名"
            "停下来。规则书自己有一行标题，写着 for Entry, Not Seeding。",
            "",
            "示意图 · 网球时差绘制",
            (
                "英文叫 Entry Protection",
                "报名能用 那个旧排名",
                "真实排名 该掉照掉",
            ),
            _PR_SCOPE_DIAGRAM,
        ),
        (
            "threshold",
            "门槛",
            "先得彻底停下来，26 周",
            "那她为什么没有这张凭证。因为门槛在前面：WTA 要求连续二十六周不参加"
            "任何比赛，ATP 那边写的是六个月，而且两家都把表演赛算在里头。"
            "二十六周就是半年——你得整整半年一场都不打，才够得着它。",
            "assets/explainer/zheng-eala/zheng_clay.jpg",
            "账号所有者提供 · 郑钦文反手随挥",
            (
                "WTA 连续 26 周",
                "ATP 6 个月",
                "表演赛也算在里头",
            ),
        ),
        (
            "gap",
            "断在哪",
            "28.8 周，却一分不算",
            "她停了多久。温网之后到二月复出多哈，中间只打过一站：二零二五年九月的"
            "中网，两场球，第二场对诺斯科娃还中途退了赛。就是这一站，把一整段停赛"
            "切成了两半——前面十点七周，后面十八点一周。两截加起来二十八点八周，"
            "比门槛还多出两周多。可条文只认连着的一段，两截各自都不够。",
            "",
            "示意图 · 网球时差绘制",
            (
                "中网只打了 2 场",
                "前段 10.7 周 后段 18.1 周",
                "合计 28.8 周 一分不算",
            ),
            _PR_GAP_DIAGRAM,
        ),
        (
            "cost",
            "代价",
            "它保护的是彻底停下来的人",
            "把条文一条条对下来，她够不上这张凭证。所以过去这一年，排名一路往下，"
            "没有任何机制替她刹住。有一点要说清楚：她本人到底申请过没有、"
            "有没有拿到过豁免，都没有公开记录，上面这些是照着规则算出来的。"
            "但规则本身写得很直白——它保护彻底停下来的人。九月硬撑着打的那两场，"
            "一年后的价码是美网正赛的一个位置。",
            "assets/explainer/wildcard/zheng_athens_2026.jpg",
            "athens-open.com 官方图库 Day 5 · 2026 雅典站第二轮，郑钦文正手击球",
            (
                "按条文算 她够不上",
                "排名一路掉 没有刹车",
                "价码是一个正赛名额",
            ),
            None,
            "硬撑着打完那两场，和彻底停满半年，换你会怎么选？",
        ),
    ),
    "lucky-loser": (
        (
            "this-week",
            "这一周",
            "那场资格赛，托米奇一分都没打",
            "先看这一周。洛斯卡沃斯的资格赛最后一轮，托米奇因为肠胃问题弃权，"
            "一分都没打，这一站对他来说本来就结束了。可几个小时后正赛有人退出，"
            "空出一个位置，按规则那个位置归他。三天后，他 6-2、6-4 赢了世界第二十六的"
            "哈恰诺夫，那是他七年来最大的一场胜利。同一周华盛顿也有一个："
            "资格赛最后一轮，斯瓦伊达在第三盘 0 比 2 时中途退出，输给了十七岁的"
            "克鲁兹·休伊特——几天后他同样出现在正赛签表里。让他们站上那片场地的身份，"
            "规则里叫幸运落败者。",
            "assets/explainer/lucky-loser/tomic_los_cabos_2026.jpg",
            "Tennis TV / @abiertoloscabos · 2026 洛斯卡沃斯，托米奇对哈恰诺夫",
            (
                "资格赛末轮 他弃权了",
                "递补进正赛 赢下世界第 26",
                "同一周 华盛顿也有一个",
            ),
        ),
        (
            "how",
            "空位给谁",
            "多数时候按排名，有时候要抽签",
            "空出来的位置给谁，分两种情况。多数时候很简单：最后一轮输掉的那批人里，"
            "排名最高的先补进去。但有一种要抽签——如果资格赛还没打完，正赛的位置"
            "就已经空着了，那么排名最高的两个人抽签决定，谁抽到谁进；空出两个位置，"
            "就是三个人一起抽。为什么要多这一道？想一下就明白：位置已经空在那儿，"
            "补位又完全按排名，那排名最高的那个人最后一轮赢也进、输也进，"
            "这场球认不认真都一样。抽签把它掰回来——输了不再是稳进，只是有机会。",
            "",
            "示意图 · 网球时差绘制",
            (
                "一般 排名最高的先补",
                "位置早空着 就要抽签",
                "抽签让输球重新有代价",
            ),
            _LUCKY_LOSER_PICK_DIAGRAM,
        ),
        (
            "rublev",
            "第一个冠军",
            "「输的那个人，是幸运的」",
            "这个身份能走多远？2017 年乌马格，卢布列夫资格赛最后一轮输了，"
            "丘里奇退赛，他补了进去——然后一路赢到决赛，6-4、6-2 击败四号种子洛伦齐，"
            "拿下十九岁那年生涯第一个冠军，颁奖的是伊万尼塞维奇。当天他自己在社媒上"
            "只写了一句：输的那个人是幸运的，我赢下了第一个 ATP 冠军。",
            "assets/explainer/lucky-loser/rublev_umag_2017_trophy.jpg",
            "Merlo de Graia · 卢布列夫本人社媒 2017-07-24 · 乌马格夺冠",
            (
                "2017 乌马格 资格赛末轮输掉",
                "递补进正赛 一路赢到夺冠",
                "19 岁 生涯第一个冠军",
            ),
        ),
        (
            "gauff",
            "被叫回来",
            "开赛前十五分钟，高芙回到球场",
            "两年后的林茨更夸张。高芙资格赛直落两盘输给科尔帕奇，本来已经出局。"
            "首轮开打前十五分钟，萨卡里手腕伤退，已经收拾东西的她被叫了回来。"
            "接下来她连赢五场，包括头号种子贝尔腾斯，决赛 6-3、1-6、6-2 击败"
            "奥斯塔彭科。十五岁七个月，2004 年以来最年轻的 WTA 冠军，也是历史上"
            "第三个以这个身份夺冠的女子球员。",
            "assets/explainer/lucky-loser/gauff_linz_2019_trophy.jpg",
            "wtatennis.com 官方图 · 2019 林茨决赛，高芙夺冠",
            (
                "资格赛已经输了 直落两盘",
                "萨卡里伤退 赛前 15 分钟顶上",
                "15 岁 7 个月 拿下冠军",
            ),
        ),
        (
            "wall",
            "到不了第五场",
            "但大满贯，没人走过第四轮",
            "不过有一堵墙，到今天还没人撞开。大满贯要赢七场才拿冠军，而靠这个身份"
            "进来的人，一个都没打进过八强——第四轮就是尽头。摸到过那儿的没几个："
            "1995 年温网的诺曼，2023 年法网的阿瓦涅相，2025 年澳网的利斯，"
            "同年温网的谢拉，还有今年法网的德容。利斯那次最接近，再赢一场"
            "就是史上第一个。她没赢下来。",
            "",
            "示意图 · 网球时差绘制",
            (
                "至今 0 人打进大满贯八强",
                "第 4 轮就是天花板",
                "利斯 2025 澳网 差一场",
            ),
            _LUCKY_LOSER_WALL_DIAGRAM,
            "如果名额早就空着，最后一轮那场球，你还会拼吗？",
        ),
    ),
    "hawkeye": (
        (
            "human",
            "人眼时代",
            "这条线，最后归谁喊",
            "在鹰眼出现以前，一条线是否被压到，全靠站在线后的这些人。他们弯着腰、"
            "盯着脚下那条白线，一站就是一整场；这套人工司线的做法，在网球场上"
            "沿用了上百年。可人眼有极限。2004 年美网四分之一决赛，小威廉姆斯"
            "遭遇多个关键球的误判被淘汰出局——她一记落在界内的回球，被主裁改判"
            "出界；赛后当值主裁被撤换、官方公开道歉。那成了回放技术上马的"
            "最后一根稻草，仅仅两年后，鹰眼挑战制正式走进大满贯。",
            "assets/explainer/hawkeye/us_open_court.jpg",
            "Beyond My Ken · CC BY-SA 4.0 · Wikimedia Commons · 2021 US Open",
            (
                "人工司线在网球沿用上百年",
                "2004 美网：小威压线球被改判出界",
                "主裁被撤换 · 两年后鹰眼进大满贯",
            ),
        ),
        (
            "mechanism",
            "技术原理",
            "毫米级的电子眼，怎么看球",
            "鹰眼到底怎么判？根据 Sony 官方说明，它的球追踪由二维视觉处理和"
            "三维三角测量组成，通常架设八到十二台高速摄像机，最高每秒 340 帧，"
            "系统误差小于两毫米。球员申请复核后，系统会根据多个机位的数据，"
            "生成球飞行轨迹与落点的三维可视化。首年挑战成功率只有三成左右——"
            "数据证明，肉眼真的会看错。",
            "",  # no licensable real photo of the tech -> original schematic
            "示意图 · 网球时差绘制",
            (
                "8–12 台高速摄像机，最高 340fps",
                "2D 视觉处理 + 3D 三角测量算落点",
                "系统误差小于 2 毫米",
            ),
            _HAWKEYE_DIAGRAM,
        ),
        (
            "today",
            "当今现状",
            "站了上百年的司线员，正在退场",
            "如今，电子司线正在取代人工。截至 2026 年，澳网、美网和温网都已"
            "完成转换；ATP 更宣布全部巡回赛全面启用电子司线。温网的草地上，"
            "已经没有司线员站在线后了——那些站了上百年的身影，正在退出网球舞台。",
            "assets/explainer/hawkeye/today.jpg",
            "wimbledon.com",
            (
                "澳网 · 美网 · 温网 已完成转换",
                "ATP 全部巡回赛启用电子司线",
                "线后不再站人，全部交给摄像机",
            ),
        ),
        (
            "exception",
            "法网例外",
            "2026 年，这把椅子还在场边",
            "但四大满贯里还有一个例外，就是法网。截至 2026 年，只有它仍然保留"
            "人工司线，没有采用实时电子司线。今年罗兰加洛斯场边还摆着"
            "罗兰加洛斯场边的司线员座椅——澳网、美网、温网早已把它撤走，"
            "只有这里还留着。",
            "assets/explainer/hawkeye/rg2026_linejudge_chair.jpg",
            "CC BY-SA 4.0 · Wikimedia Commons · 2026 Roland Garros",
            (
                "图为 2026 年法网的司线员座椅",
                "四大满贯中，仅法网保留人工司线",
                "另外三站已全部撤掉这个岗位",
            ),
        ),
        (
            "why",
            "红土的底气",
            "主裁下椅，蹲下来看那个印子",
            "法网敢这么坚持，底气就在脚下这片红土。球砸下去会留下一个印子，"
            "主裁可以走下裁判椅，蹲到线边看那个球印，再用眼睛给出最后一声判罚。"
            "别的场地上，球过了就没了；只有红土会把证据留在地上。"
            "那你觉得，法网还能坚持多久？什么时候也会换成电子司线？"
            "评论区聊聊。",
            "assets/explainer/hawkeye/ball_mark.jpg",
            "用户提供",
            (
                "球砸在红土上，会留下一个印子",
                "主裁走下裁判椅，蹲到线边验印",
                "这就是法网敢坚持人工的底气",
            ),
            "",
            "你觉得法网什么时候会改用电子司线？",
        ),
    ),
    # Same five-beat shape as hawkeye — the old way, the force that broke it,
    # the rule change, the holdout, and a question worth arguing about. Facts
    # come from the story's own verified set plus en.wikipedia "Tennis ball":
    # white until 1972, ITF yellow in 1972 for television, Wimbledon white
    # until 1986, "optic yellow", and the poll where most people said green.
    # A live story, so every claim is pinned to a source: the 12-day format and
    # the two week-long holdouts from BBC Sport; the 2025 draw expansion from
    # 56 to 96 at Canada and Cincinnati; Sinner's and Tetreault's words as
    # quoted by NBC Sports / Tennis Canada's announcement; Tsitsipas via BBC.
    # 重排过一次，依据是三个平台的后台数据：中位观众都停在第 ① 屏。原来六屏，
    # 「为什么变成两周」的答案在 ② 屏、最有画面感的辛纳抽筋在 ③ 屏、收尾那一问
    # 在 ⑥ 屏——按这条片子在小红书的人均观看 53 秒算，⑤⑥ 两屏一个人都走不到，
    # 那一问等于没问。
    #
    # 所以：答案连同示意图提到 ①，辛纳提到 ②，账单和那一问放 ③，六屏并成四屏。
    # 705 字 → 341 字，118 秒 → 58 秒。每个硬事实都留着，砍掉的是「画面里就是
    # 巴黎大师赛的球场」这类解说和重复铺陈。paris.jpg 和 djokovic.jpg 因此退出
    # 画面，它们承载的事实降级成要点条目——素材还在库里，credits.json 不动。
    "masters-format": (
        (
            "expand",
            "答案",
            "签表从 56 人扩到 96 人",
            "大师赛原本一周打完。2025 年，加拿大站和辛辛那提站把正赛签表从五十六人"
            "扩到九十六人，赛期拉长到十二天。九站大师赛里，现在已经有七站是十二天，"
            "只剩巴黎和蒙特卡洛还是一周。更多的比赛日，就是更多的门票和转播时段。",
            "",
            "示意图 · 网球时差绘制",
            (
                "正赛签表 56 人 → 96 人",
                "9 站里已有 7 站改成 12 天",
                "更多比赛日＝更多门票和转播",
            ),
            _MASTERS_FORMAT_DIAGRAM,
        ),
        (
            "withdraw",
            "代价",
            "5-1 领先，然后辛纳抽筋了",
            "2026 年法网第二轮，辛纳 6-3、6-2、5-1 领先，离赢球只差一局。"
            "然后他抽筋了，接连丢掉十五分，三十连胜就此终止。两个月后，"
            "蒙特利尔赛前一周他退赛了；同一天德约科维奇也退了，"
            "在他们之前阿尔卡拉斯已经退了。",
            "assets/explainer/masters-format/sinner.jpg",
            "rolandgarros.com 官方图 · 2026 法网第二轮 辛纳",
            (
                "2026 法网次轮，5-1 领先时抽筋",
                "连丢 15 分，30 连胜终结",
                "同日德约退赛，此前阿尔卡拉斯已退",
            ),
        ),
        (
            "whose",
            "账单",
            "一年只有一周休息",
            "球员那边说得更直接。弗里茨对 ESPN 说：我一整年只有一周休息，太离谱了。"
            "顶尖球员的赛季跨越十一个月，蒙特利尔之后紧接着辛辛那提，再往后就是美网。"
            "赛事总监也承认，这类临时退赛已经不是某一站的问题。",
            "assets/explainer/masters-format/crowd.jpg",
            "CC BY-SA 2.0 · Wikimedia Commons · 蒙特利尔中心球场",
            (
                "弗里茨：我一年只有一周休息",
                "赛季跨越 11 个月，中间几乎不停",
                "总监：临时退赛已成行业问题",
            ),
            "",
            "更长的大师赛，到底是给谁看的？",
        ),
    ),
    # Facts from en.wikipedia "Wimbledon Championships": Wimbledon and the
    # French Open are the only Slams where a same-day queue still reaches the
    # show courts, cards numbered from 2003, one queue from 2008 with ~500
    # seats per show court, overnight camping permitted with loos and water
    # laid on, colour-coded wristbands handed out at dawn, returned tickets
    # resold at 2:30pm for charity, and the millionth card on 28 June 2010.
    "queue": (
        (
            "why",
            "唯二两站",
            "当天排队，也能坐进中央球场",
            "四大满贯里，只有温网和法网，你可以早上手里没票，晚上坐进主球场。"
            "代价写在门口：排一晚上队。这条队伍甚至有自己的专名，就叫 The Queue，"
            "大写的 Q。画面是 2011 年温网第二天的队伍——草地上那条白线，"
            "就是队伍要走的路线。",
            "assets/explainer/queue/queue.jpg",
            "Carine06 · CC BY-SA 2.0 · Wikimedia Commons · 2011 温网第二日的队伍",
            (
                "只有温网和法网能当天排队进主场",
                "这条队有专名：The Queue",
                "图为 2011 年温网第二天",
            ),
        ),
        (
            "card",
            "编号卡",
            "一张卡，一个号码",
            "排上队，你会拿到一张排队卡，上面印着编号——从 2003 年起就开始编了。"
            "2008 年之后合并成一条队，三块主球场每天各留大约五百个座位。"
            "想中途离队上个厕所？得先跟旁边的人或者引导员说好你的位置。"
            "2011 年的一整套是这样：两张排队卡、一条腕带，还有票——"
            "场外票二十镑，一号球场七十四镑，中央球场一百镑。",
            "assets/explainer/queue/cards.jpg",
            "Carine06 · CC BY-SA 2.0 · Wikimedia Commons · 2011 温网排队卡与门票",
            (
                "排队卡自 2003 年起编号",
                "2008 年起单一队列，每场约 500 座",
                "图为 2011 年的排队卡与门票",
            ),
        ),
        (
            "overnight",
            "睡在草地上",
            "想进主球场，先睡一晚",
            "想坐进主球场，通常得在草地上睡一晚。全英俱乐部不但允许，"
            "还给排队的人备了厕所和饮水。维基百科上有一句写得很妙："
            "这种通宵露宿，按法律算是游荡；但在温网，它本身就是体验的一部分。"
            "2012 年的队伍就是这么排的。",
            "assets/explainer/queue/fans.jpg",
            "Carine06 · CC BY-SA 2.0 · Wikimedia Commons · 2012 温网第二日的队伍",
            (
                "主球场的票通常要排通宵",
                "俱乐部备好厕所和饮水",
                "法律上算游荡，这里算体验",
            ),
        ),
        (
            "dawn",
            "天亮之后",
            "腕带按球场分颜色",
            "天一亮，队伍开始朝场地挪动。引导员沿着队伍走，发腕带——按球场分颜色。"
            "到了售票处，拿腕带加上钱，才换成真正的门票。"
            "如果你只想进园区看外场，那不必过夜，当天来排就够了。"
            "队伍最后一段要走过一座天桥。",
            "assets/explainer/queue/bridge.jpg",
            "Clavecin · Public domain · Wikimedia Commons · 温网排队末段的天桥",
            (
                "引导员按球场发彩色腕带",
                "腕带加票款在售票处换门票",
                "只看外场不必过夜",
            ),
        ),
        (
            "million",
            "一百万张",
            "这张卡，编到了一百万号",
            "2010 年 6 月 28 日下午两点四十，第一百万张编号排队卡发了出去，"
            "拿到它的是来自南非的 Rose Stanley。排完队还有纪念贴纸——"
            "晴天一款，雨天一款；1994 年那一版上写着"
            "「我在温网排过队」。另外，提前离场的人退回来的票，"
            "下午两点半会重新发售，钱全部捐给慈善。八强打完，主球场的排队就结束了。"
            "那你呢——为一张票在草地上睡一晚，你愿意吗？",
            "assets/explainer/queue/sticker.jpg",
            "Amanda Slater · CC BY-SA 4.0 · Wikimedia Commons · 1994 年温网排队纪念贴纸",
            (
                "2010.6.28 发出第 100 万张排队卡",
                "退票下午 2:30 再售，钱捐慈善",
                "图为 1994 年的排队纪念贴纸",
            ),
            "",
            "为一张票在草地上睡一晚，你愿意吗？",
        ),
    ),
    # Every fact traces to en.wikipedia "Rufus the Hawk". Note what the
    # pictures are and are not: the first three are Rufus himself (two
    # uploaded by Avian Environmental, who actually operate him, one from
    # the 2012 Olympics), while beat 4 shows the same operator's bird at
    # Westminster Abbey — a Harris hawk on the same job, not necessarily
    # this bird, so the beat says so on screen rather than implying it.
    "rufus": (
        (
            "badge",
            "一只鹰",
            "工牌上写着「赶鸟员」",
            "温布尔登有一名员工，工牌上的职位是三个词：Bird Scarer，赶鸟员。"
            "它叫 Rufus，一只哈里斯鹰，2008 年第一次来上班的时候，才 18 周大。"
            "它接的是上一任的班——上一只鹰叫 Hamish。全英俱乐部说它是"
            "「温网大家庭的重要一员」；它有自己的推特，也有自己的工牌。",
            "assets/explainer/rufus/badge.jpg",
            "AvianEnvironmental · CC BY-SA 4.0 · Wikimedia Commons · 温网现场",
            (
                "工牌职位：Bird Scarer 赶鸟员",
                "2008 年首次上岗，当时 18 周大",
                "接的是上一只鹰 Hamish 的班",
            ),
        ),
        (
            "patrol",
            "它的工作",
            "四十二英亩，全归它管",
            "它的活儿说起来简单：把鸽子赶走。鸽子最爱停的地方，是中央球场的屋顶。"
            "整个园区四十二英亩，Rufus 全年巡场，赛期这两周每天到岗。"
            "清晨还没开门的时候，它站在栏杆上，把整片园子看了一遍。"
            "但它并不抓鸽子——它全部的工作，只是让鸽子知道：这片天空有天敌。",
            "assets/explainer/rufus/patrol.jpg",
            "AvianEnvironmental · CC BY-SA 4.0 · Wikimedia Commons · 清晨的温网园区",
            (
                "42 英亩园区，全年巡场",
                "鸽子最爱停中央球场屋顶",
                "它不抓鸽子，只让鸽子知道有天敌",
            ),
        ),
        (
            "stolen",
            "失踪三天",
            "2012 年，它被人偷走了",
            "2012 年 6 月 28 日，Rufus 在车后座被人偷走。它平时戴着无线电发射器，"
            "本来可以追踪——但发射器晚上会取下来，被偷的那一刻，谁也找不到它。"
            "这件事引发了全球关注，媒体称它是「世界上最出名的鸟」。三天后，"
            "它在温布尔登公地被发现，交给了防止虐待动物协会：身体没事，"
            "只有一条腿有点酸。那年夏天，它照常上班——在伦敦奥运会。",
            "assets/explainer/rufus/olympics.jpg",
            "Catherine Wright · CC BY-SA 2.0 · Wikimedia Commons · 2012 伦敦奥运会期间",
            (
                "2012.6.28 从车后座被偷走",
                "发射器夜里取下，当时追不到",
                "三天后在温布尔登公地找回",
            ),
        ),
        (
            "elsewhere",
            "不止温网",
            "教堂、医院、机场都请过它",
            "温网只是它的一份工作。威斯敏斯特教堂、医院、机场、垃圾填埋场，"
            "都请过它去赶鸟。同一家公司也在威斯敏斯特一带做赶鸟作业。"
            "不过它也不是全无敌手——2013 年有报道说，它被戴兜帽的人吓到过，"
            "还被一群乌鸦赶跑过。",
            "assets/explainer/rufus/abbey.jpg",
            "AvianEnvironmental · CC BY-SA 4.0 · Wikimedia Commons · 威斯敏斯特一带赶鸟作业",
            (
                "教堂、医院、机场、垃圾场都请过",
                "图为同一公司在威斯敏斯特的作业",
                "2013 年它被一群乌鸦赶跑过",
            ),
        ),
        (
            "successor",
            "谁来接班",
            "接班人没生成，无人机来了",
            "从 2008 年上岗算起，Rufus 已经干了快二十年。2025 年，驯鹰师想给它"
            "找个伴——一只叫 Pamela 的母鹰，指望生出个接班人；结果 Pamela 对它"
            "有攻击性，两只鹰没能走到一起。2026 年，驯鹰师说出了另一个担心："
            "这份工作，迟早会被无人机取代。全英俱乐部的回应是：没有换掉它的打算。"
            "这家公司在伦敦市区放飞的猛禽，不止它一只。"
            "那你觉得呢——赶鸽子这件事，该交给鹰，还是交给无人机？",
            "assets/explainer/rufus/city.jpg",
            "AvianEnvironmental · CC BY-SA 4.0 · Wikimedia Commons · 伦敦市区赶鸟作业",
            (
                "2025 年配对母鹰 Pamela 未成",
                "全英俱乐部：没有换掉它的打算",
                "图为同一公司放飞的猛禽",
            ),
            "",
            "赶鸽子该交给鹰，还是交给无人机？",
        ),
    ),
    # Dress-code details are quoted from the Championships' own clothing
    # guidelines as summarised on en.wikipedia "Wimbledon Championships":
    # first enforced 1963, no solid mass of colouring, trims no wider than
    # 1cm, backs entirely white, and from 2023 women may wear mid/dark
    # undershorts no longer than their shorts or skirt. The reason for that
    # last change — period anxiety — is the framing of the NYT/Athletic piece
    # the article cites, not our inference.
    "wimbledon-whites": (
        (
            "before",
            "白衣时代",
            "白衣比规则老得多",
            "你在温网看到的那一片白，不是审美，是规定。但穿白衣打球这件事，"
            "比规定老得多。1920 年代的球场上还没有谁强制，"
            "大家本来就穿白的。温网做的，是把这个习惯在 1963 年正式写成了"
            "规则：参赛者必须穿全白，或者近乎全白。",
            "assets/explainer/wimbledon-whites/historic.jpg",
            "Public domain · State Library of NSW · 1920 年代网球场",
            (
                "图为 1920 年代的网球场",
                "那时白衣是习惯，不是规定",
                "温网 1963 年把它写成规则",
            ),
        ),
        (
            "rule",
            "写成规则",
            "1963 年立的规矩，至今没松",
            "从 1963 年那份着装规定起，这条规矩就没有松过。2023 年的"
            "温网男单决赛，阿尔卡拉斯对德约科维奇——决赛场上，两个人从头到脚，"
            "还是白的。",
            "assets/explainer/wimbledon-whites/final2023.jpg",
            "CC BY-SA 2.0 · Wikimedia Commons · 2023 温网男单决赛",
            (
                "1963 年首次成文执行",
                "图为 2023 年温网男单决赛",
                "决赛场上依然全身白",
            ),
        ),
        (
            "howstrict",
            "严到毫米",
            "彩边不能超过一厘米",
            "严到什么程度？细则写得非常细：不得有整块色彩；彩色滚边不得超过一厘米；"
            "上衣或裙子的后背，必须完全是白的。短裤、帽子、发带、袜子，"
            "连鞋面都要以白色为主。2026 年温网的莱巴金娜，可以照着条文一条条对："
            "遮阳帽白的，护腕白的，球裙白的，球鞋白的；领口那道深色细边，"
            "就是「不得超过一厘米」的那一道。她身上唯一一处深色，"
            "是裙摆下面露出的那截打底短裤——那是 2023 年才松开的口子，最后一屏我们细说。",
            "assets/explainer/wimbledon-whites/headtotoe.jpg",
            "danielcooper850 · CC BY-SA 4.0 · Wikimedia Commons · 2026 温网 莱巴金娜",
            (
                "彩色滚边不得超过 1 厘米",
                "上衣或裙子的后背必须全白",
                "帽子、发带、袜子、鞋面都要以白为主",
            ),
        ),
        (
            "hidden",
            "看不见的地方",
            "这条规矩管到内衣",
            "它还管到看不见的地方——内衣也必须是白的。对女子选手来说，"
            "这就不只是麻烦了。生理期那几天，穿一身全白站上球场，"
            "是实打实的心理负担；而很长一段时间里，这件事没有人拿到台面上讲。"
            "2022 年，莱巴金娜在这片草地上夺冠；"
            "而这条规矩松口，还要再等一年。",
            "assets/explainer/wimbledon-whites/closeup2022.jpg",
            "Peter Menzel · CC BY-SA 2.0 · Wikimedia Commons · 2022 温网 莱巴金娜",
            (
                "规则一度要求内衣也是白色",
                "生理期上场是实打实的负担",
                "图为 2022 年温网冠军莱巴金娜",
            ),
        ),
        (
            "relax",
            "松了一道口子",
            "2023 年，只让了这一处",
            "2023 年，温网松了一道口子：女子选手终于可以穿非白色的内搭，"
            "规则写得很具体——纯色、中深色的打底短裤，长度不能超过外面的"
            "短裤或裙子。这是这条规矩立起来之后，第一次为看不见的地方让步。"
            "除此之外，一切照旧，整个园区还是一片白。那你觉得，"
            "这条百年白衣规矩，还该留着吗？",
            "assets/explainer/wimbledon-whites/grounds.jpg",
            "CC BY-SA 4.0 · Wikimedia Commons · 2022 温网园区",
            (
                "2023 年起可穿中/深色打底短裤",
                "长度不得超过短裤或裙子",
                "其余规定一概照旧",
            ),
            "",
            "这条百年白衣规矩，还该留着吗？",
        ),
    ),
    # Facts checked against en.wikipedia "Isner-Mahut match at the 2010
    # Wimbledon Championships" and against the plaque itself, which the All
    # England Club engraved with the score, the dates and the duration. Note
    # the story's own fact file said the scoreboard gave out at 50-50; the
    # article is more precise — the courtside board froze at 47-47 and went
    # dark, and it was the website's scoreboard that was reset at 50-50.
    "longest-match": (
        (
            "draw",
            "首轮抽签",
            "一场被排在 18 号场的首轮球",
            "2010 年温网首轮，23 号种子伊斯内尔，对上从资格赛打进正赛的马胡。"
            "这种签通常没人会多看一眼，比赛也就被排在了 18 号场——一片外场。"
            "6 月 22 日傍晚 6 点 13 分开球时，没人知道它会打三天。"
            "到第二天夜里，屋顶上站满了人，全世界都挤过来了。",
            "assets/explainer/longest-match/court18.jpg",
            "CC BY-SA 2.0 · Wikimedia Commons · 2010 温网 18 号场，比赛第二天夜里",
            (
                "2010 温网首轮，排在 18 号场",
                "23 号种子伊斯内尔 对 资格赛选手马胡",
                "图为第二天夜里，屋顶已站满人",
            ),
        ),
        (
            "rule",
            "没有抢七",
            "第五盘，必须净胜两局才算完",
            "问题出在当年的规则上。2010 年，除了美网，大满贯的第五盘都不打抢七："
            "打到 6 比 6 之后不会有抢七来收尾，两个人得一直打下去，直到某一方"
            "净胜两局。第一天天黑，第五盘还没开始就被迫中断；第二天下午两点零五分"
            "接着打，一局一局，谁也破不了谁的发球局。",
            "assets/explainer/longest-match/day2.jpg",
            "CC BY-SA 2.0 · Wikimedia Commons · 2010 温网次日，马胡准备发球",
            (
                "2010 年第五盘不打抢七",
                "6-6 之后必须净胜两局",
                "第一天天黑中断，第二天接着打",
            ),
        ),
        (
            "board",
            "记分牌罢工",
            "程序只写到 47 比 47",
            "打到后来，先撑不住的是记分牌。场边那块电子记分牌停在 47 比 47，"
            "然后直接黑屏——IBM 的工程师说，程序只编到 47 比 47。官网的在线记分牌"
            "多撑了一会儿，到 50 比 50 时被重置。16 号场的一块牌子上，"
            "显示的是隔壁 18 号场的比分：第五盘，51 比 50。那天一直打到 59 比 59，"
            "天又黑了，再停。",
            "assets/explainer/longest-match/scoreboard.jpg",
            "CC BY 2.0 · Wikimedia Commons · 2010 温网 16 号场记分牌，第五盘 51-50",
            (
                "场边记分牌停在 47-47 后黑屏",
                "IBM：程序只编到 47-47",
                "第二天打到 59-59 天黑再停",
            ),
        ),
        (
            "final",
            "11 小时 5 分钟",
            "70 比 68，纸都快写不下了",
            "第三天下午四点四十七分，伊斯内尔终于以 70 比 68 拿下第五盘。全场"
            "打了 183 局，总时长 11 小时 5 分钟；光第五盘就打了 8 小时 11 分钟——"
            "比在那之前最长的一整场比赛还要长。伊斯内尔发出 113 记 ACE，马胡 103 记，"
            "两个人都改写了纪录。这场球的官方记分卡，一共写满了七页。",
            "assets/explainer/longest-match/scorecard.jpg",
            "Public domain · Wikimedia Commons · 该场官方记分卡（七页）",
            (
                "183 局，总时长 11 小时 5 分钟",
                "光第五盘就打了 8 小时 11 分钟",
                "ACE：伊斯内尔 113，马胡 103",
            ),
        ),
        (
            "rules",
            "纪录封存",
            "规则改了，它不可能再被打破",
            "温网后来在 18 号场的墙上立了一块牌子，把日期、比分和时长都刻了上去。"
            "而规则也改了：2019 年温网开始，第五盘 12 比 12 打抢七；2022 年起，"
            "四大满贯统一改成决胜盘 6 比 6 打十分抢十。也就是说，从规则上讲，"
            "这场 11 小时 5 分钟不可能再被超过了。那你觉得，这样的比赛，"
            "以后还会不会再有？",
            "assets/explainer/longest-match/plaque.jpg",
            "Jonotennis · CC BY-SA 3.0 · Wikimedia Commons · 18 号场纪念牌",
            (
                "温网在 18 号场立牌纪念",
                "2019 年起第五盘 12-12 打抢七",
                "2022 年四大满贯统一十分抢十",
            ),
            "",
            "这样的比赛，以后还会有吗？",
        ),
    ),
    "yellow-ball": (
        (
            "white",
            "白球时代",
            "一百年里，网球一直是白的",
            "打开电视看网球，那颗荧光黄的球，你早就习惯了。但它变成黄色，其实还"
            "不到六十年。1972 年以前，比赛用球一直是白的，偶尔也用黑球——"
            "从现代网球在草地上诞生算起，白球陪着这项运动走了将近一百年。"
            "那个年代打的都是白球。",
            "assets/explainer/yellow-ball/white_era.jpg",
            "CC0 · Wikimedia Commons · Slazenger 白色网球（vintage）",
            (
                "1972 年以前，比赛用球是白色",
                "偶尔也用黑球，规则只认这两色",
                "白球陪网球走了近一百年",
            ),
        ),
        (
            "tv",
            "电视时代",
            "问题不在场上，在屏幕上",
            "让白球退场的，不是球员，是电视。彩色电视普及之后，转播里冒出一个"
            "尴尬的问题：白球在屏幕上太难追踪，观众盯着看，常常跟丢那颗球。"
            "研究给出了结论——换成荧光色，会明显更好认。于是一颗球的颜色，"
            "第一次由镜头而不是球场说了算。",
            "assets/explainer/yellow-ball/broadcast.jpg",
            "AndrewHenkelman · CC BY-SA 4.0 · Wikimedia Commons · 2020 US Open",
            (
                "彩色电视普及，白球在屏幕上难追踪",
                "研究结论：荧光色更容易被看见",
                "推动改色的是转播，不是球员",
            ),
        ),
        (
            "switch",
            "正式改色",
            "1972 年，黄色写进规则",
            "1972 年，国际网联正式引入黄色比赛用球，理由写得很直白：电视上"
            "更容易看清。这种荧光色有个专门的名字，叫 optic yellow，光学黄。"
            "它很快就流行开来。直到今天，ITF 认可的比赛用球颜色仍然只有两种："
            "白色，和黄色。",
            "assets/explainer/yellow-ball/optic_yellow.jpg",
            "Steven Pisano · CC BY 2.0 · Wikimedia Commons · 2013 US Open 球童手持新球",
            (
                "1972 年 ITF 正式引入黄色用球",
                "这种荧光色叫 optic yellow",
                "至今 ITF 只认白、黄两种颜色",
            ),
        ),
        (
            "exception",
            "温网例外",
            "温网又多用了十四年白球",
            "但有一个地方没跟着改，就是温布尔登。国际网联改色之后，温网继续用"
            "白球，一直用到 1986 年才换成黄色——整整多用了十四年，是四大满贯里"
            "最后一个松口的。这片草地上的规矩，总是最后才变。",
            "assets/explainer/yellow-ball/wimbledon.jpg",
            "Carine06 · CC BY-SA 2.0 · Wikimedia Commons · 1986 Wimbledon",
            (
                "ITF 改色后，温网继续用白球",
                "一直用到 1986 年才换成黄球",
                "四大满贯里最后一个松口的",
            ),
        ),
        (
            "color",
            "一场争论",
            "它到底是黄的，还是绿的",
            "最后留个问题给你。这颗球叫黄球，可它真的是黄的吗？有一次流传很广的"
            "投票里，说它是黄色的人不到一半，反而是略过半数的人投了绿色。"
            "同一颗球，有人看到黄，有人看到绿。那你呢，你看到的是黄还是绿？"
            "评论区说说。",
            "assets/explainer/yellow-ball/yellow_or_green.jpg",
            "Bertoka · CC0 · Wikimedia Commons · 上传者自述为 “green tennis ball”",
            (
                "官方叫它黄球，争议却没停过",
                "投票里选黄色的不到一半",
                "过半数的人选了绿色",
            ),
            "",
            "你看到的是黄，还是绿？",
        ),
    ),
    # Champions verified one edition at a time from each year's own English
    # Wikipedia article (2016-2026, 2020 cancelled). Women: S. Williams,
    # Muguruza, Kerber, Halep, Barty, Rybakina, Vondroušová, Krejčíková,
    # Świątek, Nosková — ten. Men: Murray, Federer, Djokovic x4, Alcaraz x2,
    # Sinner x2 — five.
    "ten-champions": (
        (
            "newest",
            "新科冠军",
            "21 岁，第一次进决赛就赢了",
            "先说最新的这一个。2026 年温网女单决赛，场上两个捷克人，谁赢都是捷克赢。"
            "最后是二十一岁的诺斯科娃 6-2、5-7、6-3 拿下穆霍娃，捧走她职业生涯的"
            "第一个大满贯——而这也是她第一次打进大满贯决赛。第一次进决赛就赢，"
            "本来就不常见；更不常见的是，第三轮她已经被人拿到过赛点，差一分就该收拾行李了。"
            "二十一岁二百三十六天，2011 年科维托娃之后最年轻的温网女单冠军。"
            "那天傍晚，她端着维纳斯玫瑰露水盘站上俱乐部阳台，底下站满了人。",
            "assets/explainer/ten-champions/noskova.jpg",
            "AELTC/Thomas Lovelock · wimbledon.com 官方图 · "
            "2026 温网女单决赛后，诺斯科娃在会员楼阳台上捧起维纳斯玫瑰露水盘",
            (
                "2026 温网决赛 6-2 5-7 6-3 胜穆霍娃",
                "首进大满贯决赛即夺冠，第三轮救过赛点",
                "21 岁 236 天，2011 年后最年轻",
            ),
        ),
        (
            "women",
            "十届十冠",
            "这块底座上，十年刻了十个名字",
            "但真正稀奇的不是她的年龄。维纳斯玫瑰露水盘的盘座上，"
            "历届女单冠军的名字就刻在上面。镜头拍到的这一段，从上往下依次是："
            "2016 小威、2017 穆古鲁扎、2018 科贝尔、2019 哈勒普、2021 巴蒂、"
            "2022 莱巴金娜、2023 万卓索娃、2024 克雷吉茨科娃、2025 斯瓦泰克。"
            "最下面那一行，师傅正拿着刻刀往上刻：2026，诺斯科娃。十届温网，十个名字，"
            "一个都没重复过。那今年的卫冕冠军斯瓦泰克呢？第三轮，被菲律宾人埃亚拉送回家了。",
            "assets/explainer/ten-champions/plinth.jpg",
            "AELTC/Charlie Raymond Kent · wimbledon.com 官方图 · 2026 年为奖盘盘座刻名",
            (
                "盘座刻的是历届女单冠军名字",
                "2016 到 2026，十行十个人",
                "今年卫冕冠军斯瓦泰克止步第三轮",
            ),
        ),
        (
            "men",
            "男单五冠",
            "同样这十届，五个人就写完了",
            "同样这十届，男单那边的名单短得有点尴尬：穆雷一次、费德勒一次、"
            "德约科维奇四次、阿尔卡拉斯两次、辛纳两次。十届，五个人，写完还有富余。"
            "今年是辛纳，决赛四盘拿下兹维列夫，背靠背卫冕。"
            "顺手做个对照：男单上一次有人卫冕，是四年前 2022 年的德约科维奇；"
            "女单上一次有人卫冕，得一路退回 2016 年的小威——正好是我们数的这十届的第一届。"
            "换句话说，女单的卫冕这一栏，已经空了整整十年。",
            "assets/explainer/ten-champions/sinner.jpg",
            "AELTC/Joel Marklund · wimbledon.com 官方图 · 2026 温网男单决赛后",
            (
                "德约 4 冠、阿尔卡拉斯 2 冠、辛纳 2 冠",
                "穆雷、费德勒各 1 冠",
                "女单已经十年没人卫冕成功",
            ),
        ),
        (
            "chart",
            "两张名单",
            "并排一放，差别不用解释",
            "把两张名单并排一放，就不用解释了。左边十行，十个名字；右边同样十行，"
            "却只堆成五块——其中一块自己占了四行，那是德约科维奇。"
            "还有个数字容易被忽略：捷克一个国家，包下了女单这十席里的三席，"
            "万卓索娃、克雷吉茨科娃、诺斯科娃。今年的决赛干脆是捷克内战，"
            "两个人打完，奖盘连国境都没出。",
            "",
            "示意图 · 网球时差绘制",
            (
                "女单：十行，十个不同的人",
                "男单：同样十行，只堆成五块",
                "捷克独占女单三席，今年还是内战",
            ),
            _TEN_CHAMPIONS_DIAGRAM,
        ),
        (
            "verdict",
            "两只奖杯",
            "一个人抱两年，一群人轮一遍",
            "今年这两位冠军在冠军晚宴上碰了面。辛纳手里那只是男单挑战杯，"
            "他连着抱了两年；诺斯科娃手里那只是维纳斯玫瑰露水盘，她是十年里"
            "第十个端起它的人。同一片草地，同样十届，一边像王朝更替，一边像轮流坐庄。"
            "同一组数字，你能听到两种完全相反的说法：有人说女单这叫百花齐放，谁都有机会；"
            "也有人说这叫群龙无首，没人扛旗。男单那边同理，你可以叫它统治力，"
            "也可以叫它垄断。所以问题就摆在这儿了——你更爱看哪一种？评论区聊聊。",
            "assets/explainer/ten-champions/champions.jpg",
            "AELTC/Andrew Baker · wimbledon.com 官方图 · 2026 冠军晚宴（官方合成合影）",
            (
                "辛纳连抱两年，诺斯科娃是第十人",
                "一种说法叫百花齐放，一种叫群龙无首",
                "换成男单：这叫统治力，还是垄断？",
            ),
            "",
            "你更爱看群雄逐鹿，还是王朝统治？",
        ),
    ),
    # Every clock time here is on the record: 19:40 is Djokovic's own words on
    # camera, 20:30 is how the 2025 closure was reported. The Sinner closure
    # has no published time, so it is placed by the score instead of guessed.
    # The Dimitrov beat states the sequence and then states that his coach
    # denied the link — the honest version is also the more interesting one.
    "roof": (
        (
            "rule",
            "两种情形",
            "只有下雨和天黑，才能把它关上",
            "先看清楚它长什么样。画面是从空中拍的全英俱乐部，前景那座就是中央球场，"
            "顶上白色、折叠起来堆在一侧的，就是那块可开合屋顶——这张拍的时候它是敞开的。"
            "它 2009 年装成。规则写得很短：只有两种情况可以关，下雨，或者光线不足。"
            "关上之后灯就能开，比赛可以一直打到当地议会规定的宵禁，晚上十一点。"
            "听起来一点都不含糊。问题出在第二条：光线不足，几点算不足？谁来判断？规则没说。",
            "assets/explainer/roof/aerial.jpg",
            "Arne Müseler · CC BY-SA 2.0 · Wikimedia Commons · 全英俱乐部航拍，白色折叠处即中央球场屋顶",
            (
                "2009 年装上，可开合",
                "只有下雨或光线不足才能关",
                "关上后可打到 23:00 议会宵禁",
            ),
        ),
        (
            "sinner",
            "两个人两种意见",
            "一个想关，一个想接着打",
            "2026 年温网第四轮，辛纳对上从资格赛打进来的望月慎太郎，世界第一百五十一位。"
            "打到第二盘 4 比 4，辛纳想关顶；望月正在打自己职业生涯最大的一场球，想接着打下去。"
            "两个人意见完全相反，官方站在了世界第一那边。而就在那之前一局，"
            "辛纳 4 比 3 领先发球，刚被回破。屋顶合上、灯亮起来之后，他把这一盘的抢七"
            "打成了 7 比 0，最后 6-3、7-6、6-3 过关，全场两小时二十五分。",
            "assets/explainer/roof/closing.jpg",
            "Carine06 · CC BY-SA 2.0 · Wikimedia Commons · 中央球场屋顶合拢过程（2012 年）",
            (
                "第二盘 4-4，辛纳想关，望月想打",
                "官方关顶；此前一局辛纳刚被回破",
                "复赛后抢七 7-0，全场 6-3 7-6 6-3",
            ),
        ),
        (
            "djokovic",
            "七点四十",
            "「我们是户外赛事」",
            "两天后，同一块场地，德约科维奇对阿利亚西姆的四分之一决赛。第三盘开始前，"
            "赛事主管走到场边通知他：屋顶要关了。当时是晚上七点四十。德约当场把话顶了回去——"
            "「前几天你们到八点半都不肯关，现在倒要关了？还不到八点半，现在才七点四十。"
            "我们完全可以在户外再打一整盘。我们是户外赛事。」他接着说："
            "「你们那么以自己的规则自豪，却一条都没在守。你们根本不知道规则是什么。」"
            "这场球打了五小时十五分，是温网历史上最长的四分之一决赛。他赢了。",
            "assets/explainer/roof/djokovic.jpg",
            "AELTC/Jon Super · wimbledon.com 官方图 · 2026 温网 1/4 决赛，德约胜阿利亚西姆",
            (
                "第三盘前通知关顶，时间 19:40",
                "德约：我们完全可以再打一整盘",
                "全场 5 小时 15 分，温网最长 1/4 决赛",
            ),
        ),
        (
            "clock",
            "差了五十分钟",
            "同一条规则，两个不一样的答案",
            "把两次关顶放到同一根时间轴上，就能看出德约在气什么。2025 年那次，"
            "屋顶是晚上八点半关的；2026 年这次，七点四十。两次都发生在七月第一周的伦敦，"
            "日落时间几乎一样，理由也都是同一条「光线不足」——中间差了整整五十分钟。"
            "规则本身没有错，它只是没有写死几点算天黑——于是关不关、什么时候关，最后都落到人的判断上。",
            "",
            "示意图 · 网球时差绘制",
            (
                "2025：20:30 关顶",
                "2026：19:40 关顶",
                "同一条规则，同一周，差 50 分钟",
            ),
            _ROOF_DIAGRAM,
        ),
        (
            "cost",
            "代价",
            "一年前，它改变过一场球",
            "这件事真正被人记住，是因为 2025 年。那一届第四轮，迪米特洛夫 6-3、7-5 领先辛纳两盘，"
            "第二盘打完，因为光线不足关顶，中断了大约十分钟。复赛之后，第三盘他 1 比 2 落后、"
            "自己发球，去够一个很低的反手截击，落地就捂住了胸口——胸肌撕裂，退赛。"
            "那是他连续第五届大满贯退赛。穆雷公开质疑过那次关顶；"
            "但迪米特洛夫自己的教练德尔加多对 BBC 说得很清楚：转到室内，不是他受伤的原因。"
            # 收尾停在破折号上，那一问由 _ask_it_out_loud 统一接上去。
            # 原来这里自己问完了「「关屋顶」到底是谁说了算？」，可封面问的就是
            # 「温网的屋顶，谁说了算？」——一头一尾同一个问题，末屏那一问白留。
            "所以真正的问题从来不是屋顶有没有害人，而是——",
            "assets/explainer/roof/roof2009.jpg",
            "Delfort · CC BY-SA 3.0 · Wikimedia Commons · 中央球场与其上方的屋顶结构",
            (
                "2025 年迪米特洛夫两盘领先，关顶中断 10 分钟",
                "复赛后胸肌撕裂退赛，连续第五届大满贯退赛",
                "教练德尔加多：转室内不是受伤原因",
            ),
            "",
            "打到一半关顶，对场上两个人公平吗？",
        ),
    ),
    # Everything here that is a rule or a reason comes from the WTA's own
    # "Tennis explained" page, which states the seven/nine split, says the
    # difference is the warm-up, and says outright what players are looking
    # for when they inspect balls. The second-serve habit is not in that
    # source, so it is voiced as what players do rather than as a rule.
    "ball-pick": (
        (
            "ritual",
            "一个动作",
            "递上来三个，只留两个",
            "每个发球局你都见过这一幕：球童把三四个球递过来，球员低头看两眼，扔回去一两个，"
            "手里只留两个。球童和球员，就是这笔交易的双方。快得没人解说，主播也不提，"
            "但这可能是整项运动里重复次数最多的一个选择——一场五盘大战，它会发生一两百次。"
            "问题是，那两眼到底在看什么？答案一点都不高级：看毛。",
            "assets/explainer/ball-pick/djokovic_ballboy.jpg",
            "AELTC/Charlie Raymond Kent · wimbledon.com 官方图 · 2026 温网，德约科维奇与一名球童",
            (
                "球童递三四个，球员只留两个",
                "一场五盘球会重复一两百次",
                "看的是球面那层毛",
            ),
        ),
        (
            "felt",
            "挑什么",
            "挑那颗最不毛的",
            "他们盯着看的是这个。温网 2026 年的比赛用球上，Slazenger 的字样、赛事名和年份"
            "还印得清清楚楚——球越新，字越完整，球面越光。球每被击中一次，外面那层羊毛、尼龙和棉"
            "混纺的毛毡就被抽松一点、支棱起来一点，阻力随之变大，球也就更慢。"
            "所以 WTA 官方的解释非常直接：球员发球前挑球，找的就是空气动力学上最占便宜的那一颗，"
            "换成人话，就是毛最少、最光的那颗，用来发一发。至于二发，不少人反而会留一颗毛多的，"
            "慢一点、转得住，容错更高。",
            "assets/explainer/ball-pick/slazenger.jpg",
            "AELTC/Joel Marklund · wimbledon.com 官方图 · 2026 温网男双决赛，球童手中的比赛用球",
            (
                "球上的印字越完整，球越新",
                "毛越蓬，阻力越大，球越慢",
                "一发挑最光的；二发常反过来",
            ),
        ),
        (
            "rule",
            "换球节奏",
            "先 7 局，之后每 9 局",
            "场上之所以一直有新旧之分，是因为球在被定期更换。规则写得很清楚：第一次换球在第七局之后，"
            "此后每九局换一次。你在转播里听见主裁喊一声「新球」，就是这个节点。"
            "两个数字不一样，很多人第一次听都以为是记错了——不是记错，它们本来就不一样。",
            "",
            "示意图 · 网球时差绘制",
            (
                "第一次：打满 7 局后换",
                "之后：每 9 局换一次",
                "主裁会喊「新球」提示",
            ),
            _BALL_CHANGE_DIAGRAM,
        ),
        (
            "warmup",
            "为什么是 7",
            "少掉的那两局，在热身里",
            "换球那一刻长这样：主裁从裁判椅上俯下身，把新球分给底下的球童，再由他们送上场。"
            "而少掉的那两局，早在比赛开始之前就被打完了——赛前热身用的，正是开赛这一批球。"
            "所以它们上场时已经不算全新，只够撑七局；后面每一批都是干干净净地净打九局。"
            "至于为什么非换不可，官方给的理由一点也不浪漫：再打下去，球就太蓬、太慢了。",
            "assets/explainer/ball-pick/newballs.jpg",
            "Steven Pisano · CC BY 2.0 · Wikimedia Commons · 2014 美网，主裁俯身向球童分发新球",
            (
                "换球时主裁把新球发给球童",
                "热身用的就是开赛这批球，所以只撑 7 局",
                "官方理由：再打就太蓬太慢",
            ),
        ),
        (
            "time",
            "还有第二样东西",
            "挑球的那几秒，也是他的",
            "还有一件事：网球是充压的，球内气压比外面高出将近一个大气压，从封罐那天起就在往外漏。"
            "所以严格说，这项运动里根本没有全新的球——挑球，是在一堆正在变旧的东西里挑一个最不旧的。"
            "而他在挑的那几秒里，其实还顺手拿到了另一样东西：喘一口气、把上一分忘掉、"
            "把下一分想清楚的时间。球童蹲在网边，等的是同一段时间。"
            "规则允许他挑，也就等于允许他慢下来。所以问题来了——",
            "assets/explainer/ball-pick/waiting.jpg",
            "AELTC/Florian Eisele · wimbledon.com 官方图 · 2026 温网，克雷吉茨科娃发球时等待的球童",
            (
                "内压比外界高出将近一个大气压",
                "没有全新的球，只有更新一点的球",
                "挑球的几秒，也是喘息的几秒",
            ),
            "",
            "他们挑的是球，还是那几秒钟？",
        ),
    ),
    # The numbers here are all on the record: 20 seconds at the Slams and 25
    # on tour before 2018, the 2018 US Open as the first Slam main draw with a
    # clock, warning-then-loss-of-first-serve as the penalty, and the 2026 ATP
    # switch to a timer that starts itself. Alcaraz is quoted from his own
    # post-match words at Queen's and at Miami; no photograph of either
    # argument is available, so beat four is the empty chair and the words are
    # spoken rather than staged.
    "shot-clock": (
        (
            "human",
            "从前",
            "计时的是一个人，不是一块钟",
            "先说件很多人不知道的事：发球计时这条规则，早就存在，只是以前没有钟。"
            "大满贯写的是二十秒，巡回赛写的是二十五秒——同一项运动，两套标准。"
            "而到底有没有超时，全靠裁判椅上这个人心里数。他觉得你磨蹭，就报一次超时；"
            "他觉得这一分打得太苦，就多给你几秒。松紧全在人，观众和球员都看不见那根线在哪儿。",
            "assets/explainer/shot-clock/umpire.jpg",
            "AELTC/Ben Solomon · wimbledon.com 官方图 · 2026 温网，主裁艾莉森·休斯",
            (
                "大满贯 20 秒，巡回赛 25 秒",
                "没有钟，全靠主裁心里数",
                "松紧在人，那根线没人看得见",
            ),
        ),
        (
            "debut",
            "2018 年",
            "钟被搬上了球场",
            "转折点是二〇一八年的美网。它成为第一个在正赛用上二十五秒计时器的大满贯——"
            "此前只在二〇一七年美网的资格赛里试过。同一年，四大满贯把二十秒改成二十五秒，"
            "和巡回赛并成一套。所以「二十五」这个数字并不是算出来的，"
            "它只是把两套标准里更宽的那一套留了下来。从这一天起，那根线第一次挂在了记分牌上，"
            "所有人都看得见。",
            "assets/explainer/shot-clock/usopen2018.jpg",
            "Carine06 · CC BY-SA 2.0 · Wikimedia Commons · 2018 美网 17 号球场，锦织圭对马特雷尔",
            (
                "2018 美网：首个正赛用计时器的大满贯",
                "同年大满贯由 20 秒改为 25 秒",
                "25 不是算出来的，是两套标准并轨",
            ),
        ),
        (
            "rule",
            "怎么算",
            "关键从来不是 25，是从哪一秒开始",
            "规则的原文其实很短：计时器由主裁在报分之后启动，球员必须在归零前开始发球动作。"
            "注意这个顺序——先是一分打完，然后是掌声，然后主裁报分，这时候钟才开始走。"
            "掌声越长，球员能喘的越久。至于罚则，第一次只是警告，此后每一次，"
            "都要罚掉一个一发——直接从二发开始。",
            "",
            "示意图 · 网球时差绘制",
            (
                "计时器在主裁报分之后启动",
                "掌声那几秒不算在 25 秒里",
                "首次警告，之后每次罚掉一个一发",
            ),
            _SHOT_CLOCK_DIAGRAM,
        ),
        (
            "auto",
            "2026 年",
            "钟自己开始走了",
            "然后是今年。ATP 把计时改成全自动：一分打完，钟几乎立刻开始走，"
            "不再等主裁报分，主裁那点裁量权也就没了。数字还是二十五，能用的时间却短了一截。"
            "阿尔卡拉斯在女王杯输给德拉珀之后说：「他跟我说有个新规则，钟不停，"
            "一分打完钟就开始走。」他又说：「我感觉分与分之间根本没时间恢复，全程都在赶。」"
            "在迈阿密对戈芬那场，他因为超时被罚，当场对主裁说：这一分我是在网前结束的，"
            "根本不可能赶上。辛纳同样在迈阿密找主裁理论过这件事。"
            "主裁的椅子还在原地，只是那二十五秒已经不归它管了。",
            "assets/explainer/shot-clock/chair.jpg",
            "Like tears in rain · CC BY-SA 4.0 · Wikimedia Commons · 2026 罗兰加洛斯的裁判椅",
            (
                "2026 年 ATP 改为全自动，一分结束即起算",
                "阿尔卡拉斯：钟不停，我全程都在赶",
                "数字还是 25，能用的时间短了一截",
            ),
        ),
        (
            "closer",
            "所以",
            "同样是 25 秒，两种活法",
            "把两头放在一起看就很清楚：二〇一八年，钟是被人按下的，掌声、报分、球员走回底线，"
            "这些都在二十五秒之外；二〇二六年，钟是自己走的，上面那些全被算了进去。"
            "支持的人说，比赛节奏终于稳定了，观众不用再等谁擦第三遍汗；"
            "反对的人说，一分打得越苦、越精彩，越会被罚——这等于在惩罚好球。"
            "两边都有道理，分歧其实只在一处——",
            "assets/explainer/shot-clock/serve.jpg",
            "AELTC/Edward Whitaker · wimbledon.com 官方图 · 2026 温网中央球场，萨巴伦卡发球",
            (
                "2018：人按下钟，掌声不算在内",
                "2026：钟自己走，什么都算在内",
                "越苦越精彩的一分，越容易被罚",
            ),
            "",
            "这 25 秒，该从哪一秒开始算？",
        ),
    ),
    # A match preview, so everything here has to be true at the moment it goes
    # out and nothing may guess at the result. Both players' numbers come from
    # their own Wikipedia articles rather than from the wires — the wires had
    # Eala at 20 (she turned 21 in May) and disagreed with each other about
    # where Zheng's ranking sits.
    "zheng-eala": (
        (
            "rival",
            "对手",
            "输了那场球的人，现在是菲律宾史上最高",
            "先看对面站的是谁。亚历山德拉·伊埃拉，二〇〇五年五月生，二十一岁，菲律宾人。"
            "二〇二二年她拿下美网青少年女单冠军，是菲律宾第一个青少年大满贯冠军。"
            "真正让世界记住她的是二〇二五年的迈阿密：一张外卡，连胜奥斯塔彭科、凯斯和斯瓦泰克闯进四强，"
            "成为第一个打进 WTA1000 四强的菲律宾人。而就在这个月的温网，她在中央球场第三轮"
            "再一次击败斯瓦泰克，第一次打进大满贯第二周。七月十三日，她升到生涯新高世界第二十八位，"
            "这是菲律宾球员在 WTA 历史上的最高排名。三年，伊埃拉从那个输给郑钦文的人，"
            "走到了本国的历史最高处。",
            "assets/explainer/zheng-eala/eala.jpg",
            "AELTC/Florian Eisele · wimbledon.com 官方图 · 2026 温网第三轮，伊埃拉对斯瓦泰克",
            (
                "21 岁，2022 年美网青少年女单冠军",
                "2025 迈阿密外卡闯四强，连胜三位大满贯冠军",
                "本月温网再胜斯瓦泰克，升至世界第 28",
            ),
        ),
        (
            "champion",
            "巴黎",
            "亚洲第一块网球单打奥运金牌",
            "另一边这位，不用多介绍。二〇二四年巴黎，郑钦文拿下女单金牌，"
            "成为亚洲第一位赢得奥运网球单打金牌的球员。她的生涯最高排名是世界第四，"
            "二〇二五年六月达到——继李娜之后，中国第二位进入女单前五的球员。"
            "在那之前，她还拿过二〇二四年澳网亚军和同年年终总决赛亚军。"
            "赢下金牌那一刻，她躺在红土上。"
            "拿到那块金牌的时候，郑钦文二十一岁——和今天站在球网对面的伊埃拉，同岁。",
            "assets/players/zheng-qinwen.jpg",
            "官方媒体供图 · ausopen.com · 2024 巴黎奥运会，郑钦文夺得女单金牌",
            (
                "2024 巴黎奥运女单金牌，亚洲第一人",
                "夺金那年钦文 21 岁，和今天的伊埃拉同岁",
                "生涯最高世界第 4，继李娜之后中国第二人",
            ),
        ),
        (
            "before",
            "三年前",
            "上一次见面，钦文拿走了金牌",
            "很多人不知道，这其实不是两人第一次见面。二〇二三年九月的杭州亚运会，女单半决赛，"
            "郑钦文六比一、六比七、六比三赢下伊埃拉。那场之后，伊埃拉拿了铜牌；郑钦文一路打到决赛，"
            "战胜同胞朱琳拿下金牌。那一届的赛后，郑钦文和朱琳一起举起国旗，"
            "背景上写着「第十九届亚运会 杭州」。那一年，伊埃拉十八岁。",
            "assets/explainer/zheng-eala/asiad.jpg",
            "新闻图片 · 2023 年 9 月杭州亚运会，郑钦文（右）与朱琳赛后合影",
            (
                "杭州亚运会半决赛：郑钦文 6-1 6-7(5) 6-3",
                "伊埃拉拿铜牌，郑钦文决赛胜朱琳夺金",
                "第二次交手，巡回赛上的第一次",
            ),
        ),
        (
            "now",
            "这三年",
            "一条线往上，一条线往下",
            "三年过去，两条线换了位置。伊埃拉现在是世界第二十八，生涯新高；"
            "郑钦文这三年经历的是另一条路：二〇二五年温网之后，她因为右肘长期疼痛接受了手术，"
            "缺席那年的美网，也错过了二〇二六年赛季的第一个月，包括澳网。二月她在多哈复出，赢了两场；"
            "但今年的法网和温网，她都止步首轮，排名从世界第四一路掉到一百开外，"
            "这一站要靠外卡才能进正赛。不过线的最后那一小段是往上走的——"
            "两周前的雅典，钦文连赢两场打进八强，那是她十三个月来的第一个巡回赛八强。",
            "",
            "网球时差绘制",
            (
                "2025 温网后右肘手术，缺席美网和澳网",
                "排名从世界第 4 掉到一百开外，本站靠外卡",
                "两周前雅典连赢两场，13 个月来第一个八强",
            ),
            _ZHENG_EALA_DIAGRAM,
        ),
        (
            "stake",
            "这一场",
            "钦文还在打，故事就没完",

            "所以这场首轮，对两个人的意思完全不一样。对伊埃拉，这是北美硬地赛季的第一场，"
            "往前看是美网，她要做的是把生涯新高的位置坐稳。对郑钦文，这是回来路上的一站——"
            "雅典之后的排名已经赶不上美网正赛的入围线，下个月很可能要从资格赛打起。"
            "伊埃拉二十一岁，正在往上爬；郑钦文在二十一岁那年，就已经站到过最高的地方。"
            "只把一句话留在这儿——祝钦文好运，也期待她早日重回巅峰。",
            "assets/explainer/zheng-eala/zheng_clay.jpg",
            "账号所有者提供 · 摄影师与出处未标注（unknown / unverified）· 郑钦文",
            (
                "7 月 27 日首轮，两人第二次交手",
                "对伊埃拉是新高的起点，对郑钦文是回来的路",
                "祝钦文好运，期待早日重回巅峰",
            ),
            "",
            "你第一次记住郑钦文，是哪一场？",
        ),
    ),
    "shang-nishikori": (
        (
            "peak",
            "最高处",
            "亚洲男子唯一的一次大满贯决赛",
            "先说对面站的是谁。锦织圭，一九八九年十二月生，日本人。二〇一四年美网，"
            "他半决赛击败当时的世界第一德约科维奇，闯进决赛——那是公开赛年代至今，"
            "代表亚洲国家的男子球员唯一一次打进大满贯单打决赛。他最终负于西里奇，"
            "但那一年他升到了生涯最高的世界第四，这也是亚洲男子球员在 ATP 排名上的最高位置。"
            "生涯十二个单打冠军。",
            "assets/explainer/shang-nishikori/nishi_2014.jpg",
            "Tennis.jp 现场报道 · 2014 年美网男单决赛第二盘，亚瑟·阿什球场",
            (
                "2014 美网决赛，亚洲男子至今唯一一次",
                "半决赛击败当时的世界第一德约科维奇",
                "生涯最高世界第 4，12 个 ATP 冠军",
            ),
        ),
        (
            "farewell",
            "告别",
            "锦织圭说，今年打完就退役",
            # 「排名四百开外」原来就写在这儿，站得住但太软。换成那两个数字本身：
            # 十一年前世界第四，现在世界第四百六十四——**对比是事实自己给的**，
            # 不用加一个形容词。挑战赛那一句同理：前世界第四的最后一年在挑战赛
            # 打球，比「多处伤」更让人愣一下，而且可核。
            "二〇二六年四月三十日，锦织圭宣布这是他的最后一个赛季。三十六岁，"
            "世界第四百六十四——十一年前，他排到过世界第四。今年他多数时间在挑战赛打球，"
            "宣布退役前两周，刚在萨凡纳的挑战赛第二轮出局。这一站要靠一张外卡才能进正赛。"
            "他自己说：我其实还想继续打。",
            # 这一屏是「告别」，所以用的是他抬手向观众致意的那一刻——这个动作
            # 本身就在说再见。按「大头特写不等于有冲击力」那条，这张是个例外：
            # 它不靠动作幅度，靠的是手势的意思。2025 年 4 月休斯敦赢下首轮之后。
            "assets/explainer/shang-nishikori/nishi_now.jpg",
            "全美红土锦标赛官方图 via Tennis.jp · 2025 年 4 月休斯敦，锦织圭赛后向观众致意",
            (
                "2026 年 4 月宣布，这是最后一季",
                "曾经的世界第 4，现在世界第 464",
                "今年多在挑战赛，本站靠外卡",
            ),
        ),
        (
            "before",
            "上一次",
            "19 岁那年，商竣程赢了他",
            "两人不是第一次碰面。二〇二四年九月，成都公开赛首轮，"
            "当时十九岁的商竣程六比四、六比四击败锦织圭——两盘，都是六比四，"
            "第二盘他在发球胜赛局里化解了两个破发点。那是他第一次遇上这位前世界第四。",
            "assets/explainer/shang-nishikori/shang_beats_nishi.jpg",
            "CGTN · 2024 年 9 月成都公开赛，商竣程",
            (
                "2024.9 成都首轮 6-4 6-4 胜锦织圭",
                "发球胜赛局连救两个破发点",
                "两人此前唯一一次交手",
            ),
        ),
        (
            "title",
            "那一周",
            "商竣程把那座冠军也拿走了",
            "而那一周还没完。赢下锦织圭之后，商竣程一路打到决赛，"
            "七比六、六比一战胜头号种子穆塞蒂，拿到生涯第一个 ATP 单打冠军。"
            "那是公开赛年代第二位赢得 ATP 单打冠军的中国男子球员——第一位是二〇二三年达拉斯的吴易昺。"
            "他也是当年最年轻的冠军，第一个二〇〇五年出生的 ATP 冠军。",
            # 这一屏讲的就是「冠军也拿走了」，那就直接给奖杯——原来那张是场边
            # 大屏打出他的名字，得看清屏上的字才明白，绕了一层。
            "assets/explainer/shang-nishikori/shang_trophy.jpg",
            "CGTN / CFP · 2024 年 9 月 24 日成都公开赛决赛后，商竣程捧起冠军奖杯",
            (
                "决赛 7-6(4) 6-1 胜头号种子穆塞蒂",
                "公开赛年代第二位 ATP 夺冠的中国男子",
                "继吴易昺 2023 年达拉斯之后",
            ),
        ),
        (
            "gap",
            "缺席",
            "商竣程刚从五个月的空白里出来",
            # 澳网那一场是这一年最亮的一笔，原来一个字没提，只讲他掉下去——不准确，
            # 也少了对比。先摆他打得最好的一场，再讲空白，落差才是事实自己给的。
            "但商竣程这一年并不好过。一月的澳网首轮，他四盘打掉了前世界第九的"
            "巴蒂斯塔·阿古特，最后一盘六比零，那是他今年最亮的一场。"
            "可二月的迪拜站，他一比六、三比六输给梅德韦杰夫，"
            "那之后就没再出现在巡回赛的赛场上——到今天为止，整整五个月。"
            "他生涯最高排名停在二〇二四年十月的世界第四十七，现在掉到了两百多位。"
            "换句话说，这一场对两个人都是回来：一个是最后一次回来，一个是空白之后第一次回来。",
            # 这一屏讲「五个月没出现」，配的就该是他**最后一次出现**的那一场。
            # 原来用的是 2025 年 10 月上海站的一张——对得上人，对不上这一屏的事，
            # 而且是全套里最没劲的一张（背光、动作不明确）。迪拜官方图库这张
            # 自己点明赛事（背景是赛事广告板），球和拍都在画面里。
            "assets/explainer/shang-nishikori/shang_dubai_2026.jpg",
            "迪拜站官方图库 · 2026 年 2 月迪拜首轮，商竣程——他至今最后一场比赛",
            (
                "澳网首轮 4 盘胜前世界第 9 阿古特",
                "2 月迪拜之后停赛，本站是五个月来首战",
                "生涯最高第 47，现排名两百开外",
            ),
        ),
        (
            "stake",
            "这一场",
            "一场首轮，装着一代人的交接",
            "所以七月二十七日的这场首轮，装的东西比一场首轮多得多。"
            "球网一边是亚洲男子网球至今飞得最高的那个人，正在打他的最后一个赛季；"
            "另一边是二十一岁的商竣程，两年前赢过他，现在刚从五个月的空白里走出来。"
            "同一天的同一站，郑钦文和维纳斯也都拿着外卡打首轮——这一轮的华盛顿，"
            "站着好几个正在告别和正在回来的人。",
            # 原来是成都夺冠后双臂举起那张——情绪够，但不是在打球，而且和第 ③④ 屏
            # 同出一周。收尾这一屏没有时间约束，按规矩该拿最近一场里最有冲击力的
            # 击球画面：2026 澳网首轮，CGTN 的图注写明「hits a shot ... against
            # Roberto Bautista-Agut ... January 19, 2026」。
            "assets/explainer/shang-nishikori/shang_ao2026.jpg",
            "CGTN / VCG · 2026 年 1 月 19 日澳网首轮，商竣程",
            (
                "7 月 27 日首轮，两人第二次交手",
                "一个在告别，一个刚回来",
            ),
            "",
            # 封面已经问过「锦织圭的最后一年，谁来接？」。末屏再问一遍同一句，
            # 等于把换评论区的唯一抓手浪费掉——收尾这一问要开一扇新门，
            # 而且要接得回第 ① 屏那个唯一：亚洲男子只打进过一次大满贯决赛。
            "亚洲男子的下一次大满贯决赛，还要等多久？",
        ),
    ),
    "venus-potapova": (
        (
            "record",
            "去年",
            "45 岁那天，维纳斯赢了一场",
            "先说去年的这一站。二〇二五年七月二十二日，华盛顿站首轮，四十五岁的"
            "维纳斯·威廉姆斯六比三、六比四击败佩顿·斯特恩斯——对手比她小二十二岁。"
            "那是她阔别单打十六个月之后的第一场比赛，发出九记 Ace；也是她自二〇二三年八月"
            "辛辛那提以来的第一场胜利。上一个比她更年长还能赢下 WTA 巡回赛单打的人，"
            "是二〇〇四年温网首轮的纳芙拉蒂洛娃，那年四十七岁。",
            "assets/explainer/venus-potapova/win_matchpoint.jpg",
            "Tennis Channel 转播画面 / ABC News · 2025 年 7 月 22 日华盛顿站首轮，第 6 个赛点",
            (
                "7.22 华盛顿首轮，6-3 6-4 胜斯特恩斯",
                "阔别单打 16 个月，那场发了 9 记 Ace",
                "2004 年纳芙拉蒂洛娃之后最年长的胜者",
            ),
        ),
        (
            "answer",
            "答案",
            # 冒号不能进大标题：小红书文案排成「小标：大标」，标题里再带一个冒号，
            # 就成了「答案：维纳斯说：我回来是为了上保险」，一行两个冒号。
            "维纳斯说，我回来是为了上保险",
            "赢下那场之后，场边采访问她为什么回来。她的第一个回答是个玩笑："
            "我得回来上保险啊，我天天跑医院，我需要这个保险。这不完全是玩笑——"
            "她说自己之前一直挂在 COBRA 上，那是失业或离职之后自费续保的路子。"
            "二〇一一年她被确诊干燥综合征，一种会带来长期疲劳和疼痛的自身免疫病，"
            "那年她退出了美网；十五年过去，她还在打。二〇二五年复出之前，"
            "她又做了一次子宫肌瘤手术，那个病拖了很多年——她说：肌瘤影响了我的职业生涯，"
            "很多时候我根本没有足够的体力去打一场真正想打的比赛。"
            "但那天她还说了第二句：说到底就是爱吧，你要是足够爱它，你就会去付出。我太爱它了。",
            "assets/explainer/venus-potapova/venus_head_down.jpg",
            "图片社图 via The National Herald · 2026 年 1 月澳网首轮",
            (
                "「我得回来上保险，我天天跑医院」",
                "2011 年确诊干燥综合征，至今 15 年",
                "「说到底就是爱，够爱就会去付出」",
            ),
        ),
        (
            "equalpay",
            "底子",
            "第一张等额冠军支票，是维纳斯的",
            "还有一件比奖杯更重的事。二〇〇五年温网决赛前一夜，维纳斯去大满贯委员会陈情，"
            "第二天她拿了冠军。二〇〇六年，她在英国《泰晤士报》写了一篇文章，"
            "标题的意思是：我只是个二等冠军。二〇〇七年二月二十二日，温网宣布男女奖金同酬——"
            "四大满贯里它是最后一个，美网一九七三年就同酬了，澳网二〇〇一年，法网二〇〇六年。"
            "那一年夺冠的正是她：七十万英镑，第二天费德勒拿到的也是七十万英镑。"
            "她是网球史上第一个拿到与男子冠军等额支票的女子冠军。"
            "她的履历还有七座大满贯女单冠军、四枚奥运金牌、四十九个巡回赛单打冠军，"
            "以及二〇〇二年二月的世界第一。",
            "assets/explainer/venus-potapova/venus_wimbledon.jpg",
            "Getty Images via andscape · 温网夺冠后手捧维纳斯玫瑰露水盘（来源未标注年份）",
            (
                "2006 年撰文：「我只是二等冠军」",
                # 原来这条是「2007 年温网同酬，她拿到第一张等额支票」，和大标题重复。
                # 换成那张支票的数字：具体、可核，比重复一遍更有劲。
                "70 万英镑，和第二天的费德勒一样",
                "7 座大满贯、4 枚奥运金牌",
            ),
        ),
        (
            "streak",
            "连败",
            "上一场胜利，就在这一站",
            "但那场胜利之后的事情，是另一条线。第二天，还是华盛顿，第二轮，"
            "维纳斯二比六、二比六输给弗雷赫——这轮连败就是从那儿开始的。"
            "接下来是辛辛那提、美网、澳网、奥斯汀、迈阿密，一直到六月的洪堡，全部止步首轮。"
            "其中咬得最紧的一场是今年一月的奥克兰：她拿下了第二盘，二十八局里赢到十二局，"
            "最后还是三盘负于利内特。到六月为止，单打十一连败。"
            "同一块场地给过她一项纪录，也给了她这轮连败的第一场。",
            "",
            "网球时差绘制",
            (
                "11 连败，起点是去年本站的第二轮",
                "2026 年至今尚无巡回赛单打胜绩",
                "世界第 469，本站靠外卡进正赛",
            ),
            _VENUS_STREAK_DIAGRAM,
        ),
        (
            "rival",
            "对面",
            "本来进不了正赛的人，打进了四强",
            "对面这位叫阿纳斯塔西娅·波塔波娃，二〇〇一年三月生，二十五岁，"
            "从二〇二六赛季起代表奥地利出战。她今年做成过一件此前没人做成的事："
            "四月的马德里站，她在资格赛末轮输了球，本来该收拾东西回家，正赛开始前半小时"
            "接到电话递补进签表；然后她一路赢下去，先后战胜世界第二莱巴金娜和普利斯科娃，"
            "打进四强——这是一九九〇年分级制度确立以来，第一个打进 WTA 一千级四强的幸运落败者。"
            "她的生涯最高排名是世界第二十一。",
            "assets/explainer/venus-potapova/potapova_madrid.jpg",
            "葡语媒体转载 · 2026 年 4 月马德里站，波塔波娃庆祝",
            (
                "25 岁，2026 赛季起代表奥地利出战",
                "马德里幸运落败者闯四强，1990 年来首例",
                "四强路上淘汰世界第二莱巴金娜",
            ),
        ),
        (
            "stake",
            "这一场",
            "网球不欠维纳斯什么，她还是来了",
            "所以七月二十七日这一场，是两个人的第一次交手。一个二十五岁，正在把那一通电话"
            "变成实力；一个四十六岁，七座大满贯、四块奥运金牌，还有温网那份和男子等额的奖金——"
            "那是她自己推成的。她早就不需要再证明什么了，却仍然要从一张外卡开始打首轮。"
            "同一天的同一站，郑钦文也拿着外卡打首轮。这一轮的球场上，"
            "站着好几个本来不该在这儿的人。",
            "assets/explainer/venus-potapova/venus_serve_2026.jpg",
            "AFP · 2026 年 3 月 6 日印第安维尔斯，维纳斯发球",
            (
                "7 月 27 日首轮，两人第一次交手",
                "46 岁的外卡，对 25 岁的上升期",
            ),
            "",
            "如果是你，46 岁还会站上场吗？",
        ),
    ),
    # 外卡这条的六屏是按「规则 → 今年的两极 → 历史的两个顶点」排的。规则
    # 那一层全部来自 2026 年大满贯规则书正文（tools/read_grand_slam_rulebook.py
    # 可复查），不用媒体转述——「三家大满贯互换外卡」那条流传很广的说法
    # 全文搜 reciprocal / exchange / swap 都搜不到，所以一个字都没写进来。
    #
    # ⚠️ 「签表上写着 WC」这句话不通用：温网 2026 官方签表 PDF 里
    # 「WC」出现 0 次，用的是 (W)/(Q)/(L)。所以第 ① 屏的画面是澳网，
    # 旁白也把两种写法都点出来，别笼统说「签表上都写 WC」。
    # 蒂姆这条**一张示意图都没有**，六屏全是实拍。账号所有者的原话：
    # 「不一定要有示意图，示意图是真实图片解释不了的时候再用示意图」。
    # 我第一版给「同一天」那个巧合画了张对照图，理由站不住——我伸手去画的
    # 真实原因是**找不到他踢球的照片**，那正是文档里标 ❌ 的那一档
    # （「找不到合适的照片」≠「照片本身讲不清」）。
    #
    # 后来照片找到了（见 assets/.../credits.json 的 kicking.jpg），于是
    # 「同一天」并进夺冠那一屏：两个日期写在同一张卡上，自己就成立，
    # 不需要画。顺带避开了「①屏埋钩子、③屏才兑现」那种悬空写法。
    # 五屏全是实拍，一张示意图都没有——「能不画的就不要自己画图」。这条片子里
    # 没有任何一件事是照片讲不清的：排名、赛点、比分都由屏幕上的要点承担。
    #
    # ⚠️ 黄泽林在本站（2026 洛斯卡沃斯）的实拍**不存在于任何可及来源**，探过哪些
    # 源、各返回什么，记在 credits.json 的 _gate2_note 里。所以他的四张图分别来自
    # 全运会、美网、亚运会和辛辛那提，**每一张都配在讲那件事的那一屏上**，
    # 没有一张是拿来顶替另一场比赛的。
    "wong-lehecka": (
        (
            "rival",
            "头号种子",
            "莱赫奇卡今年打进了大师赛决赛",
            "对面这位叫莱赫奇卡，捷克人，二〇〇一年十一月生，二十四岁，"
            "是目前捷克排名最高的男子球员。今年三月的迈阿密大师赛，他以二十一号种子"
            "一路打到决赛——那是他生涯第一个大师赛决赛，而通往决赛的那几场球，"
            "他的发球局一次都没有被破掉；决赛四比六、四比六不敌辛纳。"
            "五月二十五日，他升到生涯最高的世界第十二。这一站他是一号种子，"
            "首轮轮空，所以这是他在洛斯卡沃斯打的第一场球。",
            "assets/explainer/wong-lehecka/lehecka_miami.jpg",
            "Miami Open 官方图库 · 2026 年 3 月迈阿密大师赛，莱赫奇卡救球",
            (
                "24 岁，捷克排名最高的男子球员",
                "2026 迈阿密首进大师赛决赛，负于辛纳",
                "5 月 25 日升到生涯最高世界第 12",
            ),
        ),
        (
            "record",
            "大满贯",
            "去年黄泽林赢了世界第 14",
            "再看这一边。二〇二五年三月的迈阿密大师赛，黄泽林在六十四强击败了"
            "当时世界第十四的谢尔顿。那年八月的美网，他以世界第一百七十三的排名"
            "从资格赛第一轮打起，连过三关进入正赛，成为公开赛年代第一个"
            "打进大满贯正赛的香港男子。正赛首轮，他直落三盘赢下世界第七十一的"
            "科瓦切维奇，那是香港男子的第一场大满贯正赛胜利；第二轮又用四盘"
            "赢了沃尔顿，全场发出二十一记 Ace，成为第一个打进大满贯第三轮的"
            "香港男子。第三轮他碰上世界第十五的卢布列夫，五盘落败。",
            "assets/explainer/wong-lehecka/wong_usopen.jpg",
            "SCMP · 2025 年 8 月 29 日美网第二轮，黄泽林四盘胜沃尔顿",
            (
                "2025 迈阿密 64 强胜世界第 14 谢尔顿",
                "2025 美网从资格赛打进第三轮，香港首人",
                "第三轮五盘负于世界第 15 卢布列夫",
            ),
        ),
        (
            "asiad",
            "杭州",
            "亚运会那场，黄泽林救了 5 个赛点",
            "这些第一次，要从三年前那一场算起。二〇二三年九月，杭州亚运会男单十六强，"
            "十九岁的黄泽林对上当时世界第九十八的吴易昺——排名比他高三百六十位。"
            "决胜盘抢七里他一度一比六落后，连救五个赛点，最后六比四、三比六、七比六"
            "拿下这场两小时四十八分钟的球。那是香港球员第一次战胜世界前一百。",
            "assets/explainer/wong-lehecka/wong_asiad.jpg",
            "SCMP · 2023 年 9 月杭州亚运会男单，黄泽林反手击球",
            (
                "2023 年 9 月杭州亚运会 16 强",
                "抢七 1-6 落后连救 5 个赛点，打了 2 小时 48 分",
                "香港球员第一次赢下世界前 100",
            ),
        ),
        (
            "rematch",
            "珠海",
            "两年后，吴易昺赢了回去",
            "两年之后，两个人在珠海又碰上了。二〇二五年十一月的全运会，横琴的"
            "男单半决赛，这一次吴易昺六比七、七比六、六比四赢了回去，"
            "黄泽林拿到一枚铜牌。赛后黄泽林说：我挺为自己骄傲的，"
            "因为哪怕打到最后一分我也没有放弃，那才是最重要的。",
            "assets/explainer/wong-lehecka/wong_national_games.jpg",
            "Eugene Lee · SCMP · 2025 年 11 月全运会男单半决赛，黄泽林对吴易昺",
            (
                "2025 年 11 月全运会半决赛，珠海横琴",
                "吴易昺 6-7 7-6 6-4，黄泽林拿铜牌",
                "「哪怕打到最后一分，我也没有放弃」",
            ),
        ),
        (
            "stake",
            "九点开球",
            "黄泽林大部分比赛在外场",
            "这些年他大部分球是在外场打的，看台上几十个人；六次挑战赛决赛，"
            "才在今年的九江拿到第一个冠军，那也是香港球手的第一个挑战赛冠军。"
            "北京时间七月三十日上午九点，洛斯卡沃斯的中心球场，第一场，"
            "他站到世界第十二的对面。",
            "assets/explainer/wong-lehecka/wong_cincinnati.jpg",
            "Navin75 · CC BY-SA 4.0 · Wikimedia Commons · 2025 年 8 月辛辛那提站 4 号场",
            (
                "7 月 30 日 09:00，洛斯卡沃斯 16 强",
                "首轮 6-3 6-4 胜世界第 266 的布兰奇",
                "6 次挑战赛决赛，才拿到第一个冠军",
            ),
            "",
            "还会有一次救 5 个赛点吗？",
        ),
    ),
    "thiem-football": (
        (
            "now",
            "答案",
            "第八级联赛，替补 12 分钟破门",
            "答案是奥地利联赛金字塔最底下那一层，第八级。今年七月十五日，他在"
            "奥地利足协重新登记成了球员，转会到一家一八九九年成立的老俱乐部——"
            "那是下奥地利州最古老的球队，一九三五年拿过全国业余冠军。俱乐部的"
            "足球部负责人只说了一句：在我们这儿，谁都得自己去争首发。"
            "而在那之前，二〇二五年九月十三日，他为家乡队替补上场，十二分钟后"
            "打进一球，把比分改成三比二——踢球以来第八场正式比赛的第一粒进球。"
            "那一天，正好是他在纽约拿下美网的五周年。",
            "assets/explainer/thiem-football/kicking.jpg",
            "GEPA pictures 经 laola1 转载 · 蒂姆在业余球场上（来源未标注时间与地点，unverified）",
            (
                "2026.7.15 在足协登记，打第 8 级",
                "2025.9.13 替补 12 分钟破门",
                "同月同日，正是美网夺冠 5 周年",
            ),
        ),
        (
            "decline",
            "断点",
            "手腕伤之后，正手回不来了",
            "中间发生的事是手腕。那处伤拖了很久，回来之后他的正手不再是原来那个正手——"
            "而正手是他整套打法的支点。他后来说，他早就知道自己的生涯要结束了。",
            "assets/explainer/thiem-football/monte_carlo_2023.jpg",
            "si.robi · CC BY-SA 2.0 · Wikimedia Commons · 2023 年 4 月 10 日蒙特卡洛大师赛",
            (
                "手腕伤拖了很久，正手回不来了",
                "图为 2023 年 4 月蒙特卡洛大师赛",
                "「我早就知道生涯要结束了」",
            ),
        ),
        (
            "farewell",
            "最后一场",
            "主场首轮出局，全场没人走",
            "二〇二四年十月二十二日，维也纳，他的主场。首轮六比七、二比六负于达尔代里，"
            "九十一分钟。球打完了，全场没人走。那年他三十一岁，十七个巡回赛冠军，"
            "一座大满贯。",
            "assets/explainer/thiem-football/vienna_farewell.jpg",
            "erstebank-open.com 官方图 · 2024 年 10 月 22 日维也纳，蒂姆打完最后一场后向全场挥手",
            (
                "2024.10.22 维也纳首轮，91 分钟",
                "6-7(6) 2-6 负于达尔代里",
                "31 岁退役，17 个巡回赛冠军",
            ),
        ),
        (
            "crossover",
            "另一条路",
            "她换了个赛场，当上世界第一",
            "网球运动员离开之后能走到哪儿，历史上给过很不一样的答案。玛尔塔·马雷罗，"
            "西班牙人，WTA 单打最高世界第四十七，法网八强。二〇一三年她改打板式网球，"
            "一种在玻璃墙里打的拍类项目。三年之后，她做到了那个项目的世界第一——"
            "在第二个赛场上，比在第一个赛场上高得多。",
            "assets/explainer/thiem-football/marrero_padel.jpg",
            "Harpagornis · CC BY-SA 4.0 · Wikimedia Commons · 2019 年 5 月世界板式网球巡回赛维戈站，马雷罗",
            (
                "马雷罗：WTA 单打最高第 47",
                "2013 年改打板式网球",
                "2016 年做到该项目世界第 1",
            ),
        ),
        (
            "mirror",
            "反过来",
            "金球奖得主，45 岁去打网球",
            "也有人是反着走的。迭戈·弗兰，二〇一〇年世界杯金球奖得主。二〇一八年"
            "他从足球退役，二〇二四年十一月十三日，四十五岁的他在蒙得维的亚的挑战赛"
            "打了职业网球首秀，双打，主场坐满。一比六、二比六，输了。"
            "一个足球金球奖跑去打网球，一个网球大满贯冠军跑去踢第八级联赛。",
            "assets/explainer/thiem-football/forlan_tennis.jpg",
            "图片社图经 Forbes 转载 · 2024 年 11 月蒙得维的亚挑战赛，弗兰的职业网球首秀",
            (
                "弗兰：2010 世界杯金球奖得主",
                "2024.11.13，45 岁打网球首秀",
                "1-6 2-6，主场满座",
            ),
            "",
            "网球练出来的本事，换个赛场还剩多少？",
        ),
    ),
    "wildcard": (
        (
            "sheet",
            "签表上",
            "两个字母，一张直通正赛的票",
            "先看一眼签表。这是澳网女单签表的第二个四分之一区，一百二十八个签位，"
            "每个名字后面都写着这个人是怎么进来的：括号里的数字是种子，"
            "写着 Qualifier 的是从资格赛打上来的，而第四十六号签位那一行，"
            "名字后面跟着两个字母——WC。WC 是 wild card，中文叫外卡，"
            "主办方直接发给你的一张正赛资格：不看排名，也不用打资格赛。"
            "写法各家不一样：澳网写 WC，温网签表上写的是括号里一个 W。",
            "assets/explainer/wildcard/ao_draw_wc.jpg",
            "Jay Town/Tennis Australia · ausopen.com 官方图 · 2024 澳网女单签表第二个四分之一区，"
            "第 46 号签位写着 Olivia Gadecki – WC",
            (
                "外卡＝主办方直接发的正赛资格",
                "不看排名，也不用打资格赛",
                "图为 2024 澳网女单签表",
            ),
        ),
        (
            "rule",
            "规则原文",
            "想发几张，就能发几张",
            "那主办方最多能发多少张？大满贯规则书里有整整一节讲外卡，"
            "开头第一句就是：一名球员能够获得的外卡数量，不设任何限制。"
            "签表的构成也写死了：一百二十八个签位，可以是一百零四个直接进入"
            "加十六个资格赛出线，也可以是一百零八加十二，还可以是一百一十二加八——"
            "前面两栏一直在变，只有外卡那一栏，三种分法都是八。"
            "资格赛签表还要另外再发八到九张。这么一算，"
            "一届大满贯发出去的外卡，其实是三十张出头，不是八张。",
            "",
            "示意图 · 网球时差绘制",
            (
                "规则原文：外卡张数不设上限",
                "正赛 8 张，三种分法都不变",
                "算上资格赛，一届发出三十多张",
            ),
            _DRAW_SPLIT_DIAGRAM,
        ),
        (
            "fery",
            "今年七月",
            "世界第 114，一路打进温网四强",
            "这张票能值多少？今年七月的温网刚给过答案。英国人费里，"
            "赛前排在世界第一百一十四位，按排名连正赛都进不去，"
            "手里拿的是温网发的一张外卡。四分之一决赛他在中央球场"
            "六比四、七比六、六比零横扫科博利，直接打进四强。"
            "他是二十五年来第一个闯进温网四强的外卡，"
            "也是公开赛年代第一个打进大满贯四强的英国外卡。"
            "至于二十五年前的那一个是谁，等一下就说到。",
            "assets/explainer/wildcard/fery_2026_sf.jpg",
            "AELTC · wimbledon.com 官方图 · 2026 温网男单 1/4 决赛，费里战胜科博利后跪坐在草地上",
            (
                "费里，赛前世界第 114",
                "1/4 决赛横扫科博利，闯进四强",
                "25 年来第一个进温网四强的外卡",
            ),
        ),
        (
            "zheng",
            "另一面",
            "没拿到的那一张，同样决定去留",
            "但外卡还有另一面，就是拿不到的时候。郑钦文因伤缺阵大半年，"
            "排名掉到一百二十开外。七月中旬的雅典站，她连过两轮，"
            "拿下十三个月以来的第一个八强。可再往后就是美网："
            "今年女单正赛的直通线画在世界第一百零二位，公布名单时她排在"
            "第一百二十一位，正赛外卡没有发给她。她七月拿到的那一张，"
            "是九号公布的华盛顿站外卡。同一个七月，一个人靠外卡"
            "打进了大满贯四强，另一个人在等一张始终没等到的外卡。",
            "assets/explainer/wildcard/zheng_athens_2026.jpg",
            "athens-open.com 官方图库 Day 5 · 2026 年 7 月 15 日雅典站第二轮，郑钦文正手击球",
            (
                "雅典站打进 13 个月来首个八强",
                "美网直通线 102，她当时 121",
                "7 月 9 日拿到华盛顿站外卡",
            ),
        ),
        (
            "goran",
            "最高处",
            "世界第 125，靠一张外卡拿了温网",
            "二十五年前的那一个，就是他。二〇〇一年温网，伊万尼塞维奇，"
            "世界第一百二十五位，按排名本该去打资格赛；温网看着他此前三次"
            "打进这里的决赛又三次输掉，给了他一张外卡。他就这么一路打到了最后，"
            "决赛五盘险胜拉夫特，第九局才拿下那盘，捧起了金杯。"
            "到今天为止，他仍然是公开赛年代唯一一个以外卡身份"
            "拿下大满贯男单冠军的人。",
            "assets/explainer/wildcard/ivanisevic_2001.jpg",
            "AELTC · wimbledon.com 官方图 · 2001 年温网男单决赛后，伊万尼塞维奇在中央球场捧起奖杯",
            (
                "2001 温网，世界第 125，外卡",
                "决赛五盘险胜拉夫特",
                "公开赛年代唯一的外卡大满贯冠军",
            ),
        ),
        (
            "kim",
            "更极端的一次",
            "连排名都没有的人，拿了美网",
            "女子这边还有更极端的一次。二〇〇九年美网，克里斯特尔斯"
            "当时连世界排名都没有——她已经退役两年，生完孩子刚刚复出，"
            "这只是她复出后打的第三站比赛，进正赛靠的同样是一张外卡。"
            "结果她八强淘汰李娜，四强淘汰小威廉姆斯，"
            "决赛七比五、六比三击败沃兹尼亚奇，把冠军拿走了。"
            "她是第一个以外卡拿下美网的人，也是一九八〇年古拉贡之后，"
            "第一个当了妈妈还能拿下大满贯的人。",
            "assets/explainer/wildcard/clijsters_2009_final.jpg",
            "Timothy A. Clary/AFP · Sony Ericsson WTA Tour 官方账号转发 · "
            "2009 年 9 月 13 日美网女单决赛后，克里斯特尔斯与女儿 Jada 和冠军奖杯",
            (
                "2009 美网，当时连排名都没有",
                "八强淘汰李娜，四强淘汰小威廉姆斯",
                "史上第一个以外卡夺得美网的人",
            ),
            "",
            "外卡想发几张就发几张，你觉得合理吗？",
        ),
    ),
}


# The caption's opening hook and its hashtags belong to the topic, not to the
# function. They used to be literals inside the caption builder, written for
# Hawk-Eye — so the moment a second deck existed, the yellow-ball post opened
# with a line about line calls and tagged itself #鹰眼 #电子司线 #法网.
# 小红书的标签**要放满五个**，账号所有者定的。这组是兜底，正常每条片子都该在
# `_CAPTIONS` 里写自己的五个——但兜底本身也必须是五个，否则漏写条目的那条会
# 无声地少两个标签。thiem-football 就是这么发出去只带三个的：它在 _CAPTIONS
# 里没有条目，而当时的默认组只有三个，其余 15 条各自写满了，光看别的条看不出
# 这个洞。判据落在 test_每条片子的标签都放满五个。
_DEFAULT_TAGS = ("网球", "网球时差", "网球冷知识", "网球科普", "网球运动")
_CAPTIONS: dict[str, dict] = {
    "nadal-academy": {
        "hook": (
            "纳达尔学院宣布「史上第一次六人同时进前 100」，八周之后这个数字就不对了——\n"
            "第七个是黄泽林。而七个人到那儿时，从 13 岁到 21 岁都有。"
        ),
        "tags": ("网球", "网球时差", "黄泽林", "纳达尔学院", "伊埃拉"),
    },
    "special-exempt": {
        "hook": (
            "华盛顿两场决赛被雨推到周一，而加拿大站的资格赛两天前就打完了。\n"
            "规则给这件事留了一个位置叫特殊豁免——大师赛和 500 赛，整站只有一个。"
        ),
        "tags": ("网球", "网球时差", "布云朝克特", "特殊豁免", "网球冷知识"),
    },
    "pr-allowance": {
        "hook": (
            "保护排名不是年卡：停 6–12 个月给 9 站或 9 个月，两个上限同时倒计时。\n"
            "而且进了签表就扣一站，不看输赢——商竣程为了够到它，放弃了 2025 年的温网。"
        ),
        "tags": ("网球", "网球时差", "商竣程", "保护排名", "网球冷知识"),
    },
    "challenger-climb": {
        "hook": (
            "同一周，ATP250 的 8 号种子比挑战赛的 1 号种子还高 36 位——低级别的对手没有更强。\n"
            "难的是兑换率：挑战赛冠军赢 5 场 125 分，ATP250 赢 2 场就有 100 分。"
        ),
        "tags": ("网球", "网球时差", "张之臻", "挑战赛", "网球冷知识"),
    },
    "entry-deadline": {
        "hook": (
            "2026 美网的正赛名单，7 月 20 日就锁上了——正赛周周一往前推六周。\n"
            "男子直入线第 101，女子第 102；之后涨的用不上，跌的也不还。"
        ),
        "tags": ("网球", "网球时差", "商竣程", "郑钦文", "网球冷知识"),
    },
    "mandatory-1000": {
        "hook": (
            "辛纳今年把打过的五个大师赛全赢了，第六个没去——大师赛是强制的。\n"
            "ATP 规则书写着：处罚自动生效、不可申诉。可算下来，那一笔是零。"
        ),
        "tags": ("网球", "网球时差", "辛纳", "大师赛", "网球冷知识"),
    },    "comeback-middle": {
        "hook": (
            "同一个部位、几乎同一台手术，一个五个月后拿了温网，一个再没回去。\n"
            "而在中段那几个月，两条路长得一模一样——郑钦文现在正走在那一段里。"
        ),
        "tags": ("网球", "网球时差", "德约科维奇", "郑钦文", "网球冷知识"),
    },
    "protected-ranking": {
        "hook": (
            "「保护排名」这四个字翻拧了——ATP 规则书里它叫 Entry Protection，进赛保护。\n"
            "它替你报名，一个字都不保你的排名，而且只保护彻底停下来的人。"
        ),
        "tags": ("网球", "网球时差", "郑钦文", "保护排名", "网球冷知识"),
    },
    "lucky-loser": {
        "hook": (
            "资格赛输掉的人，可以因为别人退赛递补进正赛——这个身份叫幸运落败者。\n"
            "卢布列夫和高芙的第一个冠军，都是这么来的。"
        ),
        "tags": ("网球", "网球时差", "幸运落败者", "卢布列夫", "网球冷知识"),
    },
    "hawkeye": {
        "hook": (
            "一颗球压没压线，网球用了一百年才把这句话从人眼交给摄像机。\n"
            "现在四大满贯里，只剩一个地方还没交。"
        ),
        "tags": ("网球", "网球时差", "鹰眼", "电子司线", "网球冷知识"),
    },
    "masters-format": {
        "hook": (
            "世界第一辛纳、德约科维奇同一天退出蒙特利尔大师赛。\n"
            "赛事方这次没忍住——问题出在赛程，还是出在球员？"
        ),
        "tags": ("网球", "网球时差", "ATP", "大师赛", "辛纳"),
    },
    "queue": {
        "hook": (
            "四大满贯里只有温网和法网，当天排队还能坐进中央球场。\n"
            "代价是：在草地上睡一晚。"
        ),
        "tags": ("网球", "网球时差", "温网", "排队", "网球冷知识"),
    },
    "rufus": {
        "hook": (
            "温网有一名员工，工牌上的职位写着「赶鸟员」。\n"
            "它是一只鹰。2012 年，它还被人偷走过三天。"
        ),
        "tags": ("网球", "网球时差", "温网", "猛禽", "网球冷知识"),
    },
    "wimbledon-whites": {
        "hook": (
            "温网所有人都穿白，这条规矩管到什么程度？内衣也得是白的。\n"
            "直到 2023 年，才松了一道口子。"
        ),
        "tags": ("网球", "网球时差", "温网", "网球规则", "网球冷知识"),
    },
    "longest-match": {
        "hook": (
            "2010 年温网首轮，一片外场，两个没什么人关注的名字。\n"
            "他们在那里打了三天，11 小时 5 分钟——记分牌先撑不住了。"
        ),
        "tags": ("网球", "网球时差", "温网", "网球纪录", "网球冷知识"),
    },
    "yellow-ball": {
        "hook": (
            "网球是黄色的，这件事其实还不到六十年。\n"
            "在那之前，它白了将近一百年——把它改成黄色的不是球员，是电视。"
        ),
        "tags": ("网球", "网球时差", "网球冷知识", "温网", "网球历史"),
    },
    "roof": {
        "hook": (
            "温网中央球场的屋顶，规则只写了两种情况可以关：下雨，或者光线不足。\n"
            "2025 年八点半关，2026 年七点四十关——同一周的伦敦，差了五十分钟。"
        ),
        "tags": ("网球", "网球时差", "温网", "德约科维奇", "网球规则"),
    },
    "ten-champions": {
        "hook": (
            "维纳斯玫瑰露水盘的盘座上，十年刻了十个名字，一个都没重复。\n"
            "同样这十届，男单只有五个人在轮着抱杯——这算好事还是坏事？"
        ),
        "tags": ("网球", "网球时差", "温网", "诺斯科娃", "女子网球"),
    },
    "ball-pick": {
        "hook": (
            "球童递上来三四个球，球员只留两个——那两眼在看什么？\n"
            "答案是毛。而换球的两个数字更怪：先打 7 局，之后每 9 局。"
        ),
        "tags": ("网球", "网球时差", "网球规则", "网球冷知识", "发球"),
    },
    "shot-clock": {
        "hook": (
            "发球只有 25 秒，这条规矩你大概知道。\n"
            "但今年它悄悄变了一处：钟不再等主裁报分，一分打完就自己开始走。"
        ),
        "tags": ("网球", "网球时差", "网球规则", "阿尔卡拉斯", "ATP"),
    },
    "zheng-eala": {
        "hook": (
            "三年前的亚运会半决赛，郑钦文赢了对面那个人，然后拿走金牌。那一年钦文 21 岁。\n"
            "三年后再见，对手也 21 岁，是生涯新高世界第 28；钦文自己要靠一张外卡才能进正赛。\n"
            "排名会掉，人还在场上。"
        ),
        "tags": ("网球", "网球时差", "郑钦文", "伊埃拉", "WTA"),
    },
    "shang-nishikori": {
        "hook": (
            "锦织圭宣布了：2026 年打完就退役。\n"
            "他是公开赛年代唯一一个代表亚洲国家打进大满贯男单决赛的球员——2014 年美网。\n"
            "7 月 27 日华盛顿首轮，对面站着 21 岁的商竣程；两年前在成都，是他把锦织圭淘汰的。"
        ),
        "tags": ("网球", "网球时差", "商竣程", "锦织圭", "ATP"),
    },
    "venus-potapova": {
        "hook": (
            "去年这一站，45 岁的维纳斯赢了一场，那是 2004 年之后 WTA 最年长的单打胜利。\n"
            "赛后被问为什么回来，她说：我得回来上保险，我天天跑医院。\n"
            "然后她补了一句：说到底就是爱，够爱就会去付出。\n"
            "今年她 46 岁，又回到同一块场地，手里又是一张外卡。"
        ),
        "tags": ("网球", "网球时差", "维纳斯威廉姆斯", "WTA", "华盛顿站"),
    },
    "wong-lehecka": {
        "hook": (
            "世界第 108 打世界第 12，中间差了 96 位。\n"
            "但公开赛年代第一个打进大满贯正赛、第一个赢下大满贯正赛、"
            "第一个打进第三轮的香港男子，都是黄泽林一个人。\n"
            "2023 年杭州亚运会，他救了 5 个赛点淘汰吴易昺；"
            "2025 年迈阿密，他赢过世界第 14 的谢尔顿。\n"
            "7 月 30 日 09:00，洛斯卡沃斯中心球场第一场。"
        ),
        "tags": ("网球", "网球时差", "黄泽林", "莱赫奇卡", "洛斯卡沃斯"),
    },
    "wildcard": {
        "hook": (
            "签表上那两个字母 WC，是主办方直接发的正赛资格：不看排名，也不用打资格赛。\n"
            "规则书写得很直白——一名球员能拿到几张外卡，不设任何限制。\n"
            "今年七月，一个人靠它打进温网四强；另一个人在等一张始终没等到的外卡。"
        ),
        "tags": ("网球", "网球时差", "网球规则", "郑钦文", "温网"),
    },
    "thiem-football": {
        "hook": (
            "2020 年 9 月 13 日，他在纽约 0-2 落后翻盘，拿下生涯唯一一座大满贯。\n"
            "五年后的同一天，他在奥地利第八级联赛替补上场，12 分钟后打进一球。\n"
            "中间那几年叫手腕伤——31 岁那年他退役了。\n"
            "今年 7 月，他在足协重新登记成了球员。踢球的。"
        ),
        # 人名一律查译名表：player_zh("Dominic Thiem") → 蒂姆。
        "tags": ("网球", "网球时差", "蒂姆", "美网", "足球"),
    },
}


@dataclass(frozen=True)
class Column:
    """A named strand of the account, printed on every card it produces.

    A column is a promise, not a decoration: the reader who sees 网球有故事
    expects something that will still be true next year, and the one who sees
    开球之前 expects a match that has not started yet. Mixing them costs the
    label its meaning — a preview published under 网球有故事 is stale the
    moment play begins, and nothing on the card would have said so.
    """

    name: str
    promise: str
    # Does the piece expire? Evergreen columns can be re-shared any time;
    # a perishable one is only true until the match starts, so its copy has
    # to say when that is.
    perishable: bool


COLUMNS: dict[str, Column] = {
    "网球有故事": Column(
        name="网球有故事",
        promise="一个人人见过、没人讲得清的网球现象，讲清它的来历和现在。",
        perishable=False,
    ),
    "开球之前": Column(
        name="开球之前",
        promise="一场还没开打的比赛，把两边这几年的来路摆在一起；不预测结果。",
        perishable=True,
    ),
    # 一度还有 First Serve / Second Serve 两个英文栏目（专收「讲一个人」的片子），
    # 以及「握手之后」（一场刚打完的比赛对两个人各意味着什么）。三个都撤了，
    # 理由是同一条：**五个栏目读者记不住**。栏目是承诺，多一个就薄一分。
    #
    # 「握手之后」撤得最干净——**名下一条片子都没有**。它和「赛场之上」的界线本来
    # 按握手划（后者管比赛本身，它管这场对两个人的意义），但一年下来没有一条片子
    # 真的需要那条界线：想讲意义的时候，把意义讲进「赛场之上」的配音里就够了，
    # 读者并不需要为此多记一个名字。
    #
    # 那类片子现在去哪儿：夺冠、复出、告别本身都是一场刚打完的比赛，归「赛场之上」，
    # 只是配音的重心往前推到他这些年。真到了「塞不进去」的那天再重开，
    # 设计和取舍都在 git 历史里，不用重想一遍。
    #
    # ⚠️ **「赛场之上」和「赛后开麦」不在这个表里**：这个表只管解说视频卡面上印的
    # 台头，那两条是另外的生产线（集锦视频 / 采访视频），台头在各自的渲染里。
    # 全账号的栏目总表在 docs/columns.md。**加栏目要两处一起改**——曾经因为
    # push_reel.py 的默认值和这里对不上，休伊特那条片子海报印「网球有故事」、
    # 微信标题却写「赛场之上」。
}

DEFAULT_COLUMN = "网球有故事"


def explainer_column(slug: str) -> str:
    """The column a deck is published under."""
    return (_OPENINGS.get(slug) or {}).get("column") or DEFAULT_COLUMN


def column_of(slug: str) -> Column:
    """The column record behind a deck. Raises on a name nobody registered."""
    name = explainer_column(slug)
    try:
        return COLUMNS[name]
    except KeyError:  # a typo here would silently invent a third column
        raise KeyError(
            f"{slug} 声明的栏目「{name}」没有登记在 COLUMNS 里"
        ) from None


# The first seconds decide whether anyone stays, and a deck that opens on
# beat one makes the viewer work out the subject for themselves. Every deck
# now opens on the question it answers, said out loud and set large.
_OPENINGS: dict[str, dict] = {
    "nadal-academy": {
        # ⚠️ 原来写「纳达尔学院：七个人，七条来时路」——账号所有者 2026-08-04
        # 一句「这里文案太普通了」。毛病是它在**描述格式**（几个人、几条路），
        # 不是在讲事实，读者一个字的信息都拿不到。换成片子的落点本身：
        # 「差八岁」是 21−13 算出来的——但账号所有者又退回来一次：「这个文案也不太好，
        # 需要体现出纳达尔学院的厉害之处」。对的，**台头是门面，该先把厉害亮出来**，
        # 我那句一上来就在挑刺。现在亮的是这条线上最硬的成绩：同时七个人在世界前一百。
        # ⚠️ 想过写「一个小镇，七个世界前一百」（马纳科尔才四万人，反差最大），
        # **不能用**——会被读成「七个人都是这个小镇出的」，而他们来自马尼拉、香港、
        # 奥斯陆。第一是精准，第二才是引爆。
        # 顺带：门面亮成绩、片子再把这五个字拆开，两者不冲突——正是「最硬的那个
        # 事实放第 ① 屏」，先给人看的理由，再给人想的东西。
        "topic": "一个学院，同时七个世界前一百",
        # ⚠️ 卡的是**排一行的像素宽**（≥84px），不是字数。见 test_封面那一问要能排进一行。
        "question": "六个人的纪录，八周就破了？",
        "narration": "六个人的纪录，八周就破了？而破它的那个人，来自中国香港。",
        "gloss": "Rafa Nadal Academy = 拉法·纳达尔学院",
        # ⚠️ 封面不用抽帧，也不用学院的场地照——这条片子讲的是**人怎么来的**，
        # 场地照讲不了这件事。首选伊埃拉华盛顿捧杯（8/3 那天，且捧杯优先于击球中），
        # 尺寸要够裁 1080×1440 而不放大。见 assets/explainer/nadal-academy/credits.json。
        "image": "assets/explainer/nadal-academy/eala_washington_2026_final.jpg",
        "credit": "Getty Images / WTA 官方图库 · 2026 年 8 月 3 日华盛顿女单决赛，伊埃拉夺冠后庆祝",
    },
    "special-exempt": {
        "topic": "特殊豁免：整站只留一个位置",
        # ⚠️ 卡的是**排一行的像素宽**（≥84px），不是字数：
        # 「上一站还没打完，下一站怎么办？」只有 77px，会在词中间断成两行。
        # 这一句 89px。见 test_封面那一问要能排进一行。
        "question": "雨没停，下一站还赶得上吗？",
        "narration": "雨没停，下一站还赶得上吗？规则给这件事留了一个位置，整站只有一个。",
        "gloss": "Special Exempt = 特殊豁免",
        # ⚠️ **封面不用抽帧。** 一开始挂的是第 ⑥ 屏那张 1920×1080 的集锦帧，
        # 而封面要铺满 1080×1440 的 3:4——横帧裁完只有 810×1080，**得放大 133%**，
        # `test_封面图不许被放大` 当场判红。CLAUDE.md 那条「封面用真实照片，
        # 不要从视频里抽帧……封面又是唯一决定人点不点的那一屏」说的就是这个。
        # 换成 Commons 上 4000×6000 的原图，裁 3:4 之后还剩 1.85 倍余量。
        # 年份和这条片子讲的 2025 不同，所以写在署名里（照 pr-allowance 的做法：
        # 封面那张任何一屏都不用，借不到出处，自己写一行）。
        "image": "assets/explainer/special-exempt/cazaux_usopen_2023_forehand.jpg",
        "credit": "Hameltion / Wikimedia Commons · CC BY-SA 4.0 · 2023 年美网，卡佐正手伸展",
    },
    "pr-allowance": {
        "topic": "保护排名：9 站或 9 个月，先到先算",
        "question": "保护排名，能用几次？",
        "narration": "保护排名，能用几次？答案不是一个数，是两个上限同时在倒计时。",
        "gloss": "Entry Protection = 保护排名",
        # 封面这张没有任何一屏在用，借不到出处，自己写一行。
        # 选双脚离地那一帧：这条片子讲的是「额度」，而额度买来的正是**站上场**
        # 这件事本身。照片是 2023 年美网，年份写在卡上——他现在的处境是 2026 年的，
        # 但 Commons 上他 2025 年之后的比赛照一张都没有（探过，见 credits）。
        "image": "assets/explainer/pr-allowance/stephens_usopen_2017_lift.jpg",
        "credit": "WTA 官方图库 · 2017 年 9 月 9 日美网女单决赛，斯蒂芬斯举起奖杯",
    },
    "challenger-climb": {
        "topic": "挑战赛：难的不是对手，是兑换率",
        "question": "赢五场，不如赢两场？",
        "narration": "赢五场，不如赢两场？低级别为什么爬不上来——先说结论："
                     "不是那一档的人更凶。",
        "gloss": "Challenger = 挑战赛",
        # 封面这张没有任何一屏在用，借不到出处，自己写一行。
        # 选张之臻是因为**他就是这条片子的题目**：曾经世界前 30，
        # 现在第 158，在一站挑战赛里是 9 号种子。照片拍于他还在巡回赛上的
        # 2023 年美网——反差本身就是内容，卡上的年份写清楚。
        "image": "assets/explainer/challenger-climb/zhang_usopen_2023.jpg",
        "credit": "Wikimedia Commons · CC BY-SA 4.0 · 2023 年美网首轮，张之臻发球",
    },
    "entry-deadline": {
        "topic": "报名截止线：名单在六周之前就锁上了",
        "question": "排名涨了，为什么用不上？",
        "narration": "排名涨了，为什么用不上？因为那张名单，在开赛整整六周之前"
                     "就已经锁上了。",
        "gloss": "Entry Deadline = 报名截止线",
        # 封面这张没有任何一屏在用，借不到出处，所以自己写一行。
        # 选它是因为**原图 1023×1365 正好 3:4**，铺满 1.0x，零垫层零虚化；
        # 而商竣程正是这条片子里「用凭证够着了那条线」的那个人。
        "image": "assets/explainer/entry-deadline/us_open_court_34.jpg",
        "credit": "美网官方 · 亚瑟·阿什球场（原图 4032×3024，居中裁为 3:4）",
    },
    "mandatory-1000": {
        "topic": "强制赛：不去的代价，是一个可以算出来的数",
        "question": "强制赛，为什么可以不去？",
        "narration": "强制赛，为什么可以不去？规则书写着自动生效、不可申诉——"
                     "可算下来，那一笔罚在世界第一身上是零。",
        "gloss": "Zero-Pointer = 罚成零分",
        # 封面这张没有任何一屏在用，借不到出处，所以自己写一行。
        # 选它是因为**原图 1121×1495 正好 3:4**，铺满 1.0x，一个像素的垫层都不用；
        # 而且它就是这条片子的起点：三周前他在这儿举起奖杯，这一周他没去蒙特利尔。
        "image": "assets/explainer/ten-champions/sinner.jpg",
        "credit": "AELTC / Joel Marklund · 2026 年 7 月 12 日，辛纳温网卫冕",
    },
    "comeback-middle": {
        "topic": "中段：谁回得来，当时看不出来",
        "question": "伤好了打不出来，是低谷还是终点？",
        "narration": "伤好了打不出来，这是低谷，还是终点？"
                     "有两个人给过完全相反的答案，而当时谁也分不出来。",
        "image": "assets/explainer/comeback-middle/djokovic_ao_2018.jpg",
        "credit": "Joshua Sadli · Wikimedia Commons · CC BY-SA 2.0 · 2018 年 1 月 15 日，墨尔本",
    },
    "protected-ranking": {
        "topic": "保护排名：它保的是报名，不是排名",
        "question": "不打球，排名为什么还在掉？",
        "narration": "不打球，排名为什么还在掉？那个叫「保护排名」的东西，"
                     "一个字都没保住排名。",
        "gloss": "PR = Protected Ranking",
        "image": "assets/explainer/zheng-eala/zheng_fistpump.jpg",
        # 封面这张没有任何一屏在用，所以借不到出处，必须自己写一行。
        # 选它是因为**原图 1184×1579 正好 3:4**，铺满 1.096x，一个像素的垫层都不用
        # ——上一条片子的封面顶部虚化占了 15.6%，这条是 0。
        "credit": "账号所有者提供 · 郑钦文回望球员席",
    },
    "lucky-loser": {
        "topic": "幸运落败者：输了才有的名额",
        "question": "资格赛输了，怎么还在正赛？",
        "narration": "资格赛输了，怎么还在正赛？他自己管这叫——输的那个人，是幸运的。",
        "gloss": "LL = Lucky Loser",
        "image": "assets/explainer/lucky-loser/rublev_umag_2017_trophy.jpg",
    },
    "hawkeye": {
        "topic": "鹰眼的来历：源于一次误判",
        "question": "球压没压线，到底谁说了算？",
        "narration": "球压没压线，到底谁说了算？这件事，网球用了一百年才交出去。",
        "image": "assets/explainer/hawkeye/us_open_court.jpg",
    },
    "yellow-ball": {
        "topic": "网球改色史：源于彩色电视",
        "question": "网球为什么是黄色的？",
        "narration": "网球为什么是黄色的？而且它变成黄色，还不到六十年。",
        "image": "assets/explainer/yellow-ball/optic_yellow.jpg",
    },
    "longest-match": {
        "topic": "史上最长的比赛：源于第五盘没有抢七",
        "question": "一场网球，最长能打多久？",
        "narration": "一场网球最长能打多久？答案是十一小时五分钟，分三天打完。",
        "image": "assets/explainer/longest-match/scoreboard.jpg",
    },
    "wimbledon-whites": {
        "topic": "温网的白衣规矩：成文于 1963 年",
        "question": "温网为什么只准穿白？",
        "narration": "温网为什么只准穿白？这条规矩，一直管到内衣。",
        "image": "assets/explainer/wimbledon-whites/headtotoe.jpg",
    },
    "rufus": {
        "topic": "温网的赶鸟员：源于中央球场的鸽子",
        "question": "温网为什么雇了一只鹰？",
        "narration": "温网有一名员工是一只鹰。它为什么在那儿上班？",
        "image": "assets/explainer/rufus/patrol.jpg",
    },
    "queue": {
        "topic": "温网的排队文化：源于当天发售的门票",
        "question": "温网的票为什么要排一晚？",
        "narration": "温网的票，为什么要在草地上排一晚？",
        "image": "assets/explainer/queue/queue.jpg",
    },
    "masters-format": {
        "topic": "大师赛的退赛潮：源于赛期从一周变十二天",
        "question": "大师赛为什么变成两周？",
        "narration": "大师赛为什么变成了两周？而顶尖球员，正在一个接一个退赛。",
        "image": "assets/explainer/masters-format/sinner.jpg",
    },
    "roof": {
        "topic": "温网屋顶的争议：源于「光线不足」没有时间",
        "question": "温网的屋顶，谁说了算？",
        "narration": "温网的屋顶，到底谁说了算？规则只写了两种情况可以关。",
        "image": "assets/explainer/roof/aerial.jpg",
    },
    "ten-champions": {
        "topic": "温网的十年：女单十个冠军，男单五个",
        "question": "女单十冠，男单五冠？",
        "narration": "同样十届温网，女单十冠，男单五冠。这差别是怎么来的？",
        "image": "assets/explainer/ten-champions/noskova.jpg",
    },
    "ball-pick": {
        "topic": "挑球：每个发球局都在发生的选择",
        "question": "发球前，他们在挑什么？",
        "narration": "球童递上来三四个球，球员只留两个。那两眼，到底在挑什么？",
        "image": "assets/explainer/ball-pick/djokovic_serve.jpg",
        "credit": "AELTC/Felix Diemer · wimbledon.com 官方图 · 2026 温网 1/4 决赛，德约科维奇发球",
    },
    "shot-clock": {
        "topic": "发球 25 秒：一条改了两次的规则",
        "question": "发球的 25 秒，谁在计时？",
        "narration": "发球的二十五秒，到底是谁在计时？这条规矩你大概知道，但那块钟今年换了主人。",
        "image": "assets/explainer/shot-clock/umpire.jpg",
    },
    "zheng-eala": {
        "column": "开球之前",
        "topic": "郑钦文 VS 伊埃拉：华盛顿站首轮前瞻",
        # 「她」has no safe antecedent on this cover: both players are women and
        # the picture shows one of them, so a viewer can read it either way.
        # Every line here names whoever it means.
        "question": "三年前钦文赢了那个人，这次呢？",
        "narration": "三年前的亚运会半决赛，郑钦文赢了对面那个人，然后一路拿走金牌。"
        "三年后再见，对手升到了生涯新高世界第二十八，郑钦文自己要靠一张外卡才能进正赛。"
        "三年前钦文赢了那个人，这次呢？",
        # The cover frame comes from the account owner, who states it is
        # recent. Its background is an out-of-focus sponsor board, so unlike
        # the other candidates it commits to no surface and cannot contradict
        # a hard-court preview. No date is burned into the slide because none
        # is documented: the file carries only container EXIF — no capture
        # time, no author — and the board behind her is too blurred to read.
        # The two older photos in the deck stay where they are because their
        # dates are the point: the Olympic beat needs the gold, and the
        # "three years ago" beat needs 2023.
        # 这三条是 2026-07-27 已经推送出去的，封面小字是后加的版式，
        # 只在下次重渲时才会出现——「改的是以后，不动已经发出去的」。
        # `time` 留空：当时没有记下官方开赛时刻，宁可不印也不猜。
        "fixture": {
            "date": "7.27",
            "level": "WTA500",
            "site": "华盛顿",
            "round": "首轮",
            "players": ("郑钦文", "伊埃拉"),
        },
        "image": "assets/explainer/zheng-eala/zheng_fistpump.jpg",
        "credit": "账号所有者提供 · 摄影师与出处未标注（unknown / unverified）· 郑钦文",
    },
    "shang-nishikori": {
        "column": "开球之前",
        "topic": "商竣程 VS 锦织圭：华盛顿站首轮前瞻",
        "question": "锦织圭的最后一年，谁来接？",
        "narration": "锦织圭已经宣布，二〇二六年打完就退役。他是公开赛年代唯一一位"
        "代表亚洲国家打进大满贯男单决赛的球员。七月二十七日华盛顿首轮，"
        "站在他对面的是二十一岁的商竣程——两年前在成都赢过他的那个人。"
        "锦织圭的最后一年，谁来接？",
        "fixture": {
            "date": "7.27",
            "level": "ATP500",
            "site": "华盛顿",
            "round": "首轮",
            "players": ("商竣程", "锦织圭"),
        },
        "image": "assets/explainer/shang-nishikori/cover_shang.jpg",
        "credit": "CGTN · 2026 年 1 月香港站，商竣程",
    },
    "venus-potapova": {
        "column": "开球之前",
        "topic": "维纳斯 VS 波塔波娃：华盛顿站首轮前瞻",
        "question": "46 岁了，维纳斯为什么还在打？",
        "narration": "去年的这一站，四十五岁的维纳斯赢下一场单打，创下二〇〇四年之后的最年长纪录。"
        "一年之后她回来了，四十六岁，世界第四百六十九，手里又是一张外卡。"
        "四十六岁了，维纳斯为什么还在打？",
        # The whole deck is about her coming back to this one tournament, so
        # every Venus frame in it comes from the same shoot — 2025-07-20, the
        # week she made the record. The source calls them practice and press,
        # never match play, and no screen says otherwise.
        "fixture": {
            "date": "7.27",
            "level": "WTA500",
            "site": "华盛顿",
            "round": "首轮",
            # 表里她是「大威廉姆斯」，这条片子通篇叫她维纳斯（见测试里的
            # _ON_PURPOSE）。封面没有上下文消歧，所以写全名。
            "players": ("维纳斯·威廉姆斯", "波塔波娃"),
        },
        "image": "assets/explainer/venus-potapova/venus_serve.jpg",
        "credit": "Hameltion · CC BY-SA 4.0 · Wikimedia Commons · 2025 年 7 月华盛顿站赛前训练",
    },
    "wong-lehecka": {
        "column": "开球之前",
        # 台头不写「前瞻」：上面一行印着栏目名「开球之前」，已经说了这是赛前。
        # 加上它正好把台头顶到 21 字，超小红书那条 20 字的线。
        "topic": "黄泽林 VS 莱赫奇卡：洛斯卡沃斯站 16 强",
        # 「他」在这条片子里没有安全的指代——两个人都是男球员，封面上站着其中
        # 一个。所以封面这一问点名，正文里的第三人称一律靠上一句消歧。
        "question": "黄泽林要怎样挑战世界第 12？",
        # 第一句在句号处收住（25 字 ≈ 4.7 秒），把对阵挪到第二句：前 5 秒
        # 决定 62% 的人走不走，一句话铺完时间地点对阵就是 57 字、9 秒多。
        # 已发的两条「开球之前」都栽在这儿（见 _HOOK_TOO_LONG），这条不进名单。
        "narration": "北京时间七月三十日上午九点，洛斯卡沃斯的中心球场。"
        "第一场，一号种子、世界第十二的莱赫奇卡，对世界第一百零八的黄泽林，"
        "两个人此前从没交过手。黄泽林要怎样挑战世界第十二？",
        # 封面复用「珠海」那一屏的图，所以出处由那一屏的 credit 带过来。
        # 选它当封面的理由：它是他最近一场可及的击球帧（2025 年 11 月），
        # 球在拍面上，胸口的紫荆花徽章让画面自己说清这是谁。
        "image": "assets/explainer/wong-lehecka/wong_national_games.jpg",
        "credit": "Eugene Lee · SCMP · 2025 年 11 月全运会男单半决赛，黄泽林对吴易昺",
        # 时刻取自赛会官方 Order of Play（07/29 02:24 发布）：Estadio Alejandro
        # Burillo「Starts At 18:00」第一场，当地 UTC-7，换算成北京时间 7/30 09:00。
        # 是 Starts At 不是 Not Before，所以这个点就是开赛时刻，不是下界。
        "fixture": {
            "date": "7.30",
            "time": "09:00",
            "level": "ATP250",
            "site": "洛斯卡沃斯",
            "round": "16 强",
            "players": ("黄泽林", "莱赫奇卡"),
        },
    },
    "thiem-football": {
        "topic": "蒂姆退役之后：从大满贯到第八级联赛",
        # 封面用他踢球那张，一眼就说清这条片子讲什么。**卡上不写日期**：
        # 来源（GEPA 经 laola1）只给了 `Foto: © gepa`，没有图注、没有拍摄
        # 时间地点，写年份就是靠看图推断。画面本身立得住的只有「他在踢球」，
        # 那就只说这一句。
        "question": "美网冠军退役两年后，在哪儿比赛？",
        # 第一句必须在 5 秒内说完（上限 27 字）——0-2 落后翻盘那段挪去第二句。
        "narration": "二〇二〇年美网，他拿了生涯唯一一座大满贯。"
        "决赛先丢两盘，然后连扳三盘，第五盘抢七八比六，那年他世界第三。"
        "四年之后，手腕伤让他在三十一岁退役。"
        "美网冠军退役两年后，在哪儿比赛？",
        # 封面本来想用他踢球那张（一眼说清这条片子讲什么），换成捧杯是被
        # `test_封面图不许被放大` 逼回来的：那张 GEPA 图高只有 964px，
        # 而卡片是 1080x1440，`fill = min(w/1080, h/1440)` 怎么裁都是 0.67
        # ——封面一上来就放大 1.5 倍，和「别拿视频抽帧当封面」是同一个毛病。
        # 加进 _UNDERSIZED 能让测试过，但那是把判据改成迁就素材。
        # 踢球那张挪到第 ① 屏，正好落在讲「他现在在哪儿踢」的那一屏上；
        # 封面用捧杯 + 「退役两年后在哪儿比赛」，悬念反而更足。
        "image": "assets/explainer/thiem-football/trophy_2020.jpg",
        "credit": "AP/Getty 经 CNN 转载 · 2020 年 9 月 13 日纽约，蒂姆举起美网男单奖杯",
    },
    "wildcard": {
        "topic": "外卡：一张不设上限的入场券",
        # 封面的画面就是澳网签表，所以这里说 WC 是对的；温网写 (W)，
        # 这个差别放在第 ① 屏的旁白里讲，别在封面上笼统一句「签表上都写 WC」。
        "question": "签表里名字旁的 WC，是谁给的？",
        "narration": "签表里，有的名字后面跟着两个字母：WC。它是谁给的，凭什么给？",
        "image": "assets/explainer/wildcard/ao_draw_wc.jpg",
    },
}


def _fixture_lines(spec: dict) -> tuple[str, ...]:
    """封面上那两行小字：比赛坐标 + 对阵。

    账号所有者定的版式：

        7.30  09:00  ATP250 洛斯卡沃斯  16 强
        黄泽林  VS  莱赫奇卡

    从结构化字段拼，不让人手写整行——日期和轮次在旁白、要点、文案里都各出现
    一次，手写第四遍必然会有一处对不上。时间可以缺（三条已发的前瞻当时没有
    记下官方开赛时刻），缺了就不占位置，别印一个空的冒号。

    级别和站点分开存（`level` + `site`，印出来仍是「ATP250 洛斯卡沃斯」），
    是为了让「只做 250 及以上」这条选题门槛能对着 `TOUR_LEVELS` 查——
    合成一个字符串就只能靠正则去猜级别了。
    """
    fixture = spec.get("fixture") or {}
    if not fixture:
        return ()
    event = f"{fixture['level']} {fixture['site']}"
    head = "  ".join(
        str(value)
        for value in (fixture.get("date"), fixture.get("time"), event,
                      fixture.get("round"))
        if value
    )
    home, away = fixture["players"]
    return (head, f"{home}  VS  {away}")


def _opening_segment(story, beats: list[ExplainerSegment]) -> ExplainerSegment:
    """The cover card: the question, said out loud, before any explaining."""
    spec = _OPENINGS.get(story.slug) or {}
    question = spec.get("question") or f"{story.title}？"
    image = spec.get("image") or (beats[0].image if beats else "")
    # Usually the cover reuses a beat's photo and can borrow its credit line.
    # When it has one of its own, the opening has to carry the provenance
    # itself — an uncredited frame is one nobody can check later.
    credit = spec.get("credit", "")
    for beat in beats:
        if beat.image == image:
            credit = beat.credit
            break
    return ExplainerSegment(
        kind="cover",
        label="",
        title=question,
        narration=spec.get("narration") or question,
        image=image,
        credit=credit,
        points=(),
        diagram="",
        question="",
        fixture=_fixture_lines(spec),
        gloss=spec.get("gloss", ""),
    )


def _ask_it_out_loud(closer: ExplainerSegment) -> ExplainerSegment:
    """收尾那个问题，画面上写了，嘴上也要问出来。

    十三条片子里有十条只把问题印在末屏，旁白讲完就停——**听着的人根本不知道
    被问了什么**。而这个问题是这类短片换评论区的唯一抓手，只给眼睛不给耳朵，
    等于白留。所以在这里统一补上，而不是指望每写一条都记得手动加一遍。

    已经在旁白里问过的（去掉问号后能在旁白里找到）就不重复。
    """
    q = (closer.question or "").strip()
    if not q:
        return closer
    tail = closer.narration[-40:]
    # 只看结尾这一段有没有问号。用「问题原句是否出现在旁白里」当判据不够：
    # 好几条片子的旁白早就问过意思一样、措辞不同的话（「你觉得法网什么时候也会
    # 换成电子司线？评论区聊聊。」），逐字比对匹配不上，补一遍就变成连问两遍。
    if "？" in tail or "?" in tail:
        return closer
    # 有几条旁白是特意停在破折号上等着这一问的（「所以问题来了——」），
    # 那里再补一个句号会多出一个孤零零的点。
    joiner = "" if closer.narration.rstrip().endswith(("——", "—", "：")) else "。"
    body = closer.narration.rstrip()
    if joiner == "。" and body.endswith(("。", "！", "…")):
        joiner = ""
    return dataclasses.replace(closer, narration=f"{body}{joiner}{q}")


def explainer_script(story) -> list[ExplainerSegment]:
    """Return the three-beat script for a story, each beat with a hero visual.

    Hand-authored, fact-grounded scripts (with curated photos) are used when
    available; otherwise beats are derived from the story's own moments/facts
    and use the story's verified cover asset as the hero image so no beat is
    ever text-only.
    """
    scripted = _SCRIPTS.get(story.slug)
    if scripted:
        beats = [ExplainerSegment(*row) for row in scripted]
        beats[-1] = _ask_it_out_loud(beats[-1])
        return [_opening_segment(story, beats), *beats]

    moments = list(getattr(story, "moments", ()) or ())
    facts = list(getattr(story, "facts", ()) or ())
    cover = str(getattr(story, "image", "") or "")
    credit = f"图：{getattr(story, 'image_credit', '') or '官方媒体供图'}"
    cause = (
        f"{moments[0].headline}。{moments[0].detail}" if moments else story.hero_fact
    )
    return [
        ExplainerSegment("cause", "前因后果", "故事的起点", cause, cover, credit),
        ExplainerSegment(
            "mechanism", "技术原理", "它到底怎么回事",
            facts[0] if facts else story.hero_fact, cover, credit,
        ),
        ExplainerSegment(
            "today", "当今现状", "走到了今天",
            facts[-1] if facts else story.hero_fact, cover, credit,
        ),
    ]


# 封面大标题在这套显示字体里的字宽，**量出来的**（Chromium 里按 96px 渲一串，
# 读 getBoundingClientRect().width，再除以字号）：
#
#     一个汉字（含全角标点）  0.80 em（12 个字量出来正好 9.60）
#     一个空格               0.190 em
#     一个数字/字母          0.286～0.42 em —— **这套字体的数字不等宽**：
#                            单量「1」是 0.286，而「 12」整串是 0.892，
#                            扣掉空格摊到每个数字是 0.35。所以这里取 0.45
#                            往宽了算，宁可字号小一点也不要算窄了溢出。
#
# 别按「一个字一个 em」估：那样算「黄泽林要怎样挑战世界第 12？」是 15 em，
# 实际只有 10.49 em，差三分之一，估出来的字号会小一大截。
_COVER_EM_CJK = 0.80
_COVER_EM_ASCII = 0.45
_COVER_EM_SPACE = 0.190
# 再留 1.5% 余量：hawkeye 那句按模型算出来正好卡在 940px 上，差一个像素就
# 翻成两行，而翻没翻只有渲出来才知道。
_COVER_WIDTH_MARGIN = 0.985
# 一行装不下就退到两行的下限。定 84 的依据：再往下就是「一行小字」而不是
# 「一行大字」了，那时两行反而好读（`.cover .title` 那段注释里的老结论）。
_COVER_MIN_ONE_LINE_PX = 84


def _cover_title_em(title: str) -> float:
    """封面标题按上面那三个实测字宽折算成多少个 em。"""
    total = 0.0
    for ch in title:
        if ch == " ":
            total += _COVER_EM_SPACE
        elif ch.isascii():
            total += _COVER_EM_ASCII
        else:
            total += _COVER_EM_CJK
    return total


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def _slide_html(
    index: int, segment: ExplainerSegment, *, theme: str = "dark", topic: str = "",
    column: str = DEFAULT_COLUMN,
) -> str:
    """Image-first 3:4 brand card: real photo (or schematic) hero + short caption."""
    from ..render.webcards import _font_css

    cover = segment.kind == "cover"
    circled = ("①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨")
    # The cover is not a beat, so it carries no number and the beats after it
    # still count from one.
    beat_no = index if cover else index - 1
    number = circled[beat_no] if 0 <= beat_no < len(circled) else f"{beat_no + 1}"
    css = _font_css()

    icon_path = _REPO / "assets" / "logo" / "brand" / "icon.png"
    brand_icon = (
        f'<img class="brand-icon" src="{_data_uri(icon_path)}" alt="">'
        if icon_path.is_file()
        else ""
    )

    image_path = _REPO / segment.image if segment.image else None
    has_photo = bool(image_path and image_path.is_file())
    if has_photo:
        # Two reasons to letterbox rather than fill the card.
        #
        # A wide frame cropped to this 3:4 card loses its edges — and on a
        # photo of two people either side of a ball mark, the edges are the
        # subject. Letterbox those instead of cropping them away.
        #
        # A small frame is the other case: filling the card means scaling it
        # up, and the vintage white balls are only 947px wide, so covering
        # would blow them up 1.8x (3.6x at the 2x device scale) into mush.
        # A sharp letterboxed photo beats a soft full-bleed one.
        try:
            from PIL import Image as _Image

            with _Image.open(image_path) as probe:
                pw, ph = probe.width, max(probe.height, 1)
            wide = pw / ph >= 1.2 or max(W / pw, H / ph) > 1.6
        except Exception:  # noqa: BLE001
            wide = False
        # Letterboxing protects a beat's evidence from being cropped. The cover
        # card carries no evidence — the picture is atmosphere behind the
        # question — and bands there just make the opening look empty, so the
        # cover always fills.
        letterbox = wide and not cover
        uri = _data_uri(image_path)
        if letterbox:
            # 信箱式缩放的那几屏，上下留白原来铺的是 `.hero.diagram` 那层
            # 绿色径向渐变——**不透明**，于是卡片顶栏成了一条实心色带，
            # 而铺满的那几屏顶栏是压在照片上的（半透明观感）。同一条片子里
            # 两种顶栏，账号所有者一眼看出来：「顶部一定要半透明，和前面
            # 几张卡片一样」。
            #
            # 修法不是挪照片——挪上去她的头又会钻到顶栏底下，正是上一版
            # 被指出的问题。改成在底下垫一层**同一张照片**的模糊放大版：
            # 顶栏因此压在照片色上，和铺满的那几屏一致；上面那层 contain
            # 一个像素都不动，构图完全保持原样。
            #
            # scale(1.2) 是给 blur 留出溢出量，否则边缘会透出底色。
            hero = (
                f'<div class="hero blurbg" style="background-image:url(\'{uri}\');">'
                "</div>"
                f'<div class="hero" style="background-image:url(\'{uri}\');'
                "background-size:contain;background-repeat:no-repeat;"
                'background-position:center 34%;"></div>'
                '<div class="scrim"></div>'
            )
        else:
            hero = (
                f'<div class="hero" style="background-image:url(\'{uri}\');'
                'background-size:cover;background-position:center;"></div>'
                '<div class="scrim"></div>'
            )
    else:
        if not segment.diagram:
            # 这里原来是 `segment.diagram or _HAWKEYE_DIAGRAM`。一屏既没配图也没
            # 画示意图时，它会**悄悄**把鹰眼那张「摄像机三角测量落点」摆上去——
            # 起草外卡那条时就这么中过：封面渲出来是一张网球场测线图，和外卡毫无
            # 关系，而且不报错。已发的十四条每一屏都自带图或示意图，所以这个兜底
            # 从来没在产物里露过面，正因如此也没人发现它指着别的选题。
            #
            # 和「补位的静音盖住真音轨」「-filter_complex 不打标签就静默失效」
            # 是同一种毛病：**兜底出事的时候不吭声**。缺图就停下来说缺图。
            raise ValueError(
                f"这一屏既没有 image 也没有 diagram：[{segment.label}] {segment.title}\n"
                "补一张图或画一张示意图；别让它悄悄套用别的选题的图。"
            )
        hero = (
            '<div class="hero diagram"></div>'
            f'<div class="diagram-wrap">{segment.diagram}</div>'
            '<div class="scrim"></div>'
        )
    # One line, always: CJK glyphs run about one em wide, so size the headline
    # off its own length rather than letting it wrap.
    usable_px = W - 140
    if cover:
        # The question is the whole point of this card, so let it be big and
        # let it wrap; two lines of 9 characters beats one line of tiny text.
        #
        # 但**能一行就一行**。中文没有词边界，浏览器可以在任意两个汉字之间断，
        # 于是两行版必然会在某处把一个词劈开：「黄泽林要怎样挑 / 战世界第 12？」
        # 就是 `text-wrap:balance` 断出来的，「挑战」被切成两半。缩 7% 字号让
        # 整句落在一行上，比断在词中间好得多。装不下才退回两行（那时 balance
        # 至少保证两行长度接近，不会甩出一个三字符的孤行）。
        one_line = int(usable_px * _COVER_WIDTH_MARGIN / _cover_title_em(segment.title))
        title_px = min(96, one_line) if one_line >= _COVER_MIN_ONE_LINE_PX else min(
            96, int(usable_px * 2 / max(len(segment.title), 1))
        )
    else:
        title_px = min(62, int(usable_px / max(len(segment.title), 1)))
    question_html = (
        f'<div class="ask">{html.escape(segment.question)}</div>'
        if segment.question
        else ""
    )
    # 封面那两行小字（只有「开球之前」有）：第一行是比赛坐标，第二行是对阵。
    # 排在大问题下面，字号压到问题的三分之一上下——它是给「这到底是哪一场」
    # 兜底的，不是来抢封面的。
    gloss_html = (
        f'<div class="gloss">{html.escape(segment.gloss)}</div>'
        if segment.gloss
        else ""
    )
    fixture_html = (
        '<div class="fixture">'
        + "".join(
            f'<div class="{cls}">{html.escape(line)}</div>'
            for cls, line in zip(("when", "who"), segment.fixture)
        )
        + "</div>"
        if segment.fixture
        else ""
    )
    cover_cls = " cover" if cover else ""
    # 台头和封面小字讲的是同一件事（「黄泽林 VS 莱赫奇卡：洛斯卡沃斯站 16 强」
    # 对「7.30 09:00 ATP250 洛斯卡沃斯 16 强／黄泽林 VS 莱赫奇卡」），同一屏印两遍
    # 是噪点，而小字那份还多一个开赛时刻。所以封面有小字时台头让位，正文各屏照常。
    show_topic = topic and not (cover and segment.fixture)
    topic_html = f'<span class="topic">{html.escape(topic)}</span>' if show_topic else ""
    chip_html = (
        f'<span class="kicker">{html.escape(column)}</span>'
        if cover
        else f'<span class="chip">{number} {html.escape(segment.label)}</span>'
    )
    tail_html = ""
    points_html = (
        '<div class="points">'
        + "".join(
            f'<div class="point"><i>▪</i><span>{html.escape(p)}</span></div>'
            for p in segment.points
        )
        + "</div>"
        if segment.points
        else ""
    )
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{width:{W}px;height:{H}px;}}
body{{font-family:'TL Sans SC','Noto Sans CJK SC','Noto Sans SC',sans-serif;}}
.slide{{position:relative;width:{W}px;height:{H}px;overflow:hidden;color:#f4fbf7;
 background:#061c14;}}
.hero{{position:absolute;inset:0;}}
.hero.diagram{{background:radial-gradient(125% 80% at 50% 20%,#155a41 0%,#0b3a2a 55%,#061c14 100%);}}
/* 信箱式缩放那几屏的底衬：同一张照片的模糊放大版，让卡片顶栏压在照片色上，
   和铺满的那几屏观感一致。压暗到 .42 是为了让上层 contain 的那张仍然是
   视觉主体；scale(1.2) 给 blur 留溢出量，否则边缘透底。 */
.hero.blurbg{{background-size:cover;background-position:center;
 filter:blur(44px) brightness(.42) saturate(.85);transform:scale(1.2);}}
/* 760px on a 1080 card left the drawing at 70% width, and a 20px label inside
   a 900-unit viewBox came out around 17 real pixels — legible on a monitor,
   not on a phone held at arm's length. Fill the card instead, and start
   higher so the extra height still clears the caption block. */
.diagram-wrap{{position:absolute;left:0;right:0;top:210px;display:flex;justify-content:center;}}
.diagram-wrap svg{{width:920px;height:auto;}}
.scrim{{position:absolute;inset:0;background:linear-gradient(180deg,
 rgba(6,28,20,.55) 0%,rgba(6,28,20,.10) 34%,rgba(6,28,20,.20) 60%,rgba(6,28,20,.94) 100%);}}
.bar{{position:absolute;top:0;left:0;right:0;height:12px;z-index:5;
 background:linear-gradient(90deg,#c6f65a 0%,#37e29a 34%,#ff5a6a 67%,#4bb8ff 100%);}}
.head{{position:absolute;top:44px;left:70px;right:70px;z-index:5;display:flex;
 align-items:center;
 text-shadow:0 2px 12px rgba(0,0,0,.6);}}
.brandwrap{{display:flex;align-items:center;gap:14px;}}
.brandlines{{display:flex;flex-direction:column;gap:2px;}}
/* Muted grey worked while every cover sat under a heavy wash. With the
   photo showing through it disappeared into a bright sky or a stand full
   of green seats, so lift it and give it its own shadow — still quieter
   than the brand line above, but legible on any frame. */
.topic{{font-family:'TL Sans SC',sans-serif;font-size:27px;font-weight:700;
 color:#dcefe4;letter-spacing:1px;
 text-shadow:0 2px 10px rgba(0,0,0,.9),0 0 24px rgba(6,28,20,.8);}}
.brand-icon{{width:52px;height:52px;object-fit:contain;
 filter:drop-shadow(0 2px 8px rgba(0,0,0,.55));}}
.brand{{font-family:'TL Display SC','TL Sans SC',sans-serif;
 font-size:38px;font-weight:400;letter-spacing:1px;}}
.foot{{position:absolute;bottom:44px;left:70px;right:70px;z-index:5;
 display:flex;align-items:center;justify-content:flex-end;}}
.tag{{font-family:'Barlow Condensed','TL Sans SC',sans-serif;
 font-size:28px;color:#9fb4aa;font-weight:600;letter-spacing:2px;
 text-shadow:0 2px 10px rgba(0,0,0,.7);}}
.copy{{position:absolute;left:70px;right:70px;bottom:{CARD_COPY_BOTTOM}px;z-index:5;
 display:flex;flex-direction:column;gap:28px;}}
.chip{{align-self:flex-start;background:#37e29a;color:#062018;font-size:32px;
 font-weight:800;letter-spacing:3px;padding:12px 28px;border-radius:999px;}}
.title{{font-family:'TL Display SC','TL Sans SC',sans-serif;
 font-size:{title_px}px;line-height:1.2;font-weight:400;
 white-space:nowrap;text-shadow:0 4px 24px rgba(0,0,0,.75);}}
/* `text-wrap:balance` 而不是自己插换行：封面问题换行时，浏览器默认把最后
   一个装不下的片段甩到第二行，「黄泽林要怎样挑战世界第 / 12？」就是这么断的
   ——第二行只剩三个字符，像个错误。balance 让两行长度接近，而且**不动标题
   字符串本身**（`test_每条片子都以问题开场` 断言原字符串要出现在页面里，
   手插 `<br>` 或换行符会把那条判据弄假）。 */
.cover .title{{white-space:normal;text-wrap:balance;line-height:1.24;font-weight:400;
 text-shadow:0 2px 6px rgba(0,0,0,.9),0 6px 30px rgba(0,0,0,.85),
 0 0 60px rgba(6,28,20,.7);}}
.cover .copy{{bottom:auto;top:50%;transform:translateY(-50%);gap:34px;}}
/* The cover used to sit under a flat 62-78% wash, which made every deck
   open on the same dark green rectangle with a photo faintly behind it —
   the one frame that has to stop a thumb was the least visible. Darken
   only where words actually are: a band at the top for the brand line, a
   soft ellipse behind the centred question, and a foot for the video's
   lower edge. Everything between stays near the photo's own exposure. */
.cover .scrim{{background:
 linear-gradient(180deg,rgba(6,28,20,.62) 0%,rgba(6,28,20,.16) 17%,
  rgba(6,28,20,.08) 32%,rgba(6,28,20,.08) 66%,rgba(6,28,20,.22) 84%,
  rgba(6,28,20,.58) 100%),
 radial-gradient(128% 40% at 50% 50%,rgba(6,28,20,.58) 0%,
  rgba(6,28,20,.30) 58%,rgba(6,28,20,0) 100%);}}
.kicker{{align-self:flex-start;background:#c6f65a;color:#062018;font-size:30px;
 font-weight:800;letter-spacing:4px;padding:11px 26px;border-radius:999px;}}
.tail{{align-self:flex-start;font-size:34px;font-weight:700;color:#dff3e8;
 text-shadow:0 3px 14px rgba(0,0,0,.75);}}
.points{{align-self:stretch;display:flex;flex-direction:column;gap:16px;
 background:rgba(6,28,20,.66);border-left:7px solid #c6f65a;
 padding:24px 28px;border-radius:12px;}}
.point{{display:flex;gap:16px;align-items:flex-start;font-size:34px;
 font-weight:700;line-height:1.38;color:#f4fbf7;
 text-shadow:0 2px 8px rgba(0,0,0,.55);}}
.point i{{color:#c6f65a;font-style:normal;flex:none;line-height:1.38;}}
.ask{{align-self:stretch;margin-top:2px;font-family:'TL Display SC','TL Sans SC',sans-serif;
 font-size:38px;font-weight:400;line-height:1.3;color:#c6f65a;
 text-shadow:0 3px 14px rgba(0,0,0,.7);}}
/* 封面标题底下那行注。它是**注**不是副标题：字号压到标题的三分之一上下，
   颜色比标题淡一档，别把观众的眼睛从大问题上拽走。 */
.gloss{{align-self:flex-start;margin-top:-2px;font-size:34px;font-weight:700;
 letter-spacing:1px;color:#cfe6d8;text-shadow:0 2px 12px rgba(0,0,0,.85);}}
/* 赛前片的封面小字。两行之间用一道细线分开，而不是靠间距——封面底下就是
   照片，间距在深浅不一的画面上读不出「这两行是一组」。 */
.fixture{{align-self:flex-start;display:flex;flex-direction:column;gap:12px;
 margin-top:-10px;padding-left:4px;border-left:5px solid #c6f65a;
 padding-top:2px;padding-bottom:2px;}}
.fixture .when{{padding-left:16px;font-size:33px;font-weight:700;letter-spacing:1px;
 color:#dff3e8;text-shadow:0 2px 10px rgba(0,0,0,.8);}}
.fixture .who{{padding-left:16px;font-size:44px;font-weight:800;letter-spacing:2px;
 color:#f4fbf7;text-shadow:0 3px 14px rgba(0,0,0,.85);}}
</style></head><body>
<div class="slide{cover_cls}">{hero}<div class="bar"></div>
<div class="head"><div class="brandwrap">{brand_icon}<div class="brandlines"><span class="brand">网球时差 · {html.escape(column)}</span>{topic_html}</div></div></div>
<div class="copy">{chip_html}
<div class="title">{html.escape(segment.title)}</div>{gloss_html}{fixture_html}{points_html}{question_html}{tail_html}</div>
</div></body></html>"""


def render_explainer_slides(
    segments: Sequence[ExplainerSegment],
    outdir: Path,
    *,
    theme: str = "dark",
    topic: str = "",
    column: str = DEFAULT_COLUMN,
) -> list[Path]:
    """Render one image-first 3:4 card per beat via a headless Chromium page."""
    from playwright.sync_api import sync_playwright

    from ..render.webcards import _chromium_executable

    outdir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            exe = _chromium_executable()
            if not exe:
                raise
            browser = p.chromium.launch(executable_path=exe)
        try:
            for index, seg in enumerate(segments):
                page = browser.new_page(
                    viewport={"width": W, "height": H}, device_scale_factor=2
                )
                try:
                    page.set_content(
                        _slide_html(index, seg, theme=theme, topic=topic,
                                    column=column)
                    )
                    page.wait_for_function(
                        "document.fonts.status === 'loaded'", timeout=15000
                    )
                    page.wait_for_function(
                        "Array.from(document.images).every(i => i.complete)",
                        timeout=15000,
                    )
                    # JPEG，不是 PNG。卡片是**照片**铺满的 3:4 图，PNG 对它
                    # 是最坏的格式：七屏 2160×2880 存成 PNG 合计 **31 MB**，
                    # 换成 q86 的 JPEG 是 **3.9 MB**（12%），同一块文字区域
                    # 放大逐像素比过，肉眼看不出差别——2× 截图是为了字锐利，
                    # 那是**分辨率**的事，和无损编码无关。
                    #
                    # 这 31 MB 是要经 jsDelivr 发到微信里去的，国内那条链路
                    # 本来就慢；顺带也少往仓库里塞 27 MB/条（推分支吃 HTTP 413
                    # 那次就是被 mp4/jpg 的 pack 体积撑爆的）。
                    #
                    # 不能再压的两条：不缩尺寸（字会糊），q 不低于 82
                    # （深绿底上的浅色小字开始出现块状噪点）。
                    out = outdir / f"slide_{index:02d}.jpg"
                    page.screenshot(
                        path=str(out), type="jpeg", quality=_SLIDE_JPEG_QUALITY,
                        clip={"x": 0, "y": 0, "width": W, "height": H},
                    )
                    paths.append(out)
                finally:
                    page.close()
        finally:
            browser.close()
    return paths


def speakable(text: str) -> str:
    """Rewrite a narration so the TTS voice says scores the way people do.

    Written as "5-1", edge-tts reads the hyphen out loud — "五杠一" — which
    is wrong for every tennis score we have ever narrated. Scores are spoken
    "5 比 1", so convert them before synthesis rather than spelling them out
    by hand in each deck: the slides keep the compact "6-2 5-7 6-3" that
    reads well on screen, and only the audio changes.

    Year ranges must survive ("2016-2026 共十届" is not a score), so both
    sides are capped at three digits and the match must not sit inside a
    longer run of digits. A genuine "1-2 天" range would be mis-read, but no
    deck has one; scores are what this text is full of.

    The other fix is a heteronym. 挑 in 挑球 is tiāo, first tone, "to pick
    one out"; the voice reads it tiǎo, third tone, which is the 挑战 sense —
    to provoke. There is no way to hand edge-tts a pronunciation, so the
    audio gets a synonym instead: 选 means the same thing here and has only
    one reading. The slides keep 挑球, which is the word people write.

    The guard list is what stops 挑战 (challenge, and the Gentlemen's
    trophy) from turning into 选战; those really are tiǎo and are already
    read correctly.

    ### 硬地：地 是 dì，不是轻声的 de

    账号所有者 2026-08-02：「『硬地』这里的『地』是读 dì（四声）。配音要记住。」

    「硬」是形容词，于是合成器把后面的「地」当成了状语助词读成轻声 de
    （「硬地打」）。可这儿它是名词——硬地、红土、草地，是三种场地。
    这个词在这条线上到处都是（每条前瞻都要说「换到硬地」「第一个硬地决赛」），
    所以不能靠每条片子改一次文案。

    没法给 edge-tts 递音标，所以照 挑→选 那套办：**给合成器换一个同音字**，
    屏幕上仍然是「硬地」。选「帝」而不是「第」，是因为「第」强烈期待后面跟
    数字（第一、第二），「硬第决赛」这种串会让它顿一下；「帝」是个独立名词。
    **两边字数一样**，所以按字位算出来的字幕时间轴对两份都成立——这是
    这套办法能用的前提，换成三个字的词（「硬场地」）就不成立了。

    ⚠️ **这一处只能用耳朵验**：沙箱合不了语音，`words.json` 也不带声调。
    下一次 render 出来要听一遍那一句。
    """
    text = re.sub(r"挑(?![战衅拨逗剔眉])", "选", readable(text))
    return text.replace("硬地", "硬帝")


def readable(text: str) -> str:
    """旁白照着念出来的样子——给字幕用，不给 TTS 用。

    字幕要和耳朵里听到的对上，所以比分同样写成「6 比 4」。但 `speakable` 里那处
    挑→选是**给合成器纠音**的，屏幕上必须还是「挑球」。两者只差这一个字，
    字数一样，所以按字位算出来的时间轴对两边都成立。
    """
    return re.sub(r"(?<!\d)(\d{1,3})\s*[-–—−]\s*(\d{1,3})(?!\d)", r"\1 比 \2", text)


# 一行字幕最多多宽。这个数是从**左右要空出多少**倒推的，不是拍出来的：
# 小红书/抖音在右边压着点赞收藏评论那一列（约屏宽 15%），字幕横过去就被盖住。
# 所以两边各留 150px，可用 780px；一个汉字实际 46.6px（见 _ASS_CJK_RATIO），
# 16 个字 746px，加描边 752px，正好待得住。**改字号或改边距，这个数要跟着算**，见
# test_一行字幕待在左右两条边栏之间。
_SUB_MAX = 16
_SUB_SOFT = 10
_SUB_HARD_BREAK = "。！？；…"
_SUB_SOFT_BREAK = "，、：,"
# 屏幕上的字幕**不写标点**，规矩和实现全站统一放在 video/subtitle_text.py
# （账号所有者：「以后字幕里的尽量不要用标点符号，可以切换下一页表达」，
# 后来又补「字幕要应用到全局里」）。这儿只留本产线自己的两个数。
_SUB_TRIM = SUB_TRIM
_SUB_DROP = SUB_DROP
# 比这还短的一行会一闪而过（时间轴给的最短是 0.4 秒），并到邻行去。
_SUB_MIN = 5


_DIGIT = {"〇": "0", "零": "0", "一": "1", "二": "2", "三": "3", "四": "4",
          "五": "5", "六": "6", "七": "7", "八": "8", "九": "9"}
_NUM_CHARS = set(_DIGIT) | {"十", "百", "千", "两"}
# 数字后面跟着这些字，说明它是在数东西，屏幕上写成阿拉伯数字更好读。
#
# **「天」是后加的**：字幕里同一句会同时出现「8月2日」和「三天前」，
# 一半阿拉伯一半汉字，账号所有者一眼看出来（「文案里的数字都用阿拉伯数字」）。
# 「一天」不受影响——`一` 有单独的放行规则（「唯一一次」「一场首轮」那条），
# 「有一天」「一天到晚」照旧不转。
# **「号」和「点」少一个，日期就会写成半中半洋。** 2026-08-02 那条片子的
# 收尾字幕印的是「北京时间8月三号零点」——「八月」换成了数字，「三号」没换，
# 开场那句同样是「8月二号凌晨三点50分」。都出现在这条片子最要紧的两句上
# （开球时刻和决赛时刻），而它**不报错**：转换成功了，只是转了一半。
# 「点」不会误伤：「破发点」「赛点」里的「点」前面不是数字；「一点」「两点」
# 落在裸「一/两」那条豁免上。「号」顺带把「三号种子」也变成「3号种子」，那是对的。
_NUM_UNITS = "年月日天岁个位局盘场记座枚块届轮周号点"
_STRUCTURED = set("十百千")


def _num_value(run: str) -> str | None:
    """把「三十六」「四百六十九」这类读成数字。读不出来返回 None。"""
    total = part = 0
    seen = False
    for ch in run:
        if ch in _DIGIT:
            part = int(_DIGIT[ch]); seen = True
        elif ch == "两":
            part = 2; seen = True
        elif ch in ("十", "百", "千"):
            scale = {"十": 10, "百": 100, "千": 1000}[ch]
            total += (part or 1) * scale
            part = 0; seen = True
        else:
            return None
    return str(total + part) if seen else None


def arabic_numerals(text: str) -> str:
    """屏幕上的数字用阿拉伯数字——但只在它真的是个数字的时候。

    旁白里写「二〇二六」「六比四」是**给合成器定读法**的，那份不能动；
    这一步只改**显示出来的那一份**，所以放在切完行、算完时间轴之后。

    分寸都是怕改错才留的：

    - 「唯一一次」里连着两个「一」，按数字读就成了「唯 11 次」。所以裸的
      「一」「两」一律不碰，多字的串也必须含十/百/千或是四位年份才认
    - 「第二盘」「第三轮」「第一次」这类序数保持中文——「第 2 盘」读着别扭；
      但「世界第四」要写成「世界第 4」，那是个排名
    - 「七十万英镑」在「万」处收住，不然会变成 700000
    """
    def year(m: re.Match) -> str:
        return "".join(_DIGIT[c] for c in m.group(1))

    # 四位年份：一九八九、二〇二四。它们不含十/百/千，只能靠「后面跟着年」认出来。
    text = re.sub(rf"([{''.join(_DIGIT)}]{{4}})(?=年|赛季|届)", year, text)
    # 比分照数字写：六比四 → 6比4。
    # **`(?<!抢)` 不能省。** 「抢七」是个术语不是数字，而它后面常常紧跟比分：
    # 「抢七七比九」里贪婪的 `[NUM]+` 会把两个「七」一起吃掉，输出「抢7比9」——
    # 「抢七」塌成「抢」，屏幕上成了一个错字。加上这个后顾断言之后，第一个
    # 「七」不参与匹配，得到「抢七7比9」。
    # 单独的「抢七」本来就不受影响（`one()` 那一轮看见后面不是量词就不动它），
    # 所以这个 bug 只在**紧跟比分**时出现——踩到之前它一直是隐形的。
    text = re.sub(
        rf"(?<!抢)([{''.join(_NUM_CHARS)}]+)比([{''.join(_NUM_CHARS)}]+)",
        lambda m: f"{_num_value(m.group(1)) or m.group(1)}比"
                  f"{_num_value(m.group(2)) or m.group(2)}",
        text,
    )

    def one(m: re.Match) -> str:
        run, nxt = m.group(1), m.group(2) or ""
        before = text[m.start() - 1] if m.start() else ""
        value = _num_value(run)
        if value is None:
            return m.group(0)
        if nxt == "几":
            # 「十几岁」「二十几场」是**约数**，不是数。按数字写出来是「10几岁」
            # ——屏幕上看着像个没写完的数，账号所有者反馈「有些字幕没有补全」，
            # 这是其中一处（jodar-fritz 第 16 条）。
            return m.group(0)
        if before == "第" and len(run) == 1:
            return m.group(0)          # 第一次 / 第二盘 / 第三轮，序数留中文
        if set(run) & _STRUCTURED:
            return value + nxt         # 十九、三十六、四百六十九
        if len(run) > 1:
            # **裸数字连成一串，不读成一个数。** 中文里除了年份没人这么写，
            # 而年份那一轮在上面已经单独处理过了。
            #
            # 这一条是 docstring 第一段（「多字的串也必须含十/百/千」）一直
            # 缺的那半个实现，代价是**一个字被吃掉**：「生涯唯一一个巡回赛
            # 决赛」里的「一一」被 `_num_value` 读成 1，配上后面的「个」就成了
            # 「生涯唯1个」——正好是那条规矩举的「唯一一次」的例子，只是量词
            # 换了一个字就漏了过去。已经发出去的 eala-pegula 第 12 条字幕就是
            # 这个样子。
            return m.group(0)
        if run == "一" and nxt == "号" and text[m.end():m.end() + 1] == "种":
            # 「一号种子」要和同一条片子里的「7号种子」「3号种子」写成一路。
            # 半中半洋是这个仓库记过的老毛病（「北京时间8月三号零点」）。
            # 卡死在「一号种」三个字上，是为了不误伤「统一号召」这类词——
            # 裸的「一」在别处一律不碰，见下一条。
            return value + nxt
        if run in ("一", "两"):
            return m.group(0)          # 一场首轮、两盘，都不是在数数
        if nxt and nxt in _NUM_UNITS:
            return value + nxt         # 二月、五个、九记、七座
        return m.group(0)

    text = re.sub(rf"([{''.join(_NUM_CHARS)}]+)(.?)", one, text)
    # 排名是数字：世界第四 → 世界第 4。
    return re.sub(
        rf"(世界第)([{''.join(_NUM_CHARS)}]+)",
        lambda m: m.group(1) + (_num_value(m.group(2)) or m.group(2)), text,
    )


def _sub_width(text: str) -> float:
    """一行有多宽，单位是「一个汉字」。

    西文和数字窄一些，但**没有窄一半**：同字号下步进量出来是 0.59 个汉字，
    而数字还被单独放大到 78/68，所以实际是 0.68。原来按 0.5 算，「2026年4月30日」
    这种一行就会比估计的宽出小半个字。
    """
    latin = _ASS_LATIN_ADVANCE * _ASS_NUM_SIZE / _ASS_SIZE
    return sum(latin if ord(ch) < 0x2E80 else 1.0 for ch in text)


# 在这些字**之后**断开，读起来是顺的；在这些字**之前**断开也是顺的。
# 这两串是拿来兜底的：一句话里一个标点都没有、又长到必须切的时候，
# 靠它们找一个像词语边界的地方，别把「打进」「单打」「大满贯」从中间劈开。
# 和、与不在里面：一行以连词收尾，等于把话吊在半空。
_SUB_AFTER = "的了着过们是在有到后前上下里外位家员者岁军"
_SUB_BEFORE = "但而又也都就还所因然现那这其第把被让给从对向为以并却更最"
# 有边界可断时，允许把行切得短一些（6 格）；纯属数字数切的，还是要够满。
_SUB_MIN_AT_BOUNDARY = 6


def _break_bonus(text: str, i: int) -> int:
    """在 i 处断开像不像一个词语边界。-1＝绝对不能断。"""
    before, after = text[i - 1], text[i]
    if before.isspace() or after.isspace():
        return 2  # 空格两边总是安全的：「赢得 ATP／单打冠军」
    if before.isalnum() and ord(before) < 0x2E80 \
            and after.isalnum() and ord(after) < 0x2E80:
        return -1  # 西文／数字串中间不能断，「ATP」不该变成「AT／P」
    return int(before in _SUB_AFTER) + int(after in _SUB_BEFORE)


def _sub_display(chunk: str) -> str:
    """原文的一段 → 屏幕上真正画出来的那一行。

    先换阿拉伯数字（宽度会变），再去标点——顺序不能反。去标点那一步全站
    共用，见 `video/subtitle_text.py`。

    算宽度和最后取字**必须用同一份**，否则宽度判断和实际画出来的对不上，
    正是「一百→100 顶出一行」那次的翻版。
    """
    return drop_punctuation(arabic_numerals(chunk))


def _sub_len(chunk: str) -> int:
    """这一段在屏幕上有几个字（去标点之后）。"""
    return len(_sub_display(chunk))


def _best_break(text: str) -> int:
    """一句没有标点的长句该在哪儿断。返回断点字位。

    先看有没有像词语边界的地方（哪怕切出来的上一行短一点），没有才退回
    「装满为止」。反过来做过一版——先装满、边界只加一点分——切出来的是
    「代表亚洲国家的男子球员唯一一次打进大／满贯单打决赛」。
    """
    best, best_score = 0, -1e9
    for i in range(1, len(text)):
        width = _sub_width(text[:i])
        if width > _SUB_MAX:
            break
        bonus = _break_bonus(text, i)
        if bonus <= 0 and width < _SUB_SOFT:
            continue
        if width < _SUB_MIN_AT_BOUNDARY:
            continue
        score = bonus * 100 + i
        if score > best_score:
            best, best_score = i, score
    return best or min(len(text) - 1, _SUB_MAX)


def subtitle_lines(text: str) -> list[tuple[int, int, str]]:
    """把一段旁白切成一行行字幕，并记下每行在原文里的起止字位。

    先按标点切成子句，再把子句拼成不超宽的行——**断点优先落在标点上**。
    早先的版本是数满 18 个字就一刀切下去，切出来的是「代表亚洲国家打／进大满贯」
    「赢得 ATP 单／打冠军」：字数是对的，词被劈成了两半，读起来磕一下。

    字位要留着：时间轴是按「念到第几个字」算出来的，切完就丢掉位置的话，
    只能按行数平均分时间，长句短句都占一样久，字幕就会和声音脱开。
    """
    # 1) 按标点切子句，标点跟在自己那一句后面。破折号占两个字，整体留在上一行——
    #    「他自己形／容是勉强撑着」就是从这儿来的：把「——」当成普通字符跳过，
    #    这一句里就一个可断的地方都没有了。
    clauses: list[tuple[int, int]] = []
    start = i = 0
    while i < len(text):
        if text[i:i + 2] == "——":
            i += 2
            clauses.append((start, i))
            start = i
            continue
        if text[i] in _SUB_HARD_BREAK or text[i] in _SUB_SOFT_BREAK:
            clauses.append((start, i + 1))
            start = i + 1
        i += 1
    if start < len(text):
        clauses.append((start, len(text)))

    # 2) 超宽的子句自己再断，断在像词语边界的地方。
    #    宽度要按**真正画出来的那份**算，也就是换成阿拉伯数字、去掉标点之后的。
    #    汉字数字大多换完更窄，但「一百」两格换成「100」是 2.03 格——正好把
    #    一行顶出边。
    def shown_width(a: int, b: int) -> float:
        return _sub_width(_sub_display(text[a:b]))

    pieces: list[tuple[int, int]] = []
    for a, b in clauses:
        while shown_width(a, b) > _SUB_MAX:
            cut = a + _best_break(text[a:b])
            if cut <= a:
                break
            pieces.append((a, cut))
            a = cut
        if a < b:
            pieces.append((a, b))

    # 3) 一个子句就是一行——**不再把两个子句拼进同一行**。
    #    原来是「能装下就接着装」，于是「先看一眼签表。这是澳网女单签表的」
    #    这种句号夹在中间的行到处都是。停顿改由换页表达，句号就没地方待了。
    #
    #    唯一还合并的情形：短到会一闪而过的那种（「WC」「签表里」两三个字，
    #    时间轴最短只给 0.4 秒）。往后并一行，中间用空格——空格不是标点。
    #
    # ⚠️ **但绝不跨句号合并。** 上面那句「句号夹在中间的行到处都是」正是要防的
    #    东西，而这里原来只看「够不够短、装不装得下」，**根本不看隔开它们的是
    #    句号还是逗号**——于是「流程是这样的。本周三、周四」并成一行，
    #    「确认接受。没打这个电话」并成一行：**两句不同的话挤在同一屏**。
    #    账号所有者 2026-08-03：「字幕也要保持断句的完整性，不要多也不要少。」
    #
    #    句内（逗号、顿号）合并是好的——空格把停顿显出来，读起来仍是一句话；
    #    跨句合并是坏的，因为读者会把两件事读成一件。
    def _crosses_sentence(prev_end: int, nxt_start: int) -> bool:
        """上一行的末尾到下一句的开头之间，隔着句号那一档的硬断吗。"""
        return any(ch in _SUB_HARD_BREAK for ch in text[max(prev_end - 1, 0):nxt_start])

    # 唯一的例外：那一片短到**独自成行也读不到**（少于 3 个字，正是
    # `test_字幕里不写标点` 那条守卫的地板，时间轴最短只给 0.4 秒）。
    # 两条规矩真打架时让地板赢——「WC」「不打」「球员」这种两字句独占一屏会闪，
    # 比和邻句共一行更糟。而「而那时候」这种 4 个字的**句首片段**不在例外里，
    # 它正是账号所有者指出的那种「多了」：读者会看到半句话。
    _MERGE_ACROSS_SENTENCE_MAX = 2

    lines: list[tuple[int, int]] = []
    for a, b in pieces:
        too_short = (
            _sub_len(text[a:b]) < _SUB_MIN                      # 这一句太短
            or (lines and _sub_len(text[lines[-1][0]:lines[-1][1]]) < _SUB_MIN)
        )                                                       # 上一行太短
        if (
            lines
            and too_short
            and shown_width(lines[-1][0], b) <= _SUB_MAX
            and (
                not _crosses_sentence(lines[-1][1], a)
                or min(_sub_len(text[a:b]),
                       _sub_len(text[lines[-1][0]:lines[-1][1]]))
                <= _MERGE_ACROSS_SENTENCE_MAX
            )
        ):
            lines[-1] = (lines[-1][0], b)
        else:
            lines.append((a, b))

    out = []
    for a, b in lines:
        # 去标点和换阿拉伯数字都只作用在**显示的那一份**：位置 (a, b) 仍然指向
        # 原文，时间轴是拿原文的字位去对 WordBoundary 的，改完再算就对不上了。
        shown = _sub_display(text[a:b])
        if shown:
            out.append((a, b, shown))
    return out


def _boundary_marks(boundaries: Sequence[dict], text: str) -> list[tuple[int, float]]:
    """WordBoundary 事件 → [(这一刻念到原文第几个字, 秒数)]。

    edge-tts 的 offset 以 100 纳秒为单位，且已经把 rate 算进去了，直接可用。

    位置要**在原文里找**，不能靠累加事件文本的长度。事件文本里**没有标点**：
    某一段旁白 122 个非空白字，边界流只有 109 个，差的 13 个全是逗号句号。
    按累加长度算，「他自己说」在原文排第 108 位、在边界空间只排第 97 位，
    查出来的时刻晚了 1.7 秒——而且越往后漂得越多，最后一句被压成不到一秒。
    """
    marks: list[tuple[int, float]] = []
    pos = 0
    for b in boundaries:
        spoken = str(b.get("text") or "").strip()
        seconds = float(b.get("offset", 0)) / 1e7
        if not spoken:
            continue
        found = text.find(spoken, pos)
        if found < 0:
            # 合成器拿到的那份和显示的这份差一个字（挑→选的纠音）时会落到这里。
            # 保持单调，宁可沿用上一处，也别让时间轴倒退。
            found = pos
        marks.append((found, seconds))
        pos = found + len(spoken)
    return marks


def subtitle_cues(
    text: str,
    duration: float,
    *,
    boundaries: Sequence[dict] = (),
    offset: float = 0.0,
) -> list[tuple[float, float, str]]:
    """一段旁白的字幕时间轴：[(起, 止, 这一行)]。

    有 WordBoundary 就按它对齐——那是合成器自己报的时刻，最准。拿不到（有些
    声音不发这个事件）就按字数等比分配：不完美，但比没有字幕好得多，而且绝不会
    因为拿不到时间轴就整条片子没字幕。

    `offset` 是片头那段静音——画面从 0 开始，语音要到 0.6 秒才响，字幕跟着推。
    """
    lines = subtitle_lines(text)
    if not lines:
        return []
    marks = _boundary_marks(boundaries, text)
    stripped = [len(re.sub(r"\s", "", text[:i])) for i in range(len(text) + 1)]
    total = stripped[-1] or 1

    def at(char_index: int) -> float:
        if not marks:
            return duration * stripped[char_index] / total
        # 落在两个标记之间时**按字数插值**，不是沿用前一个标记的时刻。
        #
        # 原来是「取最后一个 idx ≤ char_index 的标记」。字幕改成一句一行之后
        # 行变密了，同一对标记之间经常落进两三行——它们会拿到**同一个起始时刻**，
        # 于是两条字幕在时间轴上重叠，libass 会同时画出来。
        # 边界事件本来就稀（一段 122 字的旁白只有 109 个），指望每行都正好压在
        # 一个事件上是不现实的；两端有锚点，中间按字数摊开就够准了。
        prev_idx, prev_sec = 0, marks[0][1]
        for idx, sec in marks:
            if idx > char_index:
                span = idx - prev_idx
                if span <= 0:
                    return min(prev_sec, duration)
                frac = (char_index - prev_idx) / span
                return min(prev_sec + (sec - prev_sec) * frac, duration)
            prev_idx, prev_sec = idx, sec
        # 最后一个标记之后：按剩下的字数一路摊到音频结束。
        span = len(text) - prev_idx
        if span <= 0:
            return min(prev_sec, duration)
        frac = (char_index - prev_idx) / span
        return min(prev_sec + (duration - prev_sec) * frac, duration)

    cues = []
    prev_end = 0.0
    for n, (a, b, shown) in enumerate(lines):
        # 起点不许倒退，也不许压在上一条的显示时间里——插值之后仍然可能出现
        # 两行落在同一处（同一个标记上多次命中），兜住它。
        start = max(at(a), prev_end)
        end = at(lines[n + 1][0]) if n + 1 < len(lines) else duration
        end = max(end, start + 0.4)
        cues.append((offset + start, offset + end, shown))
        prev_end = end
    return cues


def _ass_stamp(seconds: float) -> str:
    cs = max(0, int(round(seconds * 100)))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6_000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


# 字幕落在下边条里，一个像素都不压画面：3:4 的卡居中在 9:16 画布上，上下各空
# 240px。MarginV=62、字号 52，两行也只占到 190px 左右，正好待在黑边里。
# 描边留着——万一将来换成不留边的版式，字压在照片上也还读得出来。
#
# 写成 ASS 而不是 SRT，是因为**字号得有个参照系**。ffmpeg 把 SRT 转成 ASS 时
# 用的是 libass 默认的 384×288 画布，再拉到 1080×1920，字号 52 落到画面上就成了
# 三百多像素——第一帧烧出来，四个字盖住了整张卡。ASS 自己写 PlayRes，字号就是
# 真实像素，不用猜滤镜按什么缩放。
#
# WrapStyle 用 0（自动折行）而不是 2（不折行）。切行那一步已经把每行卡在 18 格
# 以内，正常不会超宽；但万一漏过一条，不折行就是**左右直接切掉**，折行只是往下
# 长一行——而字幕是上锚的，多长一行仍然离底边 240px。坏的方式要选能兜住的那种。
_ASS_FONT = "Noto Sans CJK SC"
# 字号不等于一个汉字占的宽度。libass 按字体的 ascent+descent 把字缩到「行高＝
# FontSize」，思源黑体这两项加起来是 1.46 em，所以一个汉字实际只占 FontSize/1.46。
# 量出来的：FontSize 46 时 16 个字横跨 505px（31.6px/字），字高 30px——在手机上
# 偏小，而我一直按「52px 一个字」在算行宽。**这个换算不能省**，见
# test_一行字幕待在左右两条边栏之间。
_ASS_CJK_RATIO = 1.46
_ASS_SIZE = 68                      # → 一个汉字约 46.6px，占屏宽 4.3%
# 数字和西文**单独放大**。同一个字号下，思源黑体的西文比汉字矮一截：量出来
# 数字的墨高只有汉字的 0.83（52 : 63），并排放着就像换了一种字体——其实是同一个
# 字体文件（拿成片里的「6」和 NotoSansCJK-Bold 逐像素比对过，一模一样，
# 和 DejaVu 的完全不同）。差的不是字体，是西文本来就画得小。
# 78/68 让数字墨高到汉字的 0.95，看着才是一家的。
_ASS_NUM_SIZE = 78
# 一个数字实际占多少个汉字宽（同字号下量的步进：40.1 / 68.0）。
_ASS_LATIN_ADVANCE = 0.59
_ASS_RUN = re.compile(r"[0-9A-Za-z]+")


def _ass_text(shown: str) -> str:
    """给数字和西文套上放大标记。汉字那份不动。"""
    return _ASS_RUN.sub(
        lambda m: f"{{\\fs{_ASS_NUM_SIZE}}}{m.group(0)}{{\\fs{_ASS_SIZE}}}", shown
    )
# 左右各留这么多：右边那一列是 app 的点赞/评论/分享按钮，字幕横过去就被盖住。
_ASS_MARGIN_H = 150
# 字幕待在**卡片里面**，不在画布的下边条里。
# 走过两版弯路：先是贴画布最底（MarginV=30），量出来字幕像素落在 y 1849–1882，
# 离底边只有 38px，被 app 底部文案区和 home 指示条盖住；然后把整张卡抬到
# CARD_TOP=88、字幕塞进变宽的下边条——底下是躲开了，卡片顶上那行台头又钻进了
# app 顶部的控件里。两头都有 UI，所以答案不是挪卡片，是**把卡上的文字往上收**，
# 在卡片内部腾一条出来。
#
# 上锚（Alignment=8，MarginV 从顶边算）：一行两行都从同一条线往下长，不会跳。
_ASS_ALIGN = 8
# 减 156 而不是更小：这样**两行的兜底情况**（1524+78×2=1680）也正好还在卡内。
_ASS_MARGIN_V = CARD_TOP + CARD_H - 156
# ASS 的颜色是 &HAABBGGRR：#e7f3ec → ecf3e7，深底 #141e18 → 181e14。
def _ass_header(height: int = VIDEO_H, margin_v: int = _ASS_MARGIN_V) -> str:
    """ASS 头。**画布高度和上锚位置要能换。**

    赛场之上的竖版片是 3:4（1080×1440），不是解说片的 9:16。`PlayResY` 写错，
    libass 会按它和真实画面的比例把整套坐标缩一遍，字幕整体跑位——而且不报错。
    默认值保持解说片原样，那组数是量真成片量出来的，别动。
    """
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {VIDEO_W}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, \
BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, \
BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TL,{_ASS_FONT},{_ASS_SIZE},&H00ECF3E7,&H000000FF,&H00181E14,&H00000000,\
1,0,0,0,100,100,0,0,1,3,0,{_ASS_ALIGN},{_ASS_MARGIN_H},{_ASS_MARGIN_H},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def write_subtitles(cues: Sequence[tuple[float, float, str]], path: Path,
                    *, height: int = VIDEO_H,
                    margin_v: int = _ASS_MARGIN_V) -> Path:
    lines = [
        f"Dialogue: 0,{_ass_stamp(start)},{_ass_stamp(end)},TL,,0,0,0,,"
        f"{_ass_text(shown.replace(chr(10), ' '))}"
        for start, end, shown in cues
    ]
    path.write_text(_ass_header(height, margin_v) + "\n".join(lines) + "\n",
                    encoding="utf-8")
    return path


def _filter_path(path: Path) -> str:
    """filter_complex 里的文件名要转义，冒号和反斜杠会被当成参数分隔符。"""
    return str(path).replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")


# Delivery, not just words. The old read was correct and flat — too slow to
# hold a thumb, and even-toned in a way that made every beat sound like the
# last. Yunjian is the one Chinese voice Microsoft tags "Passion" (their
# sports-commentary read); +22% is the pace it was chosen at, by ear, from
# five clips of the same paragraph — see tools/voice_sample.py, which exists
# because nobody can hear a parameter. Both stay parameters so a deck can be
# re-voiced without touching a script.
DEFAULT_VOICE = "zh-CN-YunjianNeural"
# +14% 起步 → +22% 用了一批 → +28% → 2026-08-03 降到 +10% → **定在 +22%**。
#
# 往上那几档的理由是「三个平台的平均播放时长 13–21 秒，快一点等于同样的注意力
# 里多装一句话」。**账号所有者 2026-08-03 听完 special-exempt 那条：「语速太快了」**
# ——往下调和往上调一样是编辑决定，不是调参。
#
# 实测（同一条片子、同一份 1129 字旁白，拿成片反推）：
#
#     +28%   170.0s   6.72 字/秒   ← 落在既往 +28% 三条实测的上沿（6.11/6.38/6.80）
#     +10%   212.3s   5.37 字/秒
#     +22%   —— 这一档早有 n=6 的实测，5.69–6.13，中位 5.98   ← 现在这一档
#
# ⚠️ **按比例推会推歪**：从 6.72 按 1.10/1.28 折算是 5.78，实测 5.37，差 8%。
# `tests/test_explainer_budget.py` 开头那句「换语速之后必须重量」又应验一次。
# 回到 +22% 不用重新猜——那一档是本仓库量得最扎实的一档（六条成片）。
#
# 改这个数会连带改片长：那个测试里的字数预算是拿成片反推出来的「字/秒」，
# 换了语速就得重新量，两处要一起改（一个数写两处必分叉）。
DEFAULT_RATE = "+22%"
DEFAULT_PITCH = "+0Hz"


def synthesize_narration(
    segments: Sequence[ExplainerSegment],
    outdir: Path,
    *,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
) -> list[Path]:
    """Synthesize one narration audio file per beat with edge-tts (online)."""
    try:
        import asyncio

        import edge_tts
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise ExplainerVideoError("缺少 edge-tts，请安装后再生成解说视频") from exc

    outdir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    # 走 stream() 而不是 save()，为的是顺手接住 WordBoundary——合成器自己报的
    # 「第几个字念到第几毫秒」。字幕的时间轴就是从这儿来的；save() 把它扔了。
    async def _one(text: str, path: Path) -> list[dict]:
        marks: list[dict] = []
        with path.open("wb") as fh:
            # boundary="WordBoundary" 必须显式要。edge-tts 的默认值是
            # **SentenceBoundary**，服务端就只发整句的时刻——我只收
            # WordBoundary，于是 words.json 每条都是 []。空列表和「这个声音
            # 不报边界」长得一模一样，字幕悄悄退回按字数分，看不出哪儿不对。
            # 两种都收下：真拿不到词级的时候，句级也比按字数猜准。
            stream = edge_tts.Communicate(
                text, voice, rate=rate, pitch=pitch, boundary="WordBoundary"
            ).stream()
            async for chunk in stream:
                if chunk.get("type") == "audio" and chunk.get("data"):
                    fh.write(chunk["data"])
                elif chunk.get("type") in ("WordBoundary", "SentenceBoundary"):
                    marks.append({
                        "offset": chunk.get("offset", 0),
                        "duration": chunk.get("duration", 0),
                        "text": chunk.get("text", ""),
                    })
        return marks

    for index, seg in enumerate(segments):
        path = outdir / f"voice_{index:02d}.mp3"
        try:
            marks = asyncio.run(_one(speakable(seg.narration), path))
        except Exception as exc:  # noqa: BLE001
            raise ExplainerVideoError(f"TTS 合成失败（第 {index + 1} 段）: {exc}") from exc
        if not path.is_file() or path.stat().st_size == 0:
            raise ExplainerVideoError(f"TTS 未生成音频（第 {index + 1} 段）")
        # 空列表也照写：字幕那边靠它区分「这个声音不报边界」和「还没合成过」。
        path.with_suffix(".words.json").write_text(
            json.dumps(marks, ensure_ascii=False), encoding="utf-8"
        )
        paths.append(path)
    return paths


def _audio_seconds(path: Path, ffprobe_bin: str, runner: Callable[..., object]) -> float:
    result = runner(
        [
            ffprobe_bin, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        check=True, capture_output=True, text=True,
    )
    try:
        return max(0.8, float(result.stdout.strip()))
    except (AttributeError, ValueError) as exc:
        raise ExplainerVideoError(f"无法读取音频时长: {path}") from exc


# The film used to open on the first syllable and cut on the last. Both ends
# read as a mistake — the cover has no time to be seen before someone starts
# talking, and the closing question is gone before it can be read. So hold a
# beat at each end. The tail is longer than the head on purpose: the last card
# ends on a question the viewer is meant to answer in the comments, and reading
# it takes longer than settling into a picture does.
LEAD_SILENCE = 0.6
TAIL_SILENCE = 1.5


def assemble_explainer_video(
    slides: Sequence[Path],
    audios: Sequence[Path],
    output: Path,
    *,
    captions: Sequence[str] | None = None,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
    lead_silence: float = LEAD_SILENCE,
    tail_silence: float = TAIL_SILENCE,
    runner: Callable[..., object] = subprocess.run,
) -> Path:
    """Mux each 3:4 slide over its narration, centre on a 9:16 canvas, concat."""
    if not slides or len(slides) != len(audios):
        raise ExplainerVideoError("幻灯片与音频数量不匹配")
    if shutil.which(ffmpeg_bin) is None:
        raise ExplainerVideoError(f"ffmpeg executable not found: {ffmpeg_bin}")

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    n = len(slides)
    # Padding lands on the two outer beats only. A one-beat film is both, so
    # it takes the head and the tail on the same audio stream.
    head = [lead_silence if i == 0 else 0.0 for i in range(n)]
    tail = [tail_silence if i == n - 1 else 0.0 for i in range(n)]

    command = [ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y"]
    for i, (slide, audio) in enumerate(zip(slides, audios)):
        seconds = _audio_seconds(Path(audio), ffprobe_bin, runner) + head[i] + tail[i]
        command.extend(
            ["-loop", "1", "-t", f"{seconds:.3f}", "-i", str(Path(slide).resolve())]
        )
        command.extend(["-i", str(Path(audio).resolve())])

    filters = []
    for i in range(n):
        chain = (
            f"[{2 * i}:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=decrease,"
            f"pad={VIDEO_W}:{VIDEO_H}:(ow-iw)/2:(oh-ih)/2:color={_BAND_COLOR},"
            f"setsar=1,fps=30"
        )
        # 字幕。静音刷是默认状态——旁白里的引语、数字、来龙去脉，静音的人一个字
        # 都拿不到，而卡上只放得下两三条短句。字幕烧进下边条（3:4 的卡居中在 9:16
        # 上，上下各空 240px），补的是耳朵那一份，不跟画面抢地方。
        if captions and i < len(captions) and captions[i].strip():
            words = Path(audios[i]).with_suffix(".words.json")
            try:
                marks = json.loads(words.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                marks = []
            cues = subtitle_cues(
                readable(captions[i]),
                _audio_seconds(Path(audios[i]), ffprobe_bin, runner),
                boundaries=marks,
                offset=head[i],
            )
            if cues:
                ass = write_subtitles(cues, output.parent / f"sub_{i:02d}.ass")
                chain += f",subtitles='{_filter_path(ass)}'"
        filters.append(f"{chain},format=yuv420p[v{i}]")
        # Silence the audio rather than the picture: adelay pushes the speech
        # later, apad hangs quiet on the end. The still stays on screen for the
        # whole padded length because its -t above already includes it.
        steps = []
        if head[i]:
            steps.append(f"adelay={round(head[i] * 1000)}:all=1")
        if tail[i]:
            steps.append(f"apad=pad_dur={tail[i]:.3f}")
        filters.append(
            f"[{2 * i + 1}:a]{','.join(steps)}[a{i}]" if steps
            else f"[{2 * i + 1}:a]anull[a{i}]"
        )
    concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(n))
    filters.append(f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]")

    command.extend(
        [
            "-filter_complex", ";".join(filters),
            "-map", "[outv]", "-map", "[outa]",
            # 这条片子是**静止画面的幻灯**：每屏 `-loop 1` 铺一张卡，全片唯一
            # 在动的像素是烧进去的字幕。所以给 x264 的参数按静图调，不按视频调。
            #
            # 量过的一份（wildcard，2 分 56 秒，1080×1920，原来 7.85 MB）：
            #   视频 5.75 MB / 264 kb/s     音频 2.22 MB / 102 kb/s
            #
            # · `-b:a 160k` 是给 **24 kHz 单声道**的 edge-tts 语音开的，超配两倍
            #   有余（实测编码器根本填不满，只跑到 102 kb/s）。64k 单声道对语音
            #   已经透明，省下约 750 KB
            # · `-tune stillimage` 就是给这种内容用的：放宽 deblock、加大心理
            #   视觉权重，静止区域不再逐帧掏比特
            # · crf 22 → 26：抽帧逐像素比过（示意图那屏字最密），肉眼无差别
            # · `-preset slow` 换来更小的体积；这一步在整条流水线里只占几十秒，
            #   而下载是在国内那条慢链路上发生的
            #
            # ⚠️ 别把 crf 再往上推：卡片是深绿底上的浅色小字，26 以上开始出块。
            # 改之前抽一帧放大比对，别按比例推。
            "-c:v", "libx264", "-preset", "slow", "-tune", "stillimage",
            "-crf", "26",
            "-c:a", "aac", "-b:a", "64k", "-ac", "1",
            "-movflags", "+faststart", str(output),
        ]
    )
    try:
        runner(command, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ExplainerVideoError(f"ffmpeg failed: {exc}") from exc
    if not output.is_file():
        raise ExplainerVideoError("ffmpeg completed without creating the explainer video")
    return output


def generate_explainer_video(
    story,
    outdir: str | Path,
    *,
    theme: str = "dark",
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
) -> Path:
    """End-to-end: three-beat script -> image-first slides -> narration -> MP4."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    segments = explainer_script(story)
    slides = render_explainer_slides(
        segments, outdir, theme=theme,
        topic=(_OPENINGS.get(story.slug) or {}).get("topic", ""),
        column=explainer_column(story.slug)
    )
    audios = synthesize_narration(segments, outdir, voice=voice, rate=rate, pitch=pitch)
    # Which voice actually spoke is otherwise unrecoverable from the output:
    # the per-beat mp3s are deleted to keep the repo small, and nobody can
    # read a voice name off an mp4. That gap already cost three decks — the
    # workflow passed a stale --voice on every dispatch, so changing the
    # default in code changed nothing, and the only way anyone found out was
    # by reading a run log days later. Write it down beside the film instead,
    # so checking is a matter of opening the artifact, not trusting a chain
    # of inference about what the arguments must have been.
    (outdir / "narration.json").write_text(
        json.dumps(
            {"voice": voice, "rate": rate, "pitch": pitch, "segments": len(audios),
             "subtitles": True},
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return assemble_explainer_video(
        slides, audios, outdir / "explainer.mp4",
        captions=[seg.narration for seg in segments],
    )

def explainer_push_html(
    segments: Sequence[ExplainerSegment],
    outdir: Path,
    *,
    date,
    xhs_text: str,
    video_name: str = "explainer.mp4",
    copy_url: str | None | _Unset = _UNSET,
) -> str:
    """Build the WeChat push using the knowledge post's own template.

    The explainer had a bespoke body that dropped everything the knowledge
    push had learned to carry: the 小红书 badge, the per-image "didn't load?
    open the original" fallback, the copy-title/body/comment page, the
    long-press hint. Reuse that template so both formats arrive looking like
    the same publication, and append the link to the finished video, which is
    the one thing a knowledge post does not have.
    """
    from ..render.knowledge import knowledge_push_html_from_parts

    slides = [f"slide_{i:02d}.jpg" for i in range(len(segments))]
    rel = outdir.as_posix()
    if "output/" in rel:
        rel = rel[rel.index("output/") :]
    # 视频和图片走同一条路。原来这里写的是 github.com/<repo>/raw/main/…，它 302
    # 跳到 raw.githubusercontent.com——那台机器国内既没有节点也没有 CDN，点开要等很久；
    # 而同一封推送里的图片一直是好的，因为图片走的是 jsDelivr（Cloudflare 边缘）。
    # 一封信里两条路，慢的那条是没走 CDN 的那条。
    #
    # 成片 7 MB 上下，在 jsDelivr 单文件 20 MB 的限制内，Content-Type 也确实是
    # video/mp4（试过）。写成 @main 是为了让 pin_asset_revision 顺手把它和图片
    # 一起钉到本次 commit 上：钉住之后 jsDelivr 给的是 max-age=31536000, immutable，
    # 边缘缓存一直命中；@main 只有短 TTL，而且成片被覆盖之后，老推送里的链接会
    # 指向新片子。
    video_url = f"{jsdelivr_base(_REPOSITORY)}/{rel}/{video_name}"
    # 复制页的按钮只在链接确认可达时才放进推送。**GitHub Pages 只服务 main**，
    # 特性分支上生成的包它永远取不到，按钮点开就是 404——微信那条消息发出去
    # 就收不回来。赛程那条线早就这么做了（cmd_schedule 调 live_copy_page_url），
    # 解说片这条却把 URL 硬写在这儿：cli.py 里 `live_copy_page_url` 甚至已经
    # import 了却没人用，是道装了一半的闸。
    #
    # 默认值用哨兵而不是 None：不传＝保持老行为（自己拼 URL），传 None＝
    # 调用方探过了、探不到，别放按钮。两者必须分得开，否则「没探」会被当成
    # 「探过了没有」，按钮就无声消失了——正文里那段文案的唯一出口。
    if isinstance(copy_url, _Unset):
        copy_url = f"{_PAGES_URL}/{rel}/copy.html"
    return knowledge_push_html_from_parts(
        date=date,
        image_urls=[
            f"{jsdelivr_base(_REPOSITORY)}/{rel}/{name}"
            for name in slides
        ],
        xhs_text=xhs_text,
        copy_url=copy_url,
        badge="知识解说视频",
        extra_action=(video_url, "▶ 打开 9:16 成片"),
    )


def explainer_xiaohongshu(
    story, segments: Sequence[ExplainerSegment], date_label: str
) -> str:
    """Write the Xiaohongshu caption for a finished explainer.

    Follows the daily post's shape — emoji headline, hook, the beats as
    sections, then the question and the sign-off — so a viewer who follows the
    account reads the same voice whichever format they land on. Every line
    comes from the beats themselves; nothing is invented for the caption.
    """
    closer = segments[-1]
    column = explainer_column(story.slug)
    question = closer.question or "你怎么看？"

    # Circled numerals rather than plain digits: the slides are numbered the
    # same way, so the caption reads as the same object.
    circled = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣")
    # The cover is the question, not a section — the caption already opens
    # with it, so numbering starts at the first real beat.
    beats = [seg for seg in segments if seg.kind != "cover"]
    sections = []
    for index, segment in enumerate(beats):
        marker = circled[index] if index < len(circled) else f"{index + 1}."
        bullets = "\n".join(f"· {point}" for point in segment.points)
        sections.append(f"{marker} {segment.label}：{segment.title}\n{bullets}")

    caption = _CAPTIONS.get(story.slug) or {}
    hook = caption.get("hook") or ""
    tags = " ".join(f"#{tag}" for tag in caption.get("tags") or _DEFAULT_TAGS)
    return (
        f"🎾{date_label} {column}｜{story.title}\n\n"
        + (f"{hook}\n\n" if hook else "")
        + "\n\n".join(sections)
        + "\n\n💬 留个答案\n"
        f"{question}\n\n"
        f"这里是 @网球时差｜{column}。\n\n"
        f"{tags}"
    )
