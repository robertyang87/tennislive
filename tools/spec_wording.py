"""会发出去的措辞判据——**单一出处**，validate_spec、promote 和 pytest 共用。

来路（2026-08-26 内容自动化盘点）：这批措辞规矩原来只活在 pytest 里
（tests/test_reel_editorial.py / tests/test_match_reel.py），而自动出片链
（orchestrate 备料 → reel-auto-ready 提升 → match-reel 渲染 → auto-push 发布）
用 GITHUB_TOKEN 直推 main，**不触发 CI**——模型/自动产的 spec 从生成到发进
微信，一次都没被这些判据扫过。已经漏过一条：`tiafoe-musetti-cincinnati-2026-qf`
带着「7点05分」（开球报到分）被并发会话自动推送出去，事后只能挂进豁免表。

CLAUDE.md 的教条本来就是「**凡是只读 spec 就能判的规矩，出处必须在
validate_spec 够得着的地方**」（bejlek-pliskova 那次）。所以：

- 正则、豁免表、扫描面全收在这儿——测试 import 这里的，别再各抄一份
  （「一个数写两处必分叉」）
- `check_spec_wording()` 给 build_match_reel 的入口和 promote_reel_draft 用，
  按 slug 查同一批豁免表；新 spec 违规在 dry-run 第 0.2 秒就红，
  不是等下一次人类 push 把 main CI 打红
- `check_interview_copy_wording()` 给 promote_interview_draft 用——采访线的
  转正入口，零豁免（只跑在新草稿上），面窄一档（不扫 zh 引语译文）
- ⚠️ 三种扫描面**故意不合并**：每一面都是当年按「误伤了什么」收窄过的
  （详见各判据的 docstring），合并等于把三条判据一起放宽或收紧

豁免表照旧**只许减不许加**，自检仍在 pytest 那头（要扫全库才能自检）。
"""

from __future__ import annotations

import re

# ── 正则（每条的来路见同名测试的 docstring）─────────────────────────────

#: 百分比写「几成几」。「成」前面必须紧挨数词，后向排除 功/为/立/绩/片/长。
PERCENT_IDIOM = re.compile(r"[一二三四五六七八九两]成(?![功为立绩片长])")

#: 单分的长度写成秒（「一分打了三十八秒」）。时长/一局的分钟数不在管辖内。
RALLY_SECONDS = re.compile(
    r"(?:一分|这一分|那一分|一个球|这个球|回合|破发点|赛点|盘点)"
    r"[^。！？\n]{0,10}?(?:打了|持续了?|来回了?|僵持了?)\s*"
    r"(?:超过|将近|接近|足足|整整)?\s*"
    r"[〇零一二三四五六七八九十百\d]+\s*秒")

#: 开球时刻报到分（「十一点十分」）。那个分钟多半是整批开赛时刻，不是这一场的。
CLOCK_MINUTE = re.compile(
    r"(?:零点|[一二三四五六七八九十]{1,3}点)\s*[零〇一二三四五六七八九十]{1,4}\s*分"
    r"|(?<!\d)\d{1,2}\s*点\s*\d{1,2}\s*分")

#: 分数式轮次（1/4 决赛、1/8 决赛）和「半决赛」。写 8 强 / 4 强 / 决赛。
#:
#: ⚠️ 这条 2026-09-01 **整个翻了个面**，主语换了，形状没变。原来（2026-08-02）
#: 账号所有者定的是反过来的：「以后不要用四强八强之类的，国内通常用半决赛
#: 1／4 决赛 1/8 决赛之类的」，正则拦的是「四强/八强/十六强」。今天他改了口径：
#: 「**8 强、4 强、决赛，这种这样说，不要说 1/4 决赛和什么 1/8 决赛之类的了**」。
#: 所以现在拦的是旧那套，放行的是「N 强」——和 2026-08-04 那次「solo 从要写
#: `_layout_why` 的例外翻成默认」是同一个形状：闸原样翻面，判据钉两头。
#:
#: 「半决赛」也在里面：他列的三档（8 强 / 4 强 / 决赛）里，「4 强」正是这一档。
#: 不禁它的话同一个账号会把同一轮叫两个名字，而那是这个仓库反复要避免的。
#: 「决赛」两套叫法一样，不动；32 强往前照旧写「第几轮」（那条没被推翻）。
FRACTION_ROUND = re.compile(r"1\s*/\s*(?:4|8|16|32)\s*决赛|四分之一决赛|半决赛")

