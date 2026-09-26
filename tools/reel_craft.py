"""竖版短片的**文案手艺**判据：技战术、复读、句式模子。

来路：账号所有者 2026-09-19 转达读者的话——「**文案不专业，剪辑也不专业，
技战术也交代不清楚**」。三句话各有一个量得出来的根子，都不是「写得不够好」
这种判断题，而是结构性的缺口：

| 读者说的 | 装闸那天全库量出来的 |
|---|---|
| 技战术交代不清楚 | 249 条里 **189 条（76%）真正的球路描述不足 2 段**——其中 169 条（68%）连一句都没有 |
| 文案不专业 | `heide-wawrinka-davis-cup-2026-wg1` 相邻两段**说的是同一句话**（相似度 0.95）；22 条片子把同一个句式重复了 5 次以上，最高 10 次 |
| 剪辑不专业 | 段尾切在一分打完之前——**那一条已经有闸了**（`build_match_reel.mid_point_findings`，2026-09-19 落的硬闸），这个模块不重复它 |

⚠️ **「旁白要有技战术拆解」这条规矩 2026-08-21 就写下来了**
（`.claude/skills/tennis-editorial/SKILL.md`「⭐ 旁白要有技战术拆解」），
一个月之后 76% 的片子球路描述不足两段。**一条只写在文档里、没有判据的规矩，
拦不住下一个会话**——这是 CLAUDE.md 反复记的那个形状，这次轮到它自己。

⚠️ **这三条都只读 spec，不碰源片**，所以坐在 `validate_spec` 里，
`--dry-run` 0.2 秒就报，不用等七分钟的 render。
"""

from __future__ import annotations

import difflib
import re

#: 「这一球是怎么打的 / 打到哪儿」——**只收球路本身**，不收比分也不收统计。
#:
#: ⚠️ **分界是「换一场球还成不成立」**：「反手直线」换一场球就是另一回事，
#: 它描述的是这一球；「一发进球率百分之七十九」「破发点五取二」换谁都能填，
#: 那是统计。读者说的「技战术交代不清楚」缺的是前者——`ruud-te` 那条 14 段
#: 里统计词满屏，球路描述只有 1 段。
#:
#: ⚠️ **这张表宁可宽一点**：它是「必须有」的检测器，漏认一个合格写法就是
#: 一次误报，而误报会把人训练成不看这道闸（CLAUDE.md 反复记的那条）。
#:
#: ⚠️ **2026-09-19 第一次真用它写片子，当场漏认三个**：`高压`（tennisnow 写的
#: 「leaping high smash」，中文标准叫法就是高压）、`底线`、`穿越`——三个都是
#: 最基本的球路词，而一条写着「一记跳起高压打飞了」的合格旁白会被判成
#: 「没有球路描述」。**判据装好之后要自己拿它写一遍**，光反向验证测不出
#: 「该认的没认」这一面（`_ABSOLUTE_CLAIM_RE` 认不出计数式全称断言，是同一个形状）。
SHOT_WORDS: tuple[str, ...] = (
    # 用哪只手、什么球
    "正手", "反手", "双反", "单反", "切削", "削球", "上旋", "平击",
    # 打到哪儿
    "直线", "斜线", "对角", "中路", "外角", "内角", "追身", "落点",
    "角度", "宽度", "深区", "压深", "反手位", "压反手",
    # 网前与头顶
    "上网", "截击", "半截击", "网前", "小球", "放短", "高吊", "挑高",
    "过顶", "扣杀", "高压", "穿越", "发球上网",
    # 相持与站位
    "底线", "相持", "回合", "抢攻", "调动", "变线", "退台", "抢上升",
    "站位", "拉开", "撕开", "打穿",
    # ⚠️ 下面三个**两用**：「第二个盘点对手主动失误」是球路描述（那一分怎么
    # 丢的），「非受迫失误三十四比十五」是统计行。靠 `_STAT_LINE` 分开，见下。
    "制胜分", "主动失误", "非受迫失误",
)

