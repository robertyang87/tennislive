"""竖版短片的「吸引力」判据——只吃 `specs/`，秒级，不联网、不读产物。

来路：2026-08-14 拿全部 64 条 reel spec 做了一次编辑质量扫描。**五条候选里
四条做成了硬闸，一条被自己的扫描结果否掉、降成了棘轮**——这份文件同时记下了
「为什么这条做成硬闸」和「为什么那条不做成硬闸」，因为后者更容易被下一个人
重新提出来（它看起来非常有道理）。

四条硬闸的共同点是**同一个形状**：拿 08-08 当分界，之前 0 条、之后全部——
也就是说它们不是这个号一贯的写法，是最近漂出来的模板。

    判据                         命中   08-08 前   08-08 后
    开场旁白复读封面钩子           6        0          6
    钩子复述赛果条/顶栏            5        0          5
    推送标题只有名字加赛果        11        0         11
    小红书标题用通稿导语开头      23        0         23

被否掉的那条是**钩子最长行的字数**（详见第二节）：它确实在漂，但字数的分布
从 8 到 25 连成一片、没有任何一道缝，按中位数 14 设闸等于宣布一半的库存有罪。
它只留了一道棘轮（不许比今天最坏的还坏），零豁免。

⚠️ 另有两条候选（「开场 N 秒内必须开口」「收尾不许用『还能走多远』」）在动手
之前就被扫描否掉了，**没有写进这份文件**：前者会误伤 14 条（片子有常驻顶栏
字幕，静音用户并非零文字信息），后者的数字虚高且已自愈（08-10 起 2/18，与
基线无差别），更简单的解释是轮次而不是套模板。别再重新提。

⚠️ **已发的片子一律不重渲**（微信消息发出去收不回来），所以每条判据都配一张
豁免表，**只许减不许加**，而且表自己有自检：表里每个 slug 必须真的存在、
而且真的还在犯这个毛病——写错一个名字，豁免就成了一盏恒真的绿灯。

豁免表按**推没推过**分成两半，这不是排版，是记账：`_已推送` 那半是永久的
（收不回来了），`_还没推送` 那半**是还来得及改的**，改一条就从表里删一条，
自检会在你改完之后提醒你删。

⚠️ 这份文件里**没有**「钩子写得好不好」「收尾动不动人」这类判据，是故意的：
判断题机械挡不住，硬凑一个会被绕过的判据还会制造「已经守住了」的错觉，
比没有更糟（CLAUDE.md 里几条「故意没有测试」是同一个理由）。
"""

import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

SPEC_DIR = Path("specs/reels")


def _specs():
    """(slug, spec) 逐条给出来。只读 `specs/`——CI 的稀疏检出不含 `output/`，
    拿产物当判据的主语会在 CI 上变成一盏恒真的绿灯（本仓库栽过一次）。"""
    for path in sorted(SPEC_DIR.glob("*.json")):
        yield path.stem, json.loads(path.read_text("utf-8"))


def _hook_lines(spec):
    """封面钩子的每一行（去掉空行）。没有钩子的返回空列表。

    ⚠️ **不按 layout 过滤。** 一开始我的扫描脚本只看 `layout == "solo"`，
    于是漏掉了 `wong-lehecka`（cutout 版式）——而它恰好是第三节那道闸第一版
    唯一的误伤。判据的范围写窄了，误伤就要等到跑起来才现形。
    """
    cover = spec.get("cover") or {}
    hook = str(cover.get("hook") or "")
    return [ln.strip() for ln in hook.split("\n") if ln.strip()]


def _first_narration(spec):
    """第一段**有旁白**的话。

    ⚠️ 要跳过没有旁白的段：开场那一格按规矩是不配旁白的冷开场（交给现场声），
    `quote` 段则是原声。这两种都不是「我们说的第一句话」。
    """
    for seg in spec.get("segments") or []:
        text = str(seg.get("narration") or "").strip()
        if text:
            return text
    return ""


def _bare(text):
    """去掉标点只留下字，用来比「说的是不是同一件事」。

    比的是内容不是排版：钩子里是换行、旁白里是逗号或破折号，同一句话在两处
    的标点必然不同，连标点一起比会把真复读判成不像。
    """
    return re.sub(r"[^\w一-鿿]", "", text)


