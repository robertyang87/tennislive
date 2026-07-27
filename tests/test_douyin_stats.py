"""`tools/analyze_douyin_stats.py` 的判据。

抖音这份数据的价值在那三列留存（2s跳出率 / 5s完播率 / 真完播率），坑在
「作品名称」里装的是标题加整段正文。所以测的是：标题怎么认出来、认不出来
时怎么老实认输、以及图文和视频的完播率不能混在一起算。
"""

from __future__ import annotations

import importlib.util
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


_load("analyze_xhs_stats")          # analyze_douyin_stats 从它 import
dy = _load("analyze_douyin_stats")

_NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
_HEADER = ["作品名称", "发布时间", "体裁", "审核状态", "播放量", "完播率",
           "5s完播率", "封面点击率", "2s跳出率", "平均播放时长", "点赞量",
           "分享量", "评论量", "收藏量", "主页访问量", "粉丝增量"]


def _write_xlsx(path: Path, rows: list[list[str]]) -> Path:
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


def _work(name, when, kind="1-3min视频", plays=1000, fin=0.02, s5=0.40,
          b2=0.33, avg=20.0, likes=1, home=0, fans=0):
    return [name, when, kind, "公开", str(plays), str(fin), str(s5), "-",
            str(b2), str(avg), str(likes), "0", "0", "0", str(home), str(fans)]


def _item(title, day, mp4=None):
    import analyze_xhs_stats as xhs
    return {"title": title, "norm": xhs.normalize(title), "dir": Path("x"),
            "date": day, "mp4": mp4}


# ------------------------------------------------------------- 标题识别


def test_作品名称是标题接正文所以按前缀自证():
    """抖音导出的「作品名称」= 标题 + 空格 + 整段正文（换行都在里面）。

    切字符串要猜标题在第几个空格处结束，猜错就整条错。前缀自证不用猜：
    去掉装饰之后，它必然以那条内容的标题开头。
    """
    work = {"_norm": dy.normalize("🎾7.26 网球有故事｜温网屋顶谁说了算 "
                                  "温网中央球场的屋顶，规则只写了两种情况可以关"),
            "_首行": "x", "_time": datetime(2026, 7, 26, 13, 31)}
    items = [_item("🎾7.26 网球有故事｜温网屋顶谁说了算", date(2026, 7, 26)),
             _item("🎾7.26 网球有故事｜大师赛为什么变两周", date(2026, 7, 26))]
    hit, why = dy.match_work(work, items)
    assert hit["title"] == "🎾7.26 网球有故事｜温网屋顶谁说了算"
    assert why.startswith("前缀自证")


def test_前缀命中多个时取最长的那个():
    """`网球有故事｜11 小时 5 分钟` 比 `网球有故事｜11` 更具体，要取长的。"""
    work = {"_norm": dy.normalize("🎾7.26 网球有故事｜11 小时 5 分钟 正文正文"),
            "_首行": "x", "_time": datetime(2026, 7, 26, 1, 37)}
    items = [_item("🎾7.26 网球有故事｜11", date(2026, 7, 26)),
             _item("🎾7.26 网球有故事｜11 小时 5 分钟", date(2026, 7, 26))]
    hit, _ = dy.match_work(work, items)
    assert hit["title"] == "🎾7.26 网球有故事｜11 小时 5 分钟"


def test_模糊回退比同样长度的前缀而不是整条首行():
    """踩过：拿整条首行（标题+正文开头）去比，长度差十几倍，相似度必然被
    拉到 0.5 上下——好的候选和坏的候选一起沉底，看起来像「真的不像」。

    `网球为什么是黄色的` 发文时砍掉了「网球有故事」：按整条首行比是 0.52，
    按同长度前缀比是 0.71，收得住。
    """
    work = {"_norm": dy.normalize("🎾7.26｜网球为什么是黄色的 "
                                  "网球是黄色的，这件事其实还不到六十年。"),
            "_首行": "🎾7.26｜网球为什么是黄色的 网球是黄色的，这件事其实还不到六十年。",
            "_time": datetime(2026, 7, 26, 1, 7)}
    items = [_item("🎾7.26 网球有故事｜网球为什么是黄色的", date(2026, 7, 26)),
             _item("🎾7.26 网球有故事｜发球前为什么要挑球", date(2026, 7, 26)),
             _item("🎾7.26 网球有故事｜温网为什么只准穿白", date(2026, 7, 26))]
    hit, why = dy.match_work(work, items)
    assert hit is not None, why
    assert hit["title"] == "🎾7.26 网球有故事｜网球为什么是黄色的"


