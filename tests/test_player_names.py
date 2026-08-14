from __future__ import annotations

import json
from pathlib import Path

import pytest

from tennislive.zh import player_zh


SNAPSHOT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "tennislive"
    / "zh"
    / "player_names_top500.json"
)


def test_top_500_snapshot_has_1000_chinese_first_display_names():
    from tools.update_player_names import validate_snapshot

    payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    validate_snapshot(payload)

    for tour in ("ATP", "WTA"):
        entries = payload["tours"][tour]
        assert len(entries) == 500
        assert all(player_zh(entry["name_en"]) != entry["name_en"] for entry in entries)


def test_official_media_form_and_feed_aliases_are_resolved():
    assert player_zh("Learner Tien") == "勒纳·钱"
    assert player_zh("Felix Auger-Aliassime") == "阿利亚西姆"
    assert player_zh("Brandon Nakashima") == "中岛布兰登"
    assert player_zh("Iga Swiatek") == "斯瓦泰克"
    assert player_zh("Ann Li") == "李吉妮"
    assert player_zh("Joanna Garland") == "葛蓝乔安娜"
    assert player_zh("Sara Sorribes Tormo") == "索里贝斯·托莫"
    assert player_zh("Tamara Korpatsch") == "科尔帕奇"
    assert player_zh("Chak Lam Coleman Wong") == "黄泽林"
    assert player_zh("Aleksandr Shevchenko") == "舍甫琴科"
    assert player_zh("Catherine McNally") == "麦克纳莉"


def test_同姓不同人不能靠姓氏兜底混成一个():
    """**「表里这个姓只有一个人」只说明表里只有一个，不说明是同一个人。**

    2026-07-29 查黄泽林那场时撞出来的：香港有两个姓 Wong 的球员同一天在打，
    `Coleman Wong`（黄泽林，男，ATP）在表里，`Hong Yi Cody Wong`（女，WTA）
    不在——姓氏兜底把她也解析成「黄泽林」，错的人还错了性别。

    兜底不能删：ESPN 给黄泽林的写法是 `Chak Lam Coleman Wong`，全名、反序、
    去中间名三条都匹配不上，正是靠它才认出来的。所以判据要能同时分开三种：

        Chak Lam Coleman Wong  vs  coleman wong    同一个词        → 认
        Catherine McNally      vs  caty mcnally    昵称，不共用词  → 认
        Hong Yi Cody Wong      vs  coleman wong    两个人          → 不认

    中间那条是第一版漏掉的：只要求「共用一个词」会把 Catherine 拦掉。按名的
    公共前缀算就分得开——catherine/caty 共三个字符，cody/coleman 只共两个。
    """
    # 认得出来的
    assert player_zh("Chak Lam Coleman Wong") == "黄泽林"
    assert player_zh("Coleman Wong") == "黄泽林"
    assert player_zh("Catherine McNally") == "麦克纳莉"
    assert player_zh("Caty McNally") == "麦克纳莉"
    # **认不出来好过认成另一个人**：原样返回英文名
    for other in ("Hong Yi Cody Wong", "Cody Wong"):
        assert player_zh(other) == other, (
            f"{other} 被解析成了 {player_zh(other)}——那是另一个人")


def test_official_ranking_text_parsers_require_exact_top_500_coverage():
    from tools.update_player_names import parse_atp_text, parse_wta_text

    atp_text = "\n".join(
        f"{rank} Surname{rank}, Given{rank} (USA) {1000-rank} 0 0 0"
        for rank in range(1, 501)
    )
    wta_blocks = []
    for rank in range(1, 501):
        name = (
            "SÁNCHEZ, ANA SOFIA"
            if rank == 417
            else f"SURNAME{rank}, GIVEN{rank}"
        )
        wta_blocks.extend(
            [str(rank), f"({rank})", name, "USA", "100"]
        )

    assert len(parse_atp_text(atp_text)) == 500
    wta = parse_wta_text("\n".join(wta_blocks))
    assert len(wta) == 500
    assert wta[416].name == "Ana Sofia Sánchez"

    with pytest.raises(ValueError, match="found=499"):
        parse_atp_text(atp_text.rsplit("\n", 1)[0])