#: 内部轮次名 → 会发出去的写法。**闸的建设性那一半。**
#:
#: ⚠️ 这张表存在的理由是：内部那两套轮次名（`zh.terms.round_zh` 和
#: `oncourt_feed.parse_round`）产出的是「半决赛」「四分之一决赛」，而它们经
#: `promote_reel_draft` 的 `cover.topic` / `topbar.line1`、
#: `promote_interview_draft` 的 `cover.sub` **流进会发出去的字段**——
#: 翻面之后不转换的话，自动链产的每一条草稿都会被上面那道零豁免的闸拦下，
#: **草稿转不了正，链子静静卡住**（本文件「走不到的路怎么查都是绿的」的反面：
#: 这次是走得到，而且每次都撞）。
#:
#: ⚠️ **只转换出口，不改内部的键。** 「半决赛」在 `KEY_ROUNDS`、排序表、
#: 覆盖率表、`LEAD_ROUND_PTS` 里当**标识符**用，跟着改是拿一条文案规矩去
#: 动一批不相干的判据——而那种改动坏起来不吭声。
_ROUND_DISPLAY = {
    "半决赛": "4强",
    "四分之一决赛": "8强", "1/4决赛": "8强", "1/4 决赛": "8强",
    "1/8决赛": "16强", "1/8 决赛": "16强", "十六强": "16强", "16强赛": "16强",
    "1/16决赛": "32强", "1/16 决赛": "32强", "32强赛": "32强",
    "64强赛": "64强",
}


def round_display(round_name: str | None) -> str:
    """轮次的**对外**写法：4 强 / 8 强 / 16 强 / 决赛 / 第几轮。

    认不出来的原样返回（资格赛、第几轮、小组赛、英文原文都从这条走）——
    宁可原样透出去让闸去拦，也别在这儿猜一个写法。
    """
    return _ROUND_DISPLAY.get((round_name or "").strip(), round_name or "")

#: love game 的字面直译。要用一个词就写「零封」。
LOVE_GAME = re.compile(r"爱局")

#: 「要到 N 个破发点」——点一律写「拿到」。中间最多隔一个数量词。
YAODAO_POINT = re.compile(r"要到[^。！？\n]{0,8}?(破发点|盘点|赛点|局点)")

#: 盘点主语：「拿到/要到/得到/握有 N 个点」之后 26 字内出现「救/保住」而
#: 中间没有点出是谁在救——读者会把主语接成拿到点的那个人。
OWN_POINT = re.compile(r"(要到|拿到|得到|握有)[^。！？\n]{0,12}?"
                       r"([一二三四五六七八九十\d]+)\s*个?(盘点|赛点|破发点)")
SAVE_VERB = re.compile(r"(救|保住)")

#: 小红书正文**首行**里必须出现一位球员的名字。
#:
#: 那一行不是"正文的开头"，是**标题**——`push_reel.split_copy()` 把它单独切出来，
#: 小红书信息流里它就是缩略图底下那一行字，微信推送里它是单独成块、可长按复制的
#: 那一句。也就是说这是**这条片子在信息流里唯一被读到的一行文字**。
#:
#: ⚠️ 它看起来该和封面钩子守同一条规矩（「身份海报上已经印着了，钩子再写一遍是
#: 白占那 27 个字」），**而那条规矩依赖一个在这儿不成立的前提**。量了一遍：solo
#: 封面的中文名是 `SCORE_CN_MAX_PX = 52px`，画布 1080 宽——小红书双列瀑布流的
#: 缩略图约 170px 宽，缩下去名字只剩 **8.2px**，钩子 14.8px。也就是**滑到这一屏
#: 的人看得见钩子，看不见名字**。所以「另一处已经印着」在封面上成立，在信息流里
#: 不成立——这正是本仓库反复记的「抄了规则，没抄它依赖的前提」。
#:
#: 判据只机械地管**一样**：有没有点出是谁。「哪一站」「什么结果」写法太多、
#: 机器分不出好坏，那半条归 CLAUDE.md，故意没有判据。
#:
#: ⚠️ 认简称：整名或**头两个字**（「德约」之于德约科维奇、「中岛」之于中岛布兰登，
#: 存量里就这两条靠它放行）。人名一个都取不到的老 spec（cover 没有 matchup）
#: **跳过不判**——没有可比的东西时报红是编一个判据，而不是执行一个判据。
CAPTION_LEAD_NAME_PREFIX = 2