def test_同一选题多版并列时按发布日期分():
    """金满贯重跑过两版（7.22 和 7.25），分数 0.81 / 0.75 挤在一起。

    这种「谁都像」不能按分数排先后——发布那天的那一版才是它。
    """
    work = {"_norm": dy.normalize("📖7.22网球故事｜金满贯到底难在哪？"
                                  "1988年，格拉芙先拿下澳网、法网"),
            "_首行": "📖7.22网球故事｜金满贯到底难在哪？",
            "_time": datetime(2026, 7, 22, 17, 45)}
    items = [_item("📖7.25网球有故事｜金满贯到底有多难？", date(2026, 7, 25)),
             _item("📖7.22网球有故事｜金满贯到底有多难？", date(2026, 7, 22))]
    hit, why = dy.match_work(work, items)
    assert hit is not None, why
    assert hit["date"] == date(2026, 7, 22)


def test_真分不出的要老实认输而不是挑第一个():
    """三巨头那条：三个候选并列 0.50，日期也分不出。

    随手挑第一个会把数据算到别人头上，而且**不会出现在未匹配一节里**，
    没人会去查——错配比不匹配糟得多。
    """
    work = {"_norm": dy.normalize("📖7.24网球有故事｜三巨头。⏳ 66座大满贯"),
            "_首行": "📖7.24网球有故事｜三巨头。⏳",
            "_time": datetime(2026, 7, 24, 13, 30)}
    items = [_item("📖7.24网球有故事｜11 小时 5 分钟的故事", date(2026, 7, 24)),
             _item("📖7.22网球有故事｜金满贯到底有多难？", date(2026, 7, 22))]
    hit, why = dy.match_work(work, items)
    assert hit is None
    # 原因要说清是「哪一种」分不出，好让人回去查，不能只说一句「没匹配」
    assert any(k in why for k in ("只有", "拉不开", "分不出"))


def test_日期差太远的不算命中():
    work = {"_norm": dy.normalize("🎾同名作品 正文"), "_首行": "🎾同名作品",
            "_time": datetime(2026, 7, 26, 12, 0)}
    items = [_item("🎾同名作品甲", date(2026, 5, 1))]
    hit, why = dy.match_work(work, items)
    assert hit is None
    assert "日期差" in why or "只有" in why


# --------------------------------------------------------------- 报告


def test_图文和视频的完播率必须分开算(tmp_path, capsys):
    """图文的「完播」是翻完几张图，门槛低得多（真实数据 13.6%～24.2%，
    视频只有 0%～9.9%）。混在一起算中位会得出「完播率还不错」的假象。
    """
    works = dy.load_works(_write_xlsx(tmp_path / "a.xlsx", [
        _HEADER,
        _work("视频甲 正文", "2026-07-26 03:33:18", fin=0.02, plays=1000),
        _work("视频乙 正文", "2026-07-26 04:40:00", fin=0.03, plays=1000),
        _work("图文甲 正文", "2026-07-24 13:30:48", kind="图文", fin=0.21,
              plays=10000, home=132, fans=4),
    ]))
    dy.report_by_kind(works)
    out = capsys.readouterr().out
    assert "图文" in out and "视频" in out
    # 图文那行的完播率中位是 21.4%，视频那行是 2.5%——不能只出一个合并数
    assert "21.0%" in out or "21.4%" in out
    assert "不可比" in out


