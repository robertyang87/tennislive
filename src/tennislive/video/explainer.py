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
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

# The card/image keeps the brand 3:4 (1080x1440); the video canvas is 9:16
# (1080x1920) with that 3:4 card centred on brand-colour bands.
W, H = 1080, 1440  # slide / image (3:4)
VIDEO_W, VIDEO_H = 1080, 1920  # video canvas (9:16)
_BAND_COLOR = "0x061c14"

_REPO = Path(__file__).resolve().parents[3]
_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "robertyang87/tennislive")
_PAGES_URL = os.environ.get(
    "TENNISLIVE_PAGES_URL",
    "https://{}.github.io/{}".format(*_REPOSITORY.split("/", 1)),
).rstrip("/")


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
            "完成转换；ATP 更宣布全部巡回赛全面启用电子司线。画面里这片草地上，"
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
            "人工司线，没有采用实时电子司线。画面里这把绿椅子，就是今年"
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
    "masters-format": (
        (
            "before",
            "老规矩",
            "大师赛原本一周就打完",
            "大师赛是四大满贯之下最高的一级。它原本的样子很简单：一周之内打完。"
            "但现在，九站大师赛里已经有七站改成了十二天——只剩巴黎和蒙特卡洛，"
            "还保持着一周的老规矩。画面里就是巴黎大师赛的球场。",
            "assets/explainer/masters-format/paris.jpg",
            "CC BY-SA 4.0 · Wikimedia Commons · 2024 巴黎大师赛 · Accor Arena",
            (
                "大师赛是四大满贯之下最高一级",
                "9 站里已有 7 站改成 12 天",
                "只剩巴黎、蒙特卡洛还是一周",
            ),
        ),
        (
            "expand",
            "扩容",
            "签表从 56 人扩到 96 人",
            "2025 年，加拿大站和辛辛那提站把正赛签表从五十六人扩到九十六人，"
            "赛期也随之拉长到十二天。理由不难理解：更多的比赛日，"
            "意味着更多的门票和更多的转播时段。但对球员来说，"
            "一个原本一周结束的赛事，现在要占掉将近两周。",
            "",
            "示意图 · 网球时差绘制",
            (
                "2025 年加拿大、辛辛那提扩容",
                "正赛签表从 56 人扩到 96 人",
                "赛期随之拉长到 12 天",
            ),
            _MASTERS_FORMAT_DIAGRAM,
        ),
        (
            "withdraw",
            "身体先垮",
            "5-1 领先，然后辛纳抽筋了",
            "先把时间拨回两个月前。2026 年法网第二轮，辛纳 6-3、6-2、5-1 领先，"
            "离赢下比赛只差一局。然后他抽筋了。接连丢掉十五分，场边麦克风录到"
            "他说自己头晕、没力气；最后被世界第五十六位的塞伦多洛连扳三盘淘汰，"
            "三十连胜就此终止。画面里就是那天的他。两个月后，蒙特利尔赛前一周，"
            "他退赛了，理由是把健康放在第一位。",
            "assets/explainer/masters-format/sinner.jpg",
            "rolandgarros.com 官方图 · 2026 法网第二轮 辛纳",
            (
                "2026 法网次轮，5-1 领先时抽筋",
                "连丢 15 分，30 连胜终结",
                "两个月后，他退出了蒙特利尔",
            ),
        ),
        (
            "organiser",
            "赛事方",
            "临时退赛，已经不是个案",
            "同一天，德约科维奇也退了赛；在他们之前，阿尔卡拉斯已经退了。"
            "画面里是三周前的他——温网中央球场，四分之一决赛刚刚打完，"
            "五盘，五个多小时。赛事总监瓦莱丽·泰特罗的回应是：我们尊重球员的决定，"
            "也理解在这样密集的赛程下，健康必须是第一位的。但她同时指出，"
            "这类临时退赛近年越来越频繁，已经不是某一站的问题——"
            "大师赛是巡回赛的旗舰，球迷理应看到最好的球员出场。",
            "assets/explainer/masters-format/djokovic.jpg",
            "AELTC / Jon Super · wimbledon.com 官方图 · 2026 温网 1/4 决赛",
            (
                "德约同日退赛，此前阿尔卡拉斯已退",
                "图为三周前温网 1/4 决赛，打满五盘",
                "赛事总监：临时退赛已成行业问题",
            ),
        ),
        (
            "whose",
            "谁的赛程",
            "更长的赛事，到底给谁看",
            "球员那边说得更直接。世界前列的弗里茨对 ESPN 说："
            "我一整年只有一周休息，太离谱了。顶尖球员的赛季跨越十一个月；"
            "蒙特利尔之后紧接着辛辛那提，再往后就是美网，中间几乎不停。"
            "加拿大网协说，正在和 ATP 商谈调整。而画面里这一满场人，"
            "就是蒙特利尔的中心球场。所以问题也就摆在这儿了："
            "一个更长的大师赛，到底是给谁看的？",
            "assets/explainer/masters-format/crowd.jpg",
            "CC BY-SA 2.0 · Wikimedia Commons · 蒙特利尔中心球场",
            (
                "弗里茨：我一年只有一周休息",
                "顶尖球员赛季跨越 11 个月",
                "蒙特利尔之后紧接辛辛那提、美网",
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
            "画面里是同一个人 2011 年的全套：两张排队卡、腕带，还有票——"
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
            "画面里这三位，正排在 2012 年的队伍里。",
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
            "画面里是队伍最后一段要走过的那座天桥。",
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
            "晴天一款，雨天一款；画面里这张是 1994 年的，上面写着"
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
            "画面里是清晨还没开门的温网，它站在栏杆上，把整片园子看了一遍。"
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
            "都请过它去赶鸟。画面里是同一家公司在威斯敏斯特一带的赶鸟作业。"
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
            "画面里这一只，同样是这家公司在伦敦市区放飞的猛禽。"
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
            "比规定老得多。画面里是 1920 年代的球场——那时候还没有谁强制，"
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
            "从 1963 年那份着装规定起，这条规矩就没有松过。画面里是 2023 年的"
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
            "连鞋面都要以白色为主。画面里是 2026 年温网的莱巴金娜，你可以照着条文一条条对："
            "遮阳帽白的，护腕白的，球裙白的，球鞋白的；领口那道深色细边，"
            "就是「不得超过一厘米」的那一道。整幅画面里唯一一处深色，"
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
            "画面里是 2022 年的莱巴金娜——那一年她在这片草地上夺冠；"
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
            "画面里这一幕，已经是第二天夜里：屋顶上站满了人，全世界都挤过来了。",
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
            "多撑了一会儿，到 50 比 50 时被重置。画面里这块牌子在 16 号场，"
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
            "两个人都改写了纪录。画面里是这场球的官方记分卡，一共写满了七页。",
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
            "画面里这些人，打的就是那个年代的白球。",
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
            "画面里是那天傍晚，她端着维纳斯玫瑰露水盘站上俱乐部阳台，底下站满了人。",
            "assets/explainer/ten-champions/noskova.jpg",
            "AELTC/Thomas Lovelock · wimbledon.com 官方图 · 2026 温网女单决赛后",
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
            "但真正稀奇的不是她的年龄。画面里这块底座，是维纳斯玫瑰露水盘的盘座，"
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
            "画面里就是今年的辛纳，决赛四盘拿下兹维列夫，背靠背卫冕。"
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
            "画面里是今年这两位冠军在冠军晚宴上的合影。辛纳手里那只是男单挑战杯，"
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
            "所以真正的问题从来不是屋顶有没有害人，而是——「关屋顶」，到底是谁说了算？",
            "assets/explainer/roof/roof2009.jpg",
            "Delfort · CC BY-SA 3.0 · Wikimedia Commons · 中央球场与其上方的屋顶结构",
            (
                "2025 年迪米特洛夫两盘领先，关顶中断 10 分钟",
                "复赛后胸肌撕裂退赛，连续第五届大满贯退赛",
                "教练德尔加多：转室内不是受伤原因",
            ),
            "",
            "「关屋顶」是谁说了算？",
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
            "手里只留两个。画面里这两个人，就是这笔交易的双方。快得没人解说，主播也不提，"
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
            "他们盯着看的是这个。画面里是温网 2026 年的比赛用球，Slazenger 的字样、赛事名和年份"
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
            "把下一分想清楚的时间。画面里这位球童蹲在网边，等的是同一段时间。"
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
            "画面里这把椅子还在原地，只是那二十五秒已经不归它管了。",
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
            "真正让世界记住她的是二〇二五年的迈阿密：一张外卡，连胜奥斯塔片科、基斯和斯瓦泰克闯进四强，"
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
            "这一边",
            "亚洲第一块网球单打奥运金牌",
            "另一边这位，不用多介绍。二〇二四年巴黎，郑钦文拿下女单金牌，"
            "成为亚洲第一位赢得奥运网球单打金牌的球员。她的生涯最高排名是世界第四，"
            "二〇二五年六月达到——继李娜之后，中国第二位进入女单前五的球员。"
            "在那之前，她还拿过二〇二四年澳网亚军和同年年终总决赛亚军。"
            "画面里这一张，就是她赢下金牌那一刻躺在红土上的样子。"
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
            "战胜同胞朱琳拿下金牌。画面就是那一届的赛后——郑钦文和朱琳一起举起国旗，"
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
            "比分我们不猜，只把一句话留在这儿——祝钦文好运，也期待她早日重回巅峰。",
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
}


@dataclass(frozen=True)
class Column:
    """A named strand of the account, printed on every card it produces.

    A column is a promise, not a decoration: the reader who sees 网球有故事
    expects something that will still be true next year, and the one who sees
    开赛之前 expects a match that has not started yet. Mixing them costs the
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
    "开赛之前": Column(
        name="开赛之前",
        promise="一场还没开打的比赛，把两边这几年的来路摆在一起；不猜比分。",
        perishable=True,
    ),
    # 和「开赛之前」成对：两个名字都指一个**时刻**，不是一段时间——第一分之前，
    # 和网前那一握之后。收尾的握手是网球独有的，别的项目吹哨响铃就散了。
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
        "column": "开赛之前",
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
        hero = (
            '<div class="hero diagram"></div>'
            f'<div class="diagram-wrap">{segment.diagram or _HAWKEYE_DIAGRAM}</div>'
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
.diagram-wrap{{position:absolute;left:0;right:0;top:250px;display:flex;justify-content:center;}}
.diagram-wrap svg{{width:760px;height:auto;}}
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
.copy{{position:absolute;left:70px;right:70px;bottom:120px;z-index:5;
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
                    out = outdir / f"slide_{index:02d}.png"
                    page.screenshot(
                        path=str(out), clip={"x": 0, "y": 0, "width": W, "height": H}
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
    text = re.sub(r"(?<!\d)(\d{1,3})\s*[-–—−]\s*(\d{1,3})(?!\d)", r"\1 比 \2", text)
    return re.sub(r"挑(?![战衅拨逗剔眉])", "选", text)


# Delivery, not just words. The old read was correct and flat — too slow to
# hold a thumb, and even-toned in a way that made every beat sound like the
# last. Yunjian is the one Chinese voice Microsoft tags "Passion" (their
# sports-commentary read); +22% is the pace it was chosen at, by ear, from
# five clips of the same paragraph — see tools/voice_sample.py, which exists
# because nobody can hear a parameter. Both stay parameters so a deck can be
# re-voiced without touching a script.
DEFAULT_VOICE = "zh-CN-YunjianNeural"
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

    async def _one(text: str, path: Path) -> None:
        await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(path))

    for index, seg in enumerate(segments):
        path = outdir / f"voice_{index:02d}.mp3"
        try:
            asyncio.run(_one(speakable(seg.narration), path))
        except Exception as exc:  # noqa: BLE001
            raise ExplainerVideoError(f"TTS 合成失败（第 {index + 1} 段）: {exc}") from exc
        if not path.is_file() or path.stat().st_size == 0:
            raise ExplainerVideoError(f"TTS 未生成音频（第 {index + 1} 段）")
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
        filters.append(
            f"[{2 * i}:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=decrease,"
            f"pad={VIDEO_W}:{VIDEO_H}:(ow-iw)/2:(oh-ih)/2:color={_BAND_COLOR},"
            f"setsar=1,fps=30,format=yuv420p[v{i}]"
        )
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
            {"voice": voice, "rate": rate, "pitch": pitch, "segments": len(audios)},
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return assemble_explainer_video(slides, audios, outdir / "explainer.mp4")

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

    slides = [f"slide_{i:02d}.png" for i in range(len(segments))]
    rel = outdir.as_posix()
    if "output/" in rel:
        rel = rel[rel.index("output/") :]
    video_url = f"https://github.com/{_REPOSITORY}/raw/main/{rel}/{video_name}"
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