#: 文案里不许提字幕这类制作规格（账号所有者 2026-08-19：「以后不要再在文案里
#: 说中英文字幕相关的文案」）。每条片子都有的规格不是这一条的内容——
#: interview 线为它攒了一张 78 个文件的豁免表；reel 语料量过是干净的（0 条），
#: 所以这条在 reel 侧**零豁免**，拦的是「promote 模板把规格话术写回来」那一类。
BILINGUAL_MENTION = re.compile(r"中英双语|中英文字幕|中英字幕|双语字幕")

# ── 豁免表：规矩生效前已经发出去的，消息收不回来。只许减不许加 ─────────────

PERCENT_IDIOM_LEGACY = frozenset({
    "baez-dimitrov", "bartunkova-charaeva", "cirstea-bartunkova",
    "eala-osaka", "eala-pegula-final", "eala-ruse", "eala-zheng",
    "fonseca-ruud", "hijikata-monfils", "kenin-lys", "kovacevic-khachanov",
    "medvedev-zandschulp", "navarro-kalinina", "noskova-mcnally",
    "ostapenko-frech", "parry-mertens", "potapova-venus", "shang-vallejo",
    "sonmez-anisimova", "swiatek-rybakina-toronto-final", "townsend-osorio",
    "townsend-rybakina", "wang-pareja", "wang-vandewinkel", "wang-vekic",
    "wangxiyu-timofeeva", "zhang-sabalenka", "zverev-griekspoor",
})

RALLY_SECONDS_LEGACY = frozenset({
    "zverev-norrie",                 # 钩子＋推送标题：「一分打了三十八秒」
    "swiatek-svitolina-toronto-sf",  # 正文：「破发点持续了超过三十秒」
})

CLOCK_MINUTE_LEGACY = frozenset({
    "alexandrova-sabalenka", "baez-dimitrov", "bencic-eala",
    "bucsa-chwalinska", "eala-mcnally", "eala-osaka", "eala-parks",
    "eala-ruse", "faria-shelton", "fils-tirante", "gauff-korneeva", "gauff-samsonova",
    "gea-shapovalov", "krejcikova-bejlek", "landaluce-draper",
    "medvedev-zandschulp", "osaka-fernandez", "pegula-rakhimova",
    "rybakina-gauff-toronto-sf", "rybakina-osaka", "rybakina-samsonova",
    "sabalenka-gibson", "shang-vallejo", "shelton-fonseca", "shelton-mensik",
    "shelton-tien-montreal-sf", "snigur-keys", "sonmez-kasatkina",
    "svitolina-alexandrova", "svitolina-anisimova", "swiatek-arango",
    "swiatek-shnaider", "townsend-osorio", "townsend-rybakina",
    "trungelliti-medvedev", "wang-vandewinkel", "wang-vekic",
    "wangxiyu-fernandez", "wong-gea", "zhang-day", "zhang-ostapenko",
    # `tiafoe-musetti-cincinnati-2026-qf` 2026-08-22T05:02:40Z 已经推过微信
    # （run 32553267109，另一个并发会话发的）：开场写着「北京时间8月22日
    # 7点05分」，报到了分钟。已发不为措辞重渲，挂账。
    "tiafoe-musetti-cincinnati-2026-qf",
})