#: 只在统计口径里出现的那三个词，单独记一份。
_STAT_ONLY_WORDS = ("制胜分", "主动失误", "非受迫失误")

#: 统计行的形状：带百分比，或者「N 比 M」这种两边对着数的写法。
#:
#: ⚠️ **为什么要这一刀**：`mensik-tien-davis-cup-2026-q2` 只有一句真的球路
#: 描述（「把门西克左右调动，用满整个球场的宽度」），却靠第 11 段
#: 「非受迫失误三十四比十五」凑满了两段——**那是一行统计，不是在讲这一球
#: 怎么打的**。读者说的「技战术交代不清楚」缺的正是后者，一行统计顶上来
#: 等于这道闸自己放水。
_STAT_LINE = re.compile(
    r"百分之|[零一二三四五六七八九十百\d]+\s*比\s*[零一二三四五六七八九十百\d]+")

#: 句式模子：同一个模子在一条片子里反复出现，读起来就是流水账。
#: ⚠️ 每一条都要**只认那个模子**，别认它里面的词——「破发点」本身没问题，
#: 「N 个破发点」连说五遍才是问题。
SENTENCE_MOLDS: tuple[tuple[str, str], ...] = (
    ("「N 个破发点/盘点/赛点」", r"[两三四五六七八九十\d]+个(?:破发点|盘点|赛点|局点)"),
    ("「N 个点全救回来了」", r"(?:破发点|盘点|赛点|局点)[^。！？]{0,14}(?:全救|都救|救了回来|救下)"),
    ("「X 比 Y，谁发球」", r"比[零一二三四五六七八九十]+[，,][^。！？]{0,8}发球"),
)

#: 同一个模子最多出现几次。22 条存量超标（9%），最高的
#: `comeback-five-love-down` 把「N 个破发点」说了 10 遍。
MOLD_MAX = 4

#: 相邻两段旁白的相似度上限。**0.80 是量出来的，不是拍的**：
#: 全库只有 `heide-wawrinka-davis-cup-2026-wg1` 越线（0.95，真复读），
#: 而 `tsitsipas-royer` 的「第一个，没了。/ 第二个，也没了。」正好 0.80
#: ——那是**有意的排比**，不是复读，所以阈值取严格大于 0.80 把它放过。
#: ⚠️ 再松到 0.75 就会把那条排比误伤，这是这个数的下界。
ECHO_MAX = 0.80

#: 「赛场之上」至少要有几段带球路描述。
#: 全库 249 条里 189 条（76%）不足 2 段（其中 169 条一句都没有），最好的一条是 5 段。
#: 2 是「转折点至少展开两次」——不是每一分都要讲怎么打的（那条边界写在
#: 「⭐ 旁白要有技战术拆解」那一节里）。
SHOT_MIN_SEGMENTS = 2