def test_snapshot_validator_rejects_an_english_primary_name():
    from tools.update_player_names import validate_snapshot

    valid = [
        {"rank": rank, "name_en": f"Player {rank}", "name_zh": f"球员{rank}"}
        for rank in range(1, 501)
    ]
    payload = {"tours": {"ATP": list(valid), "WTA": list(valid)}}
    payload["tours"]["WTA"][80] = {
        "rank": 81,
        "name_en": "Tamara Korpatsch",
        "name_zh": "Tamara Korpatsch",
    }

    with pytest.raises(ValueError, match="non-Chinese"):
        validate_snapshot(payload)


def test_cctv_is_the_highest_translation_source_after_native_names():
    from tools.update_player_names import _source_priority, _store_translation

    cctv = _source_priority("央视网", "https://sports.cctv.com/example")
    xinhua = _source_priority("新华社", "https://www.news.cn/example")
    sport_gov = _source_priority(
        "国家体育总局", "https://www.sport.gov.cn/example"
    )
    tournament = _source_priority(
        "中国网球公开赛", "https://www.chinaopen.com/example"
    )

    assert _source_priority("球员原生中文名") > cctv
    assert cctv > xinhua > sport_gov > tournament
    assert _source_priority("央视网", "https://example.com/not-cctv") < cctv

    lookup = {}
    _store_translation(
        lookup,
        "Example Player",
        ("央视译名", "央视网", "https://sports.cctv.com/example"),
    )
    _store_translation(
        lookup,
        "Example Player",
        ("新华社译名", "新华社", "https://www.news.cn/newer-example"),
    )
    assert lookup["example player"][0] == "央视译名"


def test_review_queue_is_non_blocking_and_only_contains_provisional_names():
    from tools.update_player_names import build_review_queue

    payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    queue = build_review_queue(payload)
    expected = {
        entry["name_en"]
        for tour in ("ATP", "WTA")
        for entry in payload["tours"][tour]
        if entry["translation_source"] == "machine-transliteration"
        or "待国内媒体复核" in entry["translation_source"]
    }

    assert queue["blocking"] is False
    assert {entry["name_en"] for entry in queue["entries"]} == expected
    assert "Learner Tien" not in expected


def test_中国军团名单里每个名字都要是译名函数查得出来的():
    """**`CHINESE_PLAYER_NAMES` 里写错一个字，就是永远命中不了，而且不报错。**

    命中判据是 `player_zh(p.name) in CHINESE_PLAYER_NAMES`
    （`render/common.py` 的 `is_chinese_involved`）——名单这一侧是死字符串，
    译名那一侧是函数输出，两边差一个字就永远对不上。而它坏起来的样子是
    「这位球员的比赛没进中国军团」，**和「今天她没打」一模一样**。

    2026-08-14 复算出两个躺了很久的错字，改在 `render/common.py`：

        徐一幡 → 徐一璠     Yifan Xu
        魏思佳 → 韦思佳     Sijia Wei，姓是「韦」不是「魏」

    ⚠️ 最要命的时候是**只剩 flashscore 一个源**：那个源 `Player.country`
    一律留空（`sources/flashscore.py` 的模块 docstring 写着为什么），国籍那
    一半判据整个失效，**这张表就是唯一的中国球员探测器**。而中国球员是这个
    号的第一优先级选题。2026-08-04~07 ESPN 和 SofaScore 同时被拉黑那三天，
    走的正是这条路。

    ⚠️ 判据**自动推导，不维护第二张名单**：可达集合是拿两张译名表
    （`players.py` 的 `PLAYER_ZH` + `player_names_top500.json` 快照）里的
    每一个英文名**真跑一遍 `player_zh()`** 收上来的——CLAUDE.md 那条
    「判断改没改对不要看文件内容，直接调 `player_zh()`」说的就是这个。
    钉死那两个错字的话，下一个错字它就是哑的。
    """
    from tennislive.zh import player_zh
    from tennislive.zh.players import PLAYER_ZH
    from tennislive.render.common import CHINESE_PLAYER_NAMES

    payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    english = set(PLAYER_ZH)
    for tour in ("ATP", "WTA"):
        english.update(e["name_en"] for e in payload["tours"][tour])

    # 真跑函数，不读字典的 values()——读字典验的是「表里有这个词」，
    # 跑函数验的才是「渲染时那条路真的会吐出这个词」。
    reachable = {player_zh(name) for name in english}

    # 判据自己的判据：主语没了、或者可达集合塌成空的时候要出声，
    # 而不是变成一盏恒真的绿灯。
    assert CHINESE_PLAYER_NAMES, "中国军团名单空了，这条判据没有主语"
    assert len(reachable) > 900, f"可达译名只有 {len(reachable)} 个，探测器坏了"
    assert "郑钦文" in reachable, "连郑钦文都查不出来，探测器坏了"
    assert "郑钦雯" not in reachable, "探测器把不存在的名字也算成可达了"

    unreachable = sorted(CHINESE_PLAYER_NAMES - reachable)
    assert not unreachable, (
        f"这些名字 player_zh() 永远吐不出来，写进名单等于永远命中不了："
        f"{unreachable}——名单里的字要和译名表一模一样，"
        f"改完直接调 player_zh() 验，别看文件内容")


