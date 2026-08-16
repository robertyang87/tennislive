"""TNNS 单场统计载荷的解码判据。

⚠️⚠️ **上一版这段写着「fixture 是真数据，不是手搓的」——那句话是错的，
而它正是这次翻车的原因。** 那份 `_REAL` 是我照着 `--print-body` 的片段
**手工拼的，拼的时候少套了一层**：`_` 里 `"0"`（=`data`）底下还有一个
`"0"`（=`data`），分盘挂在**内层**，`hasExtendedStats` 挂在**外层**。

少那一层的后果不是「解不出来」，是**自相矛盾**：`hasExtendedStats` 读得到、
分盘读不到，于是工具一边说「这场有扩展统计」一边说「没有制胜分」，
还打算把后半句写进 spec 当判据（2026-08-16 run 31956957338 真发生了）。

现在这份是 run 31957762816 打出来的**整份 10186 字节原文**逐字节抄的
（`[body 0]`~`[body 9000]`），层级一层不差。

CLAUDE.md：**手搓的 fixture 只能验函数的局部行为，验不了它和真页面对不对
得上**——而这次更坏：注释里那句「真数据」让下一个人（我自己）根本不会去核。
所以核心断言不是「函数能从 dict 里抠字」，而是

    分盘三块的制胜分/非受迫失误加起来，必须等于 app 上显示的全场数字

——解错任何一个 base36 下标都不可能同时对上四个数。⚠️ **但它也拦不住少一层**
（少一层是整块取不到，四个数根本没机会相加），所以另有一条专钉层级的。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("tools").resolve()))

import tnns_stats  # noqa: E402


# ⚠️⚠️ **下面这份是 2026-08-16 `--print-body` 打出来的原文，逐字节抄的，
# 不是手拼的。** 上一版（#398）的注释也写着「真数据」，而它是我照着 body 片段
# **手工拼的、少套了一层**——`_` 里 `"0"`（=`data`）底下还有一个 `"0"`（=`data`），
# 分盘挂在**内层**，`hasExtendedStats` 挂在**外层**。少那一层的后果不是解不出来，
# 是**自相矛盾**：`hasExtendedStats` 读得到、分盘读不到，工具于是一边说「这场有
# 扩展统计」一边说「没有制胜分」，还差点把那句话写进 spec 当判据。
#
# CLAUDE.md：**手搓的 fixture 只能验函数的局部行为，验不了它和真页面对不对得上**
# ——而这次更坏，注释里那句「真数据」让下一个人（我自己）根本不会去核。
_K = ["data", "Match", "title", "players", "key", "values", "replace",
      "Set 1", "keys", "missing", "Set 2", "Set 3", "ZVE by court",
      "NOR by court", "hasExtendedStats", "tabs", "id", "period",
      "refresh_time", "success"]

# `P` 只抄到用得着的下标（0~e）；顺序不能动，下标就是语义。
_P = ["Zverev", "Norrie", "service_games_won", "Service Games",
      "92% (12/13)", "79% (11/14)", "return_games_won", "Return Games",
      "21% (3/14)", "8% (1/13)", "Key Stats", "dominance_ratio",
      "Dominance Ratio", "Winners", "Unforced Errors"]


def _key_stats(dr, winners, ue):
    """每一盘的 Key Stats 那一组，原文照抄（`"2"`=title `"4"`=key `"5"`=values）。"""
    return [{"0": [{"2": "p:c", "4": "p:b", "5": dr},
                   {"2": "p:d", "5": winners},
                   {"2": "p:e", "5": ue}],
             "2": "p:a", "3": ["p:0", "p:1"]}]


# ⚠️ **两层 `"0"`**：外层是 `data`，内层还是 `data`。原文就是
# `"_":{"0":{"0":{"1":[…],"7":[…],"a":[…],"b":[…]},"e":true,…},"j":true}`
_REAL = json.dumps({
    "K": _K,
    "P": _P,
    "_": {
        "0": {                                  # data
            "0": {                              # data.data ← 分盘在这一层
                "1": _key_stats(["1.47", "0.68"], [41, 25], [35, 36]),   # Match
                "7": _key_stats(["0.86", "1.16"], [11, 7], [17, 10]),    # Set 1
                "a": _key_stats(["4.77", "0.21"], [13, 8], [5, 9]),      # Set 2
                "b": _key_stats(["1.31", "0.77"], [17, 10], [13, 17]),   # Set 3
            },
            "e": True,                          # data.hasExtendedStats ← 外层
        },
        "j": True,                              # success
    },
}, ensure_ascii=False, separators=(",", ":"))


def test_键走K表值走P表两张表不许混用():
    """解码的核心：对象的键是 `K` 的裸 base36 下标，值里 `p:` 才查 `P`。

    混用会解出一堆看着像模像样、实则张冠李戴的字段，而那种错**不报错**。
    """
    got = tnns_stats.decode(_REAL)
    assert set(got) == {"data", "success"}, f"顶层没解对：{sorted(got)}"
    # ⚠️ 分盘在 `data.data`，不是 `data`——外层还挂着 hasExtendedStats / tabs
    outer = got["data"]
    assert "hasExtendedStats" in outer, sorted(outer)
    data = outer["data"]
    assert "Match" in data and "Set 1" in data and "Set 3" in data, sorted(data)
    row = data["Set 1"][0]["data"][1]
    assert row["title"] == "Winners", row          # p:d → P[13]
    assert row["values"] == [11, 7], row
    # 分组自己的标题也走同一张池
    assert data["Set 1"][0]["title"] == "Key Stats"
    assert data["Set 1"][0]["players"] == ["Zverev", "Norrie"]


def test_分盘加起来必须等于全场():
    """**这条才是「解对了」的判据**，不是上面那条。

    2026-08-16 就是靠它确认下标读法没错：三盘的制胜分 11+13+17=41、7+8+10=25，
    非受迫失误 17+5+13=35、10+9+17=36，四个数同时和 app 上那一屏对上。
    """
    got = tnns_stats.decode(_REAL)
    whole = tnns_stats.winners_ue(got, "Match")
    assert whole == {"winners": [41, 25], "ue": [35, 36]}, whole
    for field, expect in (("winners", [41, 25]), ("ue", [35, 36])):
        total = [0, 0]
        for period in ("Set 1", "Set 2", "Set 3"):
            part = tnns_stats.winners_ue(got, period)
            assert part is not None, f"{period} 少了这两行"
            for i in (0, 1):
                total[i] += part[field][i]
        assert total == expect, f"{field} 分盘合计 {total} ≠ 全场 {expect}"


def test_有没有扩展统计读接口自己声明的那个键():
    """`hasExtendedStats` 比「从缺字段反推」可靠——「这场没有」和「我解错了」
    在产物上长得一模一样，所以要读它自己说的那句。

    ⚠️ 拿不到这个键要返回 `None` 而不是 `False`：默认成 False 就把
    「没查到」说成了「没有」。
    """
    assert tnns_stats.has_extended_stats(tnns_stats.decode(_REAL)) is True
    empty = json.dumps({"K": _K, "P": _P, "_": {"0": {}}})
    assert tnns_stats.has_extended_stats(tnns_stats.decode(empty)) is None


def test_不是这个形状要抛不许静默当成没数据():
    """接口换了形状和「这场没有统计」长得一样——必须抛，不能返回空。"""
    import pytest
    with pytest.raises(ValueError) as err:
        tnns_stats.decode(json.dumps({"matches": []}))
    assert "别当成" in str(err.value)


def test_池下标越界原样留着不许变成None():
    """越界静默变 None，下游会把它当成「这一项没有」——又一次「不吭声」。"""
    assert tnns_stats._from_pool("p:zzz", ["a"]) == "p:zzz"
    assert tnns_stats._from_pool("p:0", ["a"]) == "a"
    # 池里本来就有 "92% (12/13)" 这种值，裸串不许被当成下标
    assert tnns_stats._from_pool("1a", ["a", "b"]) == "1a"


def test_flashscore缺这两项时要把TNNS这条路指出来():
    """⚠️ **这条判据的来路是一句错话。**

    2026-08-16 账号所有者问「怎么 ATP 的统计卡片里没有制胜分和 UE 了」，
    `match_stat_hooks --stats-block` 那行原来写的是「这场接口里没有」，我照抄
    答了「这两场没有」——而 TNNS Live 上那两行就在。**flashscore 没有 ≠ 没有。**

    所以这行现在必须①把范围收在 flashscore 上、②指出 TNNS 这条路。
    """
    body = Path("tools/match_stat_hooks.py").read_text("utf-8")
    # ⚠️ 锚在**打印那一处**，不是 `_has_winners_ue` 第一次出现的地方——
    # 它先在 `stats_block` 里被赋值，按第一次出现取会切到那儿，
    # 于是这条判据变成一盏恒红的灯（第一版就是这么写的）。
    i = body.index('blk["_has_winners_ue"]')
    seg = body[i - 200: i + 1400]
    assert "flashscore 这场没有" in seg, "范围没收住——「这场没有」是错话"
    assert "tnns-stats" in seg or "tnns_stats" in seg, "没把 TNNS 这条路指出来"


def test_date这个参数要真的进到请求里():
    """⚠️ **它第一版是个收下来就扔掉的参数。**

    `fetch()` 只在**报错文案**里用过 `date` 一次，而那句话还写着「跨日的比赛
    要给 --date」——于是给了 `--date` 照样查空，报错还指着你再给一次。首页只
    给今天，所以昨天的比赛结构性地一定找不到。

    这个仓库为同一个形状栽过好几回（WTA 的 `?extended=true` 被静默忽略、
    tennisexplorer 的 `?date=` 回显了参数却返回同一张表），判据一律是
    **换个值内容变不变**，不是「参数被接受了」。这里钉的是它前面那一步：
    那个值到底有没有被拼进请求 URL。
    """
    # ⚠️ 收**每一次**调用，不是最后一次：`fetch` 会调两趟（先赛程、后统计），
    # 第二趟的 `in_page` 是 None，只记最后一次就会把第一趟的证据盖掉——
    # 而那看起来正好像「参数被扔了」。
    calls = []

    def fake_capture(urls, marks, wait=22, in_page=None):
        calls.append(in_page)
        return {tnns_stats._DAY_MARK: json.dumps(
            {"all_matches": [{"k": 42, "p": [{"n": "Zhang"}, {"n": "Day"}]}]})}

    real = tnns_stats._browser_capture
    tnns_stats._browser_capture = fake_capture
    try:
        try:
            tnns_stats.fetch(["Zhang", "Day"], date="2026-08-15")
        except SystemExit:
            pass                      # 第二跳（统计）在这条测试里走不到，无所谓
    finally:
        tnns_stats._browser_capture = real

    dated = [c for c in calls if c]
    assert dated, "给了 --date 却没有任何一条按日期发的请求——参数被扔了"
    url = dated[0][tnns_stats._DAY_MARK]
    assert "date=2026-08-15" in url, f"日期没拼进请求：{url}"
    # 换个值必须换出另一个 URL——不然「拼进去了」也只是看起来拼进去了
    calls.clear()
    tnns_stats._browser_capture = fake_capture
    try:
        try:
            tnns_stats.fetch(["Zhang", "Day"], date="2026-08-14")
        except SystemExit:
            pass
    finally:
        tnns_stats._browser_capture = real
    again = [c for c in calls if c]
    assert again and "date=2026-08-14" in again[0][tnns_stats._DAY_MARK], \
        f"换了日期请求没跟着变：{again}"


def test_取TNNS要单独一条工作流不许接进出片流程():
    """一次开浏览器 25~30 秒且不可缓存（挑战每次重过）。

    ⚠️ 判据钉两头：**入口够得着**（有这条工作流、能手动跑），
    **而且没混进 match-reel**——接进去就是每条片子白背半分钟。
    """
    wf = Path(".github/workflows/tnns-stats.yml")
    assert wf.is_file(), "工作流不在——工具写了却没有入口，等于没有"
    text = wf.read_text("utf-8")
    assert "workflow_dispatch" in text, "手动入口没了"
    assert "tools/tnns_stats.py fetch" in text, "没真的调那条命令"
    # 出片那条线不许出现它
    reel = Path(".github/workflows/match-reel.yml").read_text("utf-8")
    lines = [ln for ln in reel.splitlines() if not ln.strip().startswith("#")]
    assert "tnns_stats" not in "\n".join(lines), \
        "TNNS 混进 match-reel 了——每条片子会白背一次浏览器启动"


def test_撞名要停不许静默取第一条():
    """姓是子串匹配，而同一天很容易有两个张、两个 Wang。

    ⚠️ 取第一条会安安静静给出**另一场**的制胜分/非受迫失误——数字合法、图画得
    出来、分盘自证也过（那本来就是另一场自洽的数据）。CLAUDE.md 里「按 slug
    认领会静默认错人」是同一个形状：**认领的钥匙不唯一时，唯一安全的动作是
    报出来让人挑。**
    """
    import pytest
    day = json.dumps({"all_matches": [
        {"k": 1, "p": [{"n": "Shuai Zhang"}, {"n": "Kayla Day"}]},
        {"k": 2, "p": [{"n": "Zhang Zhizhen"}, {"n": "Holger Dayne"}]},
    ]})
    with pytest.raises(SystemExit) as err:
        tnns_stats.find_match_id(day, ["Zhang", "Day"])
    msg = str(err.value)
    assert "id=1" in msg and "id=2" in msg, f"没把候选列出来让人挑：{msg}"
    # 唯一命中照旧要正常返回，别把闸设成「永远不许有结果」
    one = json.dumps({"all_matches": [
        {"k": 7, "p": [{"n": "Shuai Zhang"}, {"n": "Kayla Day"}]},
        {"k": 8, "p": [{"n": "Coco Gauff"}, {"n": "Iga Swiatek"}]},
    ]})
    assert tnns_stats.find_match_id(one, ["Zhang", "Day"]) == "7"
    assert tnns_stats.find_match_id(one, ["Nobody"]) is None


def test_声称有却抠不出来要报矛盾不许写成这场没有():
    """⚠️ **这条判据的来路是我的工具说了一句自信的假话。**

    2026-08-16 端到端第一趟（run 31956957338，兹维列夫那场）：接口自己说
    `hasExtendedStats: True`，而抓回来的那份里抠不出 Key Stats 那几组——
    **同一场我手里有原文，41/25、35/36 明明在**。也就是说抓到的不是完整那
    一份，不是这场没有。

    而第一版在这儿照样打印了一句能粘的 `_winners_ue_why`，内容是「TNNS 这场
    也没有这两行」，还打算被抄进 spec 当判据。**那比抓不到坏得多**：抓不到只是
    没帮上忙，这是主动给出一个错答案，而下一个人没有第二个地方可以对
    （CLAUDE.md 里「喊错了是主动给出错答案」那条）。

    ⚠️ 两头都要钉：矛盾要报错，而**真的没有**（接口自己说 False/None）
    照旧要给出能粘的挂账句——只钉前一头的话，把整条路改成一律报错也能过，
    而那会把「查过确实没有」这种正当情形也堵死。
    """
    import pytest

    def _payload(ext):
        k = ["data", "Match", "hasExtendedStats"]
        return json.dumps({"K": k, "P": [], "_": {"0": {"1": [], "2": ext}}})

    # ① 声称有、抠不出来 → 必须报矛盾，且**不许**吐出 `_winners_ue_why`
    with pytest.raises(SystemExit) as err:
        tnns_stats._report("73465930", tnns_stats.decode(_payload(True)))
    msg = str(err.value)
    assert "自相矛盾" in msg, msg
    # ⚠️ 只认**能粘的那一行**（`"_winners_ue_why": "`），不认散文里提到这个
    # 字段名——报错正文里那句「别把它写成 `_winners_ue_why`」是**在教人别写**，
    # 按裸名字扫会把它判成「还在教人写」。判据宁可窄，不可宽，而这个仓库为
    # 「被自己的说明文字误伤」栽过好几次。
    assert '"_winners_ue_why":' not in msg, "还在吐能粘的假话"

    # ② 接口自己说没有 → 照旧给能粘的挂账句，别报错
    for ext in (False, None):
        body = _payload(ext) if ext is not None else json.dumps(
            {"K": ["data", "Match"], "P": [], "_": {"0": {"1": []}}})
        tnns_stats._report("42", tnns_stats.decode(body))   # 不许抛


def test_按日期取不到要红不许退回首页那份():
    """⚠️ **首页给的是今天，拿它顶替会静静地在错的一天里找人。**

    2026-08-16 run 31956961716 实况：按 `date=2026-08-15` 那一发
    `Failed to fetch`，而首页的被动抓包**早把同一个键填成了今天的赛程**，
    于是日志照打「按 date=2026-08-15 取到 149 场」——**参数没生效，而它宣称
    生效了**，然后在今天的赛程里找昨天的人，找不到。

    ⚠️ 而「找不到」和「TNNS 没有这场」长得一模一样——这正是这一整条线反复要
    防的那个形状。所以取不到必须红。

    ⚠️ 这条是 `test_date这个参数要真的进到请求里` **拦不住**的那一半：
    那条只钉「URL 拼对了」，把退回首页那一支加回来它照样绿（反向验证过）。
    两条各管一头，缺一个都会漏。
    """
    import pytest

    def cap_dated_fails(urls, marks, wait=22, in_page=None):
        # 被动抓包拿到了首页（今天）那份，按日期那一发失败——真实事故的形状
        return {tnns_stats._DAY_MARK: json.dumps(
            {"all_matches": [{"k": 1, "p": [{"n": "Someone Else"}]}]})}

    real = tnns_stats._browser_capture
    tnns_stats._browser_capture = cap_dated_fails
    try:
        with pytest.raises(SystemExit) as err:
            tnns_stats.fetch(["Zhang", "Day"], date="2026-08-15")
    finally:
        tnns_stats._browser_capture = real
    msg = str(err.value)
    assert "不退回首页那份" in msg, f"退回了首页那份，或者没说清为什么不退：{msg}"


def test_分盘挂在内层的data少套一层要读不到():
    """⚠️ **专钉层级，因为「分盘加起来等于全场」那条拦不住少一层。**

    少一层的时候整块 `Match` 根本取不到，四个数没机会相加，那条测试只会
    看到一个 `None`——而如果 fixture 自己也少套了一层（上一版就是），
    它反而是绿的。**判据和 fixture 同时错，就什么都拦不住了。**

    真实层级（run 31957762816 原文）：

        _ → "0"(data) → "0"(data) → "1"(Match) / "7"(Set 1) / …
                      → "e"(hasExtendedStats)      ← 和分盘是**兄弟**，不是祖先

    正是这个不对称造出了那次「自相矛盾」：外层那个读得到，内层那些读不到。
    """
    got = tnns_stats.decode(_REAL)
    # 两个键在不同层——这就是层级本身
    assert "hasExtendedStats" in got["data"], "外层没有 hasExtendedStats"
    assert "Match" in got["data"]["data"], "内层没有分盘"
    assert "Match" not in got["data"], (
        "分盘跑到外层去了——fixture 或解码器少套了一层，"
        "而少一层的样子是「hasExtendedStats 读得到、分盘读不到」的自相矛盾")
    # 而且 `winners_ue` 必须走内层那条路
    assert tnns_stats.winners_ue(got, "Match") == {"winners": [41, 25],
                                                   "ue": [35, 36]}


def test_列顺序要读得出来不许是None():
    """⚠️ **列顺序决定 `stats.a/b` 填给谁，读不出来比读错更容易被放过。**

    2026-08-16 端到端跑通那一趟，数字全对、自证 ✅，唯独这行打着
    `（选手顺序 None）`——`winners_ue` 改对了层级，而 `_report` 里另写了一遍
    `data.get("Match")`，**「一个数写两处必分叉」**。分叉的样子不是报错，
    是列顺序悄悄变成 None，而下一个人照着填就可能填反。

    ⚠️ 账号所有者当天的截图正好点了这件事：那一场列头是
    **Townsend 在前、Rybakina 在后**，和上面比分行的顺序**相反**——
    所以列顺序必须从 `players` 读，不能从比分行推。
    """
    got = tnns_stats.decode(_REAL)
    assert tnns_stats.players_of(got) == ["Zverev", "Norrie"]
    assert tnns_stats.players_of(got, "Set 1") == ["Zverev", "Norrie"]
    # 源码里不许再出现旧层级那种写法。
    # ⚠️ **要连 docstring 一起剥掉，不只是 `#` 行**——`players_of` 的 docstring
    # 里正写着「而这儿另写了一遍 `data.get("Match")`」，那是**在记教训**，
    # 只剥 `#` 会把它判成「又踩了这个坑」。这个仓库为「被自己的说明文字误伤」
    # 栽过五六次，今天这是第三次。
    # ⚠️ 别用 `ast.get_docstring()` 去 replace：它回的是**去过缩进**的那一份，
    # 和源码原文对不上，一个字都删不掉**而且不报错**（CLAUDE.md 明写）。
    import re
    body = Path("tools/tnns_stats.py").read_text("utf-8")
    code = re.sub(r'"""[\s\S]*?"""', "", body)
    code = "\n".join(l for l in code.splitlines()
                     if not l.lstrip().startswith("#"))
    assert 'data.get("Match")' not in code, (
        "又在 `data` 那一层取分盘了——分盘在 `data.data`，"
        "少一层的样子是「hasExtendedStats 读得到、分盘读不到」的自相矛盾")
