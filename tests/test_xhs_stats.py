"""`tools/analyze_xhs_stats.py` 的判据。

这个脚本的价值全在「别被表面数字骗了」上，所以测的也是那几个坑本身：
曝光列对视频是残缺的、标题发文时会被改、名字相近的两条不能混。
"""

from __future__ import annotations

import importlib.util
import sys
import zipfile
from datetime import date, datetime
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"
_spec = importlib.util.spec_from_file_location(
    "analyze_xhs_stats", _TOOLS / "analyze_xhs_stats.py"
)
xhs = importlib.util.module_from_spec(_spec)
sys.modules["analyze_xhs_stats"] = xhs
_spec.loader.exec_module(xhs)


_NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'


def _write_xlsx(path: Path, rows: list[list[str]]) -> Path:
    """搭一个最小的 xlsx —— 全部走共享字符串，和小红书导出的一样。"""
    shared: list[str] = []
    for row in rows:
        for cell in row:
            if cell not in shared:
                shared.append(cell)
    sst = f"<sst {_NS} count=\"{len(shared)}\" uniqueCount=\"{len(shared)}\">" + "".join(
        f"<si><t>{s}</t></si>" for s in shared
    ) + "</sst>"
    body = []
    for r, row in enumerate(rows, start=1):
        cells = "".join(
            f'<c r="{chr(64 + c)}{r}" t="s"><v>{shared.index(v)}</v></c>'
            for c, v in enumerate(row, start=1)
        )
        body.append(f'<row r="{r}">{cells}</row>')
    sheet = f"<worksheet {_NS}><sheetData>{''.join(body)}</sheetData></worksheet>"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/sharedStrings.xml", sst)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return path


_HEADER = ["笔记标题", "首次发布时间", "体裁", "曝光", "观看量", "封面点击率",
           "点赞", "评论", "收藏", "涨粉", "分享", "人均观看时长", "弹幕"]


def _note(title, when, kind, exposure, views, ctr, likes=0, fans=0, watched=0):
    return [title, when, kind, str(exposure), str(views), str(ctr),
            str(likes), "0", "0", str(fans), "0", str(watched), "0"]


def _item(title, day, mp4=None):
    return {"title": title, "norm": xhs.normalize(title), "dir": Path("x"),
            "date": day, "mp4": mp4}


def test_表头自己找而不是写死在第几行(tmp_path):
    """导出的表第一行是铺满整行的水印，表头在第二行。

    写死行号的话，哪天导出格式变一下就整体错位，而且不会报错——读出来的
    「标题」会是一串数字，看起来只是「数据怪怪的」。
    """
    xlsx = _write_xlsx(tmp_path / "a.xlsx", [
        ["最多导出排序后前1000条笔记"] * 13,
        _HEADER,
        _note("🎾测试笔记", "2026年07月26日14时05分22秒", "视频", 1000, 200, 0.2),
    ])
    notes = xhs.load_notes(xlsx)
    assert len(notes) == 1
    assert notes[0]["笔记标题"] == "🎾测试笔记"
    assert notes[0]["观看量"] == 200
    assert notes[0]["_time"] == datetime(2026, 7, 26, 14, 5)


def test_水印行数变了也仍然能找到表头(tmp_path):
    xlsx = _write_xlsx(tmp_path / "b.xlsx", [
        ["说明"], ["又一行说明"], ["再一行"],
        _HEADER,
        _note("🎾另一条", "2026年07月26日01时14分09秒", "图文", 500, 50, 0.1),
    ])
    assert xhs.load_notes(xlsx)[0]["笔记标题"] == "🎾另一条"


def test_曝光一致性自检认得出视频那一列是残缺的(tmp_path, capsys):
    """图文的 观看/曝光 等于 CTR，视频的远高于 CTR——这不是噪声，是两种分发。

    第一次看这张表时差点据此得出「图文分发更好」：图文曝光 24512 比视频的
    18184 高。其实视频有一路沉浸式自动播放的观看根本不计入曝光列。
    """
    notes = xhs.load_notes(_write_xlsx(tmp_path / "exposure.xlsx", [
        _HEADER,
        # 图文：200/2000 = 0.10，和 CTR 对得上
        _note("图文甲", "2026年07月21日21时35分35秒", "图文", 2000, 200, 0.10),
        _note("图文乙", "2026年07月22日17时45分48秒", "图文", 1000, 105, 0.10),
        # 视频：1000/2000 = 0.50，CTR 只有 0.12
        _note("视频甲", "2026年07月26日03时33分18秒", "视频", 2000, 1000, 0.12),
        _note("视频乙", "2026年07月26日18时55分45秒", "视频", 1000, 400, 0.10),
    ]))
    verdicts = xhs.report_exposure_check(notes)
    assert verdicts["图文"]["一致"] is True
    assert verdicts["视频"]["一致"] is False
    # 还原曝光要按 观看÷CTR 算，不是把记录值抄一遍
    assert verdicts["视频"]["还原曝光"] > verdicts["视频"]["记录曝光"] * 2
    assert verdicts["图文"]["还原曝光"] == pytest.approx(
        verdicts["图文"]["记录曝光"], rel=0.05)
    # 对不上的必须喊出来，不能只记在返回值里
    assert "曝光列是残缺的" in capsys.readouterr().out


