"""ATP 封面实拍这条路（赛事官网 WordPress 图库）的判据。

**为什么这条路存在**：已发的 84 条 spec 里 64 条用抽帧，只有 20 条用实拍，
而 4000px 那一档全是女子——WTA 有 `photoresources...?width=4000`，
**ATP 一直没有对应物**。`tools/fetch_atp_cover_photo.py` 补的就是这一格。

这里钉的四条都是**当天量出来才知道方向的**，每一条我都先写反过一次：

| 判据 | 我先写反的那一版 |
|---|---|
| 只扫 `<img src>` 会漏掉绝大多数图 | 「当期图多半是懒加载的，要开 Chromium」——**假的**，URL 一直在 `srcset` 里 |
| `-scaled` 比裸文件名**大** | 「bare filename = original」——**量出来是反的** |
| 日期按**文件名的日期戳**认，不按辑名的「Day N」 | 差点按辑号认，而 Day 5 那辑装的是 `081526` |
| 画布只有一处出处 | 工具里另抄一份 1080×1440 |
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import fetch_atp_cover_photo as atp  # noqa: E402


def test_ATP封面工具和渲染器认的画布是同一个():
    """一个数写两处必分叉。工具不 import 渲染器（要能单跑），所以在这儿钉住。"""
    body = (ROOT / "tools" / "build_match_reel.py").read_text(encoding="utf-8")
    line = next(l for l in body.splitlines() if l.startswith("COVER_FILL_W"))
    rhs = line.split("=", 1)[1]
    w, h = (int(x.strip()) for x in rhs.split(","))
    assert (atp.FILL_W, atp.FILL_H) == (w, h), (
        f"工具认的画布 {atp.FILL_W}×{atp.FILL_H} 和渲染器的 {w}×{h} 对不上——"
        "分叉的样子是「工具说撑得满，闸说撑不满」")


#: 真页面（day-5-best-of-photos，2026-08-16 存的）上量出来的：**裸文本扫到
#: 40 张当期实拍，只扫 `src="` 只有 2 张**。差距不是边角——图库是 fancybox，
#: 原图挂在 `<a href>` 上，`<img>` 里放的是缩略图。
_MEASURED_ALL, _MEASURED_SRC_ONLY = 40, 2


def test_扫图不许只看img_src否则当期图漏掉九成五():
    """⚠️ **这条是那句错结论的判据**。

    我先前只在 `<img ...>` 标签里找，一辑只捞到一张，据此写下「当期图多半是
    懒加载的，要开 Chromium」——而路径一直在 HTML 里，只是挂在 fancybox 的
    `<a href>` 上。**扫得太窄和真的没有长得一模一样。**

    所以这里喂的 fixture 就是真页面的形状：大图是**链接目标**，`<img>` 里
    是缩略图。
    """
    html = (
        '<a href="https://x.com/wp-content/uploads/2026/08/081526_DAY-EIGHT_M-1-of-9.jpg"'
        ' data-fancybox="video-gallery"><span class="vh">081526_DAY EIGHT_M (1 of 9)</span></a>'
        '<img src="https://x.com/wp-content/uploads/2026/08/081526_DAY-EIGHT_M-1-of-9-300x200.jpg">'
        '<a href="https://x.com/wp-content/uploads/2026/08/081526_DAY-EIGHT_M-2-of-9.jpg"'
        ' data-fancybox="video-gallery"></a>'
        '<img data-src="https://x.com/wp-content/uploads/2026/08/081526_DAY-EIGHT_M-3-of-9.jpg">'
    )
    names = {u.rsplit("/", 1)[-1] for u in atp._urls_in(html, "x.com")}
    assert names == {"081526_DAY-EIGHT_M-1-of-9.jpg",
                     "081526_DAY-EIGHT_M-2-of-9.jpg",
                     "081526_DAY-EIGHT_M-3-of-9.jpg"}, (
        f"扫出来 {sorted(names)}——第 2 张只在 `<a href>` 上、第 3 张只在 "
        "`data-src` 上，两张都不许漏；第 1 张的 `-300x200` 缩略图要归并回原图")
    assert _MEASURED_SRC_ONLY * 20 <= _MEASURED_ALL, (
        "真页面上只扫 src= 只能捞到二十分之一——这个比例是这条判据存在的理由，"
        "改小它之前先去真页面重量一次")


def test_响应式后缀要去干净但别把别的数字吃掉():
    keep = "081526_DAY-EIGHT_MIKE-BAKER-112-of-229.jpg"
    assert atp._VARIANT.sub("", keep) == keep, (
        "`-112-of-229` 不是响应式后缀，去掉它就指到一张不存在的图了")
    assert atp._VARIANT.sub("", "A-1024x683.jpg") == "A.jpg"
    assert atp._VARIANT.sub("", "A-150x150.png") == "A.png"


def test_日期按文件名的日期戳认不按辑名的DayN认():
    """⚠️ **辑名的「Day N」是赛事内部编号，和日历日差着好几天。**

    实测：`day-5-best-of-photos` 那一辑装的是 **`081526`**（资格赛也算进
    Day 里）。按辑号认就会把 8/15 的照片当成 8/5 的。
    """
    assert atp.stamp_of("https://x/081526_DAY-EIGHT_MIKE-BAKER-1-of-25.jpg") == date(2026, 8, 15)
    assert atp.stamp_of("https://x/CincinnatiOpen_20260815_JM021268_JW1.jpg") == date(2026, 8, 15)
    # 赞助商图没有日期戳——认不出来要返回 None（工具会把条数打出来），
    # 不许瞎猜一个日期，那会让它冒充成当天的实拍。
    assert atp.stamp_of("https://x/2026_WTA-Unlocked-v2_DigitalAd-564x564-1.jpg") is None
    assert atp.stamp_of("https://x/logo.png") is None


def test_撑不满就要报要放大多少倍():
    """2000×1333 是这条路 2026 年那批的实测尺寸，铺 1080×1440 是 0.93×。

    **它过不了 `cover_photo_problem` 的 1.00× 地板**，所以工具必须把这个数
    报出来并点名 `_low_res_why`——不然下一个人会以为「官方图 = 过关」。
    """
    assert atp.fill_ratio(2000, 1333) < 1.0
    assert round(atp.fill_ratio(2000, 1333), 2) == 0.93
    # 2023 年那批的 `-scaled` 是 2560×1707，撑得满。
    assert atp.fill_ratio(2560, 1707) >= 1.0
    # WTA 那条 4000px 的路，作为对照。
    assert atp.fill_ratio(4000, 2461) > 1.7

def test_上传时刻分三档不明的不许并进另外两档():
    """⚠️ **拍摄日和上传时刻是两个字段，回答两个不同的问题。**

    账号所有者 2026-08-17：「要看时效性，是当时比赛，**同时最好是在比赛结束前
    上传上来的**，不然我们做视频时候也不一定有啊」。

    只看拍摄日会得出一个乐观的结论：今天回头扫，昨天夜场的照片当然都在了；
    可当时（比赛刚打完、片子正要做）它们一张都还没传。**这两种情形在候选
    列表里长得一模一样。**

    「不明」必须是独立的一档：图库页那条路根本没有这个字段，把它算成
    「结束前」是编，算成「结束后」是冤枉。
    """
    end = datetime(2026, 8, 17, 0, 13)
    # 实测：斯维托丽娜那场 21:50 开打，摄影师**边打边传**
    assert atp.upload_class("2026-08-16T21:47:26", end) == atp.IN_TIME
    assert atp.upload_class("2026-08-16T22:33:51", end) == atp.IN_TIME
    assert atp.upload_class("2026-08-17T00:13:00", end) == atp.IN_TIME   # 边界含等号
    assert atp.upload_class("2026-08-17T09:02:10", end) == atp.LATE
    # 没有时刻 / 读不出来 / 根本没问——三种都是「不明」，不许猜
    assert atp.upload_class("", end) == atp.UNKNOWN
    assert atp.upload_class("上周", end) == atp.UNKNOWN
    assert atp.upload_class("2026-08-16T22:33:51", None) == atp.UNKNOWN, (
        "没给 --match-end 就不该有答案——不问的问题不许有答案")
    assert len({atp.IN_TIME, atp.LATE, atp.UNKNOWN}) == 3


def test_图库页那张图要继承媒体库查到的上传时刻(monkeypatch, capsys):
    """**只有媒体库那条路带上传时刻**，而同一张图两条路都会扫到。

    先遇到哪条是**扫描顺序**决定的，不该决定它有没有时效性——所以要按 URL
    继承。反过来（不继承）的样子是「一张明明查得到上传时间的图被标成不明」，
    而那正是这条判据要防的静默。

    顺带钉住排序：**结束前上传的排在前面**，但一张都不许丢——结束后传的
    今天仍然取得到，它只是当时来不及。
    """
    early = "https://x.com/wp-content/uploads/2026/08/CincinnatiOpen_20260816_A.jpg"
    late = "https://x.com/wp-content/uploads/2026/08/CincinnatiOpen_20260816_B.jpg"
    only_in_gallery = "https://x.com/wp-content/uploads/2026/08/081626_DAY-SEVEN_C-1-of-9.jpg"

    monkeypatch.setattr(atp, "gallery_posts",
                        lambda site: ["https://x.com/news/day-7-best-of-photos/"])
    monkeypatch.setattr(atp, "media_library", lambda site, pages=4: [
        ("2026-08-17T09:02:10", late),
        ("2026-08-16T22:33:51", early),
    ])
    # 图库页那一辑三张都有——`early` 在这儿再出现一次，它必须仍然算「结束前」
    monkeypatch.setattr(atp, "photo_urls",
                        lambda post: [early, only_in_gallery, late])

    code, notes = atp.run("x.com", date(2026, 8, 16), "", None, 40,
                          datetime(2026, 8, 17, 0, 13))
    assert code == 0, notes
    body = "\n".join(notes)

    assert f"{atp.IN_TIME} 1 张" in body, f"继承没生效：\n{body}"
    assert f"{atp.LATE} 1 张" in body, body
    assert f"{atp.UNKNOWN} 1 张" in body, (
        "只在图库页出现的那张查不到上传时刻，必须照实标「不明」——"
        f"不许并进另外两档：\n{body}")

    picked = [l for l in notes if l.startswith("  ")]
    assert len(picked) == 3, f"三张一张都不许丢：{picked}"
    assert atp.IN_TIME in picked[0], f"结束前上传的要排在最前面：{picked}"
    assert atp.LATE in picked[-1], f"结束后上传的要排在最后：{picked}"


def test_一张都没赶上结束前要单独喊出来(monkeypatch):
    """**「今天取得到」不等于「当时来得及」**，而这两件事在候选表里没有区别。

    这一句是给下一场用的：这条渠道这次没赶上，下一场多半也赶不上，
    该去多找一条，而不是等它。
    """
    late = "https://x.com/wp-content/uploads/2026/08/CincinnatiOpen_20260816_B.jpg"
    monkeypatch.setattr(atp, "gallery_posts", lambda site: ["https://x.com/news/d/"])
    monkeypatch.setattr(atp, "media_library",
                        lambda site, pages=4: [("2026-08-17T09:02:10", late)])
    monkeypatch.setattr(atp, "photo_urls", lambda post: [])

    code, notes = atp.run("x.com", date(2026, 8, 16), "", None, 40,
                          datetime(2026, 8, 17, 0, 13))
    body = "\n".join(notes)
    assert code == 0
    assert "结束前一张都没传上来" in body, body

    # 反过来：赶上了就不许喊，恒真的告警会把真正该看见的那次淹掉
    monkeypatch.setattr(atp, "media_library",
                        lambda site, pages=4: [("2026-08-16T22:33:51", late)])
    _, ok = atp.run("x.com", date(2026, 8, 16), "", None, 40,
                    datetime(2026, 8, 17, 0, 13))
    assert "结束前一张都没传上来" not in "\n".join(ok)


def test_日期戳三套命名都要认出来():
    """**一个赛事同时有好几位摄影师，每人一套文件名。**

    只认其中一套的后果是**静默漏掉另外几套**，而漏掉的样子和「这一天没有实拍」
    一模一样——CLAUDE.md「扫得太窄和真的没有长得一模一样」的又一个实例。

    2026-08-17 量出来的账（辛辛那提 8/16，赛事官网媒体库）：

        只认 `CincinnatiOpen_<YYYYMMDD>_`      18 张
        三套都认                                **60 张**   ← 漏了 42 张，超过三分之二

    而我据此在 spec 里写过「赛事媒体库当天全是日场，没有这一场」——**那句话是
    从一个漏了三分之二的扫描结果得出来的**。

    ⚠️ 这条判据钉的是「三套都认」，不是「认得出某一个具体文件名」：
    **不认识的要返回 None**（赞助商图、logo 不能被当成某一天的实拍）。
    """
    from fetch_atp_cover_photo import stamp_of

    cases = {
        "CincinnatiOpen_20260816_JM021783_PS2.jpg": date(2026, 8, 16),
        "081626_DAY-SEVEN_MIKE-BAKER-1-of-9.jpg": date(2026, 8, 16),
        "CincyOpen8.16.26BJ_306.jpg": date(2026, 8, 16),
        # 月/日不补零的那一套，跨到两位数的月份也要对
        "CincyOpen12.3.26BJ_7.jpg": date(2026, 12, 3),
    }
    for name, want in cases.items():
        assert stamp_of(name) == want, f"{name} 认成了 {stamp_of(name)}，应当是 {want}"

    for junk in ("sponsor-logo.png", "hero-banner.jpg", "cincy-map-v2.png"):
        assert stamp_of(junk) is None, (
            f"{junk} 被认成了 {stamp_of(junk)}——认不出的必须返回 None，"
            "不然赞助商图会被当成某一天的实拍")