#: 这张按**文件名**记（spec 和 xhs 各自算一条），照原判据的口径。
#:
#: ⚠️ 2026-09-01 判据翻面之后**整张表换了主语**：原来挂的是「用了强字」的
#: 11 个文件，现在挂的是「用了 1/4 决赛 / 1/8 决赛 / 半决赛」的 173 个。
#: 表大是因为旧写法本来就是上一版规矩要求的——已发的片子不为措辞重渲
#: （消息发出去收不回来，`push.summary` 还要和已发的 copy.html 逐字相同），
#: 和 `_LEGACY_BILINGUAL_MENTION` 那 78 个文件是同一个处置。
#: **只许减不许加**，自检在 pytest 那头（每个名字都要真的还命中）。
FRACTION_ROUND_LEGACY = frozenset({
    "alexandrova-sabalenka.json", "alexandrova-sabalenka.xhs.txt",
    "anisimova-bartunkova.json", "anisimova-bartunkova.xhs.txt",
    "anisimova-noskova.json", "anisimova-noskova.xhs.txt",
    "auger-aliassime-cerundolo.json", "auger-aliassime-cerundolo.xhs.txt",
    "bejlek-keys-cincinnati-2026-qf.json",
    "bejlek-keys-cincinnati-2026-qf.xhs.txt", "bejlek-sabalenka.json",
    "bejlek-sabalenka.xhs.txt", "bencic-eala.json", "bencic-eala.xhs.txt",
    "bencic-townsend.json", "bencic-townsend.xhs.txt",
    "boisson-krueger.json", "boisson-krueger.xhs.txt",
    "chwalinska-gibson.xhs.txt", "cirstea-pegula.json",
    "cirstea-pegula.xhs.txt", "cobolli-jodar.json", "cobolli-jodar.xhs.txt",
    "djokovic-tirante.json", "djokovic-tirante.xhs.txt", "eala-mcnally.json",
    "eala-mcnally.xhs.txt", "eala-osaka.json", "eala-osaka.xhs.txt",
    "eala-pegula.json", "eala-pegula.xhs.txt", "eala-story.json",
    "eala-story.xhs.txt", "eala-washington-story.xhs.txt", "eala-zheng.json",
    "eala-zheng.xhs.txt", "fernandez-andreeva.json",
    "fils-cobolli-cincinnati-2026-sf.json",
    "fils-cobolli-cincinnati-2026-sf.xhs.txt", "fils-deminaur.json",
    "fils-tirante.json", "fils-tirante.xhs.txt", "fonseca-ruud.xhs.txt",
    "fritz-jodar-final.xhs.txt", "fritz-merida.json", "fritz-merida.xhs.txt",
    "fritz-nakashima-cincinnati-2026-qf.json",
    "fritz-nakashima-cincinnati-2026-qf.xhs.txt", "fritz-oconnell.json",
    "fritz-oconnell.xhs.txt", "gauff-bejlek-cincinnati-2026-sf.json",
    "gauff-bejlek-cincinnati-2026-sf.xhs.txt", "gauff-bouzkova.json",
    "gauff-bouzkova.xhs.txt", "gauff-korneeva.json",
    "gauff-korneeva.xhs.txt", "gauff-kostyuk-cincinnati-2026-qf.json",
    "gauff-kostyuk-cincinnati-2026-qf.xhs.txt",
    "gauff-pegula-cincinnati-2026-final.xhs.txt", "gauff-sakkari.json",
    "gauff-sakkari.xhs.txt", "gea-shapovalov.json", "gea-shapovalov.xhs.txt",
    "jodar-fils-montreal-qf.json", "jodar-fils-montreal-qf.xhs.txt",
    "jodar-fritz.json", "jodar-fritz.xhs.txt", "jodar-tabilo.json",
    "jodar-tabilo.xhs.txt", "kostyuk-andreeva.json",
    "kostyuk-andreeva.xhs.txt", "kovacevic-khachanov.json",
    "kovacevic-khachanov.xhs.txt", "landaluce-draper.json",
    "landaluce-draper.xhs.txt", "lehecka-fils.json", "lehecka-fils.xhs.txt",
    "lina-cincinnati-2012.json", "lina-cincinnati-2012.xhs.txt",
    "maria-yastremska.json", "maria-yastremska.xhs.txt",
    "musetti-faria.json", "musetti-faria.xhs.txt", "nakashima-borges.json",
    "nakashima-borges.xhs.txt", "nakashima-jodar-montreal-sf.json",
    "nakashima-jodar-montreal-sf.xhs.txt", "noskova-tauson.xhs.txt",
    "osaka-fernandez.json", "osaka-fernandez.xhs.txt", "osaka-mertens.json",
    "osaka-mertens.xhs.txt", "paul-cobolli.json", "paul-cobolli.xhs.txt",
    "pegula-anisimova.json", "pegula-anisimova.xhs.txt",
    "pegula-rakhimova.json", "pegula-rakhimova.xhs.txt",
    "pegula-swiatek-cincinnati-2026-sf.json",
    "pegula-swiatek-cincinnati-2026-sf.xhs.txt",
    "rublev-virtanen-us-open-2026-r1.json",
    "rublev-virtanen-us-open-2026-r1.xhs.txt",
    "rybakina-gauff-toronto-sf.json", "rybakina-gauff-toronto-sf.xhs.txt",
    "rybakina-kasatkina.xhs.txt", "rybakina-li.json", "rybakina-li.xhs.txt",
    "rybakina-osaka.json", "rybakina-osaka.xhs.txt",
    "rybakina-samsonova.json", "rybakina-samsonova.xhs.txt",
    "rybakina-shnaider.json", "rybakina-shnaider.xhs.txt",
    "safiullin-alcaraz-us-open-2026-r1.xhs.txt", "shang-vallejo.xhs.txt",
    "shelton-fonseca.json", "shelton-fonseca.xhs.txt", "shelton-mensik.json",
    "shelton-mensik.xhs.txt", "shelton-nakashima-montreal-final.json",
    "shelton-tien-montreal-sf.json", "shelton-tien-montreal-sf.xhs.txt",
    "shnaider-chwalinska.json", "shnaider-chwalinska.xhs.txt",
    "shnaider-pegula.json", "shnaider-pegula.xhs.txt",
    "sonmez-anisimova.xhs.txt", "sonmez-kasatkina.json",
    "sonmez-kasatkina.xhs.txt", "svitolina-alexandrova.json",
    "svitolina-alexandrova.xhs.txt", "svitolina-anisimova.json",
    "svitolina-anisimova.xhs.txt", "swiatek-golubic.json",
    "swiatek-golubic.xhs.txt", "swiatek-kostyuk.json",
    "swiatek-kostyuk.xhs.txt", "swiatek-parry.json", "swiatek-parry.xhs.txt",
    "swiatek-rybakina-cincinnati-2026-qf.json",
    "swiatek-rybakina-cincinnati-2026-qf.xhs.txt",
    "swiatek-rybakina-toronto-final.json", "swiatek-shnaider.json",
    "swiatek-shnaider.xhs.txt", "swiatek-svitolina-toronto-sf.json",
    "swiatek-svitolina-toronto-sf.xhs.txt", "tiafoe-auger-aliassime.json",
    "tiafoe-auger-aliassime.xhs.txt",
    "tiafoe-musetti-cincinnati-2026-qf.json",
    "tiafoe-musetti-cincinnati-2026-qf.xhs.txt",
    "tiafoe-nakashima-cincinnati-2026-sf.json",
    "tiafoe-nakashima-cincinnati-2026-sf.xhs.txt", "tiafoe-story.json",
    "tiafoe-story.xhs.txt", "tirante-landaluce.xhs.txt",
    "tirante-mensik.json", "tirante-mensik.xhs.txt",
    "usopen-qualies-2026.json", "usopen-qualies-2026.xhs.txt",
    "wang-samsonova.json", "wang-samsonova.xhs.txt", "wangxiyu-keys.json",
    "wangxiyu-keys.xhs.txt", "wong-brooksby.xhs.txt", "wong-gea.xhs.txt",
    "zheng-lanlana.json", "zheng-lanlana.xhs.txt",
    "zheng-liutova-us-open-2026-r1.json",
    "zheng-liutova-us-open-2026-r1.xhs.txt", "zverev-atmane.json",
    "zverev-atmane.xhs.txt", "zverev-paul.json", "zverev-paul.xhs.txt",
})

