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

_SCRIPTS: dict[str, tuple[tuple, ...]] = {
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
            "真正让世界记住她的是二〇二五年的迈阿密：一张外卡，连胜奥斯塔彭科、基斯和斯瓦泰克闯进四强，"
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
_DEFAULT_TAGS = ("网球", "网球时差", "网球冷知识")
_CAPTIONS: dict[str, dict] = {
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
    "wildcard": {
        "hook": (
            "签表上那两个字母 WC，是主办方直接发的正赛资格：不看排名，也不用打资格赛。\n"
            "规则书写得很直白——一名球员能拿到几张外卡，不设任何限制。\n"
            "今年七月，一个人靠它打进温网四强；另一个人在等一张始终没等到的外卡。"
        ),
        "tags": ("网球", "网球时差", "网球规则", "郑钦文", "温网"),
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
        # 「不预测结果」是**编辑原则**，写给以后的自己看；
        # 别把它写进旁白或卡上——「比分我们不猜」这类话是在
        # 交代自己的规矩，读者不关心，白占一句的位置。
        perishable=True,
    ),
    # 和「开球之前」成对：两个名字都指一个**时刻**，不是一段时间——第一分之前，
    # 和网前那一握之后。收尾的握手是网球独有的，别的项目吹哨响铃就散了。
    #
    # 这里一度还有 First Serve / Second Serve 两个英文栏目，专收「讲一个人」的片子
    # （第一次被记住 / 又一次被记住）。设计得挺整齐，还是撤了，理由只有一条但够硬：
    # **五个栏目读者记不住**。栏目是承诺，多一个就薄一分；一个号能让人记住的承诺
    # 就两三个。撤掉时没有任何片子挂在它们名下，所以是干净的。
    #
    # 那类片子现在去哪儿：夺冠、复出、告别本身都是一场刚打完的比赛，归「握手之后」，
    # 只是讲的重心往前推到他这些年。真到了「三条都塞不进去」的那天再重开，
    # 设计和取舍都在 git 历史里，不用重想一遍。
    "握手之后": Column(
        name="握手之后",
        promise="一场刚打完的比赛，讲清它到底发生了什么、对两个人各意味着什么。",
        # 复盘不会过期：「谁赢了这场」明年也还成立。所以它不吃「必须写出比赛
        # 日期」那条硬要求——但仍然该写，理由不同：复盘会在几天后被翻出来转，
        # 读者要知道说的是哪一场。那是约定，不是测试。
        perishable=False,
    ),
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
        "image": "assets/explainer/venus-potapova/venus_serve.jpg",
        "credit": "Hameltion · CC BY-SA 4.0 · Wikimedia Commons · 2025 年 7 月华盛顿站赛前训练",
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
        fit = (
            "background-size:contain;background-repeat:no-repeat;"
            "background-position:center 34%;"
            if letterbox
            else "background-size:cover;background-position:center;"
        )
        backdrop = ' class="hero diagram"' if letterbox else ' class="hero"'
        hero = (
            f'<div{backdrop} style="background-image:url(\'{_data_uri(image_path)}\');'
            f'{fit}"></div>'
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
        title_px = min(96, int(usable_px * 2 / max(len(segment.title), 1)))
    else:
        title_px = min(62, int(usable_px / max(len(segment.title), 1)))
    question_html = (
        f'<div class="ask">{html.escape(segment.question)}</div>'
        if segment.question
        else ""
    )
    cover_cls = " cover" if cover else ""
    topic_html = f'<span class="topic">{html.escape(topic)}</span>' if topic else ""
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
.cover .title{{white-space:normal;line-height:1.24;font-weight:400;
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
</style></head><body>
<div class="slide{cover_cls}">{hero}<div class="bar"></div>
<div class="head"><div class="brandwrap">{brand_icon}<div class="brandlines"><span class="brand">网球时差 · {html.escape(column)}</span>{topic_html}</div></div></div>
<div class="copy">{chip_html}
<div class="title">{html.escape(segment.title)}</div>{points_html}{question_html}{tail_html}</div>
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
    """
    return re.sub(r"挑(?![战衅拨逗剔眉])", "选", readable(text))


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
_SUB_TRIM = "。，、：；,… "


_DIGIT = {"〇": "0", "零": "0", "一": "1", "二": "2", "三": "3", "四": "4",
          "五": "5", "六": "6", "七": "7", "八": "8", "九": "9"}
_NUM_CHARS = set(_DIGIT) | {"十", "百", "千", "两"}
# 数字后面跟着这些字，说明它是在数东西，屏幕上写成阿拉伯数字更好读。
_NUM_UNITS = "年月日岁个位局盘场记座枚块届轮周"
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
    text = re.sub(
        rf"([{''.join(_NUM_CHARS)}]+)比([{''.join(_NUM_CHARS)}]+)",
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
        if before == "第" and len(run) == 1:
            return m.group(0)          # 第一次 / 第二盘 / 第三轮，序数留中文
        if set(run) & _STRUCTURED:
            return value + nxt         # 十九、三十六、四百六十九
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
    #    宽度要按**真正画出来的那份**算，也就是换成阿拉伯数字之后的。汉字数字
    #    大多换完更窄，但「一百」两格换成「100」是 2.03 格——正好把一行顶出边。
    def shown_width(a: int, b: int) -> float:
        return _sub_width(arabic_numerals(text[a:b].strip(_SUB_TRIM)))

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

    # 3) 拼行：能装下就接着装，装不下另起一行。
    lines: list[tuple[int, int]] = []
    for a, b in pieces:
        if lines and shown_width(lines[-1][0], b) <= _SUB_MAX:
            lines[-1] = (lines[-1][0], b)
        else:
            lines.append((a, b))

    out = []
    for a, b in lines:
        # 阿拉伯数字只换**显示的那一份**：位置 (a, b) 仍然指向原文，时间轴是拿
        # 原文的字位去对 WordBoundary 的，换完再算就对不上了。数字比汉字窄，
        # 换完只会更短，不会顶出边。
        shown = arabic_numerals(text[a:b].strip(_SUB_TRIM))
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
        seconds = marks[0][1]
        for idx, sec in marks:
            if idx > char_index:
                break
            seconds = sec
        return min(seconds, duration)

    cues = []
    for n, (a, b, shown) in enumerate(lines):
        start = at(a)
        end = at(lines[n + 1][0]) if n + 1 < len(lines) else duration
        cues.append((offset + start, offset + max(end, start + 0.4), shown))
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
_ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {VIDEO_W}
PlayResY: {VIDEO_H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, \
BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, \
BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TL,{_ASS_FONT},{_ASS_SIZE},&H00ECF3E7,&H000000FF,&H00181E14,&H00000000,\
1,0,0,0,100,100,0,0,1,3,0,{_ASS_ALIGN},{_ASS_MARGIN_H},{_ASS_MARGIN_H},{_ASS_MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def write_subtitles(cues: Sequence[tuple[float, float, str]], path: Path) -> Path:
    lines = [
        f"Dialogue: 0,{_ass_stamp(start)},{_ass_stamp(end)},TL,,0,0,0,,"
        f"{_ass_text(shown.replace(chr(10), ' '))}"
        for start, end, shown in cues
    ]
    path.write_text(_ASS_HEADER + "\n".join(lines) + "\n", encoding="utf-8")
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
# +14% 起步，+22% 用了一批，现在 +28%。往上调是编辑决定，不是调参：三个平台的
# 平均播放时长是 13–21 秒，快一点等于同样的注意力里多装一句话。再往上会开始
# 吃字（云健在 +35% 上的爆破音会糊），所以停在这儿。
#
# 改这个数会连带改片长：`tests/test_explainer_budget.py` 里的字数预算是拿成片
# 反推出来的「字/秒」，换了语速就得重新量，别按比例推。
DEFAULT_RATE = "+28%"
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
            "-c:v", "libx264", "-preset", "medium", "-crf", "22",
            "-c:a", "aac", "-b:a", "160k",
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
    video_url = f"https://cdn.jsdelivr.net/gh/{_REPOSITORY}@main/{rel}/{video_name}"
    return knowledge_push_html_from_parts(
        date=date,
        image_urls=[
            f"https://cdn.jsdelivr.net/gh/{_REPOSITORY}@main/{rel}/{name}"
            for name in slides
        ],
        xhs_text=xhs_text,
        copy_url=f"{_PAGES_URL}/{rel}/copy.html",
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