def test_带重音的拼法要认得出是同一个人():
    """**同一个人换个拼法就掉回英文名，而且不吭声。**

    `player_zh("Gaël Monfils")` 原样返回 `Gaël Monfils`，
    `player_zh("Gael Monfils")` 给「孟菲尔斯」——卡片上就是一个英文名混在
    一排中文名里，看着像「这个人表里没有」，和真的没有长得一模一样。

    2026-08-01 查洛斯卡沃斯四强时撞到：对手 `Arthur Géa` 是法国人，维基
    条目标题带重音；ESPN 恰好给的是不带重音的写法，**纯属运气**。

    折叠同时作用在建索引和查询两边，所以它只把「查不到」变成「查得到」。

    ⚠️ `đ` 要折成 `dj` 而不是 `d`：塞尔维亚语的拉丁转写就是这么写的
    （`Đoković` → `Djokovic`，表里正是后者）。折成 `d` 得到 `dokovic`，
    照样查不到——**一个改一半的折叠比不折更难发现**，因为它看起来已经修过了。
    """
    from tennislive.zh import player_zh

    pairs = [
        ("Gael Monfils", "Gaël Monfils"),
        ("Felix Auger-Aliassime", "Félix Auger-Aliassime"),
        ("Arthur Gea", "Arthur Géa"),
        ("Novak Djokovic", "Novak Đoković"),
    ]
    for plain, accented in pairs:
        zh = player_zh(plain)
        assert zh != plain, f"{plain} 本来就查不到，这条测试的前提不成立"
        assert player_zh(accented) == zh, (
            f"{accented} 没解析成 {zh}，而是 {player_zh(accented)}——"
            "带重音的拼法掉回了英文名")

    # 反面：折叠不许把本来查得到的改掉
    for name, expect in (("Zheng Qinwen", "郑钦文"),
                         ("Chak Lam Coleman Wong", "黄泽林"),
                         ("Elina Svitolina", "斯维托丽娜")):
        assert player_zh(name) == expect, f"{name} 被折叠改坏了"


CN_ROSTER = Path(__file__).resolve().parents[1] / "data" / "cn_players.json"


def test_中国军团的两张名单必须一字不差():
    """**同一份名单存了两处，而且它们从来没被比过。**

    `data/cn_players.json`（场上采访那条线用）和 `render/common.py` 的
    `CHINESE_PLAYER_NAMES`（「中国军团」板块和内容精选用）装的是同一件事：
    哪些球员算中国大陆球员。两处各自手工维护，谁也不看谁。

    2026-08-14 第一次真把它们摆在一起量：**各 24 人，只重合 22 个**——
    蒋欣玗、汤千慧只进了 `common.py`，冯硕、叶秋语只进了 `cn_players.json`。
    24 = 24 是巧合，两人前后各抄了一遍，各漏各的。

    ⚠️ **分叉的样子是「他今天没打」。** 只在一边的那位，在另一条线上就是
    静静地不出现：比赛不进「中国军团」板块、采访不被推。两条路都不报错。
    这跟本仓库反复记的「一个数写两处必分叉」是同一个形状，只不过这次分叉的
    是一份名单，而且分叉之后**两边都还在正常工作**，各自漏各自的人。

    收谁的判据写在 `cn_players.json` 的 `_roster_note` 里，见下一条测试。
    """
    from tennislive.render.common import CHINESE_PLAYER_NAMES

    roster = json.loads(CN_ROSTER.read_text(encoding="utf-8"))["players"]
    from_file = {p["zh"] for p in roster}

    # 判据自己的判据：两边都塌成空的时候要出声，别变成一盏恒真的绿灯。
    assert len(from_file) > 25, f"cn_players.json 只剩 {len(from_file)} 人，主语没了"
    assert len(CHINESE_PLAYER_NAMES) > 25, "CHINESE_PLAYER_NAMES 塌了，主语没了"
    assert len(from_file) == len(roster), "cn_players.json 里有重名"

    only_code = sorted(CHINESE_PLAYER_NAMES - from_file)
    only_file = sorted(from_file - CHINESE_PLAYER_NAMES)
    assert not only_code and not only_file, (
        f"两张中国球员名单对不上——只在 render/common.py 里的：{only_code}；"
        f"只在 data/cn_players.json 里的：{only_file}。"
        "两处装的是同一件事，差一个名字就是那位球员在另一条线上静静消失。"
        "补齐两边，并按 cn_players.json 的 `_roster_note` 给新条目写 `admit`。")


