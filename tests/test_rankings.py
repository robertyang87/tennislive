"""排名源和缩写匹配（2026-08-25 重写）。

来路：ESPN 那条 `site.api.espn.com/.../rankings` **runner 和沙箱都 403**，
于是每个球员的 `rank` 都是 `None`——而 `match_score()` 的热度分档、爆冷判定
全靠它，自动选题一直在没有排名这一维的情况下打分。

⚠️ **而换源只修了一半。** 当天量的：一份真实 digest 里 348 名球员，**251 名
（72%）的名字是 flashscore 的 `Gauff C.` 形状**，ATP 那半边更是 127/128 全是
缩写。只查全名的话，换了能用的源之后 ATP 的 rank 照样全是 None，**而它看起来
完全像修好了**。两件事必须一起做，判据也一起钉。
"""

from __future__ import annotations

from conftest import make_match
from tennislive.sources.rankings import (RankEntry, _te_split, abbrev_key,
                                         norm_name, rank_map)


def _e(rank, name, surname, given):
    return RankEntry(rank=rank, name=name, surname=surname, given=given)


def test_缩写形状的名字要认得出来():
    assert abbrev_key("Gauff C.") == "gauff c"
    # ⚠️ 缩写不一定只有一个字母：同姓要区分时 flashscore 写三个字母
    assert abbrev_key("Wang Xin.") == "wang xin"
    assert abbrev_key("Wang Xiy.") == "wang xiy"
    # 多段姓 / 连字符姓 / 两个名的缩写
    assert abbrev_key("De Minaur A.") == "de minaur a"
    assert abbrev_key("Auger-Aliassime F.") == "auger aliassime f"
    assert abbrev_key("Cerundolo J. M.") == "cerundolo j m"
    assert abbrev_key("Liang E. S.") == "liang e s"
    # 全名不是缩写形状——那条走 norm_name，别让它也进缩写表
    assert abbrev_key("Coco Gauff") is None
    assert abbrev_key("Hong Yi Cody Wong") is None


def test_榜单要同时认全名和各档缩写():
    table = rank_map([_e(4, "Coco Gauff", "Gauff", "Coco"),
                      _e(7, "Alex De Minaur", "De Minaur", "Alex"),
                      _e(51, "Juan Manuel Cerundolo", "Cerundolo", "Juan Manuel")])
    assert table[norm_name("Coco Gauff")] == 4
    assert table[abbrev_key("Gauff C.")] == 4
    assert table[abbrev_key("De Minaur A.")] == 7
    # 两段名要按「每个名取首字母」认得出来
    assert table[abbrev_key("Cerundolo J. M.")] == 51


def test_撞名的键必须留空不许静静挑一个():
    """⚠️ `Wang X.` 可能是王欣瑜也可能是王曦雨。

    `setdefault` 会挑排名靠前的那个，而**把排名安到错的人头上，在产物上和
    安对了长得一模一样**——CLAUDE.md 里「同一站两个中国选手都姓 Wang」栽过
    这个坑。留空至少是诚实的。
    """
    table = rank_map([_e(41, "Xinyu Wang", "Wang", "Xinyu"),
                      _e(82, "Xiyu Wang", "Wang", "Xiyu")])
    assert table.get("wang x") is None, "撞键还给了答案——那是在猜"
    # 而给够字母能分开的，两个都要查得到
    assert table[abbrev_key("Wang Xin.")] == 41
    assert table[abbrev_key("Wang Xiy.")] == 82


def test_tennisexplorer的姓从slug推并且要自证():
    """文本是「姓… 名」，**按「最后一个词是名」会在两段名上切错**：
    `Cerundolo Juan Manuel` 会被切成姓「Cerundolo Juan」。所以姓从 URL slug
    推，再拿「文本以它开头」自证——150 条抽样里 149 条中。
    """
    assert _te_split("cerundolo", "Cerundolo Juan Manuel") == ("cerundolo", "juan manuel")
    assert _te_split("auger-aliassime", "Auger Aliassime Felix") == ("auger aliassime", "felix")
    # slug 尾巴那 5 位十六进制是站内哈希，不是姓的一部分
    assert _te_split("sinner-8b8e8", "Sinner Jannik") == ("sinner", "jannik")
    # 连字符两边都要归一，否则「Carreno-Busta」自证不过
    assert _te_split("carreno-busta", "Carreno-Busta Pablo") == ("carreno busta", "pablo")
    # 自证不过就退回「最后一个词是名」，别整条丢掉
    assert _te_split("totally-wrong", "Sinner Jannik") == ("sinner", "jannik")


def test_不许再指回已经全线403的ESPN排名接口():
    """⚠️ 用 AST 扫，不按文本扫——模块 docstring 里正写着那个 host，
    那是记教训的地方，按文本扫会把「把坑记下来」判成「又接回去了」。"""
    import ast  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    src = Path("src/tennislive/sources/rankings.py").read_text("utf-8")
    tree = ast.parse(src)
    # ⚠️ docstring 要按**节点身份**排除，不能拿 `ast.get_docstring()` 的文本去比
    # ——它回的是去过缩进的那一份，和源码里那个 Constant 的值对不上
    # （CLAUDE.md「别用 get_docstring 去 replace」记的是同一个坑）。
    doc_nodes = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            doc_nodes.add(id(body[0].value))
    live = [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in doc_nodes]
    assert not any("site.api.espn.com" in s for s in live), \
        "又指回 ESPN 了——那个接口 runner 和沙箱都 403，接回去等于全员 rank=None"
    assert any("api.wtatennis.com" in s for s in live), "WTA 官方那条源没了"
    assert any("tennisexplorer.com" in s for s in live), "ATP 那条源没了"


def test_补排名要同时试全名和缩写否则ATP那半边全是None():
    """⚠️ 「写了不等于跑过」：`rank_map` 认得出缩写，而 `apply_rankings` 只查
    全名的话，那张表里的缩写键一个都用不上——**ATP 那半边 127/128 是缩写**。"""
    from tennislive.digest import apply_rankings  # noqa: PLC0415
    from tennislive.sources.rankings import Rankings  # noqa: PLC0415

    m = make_match(home_name="Sinner J.", away_name="Alcaraz C.")
    apply_rankings(Rankings(atp=[_e(1, "Jannik Sinner", "Sinner", "Jannik"),
                                 _e(3, "Carlos Alcaraz", "Alcaraz", "Carlos")]), [m])
    assert m.home[0].rank == 1 and m.away[0].rank == 3, \
        "缩写名没补上排名——只查全名的话 ATP 那半边等于没修"