# ──────────────────────────────────────────────────────────────────────────
# 一、开场旁白不许复读封面钩子
# ──────────────────────────────────────────────────────────────────────────
#
# ⚠️ **这条拦的不是「听了两遍」，是「这句最贵的话没有带来第二个信息」。**
# 封面只停 `COVER_SECONDS` 秒（代码里是 1.2），而这些钩子平均 24.6 字——
# 要 20 字/秒才读得完，也就是**大多数人根本没读完封面**。所以第 ② 句是他们
# 第一次接触这句话，问题不在重复，在于本该由 ② 句给出的那个「落点」被这次
# 复读吃掉了：命中的六条里，② 句全部退化成了坐标（北京时间＋赛事＋轮次）。
#
# 参照 `shang-rublev`（账号所有者 2026-08-05 亲自定的第三版）：钩子讲过程、
# ② 句讲落点，**两句各带一个事实**。
#
# 门槛 0.8 是**从分布里量出来的，不是拍的**。64 条按相似度排开，最高处这样：
#
#     1.000  1.000  0.976  0.943  0.900  0.807 │ 0.703  0.615  0.609  0.604 …
#                                        最大的一道缝 ↑ 0.104
#
# 0.807 和 0.703 之间那道 0.104 的缝是整个高位区最宽的一道（相邻两档普遍只差
# 0.005~0.05），0.8 正落在缝里。
# ⚠️ **别往 0.7 收**：那样会把 `rybakina-kasatkina`（0.703）也拦下来，而它的
# 钩子第二行「二号种子涉险过关」是**留着没说**的——② 句只重述了 WTA 头条那个
# 58/58 的修辞并把「失误」说准成「非受迫失误」，落点没有被吃掉。
_HOOK_ECHO_MAX = 0.8

# 已经推过微信，收不回来了。**只许减不许加。**
_HOOK_ECHO_LEGACY_已推送 = frozenset({
    "bencic-eala",           # 0.976
    "fonseca-ruud",          # 0.900
    "rybakina-samsonova",    # 1.000 逐字相同
    "shnaider-pegula",       # 0.943
    "swiatek-shnaider",      # 0.807
})

# ⏰ **已渲、还没推——改这几条只花一次重渲。** 改一条就从这儿删一条。
_HOOK_ECHO_LEGACY_还没推送 = frozenset({
    # 1.000，逐字相同：钩子「首盘轻松拿下，次盘却只赢一局／这是她本赛季的
    # 第一个决赛」，① 句一字不差地又念了一遍，② 句退化成坐标。
    "swiatek-svitolina-toronto-sf",
})

_HOOK_ECHO_LEGACY = _HOOK_ECHO_LEGACY_已推送 | _HOOK_ECHO_LEGACY_还没推送


def _hook_echo_offenders():
    """{slug: 相似度}，只收超过门槛的。"""
    out = {}
    for slug, spec in _specs():
        lines = _hook_lines(spec)
        first = _first_narration(spec)
        if not lines or not first:
            continue
        ratio = SequenceMatcher(None, _bare("".join(lines)), _bare(first)).ratio()
        if ratio >= _HOOK_ECHO_MAX:
            out[slug] = round(ratio, 3)
    return out


def test_开场旁白不许复读封面钩子():
    """第 ② 句要带一个**新的**事实，不是把封面那句再念一遍。"""
    offenders = _hook_echo_offenders()
    fresh = {k: v for k, v in offenders.items() if k not in _HOOK_ECHO_LEGACY}
    assert not fresh, (
        f"这几条的第一句旁白基本就是封面钩子：{fresh}。封面只停 1.2 秒、"
        f"钩子二十多个字，大多数人根本没读完——所以第 ② 句是他们第一次接触"
        f"这句话，把它花在复读上，等于这条片子最贵的两句话只讲了一个事实。"
        f"参照 `shang-rublev`：钩子讲过程、② 句讲落点，各带一个事实。"
    )
    # 判据自己的判据：主语没了（改了字段名、换了目录）要出声，别变成恒真绿灯。
    assert len(list(_specs())) >= 40, "一条 spec 都没扫到，判据的主语像是没了"