def test_中国球员名单每条都要说清是按哪条规则收的():
    """**「这张名单应该收谁」在 2026-08-14 之前没有标准。**

    没有标准的后果是量得出来的：同一天扫官方排名 PDF，CHN 单打 top500 里
    **有八位不在名单上**（尤晓迪、白卓璇、田方然、施晗、姚欣辛、李宗钰、
    逯佳境、崔杰），其中白卓璇正在实打实地漏——库里那条
    `Zhuoxuan Bai On-Court Interview | Australian Open 2026 First Round`
    判不出中国球员。

    所以现在每条都要认领自己是按哪条规则进来的：

        admit=singles-top500   ATP/WTA 单打 top500 且国籍 CHN，译名已定
        admit=manual           不在 top500（双打名将、掉出榜的老将），必须写 `_why`

    ⚠️ `_why` 不是走过场。这条线上「手工收」是唯一的自由度，不写理由的话，
    下一个人既不知道能不能删，也不知道还该照着收谁——那就等于又回到没有标准。
    和 `mixed_fps` / `silent_source` / `_layout_why` 是同一个形状：
    **认领这一步把「想清楚了」和「凑合一下」分开。**
    """
    from tennislive.zh import player_zh

    payload = json.loads(CN_ROSTER.read_text(encoding="utf-8"))
    roster = payload["players"]
    assert len(roster) > 25, "名单塌了，这条判据没有主语"

    for entry in roster:
        admit = entry.get("admit")
        assert admit in ("singles-top500", "manual"), (
            f"{entry.get('zh')} 没写 `admit`（或者写了个不认识的值 {admit!r}）——"
            "收谁的规则写在 `_roster_note` 里，每条都要认领走的是哪一条")
        if admit == "manual":
            assert (entry.get("_why") or "").strip(), (
                f"{entry['zh']} 是手工收的，必须写 `_why` 说清为什么——"
                "不写理由的话下一个人既不敢删也不知道还该收谁")
        # 名单这一侧是死字符串，译名那一侧是函数输出，差一个字就永远对不上。
        assert player_zh(entry["en"]) == entry["zh"], (
            f"{entry['en']} 的译名是 {player_zh(entry['en'])!r}，"
            f"名单里写的是 {entry['zh']!r}——以 player_zh() 为准")

    # 暂缓收录的那几位要如实挂着，别默默消失：它们是「查过、译名还没定」，
    # 不是「没查过」。裸姓（一个字）正是不许收的那种，判据顺手钉住这一点。
    pending = payload.get("_pending_translation", [])
    assert pending, "`_pending_translation` 空了——那几位是查过的，别把账抹平"
    for row in pending:
        assert len(row["machine_zh"]) == 1, (
            f"{row['en']} 的 `machine_zh` 是 {row['machine_zh']!r}，不是裸姓了——"
            "译名定了就按规则 ① 收进 players，别留在待办里")
        assert row["en"] not in {p["en"] for p in roster}, (
            f"{row['en']} 同时出现在 players 和 _pending_translation 里")