#: 装闸那天（2026-09-19）已经发出去的、球路描述不足 2 段的片子：**188 条**。
#: 已发的不重渲（CLAUDE.md 老规矩），所以它们只报不拦。
#: ⚠️ **只许减不许加**——写新片子时把某一条从这张表里划掉，是这条线唯一
#: 该有的方向。表自带自检（`test_三张手艺豁免表只许减不许加且每条都真的存在`）。
SHOT_CRAFT_LEGACY = frozenset({
    "alcaraz-faria-us-open-2026-r2",
    "alexandrova-sabalenka",
    "altmaier-musetti",
    "andreeva-gauff",
    "anisimova-bartunkova",
    "anisimova-eala",
    "anisimova-noskova",
    "arango-venus",
    "auger-aliassime-cerundolo",
    "baez-dimitrov",
    "bartunkova-charaeva",
    "bejlek-keys-cincinnati-2026-qf",
    "bejlek-pliskova",
    "bejlek-sabalenka",
    "bencic-eala",
    "bencic-townsend",
    "berrettini-wawrinka-us-open-2026-r1",
    "boisson-krueger",
    "borges-rublev",
    "boulter-volynets",
    "bouzkova-jovic",
    "bu-jodar-us-open-2026-r1",
    "bu-zhengmichael-us-open-2026-r2",
    "bucsa-chwalinska",
    "bucsa-gauff-us-open-2026-r3",
    "chwalinska-gibson",
    "cirstea-bartunkova",
    "cirstea-kalinskaya",
    "cirstea-pegula",
    "cobolli-blockx",
    "cobolli-jodar",
    "djokovic-tirante",
    "eala-anisimova",
    "eala-fernandez",
    "eala-mcnally",
    "eala-osaka",
    "eala-parks",
    "eala-pegula-final",
    "eala-ruse",
    "eala-stoiana-us-open-2026-r1",
    "eala-svitolina",
    "eala-zheng",
    "faria-shelton",
    "fernandez-andreeva",
    "fery-deminaur",
    "fils-cobolli-cincinnati-2026-sf",
    "fils-tiafoe-cincinnati-2026-final",
    "fils-tirante",
    "fonseca-ruud",
    "fonseca-van-de-zandschulp",
    "fritz-cerundolo-us-open-2026-r3",
    "fritz-jodar-final",
    "fritz-michelsen",
    "fritz-nakashima-cincinnati-2026-qf",
    "fritz-oconnell",
    "gauff-bejlek-cincinnati-2026-sf",
    "gauff-bouzkova",
    "gauff-kostyuk-cincinnati-2026-qf",
    "gauff-li",
    "gauff-pegula-cincinnati-2026-final",
    "gauff-sakkari",
    "gauff-samsonova",
    "gea-shapovalov",
    "gea-van-de-zandschulp-us-open-2026-r4",
    "halys-deminaur",
    "heide-wawrinka-davis-cup-2026-wg1",
    "jodar-fils-montreal-qf",
    "jodar-shapovalov",
    "jodar-tabilo",
    "kenin-lys",
    "keys-bondar-us-open-2026-r2",
    "khachanov-blockx-us-open-2026-qf",
    "kostyuk-andreeva",
    "kovacevic-khachanov",
    "krejcikova-bejlek",
    "landaluce-draper",
    "lehecka-fils",
    "maria-yastremska",
    "medvedev-damm",
    "medvedev-zandschulp",
    "mensik-tien-davis-cup-2026-q2",
    "musetti-faria",
    "nakashima-borges",
    "nakashima-jodar-montreal-sf",
    "nakashima-medvedev",
    "navarro-kalinina",
    "nishikori-shang",
    "noskova-boulter",
    "noskova-mcnally",
    "noskova-tauson",
    "osaka-fernandez",
    "osaka-mertens",
    "ostapenko-frech",
    "parry-mertens",
    "paul-cobolli",
    "pegula-anisimova",
    "pegula-navarro",
    "pegula-rakhimova",
    "pegula-swiatek-cincinnati-2026-sf",
    "pegula-waltert",
    "potapova-venus",
    "putintseva-bencic-us-open-2026-r1",
    "rublev-merida-us-open-2026-r2",
    "rublev-virtanen-us-open-2026-r1",
    "ruud-te-davis-cup-2026-wg1",
    "rybakina-frech",
    "rybakina-gauff-toronto-sf",
    "rybakina-li",
    "rybakina-osaka",
    "rybakina-osaka-us-open-2026-r4",
    "rybakina-samsonova",
    "rybakina-shnaider",
    "sabalenka-gibson",
    "sabalenka-pegula-us-open-2026-sf",
    "sabalenka-wang",
    "shang-darderi-montreal-2026",
    "shang-rublev",
    "shang-vallejo",
    "shelton-fonseca",
    "shelton-mensik",
    "shelton-tien-montreal-sf",
    "shnaider-chwalinska",
    "shnaider-pegula",
    "snigur-keys",
    "sonmez-anisimova",
    "sonmez-kasatkina",
    "stearns-tauson",
    "svitolina-alexandrova",
    "svitolina-anisimova",
    "swiatek-arango",
    "swiatek-bouzkova-us-open-2026-r3",
    "swiatek-golubic",
    "swiatek-kostyuk",
    "swiatek-parry",
    "swiatek-rybakina-cincinnati-2026-qf",
    "swiatek-sakkari",
    "swiatek-shnaider",
    "swiatek-svitolina-toronto-sf",
    "tiafoe-auger-aliassime",
    "tiafoe-musetti-cincinnati-2026-qf",
    "tiafoe-nakashima-cincinnati-2026-sf",
    "tirante-fritz",
    "tirante-landaluce",
    "tirante-mensik",
    "townsend-osorio",
    "townsend-rybakina",
    "trungelliti-medvedev",
    "tsitsipas-auger-aliassime",
    "tsitsipas-fils-us-open-2026-r1",
    "tsitsipas-royer",
    "wang-arango-us-open-2026-r1",
    "wang-kalinskaya-us-open-2026-r2",
    "wang-kasatkina",
    "wang-pareja",
    "wang-samsonova",
    "wang-vandewinkel",
    "wang-vekic",
    "wangxiyu-fernandez",
    "wangxiyu-keys",
    "wangxiyu-timofeeva",
    "williams-kenin-us-open-2026-r1",
    "williams-sisters-cincinnati",
    "wong-brooksby",
    "wong-gea",
    "wong-lehecka",
    "wong-paul-us-open-2026-r1",
    "wu-alcaraz-us-open-2026-r3",
    "wu-duckworth-us-open-2026-r2",
    "wu-walton-us-open-2026-r1",
    "zhang-day",
    "zhang-fernandez-us-open-2026-r1",
    "zhang-ostapenko",
    "zhang-putintseva",
    "zhang-sabalenka",
    "zheng-burel-us-open-2026-q2",
    "zheng-keys-us-open-2026-r3",
    "zheng-liutova-us-open-2026-r1",
    "zheng-putintseva-us-open-2026-r2",
    "zheng-rybakina",
    "zheng-swiatek-us-open-2026-r4",
    "zverev-atmane",
    "zverev-griekspoor",
    "zverev-khachanov-us-open-2026-sf",
    "zverev-norrie",
    "zverev-paul",
    "zverev-shelton-us-open-2026-final",
    "zverev-sonego-us-open-2026-r1",
    "zverev-vandezandschulp-us-open-2026-qf",
})