def test_复读钩子的豁免表只许减不许加():
    for slug in sorted(_HOOK_ECHO_LEGACY):
        assert (SPEC_DIR / f"{slug}.json").is_file(), \
            f"{slug} 这条 spec 已经没了，把它从豁免表里删掉"
    offenders = _hook_echo_offenders()
    stale = _HOOK_ECHO_LEGACY - set(offenders)
    assert not stale, (
        f"这几条的开场旁白已经不复读钩子了，把它们从豁免表里删掉：{stale}"
        f"——这张表只许减不许加"
    )


# ──────────────────────────────────────────────────────────────────────────
# 二、钩子最长行的字数：**只做棘轮，不做闸**
# ──────────────────────────────────────────────────────────────────────────
#
# ⚠️ **这一条本来提议做成硬闸（最长行 ≤14 字），扫完之后否掉了。** 记在这儿是
# 因为它看起来很有道理，下一个人多半会重新提一次。
#
# 钩子字号是算出来的：`min(124, 940 / 最长那一行的字数)`。所以行越长字越小，
# 64 条有钩子的封面量下来：只有 **5 条**够到 124 的上限，**23 条小于 60px**，
# 最小 37px。而且确实在漂——只看 51 条 solo 封面、按加进仓库的日期分三段，
# 最长行的均值 11.4 → 14.5 → 17.0，`>14 字`的比例 1/8 → 9/19 → 14/24。
#
# **可它不能做成闸，因为分布是连成一片的**（这 64 条的最长行，排开）：
#
#     6 7 7 7 7 8 8 8 8 9 9 9 9 9 10 10 10 10 10 11 11 11 11 11 11 12 12 12
#     12 12 13 13 13 14 14 14 14 14 14 14 15 16 16 16 16 16 16 16 17 17 18
#     18 18 19 20 21 21 21 22 22 22 24 24 25
#
# 从 6 一路到 25，**没有任何一道干净的缝**。中位数正好落在 13（只看 solo 是
# 14）——也就是说按它设闸，「一半的库存都是错的」，而没有任何证据表明 15 字比
# 14 字更坏。这跟 CLAUDE.md 里跨切点那次是同一个形状：拿 20 条已发 spec 一扫
# 10 条会红、从 0.16s 连到 8.28s 没有分界，**那不是闸，是墙**；而墙的下场是
# 可预见的——下一个人把二十几条全塞进豁免表，然后这张表变成一张许可证。
#
# ⚠️ 上面两组数**取自两个不同的口径**（全部 64 条 vs 只看 solo 的 51 条），
# 写在一起是因为漂移那一半只在 solo 上量过。下面的棘轮扫的是**全部 64 条**，
# 别拿 solo 那组数去核它——我自己第一版就是拿 51 条的数写注释、代码扫 64 条，
# 「达到上限的有几条」当场对不上。
#
# 所以只做**棘轮**：不许比今天最坏的那条更坏。25 是量出来的当前最坏值
# （`jodar-fils-montreal-qf`，37px），不是拍的；它零豁免、只拦新的漂移。
_HOOK_LINE_WORST_TODAY = 25


def _hook_line_lengths():
    """{slug: (最长行字数, 算出来的字号)}，只看有钩子的封面。"""
    out = {}
    for slug, spec in _specs():
        lines = _hook_lines(spec)
        if not lines:
            continue
        longest = max(len(ln) for ln in lines)
        cap = 124 if len(lines) <= 2 else 96
        out[slug] = (longest, min(cap, int(940 / longest)))
    return out