YAODAO_LEGACY = frozenset({"zverev-griekspoor.json", "zverev-griekspoor.xhs.txt"})

#: 首行没点出是谁——这条规矩（2026-09-02）之前发出去的 80 条。已发不为措辞重渲
#: （消息收不回来，`push.summary` 还要和已发的 copy.html 逐字相同），和
#: `FRACTION_ROUND_LEGACY` 那 173 个文件是同一个处置。**只许减不许加**，
#: 自检在 pytest 那头（每个名字都要真的还命中）。
CAPTION_LEAD_LEGACY = frozenset({
    "altmaier-musetti", "anisimova-noskova", "arango-venus", "baez-dimitrov",
    "bartunkova-charaeva", "bejlek-pliskova", "bejlek-sabalenka",
    "boisson-krueger", "borges-rublev", "boulter-volynets", "bouzkova-jovic",
    "bucsa-chwalinska", "chwalinska-gibson", "cincinnati-story",
    "cirstea-bartunkova", "cirstea-kalinskaya", "cirstea-pegula",
    "cobolli-blockx", "djokovic-tirante", "eala-ruse",
    "eala-stoiana-us-open-2026-r1", "eala-story", "faria-shelton",
    "fery-deminaur", "fils-tiafoe-cincinnati-2026-final",
    "fonseca-van-de-zandschulp", "fritz-merida", "fritz-michelsen",
    "gauff-li", "jodar-tabilo", "kovacevic-khachanov", "lehecka-fils",
    "maria-yastremska", "medvedev-damm", "medvedev-zandschulp",
    "navarro-kalinina", "noskova-boulter", "noskova-mcnally",
    "noskova-tauson", "osaka-four-slams-2026", "osaka-iverson-tribute",
    "osaka-walkout-2026", "ostapenko-frech", "parry-mertens",
    "pegula-navarro", "putintseva-bencic-us-open-2026-r1",
    "rakhimova-krejcikova-us-open-2026-r1", "rublev-virtanen-us-open-2026-r1",
    "rybakina-kasatkina", "rybakina-shnaider", "sabalenka-gibson",
    "safiullin-alcaraz-us-open-2026-r1", "shang-rublev",
    "shnaider-chwalinska", "sonmez-anisimova", "stearns-tauson",
    "swiatek-rybakina-cincinnati-2026-qf", "tiafoe-auger-aliassime",
    "tiafoe-musetti-cincinnati-2026-qf", "tirante-fritz", "tirante-landaluce",
    "townsend-rybakina", "trungelliti-medvedev", "tsitsipas-auger-aliassime",
    "usopen-qualies-2026", "wang-kasatkina", "wang-xinyu-story",
    "wangxiyu-swiatek-us-open-2026-r1", "williams-kenin-us-open-2026-r1",
    "wong-paul-us-open-2026-r1", "wu-walton-us-open-2026-r1", "zhang-day",
    "zhang-fernandez-us-open-2026-r1", "zhang-ostapenko",
    "zheng-burel-us-open-2026-q2", "zheng-liutova-us-open-2026-r1",
    "zheng-pridankina-us-open-2026-q3", "zverev-atmane", "zverev-griekspoor",
    "zverev-norrie",
})

