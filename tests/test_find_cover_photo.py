"""AP 通讯社这条封面渠道的判据。

**为什么加这条渠道**：账号所有者 2026-08-17「多找几个渠道，**不然下一个赛事
就不一定有了啊**」。去量了一遍，他说的不是隐忧是现状——分辨率最高的那两条
**都跨不过赛事**：

    赛事官网 WP 媒体库（5541px）   扫了 11 个赛事官网，**只有辛辛那提一个**开着
    当地报纸每日图集（4813px）     得先知道当地哪份报纸（六份里五份形状对得上）

**而 AP 是通讯社，每站都派人**，说明还自带四要素 ＋ 署名。实测原图
**8212×5576 / 6226×4796**，铺 1080×1440 是 3~4×。

这里钉两条，两条都是当天量出来才知道方向的：

| 判据 | 我差点写成的那一版 |
|---|---|
| 原图在 `?url=` 上，不是 `dims.` 那个地址 | 直接用 dims 那个——**它是按版面缩好的 980×653** |
| 说明里**赛事**也要对上，不只是人 | 只按人筛——拿回来三张全是她，**没有一张是这一场** |
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import find_cover_photo as fc  # noqa: E402


def test_AP的原图在url参数上不是dims那个地址():
    """⚠️ **`dims.apnews.com` 是个动态缩放器，给的是版面尺寸。**

    实测同一张图两个地址：

        dims…/resize/980x653!/…?url=<原图>   → 980 宽，铺封面 0.91×，**不够**
        assets.apnews.com/<原图>             → **8640×5760**，铺封面 3.87×

    照 `dims` 那个用，等于把一张 8600px 的原图当成 980px 在使——而它**不报错**，
    只是封面糊，正是这条渠道存在的理由的反面。
    """
    dims = ("https://dims.apnews.com/dims4/default/941103e/2147483647/strip/true"
            "/crop/4000x2667+0+0/resize/980x653!/quality/90/"
            "?url=https%3A%2F%2Fassets.apnews.com%2Fa7%2F45%2F7023dc1f%2Fe5baa27a")
    assert fc.ap_original(dims) == "https://assets.apnews.com/a7/45/7023dc1f/e5baa27a"

    # `&amp;` 是从 HTML 里扒出来的常态，不还原就把 url 参数切没了
    amp = dims.replace("?url=", "?w=1&amp;url=")
    assert fc.ap_original(amp) is not None, "HTML 实体没还原，url 参数丢了"

    # 没有 url 参数的（版面装饰图）要返回 None，不许硬拼一个地址出来
    assert fc.ap_original("https://dims.apnews.com/dims4/default/x/resize/60x60!/") is None


def _fake_page(pairs: list[tuple[str, str]]) -> str:
    return "".join(
        f'<img src="https://dims.apnews.com/dims4/default/x/resize/980x653!/'
        f'?url=https%3A%2F%2Fassets.apnews.com%2F{key}" alt="{cap}">'
        for key, cap in pairs
    )


def test_AP按人筛还不够赛事也要对上(monkeypatch):
    """⚠️⚠️ **只按球员名筛会拿回一堆资料图，而它们和本场图长得一模一样。**

    实测 `--player Svitolina` 不筛赛事时，头三张分别是意大利公开赛的捧杯、
    多伦多半决赛（两张，还是斯瓦泰克赢的那场）——**每一张都是她，
    每一张都不是这一场**。这跟 Getty 那条「看见就先查说明」是同一个坑，
    只不过 AP 把说明直接给了，所以这一刀机器切得动。

    加上 `--event Cincinnati` 之后那三张全被挡掉（实测 0 张）；
    同一份代码 `--player Shelton --event Montreal` 拿回 2 张，都真是蒙特利尔。
    """
    page = _fake_page([
        ("aa", "Elina Svitolina of Ukraine serves during a match at the "
               "Cincinnati Open on Sunday, Aug. 16, 2026. (AP Photo/X)"),
        ("bb", "Iga Swiatek celebrates her win over Elina Svitolina in a "
               "National Bank Open semifinal in Toronto. (AP Photo/Y)"),
        ("cc", "Ben Shelton hoists the trophy at the National Bank Open in "
               "Montreal on Thursday, Aug. 13, 2026. (AP Photo/Z)"),
    ])
    # ⚠️ `_get` 要**按 URL 分派**：搜索页/hub 回的是文章链接，文章页回的才是图。
    # 第一版两种都回同一份，于是一条文章链接都抓不到——**空结果，而且看起来
    # 像「筛太狠了」**。又一次「空结果先自证是真空」，只不过这次真空是 fixture 造的。
    index = '<a href="https://apnews.com/article/cincinnati-open-tennis-abc123">x</a>'
    monkeypatch.setattr(
        fc, "_get",
        lambda url, timeout=30: page if "/article/" in url else index)

    both = fc.sweep_ap("Svitolina", "Cincinnati")
    assert len(both) == 1, [r["caption"][:60] for r in both]
    assert "Cincinnati Open" in both[0]["caption"]

    # 只按人筛：多伦多那张也会进来——这一条就是上面那句话的判据
    only_player = fc.sweep_ap("Svitolina", None)
    assert len(only_player) == 2, [r["caption"][:60] for r in only_player]
    assert any("Toronto" in r["caption"] for r in only_player), (
        "少了那张资料图，这条判据就证明不了「按人筛不够」")

    # 谢尔顿那张一次都不该混进斯维托丽娜的结果里
    assert not any("Shelton" in r["caption"] for r in both + only_player)


def test_AP的赛事名要整个比不能只比第一个词(monkeypatch):
    """⚠️⚠️ **这道闸一度只比赛事名的第一个词，于是它对「US Open」整个失效**——
    `"US Open".split()[0]` 是 `us`，而「United States」「Australian」「because」
    里都有它。2026-08-25 实测 `--event "US Open"`：AP 那一档拿回来六张，
    温网、马德里、法网各有，**一张美网都没有**，而它和「这一档没图」在输出里
    长得一模一样（CLAUDE.md「非空 ≠ 对题」）。

    ⚠️ 另一头：AP 有时写「U.S. Open」，所以两边都要抹掉非字母数字再比——
    只做前一半的话，真到了美网又会一张都筛不出来，变成反方向的静默失效。

    ⚠️ 顺带记下当天量到的事实（免得下次把这个零读成 bug）：**AP 的美网前瞻稿
    配的全是别站的资料图**（温网、蒙特利尔、印第安维尔斯），所以正赛开打之前
    这一档对美网**本来就该是零**——那是一个真的空，不是筛狠了。
    """
    page = _fake_page([
        ("aa", "Aryna Sabalenka returns the ball to Naomi Osaka in their fourth "
               "round match at the Wimbledon Tennis Championships in London. (AP Photo/X)"),
        ("bb", "Aryna Sabalenka poses with the trophy after winning the U.S. Open "
               "women's singles final in New York. (AP Photo/Y)"),
    ])
    index = '<a href="https://apnews.com/article/us-open-tennis-sabalenka-abc123">x</a>'
    monkeypatch.setattr(
        fc, "_get",
        lambda url, timeout=30: page if "/article/" in url else index)

    got = fc.sweep_ap("Sabalenka", "US Open")
    assert len(got) == 1, [r["caption"][:70] for r in got]
    assert "U.S. Open" in got[0]["caption"], "写成「U.S. Open」的那张要认得出"


def test_当地报纸不许再把域名写死在代码里():
    """这一档原来把 `cincinnati.com` 写死，**于是它在别的站上根本不会跑**——
    而跳过的样子和查空一模一样（同一个坑 08-17 在 `--site` 上刚栽过一次）。

    ⚠️ 判据钉的是「域名从参数来」，不是「表里有几个城市」：表会长，
    写死不会自己长回来。
    """
    src = (ROOT / "tools" / "find_cover_photo.py").read_text(encoding="utf-8")
    body = src.split('"""', 2)[2]          # 去掉模块 docstring（来路写在那儿）
    code = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    assert "_GANNETT_SITE" not in code, "又把报纸域名写死成模块常量了"
    assert "cincinnati" in fc._LOCAL_PAPERS, "辛辛那提那条已经出过图，不许丢"
    assert len(fc._LOCAL_PAPERS) >= 2, (
        "只剩一个城市就等于又写死了——这一档的全部意义是换个赛事还能跑")
    import inspect  # noqa: PLC0415
    sig = inspect.signature(fc.sweep_local_paper)
    assert "paper" in sig.parameters, "报纸域名必须是参数，不能从模块常量拿"


