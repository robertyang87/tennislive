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