# ── 三种扫描面（故意不合并，见模块 docstring）──────────────────────────────


def voiced_texts(spec: dict) -> list[str]:
    """钩子 + push 字符串 + 旁白 + 顶栏——「几成几/写秒/报到分」那三条的面。"""
    texts = [str((spec.get("cover") or {}).get("hook") or "")]
    texts += [str(v) for v in (spec.get("push") or {}).values()
              if isinstance(v, str)]
    texts += [str(s.get("narration") or "") for s in spec.get("segments") or []
              if isinstance(s, dict)]
    texts += [str(v) for v in (spec.get("topbar") or {}).values()
              if isinstance(v, str)]
    return texts


def outward_deep(spec: dict):
    """旁白 + cover 里非注解的字符串（含嵌套 dict/list）+ push + topbar——
    轮次/爱局的面。

    ⚠️ **`topbar` 是 2026-09-01 补进来的，而它本来是这条规矩最该盖住的一面**：
    `topbar.line1` 写的就是「<年> <赛事> <轮次>」，**烧在画面上、整个比赛段
    一直挂着**，比封面那一行还显眼。原来只扫 cover/push 的话，翻面之后
    `promote_reel_draft` 往 line1 写一句「半决赛」照样过闸。
    补它的代价量过是**零**：46 条 topbar 里带旧写法的 spec 全部已经在豁免表里
    （它们的 cover.topic 也有同一句），「爱局」在 topbar 里零命中。
    """
    for seg in spec.get("segments") or []:
        if isinstance(seg, dict):
            yield seg.get("narration", "")
    for key, value in (spec.get("topbar") or {}).items():
        if not key.startswith("_") and isinstance(value, str):
            yield value
    for key, value in (spec.get("cover") or {}).items():
        if key.startswith("_"):
            continue
        for item in ([value] if isinstance(value, str)
                     else list(value.values()) if isinstance(value, dict)
                     else []):
            if isinstance(item, str):
                yield item
            elif isinstance(item, list):
                yield from (x for x in item if isinstance(x, str))
    for key, value in (spec.get("push") or {}).items():
        if not key.startswith("_") and isinstance(value, str):
            yield value


def outward_flat(spec: dict):
    """旁白 + cover 顶层字符串 + push——「要到」那条的面（更窄，照原判据）。"""
    for seg in spec.get("segments") or []:
        if isinstance(seg, dict):
            yield seg.get("narration", "")
    for key, value in (spec.get("cover") or {}).items():
        if key.startswith("_") or not isinstance(value, str):
            continue
        yield value
    for key, value in (spec.get("push") or {}).items():
        if not key.startswith("_") and isinstance(value, str):
            yield value


def _hits(pattern: re.Pattern, texts) -> list[str]:
    return sorted({m.group(0) for t in texts for m in pattern.finditer(t or "")})


def spec_player_names(spec: dict) -> list[str]:
    """盘点主语判据要认的人名：matchup / subject / winner / versus 两格。"""
    cover = spec.get("cover") or {}
    names = [w.get("name", "") for w in (cover.get("matchup") or [])
             if isinstance(w, dict)]
    names += [cover.get("subject", ""), cover.get("winner", "")]
    versus = cover.get("versus") or {}
    for side in ("top", "bottom"):
        names += list((versus.get(side) or {}).get("names") or [])
    return [n for n in names if n]