#: 相邻段复读的存量：**只有一条**，就是这条规矩的来路本身。
#: 已经推过微信了，不重渲；留在这儿是为了让判据对新片子是硬的。
ECHO_LEGACY = frozenset({
    "heide-wawrinka-davis-cup-2026-wg1",
})


#: 同一句式用超过 MOLD_MAX 次的存量：22 条（9%）。
MOLD_LEGACY = frozenset({
    "bartunkova-charaeva",
    "chung-nagal-davis-cup-2026",
    "cirstea-bartunkova",
    "comeback-five-love-down",
    "eala-osaka",
    "eala-stoiana-us-open-2026-r1",
    "eala-svitolina",
    "gauff-bouzkova",
    "jodar-tabilo",
    "keys-bondar-us-open-2026-r2",
    "noskova-boulter",
    "osaka-mertens-us-open-2026-r3",
    "rakhimova-krejcikova-us-open-2026-r1",
    "swiatek-bouzkova-us-open-2026-r3",
    "tien-monfils-us-open-2026-r2",
    "wang-kalinskaya-us-open-2026-r2",
    "wangxiyu-timofeeva",
    "williams-kenin-us-open-2026-r1",
    "wong-gea",
    "zheng-keys-us-open-2026-r3",
    "zheng-rybakina",
    "zheng-swiatek-us-open-2026-r4",
})