def test_图集正则要认得出赛事名那几段():
    """⚠️⚠️ **这条正则一度写死成 `sports/<年>/`，于是美网那一整类图集被漏掉。**

    2026-08-25 查美网时撞上的：Gannett 的图集路径里，赛事名那几段是**可有可无**
    的，实测同时存在三种深度——

        /picture-gallery/sports/2026/08/17/photos-cincinnati-open-round-3/<id>/
        /picture-gallery/sports/tennis/2025/09/07/carlos-alcaraz-…/<id>/
        /picture-gallery/sports/tennis/open/2025/09/06/aryna-sabalenka-…/<id>/

    老正则只认第一种。**而漏掉的样子和「这一天没有图集」一模一样**——按它扫，
    美网决赛那两辑（实测原图 6000×4000）一条都翻不出来，然后就会得出
    「当地报纸这一档对美网没有」这个错结论。

    ⚠️ 另一头也要钉：日期那一段必须还锚着。放成 `.*` 的话
    `/picture-gallery/` 底下任何一条链接都会被收进来，「非空 ≠ 对题」。
    """
    real = [
        "/picture-gallery/sports/2026/08/17/photos-cincinnati-open-round-3/12345678007/",
        "/picture-gallery/sports/tennis/2025/09/07/carlos-alcaraz-2025-us-open/86032600007/",
        "/picture-gallery/sports/tennis/open/2025/09/06/aryna-sabalenka-us-open/86019978007/",
    ]
    for path in real:
        assert fc._GALLERY_RE.findall(f'<a href="{path}">x</a>'), f"扫不到 {path}"

    # 反面：不带日期的栏目页不许被当成图集
    for wrong in ["/picture-gallery/sports/tennis/",
                  "/story/sports/tennis/2025/09/07/carlos-alcaraz/86032600007/"]:
        assert not fc._GALLERY_RE.findall(f'<a href="{wrong}">x</a>'), f"不该扫到 {wrong}"

    # 只许有一个出处——两处各写一遍必分叉（索引页和 sitemap 各扫一次）
    src = (ROOT / "tools" / "find_cover_photo.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert code.count("picture-gallery/sports/(?:") == 1, (
        "图集正则又抄成了两份——索引页和 sitemap 必须共用同一个")


def test_美网也要有一份当地报纸():
    """美网这一站落在 `lohud`（威郡本地报）名下是查不到图的——**USA TODAY 自己
    派摄影师去法拉盛**，2025 决赛周那两辑实测原图 6000×4000 / 6283×4189，
    比 WTA `photo-resources` 那档（4000px）还高一档。

    ⚠️ 判据钉的是「`--event "US Open"` 查得到一份报纸」，不是钉死某个域名：
    查不到的话这一档会**整个不跑**，而它在输出里和「查空」长得一模一样
    （同一个坑在 `--site` 和写死 `cincinnati.com` 上各栽过一次）。
    """
    hit = [dom for city, dom in fc._LOCAL_PAPERS.items() if city in "us open"]
    assert hit, "`--event \"US Open\"` 在 _LOCAL_PAPERS 里查不到报纸，这一档会静默不跑"


def test_报纸那一档筛掉的辑数要报出来(monkeypatch):
    """⚠️ 正则放宽之后，同一天翻到的图集**不止这项运动**：USA TODAY 2025-09-06
    那天两辑里只有一辑是网球，另一辑是棒球（卡尔·里普肯），不筛就拿回 49 张
    不对题的图——「非空 ≠ 对题」。

    但筛掉的必须**报出数来**（CLAUDE.md「打印被丢弃的原因和数量」），否则
    「筛窄了」和「这一天真的只有这些」又分不开。

    ⚠️ 判据**真跑一遍这个函数**，不查源码里有没有那几个字：第一版是查文本的，
    把 `notes` 整个换成 `[]` 它照样绿——「查源码文本的断言只能防有人把它删了，
    防不住它从来没工作过」。
    """
    tennis = "/picture-gallery/sports/tennis/2025/09/06/aryna-sabalenka-us-open/86019978007/"
    ball = "/picture-gallery/sports/mlb/2025/09/06/cal-ripken-2131/85997145007/"

    def fake_get(url, timeout=0):
        if "/sitemap/" in url or "/search/" in url:
            return f'<a href="{tennis}">a</a><a href="{ball}">b</a>'
        who = "Aryna Sabalenka" if "sabalenka" in url else "Cal Ripken"
        return ('<script type=application/ld+json>'
                + json.dumps({"image": [{"url": "https://www.usatoday.com/gcdn/x.jpg",
                                         "caption": f"{who} at it", "copyrightHolder": "USA TODAY"}]})
                + "</script>")

    monkeypatch.setattr(fc, "_get", fake_get)
    got = fc.sweep_local_paper("www.usatoday.com", "US Open", None, "2025-09-06")
    caps = [r["caption"] for r in got["rows"]]
    assert caps and all("Sabalenka" in c for c in caps), f"棒球那辑没筛掉：{caps}"
    assert any("2 辑" in n and "1 辑" in n for n in got["notes"]), (
        f"筛掉一辑却没报出来：{got['notes']}")

    # 原图域名要换过（`www.usatoday.com/gcdn/` 恒 406）
    assert all(r["url"].startswith("https://www.gannett-cdn.com/") for r in got["rows"])


def test_美网球员表取不到要说取不到不许报成查无此人(monkeypatch):
    """⚠️ **`players.json` 间歇 403，而它被吞成了「没有这个人」。**

    2026-09-04 做布云朝克特那条片子时撞上的：`find_cover_photo --player Bu`
    报「players.json 里没有叫 'Bu' 的人——先怀疑查询词」，而手查同一个接口
    `atpy09v` 是第一条命中。真因是这个接口**间歇 403**（实测 6 次里 3 次），
    而 `usopen_player_ids` 是裸的 `except Exception: return []`——

        取数失败  → 空列表 → 「没有叫 X 的人，先怀疑查询词」
        真的没有  → 空列表 → 同一句话

    **两种情况在报告上一个字都不差**，而处置完全相反：前者重跑就好，后者要换
    查询词。照它给的方向去改查询词，改多久都改不出来——这正是 CLAUDE.md
    「空结果先自证是真空」和「兜底出事的时候不吭声」那两条。

    ⚠️ **这里钉两头，缺一头都是恒真的**：只钉「取不到要出声」的话，把「查无此人」
    那一支也改成同一句话照样绿，而那会把一个真的该换查询词的情形也说成取数失败。
    """
    calls = {"n": 0}

    def always_403(url, timeout=30):
        calls["n"] += 1
        raise RuntimeError("403 Client Error: Forbidden")

    monkeypatch.setattr(fc, "_get", always_403)
    monkeypatch.setattr(fc.time, "sleep", lambda *_: None)

    # ① 取数失败：必须抛出专门的异常，不许静静返回空列表
    try:
        fc.usopen_player_ids("Bu", "2026")
    except fc.UsoPlayersUnavailable:
        pass
    else:
        raise AssertionError("players.json 取不到时静静返回了空列表——"
                             "调用方会把它读成「没有这个人」")
    assert calls["n"] == fc._USO_PLAYERS_TRIES, (
        f"间歇 403 要重试，实际只发了 {calls['n']} 次请求")

    # ② 而报告里那句话要说「取不到」，不许说「没有叫 X 的人」
    report = fc.sweep_usopen("Bu", None, "2026")
    said = "\n".join(report.get("notes") or [])
    assert "取不到" in said, f"取数失败没有出声：{said!r}"
    assert "没有叫" not in said, f"取数失败被报成了查无此人：{said!r}"


def test_美网球员表真的没这个人还是要说没这个人(monkeypatch):
    """上一条的另一头：接口通、名字确实不在表里，报告要照旧指向查询词。

    没有这一条的话，把「查无此人」那一支删掉、两种情况都报「取不到」，
    上一条测试照样绿——而那会让一个真的写错了查询词的人去反复重试。
    """
    people = {"players": [{"id": "atpy09v", "first_name": "Yunchaokete",
                           "last_name": "Bu", "country": "CHN"}]}

    def feed(url, timeout=30):
        if "players.json" in url:
            return json.dumps(people)
        return json.dumps({"content": [], "totalRows": 0})

    monkeypatch.setattr(fc, "_get", feed)

    assert fc.usopen_player_ids("Bu", "2026"), "表里有他却没认出来"

    report = fc.sweep_usopen("Nosuchplayer", None, "2026")
    said = "\n".join(report.get("notes") or [])
    assert "没有叫" in said, f"真的查无此人时没有指向查询词：{said!r}"
    assert "取不到" not in said, f"把查无此人报成了取数失败：{said!r}"


def test_美网那几个feed间歇403要自己重试扛过去(monkeypatch):
    """⚠️ **间歇 403 不只在 `players.json` 上**，三个 feed 都会。

    2026-09-04 找吴易昺封面时量到的：`find_cover_photo` 对美网接口的**五次调用
    全部 403**，工具据此报「没有对得上的」；而同一时刻带重试的直连一次拿到完整
    18 条。也就是说前一条修的只是三处里的一处——`tag` 和 `byType/photo`
    那两处照旧把一次限流读成「这一档查空了」。
    """
    hits = {"n": 0}

    def flaky(url, timeout=30):
        hits["n"] += 1
        if hits["n"] < 3:                      # 前两次 403，第三次通
            raise RuntimeError("403 Client Error: Forbidden")
        return json.dumps({"content": [], "totalRows": 0})

    monkeypatch.setattr(fc, "_get", flaky)
    monkeypatch.setattr(fc.time, "sleep", lambda *_: None)

    body = fc._uso_get("https://www.usopen.org/whatever")
    assert json.loads(body)["totalRows"] == 0
    assert hits["n"] == 3, f"没有重试，只发了 {hits['n']} 次"


def test_重试不许升到_get自己上面去(monkeypatch):
    """上一条的另一头：**别的站是恒 403，重试只是把一次失败拖成四次。**

    `atptour.com` 全站 403 是这个仓库量死过的结论（CLAUDE.md 记着）。把重试
    升进 `_get`，「这条路不通」这个真结论会跟着慢四倍，而它一点用都没有。

    ⚠️ **桩必须打在 `requests.get` 上，不能打在 `fc._get` 上。** 第一版就是
    那么写的，而且和上一条挤在同一个测试函数里——`fc._get` 早被上一头换成了
    桩，这一头调到的还是它，真正的 `_get` 里有没有重试循环**根本走不到**。
    反向验证时把重试升进 `_get`，它照样绿。**恒真的断言比没有断言更坏**，
    是反向验证把它抓出来的。
    """
    sent = {"n": 0}

    class _Resp:
        text = ""

        def raise_for_status(self):
            raise RuntimeError("403 Client Error: Forbidden")

    def one_shot(url, **kw):
        sent["n"] += 1
        return _Resp()

    monkeypatch.setattr(fc.requests, "get", one_shot)
    try:
        fc._get("https://www.atptour.com/")
    except RuntimeError:
        pass
    assert sent["n"] == 1, (
        f"`_get` 自己也重试了 {sent['n']} 次——恒 403 的站会被拖成四倍，"
        f"而「这条路不通」这个真结论跟着慢四倍")


def test_三处美网调用都走带重试的那条路():
    """判据钉的是**位置**，不是行为。

    行为测试只证明 `_uso_get` 会重试，证明不了三个调用点真的用了它——
    「一个数写两处必分叉」的老账：改一处、漏两处，而漏掉的那两处照旧把限流
    读成查空，报告上一个字都不差。
    """
    src = (ROOT / "tools" / "find_cover_photo.py").read_text(encoding="utf-8")
    body = re.sub(r'"""[\s\S]*?"""', "", src)          # 去掉 docstring，注释里会提到这些名字
    body = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    for feed in ("_USO_PLAYERS.format", "/tag?tags=", "/content/byType/photo"):
        line = [l for l in body.splitlines() if feed in l and "_get(" in l]
        assert line, f"找不到调用 {feed} 的那一行"
        assert all("_uso_get(" in l for l in line), (
            f"{feed} 那一处还在裸调 `_get`，间歇 403 会被读成查空：{line}")