def test_钩子字号那个公式没变过():
    """上面整段推理（行越长字越小、25 字只剩 37px）全建立在这个公式上。

    公式一改，那段话和它推出来的棘轮就都要重算——所以把它钉住，
    **而且是 import 出来钉的，不是 grep 出来的**：改完源码要验的是 import
    的结果，`grep` 会被注释和 docstring 骗过去。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import versus_poster

    assert versus_poster.SHORT_HOOK_TITLE_PX == 124, \
        "短钩子的字号上限变了，重算钩子长度那一节的账"
    body = Path("tools/versus_poster.py").read_text("utf-8")
    assert "title_px = min(cap, int(940 / max(" in body, \
        "钩子字号不再是 min(cap, 940/最长行) 了，上面那段推理要重做"


def test_钩子最长行不许比今天最坏的还长():
    """棘轮，不是闸：只拦「比现在更坏」，不宣布一半的库存有罪。"""
    lengths = _hook_line_lengths()
    over = {s: v for s, v in lengths.items() if v[0] > _HOOK_LINE_WORST_TODAY}
    assert not over, (
        f"这几条钩子的最长行比今天最坏的那条（{_HOOK_LINE_WORST_TODAY} 字）还长："
        f"{over}（值是「最长行字数, 算出来的字号」）。字号是 "
        f"min(124, 940/最长行) 算的，行越长字越小——封面是唯一决定人点不点的"
        f"那一屏，别再往下漂了。"
    )
    assert len(lengths) >= 40, f"只扫到 {len(lengths)} 条钩子，判据的主语像是没了"


# ──────────────────────────────────────────────────────────────────────────
# 三、钩子不许复述赛果条和顶栏已经印着的东西
# ──────────────────────────────────────────────────────────────────────────
#
# 「赛场之上」的封面上，钩子底下那行赛果条**已经印着赢家、比分和对手**
# （`🇰🇿 莱巴金娜 6-4 4-6 6-4 🇷🇺 萨姆索诺娃`），顶栏第一行**已经印着赛事和
# 轮次**（`WTA1000 多伦多 1/8决赛`）。钩子再写一遍「6-3锁定这场1/4决赛」，
# 是拿整张海报最大的那几个字去复读它正下方的一行小字。
#
# 这和 CLAUDE.md 那条「钩子要有剧情的跌宕，不是把两个身份摆在一起」是同一条
# 的另一半：那条禁的是复读**排名**（赛果行已印），这条禁的是复读**比分和轮次**。
#
# ⚠️ **判据是从这条 spec 自己的字段推出来的，不维护词表**：拿 `cover.result`
# 里的每一盘比分、和 `topbar.line1` 里的轮次，去钩子里找。词表会过期，
# 而「海报上另一处印着什么」永远是这份 spec 自己说了算。
#
# ⚠️ 轮次要**长的先匹配、而且要相等**，不能用 `in`：`swiatek-svitolina-toronto-sf`
# 的钩子写着「这是她本赛季的第一个**决赛**」——那是里程碑（她刚赢下半决赛），
# 而顶栏写的是「半决赛」。按子串匹配，「决赛」会在「半决赛」里命中，
# 把一条完全正当的钩子判成复读。**判据宁可窄，不可宽**，这一处第一版就误伤了。
#
# ⚠️⚠️ **比分那一半只认「赢家赢下的那几盘」，这是跑出来才发现的。**
# 第一版拿 `cover.result` 里的每一盘去钩子里找，跑完当场拦下 `wong-lehecka`
# 的「先输 1-6／再掀翻头号种子」——而 CLAUDE.md 里白纸黑字记着这条规矩**已经
# 被试过并且否掉了**：「我一度想加一条『钩子里不许出现比分』，拿存量一验，
# 被拦掉的恰恰是最好的两条……比分在这里是制造张力的手段，不是复述结果。
# 判据要卡的是『有没有开一扇门』，不是『有没有数字』。」
#
# 分界是**这一盘赢家是赢了还是输了**，而 `cover.result` 是赢家在前的
# （CLAUDE.md 钉死的口径），所以机械判得出来：
#
#     先输 1-6，再掀翻头号种子      1-6 是他**丢掉**的一盘 → 是挫折，开了一扇门 ✅
#     6-3 锁定这场 1/4 决赛         6-3 是他**赢下**的一盘 → 是结果，赛果条已印 ❌
#
# 全库扫下来只有这四条钩子引了本场比分，三坏一好，按这个口径分得干干净净。
_SET_SCORE = re.compile(r"^(\d+)-(\d+)")
_ROUND_TOKEN = re.compile(
    r"(1/4决赛|1/8决赛|四分之一决赛|半决赛|决赛|第[一二三四]轮|资格赛)"
)


def _hook_duplicate_offenders():
    """{slug: [哪几处复读了]}。"""
    out = {}
    for slug, spec in _specs():
        cover = spec.get("cover") or {}
        lines = _hook_lines(spec)
        if not lines:
            continue
        hook = "".join(lines).replace(" ", "")
        why = []
        for one_set in str(cover.get("result") or "").split():
            got = _SET_SCORE.match(one_set)
            if not got:
                continue
            # 只认赢家**赢下**的那几盘：丢掉的那一盘写进钩子是挫折（开门），
            # 赢下的那一盘写进钩子是结果（赛果条正下方已经印着）。
            if int(got.group(1)) <= int(got.group(2)):
                continue
            if got.group(0) in hook:
                why.append(f"比分{got.group(0)}")
        topbar_rounds = set(
            _ROUND_TOKEN.findall(str((spec.get("topbar") or {}).get("line1") or ""))
        )
        for token in sorted(set(_ROUND_TOKEN.findall(hook))):
            if token in topbar_rounds:
                why.append(f"轮次{token}")
        if why:
            out[slug] = why
    return out


_HOOK_DUP_LEGACY_已推送 = frozenset({
    "nakashima-jodar-montreal-sf",   # 钩子「把这场半决赛收官」，顶栏也写着半决赛
    "shelton-mensik",                # 钩子「6-3 6-1，晋级蒙特利尔半决赛」
})

# ⏰ **已渲、还没推——还来得及改。**
_HOOK_DUP_LEGACY_还没推送 = frozenset({
    "jodar-fils-montreal-qf",        # 「6-3锁定这场1/4决赛」：比分和轮次一起复读
    "rybakina-osaka",                # 「6-4逆转拿下这场鏖战」
    "shelton-tien-montreal-sf",      # 「他才把这场半决赛收进口袋」
})

_HOOK_DUP_LEGACY = _HOOK_DUP_LEGACY_已推送 | _HOOK_DUP_LEGACY_还没推送


def test_钩子不许复述赛果条和顶栏印着的东西():
    offenders = _hook_duplicate_offenders()
    fresh = {k: v for k, v in offenders.items() if k not in _HOOK_DUP_LEGACY}
    assert not fresh, (
        f"这几条钩子在复读海报上别处已经印着的东西：{fresh}。赛果条印着比分和"
        f"赢家、顶栏第一行印着赛事和轮次——钩子是整张海报最大的那几个字，"
        f"拿它复读正下方那行小字，等于这张封面只讲了一件事。"
    )
    assert len(list(_specs())) >= 40, "一条 spec 都没扫到，判据的主语像是没了"


def test_钩子复读赛果的豁免表只许减不许加():
    for slug in sorted(_HOOK_DUP_LEGACY):
        assert (SPEC_DIR / f"{slug}.json").is_file(), \
            f"{slug} 这条 spec 已经没了，把它从豁免表里删掉"
    stale = _HOOK_DUP_LEGACY - set(_hook_duplicate_offenders())
    assert not stale, (
        f"这几条钩子已经不复读赛果/轮次了，把它们从豁免表里删掉：{stale}"
        f"——这张表只许减不许加"
    )


# ──────────────────────────────────────────────────────────────────────────
# 四、推送标题不许只有名字加赛果
# ──────────────────────────────────────────────────────────────────────────
#
# 来路：08-08 之后的推送列表里连着出现「莱巴金娜逆转晋级」「斯瓦泰克逆转晋级」
# 「斯维托丽娜逆转晋级」——**在微信的消息列表里几乎分不出是三条不同的片子**。
#
# 对照组把「不会写」这个解释排除掉了：同一批人写的「网球有故事」标题
# **6 条全部合格**（「小镇如何留住百年大赛」「从奥运冠军到资格赛」），
# 而「赛场之上」55 条里有 11 条只剩名字加赛果。所以缺的不是本事，是一道闸。
#
# ⚠️ **判据是「剥掉之后还剩什么」，不是「以什么结尾」。** 第一版按「以晋级/
# 淘汰/横扫/逆转结尾」扫，命中 21 条——里面「46 岁大威首轮出局」「梅德韦杰夫
# 9 双误两盘出局」「王欣瑜救三盘点过关」全是**带着信息的**好标题，被误伤了。
# 改成：把这条 spec 自己登记的球员名（`cover.matchup` / `winner` / `subject`）
# 和赛果动词都剥掉，**什么都不剩**的才算。命中降到 11 条，而且全部是
# 08-08 之后的。
#
# ⚠️ 动词表是个词表，会过期——但它只用来**剥**：漏掉一个动词的后果是**漏判**
# （少拦一条），不是误伤，方向是安全的那一头。现成的好写法就在同一份 spec 的
# `push.lead` 里（「此前和佩古拉交手四次全负，最近一次就是一周前华盛顿站
# 半决赛」——那才是标题）。
_RESULT_VERB = re.compile(
    r"(晋级|淘汰|横扫|逆转|击败|险胜|过关|出局|收官|锁定|苦战|拿下|战胜|获胜|胜)"
)


def _summary_offenders():
    """{slug: 推送标题}，只收「剥完名字和赛果动词之后什么都不剩」的。"""
    out = {}
    for slug, spec in _specs():
        cover = spec.get("cover") or {}
        if cover.get("eyebrow") != "赛场之上":
            continue
        summary = str((spec.get("push") or {}).get("summary") or "").strip()
        if not summary:
            continue
        rest = summary
        names = [str(m.get("name") or "") for m in (cover.get("matchup") or [])]
        names += [str(cover.get("winner") or ""), str(cover.get("subject") or "")]
        for name in names:
            if name.strip():
                rest = rest.replace(name.strip(), "")
        rest = _RESULT_VERB.sub("", rest)
        if not re.sub(r"[，,。、·\s]", "", rest):
            out[slug] = summary
    return out


_SUMMARY_LEGACY_已推送 = frozenset({
    "osaka-fernandez",             # 大坂直美淘汰费尔南德斯
    "osaka-mertens",               # 奥萨卡横扫梅尔滕斯晋级
    "rybakina-gauff-toronto-sf",   # 莱巴金娜逆转晋级
    "shelton-fonseca",             # 谢尔顿险胜丰塞卡
    "shelton-mensik",              # 谢尔顿横扫门西克
    "svitolina-alexandrova",       # 斯维托丽娜逆转晋级
    "swiatek-golubic",             # 斯瓦泰克横扫戈卢比奇晋级
    "swiatek-kostyuk",             # 斯瓦泰克逆转科斯秋克晋级
})

# ⏰ **还没推——`push.summary` 只是一行字，改它连重渲都不用。**
_SUMMARY_LEGACY_还没推送 = frozenset({
    "rybakina-li",                    # 莱巴金娜逆转晋级
    "rybakina-osaka",                 # 莱巴金娜逆转大坂直美
    "swiatek-svitolina-toronto-sf",   # 斯瓦泰克逆转晋级
})

_SUMMARY_LEGACY = _SUMMARY_LEGACY_已推送 | _SUMMARY_LEGACY_还没推送


def test_推送标题不许只有名字加赛果():
    offenders = _summary_offenders()
    fresh = {k: v for k, v in offenders.items() if k not in _SUMMARY_LEGACY}
    assert not fresh, (
        f"这几条推送标题剥掉名字和赛果动词之后什么都不剩：{fresh}。"
        f"「谁逆转晋级」在微信的消息列表里分不出是哪一条片子——同一份 spec 的 "
        f"`push.lead` 里往往就躺着那句该当标题的话。"
    )
    # 判据自己的判据：断言「不出现」之前，先证明它在正常情况下会出现——
    # 栏目名写错、字段改名，这里都会当场出声，而不是变成恒真的绿灯。
    scanned = sum(
        1 for _, spec in _specs()
        if (spec.get("cover") or {}).get("eyebrow") == "赛场之上"
        and str((spec.get("push") or {}).get("summary") or "").strip()
    )
    assert scanned >= 40, f"只扫到 {scanned} 条赛场之上的推送标题，判据的主语像是没了"


def test_推送标题的豁免表只许减不许加():
    for slug in sorted(_SUMMARY_LEGACY):
        assert (SPEC_DIR / f"{slug}.json").is_file(), \
            f"{slug} 这条 spec 已经没了，把它从豁免表里删掉"
    stale = _SUMMARY_LEGACY - set(_summary_offenders())
    assert not stale, (
        f"这几条推送标题已经不只是名字加赛果了，把它们从豁免表里删掉：{stale}"
        f"——这张表只许减不许加"
    )


# ──────────────────────────────────────────────────────────────────────────
# 五、小红书标题不许用通稿导语开头
# ──────────────────────────────────────────────────────────────────────────
#
# `.xhs.txt` 的第一行就是小红书那一格标题，也就是这条片子在信息流里最贵的一行。
# 08-08 之后它变成了通讯社发稿的样子：**23 条以「N号种子」打头或者把「用时
# 1小时26分」写进标题**——而「用时」是个数据接口字段（`MatchTimeTotal`），
# 读者不会因为一场球打了 1 小时 26 分钟点进来。
#
# 同样是 0 条在 08-08 之前、23 条在之后；「网球有故事」那几条的第一行则是
# 「四岁那年，外公塞给她一把比她还高的球拍」——同一批人，同一天，写得出来。
#
# ⚠️ **只拦两种，判据宁可窄不可宽**：① 整行**以**「N号种子」开头（把最贵的
# 位置让给了种子序号）；② 行里出现「用时」（那是接口字段，属于正文不属于标题）。
# 种子号出现在句中不拦——`eala-washington-story` 的标题里也有「二号种子」，
# 但它开头是「21 岁的伊埃拉在华盛顿五场全胜」，位置对了就不是这个毛病。
_XHS_LEDE_SEED = re.compile(r"^(\d+|[一二三四五六七八九十]+)号种子")


def _xhs_lede_offenders():
    """{slug: 标题那一行}。"""
    out = {}
    for path in sorted(SPEC_DIR.glob("*.xhs.txt")):
        slug = path.name[: -len(".xhs.txt")]
        if not (SPEC_DIR / f"{slug}.json").is_file():
            continue
        lines = [ln.strip() for ln in path.read_text("utf-8").split("\n") if ln.strip()]
        if not lines:
            continue
        title = lines[0]
        if _XHS_LEDE_SEED.match(title) or "用时" in title:
            out[slug] = title
    return out


_XHS_LEDE_LEGACY_已推送 = frozenset({
    "alexandrova-sabalenka", "anisimova-bartunkova", "bencic-eala",
    "gauff-korneeva", "osaka-fernandez", "osaka-mertens",
    "rybakina-gauff-toronto-sf", "rybakina-samsonova", "shelton-fonseca",
    "shelton-mensik", "shnaider-pegula", "svitolina-alexandrova",
    "svitolina-anisimova", "swiatek-golubic", "swiatek-kostyuk",
    "swiatek-shnaider",
})

# ⏰ **还没推——正文是纯文本文件，改第一行不用重渲。**
_XHS_LEDE_LEGACY_还没推送 = frozenset({
    "bencic-townsend", "eala-mcnally", "gauff-sakkari",
    "jodar-fils-montreal-qf", "rybakina-osaka",
    "shelton-tien-montreal-sf", "swiatek-svitolina-toronto-sf",
})

_XHS_LEDE_LEGACY = _XHS_LEDE_LEGACY_已推送 | _XHS_LEDE_LEGACY_还没推送


def test_小红书标题不许用通稿导语开头():
    offenders = _xhs_lede_offenders()
    fresh = {k: v for k, v in offenders.items() if k not in _XHS_LEDE_LEGACY}
    assert not fresh, (
        f"这几条的小红书标题是通稿导语：{fresh}。第一行是信息流里最贵的一行，"
        f"「N号种子」打头或者把「用时」写进标题，等于把它让给了一个数据接口"
        f"字段——「网球有故事」那几条第一行写的是「四岁那年，外公塞给她一把"
        f"比她还高的球拍」，同一批人写得出来。"
    )
    scanned = sum(
        1 for p in SPEC_DIR.glob("*.xhs.txt")
        if (SPEC_DIR / f"{p.name[:-len('.xhs.txt')]}.json").is_file()
    )
    assert scanned >= 40, f"只扫到 {scanned} 份文案，判据的主语像是没了"


def test_小红书标题的豁免表只许减不许加():
    for slug in sorted(_XHS_LEDE_LEGACY):
        assert (SPEC_DIR / f"{slug}.xhs.txt").is_file(), \
            f"{slug} 这份文案已经没了，把它从豁免表里删掉"
    stale = _XHS_LEDE_LEGACY - set(_xhs_lede_offenders())
    assert not stale, (
        f"这几条的小红书标题已经不是通稿导语了，把它们从豁免表里删掉：{stale}"
        f"——这张表只许减不许加"
    )
