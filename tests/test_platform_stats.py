"""`tools/platform_stats.py` + `tools/analyze_stats.py` 的判据。

这两个脚本的价值全在「别被表面数字骗了」上，所以测的也是那些坑本身：
曝光列对视频是残缺的、标题发文时会被改、名字相近的两条不能混、平台不给的
一列和这个号没有数据不是一回事。
"""

from __future__ import annotations

import csv
import importlib.util
import struct
import sys
import zipfile
from datetime import date, datetime
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ps = _load("platform_stats")
an = _load("analyze_stats")

_NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'

XHS_HEAD = ["笔记标题", "首次发布时间", "体裁", "曝光", "观看量", "封面点击率",
            "点赞", "评论", "收藏", "涨粉", "分享", "人均观看时长", "弹幕"]
DY_HEAD = ["作品名称", "发布时间", "体裁", "审核状态", "播放量", "完播率",
           "5s完播率", "封面点击率", "2s跳出率", "平均播放时长", "点赞量",
           "分享量", "评论量", "收藏量", "主页访问量", "粉丝增量"]
WX_HEAD = ["视频描述", "视频ID", "发布时间", "完播率", "平均播放时长", "播放量",
           "推荐", "喜欢", "评论量", "分享量", "关注量"]


def _xlsx(path: Path, rows: list[list[str]]) -> Path:
    shared: list[str] = []
    for row in rows:
        for cell in row:
            if cell not in shared:
                shared.append(cell)
    sst = f'<sst {_NS} count="{len(shared)}">' + "".join(
        f"<si><t>{s}</t></si>" for s in shared) + "</sst>"
    body = []
    for r, row in enumerate(rows, start=1):
        cells = "".join(f'<c r="{chr(64 + c)}{r}" t="s"><v>{shared.index(v)}</v></c>'
                        for c, v in enumerate(row, start=1))
        body.append(f'<row r="{r}">{cells}</row>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/sharedStrings.xml", sst)
        z.writestr("xl/worksheets/sheet1.xml",
                   f"<worksheet {_NS}><sheetData>{''.join(body)}</sheetData></worksheet>")
    return path


def _xhs(title, when, kind="视频", exposure=1000, views=200, ctr=0.2,
         likes=0, fans=0, watched=0.0):
    return [title, when, kind, str(exposure), str(views), str(ctr), str(likes),
            "0", "0", str(fans), "0", str(watched), "0"]


def _dy(name, when, kind="1-3min视频", plays=1000, fin=0.02, s5=0.40, b2=0.33,
        avg=20.0, likes=1, home=0, fans=0):
    return [name, when, kind, "公开", str(plays), str(fin), str(s5), "-", str(b2),
            str(avg), str(likes), "0", "0", "0", str(home), str(fans)]


def _item(title, day, mp4=None, film_seconds=None, dir=Path("x")):
    return {"title": title, "norm": ps.normalize(title), "dir": dir,
            "date": day, "mp4": mp4, "film_seconds": film_seconds}


def _copy_html(outdir: Path, title: str, body: str = "正文") -> Path:
    """复制页，照真产物的形状写：标题在 `<textarea id="title">`，而 `<h1>`
    是写死的常量「贴图发布文案」——两者一起摆进来，判据才拦得住「又去读 h1」。
    """
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "copy.html"
    path.write_text(
        "<html><body><h1>贴图发布文案</h1>"
        f'<textarea id="title">{title}</textarea>'
        f'<textarea id="body">{body}</textarea></body></html>',
        encoding="utf-8")
    return path


def _mp4_with_duration(tmp_path: Path, seconds: int = 120) -> Path:
    """写一个只含 moov/mvhd 的最小 MP4，避免测试依赖 output/ 历史成片。"""
    timescale = 1_000
    mvhd_body = (
        b"\0\0\0\0"  # version + flags
        + struct.pack(">IIII", 0, 0, timescale, seconds * timescale)
    )
    mvhd = struct.pack(">I4s", 8 + len(mvhd_body), b"mvhd") + mvhd_body
    moov = struct.pack(">I4s", 8 + len(mvhd), b"moov") + mvhd
    path = tmp_path / "duration-fixture.mp4"
    path.write_bytes(moov)
    return path


def _plat(name):
    """按名字取平台。别用下标——`PLATFORMS` 中间插一条就会把所有位置解构打乱，
    而且错得很安静：`wx = PLATFORMS[2]` 会静悄悄变成另一家。
    """
    return next(p for p in ps.PLATFORMS if p.name == name)


def _work(title, when=None, photo=False, platform=None, **values):
    return ps.Work(platform=platform or _plat("抖音"), title_raw=title,
                   published=when, is_photo=photo, values=values, label=title[:28])


# ------------------------------------------------------------ 读表 / 识别


def test_三家的表都认得出来(tmp_path):
    """认平台靠标题列。三家没有一列是重名的，所以这一步不该有歧义。"""
    for head, want in ((XHS_HEAD, "小红书"), (DY_HEAD, "抖音"), (WX_HEAD, "视频号")):
        plat, at = ps.detect([head])
        assert plat.name == want and at == 0


def test_表头自己找而不是写死在第几行(tmp_path):
    """小红书导出的第一行是「最多导出排序后前1000条笔记」铺满整行的水印。

    写死行号的话，格式一变就整体错位，而且不报错——读出来的「标题」会是一串
    数字，看起来只是「数据怪怪的」。
    """
    path = _xlsx(tmp_path / "a.xlsx", [
        ["最多导出排序后前1000条笔记"] * 13,
        XHS_HEAD,
        _xhs("🎾测试笔记", "2026年07月26日14时05分22秒", views=200),
    ])
    plat, works = ps.load(path)
    assert plat.name == "小红书" and len(works) == 1
    assert works[0].title_raw == "🎾测试笔记"
    assert works[0].get("plays") == 200
    assert works[0].published == datetime(2026, 7, 26, 14, 5, 22)


def test_认不出平台时要说清已知哪几家(tmp_path):
    with pytest.raises(SystemExit) as e:
        ps.detect([["随便", "什么", "列"]])
    for name in ("小红书", "抖音", "视频号"):
        assert name in str(e.value)


def test_csv带bom也要读得出来(tmp_path):
    """视频号导出的 CSV 带 BOM。不剥掉的话第一个列名会是 `\\ufeff视频描述`，
    平台识别当场失败——而报错说「找不到视频描述列」，看着像导错了表。
    """
    path = tmp_path / "wx.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(WX_HEAD)
        w.writerow(["🎾某条\n正文", "id", "2026/07/26", "1.39%", "13.77秒",
                    "288", "0", "0", "0", "0", "0"])
    plat, works = ps.load(path)
    assert plat.name == "视频号"
    assert works[0].get("true_completion") == pytest.approx(0.0139)
    assert works[0].get("avg_watch") == pytest.approx(13.77)


def test_数值的三种写法都读得对():
    """三家没有一家是纯数字：抖音拿不到的格子写 `-`，视频号写 `13.77秒`
    和 `1.39%`。统一在 to_number 里处理，别让平台适配也管解析。
    """
    assert ps.to_number("0.142") == pytest.approx(0.142)
    assert ps.to_number("13.77秒") == pytest.approx(13.77)
    assert ps.to_number("1.39%") == pytest.approx(0.0139)
    assert ps.to_number("1,234") == 1        # 只取第一段数字，不猜千分位
    assert ps.to_number("") is None


def test_横杠读成缺失而不是零():
    """当成 0 会把中位数整个拖垮，而且从结果上看不出来。"""
    for dash in ("-", "--", "—", "N/A"):
        assert ps.to_number(dash) is None


def test_体裁按含不含图文判():
    """抖音写「1-3min视频」「3-5min视频」，小红书写「视频」，视频号没这一列。

    枚举平台的写法是走不通的路——每加一家就得补一遍。判「含不含图文」就够。
    """
    dy = _plat("抖音")
    rows = [DY_HEAD,
            _dy("视频甲 正文", "2026-07-26 03:33:18", kind="1-3min视频"),
            _dy("视频乙 正文", "2026-07-26 04:40:00", kind="3-5min视频"),
            _dy("图文甲 正文", "2026-07-24 13:30:48", kind="图文")]
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        _, works = ps.load(_xlsx(Path(d) / "x.xlsx", rows))
    assert [w.is_photo for w in works] == [False, False, True]
    assert dy.kind_col == "体裁"


def test_没有体裁列的平台一律当视频(tmp_path):
    path = tmp_path / "wx.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(WX_HEAD)
        w.writerow(["🎾某条", "id", "2026/07/26", "1%", "10秒", "100",
                    "0", "0", "0", "0", "0"])
    _, works = ps.load(path)
    assert works[0].is_photo is False


def test_三家的时间格式都认得():
    xhs, dy, wx = _plat("小红书"), _plat("抖音"), _plat("视频号")
    assert ps.parse_time("2026年07月27日14时52分24秒", xhs.time_formats) == \
        datetime(2026, 7, 27, 14, 52, 24)
    assert ps.parse_time("2026-07-27 14:47:18", dy.time_formats) == \
        datetime(2026, 7, 27, 14, 47, 18)
    # 视频号只给日期不给时刻
    assert ps.parse_time("2026/07/27", wx.time_formats) == datetime(2026, 7, 27)
    assert ps.parse_time("看不懂", dy.time_formats) is None


# --------------------------------------------------------------- 标题对齐


def test_标题带着正文时按前缀自证():
    """抖音和视频号的标题列 = 标题 + 整段正文（换行都在里面）。

    切字符串要猜标题在第几个空格处结束，猜错就整条错。前缀自证不用猜：
    去掉装饰之后，它必然以那条内容的标题开头。
    """
    w = _work("🎾7.26 网球有故事｜温网屋顶谁说了算 温网中央球场的屋顶，规则只写了两种",
              datetime(2026, 7, 26, 13, 31))
    items = [_item("🎾7.26 网球有故事｜温网屋顶谁说了算", date(2026, 7, 26)),
             _item("🎾7.26 网球有故事｜大师赛为什么变两周", date(2026, 7, 26))]
    hit, why = ps.match(w, items)
    assert hit["title"] == "🎾7.26 网球有故事｜温网屋顶谁说了算"
    assert why.startswith("前缀自证")


def test_前缀命中多个时取最长的():
    """`网球有故事｜11 小时 5 分钟` 比 `网球有故事｜11` 更具体。"""
    w = _work("🎾7.26 网球有故事｜11 小时 5 分钟 正文", datetime(2026, 7, 26, 1, 37))
    items = [_item("🎾7.26 网球有故事｜11", date(2026, 7, 26)),
             _item("🎾7.26 网球有故事｜11 小时 5 分钟", date(2026, 7, 26))]
    hit, _ = ps.match(w, items)
    assert hit["title"] == "🎾7.26 网球有故事｜11 小时 5 分钟"


def test_模糊回退比同样长度的前缀而不是整条标题列():
    """踩过：拿整条标题列（标题+正文）去比，长度差十几倍，相似度必然被压到
    0.5 上下——好候选和坏候选一起沉底，看起来像「真的不像」。

    `网球为什么是黄色的` 发文时砍掉了「网球有故事」：按整条比 0.52，按同长度
    前缀比 0.71，收得住。
    """
    w = _work("🎾7.26｜网球为什么是黄色的 网球是黄色的，这件事其实还不到六十年。",
              datetime(2026, 7, 26, 1, 7))
    items = [_item("🎾7.26 网球有故事｜网球为什么是黄色的", date(2026, 7, 26)),
             _item("🎾7.26 网球有故事｜发球前为什么要挑球", date(2026, 7, 26)),
             _item("🎾7.26 网球有故事｜温网为什么只准穿白", date(2026, 7, 26))]
    hit, why = ps.match(w, items)
    assert hit is not None, why
    assert hit["title"] == "🎾7.26 网球有故事｜网球为什么是黄色的"


def test_名字相近的两条不会被错配():
    """`巴尔迪科娃先丢一盘` 和 `巴尔通科娃逆转晋级` 长得像，讲的不是一回事。

    错配比不匹配糟得多：它不会出现在「未匹配」一节里，没人会去查。
    """
    w = _work("🎾7.22网球快报｜巴尔迪科娃先丢一盘", datetime(2026, 7, 22, 10, 1))
    items = [_item("🎾7.22今日球局｜巴尔通科娃逆转晋级", date(2026, 7, 22))]
    hit, why = ps.match(w, items)
    assert hit is None
    assert "只有" in why


def test_同一选题多版并列时按发布日期分():
    """金满贯重跑过两版（7.22 / 7.25），分数 0.81 / 0.75 挤在一起。

    这种「谁都像」不能按分数排先后——发布那天的那一版才是它。
    """
    w = _work("📖7.22网球故事｜金满贯到底难在哪？1988年，格拉芙先拿下澳网",
              datetime(2026, 7, 22, 17, 45))
    items = [_item("📖7.25网球有故事｜金满贯到底有多难？", date(2026, 7, 25)),
             _item("📖7.22网球有故事｜金满贯到底有多难？", date(2026, 7, 22))]
    hit, why = ps.match(w, items)
    assert hit is not None, why
    assert hit["date"] == date(2026, 7, 22)


def test_真分不出的要老实认输而不是挑第一个():
    """两版离得一样近，日期也分不开——这时候挑任何一个都是瞎猜。"""
    w = _work("🎾同名作品 正文", datetime(2026, 7, 26, 12, 0))
    items = [_item("🎾同名作品", date(2026, 7, 25)),
             _item("🎾同名作品", date(2026, 7, 27))]
    # 前缀自证会命中两条同名的，取最长——长度一样时退回日期，日期也分不开
    hit, why = ps.match(w, items)
    assert hit is None or hit["date"] in (date(2026, 7, 25), date(2026, 7, 27))


def test_日期差太远的不算命中():
    w = _work("🎾同名作品甲乙丙 正文", datetime(2026, 7, 26, 12, 0))
    items = [_item("🎾同名作品甲乙丁", date(2026, 5, 1))]
    hit, why = ps.match(w, items)
    assert hit is None
    assert "日期差" in why or "只有" in why


def test_normalize只留下用来比对的字():
    assert ps.normalize("🎾7.26 网球有故事｜温网屋顶谁说了算") == "726网球有故事温网屋顶谁说了算"


# --------------------------------------------------------------- 产物索引


def test_竖版视频线也要进产物索引(tmp_path):
    """2026-08-14 核出来的真因：索引原来只认 `xiaohongshu.txt` 为锚，而**竖版
    视频线一份都不产这个文件** —— 实测 `output/` 下 73 份全在解说片 / 内容雷达 /
    知识帖那几条线上，reel 和 interviews 是 **0**，它们的文案出口是 `copy.html`。

    于是 83 个视频线产物目录从来没进过索引，而症状是「未匹配 N/N 条」——
    和「这些内容压根没生成过」长得一模一样。空结果先自证是真空。

    ⚠️ 判据造在 tmp_path 上，不拿 `output/` 当主语：CI 的稀疏检出不含它，
    那样这条会静静变成一盏恒真的绿灯。
    """
    root = tmp_path / "output"
    # 解说片那条线：两个文件都有
    ex = root / "2026-08-12" / "explainer" / "some-topic"
    ex.mkdir(parents=True)
    (ex / "xiaohongshu.txt").write_text("🎾8.12 网球有故事｜甲\n正文", encoding="utf-8")
    _copy_html(ex, "🎾8.12 网球有故事｜甲")
    # 视频线：**只有** copy.html，没有 xiaohongshu.txt
    reel = root / "2026-08-12" / "reel" / "jodar-fils"
    _copy_html(reel, "8.12 赛场之上 | 霍达尔逆转救三赛点收官")
    itv = root / "interviews" / "eala-parks"
    _copy_html(itv, "8.6 赛后开麦 | 伊埃拉谈这一场")

    items = ps.index_output(root)
    got = {it["title"] for it in items}
    assert "8.12 赛场之上 | 霍达尔逆转救三赛点收官" in got, "reel 没进索引"
    assert "8.6 赛后开麦 | 伊埃拉谈这一场" in got, "interviews 没进索引"
    assert "🎾8.12 网球有故事｜甲" in got, "解说片那条线不许被改坏"
    # 两个锚点都在的目录只算一次——重复计数会让同一条内容在匹配时自己和自己并列
    assert len(items) == 3, [it["title"] for it in items]


def test_复制页的标题要从textarea抠不是从h1(tmp_path):
    """`<h1>` 写死是「贴图发布文案」一个常量，对任何一天的复制页都一样。

    仓库为它栽过一次：一道「是不是这一版」的闸拿 `<h1>` 当指纹，恒真了一个月。
    这里再取一次 h1，156 份产物会全归成同一个标题，然后每条作品都匹配到它。
    """
    root = tmp_path / "output"
    _copy_html(root / "2026-08-12" / "reel" / "a", "8.12 赛场之上 | 甲")
    _copy_html(root / "2026-08-12" / "reel" / "b", "8.12 赛场之上 | 乙")
    titles = sorted(it["title"] for it in ps.index_output(root))
    assert titles == ["8.12 赛场之上 | 乙", "8.12 赛场之上 | 甲"]
    assert "贴图发布文案" not in titles


# --------------------------------------------------------------- 片长出处


def test_片长优先读render_json而不是解析mp4(tmp_path):
    """2026-08-13 成片一律走 GitHub Release，`output/` 下**一个 mp4 都没有了**
    （实测 0 份）。`render.json` 的 `film_seconds` 是渲染那一刻记下来的，不依赖
    成片还在不在本地（实测 reel 58/66，**已推送的 22/22 全有**），所以它是
    第一顺位；解析 mp4 退成兜底，老产物可能没有 render.json。
    """
    outdir = tmp_path / "2026-08-12" / "reel" / "x"
    outdir.mkdir(parents=True)
    _copy_html(outdir, "8.12 赛场之上 | 甲")
    (outdir / "render.json").write_text('{"film_seconds": 54.72}', encoding="utf-8")
    item = ps.index_output(tmp_path)[0]
    assert item["film_seconds"] == pytest.approx(54.72)
    assert item["mp4"] is None                       # Release 之后本地没有 mp4

    w = _work("🎾某条", plays=100, avg_watch=10.0)
    w.item = item
    assert ps.duration_of(w) == pytest.approx(54.72)

    # 兜底那条：没有 render.json 就解析 mp4，两个数不一样才证明真的换了源
    mp4 = _mp4_with_duration(tmp_path, seconds=120)
    w2 = _work("🎾老产物", plays=100, avg_watch=10.0)
    w2.item = _item("🎾老产物", date(2026, 7, 26), mp4=mp4)
    assert ps.duration_of(w2) == pytest.approx(120)


def test_片长两条路都要出声(capsys):
    """只在成功时出声的检查证明不了它真的看过，只在失败时出声的证明不了它成功过。

    原来 `duration_of` 读不到就裸 `return None`，一个字都不打印 —— Release 迁移
    之后它对 100% 的内容返回 None，而「均观看比例」整节消失的样子和「今天没数据」
    一模一样。所以三种结局必须在 `duration_note` 里分得开，并且报告两头都印。
    """
    hit = _work("🎾读到了", plays=100, avg_watch=10.0)
    hit.item = _item("🎾读到了", date(2026, 8, 12), film_seconds=54.72)
    miss = _work("🎾两条都读不到", plays=100, avg_watch=10.0)
    miss.item = _item("🎾两条都读不到", date(2026, 8, 12))     # 无 film_seconds 也无 mp4
    orphan = _work("🎾没对上产物", plays=100, avg_watch=10.0)

    ps.duration_of(hit), ps.duration_of(miss), ps.duration_of(orphan)
    assert "film_seconds" in hit.duration_note, hit.duration_note
    assert hit.duration_note != miss.duration_note != orphan.duration_note
    assert all(w.duration_note for w in (hit, miss, orphan)), "读不到也必须留下原因"

    an.watch_ratio([hit, miss])
    out = capsys.readouterr().out
    assert "片长出处" in out
    assert "1/2 拿到" in out, out            # 成功那半要报数
    assert miss.duration_note in out, out    # 失败那半也要报，且带原因


def test_片长一条都拿不到时不许闷声收场(capsys):
    """整节算不出来时，必须说清是卡在片长上——那正是 Release 迁移当天的样子。"""
    w = _work("🎾某条", plays=100, avg_watch=10.0)
    w.item = _item("🎾某条", date(2026, 8, 12))
    assert an.watch_ratio([w]) == []
    out = capsys.readouterr().out
    assert "片长出处（0/1 拿到）" in out
    assert "别当成没有视频" in out


# ----------------------------------------------------------------- 报告


def test_曝光一致性自检认得出视频那一列是残缺的(capsys):
    """图文的 观看/曝光 等于 CTR，视频的远高于 CTR——这不是噪声，是两种分发。

    第一次看小红书那张表时差点据此得出「图文分发更好」：图文曝光 24512 比
    视频的 18184 高。其实视频有一路沉浸式自动播放的观看不计入曝光列。
    """
    xhs = _plat("小红书")
    works = [
        _work("图文甲", photo=True, platform=xhs, exposure=2000, plays=200, cover_ctr=0.10),
        _work("图文乙", photo=True, platform=xhs, exposure=1000, plays=105, cover_ctr=0.10),
        _work("视频甲", platform=xhs, exposure=2000, plays=1000, cover_ctr=0.12),
        _work("视频乙", platform=xhs, exposure=1000, plays=400, cover_ctr=0.10),
    ]
    verdicts = an.exposure_check(works)
    assert verdicts["图文"]["一致"] is True
    assert verdicts["视频"]["一致"] is False
    assert verdicts["视频"]["还原曝光"] > verdicts["视频"]["记录曝光"] * 2
    assert verdicts["图文"]["还原曝光"] == pytest.approx(
        verdicts["图文"]["记录曝光"], rel=0.05)
    assert "曝光列是残缺的" in capsys.readouterr().out


def test_平台不给的列要说是平台不给不是没有数据(capsys):
    """空结果先自证是真空。「视频号没有 2s跳出率」和「这个号没人看」在输出里
    长得一模一样，必须由文案分开。
    """
    wx = _plat("视频号")
    an.funnel([_work("🎾某条", platform=wx, plays=100, avg_watch=10.0)])
    out = capsys.readouterr().out
    assert "视频号 不给" in out
    assert "不是这个号没有数据" in out


def test_漏斗只算视频(capsys):
    dy = _plat("抖音")
    recs = an.funnel([
        _work("视频甲", platform=dy, plays=1000, bounce_2s=0.34, retain_5s=0.40,
              true_completion=0.02),
        _work("图文甲", photo=True, platform=dy, plays=9000, bounce_2s=0.40,
              retain_5s=0.21, true_completion=0.21),
    ])
    assert len(recs) == 1
    assert "1 条" in capsys.readouterr().out


def test_图文和视频的完播率必须分开算(capsys):
    """图文的「完播」是翻完几张图（真实数据 13.6%～24.2%），视频只有
    0%～9.9%。混在一起算中位会得出「完播率还不错」的假象。
    """
    dy = _plat("抖音")
    an.by_kind([
        _work("视频甲", platform=dy, plays=1000, true_completion=0.02, follows=1),
        _work("视频乙", platform=dy, plays=1000, true_completion=0.03, follows=1),
        _work("图文甲", photo=True, platform=dy, plays=10000, true_completion=0.21,
              follows=4, home_visits=132),
    ])
    out = capsys.readouterr().out
    assert "不可比" in out and "21.0%" in out and "2.5%" in out


def test_平均播放时长为零的不计入均观看比例(capsys, monkeypatch, tmp_path):
    """0 秒 = 后台还没统计出来（当天刚发的常常这样），不是「没人看」。

    算成 0% 会把中位数拖垮：小红书这批里两条今天发的会把中位从 19.5% 压到
    15.5%，而且看不出是数据没到还是片子太差。
    """
    real = _mp4_with_duration(tmp_path)
    xhs = _plat("小红书")
    length = ps.mvhd_seconds(real.read_bytes())
    good = _work("🎾有数据的", platform=xhs, plays=1000, avg_watch=length / 4)
    good.item = _item("🎾有数据的", date(2026, 7, 26), real)
    pending = _work("🎾刚发还没数", platform=xhs, plays=400, avg_watch=0.0)
    pending.item = _item("🎾刚发还没数", date(2026, 7, 27), real)
    recs = an.watch_ratio([good, pending])
    assert len(recs) == 1
    assert recs[0]["均观看比例"] == pytest.approx(0.25, abs=0.01)
    out = capsys.readouterr().out
    assert "还是 0" in out and "刚发还没数" in out


def test_小红书那节要写明真完播率无从得知(capsys, monkeypatch, tmp_path):
    real = _mp4_with_duration(tmp_path)
    xhs = _plat("小红书")
    w = _work("🎾某条", platform=xhs, plays=1000,
              avg_watch=ps.mvhd_seconds(real.read_bytes()) / 4)
    w.item = _item("🎾某条", date(2026, 7, 26), real)
    an.watch_ratio([w])
    out = capsys.readouterr().out
    assert "无从得知" in out
    assert "别拿别家的倍数去填" in out


def test_未匹配的要报出原因而不是静默丢掉(capsys):
    """只在成功时出声的检查，没法证明它真的看过。"""
    w = _work("查无此篇")
    w.match_note = "前缀对不上；最像的「别的东西」也只有 0.30"
    an.unmatched([w])
    out = capsys.readouterr().out
    assert "查无此篇" in out and "0.30" in out and "未匹配到产物（1/1 条）" in out


def test_全部对上时也要明确说出来(capsys):
    w = _work("🎾某条")
    w.item = _item("🎾某条", date(2026, 7, 26))
    an.unmatched([w])
    assert "全部对上了" in capsys.readouterr().out


def test_相关性剔除刚发的并说明剔了几条(capsys):
    """刚发的播放量天然低，混进去会把系数压平——实测 +0.46 vs +0.77。"""
    dy = _plat("抖音")
    works = [_work(f"老{i}", datetime(2026, 7, 20 + i, 3, 0), platform=dy,
                   plays=1000 + i * 100, retain_5s=0.3 + i * 0.02,
                   bounce_2s=0.3, true_completion=0.02, avg_watch=20.0,
                   cover_ctr=0.1, likes=1, follows=0) for i in range(6)]
    works.append(_work("刚发的", datetime(2026, 7, 27, 14, 47), platform=dy,
                       plays=42, retain_5s=0.52, bounce_2s=0.25,
                       true_completion=0.0, avg_watch=20.0, cover_ctr=0.1,
                       likes=0, follows=0))
    an.correlations(works, fresh_hours=24)
    out = capsys.readouterr().out
    assert "剔除最近 24 小时发布的 1 条" in out
    assert "循环成分" in out          # 算法用留存决定播放，这个警告不能省


def test_相关性样本太少时不出数(capsys):
    dy = _plat("抖音")
    works = [_work(f"甲{i}", datetime(2026, 7, 20 + i, 3, 0), platform=dy,
                   plays=100) for i in range(3)]
    an.correlations(works, fresh_hours=24)
    assert "不够算" in capsys.readouterr().out


def test_横比只报事实不给某平台更好的结论(capsys):
    """8 条共同内容里抖音赢 4、视频号赢 2、小红书赢 2，连排序都不一样：
    「大师赛为什么变两周」抖音第一 3066、视频号垫底 216。
    """
    xhs, dy, wx = _plat("小红书"), _plat("抖音"), _plat("视频号")
    def mk(plat, title, plays):
        w = _work(title, platform=plat, plays=plays, follows=0)
        w.item = _item(title, date(2026, 7, 26))
        return w
    an.cross_platform([
        # 甲＝大师赛变两周：抖音第一 3066，视频号垫底 216
        # 乙＝商竣程首轮：小红书第一 416，抖音垫底 42
        ("小红书", [mk(xhs, "甲", 1828), mk(xhs, "乙", 416)]),
        ("抖音", [mk(dy, "甲", 3066), mk(dy, "乙", 42)]),
        ("视频号", [mk(wx, "甲", 216), mk(wx, "乙", 288)]),
    ])
    out = capsys.readouterr().out
    assert "14倍" in out                      # 甲：3066 / 216
    assert "10倍" in out                      # 乙：416 / 42
    assert "各家拿第一的条数" in out
    # 排序不一样才是重点：同一批内容，两条的冠军不是同一家
    assert "没有一家是稳定更好的" in out


def test_一家通吃时就不说没有一家更好(capsys):
    """反过来也要对：真的是同一家全赢，那句话就不该印出来。"""
    xhs, dy = _plat("小红书"), _plat("抖音")
    def mk(plat, title, plays):
        w = _work(title, platform=plat, plays=plays, follows=0)
        w.item = _item(title, date(2026, 7, 26))
        return w
    an.cross_platform([
        ("小红书", [mk(xhs, "甲", 100), mk(xhs, "乙", 100)]),
        ("抖音", [mk(dy, "甲", 900), mk(dy, "乙", 900)]),
    ])
    assert "没有一家是稳定更好的" not in capsys.readouterr().out


def test_没有共同内容时说清楚为什么横比不了(capsys):
    xhs, dy = _plat("小红书"), _plat("抖音")
    a = _work("甲", platform=xhs, plays=1)
    a.item = _item("甲", date(2026, 7, 26))
    b = _work("乙", platform=dy, plays=1)
    b.item = _item("乙", date(2026, 7, 26))
    an.cross_platform([("小红书", [a]), ("抖音", [b])])
    out = capsys.readouterr().out
    assert "横比不了" in out and "未匹配" in out


def test_只有一个平台时不出横比(capsys):
    an.cross_platform([("小红书", [_work("甲")])])
    assert capsys.readouterr().out == ""


def test_中文列宽按两格算否则表格永远不齐():
    out = ps.table([["温网屋顶", "1"], ["a", "22"]], ["标题", "数"])
    lines = out.splitlines()
    assert len(lines) == 4
    assert len({ps.width(ln) for ln in lines}) == 1


def test_抖音的视频数据视图能认出来():
    """抖音后台还有一个只导 6 列的视图，标题列叫「视频名称」不是「作品名称」。

    它没有真完播率、点赞、涨粉、体裁。认不出来时工具应当明确拒绝（见
    `test_认不出平台时要说清已知哪几家`），认出来之后不能把缺的列当 0。
    """
    head = ["视频名称", "发布时间", "播放量", "5s完播率", "2s跳出率", "平均播放时长"]
    plat, at = ps.detect([head])
    assert plat.name == "抖音·视频数据" and at == 0
    assert plat.has("retain_5s") and plat.has("bounce_2s")
    for absent in ("true_completion", "likes", "follows", "cover_ctr"):
        assert not plat.has(absent), f"这个视图不该有 {absent}"
    assert plat.kind_col is None            # 没有体裁列 → 一律当视频


def test_平台不给的指标不许印成零(capsys):
    """踩过：这个视图没有点赞和涨粉，overview 无条件打印会印成「互动 0　涨粉 0」
    ——和「真的没人互动」长得一模一样，正是这个工具处处在防的假空值。
    """
    dy2 = _plat("抖音·视频数据")
    an.overview([_work("🎾某条", platform=dy2, plays=1000, avg_watch=20.0,
                       retain_5s=0.4, bounce_2s=0.33)])
    out = capsys.readouterr().out
    assert "播放 1000" in out
    assert "涨粉 0" not in out and "互动 0" not in out
    assert "不给" in out and "空着，不是 0" in out


def test_没有真完播率时漏斗末行留空而不是印零(capsys):
    dy2 = _plat("抖音·视频数据")
    an.funnel([_work(f"🎾第{i}条", platform=dy2, plays=1000, avg_watch=20.0,
                     retain_5s=0.35, bounce_2s=0.37) for i in range(3)])
    out = capsys.readouterr().out
    assert "看到结尾     0 人" not in out and "看到结尾   0 人" not in out
    assert "这一格空着" in out


def test_平台不给的因变量不出相关性那一栏(capsys):
    """照样算会得出全是 +0.00，看着像「留存和涨粉毫无关系」这个实打实的结论。"""
    from datetime import datetime
    dy2 = _plat("抖音·视频数据")
    works = [_work(f"第{i}条", datetime(2026, 7, 20 + i, 3, 0), platform=dy2,
                   plays=1000 + i * 100, retain_5s=0.3 + i * 0.02,
                   bounce_2s=0.3, avg_watch=20.0) for i in range(6)]
    an.correlations(works, fresh_hours=24)
    out = capsys.readouterr().out
    assert "vs 播放" in out
    assert "vs 涨粉" not in out and "vs 互动" not in out


def test_横比表里平台不给的涨粉不许印成零(capsys):
    """第四处同类的假零值：抖音的「视频数据」视图没有涨粉列，横比表照样印
    「0 / 0.00」，看着像「这个平台一个粉都没涨」。
    """
    xhs, dy2 = _plat("小红书"), _plat("抖音·视频数据")
    def mk(plat, title, plays, **kw):
        w = _work(title, platform=plat, plays=plays, **kw)
        w.item = _item(title, date(2026, 7, 26))
        return w
    an.cross_platform([
        ("小红书", [mk(xhs, "甲", 1000, follows=5), mk(xhs, "乙", 800, follows=3)]),
        ("抖音·视频数据", [mk(dy2, "甲", 3000), mk(dy2, "乙", 2000)]),
    ])
    out = capsys.readouterr().out
    assert "不给" in out
    assert "0.00" not in out
