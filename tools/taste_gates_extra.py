#!/usr/bin/env python3
"""账号所有者口味规则里**剩下那批**候选闸——逐条量过全库之后留下来的那几道。

来路：2026-09-27 账号所有者「总结我的口味和品味这种个性化的要求，形成一个通用的规则
在做视频前就拦掉，而不是说做了一半又返工」。口味规则书挖出 125 条，其中 32 条的闸
只有提案、没量过。这个模块是那 32 条逐条**先拿全库量**（已发的 spec 上报几条＝误伤，
被账号所有者打回的历史版本上报几条＝真阳）之后的结果：

- 误伤能压到 0（或者全是规矩定下之前已发的、挂进存量表）**而且**至少逮得住一个
  被打回的历史版本的，才进这里
- 已经有闸的（封面复用、原声双语、全称断言……）、别的包在做的、要量源片才判得了的，
  都**不在这里**——账和理由写在 ``notes`` 里，不在代码里假装做了

⚠️ 分两种出口，和仓库的老规矩一致：

- **硬的**：手写 spec 红（``--dry-run`` 0.2 秒就报）；自动产的 spec
  （``_production.status == "ready_for_render"``）只报不拦——那一头没人写认领，
  做硬会把自动链卡成「今天没有候选」
- **只报的**：判断题，机器只负责把它摆到眼前（``[口味] 只报``），不替人决定

几条是从 pytest 里**挪过来**的（收尾一问、推送标题剥完为空、制胜分/UE 认领、Tennis TV
片尾认领、quote 段认领、小红书 markdown）：它们原来只在 CI 上跑，会话手写的 spec 要等
CI 才红，挪进 `--dry-run` 之后 0.2 秒就红。⚠️ **自动链那一头这次只多了「看得见」，没多
「拦得住」**：自动出片链直推 main 不触发 CI（`andreeva-gauff` 就是这么带着一句「停在数据
上的收尾」发进微信的），而自动 spec 在这里一律只报不拦——同样那条 spec 今天会在 run 日志
里多印一行 `[口味] 只报`，照样发得出去。要真拦住自动链，得在自动链自己的闸上做，不在这儿。
挪过来之后**判据和存量表只有这一个出处**，测试 import 这里的，不再各抄一份（「一个数写
两处必分叉」）。

存量表一律**只许减不许加**，自检在 ``tests/test_taste_gates_extra.py``。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))


def _auto(spec: dict) -> bool:
    return (spec.get("_production") or {}).get("status") == "ready_for_render"


def _slug(spec: dict) -> str:
    return str(spec.get("slug") or "")


def _eyebrow(spec: dict) -> str:
    return str((spec.get("cover") or {}).get("eyebrow") or "").strip()


def _hook_text(spec: dict) -> str:
    """钩子两行拼成一句——两行本来就是一句话，换行只是排版。"""
    return "".join(str((spec.get("cover") or {}).get("hook") or "").split("\n"))


def _quote_texts(seg: dict) -> list[str]:
    raw = seg.get("quote")
    items = raw if isinstance(raw, list) else [raw] if raw else []
    out = []
    for item in items:
        text = item.get("text") if isinstance(item, dict) else item
        if text:
            out.append(str(text))
    return out


def _our_copy(spec: dict) -> list[str]:
    """**我们写的**字：旁白、cover/push/topbar 里非注解的字符串、钩子。不含原声段——
    `quote` 是解说／当事人自己的话的双语字幕，照实翻（账号所有者 2026-09-19「精彩的原声
    解说……配上中英文字幕保留下来」），管「我们的文案怎么写」的硬闸不许扫它。"""
    from spec_wording import outward_deep  # noqa: PLC0415

    return [str(t) for t in outward_deep(spec) if t] + [_hook_text(spec)]


def _outward(spec: dict) -> list[str]:
    """会发出去的字：`_our_copy` ＋ 原声段的双语字幕。只给只报的提醒用。"""
    texts = _our_copy(spec)
    for seg in spec.get("segments") or []:
        if isinstance(seg, dict):
            texts += _quote_texts(seg)
    return texts


def _hits(pattern: re.Pattern, texts) -> list[str]:
    return sorted({m.group(0) for t in texts for m in pattern.finditer(t or "")})


# ───────────────────────────────────────── ① 钩子／推送标题不拿全场总分差说事 ──

_N = r"[\d一二两三四五六七八九十百零]+"
#: 「全场只多赢一分」「总分九十七平」「她少赢了七个小分」。三盘球的总得分永远接近，
#: 这个数说不出这场球的形状（账号所有者 2026-09-13「不要写总分差距了」、2026-09-19
#: chung-nagal 第一版钩子「其实网球差距就在一两分的关键分」）。
#:
#: **这是这条规矩唯一的一份正则**——`taste_preflight` 摆事实用的也是它（原来各写一份，
#: 一个漏「总分落后18分」、一个把「全场多次破发」摆成总分说法）。四个形状：
#:
#: - 「总分／总得分／总小分」**裸词就算**：钩子和推送标题里出现它，说的只能是总得分。
#:   全库量过：已发的 12 条全在存量表里；自动草稿 126 份里 19 份（「高芙总分落后18分」
#:   「科斯秋克总得分领先遭逆转」「克维多总分打平」）——旧版只认得 8 份
#: - 「全场」**必须带一个「N 分」**（「全场落后9分」）：裸的「全场状态差」「全场一直领先」
#:   「全场发球差强人意」说的是状态，不是总分（review 探出来的三个误伤）
#: - 「多／少(赢|拿|得) N 分」：「多9分却输球」。前面是「至／最／不」的（至少三分）、
#:   后面跟「钟／之」的（多花十分钟、四分之一）不算
#: - 「N 个小分」
#:
#: ⚠️ 数字两边**允许空格**：「全场只多拿 6 分」是这个仓库最常见的写法（80 条带数字的钩子／标题里
#: 31 条这么写，已发的 zverev-sonego-us-open-2026-r1、tiafoe-michelsen 旁白都是）。合并两份正则时
#: 一度丢了 `\s*`，带空格的写法整批漏过（批次 4 复审抓到）——判据
#: `test_钩子里比全场总分差要拦` 的空格那几条。
#: ⚠️ 合并时放弃过 copy-strip 那份的一个分支：「全场只?(?:多|少)赢?」不要求带「N 分」，
#: 所以认得「全场多赢一个球」（单位是球）和「全场多出 26 分」（动词是「出」）——合并版
#: 两个都漏了（批次复审 nit：自动草稿 snigur-shnaider 的 thesis 正写着「全场多出26分」，
#: thesis 会喂钩子）。2026-09-27 收回来，但不照抄那个不带数的分支：动词表补「出」，
#: 「全场…多/少…N 个球」单列一支（单位是球只在「全场」后面认，「多一个球」单说太宽）
#: ——照旧不误伤「全场多次破发」「全场一直领先」。
#: ⚠️ 故意不收裸的「差 N 分」：「只差一分被拖进决胜盘」是他接受过的钩子，那一分是关键分。
TOTAL_MARGIN = re.compile(
    rf"总分|总得分|总小分"
    rf"|全场[^\n，。]{{0,8}}?(?:领先|落后|只差|差)\s*{_N}\s*个?小?分(?!钟|之)"
    rf"|(?<![至最不])(?:多|少)(?:赢|拿|得|出)?了?\s*{_N}\s*个?小?分(?!钟|之)"
    rf"|全场只?(?:多|少)(?:赢|拿|得|出)?了?\s*{_N}\s*个球"
    rf"|{_N}\s*个小分")

#: 2026-09-19 那条规矩之前已经发出去的。全库量过：钩子／推送标题里写总分差的 12 条，
#: **最晚一条是 09-12**，规矩之后 0 条——也就是说这 12 条全是规矩定下之前的写法，
#: 不是这道闸的误伤。已发的不为文案重渲。
TOTAL_MARGIN_LEGACY = frozenset({
    "bejlek-keys-cincinnati-2026-qf",   # 总分一百零七平（08-22）
    "boulter-volynets",                 # 她少赢了七个小分（08-15）
    "fritz-cerundolo-us-open-2026-r3",  # 两盘领先 多拿两分（09-06）
    "fritz-nakashima-cincinnati-2026-qf",  # 总分九十七平（08-22）
    "kenin-lys",                        # 总分却是七十一平（08-15）
    "navarro-kalinina",                 # 一百六十九个小分／她只多赢了一个（08-16）
    "rybakina-gauff-us-open-2026-sf",   # 全场只多赢六分（09-11）
    "safiullin-alcaraz-us-open-2026-r1",  # 总分只差八分（09-01）
    "snigur-keys",                      # 全场只多赢四分（08-17）
    "wang-kalinskaya-us-open-2026-r2",  # 推送标题：王欣瑜多拿一分仍然出局
    "wu-duckworth-us-open-2026-r2",     # 首盘只多赢四分（09-03）
    "zverev-khachanov-us-open-2026-sf",  # 全场只多赢三分（09-12）
})


#: 这条管**比赛片**的钩子：账号所有者那两句（09-13、09-19 chung-nagal）说的都是一场球的
#: 封面。「网球有故事」讲规则和来路，「总得分多却输了比赛」本身就是一个正经的计分故事，
#: 不在这条里。`cover.eyebrow` 空着按「赛场之上」算（和 `build_cover` 同一个缺省，
#: 自动草稿就是空的）；赛后开麦由 `interview_taste_extra` 带着栏目名进来。
TOTAL_MARGIN_COLUMNS = frozenset({"", "赛场之上", "赛后开麦"})


def total_margin_problem(spec: dict) -> str | None:
    if _slug(spec) in TOTAL_MARGIN_LEGACY or _eyebrow(spec) not in TOTAL_MARGIN_COLUMNS:
        return None
    fields = (("钩子", _hook_text(spec)),
              ("推送标题", str((spec.get("push") or {}).get("summary") or "")))
    bad = [f"{name}「{m.group(0)}」" for name, text in fields
           for m in TOTAL_MARGIN.finditer(text)]
    if not bad:
        return None
    return ("钩子／推送标题拿全场总分差说事：" + "、".join(bad) + "。\n"
            "账号所有者 2026-09-19：「以后尽量避免比较全场得分只差几分……其实网球差距就在"
            "一两分的关键分」。差距写在关键分上（几个盘点、赛点，对手救下了几个——钩子里"
            "不写「破发」「抢七」，账号所有者 2026-09-27），或者拿人物的来路当影子"
            "（chung-nagal「背伤毁掉的生涯／他咬了三小时翻回来」）。旁白和小红书正文不管。")


# ─────────────────────────────────────── ② 「三个赛点只兑现了一个」的同义反复 ──

#: 赛点／盘点是「兑现即终止」的点：赢家永远只兑现最后一个，「N 个只兑现了一个」
#: 不是短板，是同义反复（账号所有者 2026-08-19「这种文案是有问题的，以后杜绝类似
#: 的弱智文案」）。**只认赛点和盘点**——破发点分散在十几个发球局里，2/13 是真会
#: 变的效率，不是「N 选 1」的同义反复（berrettini-wawrinka「十三个破发点／他只兑现两个」
#: 这道闸不拦）。⚠️ 这只说它**不是同义反复**，不说它是好钩子：2026-09-27 起钩子里
#: 「破发」「抢七」都不用（O6），那是另一道判据的事。
ONE_OF_N = re.compile(r"(赛点|盘点)[^。！？\n]{0,8}只(兑现|转化|拿下|把握住?)了?[一1]个")

#: 就是账号所有者点名的那一条，已发。
ONE_OF_N_LEGACY = frozenset({"bouzkova-jovic"})


def _one_of_n_claimed(spec: dict) -> bool:
    """spec 顶层 `_one_of_n_why` 认领（2026-09-27 复审 nit）：**盘点跨盘不一定是同义反复**——
    一盘里盘点没拿下、丢了这一盘，后一盘再兑现一个（「两盘下来三个盘点只兑现了一个」）
    是真会变的效率。判据是「这几个点是不是同一个终止单元里的同一串」（tennis-editorial），
    正则分不出来，所以给手写 spec 一个和别的 `_why` 同形状的口；豁免表只许减，不是出口。
    赛点对赢家恒是同义反复，认领口照样开着——写不出为什么就别写。"""
    return bool(str(spec.get("_one_of_n_why") or "").strip())


def one_of_n_problem(spec: dict, xhs_text: str | None = None) -> str | None:
    """只扫我们写的字（`_our_copy` ＋ 小红书正文），不扫原声段：解说喊一句「三个盘点只
    拿下一个」照实配双语字幕，不许因此把手写 spec 拦在渲染入口——和采访那边不扫 `zh`
    同一个形状（`test_赛点同义反复只管我们的文案_解说原声照实翻`）。
    认领口 spec 顶层 `_one_of_n_why`（见 `_one_of_n_claimed`）。"""
    if _slug(spec) in ONE_OF_N_LEGACY or _one_of_n_claimed(spec):
        return None
    hits = _hits(ONE_OF_N, _our_copy(spec) + ([xhs_text] if xhs_text else []))
    if not hits:
        return None
    return (f"写了「N 个赛点／盘点只兑现了一个」：{hits}——赢家永远只兑现最后一个，"
            "这是同义反复（账号所有者 2026-08-19「以后杜绝类似的弱智文案」）。"
            "要写就写对手救下了几个（「约维奇连救两个」「五个赛点，一个没给」）。")


# ─────────────────────────────────────────────── ③ 不提彭帅（只报，永不做成闸） ──

PENG_SHUAI = re.compile(r"彭帅|Peng\s*Shuai|Shuai\s*Peng", re.I)


def peng_shuai_note(texts) -> str | None:
    """**只报**。这条在口味规则书（`tennis-owner-taste`）里标的是「转述（09-16）」：
    `research/wta-finals-venues-2026.md` 里会话记下的，**没有他的原话**。账号所有者
    2026-09-27 选定：转述／推断来的规则只按自查过，**没有他的原话之前不许做成闸**
    （SKILL 头部那段；`test_推断出来的口味规则永不做成闸` 钉的就是这个）。

    所以三个入口（`spec_taste_extra`／`xhs_taste_extra`／`interview_taste_extra`）
    都把它放进只报的那一半——硬的那一半注进「彭帅」和注进「李娜」必须一模一样
    （`test_不提彭帅是转述来的_三个入口都只报不拦`）。做成硬闸的那一版会把一条
    如实翻译球员提到彭帅的采访字幕拦在渲染入口、把含这句字幕的自动采访草稿挡在转正外。
    """
    hits = _hits(PENG_SHUAI, texts)
    if not hits:
        return None
    return (f"会发出去的字里提了彭帅：{hits}。口味规则书里这条是**转述**（09-16，"
            "research/wta-finals-venues-2026.md 里会话记的，没有他的原话），只按自查过、"
            "不拦：确认一下这里是不是真要提——讲深圳合同为什么断，写到「疫情停办、此后没再"
            "回去」就够；采访字幕是当事人的原话，照实翻。注解栏（`_` 开头的键）不管。")


# ─────────────────────────────────────── ④ 赛场之上封面不用 fit:width 的信箱式 ──

#: 已发的两条：`wangxiyu-fernandez`（2026-08-17，规矩之前）和 `zheng-keys-us-open-2026-r3`
#: （09-06，写了 `_fit_why`，推送之后没人提——但按这条的口径它也是信箱式）。
FIT_WIDTH_LEGACY = frozenset({"wangxiyu-fernandez", "zheng-keys-us-open-2026-r3"})


def cover_fit_problem(spec: dict) -> str | None:
    """⚠️ **`_fit_why` 在「赛场之上」不放行，是量出来的**：账号所有者 2026-08-31 否掉的
    zhang-fernandez 那一版（008a8806）**正写着一段很认真的 `_fit_why`**（「源图 1280×720
    横构图，cover 要放大 2.00 倍……两版真渲出来比过」）——而他的回答是「建议还是裁切铺满
    画布全屏做封面，不要用当前这种方式了」，改完用的正是 2.0× 放大。认领口一开，被否掉的
    那一版照样过闸。「网球有故事」的信箱式不在这条里。
    """
    if _eyebrow(spec) != "赛场之上" or _slug(spec) in FIT_WIDTH_LEGACY:
        return None
    portrait = (spec.get("cover") or {}).get("portrait")
    if not isinstance(portrait, dict) or portrait.get("fit") != "width":
        return None
    return ("「赛场之上」封面写了 `cover.portrait.fit: \"width\"`——人物只占中段，上下两条"
            "模糊带。账号所有者 2026-08-31：「建议还是裁切铺满画布全屏做封面，不要用当前这种"
            "方式了」；2026-09-06：「封面要全铺满」。\n"
            "删掉 `fit`（默认 cover 裁切铺满），用 `zoom` / `focus` / `focus_y` 把人物放到"
            "几何中心、接近铺满、四周留一圈（横构图 1280×720 的那张放大 2.0× 用的就是这条路）。"
            "⚠️ `_fit_why` 在这一栏不放行——被否掉的那一版正写着一段 `_fit_why`。")


# ──────────────────────────────── ⑤ 赛场之上封面一律 solo，`_layout_why` 不再放行 ──

#: 2026-08-04「以后都用 solo 版」之前、带 `_layout_why` 钉成 diagonal 的两条（已发）。
#: 其余存量是 `build_match_reel._LEGACY_VS_COVERS`，两张表合起来用，不另抄一份。
SOLO_EXTRA_LEGACY = frozenset({"eala-zheng", "nishikori-shang"})


def legacy_vs_covers() -> frozenset[str]:
    """`build_match_reel._LEGACY_VS_COVERS`。`--dry-run` 是把 build_match_reel 当
    `__main__` 跑的，按模块名再 import 一遍等于把一万行的工具再加载一次——先找已经
    加载的那份。"""
    for name in ("build_match_reel", "__main__"):
        table = getattr(sys.modules.get(name), "_LEGACY_VS_COVERS", None)
        if table is not None:
            return frozenset(table)
    from build_match_reel import _LEGACY_VS_COVERS  # noqa: PLC0415
    return frozenset(_LEGACY_VS_COVERS)


def solo_layout_problem(spec: dict) -> str | None:
    """`build_cover` 那道闸认 `_layout_why`：写一句就能退回 VS。**而账号所有者正是在
    一条写了 `_layout_why` 的 VS 封面上说了不**——shang-mannarino 42cfae85（「solo 要的
    本场官方实拍出片时不存在」），2026-09-24：「不要用这种封面……还不如从比赛画面中截取
    抽帧去做」。所以「赛场之上」这一栏认领口关掉：没有实拍就挑一帧清晰的抽帧。
    「网球有故事」讲两个人的交手史照旧可以用 H2H 双人版（`build_cover` 那边不动）。
    """
    if _eyebrow(spec) != "赛场之上":
        return None
    layout = str((spec.get("cover") or {}).get("layout", "cutout"))
    if layout == "solo":
        return None
    if _slug(spec) in legacy_vs_covers() | SOLO_EXTRA_LEGACY:
        return None
    return (f"「赛场之上」的封面写的是 layout={layout!r}。这一栏一律 solo：本场实拍铺满，"
            "下面一块带双方国旗和排名的比分板。**`_layout_why` 在这一栏不再放行**——"
            "账号所有者 2026-09-24 否掉的正是一条写了认领的 VS 封面（shang-mannarino）："
            "「不要用这种封面……还不如从比赛画面中截取抽帧去做」。没有官方实拍就用 "
            "`cover.portrait.frame_at` 挑一帧清晰、偏正面的。")


# ─────────────────── ⑥ 前瞻事实写了「要等 X」，渲之前回头查 X：**不在这个模块** ──
#
# 它的闸是 `reel_facts.waiting_fact_problem`（认领 spec 顶层 `_rechecked_at`；渲染入口
# 另拿发布账本比 `waiting_fact_stale_problem`），`validate_spec` 经 `time_sensitive_gate`
# 调它。这里曾另写过一份（认领 `_pending_resolved`）：两道闸各不认对方的字段，只写
# `_rechecked_at` 被这一份拦、只写 `_pending_resolved` 被那一份拦（它把注解里的这个字段
# 当成「还没定」又扫一遍），CI 的全库扫描也跟着红。同一条规矩只许一道闸。


# ─────────────────────────── ⑦ 收尾要落在一问上（挪自 tests/test_match_reel.py） ──

#: 收尾没落在一问上、而且**已经发出去了**的。只许减不许加，自检在测试里。
ENDING_LEGACY = frozenset({
    # `eala-parks` 收在「六比二，晋级第三轮。」这句数据上。
    "eala-parks",
    # `shang-darderi-montreal-2026` 收在「四比五，他救下两个赛点。」这句数据上。
    "shang-darderi-montreal-2026",
    # `zheng-you-us-open-2026-q1` 收在「……零次被破发，是这场胜利最硬的答案。」
    # 这句数据上。它 2026-08-25T01:53:09Z 已经推过微信（run 32799209180），
    # 收尾那句烧在音轨和字幕里，不为措辞重渲。
    "zheng-you-us-open-2026-q1",
    # `andreeva-gauff` 收在「全场总得分九十五比九十四，高芙只多拿一分。
    # 她救回两个赛点，把这场胜利拼到了手里。」这句数据上。它
    # 2026-09-10T00:43:27Z 已经推过微信（发布台账 `sent`）。它是**自动链产的**，
    # 而这条判据当时只活在 pytest 里——自动链直推 main 不触发 CI。挪进
    # `validate_spec` 之后自动 spec 也会在 dry-run 里被报出来。
    "andreeva-gauff",
})


def ending_offender(spec: dict) -> str | None:
    """停在数据上的那句收尾（没落在一问上），落在一问上返回 None。

    末尾一问落在「最后一句 narration」或者「真正的最后一段（narration 或 quote 的中文
    那半行）」任意一处就算数——gauff-bejlek 的末拍是转播原声「这一次，她能拿下吗？」。
    只看最后一段的末尾，不数问号个数：中间抛几问是写稿的选择。
    """
    segs = [s for s in spec.get("segments") or [] if isinstance(s, dict)]
    nars = [str(s.get("narration") or "") for s in segs]
    nars = [n for n in nars if n]
    last_narration = nars[-1] if nars else ""
    true_last = ""
    last_seg = segs[-1] if segs else {}
    nar = str(last_seg.get("narration", "")).strip()
    if nar:
        true_last = nar
    else:
        quote = last_seg.get("quote")
        if isinstance(quote, str) and quote.strip():
            true_last = quote.strip()
        elif isinstance(quote, list) and quote:
            entry = quote[-1]
            text = entry.get("text", "") if isinstance(entry, dict) else str(entry)
            zh = str(text).split("\n")[-1].strip()
            true_last = zh or str(text).strip()
    if not last_narration and not true_last:
        return None
    if "？" in last_narration[-30:] or "？" in true_last[-30:]:
        return None
    return (true_last or last_narration)[-26:]


def ending_problem(spec: dict) -> str | None:
    if _slug(spec) in ENDING_LEGACY:
        return None
    # User explicitly requested the real Tokyo farewell thanks as the ending
    # for this film (2026-10-04). Do not rewrite a player's quote into a question.
    # Scope to the actual official source and literal, complete closing quote;
    # only a five-second graphic with that same source's applause may follow.
    if _slug(spec) == "nishikori-career-farewell" and _eyebrow(spec) == "网球有故事":
        segs = spec.get("segments") or []
        if len(segs) >= 2:
            speech, brand = segs[-2:]
            sources = spec.get("sources") or {}
            official = "https://x.com/japanopentennis/status/2105641498721284153"
            if (sources.get(speech.get("source")) == official
                    and sources.get(brand.get("source")) == official
                    and speech.get("start") == 313 and speech.get("end") == 323
                    and _quote_texts(speech) == ["本当にありがとうございました\n真的非常感谢大家"]
                    and not speech.get("narration")
                    and brand.get("start") == 315 and brand.get("end") == 320
                    and brand.get("visual_image")
                    and not brand.get("narration") and not brand.get("quote")):
                return None
    tail = ending_offender(spec)
    if tail is None:
        return None
    return (f"收尾停在数据上，没有落在一问上：…{tail}\n"
            "账号所有者：「不要平白地叙事，要能引爆传播」。最后一段要么旁白问出一个针对"
            "这场的问题，要么留一句带问号的原声；先用一个数字回答开场的问题，再抛下一问。"
            "往积极的方向落——请读者期待他兑现，不是请读者怀疑他。")


# ─────────── ⑧ 推送标题：剥完名字和赛果动词要还剩东西（挪自 tests/test_reel_editorial.py） ──

#: 动词表只用来**剥**：漏掉一个动词的后果是漏判，不是误伤，方向是安全的那一头。
RESULT_VERB = re.compile(
    r"(晋级|淘汰|横扫|逆转|击败|险胜|过关|出局|收官|锁定|苦战|拿下|战胜|获胜|胜)")

SUMMARY_LEGACY_已推送 = frozenset({
    # ⚠️ 这条是这道判据落地（#332）的同一天做的，两边并行，改完 spec 才撞上。
    #    它 08-14 03:2x 已经自动推送过了——`push.summary` 参与拼微信标题，
    #    改它会让今天算出来的标题和当时真发出去的那条对不上（eala-osaka 那条
    #    「故意不补 summary」记的就是这个），所以按已推送挂账，不改字。
    "landaluce-draper",            # 兰达卢塞逆转
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
SUMMARY_LEGACY_还没推送 = frozenset({
    "rybakina-li",                    # 莱巴金娜逆转晋级
    "rybakina-osaka",                 # 莱巴金娜逆转大坂直美
    "swiatek-svitolina-toronto-sf",   # 斯瓦泰克逆转晋级
})

SUMMARY_LEGACY = SUMMARY_LEGACY_已推送 | SUMMARY_LEGACY_还没推送

#: 两个本该连读的动词中间插了代词（「决胜局四十比零落后**她**逆转」）——账号所有者
#: 2026-08-20「标题写的要有钩子，但是你要写的通顺」。全库量过只有被点名的那一条。
SUMMARY_PRONOUN_SPLIT = re.compile(r"落后(她|他)(逆转|翻盘|赢)")
SUMMARY_FLUENCY_LEGACY = frozenset({"kostyuk-andreeva"})


def summary_strip_offender(spec: dict) -> str | None:
    """「赛场之上」推送标题剥掉名字和赛果动词之后什么都不剩的，返回那个标题。"""
    cover = spec.get("cover") or {}
    if cover.get("eyebrow") != "赛场之上":
        return None
    summary = str((spec.get("push") or {}).get("summary") or "").strip()
    if not summary:
        return None
    rest = summary
    names = [str(m.get("name") or "") for m in (cover.get("matchup") or [])]
    names += [str(cover.get("winner") or ""), str(cover.get("subject") or "")]
    for name in names:
        if name.strip():
            rest = rest.replace(name.strip(), "")
    rest = RESULT_VERB.sub("", rest)
    return None if re.sub(r"[，,。、·\s]", "", rest) else summary


def push_summary_problem(spec: dict) -> str | None:
    slug = _slug(spec)
    out = []
    if slug not in SUMMARY_LEGACY and (summary := summary_strip_offender(spec)):
        out.append(f"推送标题「{summary}」剥掉名字和赛果动词之后什么都不剩——「谁逆转晋级」"
                   "在微信消息列表里分不出是哪一条片子；同一份 spec 的 `push.lead` 里往往"
                   "就躺着那句该当标题的话（下一轮的强敌、关键分、来路）。")
    summary = str((spec.get("push") or {}).get("summary") or "")
    if slug not in SUMMARY_FLUENCY_LEGACY and (m := SUMMARY_PRONOUN_SPLIT.search(summary)):
        out.append(f"推送标题「{summary}」在两个连读的动词中间插了代词（{m.group(0)}）——"
                   "一句只留一层铺垫：「零比二落后连赢六局」（账号所有者 2026-08-20「要写的"
                   "通顺」）。")
    return "\n".join(out) or None


# ──────────── ⑨ 数据图缺制胜分/UE 要写 `_winners_ue_why`（挪自 tests/test_reel_editorial.py） ──

#: 这条闸上线之前就写好的全部。里面包括 `zverev-norrie` 那一类——那两行数字一直
#: 拿得到，而它发出去的时候没有。已发的片子不重渲，只挂账，只管以后。
WINNERS_UE_LEGACY = frozenset({
    "baez-dimitrov", "bejlek-pliskova", "boisson-krueger", "boulter-volynets",
    "bucsa-chwalinska", "cirstea-bartunkova", "eala-ruse", "hijikata-monfils",
    "jodar-shapovalov", "kenin-lys", "maria-yastremska", "navarro-kalinina",
    "noskova-boulter", "ostapenko-frech", "parry-mertens", "pegula-waltert",
    "sonmez-anisimova", "sonmez-kasatkina", "stearns-tauson", "townsend-osorio",
    "tsitsipas-royer", "wang-vandewinkel", "wangxiyu-timofeeva",
})


def winners_ue_missing(spec: dict) -> bool:
    """「赛场之上」有 `stats` 块、却缺制胜分/非受迫失误、又没说查过 TNNS。

    两边都要查：`render_stat_card.usable_rows` 对「只有一边有」是报错的。整块没有
    归 `reel_asset_gates.stats_card_problem` 管。
    """
    if _eyebrow(spec) != "赛场之上" or not spec.get("segments"):
        return False
    stats = spec.get("stats")
    if not stats:
        return False
    a, b = stats.get("a") or {}, stats.get("b") or {}
    if all(key in a and key in b for key in ("winners", "ue")):
        return False
    return not stats.get("_winners_ue_why")


def winners_ue_problem(spec: dict) -> str | None:
    if _slug(spec) in WINNERS_UE_LEGACY or not winners_ue_missing(spec):
        return None
    return ("数据图缺制胜分/非受迫失误，又没写 `stats._winners_ue_why`。**flashscore 没有 ≠ "
            "没有**——TNNS Live 这两行按场给（账号所有者 2026-08-16「tnns live 有啊」）：\n"
            "    gh workflow run tnns-stats.yml -f who=<姓>,<姓>\n"
            "拿到就填进 `stats.a/b` 的 `winners` / `ue`；五类源都查空才写一句 "
            "`stats._winners_ue_why` 记下来。")


# ────────── ⑩ Tennis TV 源片要说清片尾和台标怎么剪（挪自 tests/test_match_reel.py） ──

#: 用 Tennis TV 源片、而且发在「片尾和台标要剪掉」这条规矩（账号所有者 2026-08-16）
#: 之前的片子。已发的不重渲——**只许减不许加**。
TENNISTV_LEGACY = frozenset({
    "baez-dimitrov", "djokovic-tirante", "eala-svitolina", "fonseca-ruud",
    "fritz-jodar-final", "gea-shapovalov", "hewitt-washington",
    "hijikata-monfils", "kovacevic-khachanov",
    "landaluce-draper", "medvedev-zandschulp", "nakashima-jodar-montreal-sf",
    "shang-darderi-montreal-2026", "shang-vallejo", "shelton-fonseca",
    "shelton-nakashima-montreal-final", "shelton-tien-montreal-sf",
    "tirante-fritz", "tsitsipas-royer", "wang-samsonova", "wong-brooksby",
    "wong-gea", "wong-lehecka", "zverev-griekspoor",
})


def uses_tennistv(spec: dict) -> bool:
    """只看 `_source` 和 `_editing_why` 这两栏（我们自己写的来路交代）——`_no_repeat`
    里会点名别的片子，整份扫会误判。判据宁可窄，不可宽。"""
    blob = " ".join(str(spec.get(k) or "") for k in ("_source", "_editing_why"))
    return "Tennis TV" in blob or "TennisTV" in blob


def tennistv_trim_problem(spec: dict) -> str | None:
    if _slug(spec) in TENNISTV_LEGACY or not uses_tennistv(spec):
        return None
    if str(spec.get("_tennistv_trim") or "").strip():
        return None
    return ("用了 Tennis TV 的源片，却没写 `_tennistv_trim`。账号所有者 2026-08-16：「把后面 "
            "tennis tv 的片尾也裁剪掉啊」「最好把右上角的 tennistv logo 裁剪掉」——写一句说清"
            "末段离片尾板多远、取景窗有没有把角上那块台标框进来（「忘了看」和「看过了没问题」"
            "在成片上分不出来）。")


# ───────── ⑪ 赛场之上的 quote 段只认转播原声／颁奖现场声（挪自 tests/test_match_reel.py） ──

QUOTE_KINDS = frozenset({"broadcast", "ceremony"})
#: 账号所有者 2026-08-10 点名的四条（quote 窗口全落在 WTA 纯集锦 310 秒之后），已发。
QUOTE_KIND_LEGACY = frozenset({
    "rybakina-samsonova", "alexandrova-sabalenka", "osaka-mertens", "swiatek-kostyuk",
})


def quote_kind_offenders(spec: dict) -> list[int]:
    """「赛场之上」里没认领 `_quote_kind`（或认领了不合法的值）的 quote 段序号（1 起）。"""
    if _eyebrow(spec) != "赛场之上":
        return []
    return [i for i, seg in enumerate(spec.get("segments") or [], 1)
            if isinstance(seg, dict) and seg.get("quote")
            and seg.get("_quote_kind") not in QUOTE_KINDS]


def quote_kind_problem(spec: dict) -> str | None:
    if _slug(spec) in QUOTE_KIND_LEGACY:
        return None
    bad = quote_kind_offenders(spec)
    if not bad:
        return None
    return (f"第 {bad} 段的 quote 没认领 `_quote_kind`（broadcast／ceremony）。账号所有者："
            "「赛场之上视频不要赛后采访」——那是赛后开麦的素材，另出一条；转播解说原声、"
            "颁奖现场声才许留，写上认领。")


# ─────────────────────── ⑫ 小红书正文是纯文本（挪自 tests/test_match_reel.py） ──

#: 出口（复制页 textarea、微信正文）不渲染 markdown，粘过去会原样露出来。**不管 `-`
#: 开头的行**（粘过去就是一个横杠）；tag 行 `#网球时差` 不误伤（ATX 标题要带空格）。
XHS_MARKS = (
    ("星号（**加粗** / *斜体*）", re.compile(r"\*")),
    ("反引号", re.compile(r"`")),
    ("下划线强调 __", re.compile(r"__")),
    ("表格竖线", re.compile(r"^\s*\|", re.M)),
    ("# 标题", re.compile(r"^#{1,6}\s", re.M)),
    ("> 引用", re.compile(r"^>\s", re.M)),
    ("[]() 链接", re.compile(r"\[[^\]]*\]\([^)]*\)")),
)


def xhs_markdown_hits(text: str) -> list[str]:
    return [f"{name}×{len(pat.findall(text))}" for name, pat in XHS_MARKS if pat.search(text)]


def xhs_markdown_problem(text: str | None) -> str | None:
    hits = xhs_markdown_hits(text or "")
    if not hits:
        return None
    return (f"小红书正文里有 markdown 记号：{hits}。账号所有者 2026-08-06：「正文里复制的内容，"
            "不要用 markdown 格式，复制过去显示会有问题」——出口不渲染它，粘过去会原样露出来。")


# ═══════════════════════════ 只报的四道（③ 彭帅那条也只报，住在上面它自己那一节） ══

#: 钩子写身份：非头号的种子号、「世界第 N」（N≠1）。「掀翻世界第一」「淘汰头号种子」
#: 是结果行的重量，放行；其余的要自己确认它不是「只靠排名」。
HOOK_IDENTITY = re.compile(
    r"世界第(?!一(?![\d一二三四五六七八九十百]))[\d一二三四五六七八九十百]+"
    r"|(?<!头)(?<![\d一二三四五六七八九十])(?!(?:1|一)号)[\d一二三四五六七八九十]+号种子")


def hook_identity_note(spec: dict) -> str | None:
    cover = spec.get("cover") or {}
    if _eyebrow(spec) != "赛场之上" or str(cover.get("_hook_identity_why") or "").strip():
        return None
    hits = _hits(HOOK_IDENTITY, [_hook_text(spec)])
    if not hits:
        return None
    return (f"钩子里写了身份 {hits}——账号所有者 2026-08-05「你这个只靠排名，这个太机械化、"
            "固定化了」、2026-09-26「封面别说淘汰八号种子，说挺进 8 强」。结果行写本人走到"
            "哪一步；对手的身份只在够分量（头号种子、世界第一）时才当落点。确认过写 "
            "`cover._hook_identity_why`。")


#: 球员的声明（退赛、伤情、复出、告别）要先去本人和官方的 X、Instagram 找当事人开口
#: 的视频（sinner-beijing-withdrawal-2026，账号所有者 2026-09-25「多去找找 X 和
#: Instagram」「建议把辛纳自己的视频加在最前面」）。
SOCIAL_TOPIC = re.compile(r"退赛|退出|伤病|伤情|复出|告别|声明|withdraw|retire|injur", re.I)


def social_first_note(spec: dict) -> str | None:
    if _eyebrow(spec) != "网球有故事" or str(spec.get("_social_checked") or "").strip():
        return None
    cover = spec.get("cover") or {}
    blob = " ".join([_slug(spec), str(cover.get("hook") or ""), str(cover.get("topic") or "")])
    m = SOCIAL_TOPIC.search(blob)
    if not m:
        return None
    return (f"讲的是球员声明一类（{m.group(0)}）：先去本人和官方的 X、Instagram 找当事人自己"
            "开口的视频，放第 1 段当冷开场、配中英双语，别拿旁白转述他的话。查过写 "
            "`_social_checked`（查了哪些账号、结果如何）。")


#: 给人看的字里的**计数**汉字数字（「三天前」「八号种子」「三盘」）。序数（第…）、术语
#: （抢七／抢十）、「世界第一」、「一个没给」「两个赛点」这类惯用说法不在里面——
#: `arabic_numerals` 直接喂手写字段会把「抢十」换成「抢10」、把「第180三盘」粘成
#: 「第1803盘」，所以这里只认「二~九开头、后面跟量词」的计数。
#:
#: 两个不是计数的形状要让开（review 探出来的）：副词「十分漂亮」（「十分钟」照旧算——
#: 「三十四分钟」写进钩子正该是「34分钟」）、分数「四分之一」（轮次另有「1/4决赛」那道闸）。
#: ⚠️ 全库 307 条里约一半会报——**那不是误伤率**：抽出来全是「五局」「三个赛点」这类真计数，
#: 是 2026-09-16 那条规矩之前的写法（spec 里没有可靠的日期字段，按日期切不了）。
#: 只报的闸只对手上这一条出声，新写的 spec 报了就是真该改。
SCREEN_COUNT = re.compile(
    r"(?<![第抢世界星期周礼拜一二三四五六七八九十百千万两〇零])(?!十分(?!钟))"
    r"([二三四五六七八九十][一二三四五六七八九十百千]*|一[十百千][一二三四五六七八九十百千]*)"
    r"(?=个|次|天|周|年|月|岁|局|盘|分(?!之)|场|拍|座|支|位|名|小时|号种子|连胜|连败|届|站|城)")


#: 发布账本里记着「已经发出去」的状态（竖版短片账本写 `sent`，采访账本写 PushPlus 的 `accepted`）。
_DELIVERED = frozenset({"sent", "accepted"})


def reel_ledger_dir() -> Path:
    """竖版短片的发布账本——只认 `reel_facts.REEL_LEDGER_DIR` 这一个出处（它认
    `TENNISLIVE_REEL_LEDGER_DIR`，`tests/conftest.py::_empty_reel_ledger` 钉得住）。
    **调用时再取**：模块级抄一份的话 monkeypatch 够不着，判据测试就只能读真账本。"""
    import reel_facts  # noqa: PLC0415

    return Path(reel_facts.REEL_LEDGER_DIR)


def interview_ledger_dir() -> Path:
    """采访线的发布账本——只认 `auto_push_interview_gate.LEDGER_DIR`（相对仓库根）。

    设了 `publication_ledger.INTERVIEW_LEDGER_ENV` 就只读那个目录：和
    `publication_ledger.interview_published` 同一个钉法（`tests/conftest.py::
    _empty_interview_ledger`），判据测试不读真账本——竖版短片那半边 `reel_ledger_dir`
    认 `TENNISLIVE_REEL_LEDGER_DIR` 是同一条。**调用时再取**。"""
    import os  # noqa: PLC0415

    from publication_ledger import INTERVIEW_LEDGER_ENV  # noqa: PLC0415

    if pinned := os.environ.get(INTERVIEW_LEDGER_ENV):
        return Path(pinned)
    import auto_push_interview_gate  # noqa: PLC0415

    return ROOT / auto_push_interview_gate.LEDGER_DIR


def already_published(slug: str, ledger_dir: Path) -> bool:
    """`<ledger_dir>/<slug>.json` 里有一条发出去了的记录。读一个文件，不扫目录。
    `ledger_dir` 从 `reel_ledger_dir()` / `interview_ledger_dir()` 拿，别在这儿再拼一份路径。

    只给「汉字数字」那条只报用：它在全库 307 条里报一半（规矩之前的写法），而已发的不为
    文案重渲——对一条已经发出去的片子每趟 dry-run 都印一遍，只会把它训练成没人看的噪音
    （review 量过：09-17 之后手改的 114 条里 35 条会印）。⚠️ 账本 2026-08-24 起才有，更早
    发的那批查不到、照旧会印；那批本来就很少再被跑到。"""
    try:
        doc = json.loads((Path(ledger_dir) / f"{slug}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    attempts = doc.get("attempts") if isinstance(doc, dict) else None
    return any(isinstance(a, dict) and a.get("status") in _DELIVERED for a in attempts or [])


def screen_numerals_note(fields) -> str | None:
    """fields: [(字段名, 文本)]。只报：写成阿拉伯数字（账号所有者 2026-09-16）。
    已经发出去的片子由调用方跳过（`already_published`）。"""
    bad = [f"{name}「{str(text)[m.start():m.end() + 2]}」" for name, text in fields
           for m in SCREEN_COUNT.finditer(str(text or ""))]
    if not bad:
        return None
    return ("给人看的字里的数字写成了汉字：" + "、".join(bad) + "——账号所有者 2026-09-16"
            "「给用户看的文案里的数字不要用汉字，就用 2025 之类的阿拉伯数字」（TTS 底稿照旧写"
            "汉字；序数、抢七、万不换）。")


#: 英文里的昵称、简称不另外音译成一个新名字（账号所有者 2026-09-06「麦迪是凯斯名字的
#: 简称」，258269d6）。**只收被点过名的**——「萨沙」「伊加」这类直呼名在已发的采访
#: 字幕里有几十处，账号所有者没说过不行，这张表只随真实的投诉长。
NICKNAMES = {"麦迪": "凯斯"}


def nickname_note(texts) -> str | None:
    pattern = re.compile("|".join(map(re.escape, NICKNAMES)))
    hits = _hits(pattern, texts)
    if not hits:
        return None
    return ("字幕里把昵称音译成了一个新名字：" + "、".join(
        f"{h}→{NICKNAMES[h]}" for h in hits) + "——一律走仓库译名表（账号所有者 2026-09-06）。")


# ═══════════════════════════════════════════════════════════════════ 接入口 ══

def spec_taste_extra(spec: dict) -> tuple[list[str], list[str]]:
    """`validate_spec` 只接这一刀：返回 `(硬的, 只报的)`。自动 spec 的硬项降成只报。

    ⚠️ 「前瞻事实写了要等 X，渲之前回头查 X」**不在这里**：它的闸是
    `reel_facts.waiting_fact_problem`（认领 `_rechecked_at`；渲染入口另拿发布账本比
    `waiting_fact_stale_problem`），`validate_spec` 经 `time_sensitive_gate` 调它。这里
    曾经另写过一份（`_pending_resolved`），两道闸互相不认对方的认领字段——只写一种
    就被另一道拦（`test_前瞻事实只有一道闸_认领字段是_rechecked_at`）。
    """
    hard: list[str] = []
    soft: list[str] = []
    for check in (total_margin_problem, one_of_n_problem, cover_fit_problem,
                  solo_layout_problem, ending_problem, push_summary_problem,
                  winners_ue_problem, tennistv_trim_problem, quote_kind_problem):
        if problem := check(spec):
            hard.append(problem)
    if note := peng_shuai_note(_outward(spec)):
        soft.append(note)                     # 转述来的规则：只报，永不做成闸（见 peng_shuai_note）
    cover, push = spec.get("cover") or {}, spec.get("push") or {}
    numerals = None if already_published(_slug(spec), reel_ledger_dir()) else \
        screen_numerals_note([("钩子", cover.get("hook")), ("副标题", cover.get("topic")),
                              ("推送标题", push.get("summary"))])
    for note in (hook_identity_note(spec), social_first_note(spec), numerals,
                 nickname_note(sum((_quote_texts(s) for s in spec.get("segments") or []
                                    if isinstance(s, dict)), []))):
        if note:
            soft.append(note)
    if _auto(spec):
        return [], hard + soft
    return hard, soft


def xhs_taste_extra(spec: dict, xhs_text: str | None) -> tuple[list[str], list[str]]:
    """小红书正文那一面（`enforce_spec_wording` 那个座位，它才拿得到 `.xhs.txt`）。"""
    if not xhs_text:
        return [], []
    hard = [p for p in (xhs_markdown_problem(xhs_text),
                        one_of_n_problem({"slug": _slug(spec),
                                          "_one_of_n_why": spec.get("_one_of_n_why")},
                                         xhs_text)) if p]
    soft = [n for n in (peng_shuai_note([xhs_text]),) if n]
    return ([], hard + soft) if _auto(spec) else (hard, soft)


def interview_taste_extra(spec: dict, xhs_text: str | None = None
                          ) -> tuple[list[str], list[str]]:
    """赛后开麦：钩子是 `cover.title`（两行列表），推送标题同名。"""
    cover, push = spec.get("cover") or {}, spec.get("push") or {}
    title = cover.get("title")
    title = "".join(title) if isinstance(title, list) else str(title or "")
    shadow = {"slug": _slug(spec), "cover": {"hook": title, "eyebrow": "赛后开麦"},
              "push": {"summary": push.get("summary")}}
    # 我们写的文案：标题、推送、解读卡。「赛点只兑现了一个」管的是这些（账号所有者
    # 08-19 说的是我们的文案）——`zh` 是当事人自己的话的译文，照实翻，不许因为球员说了
    # 「三个盘点只拿下一个」就把片子拦在渲染入口、把自动草稿挡在转正外。
    ours = [title] + [str(v) for k, v in push.items()
                      if not str(k).startswith("_") and isinstance(v, str)]
    ours += [str((spec.get("takeaway") or {}).get(k) or "") for k in ("point", "narration")]
    texts = ours + [str(z) for z in spec.get("zh") or []]
    one_of_n = None
    if (_slug(spec) not in ONE_OF_N_LEGACY and not _one_of_n_claimed(spec)
            and (hits := _hits(ONE_OF_N, ours))):
        one_of_n = (f"写了「N 个赛点／盘点只兑现了一个」：{hits}——赢家永远只兑现最后一个，"
                    "要写就写对手救下了几个（账号所有者 2026-08-19）。")
    hard = [p for p in (total_margin_problem(shadow), one_of_n,
                        xhs_markdown_problem(xhs_text)) if p]
    soft = [n for n in (peng_shuai_note(texts + ([xhs_text] if xhs_text else [])),
                        None if already_published(_slug(spec), interview_ledger_dir()) else
                        screen_numerals_note([("标题", title), ("推送标题", push.get("summary"))]),
                        nickname_note([str(z) for z in spec.get("zh") or []])) if n]
    return hard, soft
