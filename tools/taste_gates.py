"""账号所有者的**口味**判据：做视频之前就拦掉，而不是做了一半再返工。

来路：账号所有者 2026-09-27「**总结我的口味和品味这种个性化的要求，形成一个
通用的规则在做视频前就拦掉，而不是说做了一半又返工**」。当天从全部提交史里
挖出 125 条口味规则（引语、被否的版本、被接受的版本），逐条拿全库验过误报：
能机械化、而且**已接受的产物零误报**的，落在这个模块里；判断题（「有没有吸引力」
「选图情绪对不对」）照旧留在 tennis-editorial，不硬凑判据。

这里的每一条都**只读 spec**，坐在 `build_match_reel.validate_spec`（`--dry-run`
0.2 秒就报）和采访线的入口检查链里，不碰源片、不联网。

| 判据 | 管什么 | 被否的原样（来路） |
|---|---|---|
| `hook_result_problem` | 赛场之上钩子第二行必须是**结果**（谁赢了谁／走到哪一步）；钩子不比全场总分差 | fernandez-andreeva「5比2被追成5比5／她连拿最后2局」→「钩子文案都看不出什么」 |
| `hook_jargon_problem` | 钩子里不许有要解释的术语和梗（破发、抢七、首秀、说晚安…） | bouzkova-kartal「最后一局破发到零」→「最后一局破发到 0 是啥意思」 |
| `copy_count_problem` / `rank_claim_problem` | 钩子和推送标题里同一个数只能有一个说法 | wu-walton 钩子「三个盘点」、推送标题「两个盘点」，已发 |
| `board_announce_problem` | 旁白不许把每一局按顺序报一遍谁发球 | eala-svitolina 12 段里 7 段在报 |
| `set_coverage_report` | 每一盘旁白至少提一句（**只报**） | rune-dimitrov「前面几盘都没讲」 |
| `ending_order_problem` | 片子收在时间上最晚的那个镜头上，握手之后不许再接回放 | zheng-burel 8 个版本：握手之后又接两段、外加第二遍回放 |
| `story_band_problem` | 交手史片每一场第一次出现都要贴 story_text 信息条 | sabalenka-rybakina-h2h v1 →「右上角，每场比赛对应的文字贴图也没有啊」 |

**三档执行，和仓库里别的口味闸同一个形状：**

| 谁写的 | 怎么办 |
|---|---|
| 手写的新 spec | **硬**——`--dry-run` 当场红 |
| `data/legacy_taste_gates.json` 里已发的老片子 | 放行（已发的不重渲）；**钩子冻的是原文**，改一个字就重新受管 |
| 自动产的 spec（`_production.status == ready_for_render`） | **只报**——那一头没有人写认领，做硬会把自动链卡成「今天没有候选」；判据文本照样印进日志（行首 `[口味·<块>]`） |

采访线的封面大标题术语：账号所有者 2026-09-27 ~23:00Z 答复**做硬**——手写的硬、
自动链没核没发的只报（和钩子同一个分法），见 `interview_taste_findings`。

⚠️ **这些闸不接模型。** 账号所有者 2026-09-27：「minimax 和 deepseek 都不要用，后续会
拿掉」——所以这里只读 spec（谁写的都一样判），**不回喂任何模型重写钩子，也不为
`repair_reel_spec` 的回喂去挑日志行首的写法**。判据
`tests/test_taste_gates.py::test_口味闸不接模型`。

⚠️ **钩子的豁免冻的是那一版钩子的原文，不是 slug。** 老规矩的豁免表按 slug
放行，于是一条老片子重写钩子时照样不受管——而「重写钩子」正是这批规矩最该
管住的动作。冻原文之后，改一个字就要按新规矩写。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_PATH = ROOT / "data" / "legacy_taste_gates.json"
ALLUSIONS_PATH = ROOT / "data" / "hook_allusions.json"


#: 口味闸要当成对象读的顶层键。
_OBJECT_KEYS = ("cover", "push", "_production")


def _obj(spec: dict, key: str) -> dict:
    """`spec[key]`，不是对象就当空的——各道闸单独调时不抛 AttributeError；
    形状不对由入口的 `shape_problem` 当成硬发现报出来（fail closed，不放行）。"""
    value = spec.get(key)
    return value if isinstance(value, dict) else {}


def shape_problem(spec: dict) -> str | None:
    """`cover`／`push`／`_production` 写成了字符串或列表：口味闸读不了这份 spec。

    评审 N（2026-09-27）：`requests/stories/zheng-usopen-icons.cover-v2.json` 那种
    `cover` 是字符串的形状，原来喂进来是一个 AttributeError 的 traceback；现在
    是一条读得懂的硬发现——手写的红、自动的报，**不静静放行**。
    """
    bad = [f"`{key}` 是 {type(spec[key]).__name__}" for key in _OBJECT_KEYS
           if spec.get(key) is not None and not isinstance(spec[key], dict)]
    if not bad:
        return None
    return ("口味闸读不了这份 spec：" + "、".join(bad)
            + "——这几个键要写成对象（{...}），比如 `cover` 里放 eyebrow／hook／title")


def is_auto(spec: dict) -> bool:
    """自动产的 spec：只报不拦（和 `_narration_craft` / `unvoiced_quote_problem` 同一个口径）。"""
    return _obj(spec, "_production").get("status") == "ready_for_render"


def _eyebrow(spec: dict) -> str:
    cover = _obj(spec, "cover")
    return str(cover.get("eyebrow") or spec.get("_column") or "")


def hook_lines_of(value) -> list[str]:
    """钩子/采访标题按行拆开：字符串按 `\\n`，列表按项（采访线的 `cover.title` 是列表）。"""
    if isinstance(value, list):
        raw = [str(x) for x in value]
    else:
        raw = str(value or "").split("\n")
    return [ln.strip() for ln in raw if ln.strip()]


def _hook_text(spec: dict) -> str:
    return "\n".join(hook_lines_of(_obj(spec, "cover").get("hook")))


# ── 豁免表 ──────────────────────────────────────────────────────────────

def load_legacy() -> dict:
    try:
        return json.loads(LEGACY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _frozen(section: str, slug: str, text: str, legacy: dict | None) -> bool:
    """这一条的**原文**还是冻进豁免表的那一版吗。改过一个字就不算。"""
    table = (load_legacy() if legacy is None else legacy).get(section) or {}
    return slug in table and table[slug] == text


# ════════════════════════════════════════════════════════════════════════
# ① 钩子第二行是结果：关键局面 ＋ 结果（口味规则 hook-key-moment-and-result）
# ════════════════════════════════════════════════════════════════════════
#
# 账号所有者 2026-09-25（mensik-nakashima 连否三版之后）：「**以后钩子文案只讲
# 重点或关键内容，以及结果**」；同日 bucsa-noskova：「封面钩子文案没交代赛果啊」；
# cobolli-jodar：「标题文案要让人看懂结果的」。
#
# 判据是「第二行里有没有一个**整场级**的结果」——不是有没有一个动词。
# ⚠️ 候选阶段那张宽表（裸的 丢/输/拿下/赢 都算结果）当场放过了三条被否的钩子：
# 「整场她只丢了一局／丢在自己的发球局」「他破了 再没输过一盘」「10个接发局／
# 一局也没拿下」——**丢的是一局、输的是一盘，那是过程不是结果**。所以：
#
#   强词（淘汰 / 逆转 / 挺进 / 夺冠 / 战胜…）       → 一定是结果
#   弱词（赢 / 输 / 拿下 / 拿到）                    → 宾语不是分/局/盘/点才算
#
# 量出来的账（2026-09-27，263 条赛场之上）：规矩定下之后（2026-09-25 13:21Z）
# 设的 18 条钩子 **0 条红**；20 个被否的历史钩子版本红 15 个（专门因「没交代赛果」
# 被否的 8 个红 7 个）；规矩之前的存量按原文冻进豁免表。同日评审后补全了结果词
# （过关／锁定／收进口袋／轮次名…）：被否的那 20 个一个没漏，豁免表 178 → 169。
# ⚠️ 规矩之后的钩子**补词表，不冻结**：豁免表只收规矩之前的存量（`_counts.hook_shape`
# 那句「规矩之后设的钩子 0 条在内」要一直成立）——评审 B2 的 fernandez-gibson 就是
# 这么处理的。

#: 轮次名按 CLAUDE.md 的口径（决赛／半决赛／1/4决赛／1/8决赛／第N轮）：第二行点到
#: 一个轮次，说的就是「走到哪一步」。「总决赛」是赛事名（「总决赛冠军」是身份），
#: 不算。
_ROUND_NAME = r"1/8决赛|1/4决赛|半决赛|(?<!总)决赛|第[一二三四1-4]轮|下一轮"
#: 评审 B2（2026-09-27）：fernandez-gibson 新加坡决赛的钩子「连赢8局夺下冠军」
#: 09-27 11:44Z 已推，而这张表只认两个字挨着的「夺冠」——合进 main 当场把一条
#: 已接受的决赛钩子判红。同一批补上常见的结果说法：夺下/夺得…冠、登顶、加冕、
#: 问鼎、闯入/杀入/挺入、跻身，以及输家那一侧的不敌/惜败/憾负。
#: ⚠️ 「闯入/杀入/挺进」后面接的是盘或抢七（「一路杀入决胜盘」「杀入了抢七」
#: 「闯入盘末」）就是过程，不算——「了」要放进否定前瞻里面：写成 ``入了?(?!…)``
#: 时「了?」会回溯成空，前瞻看到的是「了抢七」，照样放行。
#: ⚠️ 「争夺冠军」是赛前的说法（两人争的是冠军，谁拿到还没发生），「夺」前面是
#: 「争」就不算——复审第二轮 nit：``has_match_result('两人争夺冠军')`` 原来是 True。
_STRONG_RESULT = re.compile(
    r"淘汰|逆转|击败|掀翻|送走|横扫|翻盘|翻了?回来|赢了?回来|扳回来|晋级"
    r"|进了?(?:决赛|半决赛|\d+强|八强|四强|1/4决赛)|首进|捧杯|捧起[^，,]{0,4}杯"
    r"|(?:拿下|赢下|拿到|第一个|第一)[^，,]{0,6}冠军?|出局|止步|告负|收官|战胜"
    r"|过关|锁定|收进口袋|胜利|首冠|卫冕|会师|笑到最后|" + _ROUND_NAME
    + r"|胜(?![盘局分利])|负于|输给|赢(?:双打|单打)"
    r"|(?<!争)夺(?:下|得|取)?[^，,]{0,4}冠|登顶|加冕|问鼎"
    r"|(?:(?:闯|杀|挺)入|挺进)(?!了?(?:决胜|抢[七十]|第[一二三四五1-5]盘|盘末|局末))"
    r"|跻身|不敌|惜败|憾负")
#: 让「赢/输/拿下」变成**过程**而不是结果的那些宾语：分、局、盘、点、球、拍。
#: 「比分」「分钟」里的「分」不算（`(?<!比)分(?!钟)`）；「这场球」「赢球」「输球」
#: 里的「球」说的是整场，不是一分（`(?<![场赢输])球`，紧跟动词的「赢球」在下面判）。
_SUB_MATCH_UNIT = re.compile(r"局|(?<!比)分(?!钟)|盘|点|抢[七十]|(?<![场赢输])球|拍|ACE")
_WEAK_RESULT = re.compile(r"赢(?:下|了|得)?|输(?:了|掉)?|拿(?:下|了下来)|拿到")


def has_match_result(line: str) -> bool:
    """这一行说出了**整场**的结果没有。"""
    if _STRONG_RESULT.search(line):
        return True
    for m in _WEAK_RESULT.finditer(line):
        before = line[max(0, m.start() - 3):m.start()]
        after = re.split(r"[，,。 ]", line[m.end():m.end() + 5])[0]
        if re.search(r"(?:多|少)$", before):      # 多赢/少赢 = 总分差，不是结果
            continue
        if after.startswith("球"):               # 赢球 / 输球 = 整场
            return True
        if _SUB_MATCH_UNIT.search(before) or _SUB_MATCH_UNIT.search(after):
            continue                             # 赢了一局 / 丢一盘 = 过程
        if after.startswith("过"):               # 一次都没赢过 = 交手史
            continue
        return True
    return False


_NUM = r"(?:\d+|[零一二两三四五六七八九十百]+)"
#: 全场总分差（账号所有者 2026-09-19，看完 chung-nagal「全场只多赢一分」：
#: 「以后尽量避免比较全场得分只差几分……其实网球差距就在一两分的关键分，
#: 而不要把这个放在封面的钩子上」）。「只差一分被拖进决胜盘」是关键分，放行——
#: 所以不收「差 N 分」。「至少/最多」不是差值，前面挡掉。
#:
#: ⚠️ **这条规矩的正则只有一份，在 `taste_gates_extra.TOTAL_MARGIN`**——两个包
#: （wp/taste-gates-copy-strip 在这儿、wp/taste-gates-verify-rest 在那儿）各写过一份，
#: 合并时收成一份：那一份按 126 份自动草稿量过（「总分落后18分」这里原来认不得），
#: 也挡掉了这里原来会误伤的「全场多次破发」「全场一直领先」。钩子的形状闸
#: （`hook_result_problem`）和推送标题的总分闸（`total_margin_problem`）用的是同一个对象。
_TOOLS = str(Path(__file__).resolve().parent)
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
from taste_gates_extra import TOTAL_MARGIN as TOTAL_POINTS  # noqa: E402

#: 第一行的比分没说是哪一盘（「最后关头4比6落后」——4 比 6 是什么？）。**只报**：
#: 它也扫到了规矩之前被接受的 tsitsipas 第一行，做硬会误伤。
_SCORE = re.compile(_NUM + r"\s*(?:比|-|:|：)\s*" + _NUM)
_SET_LABEL = re.compile(
    r"首盘|次盘|第[一二三四五1-5]盘|决胜盘|抢[七十]|第[一二三四五六七八九十\d]+局|盘")


def hook_result_problem(spec: dict, *, legacy: dict | None = None) -> str | None:
    """「赛场之上」钩子：第二行交代结果；钩子不比全场总分差。"""
    if _eyebrow(spec) != "赛场之上":
        return None
    lines = hook_lines_of(_obj(spec, "cover").get("hook"))
    if not lines:
        return None
    slug = str(spec.get("slug") or "")
    if _frozen("hook_shape", slug, "\n".join(lines), legacy):
        return None
    cover = _obj(spec, "cover")
    bad = []
    if (len(lines) >= 2 and not has_match_result(lines[1])
            and not str(cover.get("_hook_shape_why") or "").strip()):
        bad.append(
            f"第二行「{lines[1]}」没交代结果——钩子两行：第一行写**关键局面**"
            "（在哪个关头处于什么局面），第二行写**结果**（谁赢了谁／走到哪一步："
            "淘汰、逆转、挺进8强、夺冠…）。只念这两行，不看网球的人也要说得出"
            "「谁赢了、赢得有多险」。\n"
            "    ✅「决胜盘一度落后／中岛布兰登逆转门西克」「次盘5比2被追平／7比5淘汰头号种子」\n"
            "    ❌「5比2被追成5比5／她连拿最后2局」「首盘告负／抢七七比三扳平」"
            "（只有过程——账号所有者：「钩子文案都看不出什么」「标题文案要让人看懂结果的」）\n"
            "    新闻点就是事件本身、没有赛果可讲（「威廉姆斯姐妹／时隔四年合体」）"
            "才写 `cover._hook_shape_why` 认领")
    total = TOTAL_POINTS.search("\n".join(lines))
    if total:
        bad.append(
            f"钩子在比全场总分差（「{total.group(0)}」）——账号所有者 2026-09-19："
            "「以后尽量避免比较全场得分只差几分……网球差距就在一两分的关键分，"
            "而不要把这个放在封面的钩子上」。换成关键分（几个破发点救下几个、"
            "第几个赛点兑现），或者拿人的来路当影子")
    if not bad:
        return None
    return ("封面钩子不合口味（账号所有者 2026-09-25：「以后钩子文案只讲重点或"
            "关键内容，以及结果」）：\n  - " + "\n  - ".join(bad))


_POINT_WORDS = {"0", "15", "30", "40", "零", "十五", "三十", "四十"}


def _is_point_score(score: str) -> bool:
    """「四十比三十」是局内比分（发球局里的分），不是盘里的局分——不问是哪一盘。"""
    parts = [p.strip() for p in re.split(r"比|-|:|：", score) if p.strip()]
    return len(parts) == 2 and all(p in _POINT_WORDS for p in parts) and any(
        p not in {"0", "零"} for p in parts)


def hook_score_label_report(spec: dict, *, legacy: dict | None = None) -> str | None:
    """**只报**：第一行出现比分，却没说是哪一盘的。

    冻进豁免表的老钩子不报——那是已发的片子，报了也没人改，只会把人训练成
    不看这一行。
    """
    if _eyebrow(spec) != "赛场之上":
        return None
    lines = hook_lines_of(_obj(spec, "cover").get("hook"))
    if not lines:
        return None
    slug, text = str(spec.get("slug") or ""), "\n".join(lines)
    if _frozen("hook_shape", slug, text, legacy) or _frozen("hook_jargon", slug, text, legacy):
        return None
    first = re.sub(r"抢[七十]", "", lines[0])
    m = next((x for x in _SCORE.finditer(first) if not _is_point_score(x.group(0))), None)
    if not m or _SET_LABEL.search(first[:m.start()]) or _SET_LABEL.search(first[m.end():m.end() + 2]):
        return None
    return (f"钩子第一行「{lines[0]}」有个比分，没说是哪一盘的——不看网球的人会问"
            "「这个比分是什么的比分？」（mensik-nakashima 第二版「最后关头4比6落后」"
            "就是这么被否的）。能加「首盘/决胜盘」就加，或者换成不带数字的局面")


# ════════════════════════════════════════════════════════════════════════
# ② 钩子里不许有要解释的术语和梗（口味规则 hook-no-jargon-or-allusion）
# ════════════════════════════════════════════════════════════════════════
#
# 账号所有者 2026-09-22：「最后一局破发到 0 是啥意思」——**连这个号的所有者都要
# 停下来问一句，刷到的人只会划走**；2026-09-25 读者评「德约对看台说晚安」
# 「莫名其妙的文案」；2026-09-25 mensik-nakashima「首秀」「7分里拿下6分」；
# **2026-09-27 账号所有者选定：钩子里「破发」「抢七」也禁，旁白照旧可以用**。
#
# 放行：赛点、盘点、决胜盘、局、盘——账号所有者 09-24 自己写过「首盘错过4个盘点」。
# 「一发」前面挡「第」：采访标题「世界第一发球胜赛」里的「第一发」不是一发。
HOOK_JARGON = re.compile(
    r"破发|抢七|抢十|(?<!第)一发(?!不可)|二发|(?<![A-Za-z])(?:ACE|[Aa]ce)(?![A-Za-z])"
    r"|爱司|爱局|(?<![A-Za-z])[Ll]ove(?![A-Za-z])|接发球?局|得分率|决胜局"
    r"|发球胜[赛盘]局|首秀|复仇|[\d一二两三四五六七八九十]+分里")


def hook_allusions() -> list[str]:
    """典故和梗：只从**真实的抱怨**里长出来，不预先猜。"""
    try:
        data = json.loads(ALLUSIONS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    return [str(x) for x in data.get("allusions") or [] if str(x).strip()]


def hook_terms_regex() -> re.Pattern:
    """`HOOK_JARGON` ＋ `data/hook_allusions.json` 里的典故拼成一条（典故那半不分大小写）。

    词表只有这一份：闸（`jargon_hits`）和开工前预检（`taste_preflight.HOOK_TERMS`）
    都从这里取——预检原来自己抄了一份，`ACE` 的边界写法已经和这里分了叉。
    """
    alts = "|".join(re.escape(a) for a in hook_allusions())
    return re.compile(HOOK_JARGON.pattern + (f"|(?i:{alts})" if alts else ""))


def jargon_hits(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(0) for m in hook_terms_regex().finditer(text)))


_JARGON_FIX = (
    "封面那一屏的全部价值就是一眼读懂，读不懂等于这一屏没有。换成零背景也读得懂的"
    "说法：「破发到零」→「一分没给」、「3个破发点全救下」→「3次机会全落空」、"
    "「抢七扳平」→「一分一分咬回来」；典故要么不用，要么当场讲明白。"
    "**旁白里照旧可以用这些词**——旁白有时间铺垫，说完还能解释半句")


def hook_jargon_problem(spec: dict, *, legacy: dict | None = None) -> str | None:
    """竖版短片（三个栏目）的 `cover.hook`：不许有要解释的术语和梗。

    认领口 `cover._hook_term_why` **只给「网球有故事」**——那一栏的片子可以
    本身就在讲这个术语（讲抢七规则的片子，钩子里有「抢七」是题目本身）；
    「赛场之上」没有这个口：账号所有者 2026-09-27 点名禁的就是那一栏。
    """
    text = _hook_text(spec)
    if not text:
        return None
    slug = str(spec.get("slug") or "")
    if _frozen("hook_jargon", slug, text, legacy):
        return None
    cover = _obj(spec, "cover")
    if (_eyebrow(spec) != "赛场之上"
            and str(cover.get("_hook_term_why") or "").strip()):
        return None
    hits = jargon_hits(text)
    if not hits:
        return None
    return (f"封面钩子里有要解释的术语／梗：{hits}（钩子「{text.replace(chr(10), '／')}」）——"
            "账号所有者 2026-09-22：「最后一局破发到 0 是啥意思」；2026-09-27 定的："
            "钩子里「破发」「抢七」也不用。" + _JARGON_FIX)


def summary_jargon_report(spec: dict) -> str | None:
    """**只报**：推送标题里的术语（全库 300 条里 45 条有，做硬会成一条常年红）。"""
    summary = str(_obj(spec, "push").get("summary") or "")
    hits = jargon_hits(summary)
    if not hits:
        return None
    return f"推送标题「{summary}」里有术语 {hits}——它和钩子印在同一张推送卡上，能换就换"


def interview_title_jargon_problem(spec: dict, *, legacy: dict | None = None) -> str | None:
    """采访线封面大标题（`cover.title`）——它就是采访片的钩子，同一条规矩。

    ⚠️ 规矩定下之后还有两条推出去的标题用了「首秀」（拉沃尔杯那两条），
    按原文冻进豁免表；认领口 `cover._title_term_why` 给「受访者说的就是这个词、
    标题在引他的话」这一种。
    """
    cover = _obj(spec, "cover")
    text = "\n".join(hook_lines_of(cover.get("title")))
    if not text:
        return None
    slug = str(spec.get("slug") or "")
    if _frozen("interview_title_jargon", slug, text, legacy):
        return None
    if str(cover.get("_title_term_why") or "").strip():
        return None
    hits = jargon_hits(text)
    if not hits:
        return None
    return (f"采访封面标题里有要解释的术语／梗：{hits}（「{text.replace(chr(10), '／')}」）——"
            "采访封面的大标题就是这条片子的钩子。" + _JARGON_FIX)


def explainer_question_jargon_problem(slug: str, opening: dict, *,
                                      legacy: dict | None = None) -> str | None:
    """字卡解说的封面问句（`_OPENINGS[slug]["question"]`）——那一屏的钩子。

    ⚠️ 只扫 `question`，不扫 `topic`：topic 是台头的小字说明，候选阶段扫进来的
    两条（「一发有钟，二发没有」「源于第五盘没有抢七」）都是片子本身在讲的规则。
    认领口 `hook_term_why`：片子讲的就是这个术语本身。这条线没有 `--dry-run`，
    判据坐在 tests/test_taste_gates.py（CI）。
    """
    text = str((opening or {}).get("question") or "")
    if not text or _frozen("explainer_question_jargon", slug, text, legacy):
        return None
    if str((opening or {}).get("hook_term_why") or "").strip():
        return None
    hits = jargon_hits(text)
    if not hits:
        return None
    return f"{slug} 的封面问句「{text}」里有要解释的术语／梗：{hits}——" + _JARGON_FIX


# ════════════════════════════════════════════════════════════════════════
# ③ 同一个数只能有一个说法：钩子 × 推送标题（口味规则 copy-fields-one-source-of-truth）
# ════════════════════════════════════════════════════════════════════════
#
# wu-walton-us-open-2026-r1：钩子改成「三个盘点一个没给」，`push.summary` 还写着
# 「两个盘点没给」——**推送卡上一张图两行字，一个数两个说法**，发了出去
# （91f23a50）。全部 1,180 个历史版本里它是唯一一次触发；现存 413 条零触发。
#
# ⚠️ **只比钩子和推送标题**，这两行印在同一张推送卡上、没有地方放上下文，
# 里面的数必然说的是同一件事。`push.lead` 和小红书首行不比：候选阶段扫进来当场
# 45 条误报，全是「真的、但说的是另一件事」（首盘二十七分钟 vs 全场七十二分钟、
# 她面对的破发点 vs 她拿到的破发点、15 个里兑现 2 个 = 浪费 13 个）。
# ⚠️ 名词只收**被计数的对象**，不收 局/盘/分钟：那三个在候选阶段 100% 是误报。

_CN_DIGIT = {"〇": 0, "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn_int(run: str) -> int | None:
    if run.isdigit():
        return int(run)
    total = part = 0
    seen = False
    for ch in run:
        if ch in _CN_DIGIT:
            part = _CN_DIGIT[ch]
            seen = True
        elif ch in "十百千":
            total += (part or 1) * {"十": 10, "百": 100, "千": 1000}[ch]
            part = 0
            seen = True
        else:
            return None
    return total + part if seen else None


_COUNT_NOUNS = ("接发球局", "接发局", "发球局", "破发点", "盘点", "赛点", "局点",
                "ACE", "双误", "连胜", "连败")
_NOUN_ALT = "|".join(sorted(map(re.escape, _COUNT_NOUNS), key=len, reverse=True))
_CNUM = r"(\d+|[零〇一二两三四五六七八九十百千]+)"
_RX_COUNT = re.compile(r"(?<![比\d.:：\-])(第)?" + _CNUM
                       + r"\s*(?:个|次|记)?\s*(" + _NOUN_ALT + ")", re.I)
_RX_BARE = re.compile(r"(?<![比\d.:：\-])(第)?" + _CNUM
                      + r"\s*(个|次)(?!\s*(?:" + _NOUN_ALT + "))")
_CAI_AFTER = re.compile(r"^[^，。、／/\n]{0,3}才")
_NEG_AFTER = re.compile(r"^\s*(?:都|也)?\s*(?:没|不|未)")


def counted_claims(text: str) -> dict[str, set[int]]:
    """名词 → 这一行对它说了哪些数。

    隐含的计数（每条都在已接受的文案里见过）：
      * 「一个X都没/也没」「没…一个X」 → 0
      * 「第N个X」「N个X…才」           → {N, N−1}（「第四个赛点才落地」＝前三个没兑现）
      * 同一行里提过 X 之后的裸「N个/N次」算 X 的（「赛点，菲斯连救三个」）
    """
    text = text or ""
    events: list[tuple[int, str, int]] = []
    anchors = [(m.start(), m.group(0).upper())
               for m in re.finditer(_NOUN_ALT, text, re.I)]
    for m in _RX_COUNT.finditer(text):
        value = cn_int(m.group(2))
        if value is None:
            continue
        noun = m.group(3).upper()
        vals = {value}
        after = text[m.end():m.end() + 4]
        before = text[max(0, m.start() - 5):m.start()]
        if m.group(1) or _CAI_AFTER.match(after):
            vals.add(value - 1)
        elif value == 1 and (_NEG_AFTER.match(after) or re.search(r"[没未不]", before)):
            vals = {0}
        events += [(m.start(), noun, v) for v in vals]
    counted = {p for p, _, _ in events}
    for m in _RX_BARE.finditer(text):
        if m.start() in counted:
            continue
        value = cn_int(m.group(2))
        prior = [n for p, n in anchors if p < m.start()]
        if value is None or not prior:
            continue
        after = text[m.end():m.end() + 4]
        vals = {value}
        if m.group(1) or _CAI_AFTER.match(after):
            vals.add(value - 1)
        elif value == 1 and _NEG_AFTER.match(after):
            vals = {0}
        events += [(m.start(), prior[-1], v) for v in vals]
    out: dict[str, set[int]] = {}
    for _, noun, v in events:
        out.setdefault(noun, set()).add(v)
    return out


def copy_count_clash(hook: str, summary: str) -> list[str]:
    """钩子和推送标题对同一个名词给了**完全不相交**的两组数。"""
    a, b = counted_claims(hook), counted_claims(summary)
    return [f"{noun}：钩子说 {sorted(a[noun])}，推送标题说 {sorted(b[noun])}"
            for noun in sorted(set(a) & set(b)) if not a[noun] & b[noun]]


def copy_count_problem(spec: dict, *, title_key: str = "hook") -> str | None:
    """reel 用 `cover.hook`，采访线用 `cover.title`（`title_key="title"`）。"""
    cover = _obj(spec, "cover")
    push = _obj(spec, "push")
    hook = "\n".join(hook_lines_of(cover.get(title_key)))
    summary = str(push.get("summary") or "")
    if not hook or not summary or str(push.get("_summary_count_why") or "").strip():
        return None
    clash = copy_count_clash(hook, summary)
    if not clash:
        return None
    return ("钩子和推送标题对同一个数说了两个说法（它们印在同一张推送卡上）："
            + "；".join(clash)
            + "——改钩子就要在同一次提交里连 `push.summary` 一起改（wu-walton 那条"
            "钩子「三个盘点」、推送标题「两个盘点」就这么发了出去）。两处真说的是"
            "两件事，写 `push._summary_count_why` 认领")


#: 声称的排名：只认「世界第N」「世界排名N」「排名(掉到/升到/来到/是)N」。
#: 种子序号不是排名（卢布列夫在蒙特利尔是十号种子、世界第十六）。
_RANK_CLAIM = re.compile(r"(?:世界第|世界排名|排名(?:掉到|升到|来到|是)?)"
                         r"\s*([0-9]+|[一二三四五六七八九十百千两]+)")


def rank_claims(text: str) -> list[int]:
    out = []
    for m in _RANK_CLAIM.finditer(text or ""):
        value = cn_int(m.group(1))
        if value is not None:          # 读不出来（「排名最高」）就跳过，别猜
            out.append(value)
    return out


def rank_claim_problem(spec: dict) -> str | None:
    """钩子和推送标题里写的排名，必须是 `cover.matchup`／`versus` 登记的那个数。

    账号所有者 2026-08-05「贴近比赛事实」——查卢布列夫排名时读成了维基榜单的
    **变化列**（「世界第九」，实为第十六），海报名条从 matchup 渲、钩子是手写的，
    同一张图上一个人两个名次。原来只活在 pytest 里（CI 才红，自动链一次都扫不到），
    现在坐进 `validate_spec`；测试 `test_钩子和文案里写的排名要和matchup对得上`
    改成调这里。
    """
    cover = _obj(spec, "cover")
    registered: set[int] = set()
    for who in cover.get("matchup") or []:
        if isinstance(who, dict) and isinstance(who.get("rank"), int):
            registered.add(who["rank"])
    versus = cover.get("versus")
    versus = versus if isinstance(versus, dict) else {}
    for side in ("top", "bottom"):
        panel = versus.get(side) or {}
        if isinstance(panel, dict) and isinstance(panel.get("rank"), int):
            registered.add(panel["rank"])
    if not registered:
        return None
    bad = []
    for where, text in (("cover.hook", _hook_text(spec)),
                        ("push.summary", str(_obj(spec, "push").get("summary") or ""))):
        for claimed in rank_claims(text):
            if claimed not in registered:
                bad.append(f"{where} 写着世界第 {claimed}")
    if not bad:
        return None
    return ("钩子/推送标题里的排名和 matchup 登记的对不上：" + "；".join(bad)
            + f"——matchup 登记的是 {sorted(registered)}。海报名条从 matchup 渲，"
            "同一张图上一个人不能有两个名次")


# ════════════════════════════════════════════════════════════════════════
# ④ 旁白讲清走向：不逐局报发球；每一盘至少一句（后者只报）
#   （口味规则 narration-match-flow-every-set）
# ════════════════════════════════════════════════════════════════════════

#: 「轮到她发球」这类报幕。原来只活在 `test_旁白不许把每一局都念一遍` 里。
ANNOUNCE = re.compile(
    r"轮到.{0,4}发球"
    r"|自己的?发球局"
    r"|对面的?发球局"
    r"|对面发球(?!局)"
    r"|(?:紧接着|下一局|这一局)[^。；]{0,6}发球局")
#: 卡密度不卡单次：❌ eala-svitolina 58%（7/12）；✅ wong-gea 20%、wang-pareja 11%。
BOARD_SHARE_MAX = 0.25
#: 发在这条规矩之前、只许减不许加（自检在 tests/test_taste_gates.py）。
BOARD_ANNOUNCE_LEGACY = frozenset({"eala-svitolina"})


def _quote_text(raw) -> str:
    if isinstance(raw, list):
        return " ".join(str(x if isinstance(x, str) else (x or {}).get("text", "")) for x in raw)
    return str(raw or "")


def board_announce_share(spec: dict) -> tuple[int, int, float | None]:
    """(报幕段数, 有旁白的段数, 占比)；有旁白的段不足 5 段时占比为 None。"""
    segs = [s for s in spec.get("segments") or []
            if isinstance(s, dict) and str(s.get("narration") or "").strip()]
    if len(segs) < 5:
        return 0, len(segs), None
    hit = [s for s in segs
           if ANNOUNCE.search(str(s.get("narration") or "") + _quote_text(s.get("quote")))]
    return len(hit), len(segs), len(hit) / len(segs)


def board_announce_problem(spec: dict, *, legacy: frozenset | None = None) -> str | None:
    slug = str(spec.get("slug") or "")
    if slug in (BOARD_ANNOUNCE_LEGACY if legacy is None else legacy):
        return None
    hit, total, share = board_announce_share(spec)
    if share is None or share <= BOARD_SHARE_MAX:
        return None
    return (f"旁白把每一局按顺序报了一遍：{hit}/{total} 段（{share:.0%}）在报「谁在发球」"
            f"（上限 {BOARD_SHARE_MAX:.0%}）——记分条上一直写着，说了等于没说。"
            "小红书读者：「她发球，她接发。。。她发球，她接发」。走向讲四个点"
            "（谁领先 → 谁追上 → 转折在哪 → 怎么收），不是每一局都交代一次开球权")


_ORDINAL_SET = {
    1: r"首盘|第一盘|第1盘|第 ?1 ?盘|开盘|头一盘",
    2: r"次盘|第二盘|第2盘|第 ?2 ?盘",
    3: r"第三盘|第3盘|第 ?3 ?盘",
    4: r"第四盘|第4盘|第 ?4 ?盘",
    5: r"第五盘|第5盘|第 ?5 ?盘",
}
_DECIDER = r"决胜盘|决胜局|抢十|决胜抢|超级抢七|长盘"
_CN_SMALL = "零一二三四五六七八九十"


def _cn_small(n: int) -> str:
    return _CN_SMALL[n] if 0 <= n <= 10 else str(n)


def _set_score_pat(a: int, b: int) -> str:
    alts = {f"{a}-{b}", f"{b}-{a}", f"{a}比{b}", f"{b}比{a}", f"{a} 比 {b}", f"{b} 比 {a}",
            f"{_cn_small(a)}比{_cn_small(b)}", f"{_cn_small(b)}比{_cn_small(a)}"}
    return "|".join(re.escape(x) for x in alts)


def set_coverage_report(spec: dict) -> str | None:
    """**只报**：`cover.result` 里的某一盘，旁白一句都没提。

    账号所有者 2026-09-20（rune-dimitrov 第一版）：「**内容太单薄了，前面几盘都
    没讲**」。宽口径（盘序、盘分、「先丢一盘」、决胜盘、抢七都算提到）在 256 条
    存量上只报 2 条；严口径能抓到 rybakina-samsonova（决胜盘只在冷开场出现），
    但误报 21 条，所以不上。认领口 `_set_coverage_why`。
    """
    if _eyebrow(spec) != "赛场之上" or str(spec.get("_set_coverage_why") or "").strip():
        return None
    result = _obj(spec, "cover").get("result")
    sets = re.findall(r"(\d{1,2})-(\d{1,2})(?:\((\d+)\))?", str(result or ""))
    n = len(sets)
    if n < 2:
        return None
    text = "\n".join(str(s.get("narration") or "") for s in spec.get("segments") or []
                     if isinstance(s, dict))
    missing = []
    for i, (a, b, tb) in enumerate(sets, 1):
        pats = [_ORDINAL_SET.get(i, "$^")]
        if i == 1:
            pats.append(r"先(?:丢|输|赢|拿|下)了?(?:一|这一)盘")
        if i == n:
            pats.append(_DECIDER)
        if n == 2 and i == 2:
            pats.append(r"两盘|直落|连下两盘|再下一城")
        pats.append(_set_score_pat(int(a), int(b)))
        if tb:
            pats.append(r"抢七|抢十")
        if not re.search("|".join(pats), text):
            missing.append(f"第 {i} 盘（{a}-{b}）")
    if not missing:
        return None
    return ("旁白一句没提：" + "、".join(missing)
            + "——账号所有者 2026-09-20：「前面几盘都没讲」。每一盘至少一句"
            "（怎么丢的、怎么扳回来的），真不用讲写 `_set_coverage_why`")


# ════════════════════════════════════════════════════════════════════════
# ⑤ 收在时间上最晚的那个镜头：握手之后不许再接回放（口味规则 post-win-celebration-kept）
# ════════════════════════════════════════════════════════════════════════
#
# 账号所有者 2026-09-05（zheng-keys）「不要裁剪后面获胜后的镜头，要保留足够多的
# 细节」、2026-09-11「每段视频最后肯定要以最后一球作为结束」。zheng-burel 连着
# 8 个版本把握手之后的画面（第 8–9 段）排在**第二遍回放**之前——片子最后一个
# 镜头不是时间上最晚的那一刻。`ending_payoff_problem` 对这 8 个版本全是 PASS。
#
# 判据：从「倒回比赛前段」那一段起算正文；正文**最后一段**的 end 必须够到正文里
# 出现过的最晚源片时刻（容差 0.5s）。「握手完不完整、有没有捧杯」看画面，这条闸
# 够不着，留给预览和提示词。存量 236 条可判的只红 3 条，全是 08-03..08-13 发的。
ENDING_ORDER_TOL = 0.5
ENDING_ORDER_LEGACY = frozenset({"eala-pegula-final", "osaka-mertens", "shelton-tien-montreal-sf"})


def ending_order_problem(spec: dict, *, legacy: frozenset | None = None) -> str | None:
    if _eyebrow(spec) != "赛场之上":
        return None
    slug = str(spec.get("slug") or "")
    if slug in (ENDING_ORDER_LEGACY if legacy is None else legacy):
        return None
    raw = [s for s in spec.get("segments") or [] if isinstance(s, dict)]
    if len(raw) < 2 or raw[0].get("image"):
        return None
    declared = spec.get("sources")
    primary = str(next(iter(declared))) if isinstance(declared, dict) and declared else ""
    source = str(raw[0].get("source", primary))
    try:
        first_start = float(raw[0]["start"])
    except (KeyError, TypeError, ValueError):
        return None
    body: list[tuple[int, float, float]] = []
    for index, seg in enumerate(raw[1:], 2):
        if seg.get("image") or str(seg.get("source", primary)) != source:
            continue
        try:
            body.append((index, float(seg["start"]), float(seg["end"])))
        except (KeyError, TypeError, ValueError):
            continue
    rewind = next((k for k, (_, start, _) in enumerate(body) if start + 0.25 < first_start), None)
    if rewind is None:
        return None                   # 没有倒叙：不是冷开场结构，这条不管
    body = body[rewind:]
    last = body[-1]
    latest = max(body, key=lambda item: item[2])
    if last[2] + ENDING_ORDER_TOL >= latest[2]:
        return None
    last_seg = raw[last[0] - 1]
    if str(last_seg.get("_ending_order_why") or "").strip():
        return None
    return (f"片子没收在时间上最晚的那个镜头：正文最后一段（第 {last[0]} 段）收在源片 "
            f"{last[2]:.2f}s，可第 {latest[0]} 段已经放到了 {latest[2]:.2f}s——"
            "握手／离场这些赢球之后的画面排在了一段更早的画面前面（zheng-burel 8 个版本"
            "就是握手之后又接回放）。账号所有者：「不要裁剪后面获胜后的镜头」「每段视频"
            "最后肯定要以最后一球作为结束」。把赢球之后的镜头挪到最后、按时间顺序连着放；"
            "真要这么收，在最后一段写 `_ending_order_why`")


# ════════════════════════════════════════════════════════════════════════
# ⑥ 交手史片：每一场第一次出现都要贴 story_text 信息条（口味规则 story-info-band-per-match）
# ════════════════════════════════════════════════════════════════════════
#
# 账号所有者 2026-09-11（sabalenka-rybakina-h2h 已发的 v1）：「**右上角，每场比赛
# 对应的文字贴图也没有啊**」。
#
# ⚠️ **只管交手史片**。宽口径（每一条「网球有故事」、每一个源）在 38 条已接受的
# 片子里红 35 条——那些是拿比赛画面当 B-roll 讲规则的片子，账号所有者从没要过
# 信息条。交手史片三条已接受的全过，被否的 v1 红在第 2/4/5 段。
_H2H_SLUG = re.compile(r"h2h|meetings")


def is_h2h_story(spec: dict) -> bool:
    if _eyebrow(spec) != "网球有故事":
        return False
    cover = _obj(spec, "cover")
    if str(cover.get("story_kind") or "") == "h2h":
        return True
    blob = f"{cover.get('hook') or ''} {cover.get('topic') or ''}"
    return "交手" in blob or bool(_H2H_SLUG.search(str(spec.get("slug") or "")))


def _match_groups(keys) -> dict[str, str]:
    """同一场的不同剪辑合成一组：一个键是另一个的前缀（`ao2023` / `ao2023cup`）。"""
    keys = [str(k) for k in keys]
    group = {}
    for k in keys:
        root = k
        for other in keys:
            if other != k and k.startswith(other) and len(other) >= 3:
                root = other
        group[k] = root
    return group


def story_band_problem(spec: dict) -> str | None:
    if not is_h2h_story(spec):
        return None
    segs = [s for s in spec.get("segments") or [] if isinstance(s, dict)]
    sources = spec.get("sources")
    group = _match_groups(sources.keys() if isinstance(sources, dict) else [])
    seen: set[str] = set()
    missing = []
    for i, seg in enumerate(segs):
        src = seg.get("source")
        if not src or seg.get("image"):
            continue
        g = group.get(str(src), str(src))
        if g in seen:
            continue
        seen.add(g)
        if ((seg.get("inset") or {}).get("kind") == "story_text"
                or (i > 0 and (segs[i - 1].get("title_card") or segs[i - 1].get("stat_card")))
                or str(seg.get("_band_skip_why") or "").strip()):
            continue
        if i == 0 and not str(seg.get("narration") or "").strip():
            continue                  # 无旁白的冷开场
        missing.append(f"第 {i + 1} 段（{src}）")
    if not missing:
        return None
    return ("交手史片里每一场第一次出现，右上角都要贴 story_text 信息条"
            "（日期·赛事轮次｜赢家｜整场比分｜一句意义）：" + "、".join(missing)
            + " 没有——账号所有者 2026-09-11：「右上角，每场比赛对应的文字贴图也没有啊」。"
            "前一段是标题卡/数据卡的不用贴；真不用贴写这一段的 `_band_skip_why`")


# ════════════════════════════════════════════════════════════════════════
# 入口
# ════════════════════════════════════════════════════════════════════════

def reel_taste_scoped(spec: dict) -> list[tuple[str, bool, str]]:
    """[(块, 硬不硬, 判据原文)]。块（钩子／文案／旁白／窗口／信息条）只是告诉人去哪儿改；
    硬的那几条对自动 spec 也只报，由调用方按 `is_auto` 分流。"""
    shape = shape_problem(spec)
    if shape:
        return [("形状", True, shape)]
    hard = [(label, p) for label, p in (
        ("钩子", hook_result_problem(spec)),
        ("钩子", hook_jargon_problem(spec)),
        ("文案", copy_count_problem(spec)),
        ("文案", rank_claim_problem(spec)),
        ("旁白", board_announce_problem(spec)),
        ("窗口", ending_order_problem(spec)),
        ("信息条", story_band_problem(spec)),
    ) if p]
    soft = [(label, p) for label, p in (
        ("钩子", hook_score_label_report(spec) if not hard else None),
        ("文案", summary_jargon_report(spec)),
        ("旁白", set_coverage_report(spec)),
    ) if p]
    return [(lb, True, p) for lb, p in hard] + [(lb, False, p) for lb, p in soft]


def reel_taste_findings(spec: dict) -> tuple[list[str], list[str]]:
    """(硬的, 只报的)。硬的那一组对自动 spec 也只报，由调用方按 `is_auto` 分流。"""
    scoped = reel_taste_scoped(spec)
    return [p for _, h, p in scoped if h], [p for _, h, p in scoped if not h]


def interview_is_auto(spec: dict) -> bool:
    """自动链写的、还没人核也还没发的采访 spec——和 `build_interview_request.
    unverified_auto_spec` 是**同一个判据**（章 `auto_pending` ＋ 没被 `_protected`
    销章），不另写一份。读不到那个模块就当手写的（fail closed：硬）。"""
    if not isinstance(spec, dict) or spec.get("transcript_verification") != "auto_pending":
        return False
    try:
        from build_interview_request import unverified_auto_spec  # noqa: PLC0415
    except ImportError:
        return False
    return unverified_auto_spec(spec)


def interview_taste_findings(spec: dict, *, auto: bool | None = None
                             ) -> tuple[list[str], list[str]]:
    """采访线：(硬的, 只报的)。

    硬：标题和推送标题同一个数只能有一个说法（规则书 `copy-fields-one-source-of-truth`
    写明管 reel／采访／字卡三条线）——谁写的都硬（自动转正的模板标题结构上碰不到它）。

    封面大标题里的术语：账号所有者 2026-09-27 ~23:00Z 答复**做硬**（原来只报，
    因为规则书那条写的是 reel 和字卡、O6 说的是「钩子」，实现时自己延伸的要等他确认）。
    分法和「赛场之上」的钩子一样：**手写的硬，自动链没核没发的只报**
    （`interview_is_auto`；`auto` 显式传进来就按它）。已发的 11 条按原文冻在
    `legacy_taste_gates.json` 的 `interview_title_jargon`，只许减不许加。
    """
    shape = shape_problem(spec)
    if shape:
        return [shape], []
    hard = [p for p in (copy_count_problem(spec, title_key="title"),) if p]
    jargon = interview_title_jargon_problem(spec)
    if not jargon:
        return hard, []
    if interview_is_auto(spec) if auto is None else auto:
        return hard, [jargon]
    return hard + [jargon], []
