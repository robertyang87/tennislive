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
import mimetypes
import os
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
            "退赛",
            "世界第一，赛前一周退赛",
            "2026 年八月的蒙特利尔站，世界第一辛纳退赛了。他给出的说法是："
            "和团队反复权衡之后做了这个艰难的决定；错过这么重要的比赛从来都不容易，"
            "但他们相信，把健康放在第一位是对的。",
            "assets/explainer/masters-format/sinner.jpg",
            "CC BY-SA 4.0 · Wikimedia Commons · 2025 法网 辛纳",
            (
                "2026 年 8 月蒙特利尔站",
                "世界第一辛纳赛前一周退赛",
                "辛纳：把健康放在第一位",
            ),
        ),
        (
            "organiser",
            "赛事方",
            "赛事方：这已经不是个案",
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
            "西西帕斯说得更直接：大师赛变成了一种拖沓，质量明显下降，"
            "球员得不到该有的恢复和训练时间。顶尖球员的赛季跨越十一个月；"
            "蒙特利尔之后紧接着辛辛那提，再往后就是美网。"
            "加拿大网协说，正在和 ATP 商谈调整。问题也就摆在这儿了："
            "一个更长的大师赛，到底是给谁看的？",
            "assets/explainer/masters-format/tsitsipas.jpg",
            "CC BY-SA 4.0 · Wikimedia Commons · 2024 巴塞尔室内赛 西西帕斯",
            (
                "西西帕斯：变成拖沓，质量下降",
                "顶尖球员赛季跨越 11 个月",
                "加拿大网协：正在与 ATP 商谈",
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
            "第一百万张排队卡",
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
            "严到什么程度？细则写着：不得有整块色彩；彩色滚边不得超过一厘米；"
            "上衣或裙子的后背，必须完全是白的。短裤、帽子、发带、袜子，"
            "连鞋面都要以白色为主。画面里是 2023 年温网四强的冯德罗索娃——"
            "遮阳帽、球裙、袜子、球鞋，全白；鞋上那一点绿，就是规则允许的极限。",
            "assets/explainer/wimbledon-whites/headtotoe.jpg",
            "CC BY-SA 2.0 · Wikimedia Commons · 2023 温网四强 冯德罗索娃",
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
            "这不只是麻烦。生理期那几天，穿一身白站上球场，是实打实的心理负担；"
            "很长一段时间里，这件事没有人拿到台面上讲。",
            "assets/explainer/wimbledon-whites/women2023.jpg",
            "CC BY-SA 2.0 · Wikimedia Commons · 2023 温网女单四强",
            (
                "规则一度要求内衣也是白色",
                "生理期上场是实打实的负担",
                "图为 2023 年温网女单四强",
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
}


def explainer_script(story) -> list[ExplainerSegment]:
    """Return the three-beat script for a story, each beat with a hero visual.

    Hand-authored, fact-grounded scripts (with curated photos) are used when
    available; otherwise beats are derived from the story's own moments/facts
    and use the story's verified cover asset as the hero image so no beat is
    ever text-only.
    """
    scripted = _SCRIPTS.get(story.slug)
    if scripted:
        return [ExplainerSegment(*row) for row in scripted]

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


def _slide_html(index: int, segment: ExplainerSegment, *, theme: str = "dark") -> str:
    """Image-first 3:4 brand card: real photo (or schematic) hero + short caption."""
    from ..render.webcards import _font_css

    circled = ("①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨")
    number = circled[index] if index < len(circled) else f"{index + 1}"
    css = _font_css()

    icon_path = _REPO / "assets" / "logo" / "tennis-clock-icon.png"
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
        fit = (
            "background-size:contain;background-repeat:no-repeat;"
            "background-position:center 34%;"
            if wide
            else "background-size:cover;background-position:center;"
        )
        backdrop = ' class="hero diagram"' if wide else ' class="hero"'
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
    title_px = min(62, int(usable_px / max(len(segment.title), 1)))
    question_html = (
        f'<div class="ask">{html.escape(segment.question)}</div>'
        if segment.question
        else ""
    )
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
<div class="slide">{hero}<div class="bar"></div>
<div class="head"><div class="brandwrap">{brand_icon}<span class="brand">网球时差 · 网球有故事</span></div></div>
<div class="copy"><span class="chip">{number} {html.escape(segment.label)}</span>
<div class="title">{html.escape(segment.title)}</div>{points_html}{question_html}</div>
<div class="foot"><div class="tag">@网球时差 · TENNIS JETLAG</div></div>
</div></body></html>"""


def render_explainer_slides(
    segments: Sequence[ExplainerSegment],
    outdir: Path,
    *,
    theme: str = "dark",
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
                    page.set_content(_slide_html(index, seg, theme=theme))
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


def synthesize_narration(
    segments: Sequence[ExplainerSegment],
    outdir: Path,
    *,
    voice: str = "zh-CN-YunxiNeural",
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
        await edge_tts.Communicate(text, voice).save(str(path))

    for index, seg in enumerate(segments):
        path = outdir / f"voice_{index:02d}.mp3"
        try:
            asyncio.run(_one(seg.narration, path))
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


def assemble_explainer_video(
    slides: Sequence[Path],
    audios: Sequence[Path],
    output: Path,
    *,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
    runner: Callable[..., object] = subprocess.run,
) -> Path:
    """Mux each 3:4 slide over its narration, centre on a 9:16 canvas, concat."""
    if not slides or len(slides) != len(audios):
        raise ExplainerVideoError("幻灯片与音频数量不匹配")
    if shutil.which(ffmpeg_bin) is None:
        raise ExplainerVideoError(f"ffmpeg executable not found: {ffmpeg_bin}")

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    command = [ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y"]
    for slide, audio in zip(slides, audios):
        seconds = _audio_seconds(Path(audio), ffprobe_bin, runner)
        command.extend(
            ["-loop", "1", "-t", f"{seconds:.3f}", "-i", str(Path(slide).resolve())]
        )
        command.extend(["-i", str(Path(audio).resolve())])

    n = len(slides)
    filters = []
    for i in range(n):
        filters.append(
            f"[{2 * i}:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=decrease,"
            f"pad={VIDEO_W}:{VIDEO_H}:(ow-iw)/2:(oh-ih)/2:color={_BAND_COLOR},"
            f"setsar=1,fps=30,format=yuv420p[v{i}]"
        )
    concat_inputs = "".join(f"[v{i}][{2 * i + 1}:a]" for i in range(n))
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
    voice: str = "zh-CN-YunxiNeural",
) -> Path:
    """End-to-end: three-beat script -> image-first slides -> narration -> MP4."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    segments = explainer_script(story)
    slides = render_explainer_slides(segments, outdir, theme=theme)
    audios = synthesize_narration(segments, outdir, voice=voice)
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
    question = closer.question or "你怎么看？"

    # Circled numerals rather than plain digits: the slides are numbered the
    # same way, so the caption reads as the same object.
    circled = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣")
    sections = []
    for index, segment in enumerate(segments):
        marker = circled[index] if index < len(circled) else f"{index + 1}."
        bullets = "\n".join(f"· {point}" for point in segment.points)
        sections.append(f"{marker} {segment.label}：{segment.title}\n{bullets}")

    caption = _CAPTIONS.get(story.slug) or {}
    hook = caption.get("hook") or ""
    tags = " ".join(f"#{tag}" for tag in caption.get("tags") or _DEFAULT_TAGS)
    return (
        f"🎾{date_label} 网球有故事｜{story.title}\n\n"
        + (f"{hook}\n\n" if hook else "")
        + "\n\n".join(sections)
        + "\n\n💬 留个答案\n"
        f"{question}\n\n"
        "这里是 @网球时差｜网球有故事。\n\n"
        f"{tags}"
    )