def test_漏斗只算视频(tmp_path, capsys):
    """图文没有「第 2 秒」这回事。"""
    works = dy.load_works(_write_xlsx(tmp_path / "b.xlsx", [
        _HEADER,
        _work("视频甲 正文", "2026-07-26 03:33:18", b2=0.34, s5=0.40),
        _work("图文甲 正文", "2026-07-24 13:30:48", kind="图文"),
    ]))
    recs = dy.report_funnel(works)
    assert len(recs) == 1
    assert "1 条" in capsys.readouterr().out


def test_没有留存列时要说清楚不是没有数据(capsys):
    """空结果先自证是真空：导出时没勾那几列，和「这些片子没人看」长得一样。"""
    dy.report_funnel([{"_图文": False, "2s跳出率": None, "5s完播率": None,
                       "_标题": "x", "_互动": 0}])
    assert "别当成没有数据" in capsys.readouterr().out


def test_相关性样本太少时不出数(tmp_path, capsys):
    """三个点也能算出相关系数，但那个数没有意义。宁可不出。"""
    works = dy.load_works(_write_xlsx(tmp_path / "c.xlsx", [
        _HEADER,
        _work("视频甲 正文", "2026-07-20 03:33:18"),
        _work("视频乙 正文", "2026-07-21 04:40:00"),
        _work("视频丙 正文", "2026-07-26 04:40:00"),
    ]))
    dy.report_correlations(works, fresh_hours=24)
    assert "不够算" in capsys.readouterr().out


def test_相关性要剔除刚发的并说明剔了几条(tmp_path, capsys):
    """刚发的播放量天然低，混进去会把系数压平——实测 +0.46 vs +0.77。"""
    rows = [_HEADER]
    for i in range(6):
        rows.append(_work(f"老视频{i} 正文", f"2026-07-2{i} 03:00:00",
                          plays=1000 + i * 100, s5=0.3 + i * 0.02))
    rows.append(_work("刚发的 正文", "2026-07-27 14:47:18", plays=42, s5=0.52))
    works = dy.load_works(_write_xlsx(tmp_path / "d.xlsx", rows))
    dy.report_correlations(works, fresh_hours=24)
    out = capsys.readouterr().out
    assert "剔除 1 条" in out
    assert "循环成分" in out       # 算法用留存决定播放，这个警告不能省


def test_流失速度三段加起来要对得上(tmp_path, capsys, monkeypatch):
    """踩过：一边取「跳出率的中位」、一边取「存活率的中位」，两个中位数
    不互补，三段加起来对不上一百，表格自己和自己打架。

    这里让 `index_output` 返回一个指向真成片的候选，把整节跑起来再验算。
    """
    real = next((_TOOLS.parents[0] / "output").rglob("*.mp4"), None)
    if real is None:
        pytest.skip("output/ 下没有成片可量")
    works = dy.load_works(_write_xlsx(tmp_path / "e.xlsx", [
        _HEADER,
        _work("🎾某条 正文正文", "2026-07-26 03:33:18", b2=0.40, s5=0.30, fin=0.02),
    ]))
    monkeypatch.setattr(dy, "index_output",
                        lambda root: [_item("🎾某条", date(2026, 7, 26), real)])
    dy.report_rates(works, [], tmp_path)
    out = capsys.readouterr().out
    assert "没对上成片" not in out

    # 每行末尾三列固定是「走掉 / 秒数 / 人每秒」，标签本身带空格，从后往前取
    lost = [int(ln.split()[-3]) for ln in out.splitlines()
            if ln.startswith(("0–2 秒", "2–5 秒", "5 秒–片尾"))]
    assert len(lost) == 3
    # 走掉的三段 + 看到结尾的 2 人 = 100
    assert sum(lost) + 2 == 100


def test_导出里的横杠读成缺失而不是零():
    """封面点击率那列拿不到时写的是 `-`。当成 0 会把中位数拖垮。"""
    assert dy._to_num("-") is None
    assert dy._to_num("") is None
    assert dy._to_num("0.25") == 0.25


def test_发布时间几种写法都认得():
    assert dy._parse_time("2026-07-27 14:47:18") == datetime(2026, 7, 27, 14, 47, 18)
    assert dy._parse_time("2026-07-27 14:47") == datetime(2026, 7, 27, 14, 47)
    assert dy._parse_time("看不懂") is None
