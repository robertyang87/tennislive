"""封面实拍渠道：WTA 赛后稿头图（大满贯也有）、赛事 WP 媒体库按比赛日全翻、中文媒体。

三条都是「图一直在，工具没扫到」：

| slug | 当时推出去的 | 其实就在那儿的 |
|---|---|---|
| `zheng-pridankina-us-open-2026-q3` | 美网官方接口 1280×720（放大 2.0 倍） | WTA 赛后稿头图 `Zheng-Q3-Jimmie.jpg` 4700×2916（64525b36） |
| `zverev-deminaur-laver-cup-2026` | 162.4s 抽帧（「扫最近 12 条」） | 媒体库同场 Getty `CB_38668…`，首推前 25 分钟就上传了（1a4f92d3） |
| `bu-majchrzak-hangzhou-2026-r2` | 抽帧，推了三次 | 公众号「网球之家」本场赛后稿配图（5beecfa6） |
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import cover_cn_media as cc  # noqa: E402
import find_cover_photo as fc  # noqa: E402

# ——— WTA ———

def test_WTA赛后稿头图那种文件名不许被过滤掉():
    """原来只认 `-DSC_1234` 和 `GettyImages-`，`<姓>-<轮次>-<摄影师>.jpg` 整类被扔掉。"""
    for keep in ("Zheng-Q3-Jimmie.jpg", "Eala-R2-Jimmie.jpg",
                 "Townsend-R1-Dylan-Buell-Getty-2.jpg",
                 "Iga_Swiatek_-_US_Open_2026_-_Wednesday_Qs-DSC_7153.jpg",
                 "GettyImages-2296941670.jpg", "Craig-Tiley-trophy.jpg"):
        assert fc.is_wta_photo(keep), keep
    # 2026-09-27 一篇赛后稿上真抓到的站点素材（23 条里 18 条是这种）
    for drop in ("Corpay_400x160.png", "WTA_Web_Quick-Links_Tiles-Video_288x288.png",
                 "unlocked.png", "New-Site-Footer-Logos-400x160-1-.png",
                 "Accenture-Footer-Logo.png", "Finals-Quick-Link-Tile.png"):
        assert not fc.is_wta_photo(drop), drop


def test_列表页扫到的头图_赛事不写在文件名里也不许被赛事过滤扔掉(monkeypatch):
    page = ('x "photo-resources/2026/08/28/c69dbe44-9fc0-470e-b246-a53f54e8e274/'
            'Zheng-Q3-Jimmie.jpg" y "photo-resources/2025/04/25/120eae50-524a-4a37-a45f-'
            '345a0b38d3eb/Corpay_400x160.png" z "photo-resources/2026/08/27/d3d3624f-1e9e-'
            '4ac8-8454-8deda8ab9a2b/Iga_Swiatek_-_Cincinnati_Open_2026_-_Day_2-DSC_7153.jpg"')
    monkeypatch.setattr(fc, "_get", lambda url, timeout=30: page)
    monkeypatch.setattr(fc, "getty_caption", lambda gid: None)
    rows = fc.sweep_wta("Zheng", "US Open", None)
    assert [r["name"] for r in rows] == ["Zheng-Q3-Jimmie.jpg"]
    assert rows[0]["path_date"] == "2026-08-28"
    # 文件名写着别的赛事的，照旧按赛事筛掉（辛辛那提那张 DSC 不是美网）
    assert not fc.sweep_wta("Swiatek", "US Open", None)
    assert fc.sweep_wta("Swiatek", "Cincinnati", None)


def _wta_item(i, when, title, lead_title, photo, seg="x", body=""):
    return {"id": 4568000 + i, "date": when, "title": title, "description": "",
            "titleUrlSegment": seg, "tags": [{"label": "Match Reaction"}],
            "onDemandUrl": f"https://photoresources.wtatennis.com/photo-resources/{photo}",
            "leadMedia": {"type": "photo", "title": lead_title,
                          "originalDetails": {"width": 4700, "height": 2916}},
            "body": body}


def test_WTA赛后稿走内容接口_大满贯也有_头图是本人的排前面():
    pages = {
        0: [_wta_item(1, "2026-08-30T10:00:00Z", "Sabalenka through", "Sabalenka, US Open",
                      "2026/08/30/u1/Sabalenka-R1-Jimmie.jpg")],
        # ⚠️ 接口按发稿时刻新到旧给——头图是别人的那篇**排在前面**（晚发），
        # 不重排的话「提到名字」的稿子会压在本人头图上面
        1: [_wta_item(3, "2026-08-28T20:57:00Z",
                      "Montgomery returns to US Open main draw; Zheng's match pushed",
                      "Robin Montgomery, US Open 2026",
                      "2026/08/28/u3/Robin-Montgomery-US-Open-2026.jpg"),
            _wta_item(2, "2026-08-28T18:31:00Z",
                      "Zheng, Liutova qualify for US Open; Zidansek stops Andreescu",
                      "Zheng Qinwen, US Open 2026",
                      "2026/08/28/c69dbe44/Zheng-Q3-Jimmie.jpg",
                      seg="zheng-liutova-qualify-for-us-open")],
        2: [_wta_item(4, "2026-08-20T00:00:00Z", "Zheng in Cincinnati", "Zheng Qinwen",
                      "2026/08/20/u4/Zheng-R2-Jimmie.jpg")],
    }
    asked = []

    def fetch(url):
        page = int(url.split("page=")[1].split("&")[0])
        asked.append(page)
        return {"content": pages.get(page, [])}

    res = fc.sweep_wta_articles("Zheng", "2026-08-28", fetch=fetch)
    got = [(r["caption"], r["lead_is_player"]) for r in res["rows"]]
    assert got == [("Zheng Qinwen, US Open 2026", True),
                   ("Robin Montgomery, US Open 2026", False)], got
    top = res["rows"][0]
    assert top["url"].endswith("/Zheng-Q3-Jimmie.jpg?width=4000")
    assert top["url"].startswith("https://photoresources.wtatennis.com/photo-resources/")
    assert top["wh"] == "4700x2916"
    assert asked == [0, 1, 2], "翻到窗口起点之前就该停——第 2 页已经早于窗口"
    assert not res["notes"]

    # 翻满还没翻到窗口起点：要明说「更早的没查」
    res = fc.sweep_wta_articles("Zheng", "2026-08-28", fetch=fetch, max_pages=1)
    assert res["notes"] and "没查" in res["notes"][0]


# ——— WP 媒体库 ———

def _wp_media(i, caption="", title="Laver Cup 2026 – Day 2", name=None):
    return {"id": i, "date": f"2026-09-26T{10 + i % 12:02d}:00:00",
            "date_gmt": f"2026-09-26T{10 + i % 12:02d}:00:00",
            "source_url": f"https://www.lavercup.com/wp-content/uploads/2026/09/"
                          f"{name or f'IMG_{i:04d}'}.jpg",
            "title": {"rendered": title}, "caption": {"rendered": f"<p>{caption}</p>"},
            "alt_text": "", "media_details": {"width": 1200, "height": 727}}


def test_WP媒体库按比赛日全翻再按名字筛_不是最近N条():
    """那张同场 Getty 在第 2 页（第 127 张）；说明里有名字、文件名里没有。"""
    items = [_wp_media(i, caption="LONDON – Crowd atmosphere") for i in range(150)]
    items[126] = _wp_media(
        126, name="CB_38668_851hOsBx_20260926044626",
        caption="LONDON, ENGLAND – SEPTEMBER 26: Alex de Minaur of Team World reacts as "
                "he competes against Alexander Zverev of Team Europe")
    asked = []

    def fetch(url):
        asked.append(url)
        if "/posts?" in url:
            return [], {}
        page = int(url.rsplit("page=", 1)[1])
        return items[(page - 1) * 100: page * 100], {"X-WP-TotalPages": "2"}

    res = fc.sweep_tournament("www.lavercup.com", "2026-09-26", "de Minaur", fetch=fetch)
    assert res["scanned"] == 150
    assert [r["url"].rsplit("/", 1)[-1] for r in res["by_name"]] == \
        ["CB_38668_851hOsBx_20260926044626.jpg"]
    assert "Alex de Minaur of Team World reacts" in res["by_name"][0]["caption"]
    media_urls = [u for u in asked if "/media?" in u]
    assert "after=2026-09-26T00:00:00" in media_urls[0]
    assert "before=2026-09-28T00:00:00" in media_urls[0]
    assert not res["notes"]

    # 翻不完要明说
    res = fc.sweep_tournament("www.lavercup.com", "2026-09-26", "de Minaur",
                              fetch=fetch, max_pages=1)
    assert not res["by_name"] and res["notes"] and "没看" in res["notes"][0]


def test_报纸域名只剥协议前缀不剥字符(monkeypatch):
    """`lstrip('https://')` 剥的是字符集：`providencejournal.com` → `rovidencejournal.com`。"""
    asked = []
    monkeypatch.setattr(fc, "_get", lambda url, timeout=30: asked.append(url) or "")
    fc.sweep_local_paper("providencejournal.com", "Newport", None, None)
    fc.sweep_local_paper("https://www.providencejournal.com/", "Newport", None, None)
    assert asked and all(u.startswith(("https://providencejournal.com/",
                                       "https://www.providencejournal.com/"))
                         for u in asked), asked


def test_候选要标出铺封面要不要放大():
    assert fc.fill_note("4700x2916") == "铺满不放大"
    # zverev-deminaur 那张同场 Getty 在媒体库里只有 1200×727——对得上这一场，但比抽帧还软
    assert "1.98" in fc.fill_note("1200x727")
    assert fc.fill_note((1280, 1829)) == "铺满不放大"
    assert fc.fill_note("?") == ""


def test_这一趟查了什么要列出中文媒体那一档(monkeypatch, capsys):
    for name in ("sweep_wta", "sweep_ap"):
        monkeypatch.setattr(fc, name, lambda *a, **k: [])
    monkeypatch.setattr(fc, "sweep_wta_articles",
                        lambda *a, **k: {"rows": [], "notes": [], "window": "w",
                                         "pages_read": 1})
    monkeypatch.setattr(sys, "argv", ["find_cover_photo.py", "--player", "Bu",
                                      "--event", "Hangzhou"])
    assert fc.main() == 0
    out = capsys.readouterr().out
    tail = out.split("=== 这一趟查了什么")[1]
    assert "WTA 赛后稿头图" in tail.split("没跑")[0]
    assert "中文媒体" in tail.split("没跑")[1], tail


def test_这一趟查了什么_一页都没取到的那一档不许记成跑过(monkeypatch, capsys):
    """那份清单是要照抄进 `_frame_why` 的——第 0 页就取不到、搜狗全抛异常，都是「没跑」。"""
    for name in ("sweep_wta", "sweep_ap"):
        monkeypatch.setattr(fc, name, lambda *a, **k: [])
    monkeypatch.setattr(fc, "sweep_wta_articles",
                        lambda *a, **k: {"rows": [], "window": "w", "pages_read": 0,
                                         "notes": ["第 0 页取不到（403）——**这一档没翻完，不是没有**"]})
    monkeypatch.setattr(cc, "sweep_cn_media", lambda *a, **k: {
        "rows": [], "notes": [], "ran": [], "skipped": ["搜狗微信", "当地网站（杭州没登记）"]})
    monkeypatch.setattr(sys, "argv", ["find_cover_photo.py", "--player", "Bu",
                                      "--event", "Hangzhou", "--zh", "布云朝克特"])
    assert fc.main() == 0
    tail = capsys.readouterr().out.split("=== 这一趟查了什么")[1]
    ran, skipped = tail.split("没跑")[0], tail.split("没跑")[1]
    assert "WTA 赛后稿头图" not in ran and "WTA 赛后稿头图" in skipped, tail
    assert "搜狗微信" not in ran and "中文媒体·搜狗微信" in skipped, tail
    assert "当地网站（杭州没登记）" in skipped, tail


# ——— 中文媒体 ———

_SOGOU = """
<ul class="news-list">
<li id="sogou_vr_11002601_box_0" d="x"><div class="txt-box">
<h3><a target="_blank" href="/link?url=dn9a_AAA&amp;type=2&amp;query=x" id="t0">
锐评<em><!--red_beg-->布云朝克特<!--red_end--></em>进八强:够拼的小布</a></h3>
<div class="s-p"><span class="all-time-y2">网球之家</span>
<span class="s2"><script>document.write(timeConvert('1790407806'))</script></span></div>
</div></li>
<li id="sogou_vr_11002601_box_1" d="x"><div class="txt-box">
<h3><a target="_blank" href="/link?url=dn9a_BBB" id="t1">四川大学华西医院心脏大血管外科胡佳教授团队</a></h3>
<div class="s-p"><span class="all-time-y2">血管资讯</span>
<span class="s2"><script>document.write(timeConvert('1767494400'))</script></span></div>
</div></li>
</ul>"""

_LINK_JS = """<script>
    setTimeout(function () {
        var url = '';
        url += 'https://mp.';
        url += 'weixin.qq.c';
        url += 'om/s?src=11';
        url += '&timestamp=';
        url += '1790497185&';
        url += 'ver=6991&si';
        url += 'gnature=o@Hf';
        url.replace("@", "");
        window.location.replace(url)
    },100);