def caption_lead(xhs_text: str) -> str:
    """小红书正文的**首行**，也就是标题那一行（和 `push_reel.split_copy` 同一套切法）。"""
    return next((ln.strip() for ln in (xhs_text or "").splitlines() if ln.strip()), "")


def caption_lead_names_nobody(first_line: str, names: list[str]) -> bool:
    """这一行里一个球员的名字都没有吗？

    人名一个都取不到时返回 **False**（判不了就不判，见 `CAPTION_LEAD_NAME_PREFIX`
    上面那段）——报红需要有可比的东西，没有就不是"违规"，是"这条判不了"。
    """
    names = [n for n in names if n]
    if not names or not first_line:
        return False
    n = CAPTION_LEAD_NAME_PREFIX
    return not any(name in first_line or (len(name) > n and name[:n] in first_line)
                   for name in names)


def save_subject_flag(text: str, names: list[str]) -> list[str]:
    """「拿到 N 个点…救/保住」而中间没写出是谁在救的那些片段。"""
    bad = []
    for m in OWN_POINT.finditer(text):
        after = text[m.end():m.end() + 26]
        hit = SAVE_VERB.search(after)
        if hit and not any(n in after[:hit.start()] for n in names):
            bad.append(f"…{m.group(0)}｜{after[:26]}…")
    return bad


def interview_outward_texts(spec: dict) -> list[str]:
    """采访线会发出去的「我们的话」：push / takeaway / cover 里非注解的字符串。

    ⚠️ **不扫 `zh` 字幕行**：那是受访者说的话的译文，措辞判据管的是我们的
    文案——硬扫会逼人改动引语（他真说了「七成」就只能照实译，改成
    「百分之七十」是译法偏好，不是判据；specs/interviews 存量里那几处
    一成/两成正是这么来的）。译文的写法偏好归翻译教材管，不落硬闸。
    """
    texts: list[str] = []
    for key, value in (spec.get("push") or {}).items():
        if not key.startswith("_") and isinstance(value, str):
            texts.append(value)
    for card in (spec.get("takeaway") or {}).values():
        if isinstance(card, dict):
            texts += [v for k, v in card.items()
                      if not k.startswith("_") and isinstance(v, str)]
    for key, value in (spec.get("cover") or {}).items():
        if key.startswith("_"):
            continue
        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, list):
            texts += [x for x in value if isinstance(x, str)]
    return texts


def check_interview_copy_wording(spec: dict,
                                 xhs_text: str | None = None) -> list[str]:
    """采访线转正入口的措辞判据——**零豁免**。

    这条闸只跑在新草稿转正那一刻（promote_interview_draft），老 spec 不再过
    promote，所以不需要豁免表；也因此每一条报出来的都该当场改，不该挂账。
    面比 reel 侧窄：只扫「我们的话」（push/takeaway/cover/小红书正文），
    不扫 zh 引语译文（见 interview_outward_texts 的 docstring）。
    盘点主语那条（save_subject_flag）没进来：它要人名表，而采访文案的模板
    不叙述逐分——真出现了归终审，别为扫不到的面硬凑判据。
    """
    texts = interview_outward_texts(spec) + ([xhs_text] if xhs_text else [])
    problems: list[str] = []
    for pattern, label, fix in (
            (PERCENT_IDIOM, "百分比写成了「几成几」",
             "旁白写「百分之三十四」，正文可写 34%"),
            (RALLY_SECONDS, "把单分的长度写成了秒",
             "说打了多少拍；拿不到拍数就换个说法"),
            (CLOCK_MINUTE, "开球时刻报到了分钟",
             "只说个大概（X 点多 / 快 X 点），时段词留着"),
            (FRACTION_ROUND, "轮次写了分数式或「半决赛」",
             "写 8 强 / 4 强 / 决赛，再往前写「第几轮」"),
            (LOVE_GAME, "love game 被字面直译成了「爱局」", "写「零封」"),
            (YAODAO_POINT, "写了「要到…点」",
             "破发点/盘点/赛点一律写「拿到」"),
            (BILINGUAL_MENTION, "文案里提了字幕这类制作规格",
             "读者关心这场球发生了什么，不关心我们用什么字幕方案做的"
             "（2026-08-19 的规矩）"),
    ):
        if hits := _hits(pattern, texts):
            problems.append(f"{label}：{hits}——{fix}")
    return problems