#: ⭐ 配音里不许出现「解说说」三个字。
#:
#: 账号所有者 2026-09-26：「**配音的 tts 里不要再说解说说这三个字了**」。
#: 「解说说，这一拍太漂亮了」这种转述，在 TTS 里是两个「说」连读，而且把转播的话
#: 换成我们的声音再说一遍——要引解说就留原声配双语字幕（CLAUDE.md「精彩的原声
#: 解说要留下来」），要讲就直接讲那一拍，不必借解说的嘴。
#: 管的是**进 TTS 的文本**：`cover.narration` 和 `segments[].narration`。
COMMENTATOR_SAID = "解说说"

#: 定规矩那天已经发出去的：只许减不许加，自检在 tests/test_reel_craft.py。
COMMENTATOR_SAID_LEGACY = frozenset({
    "boulter-volynets",
    "bucsa-noskova-bjk-cup-2026-sf",
    "chung-nagal-davis-cup-2026",
    "chwalinska-townsend-us-open-2026-r1",
    "cobolli-jodar",
    "djokovic-beijing-return",
    "djokovic-tirante",
    "fritz-cerundolo-us-open-2026-r3",
    "gea-van-de-zandschulp-us-open-2026-r4",
    "grant-kalinina-bjk-cup-2026-sf",
    "muchova-bouzas-bjk-cup-2026-sf",
    "safiullin-alcaraz-us-open-2026-r1",
    "sakkari-gibson-singapore-2026-qf",
    "shelton-nakashima-montreal-final",
    "svitolina-paolini-bjk-cup-2026-sf",
    "tien-monfils-us-open-2026-r2",
    "zhang-fernandez-us-open-2026-r1",
    "zheng-paolini-bjk-cup-2026-qf",
    "zhiyenbayeva-bouzas-bjk-cup-2026",
})


def commentator_said_problem(spec: dict, *,
                             legacy: frozenset[str] = frozenset()) -> str | None:
    """配音文本里出现「解说说」就报，给出是哪几段。"""
    if str(spec.get("slug") or "") in legacy:
        return None
    where = []
    if COMMENTATOR_SAID in str((spec.get("cover") or {}).get("narration") or ""):
        where.append("封面")
    for i, seg in enumerate(spec.get("segments") or [], start=1):
        if COMMENTATOR_SAID in str((seg or {}).get("narration") or ""):
            where.append(f"第 {i} 段")
    if not where:
        return None
    return (f"配音里出现「{COMMENTATOR_SAID}」（{'、'.join(where)}）——账号所有者 2026-09-26："
            "「配音的 tts 里不要再说解说说这三个字了」。要引解说就留原声段配中英字幕，"
            "要讲就直接讲那一拍怎么打的，别借解说的嘴转述。")


def _narrations(spec: dict) -> list[str]:
    """按段取旁白原文，空段和纯画面段不算。"""
    out = []
    for seg in spec.get("segments") or []:
        text = str((seg or {}).get("narration") or "").strip()
        if text:
            out.append(text)
    return out


def _describes_a_shot(text: str) -> bool:
    """这一段旁白有没有在讲**某一球是怎么打的**。

    ⚠️ 两用词（制胜分/主动失误/非受迫失误）落在**统计行**里不算——
    「非受迫失误三十四比十五」是一行数据，「第二个盘点对手主动失误」才是
    球路描述。分界是这句话里有没有百分比或「N 比 M」的对数写法。
    """
    real = [w for w in SHOT_WORDS if w in text]
    if not real:
        return False
    if all(w in _STAT_ONLY_WORDS for w in real) and _STAT_LINE.search(text):
        return False
    return True