def test_排名PDF里的国籍码不许再被扔掉():
    """**两份排名 PDF 里本来就写着 IOC 国籍码，解析器一直丢掉。**

    ATP 那份在同一行的括号里（`459  Cui, Jie (CHN) 102 …`），旧正则用的是
    **非捕获组**——匹配上了，然后丢掉；WTA 那份在名字的**下一行**
    （`ZHENG, SAISAI` / `CHN`），旧扫描根本没看那一行。

    代价是上面那两条测试记的事：中国球员名单只能靠人手抄，收谁没有标准，
    而漏一个人不吭声。存下国籍之后，「CHN 单打 top500 自动进」这条规则就能
    从快照直接算出来，不用再按拼音写法猜——那个启发式**有反例**：
    `Jia-Jing Lu`（逯佳境）带连字符却是大陆球员。

    ⚠️ **不是每一行都有国籍**（中立身份的球员那一栏是空的，实测 WTA 榜首就
    没有）。取不到时留空串，**不猜**——猜出来的国籍和查出来的长得一模一样。
    """
    from tools.update_player_names import parse_atp_text, parse_wta_text

    atp_text = "\n".join(
        f"{rank} Surname{rank}, Given{rank} (CHN) {1000-rank} 0 0 0"
        if rank == 7 else
        f"{rank} Surname{rank}, Given{rank} (USA) {1000-rank} 0 0 0"
        for rank in range(1, 501)
    )
    wta_blocks: list[str] = []
    for rank in range(1, 501):
        wta_blocks.extend([str(rank), f"({rank})", f"SURNAME{rank}, GIVEN{rank}"])
        # 第 9 名故意不给国籍：中立身份的球员在真 PDF 里就是这样，
        # 那一行直接是积分。解析器必须认得出这是「没有」，而不是把积分当国籍。
        if rank != 9:
            wta_blocks.append("CHN" if rank == 5 else "USA")
        wta_blocks.append("100")

    atp = parse_atp_text(atp_text)
    wta = parse_wta_text("\n".join(wta_blocks))
    assert len(atp) == 500 and len(wta) == 500, "先证明解析本身没坏"

    assert atp[6].country == "CHN", f"ATP 行内的 (CHN) 没收上来：{atp[6]}"
    assert atp[0].country == "USA", "ATP 国籍码收错了"
    assert wta[4].country == "CHN", f"WTA 下一行的 CHN 没收上来：{wta[4]}"
    assert wta[0].country == "USA", "WTA 国籍码收错了"
    assert wta[8].country == "", (
        f"没有国籍的那一行被填成了 {wta[8].country!r}——那是积分，不是国籍")

    # 反面：整份都收得上来，不是只有被断言的那两条碰巧对
    assert sum(1 for r in atp if r.country) == 500
    assert sum(1 for r in wta if r.country) == 499


def test_国籍要跟着进快照而且取不到就不写这个键():
    """`build_snapshot` 把 `RankedName.country` 原样带进快照条目。

    ⚠️ **取不到就整个不写这个键。** 写一个空串的话，「这一行 PDF 上没有国籍」
    和「这个人没有国籍」在快照里长得一模一样；缺键至少能用 `"country" in entry`
    分出来。

    ⚠️ 现存的 `player_names_top500.json` 是在这之前生成的，**一条 `country`
    都没有**，所以 `validate_snapshot` 不许要求它——真要求了那条校验对现存
    快照当场恒红，而「一条常年红的检查和没有检查是同一个毛病」。
    """
    from tools.update_player_names import (
        RANKING_LIMIT,
        RankedName,
        build_snapshot,
        validate_snapshot,
    )

    def rows(tour: str) -> list[RankedName]:
        out = []
        for rank in range(1, RANKING_LIMIT + 1):
            # 第 3 名故意没有国籍
            country = "" if rank == 3 else ("CHN" if rank == 4 else "USA")
            out.append(RankedName(tour, rank, f"{tour} Player {rank}",
                                  f"Sur{rank}", country))
        return out

    # ⚠️ 译名里不许混进拉丁字母——`build_snapshot` 自己就拦这个
    # （`re.search(r"[A-Za-z]", zh)`），第一版写成 `f"{t}球员{r}"`
    # 当场被它拦下，报的却是「has no Chinese name」。
    zh = {f"{t} Player {r}": f"球员{r}"
          for t in ("ATP", "WTA") for r in range(1, RANKING_LIMIT + 1)}
    import tools.update_player_names as mod

    original = mod._translation_lookup
    mod._translation_lookup = lambda: {
        " ".join(k.casefold().split()): (v, "curated-dictionary", "")
        for k, v in zh.items()}
    try:
        snap = build_snapshot(rows("ATP"), rows("WTA"),
                              ranking_date="2026-08-14", allow_machine=False)
    finally:
        mod._translation_lookup = original

    atp = snap["tours"]["ATP"]
    assert atp[3]["country"] == "CHN", "国籍没跟着进快照"
    assert atp[0]["country"] == "USA"
    assert "country" not in atp[2], (
        f"取不到国籍时写了 {atp[2].get('country')!r}——该整个不写这个键")

    # 现存快照没有 country，校验器不许因此报错。
    validate_snapshot(snap)
    legacy = {"tours": {t: [{k: v for k, v in e.items() if k != "country"}
                            for e in snap["tours"][t]]
                        for t in ("ATP", "WTA")}}
    validate_snapshot(legacy)