def check_spec_wording(spec: dict, slug: str,
                       xhs_text: str | None = None) -> list[str]:
    """给一条 spec（可带小红书正文）跑全部措辞判据，返回没被豁免的违规。

    豁免按 slug／文件名查同一批表——已发的老 spec 重新 dry-run 照旧绿；
    新 spec 违规当场红，不用等下一次人类 push 把 main CI 打红。
    """
    problems: list[str] = []
    voiced = voiced_texts(spec) + ([xhs_text] if xhs_text else [])

    if slug not in PERCENT_IDIOM_LEGACY:
        if hits := _hits(PERCENT_IDIOM, voiced):
            problems.append(
                f"百分比写成了「几成几」：{hits}——旁白写「百分之三十四」"
                f"（TTS 读得对，字幕烧成「百分之34」），正文可写 34%")
    if slug not in RALLY_SECONDS_LEGACY:
        if hits := _hits(RALLY_SECONDS, voiced):
            problems.append(
                f"把单分的长度写成了秒：{hits}——说打了多少拍；拿不到拍数"
                f"就别写长度，换个说法（这一分怎么结束的、全场什么反应）")
    if slug not in CLOCK_MINUTE_LEGACY:
        if hits := _hits(CLOCK_MINUTE, voiced):
            problems.append(
                f"开球时刻报到了分钟：{hits}——0–9 分说「X 点」、10–39 分说"
                f"「X 点多」、40–59 分说「快 X+1 点」，时段词（凌晨/晚上）留着；"
                f"那个分钟多半是整批开赛时刻，不是这一场的")

    spec_name, xhs_name = f"{slug}.json", f"{slug}.xhs.txt"
    if spec_name not in FRACTION_ROUND_LEGACY:
        if hits := _hits(FRACTION_ROUND, outward_deep(spec)):
            problems.append(
                f"轮次写了分数式或「半决赛」：{hits}——写 8 强 / 4 强 / 决赛，"
                f"再往前写「第几轮」")
    if xhs_text and xhs_name not in FRACTION_ROUND_LEGACY:
        if hits := _hits(FRACTION_ROUND, [xhs_text]):
            problems.append(f"小红书正文的轮次写了分数式或「半决赛」：{hits}")

    if hits := _hits(LOVE_GAME, list(outward_deep(spec)) +
                     ([xhs_text] if xhs_text else [])):
        problems.append(
            f"love game 被字面直译成了「爱局」：{hits}——写「零封」，"
            f"或者靠逐分（15:0/30:0/40:0）讲清楚，不另造标签")

    if spec_name not in YAODAO_LEGACY:
        if hits := _hits(YAODAO_POINT, outward_flat(spec)):
            problems.append(f"写了「要到…点」：{hits}——破发点/盘点/赛点"
                            f"一律写「拿到」")
    if xhs_text and xhs_name not in YAODAO_LEGACY:
        if hits := _hits(YAODAO_POINT, [xhs_text]):
            problems.append(f"小红书正文写了「要到…点」：{hits}——一律写「拿到」")

    text = "".join(str(s.get("narration", ""))
                   for s in spec.get("segments") or [] if isinstance(s, dict))
    if xhs_text:
        text += "\n" + xhs_text
    if bad := save_subject_flag(text, spec_player_names(spec)):
        problems.append(
            "「拿到 N 个盘点」之后接「救/保住」，没写出是谁在救——读者会把"
            "主语接成拿到点的那个人：" + "；".join(bad))

    if xhs_text and slug not in CAPTION_LEAD_LEGACY:
        first = caption_lead(xhs_text)
        if caption_lead_names_nobody(first, spec_player_names(spec)):
            problems.append(
                f"小红书正文首行一个球员的名字都没有：「{first}」——那一行是"
                f"**标题**（信息流里缩略图底下唯一被读到的一行），刷到的人得先"
                f"知道这是谁。封面钩子不写身份是因为海报上印着，而缩略图缩到 "
                f"170px 时那个名字只剩 8.2px，前提在这儿不成立。"
                f"把「谁」补进这一行，钩子留在后半句")

    if hits := _hits(BILINGUAL_MENTION, voiced):
        problems.append(
            f"文案里提了字幕这类制作规格：{hits}——读者关心这场球发生了什么，"
            f"不关心我们用什么字幕方案做的（2026-08-19 的规矩）")
    return problems
