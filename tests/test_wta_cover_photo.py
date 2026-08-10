"""封面实拍抓取（fetch_wta_cover_photo）：判据全在挑选和自证上。

抓错文章 = 把别人那场的头图当封面发出去，而它看起来完全正常——
所以挑文章和自证的判据必须钉死。链路本身 2026-08-09 拿真实比赛
（多伦多 806/LS008，亚历山德罗娃 vs 萨巴伦卡）端到端跑通过，
细节在工具 docstring。
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from fetch_wta_cover_photo import (  # noqa: E402
    filename_certifies,
    og_image,
    photo_date_off,
    pick_article,
)


def test_挑文章按姓氏命中数_零命中不许凑():
    links = [
        "/news/1/gauff-withstands-late-push",
        "/news/2/alexandrova-cracks-the-sabalenka-code-again",
        "/news/3/eala-extends-win-streak",
    ]
    got = pick_article(links, ["alexandrova", "sabalenka"])
    assert got == "/news/2/alexandrova-cracks-the-sabalenka-code-again", \
        "两个姓氏都命中的要赢过只命中一个的"
    # 比赛页上挂着别场的稿子——零命中必须返回 None，不许退而求其次
    assert pick_article(links, ["zheng", "osaka"]) is None


def test_og_image两种属性顺序都认而且去掉缩图参数():
    a = '<meta property="og:image" content="https://x/p.jpg?width=160">'
    b = '<meta content="https://x/p.jpg" property="og:image">'
    assert og_image(a) == "https://x/p.jpg", "缩图参数要去掉，要的是原图"
    assert og_image(b) == "https://x/p.jpg"
    assert og_image("<html></html>") is None


def test_文件名自证认下划线和大小写_编号名不自证():
    url = ("https://photoresources.wtatennis.com/wta/photo/2026/08/09/x/"
           "Ekaterina_Alexandrova_-_National_Bank_Open_2026_-_Day_7-DSC.jpg")
    assert filename_certifies(url, ["alexandrova"])
    assert not filename_certifies(
        "https://x/GettyImages-2288643508.jpg", ["alexandrova"]), \
        "Getty 编号名不自证——工具要提示人打开看一眼"


def test_资料图预警按路径日期和比赛日差():
    url = "https://photoresources.wtatennis.com/wta/photo/2026/08/09/x/p.jpg"
    assert photo_date_off(url, date(2026, 8, 9)) == 0
    assert photo_date_off(url, date(2026, 8, 3)) == 6, "差 6 天该触发资料图预警"
    assert photo_date_off("https://x/p.jpg", date(2026, 8, 9)) is None, \
        "解析不出日期就不判，别硬猜"


def test_给了两个姓氏就必须两个都命中_单命中不许顶():
    """2026-08-10 踩的：LS012 赛后稿未挂，单命中把 8/4 双打预告旧稿挑回来，
    头图是 Bad Homburg 资料图。单命中要返回 None 走重试，别拿别的稿子顶。"""
    links = [
        "/news/1/alex-eala-venus-williams-to-team-up-for-toronto-doubles",
        "/news/2/gauff-withstands-late-push",
    ]
    assert pick_article(links, ["eala", "bencic"]) is None, \
        "只命中 eala 的双打旧稿不许当这场球的赛后稿"
    # 单姓氏调用（1 个就是全命中）不受影响
    assert pick_article(links, ["gauff"]) == "/news/2/gauff-withstands-late-push"