def test_发文时改过标题的笔记仍然对得上产物():
    """生成 `🎾7.26 网球有故事｜网球为什么是黄色的`，发出去时砍成了
    `🎾7.26｜网球为什么是黄色的`。精确匹配不上，但这是同一条。
    """
    note = {"笔记标题": "🎾7.26｜网球为什么是黄色的",
            "_time": datetime(2026, 7, 26, 1, 14)}
    items = [
        _item("🎾7.26 网球有故事｜网球为什么是黄色的", date(2026, 7, 26)),
        _item("🎾7.26 网球有故事｜温网屋顶谁说了算", date(2026, 7, 26)),
    ]
    hit, why = xhs.match_note(note, items, xhs.MIN_RATIO)
    assert hit is not None, why
    assert hit["title"] == "🎾7.26 网球有故事｜网球为什么是黄色的"
    assert why.startswith("模糊")


def test_名字相近的两条不会被错配():
    """`巴尔迪科娃先丢一盘` 和 `巴尔通科娃逆转晋级` 长得像，讲的不是一回事。

    模糊匹配一放松就会把这两条粘在一起，然后比例算到别人头上——错配比
    不匹配糟得多，因为它不会出现在「未匹配」一节里，没人会去查。
    """
    note = {"笔记标题": "🎾7.22网球快报｜巴尔迪科娃先丢一盘",
            "_time": datetime(2026, 7, 22, 10, 1)}
    items = [_item("🎾7.22今日球局｜巴尔通科娃逆转晋级", date(2026, 7, 22))]
    hit, why = xhs.match_note(note, items, xhs.MIN_RATIO)
    assert hit is None
    assert "低于" in why


def test_对不上的要报出原因而不是静默丢掉(capsys):
    """只在成功时出声的检查，没法证明它真的看过。"""
    note = {"笔记标题": "查无此篇", "体裁": "图文", "_time": None}
    xhs.report_unmatched([(note, "最像的也只有 0.30（别的东西），低于 0.75")])
    out = capsys.readouterr().out
    assert "查无此篇" in out
    assert "0.30" in out          # 差多少要说出来
    assert "未匹配到产物（1 条）" in out


def test_未匹配为零时也要明确说出来(capsys):
    xhs.report_unmatched([])
    assert "全部对上了" in capsys.readouterr().out


def test_日期差太远的不算命中():
    """标题一模一样但隔了半个月，多半是重跑的旧目录，不是这一条。"""
    note = {"笔记标题": "🎾同名笔记", "_time": datetime(2026, 7, 26, 12, 0)}
    items = [_item("🎾同名笔记甲", date(2026, 7, 1))]
    hit, why = xhs.match_note(note, items, 0.5)
    assert hit is None
    assert "日期差" in why


def test_同名多份按发布日期取最近的那份():
    """同一个选题重跑过几次，output/ 下会留好几份，标题一字不差。"""
    note = {"笔记标题": "🎾7.26｜鹰眼", "_time": datetime(2026, 7, 26, 23, 37)}
    items = [_item("🎾7.26｜鹰眼", date(2026, 7, 20)),
             _item("🎾7.26｜鹰眼", date(2026, 7, 26))]
    hit, why = xhs.match_note(note, items, xhs.MIN_RATIO)
    assert hit is not None and hit["date"] == date(2026, 7, 26)
    assert "同名多份" in why


def test_均观看比例按成片时长算不按估计(tmp_path, capsys):
    """人均观看 46 秒，片长 140 秒是 33%，片长 60 秒就是 77%——差别是全部。

    所以片长必须来自成片本身。这里塞一个真的 mp4 进去量。
    """
    real = next((_TOOLS.parents[0] / "output").rglob("*.mp4"), None)
    if real is None:
        pytest.skip("output/ 下没有成片可量")
    length = xhs.mvhd_seconds(real.read_bytes())
    note = {"笔记标题": "🎾某条", "人均观看时长": length / 4,
            "观看量": 1000, "涨粉": 3}
    records = xhs.report_completion([(note, _item("🎾某条", date(2026, 7, 26), real), "精确")])
    assert len(records) == 1
    assert records[0]["均观看比例"] == pytest.approx(0.25, abs=0.01)
    assert records[0]["片长"] == pytest.approx(length, abs=0.1)
    assert "25%" in capsys.readouterr().out


def test_没有成片的笔记不进均观看比例而不是记成零(capsys):
    """图文没有 mp4。把它当成「均观看比例 0」会把中位数整个拉垮。"""
    note = {"笔记标题": "📖图文一篇", "人均观看时长": 25, "观看量": 500, "涨粉": 1}
    records = xhs.report_completion([(note, _item("📖图文一篇", date(2026, 7, 24)), "精确")])
    assert records == []
    # 而且要说清楚是「没对上成片」，别让人以为真的没有视频
    assert "别当成没有视频" in capsys.readouterr().out


def test_normalize只留下用来比对的字():
    """emoji、`｜`、空格全是装饰，去掉之后剩下的才是内容。"""
    assert xhs.normalize("🎾7.26 网球有故事｜温网屋顶谁说了算") == "726网球有故事温网屋顶谁说了算"
    assert xhs.normalize("💥7.24今日球局｜爆冷：托雷斯掀翻塔比洛") == \
        "724今日球局爆冷托雷斯掀翻塔比洛"


def test_中文列宽按两格算否则表格永远不齐():
    out = xhs._table([["温网屋顶", "1"], ["a", "22"]], ["标题", "数"])
    lines = out.splitlines()
    # 表头、分隔线、两行数据
    assert len(lines) == 4
    # 每一行的显示宽度要一样
    import unicodedata

    def width(s):
        return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)

    assert len({width(ln) for ln in lines}) == 1
