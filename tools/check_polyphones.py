#!/usr/bin/env python3
"""多音字预检：换字表（`video/pronounce.py`）管不到的多音字，出片之前列出来。

账号所有者 2026-09-27：「配音 tts 里的多音字最好在生成语音时候替换成同音的字」。
换字表只收**量过**的词；新片子里冒出来的新词，这一步把它们拦在出片前。

    python3 tools/check_polyphones.py --slug <slug>            # 静态，零点几秒，不联网
    python3 tools/check_polyphones.py --slug <slug> --measure  # 真合成器逐处比对（要联网）

**静态那一半**（`render --dry-run` 和采访片每一趟开头印的就是它，只报不拦）：对每一段
要喂给合成器的旁白，逐字找「这儿的读音不是这个字两个常用读音里的任何一个」的多音字
（常用＝pypinyin 单字默认读音 ＋ 词组库里最多的那个，见 `poly_info`），扣掉换字表已经
换掉的、量过读对的（`MEASURED_OK`）、落在词典词里且词典给的正是这个读音的（只计数），
剩下的列出来。「这儿的读音」按 pypinyin 的词组切分 ＋ 下面手校过的 `INTENDED` 规则。
**这是代理，不是合成器本身**：pypinyin 说对的，合成器未必对（长回合 这一类默认读音
也会被读错，静态这一半看不见）——所以还有另一半。2026-09-27 扫全库 469 条片子
（赛场之上／采访 spec ＋ 解说片 slug）报 10 处（第一版 2349 处，条条都红没人读，见 `poly_info`）。

**量的那一半**（`--measure`，要联网、一处十几秒）：逐处拿 `tools/measure_polyphone.py`
比对（同一把嗓子念「原句」「换成只有对的读音的字」「换成只有错的读音的字」，比那一个
音节）；读错的顺手量换字候选，读对的那个印成一行能直接抄进 `pronounce.HOMOPHONES` 的
表项。校准数据在那个工具的 docstring。

⚠️ 「列出来」不等于「读错了」：静态一半报的是**风险**。真要知道读没读错，跑 `--measure`。

生产任务必须安装轻量 pypinyin 并运行独立 CLI；缺依赖的 CLI 返回2，不能当成功。
可选 dry-run 提示仍只报不拦，但「这趟没查」绝不是已覆盖。静态正确与声学正确是
两种证据；发布前仍须对实际嗓音、语速的封面、所有旁白和片尾逐段声学复核。
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import shlex
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from tennislive.video import pronounce  # noqa: E402

#: 生产里的语速：赛场之上 +6%（match-reel.yml），解说片／采访卡 +22%（explainer.DEFAULT_RATE）。
REEL_RATE = "+6%"
STORY_RATE = "+22%"
VOICE = "zh-CN-YunjianNeural"

# ---------------------------------------------------------------------------
# 这个字在这儿该读什么：pypinyin 的词组读音打底，下面这些手校规则覆盖它。
# 每条都拿全库语料里的真上下文对过（2026-09-27 普查），不是凭记忆写的规则。
# (正则，里面恰好一个单字捕获组；TONE3 读音)。按顺序套，后面的覆盖前面的。
# ---------------------------------------------------------------------------
INTENDED: tuple[tuple[str, str], ...] = (
    # 场：比赛量词 chǎng；雨、病、梦 cháng
    (r"(场)", "chang3"),
    (r"(场)(?=雨|大雨|暴雨|病|大病|梦|噩梦|空|误会|虚惊)", "chang2"),
    # 长：形容词 cháng；首长、生长 zhǎng
    (r"(长)", "chang2"),
    (r"(?<=[队判年成增家校部院局会组班社市省州首师兄学生助滋])(长)", "zhang3"),
    (r"(长)(?=这样|什么样|成|大|相)", "zhang3"),
    # 重：再一次 chóng
    (r"(重)(?=做|演|发|来|打|回|返|拾|置|逢|算|合|新|复|赛|播|启|开|写|选|排|建|组|夺|现|燃"
     r"|申|审|判|考|修|制|振|整|蹈)", "chong2"),
    # 得：必须 děi
    (r"(?<=[还就总都也先])(得)(?=再|留|交|跟|排|为|承|从|走|打|重|看|自己|有|去|加|先|等)", "dei3"),
    (r"(?<=[你我他她它])(得)(?=[再先去把])", "dei3"),
    (r"(?<=队)(得)(?=赢)", "dei3"),
    (r"(?<=[，。？！])(得)(?=先)", "dei3"),
    (r"(?<=总)(得)(?=分)", "de2"),
    (r"(?<=夺)(得)", "de2"),
    # 着：够得着 zháo
    # Python 的 re 不收变宽的后顾，拆成几个定宽的
    (r"(?:(?<=够)|(?<=够不|够得|摸不|摸得|碰不|碰得|睡不|睡得|找不|用不|犯不|顾不|挨不))(着)",
     "zhao2"),
    (r"(着)(?=地)", "zhao2"),
    # 冲：朝着 chòng
    (r"(冲)(?=着|他|她|我|你|对方|观众|看台)", "chong4"),
    # 倒：摔倒 dǎo
    (r"(倒)(?=在|下|地|向)", "dao3"),
    (r"(?<=[扑摔躺滑压跌击推绊累病撂])(倒)", "dao3"),
    # 中：打中 zhòng
    (r"(?<=[打砸击命射连猜])(中)", "zhong4"),
    (r"(?<=[一二三四五六七八九十])(中)(?=[一二三四五六七八九十零])", "zhong4"),
    (r"(中)(?=标)", "zhong4"),
    # 间：中间隔着 jiān
    (r"(?<=中)(间)(?=隔)", "jian1"),
    # 空：腾出 kòng
    (r"(空)(?=出|着|位|缺|白|当|档|额|隙|闲)", "kong4"),
    (r"(?:(?<=早就|已经)|(?<=就真的))(空)", "kong4"),
    # 差：时差、差距 chā
    (r"(?<=[时分落误相])(差)", "cha1"),
    (r"(?<=时间)(差)", "cha1"),
    (r"(差)(?=[异距别值额])", "cha1"),
    # 数：数一数 shǔ
    (r"(数)(?=了一遍|到|一数|数)", "shu3"),
    (r"(?<=往前|往回|倒着|心里)(数)", "shu3"),
    (r"(?<=一年)(数)(?=十)", "shu3"),
    # 背：背着 bēi
    (r"(背)(?=着|起|包)", "bei1"),
    (r"(?<=直)(奔)", "ben4"),
    (r"(?<=补)(给)", "gei3"),
    (r"(?<=强)(劲)", "jing4"),
    (r"(?<=也)(薄)", "bao2"),
    (r"(露)(?=怯|一手)", "lou4"),
    (r"(散)(?=了|开|去|不掉)", "san4"),
    (r"(削)(?=球)", "xiao1"),
    # 挑：挑高球、挑起、挑回 tiǎo（换字表不换它；量过原样读 tiāo——见 REWRITE_ONLY）
    (r"(挑)(?=高|起|回)", "tiao3"),
    (r"(?<=连轴)(转)", "zhuan4"),
    # --- 人名、译名 ---
    (r"(曾)(?=丽美|俊欣)", "zeng1"),
    (r"(?<=[费比哈库万卜杜])(勒)", "le4"),
    (r"(勒)(?=纳|孔特|普)", "le4"),
    (r"(塞)(?=蒂|伦多|卡|娃|尔|浦|内|维|拜|巴|纳|罗|戈|克|斯|拉)", "sai4"),
    (r"(?<=卢)(塞)", "sai4"),
    (r"(?<=[烈费巴瓦克延季])(耶)", "ye1"),
    (r"(?<=盖里)(耶)", "ye1"),
    (r"(什)(?=维利|金|卡|科娃|拉姆)", "shi2"),
    (r"(?<=巴西拉)(什)", "shi2"),
    (r"(?<=格)(乐)", "le4"),
    # V得 的补语标记：轻声 de
    (r"(?<=[打拿守写拼收差数追挡扛看回进够来赢做走跑说变显过觉记值懂舍])(得)"
     r"(?=很|太|更|最|真|非常|不|并|下|住|了|起|过|上|动|清|明|漂|干|好|快|慢|多|少|凶|狠"
     r"|稳|满|远|早|晚|也|这么|那么|去|见|着|到|出|比|相当|有点|一点)", "de5"),
    (r"(?<=比分)(为)", "wei2"),
    (r"(?<=了)(地)", "di4"),
    (r"(?<=在)(地)", "di4"),
    (r"(?<=塞)(缪)", "miu4"),
    (r"(朴)(?=素贤|恩|志|成|敏|宰|世|智|秀)", "piao2"),
    (r"(勒)(?![紧住死脖着进])", "le4"),
    (r"(?<=阿)(什)(?!么)", "shi2"),
    (r"(拽)", "zhuai4"),
    (r"(场)(?=硬仗|大战|恶战|鏖战|拉锯战|复仇之战)", "chang2"),
    (r"(?<=[，。？！；：—])(得)(?![分到了出])", "dei3"),
    (r"(?<=仍然|依然|还是|只能|总是|必须)(得)", "dei3"),
)

#: 译名的惯例读音：命中译名表里的名字时，名字里这几个字一律按这个读。
NAME_CHAR_READING = {"勒": "le4", "塞": "sai4", "耶": "ye1", "什": "shi2",
                     "舍": "she4", "缪": "miu4"}

#: 读音两可、词典和口语分叉的位置——报的时候标一句「口径题」，别当错读去换。
UNCERTAIN = (
    # 「这一栏已经空了十年」：kōng（空无）和 kòng（空缺）两可；合成器读 kōng
    # （2026-09-27 +22% 与「箜」相同 0.0）。读哪个是编辑的事，不是换字表的事。
    r"(?:(?<=早就)|(?<=已经))(空)(?=了)",
    r"(场)(?=硬仗|大战|恶战|鏖战|拉锯战|复仇之战)",
    r"(当)(?=天|年|晚)",
)

#: **量过读错、换字表又没有能换的字**的位置：只能改写句子，逐条提醒（不再当「风险」
#: 让人去 `--measure`——已经量过了）。
#: 2026-09-27 量的：「把球挑回底线」原样喂给合成器读 tiāo（与 祧/佻 相同 0.003），
#: 要的是 tiǎo；tiǎo 那头找不到读音稳定的单音字（窕/朓 自测不过）。换字表的 挑→选
#: 原来会把这几处换成「选」（成了另一个词），同日整条拿掉了，读音偏的问题还在——
#: 改写句子（「把球挑回底线」→「把球高高吊回底线」之类）是作者的事。
REWRITE_ONLY = (
    (r"挑(?=[高起回])", "挑高球／挑起／挑回 的「挑」是 tiǎo，原样喂给合成器量过读成 tiāo，"
                        "换字表没有能换的字——这一句换个说法"),
)

# 量过读对的词（2026-09-27 三批普查，measure_polyphone，云见 +6%/+22%）：
# 预检不再报它们。值是 (字, 读音, 一句证据)。只收「原句本来就读对」的——
# 读错的在换字表里，不在这儿。
MEASURED_OK: dict[str, tuple[str, str, str]] = {
    "时差": ("差", "chā", "片尾「关注网球时差」与 插/叉 调形 0.68/0.79"),
    "安德烈耶娃": ("耶", "yē", "与「椰」共振峰和 F0 相同"),
    "恰拉耶娃": ("耶", "yē", "F0 与 椰/掖 0.41~0.58"),
    "日延巴耶娃": ("耶", "yē", "correct/medium"),
    "季莫费耶娃": ("耶", "yē", "correct/medium"),
    "鲁瓦耶": ("耶", "yē", "correct/medium"),
    "克耶高斯": ("耶", "yē", "correct/medium"),
    "盖里耶里": ("耶", "yē", "correct"),
    "穆塞蒂": ("塞", "sài", "离 赛 0.75，离 sè/sāi 2.7"),
    "伊万尼塞维奇": ("塞", "sài", "与 赛 共振峰 0.011"),
    "巴塞罗那": ("塞", "sài", "F0 与 赛 0.04"),
    "巴塞尔": ("塞", "sài", "元音轨迹 ai 不是 e"),
    "塞缪尔": ("塞", "sài", "与 赛 相同 0.011~0.014"),
    "丰塞卡": ("塞", "sài", "correct"),
    "普汀塞娃": ("塞", "sài", "correct"),
    "兰达卢塞": ("塞", "sài", "correct"),
    "塞伦多洛": ("塞", "sài", "correct/medium"),
    "塞尔维亚": ("塞", "sài", "correct/medium"),
    "塞莱斯": ("塞", "sài", "correct/high"),
    "塞拉利昂": ("塞", "sài", "correct/medium"),
    "费德勒": ("勒", "lè", "与 叻/乐 相同 0.00"),
    "比勒尔": ("勒", "lè", "共振峰 e 下降，同 乐/泐"),
    "哈勒普": ("勒", "lè", "correct"),
    "勒纳": ("勒", "lè", "correct/high"),
    "泰勒": ("勒", "lè", "correct/medium"),
    "阿什": ("什", "shí", "与 实 F0 0.035"),
    "巴图什科娃": ("什", "shí", "离 实十时 1.8，离 神 3.8"),
    "瓦舍罗": ("舍", "shè", "correct"),
    "舍甫琴科": ("舍", "shè", "correct"),
    "特日格乐": ("乐", "lè", "correct/medium"),
    "布云朝克特": ("朝", "cháo", "F0 与 嘲 0.85~0.96，离 招昭 2.5~4.8"),
    "曾祖父": ("曾", "zēng", "correct/low"),
    "曾丽美": ("曾", "zēng", "correct/medium"),
    "总得分": ("得", "dé", "离 德 1.1，离 的 2.8"),
    "夺得": ("得", "dé", "correct/low"),
    "先得": ("得", "děi", "共振峰 ei 上滑，同「内」"),
    "够不着": ("着", "zháo", "共振峰 ao，同 找/沼"),
    "找不着北": ("着", "zháo", "共振峰 ao，同 找/沼"),
    "没够着": ("着", "zháo", "correct"),
    "够得着": ("着", "zháo", "correct"),
    "重发": ("重", "chóng", "correct/medium 两种语速"),
    "重新": ("重", "chóng", "F0 上升同 崇"),
    "重回": ("重", "chóng", "correct"),
    "重来": ("重", "chóng", "correct"),
    "重置": ("重", "chóng", "correct"),
    "重拾": ("重", "chóng", "correct/medium"),
    "重打": ("重", "chóng", "「这一分要重打」correct/high"),
    "倒在": ("倒", "dǎo", "correct/medium"),
    "滑倒": ("倒", "dǎo", "correct"),
    "扑倒": ("倒", "dǎo", "correct"),
    "空当": ("空", "kòng", "离 控 2.0，离 箜崆 6.1"),
    "空档": ("空", "kòng", "correct"),
    "空位": ("空", "kòng", "与 控 相同 0.0"),
    "连轴转": ("转", "zhuàn", "correct/medium"),
    "登场": ("场", "chǎng", "与 厂 0.44"),
    "外场": ("场", "chǎng", "correct"),
    "整场": ("场", "chǎng", "correct/medium"),
    "第一场": ("场", "chǎng", "correct/high"),
    "下一场": ("场", "chǎng", "correct"),
    "一场场": ("场", "chǎng", "correct"),
    "更长": ("长", "cháng", "与 常 相同 0.00"),
    "长裙": ("长", "cháng", "与 肠 0.29"),
    "长凳": ("长", "cháng", "与 肠/常 相同"),
    "太长": ("长", "cháng", "与 常 相同 0.00"),
    "最长": ("长", "cháng", "correct"),
    "还长": ("长", "cháng", "correct"),
    "很长": ("长", "cháng", "correct/medium"),
    "越长": ("长", "cháng", "correct/high"),
    "打长": ("长", "cháng", "correct/medium"),
    "长文": ("长", "cháng", "correct/medium"),
    "背起": ("背", "bēi", "F0 平，同 杯悲碑"),
    "背着": ("背", "bēi", "F0 平，同 杯悲碑"),
    "冠军": ("冠", "guàn", "与 贯 0.30"),
    "夺冠": ("冠", "guàn", "与 贯 相同 0.007"),
    "切削": ("削", "xiāo", "correct/medium"),
    "差距": ("差", "chā", "correct/medium"),
    "分差": ("差", "chā", "correct"),
    "时间差": ("差", "chā", "correct/medium"),
    "调整": ("调", "tiáo", "correct/high"),
    "挑战": ("挑", "tiǎo", "correct/medium"),
    "挑衅": ("挑", "tiǎo", "correct"),
    "直奔": ("奔", "bèn", "correct"),
    "率先": ("率", "shuài", "correct"),
    "坦率": ("率", "shuài", "correct"),
    "应对": ("应", "yìng", "correct"),
    "中间隔着": ("间", "jiān", "correct/medium（中间｜隔着）"),
    "补给": ("给", "gěi", "correct/low"),
    "盘间": ("间", "jiān", "correct/high"),
    "还击": ("还", "huán", "correct/medium"),
    "主角": ("角", "jué", "与 决 0.03"),
    "拽": ("拽", "zhuài", "correct/low"),
    "七中一": ("中", "zhòng", "切成 七｜中｜一 时读对（换字表照样换成 众，仍读对）"),
    "冲他": ("冲", "chòng", "correct/low"),
    "要重": ("重", "chóng", "correct/high"),
    "为六比": ("为", "wéi", "correct"),
    # 2026-09-27 收口时补量的（云见，measure_polyphone）：
    "数到": ("数", "shǔ", "「转播数到第三个赛点」+6% correct/high，与「署」相同 0.092"),
    "拆了重做": ("重", "chóng", "+6% correct/high，与「崇」相同 0.038（拆开重做 才读错，见换字表）"),
    "就得重做": ("重", "chóng", "+22% correct/medium"),
    "冲着": ("冲", "chòng", "「冲着看台」+6% correct/low（0.225）；普查那轮三句 uncertain、调形偏 chòng"),
    "砸中": ("中", "zhòng", "「水瓶砸中了头」+6% correct/low（0.277）；普查那轮 uncertain、F0 下降同「众」"),
}

# 旧记录明确给过原句的，只认可该原句；不能把一次正确推广到这个词的
# 所有句子。没有保存完整原句的旧条目仍是低噪声静态筛选资料，不是声学凭证。
# 不补造未留存的测量语境。这里只忽略句末标点；逗号、前后措辞必须相同。
# 「要重」是旧的重字免检旁路，也必须跟「重打」一起收窄。
MEASURED_OK_CONTEXTS: dict[str, tuple[str, ...]] = {
    "时差": ("关注网球时差",),
    "重打": ("这一分要重打",),
    "要重": ("这一分要重打",),
    "数到": ("转播数到第三个赛点",),
    "冲着": ("冲着看台",),
    "砸中": ("水瓶砸中了头",),
}


def _sentence_at(text: str, index: int) -> tuple[str, int]:
    start = max(text.rfind(p, 0, index) for p in "。？！；") + 1
    ends = [x for x in (text.find(p, index) for p in "。？！；") if x >= 0]
    end = min(ends) + 1 if ends else len(text)
    return text[start:end], index - start


def _context_key(text: str) -> str:
    return text.strip().rstrip("。？！!?；;")


def _context_matches(word: str, text: str, index: int) -> bool:
    contexts = MEASURED_OK_CONTEXTS.get(word)
    return contexts is None or _context_key(_sentence_at(text, index)[0]) in contexts

#: 历史「字＋读音」资料：没有观察到错读不等于未来所有句子都正确。
#: 得 děi 没有只读 děi 的参考字，声学比对只能拿近似字代理（结论最多 low），
#: 所以看的是共振峰：「得自己倒贴」「还得再守」「先得有」三句 F2 都升到 ~1950 Hz
#: （ei，同 垒/磊/内），没有一句像「德」（dé，F2 平在 1300~1550）。
#: 原来按整类免检；现在只认可下面保留的三个原语境，新句子明确待测。
MEASURED_OK_READINGS: dict[tuple[str, str], str] = {
    ("得", "dei3"): "三句共振峰都是 ei（2026-09-27，+6%/+22%），没有一句读成 dé",
}
MEASURED_OK_READING_CONTEXTS: dict[tuple[str, str], tuple[str, ...]] = {
    ("得", "dei3"): ("得自己倒贴", "还得再守", "先得有"),
}


def _reading_context_ok(text: str, index: int, char: str, reading: str) -> bool:
    contexts = MEASURED_OK_READING_CONTEXTS.get((char, reading), ())
    return _context_key(_sentence_at(text, index)[0]) in contexts


@dataclass
class Spoken:
    """一段要喂给合成器的旁白。`text` 是**显示那份**（`readable()` 之后）。"""
    label: str
    text: str
    rate: str


@dataclass
class Risk:
    label: str
    text: str            # 显示那份（整段）
    index: int           # 多音字在 text 里的字位
    char: str
    word: str            # 它所在的词（pypinyin 的词组切分）
    intended: str        # TONE3
    default: str         # TONE3：这个字「不看上下文」会被读成的那个（单字默认读音）
    others: list[str]    # 其余活着的读音（TONE3）
    rate: str
    lexicon: bool        # 所在的词是词典词、词典给的正是这个读音（报告里只计数）
    uncertain: bool = False
    measured: dict = field(default_factory=dict)
    context_recheck: bool = False

    def sentence(self) -> tuple[str, int]:
        """这一处所在的那一句（显示那份）和它在句子里的字位。"""
        return _sentence_at(self.text, self.index)


# ---------------------------------------------------------------- pypinyin
_HAN = re.compile(r"[㐀-鿿]+")
_SANDHI = set("一不")
_FREE = set("谁这那哪")
_EXTRA_LIVE = {"地": ["de5"], "朝": ["zhao1"], "曾": ["zeng1"], "耶": ["ye1"],
               "勒": ["le4"], "塞": ["sai4"], "什": ["shi2"], "单": ["shan4"],
               "解": ["xie4"], "区": ["ou1"], "盖": ["ge3"], "覃": ["qin2"],
               "仇": ["qiu2"], "员": ["yun4"], "尉": ["yu4"], "乐": ["yue4"],
               "查": ["zha1"], "奔": ["ben4"], "背": ["bei1"], "着": ["zhao2"],
               "得": ["dei3"]}


@lru_cache(maxsize=1)
def _phrase_readings_raw() -> dict[str, collections.Counter]:
    """词组库里每个字各读音出现几次（带调号的原样读音）。

    ⚠️ 只数不转：第一版在这儿对 12 万个字逐个 `to_tone3`，一趟 5.6 秒——
    `--dry-run` 本来 0.2 秒，不能为一行只报不拦的提示白等 5 秒。转成 TONE3
    挪到 `_phrase_readings(ch)`，只转真被问到的那几个字。
    """
    from pypinyin.constants import PHRASES_DICT
    out: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for w, rs in PHRASES_DICT.items():
        if len(w) == len(rs):
            for ch, r in zip(w, rs):
                out[ch][r[0]] += 1
    return out


@lru_cache(maxsize=None)
def _phrase_readings(ch: str) -> collections.Counter:
    from pypinyin.contrib.tone_convert import to_tone3
    out: collections.Counter = collections.Counter()
    for r, n in _phrase_readings_raw().get(ch, {}).items():
        out[to_tone3(r, neutral_tone_with_five=True)] += n
    return out


@lru_cache(maxsize=None)
def poly_info(ch: str) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
    """(是不是多音字, 算「常用」的读音, 活着的读音)。冷僻读音（词组库里不到 3 次）不算。

    「常用」是**两个**：pypinyin 的单字默认读音（`PINYIN_DICT` 第一个——不看上下文
    就会念成它），和词组库里这个字出现得最多的读音。只拿一个当基准，第一版扫全库
    307 条 spec 报了 2349 处、302 条条条有份：拿词组库计数，「只 zhǐ」「都 dōu」
    「还 hái」「给 gěi」「娜 nà」全成了「非常用」（词组库里 一只/首都/归还/供给/婀娜
    占多数）；拿单字默认，「长 cháng」「空 kōng」又全成了。两个都不是才报：
    同一批 spec 降到 38 处，剩下的是 得(děi) 冲(chòng) 中(zhòng) 场(cháng) 这一类
    ——**一条条条都红的提示没人读**（「判据宁可窄，不可宽」）。"""
    from pypinyin.constants import PINYIN_DICT
    from pypinyin.contrib.tone_convert import to_tone3
    raw = PINYIN_DICT.get(ord(ch))
    hs = [to_tone3(x, neutral_tone_with_five=True) for x in raw.split(",")] if raw else []
    ph = _phrase_readings(ch)
    live = hs[:1]
    for r in hs[1:] + [r for r, _ in ph.most_common()]:
        if ph[r] >= 3 and r not in live:
            live.append(r)
    for r in _EXTRA_LIVE.get(ch, []):
        if r not in live:
            live.append(r)
    base = lambda r: r.rstrip("12345")  # noqa: E731
    real = [r for r in live if not (r.endswith("5") and any(
        base(o) == base(r) and o != r for o in live))]
    defaults = tuple(dict.fromkeys(
        x for x in (hs[0] if hs else None, ph.most_common(1)[0][0] if ph else None) if x))
    is_poly = ch not in _SANDHI and ch not in _FREE and len(set(real)) >= 2
    return is_poly, defaults, tuple(live)


@lru_cache(maxsize=1)
def _compiled_intended() -> tuple[tuple[re.Pattern[str], str], ...]:
    return tuple((re.compile(p), r) for p, r in INTENDED)


@lru_cache(maxsize=1)
def _name_parts() -> tuple[str, ...]:
    """译名表里的名字（≥2 个汉字），长的在前。"""
    names: set[str] = set()
    try:
        from tennislive.zh.players import PLAYER_ZH
        from tennislive.zh.tournaments import TOURNAMENT_ZH
        vals = list(PLAYER_ZH.values()) + list(TOURNAMENT_ZH.values())
        top = json.loads((ROOT / "src/tennislive/zh/player_names_top500.json")
                         .read_text(encoding="utf-8"))
        for rows in top.get("tours", {}).values():
            vals += [r.get("name_zh", "") for r in rows]
    except Exception:  # noqa: BLE001 — 译名表读不到只是少一层惯例读音
        vals = []
    for v in vals:
        for part in re.split(r"[·・\s]", str(v or "")):
            if len(part) >= 2 and _HAN.fullmatch(part):
                names.add(part)
    return tuple(sorted(names, key=len, reverse=True))


def _readings(text: str) -> tuple[list[str | None], list[str | None], list[str | None], set[int]]:
    """逐字：(这儿该读什么, 所在的词, 词典词在这个字上给的读音, 手校规则碰过的字位)。"""
    from pypinyin import Style, pinyin
    from pypinyin.constants import PHRASES_DICT
    from pypinyin.contrib.tone_convert import to_tone3
    from pypinyin.seg.simpleseg import seg as py_seg
    n = len(text)
    reading: list[str | None] = [None] * n
    word: list[str | None] = [None] * n
    lex_reading: list[str | None] = [None] * n
    for m in _HAN.finditer(text):
        at = m.start()
        for w in py_seg(m.group()):
            rs = pinyin(w, style=Style.TONE3, neutral_tone_with_five=True)
            for k in range(len(w)):
                reading[at + k] = rs[k][0] if k < len(rs) else None
                word[at + k] = w
                if len(w) >= 2 and w in PHRASES_DICT and k < len(PHRASES_DICT[w]):
                    lex_reading[at + k] = to_tone3(PHRASES_DICT[w][k][0],
                                                   neutral_tone_with_five=True)
            at += len(w)
    touched: set[int] = set()
    for rx, r in _compiled_intended():
        for m in rx.finditer(text):
            k = m.start(1)
            if reading[k] is not None:
                reading[k] = r
                touched.add(k)
    for name in _name_parts():
        start = 0
        while (k := text.find(name, start)) >= 0:
            for j, ch in enumerate(name):
                if ch in NAME_CHAR_READING and (k + j) not in touched:
                    reading[k + j] = NAME_CHAR_READING[ch]
                    touched.add(k + j)
                    word[k + j] = name
            start = k + len(name)
    return reading, word, lex_reading, touched


def _measured_ok_positions(text: str) -> set[int]:
    out: set[int] = set()
    for w, (ch, _r, _why) in MEASURED_OK.items():
        start = 0
        while (k := text.find(w, start)) >= 0:
            j = w.find(ch)
            while j >= 0:
                if _context_matches(w, text, k + j):
                    out.add(k + j)
                j = w.find(ch, j + 1)
            start = k + 1
    return out


def _context_recheck_positions(text: str) -> set[int]:
    """有原句证据的词出现在新句子里，需要实测；词典命中不能藏掉提醒。"""
    out: set[int] = set()
    for word in MEASURED_OK_CONTEXTS:
        char = MEASURED_OK[word][0]
        for match in re.finditer(re.escape(word), text):
            for offset, current in enumerate(word):
                index = match.start() + offset
                if current == char and not _context_matches(word, text, index):
                    out.add(index)
    return out


def analyze(sp: Spoken) -> tuple[list[Risk], int, list[str]]:
    """一段旁白：(换字表管不到的非常用读音, 落在量过读对的词上的处数, 只能改写句子的提醒)。"""
    text = sp.text
    reading, word, lex_reading, _touched = _readings(text)
    covered = pronounce.covered_positions(text)
    rewrite = {m.start() for p, _ in REWRITE_ONLY for m in re.finditer(p, text)}
    ok = _measured_ok_positions(text)
    recheck = _context_recheck_positions(text)
    unc = {m.start(1) for p in UNCERTAIN for m in re.finditer(p, text)}
    risks: list[Risk] = []
    skipped_ok = 0
    for i, ch in enumerate(text):
        want = reading[i]
        if want is None:
            continue
        is_poly, defaults, live = poly_info(ch)
        if (not is_poly or want in defaults or want.endswith("5") or i in covered
                or i in rewrite):
            continue
        if i in ok or _reading_context_ok(text, i, ch, want):
            skipped_ok += 1
            continue
        new_context = (i in recheck or (ch, want) in MEASURED_OK_READING_CONTEXTS)
        others = [r for r in live if r != want and not r.endswith("5")]
        risks.append(Risk(
            label=sp.label, text=text, index=i, char=ch, word=word[i] or ch,
            intended=want, default=defaults[0] if defaults else "", others=others,
            rate=sp.rate, lexicon=lex_reading[i] == want and not new_context,
            uncertain=i in unc, context_recheck=new_context))
    notes = [f"{sp.label}「{text[max(0, m.start() - 4):m.end() + 4]}」：{why}"
             for p, why in REWRITE_ONLY for m in re.finditer(p, text)]
    return risks, skipped_ok, notes


# ---------------------------------------------------------------- 语料
def reel_texts(spec: dict) -> list[Spoken]:
    """赛场之上：`cover.narration`（网球有故事的剪辑片才有）、每段旁白、片尾那句。"""
    from tennislive.video.explainer import readable
    from tennislive.video.outro_page import NARRATION as OUTRO
    out: list[Spoken] = []
    cover = spec.get("cover") or {}
    if isinstance(cover, dict) and str(cover.get("narration") or "").strip():
        out.append(Spoken("封面", readable(cover["narration"]), REEL_RATE))
    for i, seg in enumerate(spec.get("segments") or []):
        if isinstance(seg, dict) and str(seg.get("narration") or "").strip():
            out.append(Spoken(f"第 {i + 1} 段", readable(seg["narration"]), REEL_RATE))
    if spec.get("outro", True):
        out.append(Spoken("片尾", readable(OUTRO), REEL_RATE))
    return out


def interview_texts(spec: dict, speech=None) -> list[Spoken]:
    """赛后开麦：解读卡的口播（`build_interview_clip._takeaway_speech`，就是念的那份）。

    `speech` 给了就用它——采访片自己的预检从 `__main__` 里调，再 import 一遍
    `build_interview_clip` 等于把那个几千行的模块加载第二次。
    """
    from tennislive.video.explainer import readable
    from tennislive.video.outro_page import NARRATION as OUTRO
    if speech is None:
        sys.path.insert(0, str(ROOT / "tools"))
        from build_interview_clip import _takeaway_speech as speech  # noqa: PLC0415
    rate = spec.get("takeaway_rate") or STORY_RATE
    out: list[Spoken] = []
    for which, card in (spec.get("takeaway") or {}).items():
        if isinstance(card, dict):
            out.append(Spoken(f"解读卡 {which}", readable(speech(card)), rate))
    # 采访片无解读卡时也有品牌片尾；片尾使用默认 +22%，不跟 takeaway_rate。
    out.append(Spoken("片尾", readable(OUTRO), STORY_RATE))
    return out


def explainer_texts(slug: str) -> list[Spoken]:
    """网球有故事（字卡）：`explainer_script` 排出来的每一屏，含开场和末屏那一问。"""
    from tennislive.video import explainer as E
    from tennislive.video.outro_page import NARRATION as OUTRO
    story = None
    try:
        from tennislive.render.tournament_story import find_story_by_slug
        story = find_story_by_slug(slug)
    except Exception:  # noqa: BLE001
        story = None
    if story is not None:
        segs = E.explainer_script(story)
    elif slug in E._SCRIPTS:
        segs = [E.ExplainerSegment(*row) for row in E._SCRIPTS[slug]]
        if segs:
            segs[-1] = E._ask_it_out_loud(segs[-1])
    else:
        return []
    return [Spoken(f"第 {i + 1} 屏", E.readable(s.narration), STORY_RATE)
            for i, s in enumerate(segs) if (s.narration or "").strip()] + [
                Spoken("片尾", E.readable(OUTRO), STORY_RATE)]


def spoken_texts(slug: str | None = None, spec_path: Path | None = None) -> list[Spoken]:
    """这条片子要喂给合成器的每一段（三条线都认）。"""
    if spec_path is not None:
        spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        if "takeaway" in spec and "segments" not in spec:
            return interview_texts(spec)
        return reel_texts(spec)
    assert slug
    reel = ROOT / "specs/reels" / f"{slug}.json"
    if reel.is_file():
        return reel_texts(json.loads(reel.read_text(encoding="utf-8")))
    interview = ROOT / "specs/interviews" / f"{slug}.json"
    if interview.is_file():
        return interview_texts(json.loads(interview.read_text(encoding="utf-8")))
    return explainer_texts(slug)


def _measure_cmd(slug: str | None, spec_path: str | Path | None) -> str:
    """提示里那行 `--measure` 命令。给了 spec 路径就指路径：`repair_reel_spec`、
    `taste_preflight` 这些拿**临时副本**跑 dry-run 的，按 slug 会指回仓库里那份
    没改过的 spec，量的就不是刚报出来的这几处。"""
    target = (f"--spec {shlex.quote(str(spec_path))}" if spec_path
              else f"--slug {slug or '<slug>'}")
    return f"python3 tools/check_polyphones.py {target} --measure"


def static_report(texts: list[Spoken], slug: str | None = None,
                  spec_path: str | Path | None = None) -> tuple[list[str], list[Risk]]:
    """`render --dry-run` 印的那几行。**没有也要出声**。

    逐条列的只有「不在词典词里」的——词典词（`银行`「重复」「露怯」这类，词典给的正是
    这个读音）合成器多半认得，只报个数。返回的 `risks` 两类都有（`--measure` 先量前者）。
    """
    risks: list[Risk] = []
    ok_total = 0
    notes: list[str] = []
    for sp in texts:
        r, ok, n = analyze(sp)
        risks += r
        ok_total += ok
        notes += n
    shown = [r for r in risks if not r.lexicon]
    lex = len(risks) - len(shown)
    lines: list[str] = []
    if shown:
        lines.append(f"[多音字] {len(shown)} 处读音不是这个字的常用读音、不在词典词里、"
                     "换字表也没管（src/tennislive/video/pronounce.py）：")
        for r in shown:
            ctx = r.text[max(0, r.index - 6):r.index + 7]
            tag = ("⚠️ 新语境未实测，旧句正确不能免检" if r.context_recheck
                   else "口径题" if r.uncertain else "⚠️ 合成器可能读错")
            lines.append(f"  {r.label}「{ctx}」 {r.char} 应读 {_show(r.intended)}"
                         f"（不看上下文会读 {_show(r.default)}）［{tag}］")
        lines.append("  要知道合成器到底读成什么（要联网，一处十几秒）：\n"
                     f"    {_measure_cmd(slug, spec_path)}"
                     "\n  读错了就把它量出来的表项抄进 pronounce.HOMOPHONES；只报不拦。")
    else:
        lines.append("[多音字] 没有换字表管不到的非常用读音"
                     f"（{sum(len(t.text) for t in texts)} 字、{len(texts)} 段查过）")
    tail = []
    if lex:
        tail.append(f"{lex} 处在词典词里（词典给的就是这个读音，合成器多半认得）")
    if ok_total:
        tail.append(f"{ok_total} 处落在量过读对的词上（check_polyphones.MEASURED_OK）")
    if tail:
        lines.append("  另 " + "；".join(tail) + "，不逐条报")
    for n in notes:
        lines.append(f"  ⚠️ {n}")
    lines.append("  静态筛选不是声学通过；词典和历史词条不能证明本次整句读对。"
                 f"本次 {len(texts)} 段仍须按实际嗓音、语速逐段声学复核，含封面、旁白和片尾。")
    return lines, risks


NO_PYPINYIN = ("[多音字] ⚠️ 这趟没查：没装 pypinyin（pip install pypinyin；"
               "生产任务必须安装后重跑检查）——**没查不等于没有**")


def pypinyin_available() -> bool:
    """只问装没装，不 import：缺它时别先付别的 import 的钱。"""
    import importlib.util  # noqa: PLC0415
    try:
        return importlib.util.find_spec("pypinyin") is not None
    except (ImportError, ValueError):
        return False


def _unfinished(exc: BaseException) -> str:
    return f"[多音字] ⚠️ 这趟没查完：{type(exc).__name__}: {exc}"[:300]


def report_lines(texts: list[Spoken], slug: str | None = None,
                 spec_path: str | Path | None = None) -> list[str]:
    """给出片前的预检座位用（`render --dry-run`、采访片每一趟开头）：只报不拦，
    查不了要**出声**——「没查」和「查过没有」在日志里不许长得一样。"""
    if not pypinyin_available():
        return [NO_PYPINYIN]
    try:
        return static_report(texts, slug, spec_path)[0]
    except Exception as exc:  # noqa: BLE001 — 预检自己出错不许拖垮出片，但要说出来
        return [_unfinished(exc)]


def preflight_lines(make_texts, slug: str | None = None,
                    spec_path: str | Path | None = None) -> list[str]:
    """出片前预检座位的唯一入口：**先**看 pypinyin 在不在，再取语料。

    取语料要 import `tennislive.video.explainer`（约 2.4 秒）——采访片那个模块
    故意不 import 它；runner 上 pypinyin 恒缺，每一趟为了印一句「这趟没查」先付
    那 2.4 秒不值。取语料出错也只出声、不抛：这是只报不拦的预检，不许拖垮出片。
    """
    if not pypinyin_available():
        return [NO_PYPINYIN]
    try:
        texts = make_texts()
    except Exception as exc:  # noqa: BLE001
        return [_unfinished(exc)]
    return report_lines(texts, slug, spec_path)


def _show(r: str) -> str:
    try:
        from pypinyin.contrib.tone_convert import to_tone
        return r[:-1] if r.endswith("5") else to_tone(r)
    except Exception:  # noqa: BLE001
        return r


# ---------------------------------------------------------------- 量
def _measure_one(r: Risk, voice: str = VOICE) -> dict:
    """真合成器比对一处；读错就顺手量换字候选。"""
    from tennislive.video.explainer import speakable
    sys.path.insert(0, str(ROOT / "tools"))
    import measure_polyphone as mp  # noqa: PLC0415

    sent, at = r.sentence()
    spoken = speakable(sent)
    if len(spoken) != len(sent):
        return {"verdict": "skipped", "why": "换字前后字数不一致（不该发生）"}
    word = r.word if r.word and r.word in sent else r.char
    ok_refs, _ = mp.suggest_homophones(r.intended, exclude=word, k=3)
    if not ok_refs:
        return {"verdict": "skipped", "why": f"找不到只读 {_show(r.intended)} 的常用字当参考"}
    results = []
    for wrong in r.others[:2]:
        bad_refs, _ = mp.suggest_homophones(wrong, exclude=word, k=3)
        if not bad_refs:
            continue
        m = mp.measure(word, spoken, ok_refs, bad_refs, voice, r.rate, char=r.char,
                       at=at)
        results.append({"wrong": wrong, "bad_refs": "".join(bad_refs),
                        "verdict": m["verdict"], "confidence": m["confidence"],
                        "score": m["score"], "near": m["near_identical_to"]})
    if not results:
        return {"verdict": "skipped", "why": "错读那头找不到只有一个读音的常用字"}
    verdicts = [x["verdict"] for x in results]
    if "misread" in verdicts:
        verdict = "misread"
    elif all(v == "correct" for v in verdicts):
        verdict = "correct"
    else:
        verdict = "uncertain"
    out = {"verdict": verdict, "runs": results, "sentence": spoken, "ok_refs": "".join(ok_refs)}
    if verdict == "misread":
        bad = next(x for x in results if x["verdict"] == "misread")
        conf = [x["confidence"] for x in results if x["verdict"] == "misread"]
        out["confidence"] = "high" if "high" in conf else ("medium" if "medium" in conf else "low")
        cands, _ = mp.suggest_homophones(r.intended, exclude=word, k=4)
        for cand in cands[:3]:
            refs = [c for c in cands if c != cand][:2] or ok_refs
            m = mp.measure(word, spoken, refs, list(bad["bad_refs"]), voice, r.rate,
                           char=r.char, orig_override=cand, at=at)
            if m["verdict"] == "correct":
                out["replacement"] = cand
                out["replacement_evidence"] = (
                    f"score {m['score']:+.2f}，离对的参考 {m['features']['comb']['d_intended']}、"
                    f"离错的 {m['features']['comb']['d_wrong']}")
                break
    return out


def measure_risks(risks: list[Risk], *, limit: int = 6, workers: int = 3,
                  voice: str = VOICE) -> tuple[list[str], list[Risk]]:
    """逐处量（最多 `limit` 处，先量不在词典里的）。返回 (报告行, 量出来读错的)。"""
    sys.path.insert(0, str(ROOT / "tools"))
    import measure_polyphone as mp  # noqa: PLC0415
    miss = mp.missing_deps()
    if miss:
        return ([f"[多音字·量] ⚠️ 这趟没量：缺 {', '.join(miss)}"
                 "（pip install -e \".[polyphone]\"；ffmpeg 走 apt）——**没量不等于没问题**"], [])
    if not risks:
        return (["[多音字·量] 静态没报出要量的位置，这趟不用合成"], [])
    order = sorted(risks, key=lambda r: (r.uncertain, r.lexicon))
    todo, rest = order[:limit], order[limit:]
    lines = [f"[多音字·量] 真合成器逐处比对 {len(todo)} 处（{VOICE}）"
             + (f"，另 {len(rest)} 处超过上限没量（--limit）" if rest else "") + "："]
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        results = list(pool.map(lambda r: _safe_measure(r, voice), todo))
    bad: list[Risk] = []
    for r, m in zip(todo, results):
        r.measured = m
        ctx = r.text[max(0, r.index - 6):r.index + 7]
        head = f"  {r.label}「{ctx}」 {r.char}→{_show(r.intended)}："
        if m["verdict"] == "misread":
            bad.append(r)
            line = f"{head}**读错**（{m.get('confidence')}）"
            if m.get("replacement"):
                line += f"；换「{m['replacement']}」读对了（{m['replacement_evidence']}）"
                lines.append(line)
                lines.append("    表项草稿（抄进 pronounce.HOMOPHONES，guards 自己补）：")
                lines.append("    " + suggest_entry(r))
            else:
                lines.append(line + "；三个候选同音字都没读对——改写这一句")
        elif m["verdict"] == "correct":
            lines.append(f"{head}读对了——可以记进 MEASURED_OK")
        else:
            lines.append(f"{head}{m['verdict']}（{m.get('why') or '两边参考音都够不着，量不准'}）")
    return lines, bad


def _safe_measure(r: Risk, voice: str) -> dict:
    try:
        return _measure_one(r, voice)
    except Exception as exc:  # noqa: BLE001 — 一处量不了不许拖垮整份报告，但要说出来
        return {"verdict": "error", "why": f"{type(exc).__name__}: {exc}"[:200]}


def suggest_entry(r: Risk) -> str:
    cand = r.measured.get("replacement", "?")
    word = r.word if r.word and len(r.word) <= 6 else r.char
    k = word.find(r.char)
    rep = word[:k] + cand + word[k + 1:]
    return (f"Homophone(key=\"{word}\", pattern=\"{word}\", replace=\"{rep}\", word=\"{word}\", "
            f"reading=\"{_show(r.intended)}\", evidence=\"<日期> measure_polyphone（{r.rate}）："
            f"原句读错；换「{cand}」{r.measured.get('replacement_evidence', '')}\", "
            f"examples=((\"{r.sentence()[0]}\", \"<换完>\"),), guards=())")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug", help="赛场之上 / 采访 / 解说片的 slug")
    g.add_argument("--spec", help="直接给 spec 路径（reel 或 interview）")
    ap.add_argument("--measure", action="store_true", help="真合成器逐处比对（要联网）")
    ap.add_argument("--limit", type=int, default=12, help="--measure 最多量几处")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args(argv)
    if not pypinyin_available():
        print(NO_PYPINYIN)
        return 2  # 生产独立检查命令未执行，不能作为成功凭证。
    texts = spoken_texts(a.slug, Path(a.spec) if a.spec else None)
    if not texts:
        print(f"[多音字] 找不到 {a.slug or a.spec} 的旁白（specs/reels、specs/interviews、"
              "explainer._SCRIPTS 都查过）")
        return 2
    lines, risks = static_report(texts, a.slug, a.spec)
    print("\n".join(lines))
    if a.measure:
        try:
            from tennislive.localca import trust_local_proxy_ca
            trust_local_proxy_ca()
        except Exception:  # noqa: BLE001
            pass
        mlines, bad = measure_risks(risks, limit=a.limit, workers=a.workers)
        print("\n".join(mlines))
        if bad:
            return 1
        # 缺依赖、超 limit、uncertain/unreliable/skipped 均不是声学通过。
        incomplete = (any("这趟没量" in line for line in mlines)
                      or any(r.measured.get("verdict") != "correct" for r in risks))
        return 2 if incomplete else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