</script>"""

_ARTICLE = """<meta property="og:title" content="锐评布云朝克特进八强" />
<script>var nickname = htmlDecode("网球之家"); var ct = "1790407806";</script>
<img data-src="https://mmbiz.qpic.cn/mmbiz_jpg/AbC123/640?wx_fmt=jpeg&amp;from=appmsg" />
<img data-src="https://mmbiz.qpic.cn/sz_mmbiz_jpg/DeF456" />
<img data-src="https://mmbiz.qpic.cn/mmbiz_gif/GhI789/640?wx_fmt=gif" />
<img data-src="https://mmbiz.qpic.cn/mmbiz_png/JkL/640?wx_fmt=png" />"""


def test_搜狗微信结果页和跳转页和文章页都认得出():
    rows = cc.parse_sogou_results(_SOGOU)
    assert rows[0]["title"] == "锐评布云朝克特进八强:够拼的小布"
    assert rows[0]["account"] == "网球之家"
    assert rows[0]["ts"] == dt.datetime.fromtimestamp(1790407806, dt.timezone.utc)
    assert rows[0]["link"].startswith("https://weixin.sogou.com/link?url=dn9a_AAA&type=2")
    # 跳转页把地址拆成十几段 `url += '…'`，还往里掺一个 @
    assert cc.sogou_link_target(_LINK_JS) == (
        "https://mp.weixin.qq.com/s?src=11&timestamp=1790497185&ver=6991&signature=oHf")
    art = cc.weixin_article(_ARTICLE)
    assert art["account"] == "网球之家" and art["title"] == "锐评布云朝克特进八强"
    assert art["images"] == [
        "https://mmbiz.qpic.cn/mmbiz_jpg/AbC123/0?wx_fmt=jpeg",
        "https://mmbiz.qpic.cn/sz_mmbiz_jpg/DeF456/0?wx_fmt=jpeg",
        "https://mmbiz.qpic.cn/mmbiz_png/JkL/0?wx_fmt=png"], "gif 是分割线，原图要换成 /0"


def test_当地网站列表页和文章页认得出():
    listing = ('<li><a href="//ent.scol.com.cn/ty/202609/83329666.html" target="_blank">'
               'J300冠军胡佳首秀憾负 中国网球小将交出成长答卷</a></li>'
               '<li><a href="//ent.scol.com.cn/ty/202609/83331381.html">吴艳妮</a></li>')
    arts = cc.parse_outlet_listing(listing, "https://ent.scol.com.cn/ty/")
    assert arts[0] == ("https://ent.scol.com.cn/ty/202609/83329666.html",
                       "J300冠军胡佳首秀憾负中国网球小将交出成长答卷")
    page = ('<img src="/images/2013scol.jpg"><span>2026-09-23 18:36</span>'
            '<img src="https://imgcdn.scol.com.cn/media/2026/09/23/190418125794.jpg">'
            '<img src="https://imgcdn.scol.com.cn/media/2026/09/27/150851319840.gif">')
    imgs, when = cc.outlet_article_images(page)
    assert imgs == ["https://imgcdn.scol.com.cn/media/2026/09/23/190418125794.jpg"]
    assert when == "2026-09-23 18:36"


class _Resp:
    def __init__(self, text, url="https://weixin.sogou.com/weixin?x"):
        self.text, self.url, self.encoding = text, url, "utf-8"
        self.apparent_encoding = "utf-8"


class _Session:
    def __init__(self, routes):
        self.routes, self.asked = routes, []

    def get(self, url, params=None, headers=None, timeout=None, **_):
        self.asked.append((url, params))
        for key, value in self.routes:
            if key in url:
                return value if isinstance(value, _Resp) else _Resp(value)
        return _Resp("")


def test_中文媒体按名字和发文时刻筛_筛掉几条要报出来():
    # 路由按最具体的在前：`https://weixin.sogou.com/link?…` 里也有「/weixin」
    session = _Session([("/link?", _LINK_JS), ("mp.weixin.qq.com", _ARTICLE),
                        ("weixin.sogou.com/weixin", _SOGOU)])
    res = cc.sweep_cn_media(["布云朝克特", "迈赫扎克"], date="2026-09-26", city="杭州",
                            session=session, sizes=False)
    assert [r["account"] for r in res["rows"]] == ["网球之家"]
    assert len(res["rows"][0]["images"]) == 3
    assert "搜狗微信" in res["ran"]
    note = next(n for n in res["notes"] if n.startswith("去重后"))
    assert "没有「布云朝克特」的 1 条" in note, note
    # 三组查询词：名字＋对手、名字＋城市、名字——「布云朝克特 八强」这种词 0 条是查询词的锅
    queries = [p["query"] for u, p in session.asked if p]
    assert queries == ["布云朝克特 迈赫扎克", "布云朝克特 杭州", "布云朝克特"]
    assert any("没有登记当地网站" in n for n in res["notes"]), "杭州没有登记当地网站要说没跑"

    # 窗口之外（前一轮的稿子）筛掉
    res = cc.sweep_cn_media(["布云朝克特"], date="2026-09-20", session=session, sizes=False)
    assert not res["rows"]


def test_搜狗每条查询都取不到_不许记成跑过():
    """代理 403／断网时每条查询都抛异常，`blocked` 一直是 False——原来照样记「跑过」。"""
    class _Down:
        def get(self, *a, **k):
            raise ConnectionError("403 Forbidden (proxy)")

    res = cc.sweep_cn_media(["布云朝克特"], session=_Down(), sizes=False)
    assert "搜狗微信" not in res["ran"], res
    assert "搜狗微信" in res["skipped"], res
    assert any("没跑" in n for n in res["notes"]), res["notes"]
    # 至少一条查询拿回了结果页（哪怕 0 条命中）才算跑过
    ok = cc.sweep_cn_media(["布云朝克特"], session=_Session([("/weixin", "<ul></ul>")]),
                           sizes=False)
    assert "搜狗微信" in ok["ran"] and "搜狗微信" not in ok["skipped"], ok


def test_撞上反爬要说没跑完不是没有():
    session = _Session([("/weixin", _Resp("<html>验证码</html>",
                                          url="https://weixin.sogou.com/antispider/?x"))])
    res = cc.sweep_cn_media(["布云朝克特"], session=session, sizes=False)
    assert "搜狗微信" not in res["ran"]
    assert "搜狗微信" in res["skipped"]
    assert any("antispider" in n and "不是没有" in n for n in res["notes"])


def test_当地网站表里有证据的那一站能跑():
    assert "ent.scol.com.cn" in cc.CN_OUTLETS["成都"][0]
    listing = ('<a href="//ent.scol.com.cn/ty/202609/83329666.html">'
               'J300冠军胡佳首秀憾负</a>')
    session = _Session([("weixin.sogou.com/weixin", "<ul></ul>"),
                        ("ent.scol.com.cn/ty/2026", ('<img src="https://imgcdn.scol.com.cn/'
                                                     'media/2026/09/23/190418125794.jpg">')),
                        ("ent.scol.com.cn/ty/", listing)])
    res = cc.sweep_cn_media(["胡佳", "科普日瓦"], city="成都", session=session, sizes=False)
    scol = [r for r in res["rows"] if r["channel"] == "ent.scol.com.cn"]
    assert len(scol) == 1, "两页列表里同一篇要去重"
    assert scol[0]["images"][0][0].endswith("190418125794.jpg")


def test_cover_photo_problem的报错要指到中文媒体那一档():
    import build_match_reel as reel

    msg = reel.cover_photo_problem({"slug": "zzz-not-approved",
                                    "cover": {"portrait": {"frame_at": 12.0}}})
    assert msg and "--zh" in msg and "--city" in msg


def test_evidence_fixture_is_valid_json():
    # 顺手确认 fixture 里那段搜狗结果不是靠运气解析出来的：两条都认出来了
    assert len(cc.parse_sogou_results(_SOGOU)) == 2
    json.dumps([r["title"] for r in cc.parse_sogou_results(_SOGOU)], ensure_ascii=False)