def _is_match_recap(spec: dict) -> bool:
    """这条片子是不是「赛场之上」。

    ⚠️ 按 `cover.eyebrow` 认，不按 `_column`——`_column` 在存量里是自由文本
    （99 条写「赛场之上」、42 条写「reel」、37 条空着、十几条写成一整段说明），
    而 `eyebrow` 是真印在画面上的那一行，只有三个值。
    """
    return str((spec.get("cover") or {}).get("eyebrow") or "").strip() == "赛场之上"


def shot_craft_problem(spec: dict, *, legacy: frozenset[str] = frozenset()) -> str | None:
    """⭐⭐ 「赛场之上」的旁白里必须有球路描述，不能只有比分和统计。

    认领口：spec 顶层写 `_tactics_why`，说清**这条源片为什么看不出球路**
    （例：只有远景宽拍、全片是颁奖和反应镜头）。⚠️ 认领的是「查过了，
    真的写不出」，不是「这次先不写」。
    """
    if not _is_match_recap(spec):
        return None
    if str(spec.get("_tactics_why") or "").strip():
        return None
    if str(spec.get("slug") or "") in legacy:
        return None
    nars = _narrations(spec)
    if not nars:
        return None
    hit = [t for t in nars if _describes_a_shot(t)]
    if len(hit) >= SHOT_MIN_SEGMENTS:
        return None
    return (
        f"技战术：{len(nars)} 段旁白里只有 {len(hit)} 段说得出球路，"
        f"至少要 {SHOT_MIN_SEGMENTS} 段（读者 2026-09-19：「技战术也交代不清楚」）。\n"
        "    在转折点那几分上写清**怎么打丢/打赢的**——正反手、直线还是斜线、"
        "落点深浅、上网还是底线相持；球路用画面核（缩略图墙）或解说原声核，"
        "不许凭「通常这样打」编。\n"
        "    真的看不出球路，就在 spec 顶层写 "
        "`\"_tactics_why\": \"<这条源片为什么看不出>\"` 认领。"
    )


def echo_narration_problem(spec: dict, *, legacy: frozenset[str] = frozenset()) -> str | None:
    """⚠️ 相邻两段旁白不许说同一句话。

    来路：`heide-wawrinka-davis-cup-2026-wg1` 第 9、10 段——
    「决胜盘三比二，海德又拿到四个破发点，瓦林卡四个全救回来了。」
    「决胜盘三比二，海德又拿到四个破发点，瓦林卡四个又全救了回来。」
    **一模一样的一句话，连着说了两遍，就这么推上了微信。**
    """
    if str(spec.get("slug") or "") in legacy:
        return None
    nars = _narrations(spec)
    for i, (a, b) in enumerate(zip(nars, nars[1:]), start=1):
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        if ratio > ECHO_MAX:
            return (
                f"复读：第 {i} 段和第 {i + 1} 段说的是同一句话（相似度 {ratio:.2f}）。\n"
                f"      第 {i} 段：{a}\n"
                f"      第 {i + 1} 段：{b}\n"
                "    删掉一段，或者把第二段换成这一分真正新增的东西。"
            )
    return None


def sentence_mold_problem(spec: dict, *, legacy: frozenset[str] = frozenset()) -> str | None:
    """⚠️ 同一个句式模子不许在一条片子里反复套。

    这是「流水账」量得出来的那一半：`comeback-five-love-down` 19 段里
    「N 个破发点」说了 10 遍。句式一样、只换数字，读者读到的就是同一句话
    重复十遍。
    """
    if str(spec.get("slug") or "") in legacy:
        return None
    text = "。".join(_narrations(spec))
    if not text:
        return None
    for name, pattern in SENTENCE_MOLDS:
        n = len(re.findall(pattern, text))
        if n > MOLD_MAX:
            return (
                f"句式：{name} 这个模子在一条片子里用了 {n} 次"
                f"（最多 {MOLD_MAX} 次）。\n"
                "    同一个模子只换数字，读起来就是流水账。换说法：把其中几处"
                "改成这一分**怎么打的**，或者合并成一句带走。"
            )
    return None
