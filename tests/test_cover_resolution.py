"""封面图的分辨率门槛。

封面推近会把压缩噪点和插值一起放大，所以「现在看着还行」不等于「推了还行」。
这条要求是在做推近样片时冒出来的：先量清楚哪几张经不起推，再决定哪几条片子
能用动效、哪几条只能保持静止。

两道线：

    1.00x   铺满卡片，一个像素都不放大 —— 所有封面图都该过这条，和动不动无关
    1.08x   还留得出推近 8% 的余量 —— 过不了的只能用静止封面，不算错

基准是**成片里的卡片 1080×1440**，不是截图的 2160×2880。见
`test_基准是成片里的卡片不是二倍截图`——第一次量就错在这里。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


chk = _load("check_cover_resolution")

from tennislive.video.explainer import _SCRIPTS  # noqa: E402

# 现在就在放大的三张，只许变大不许变小。换了更大的原图就从这里删掉。
# 值是当前的铺满倍数，留 0.02 的容差给不同 Pillow 版本的读取差异。
_UNDERSIZED = {
    "rufus": 0.83,             # 1600x1200
    "lucky-loser": 0.85,       # 914x1219，见下
    "wimbledon-whites": 0.87,  # 937x1250，全套最小
    "shang-nishikori": 0.95,   # 1023x1365
}
# lucky-loser 为什么只能用这张：封面是卢布列夫 2017 乌马格捧杯，而**干净原图
# 四条路全走完都取不到**（Commons 三种查询词加分类搜索全 0、乌马格官网 2017 的
# 文章页和图集页在两个镜像上都 404、ATP 总站 403、Wayback 整站对本环境 403、
# Getty 付费）。现在这张是账号所有者从卢布列夫本人社媒截的，1179 宽，无论怎么
# 裁都到不了 1080x1440。
#
# 一度改成**垫成 3:4**（1179x1572）绕开这条，能 1.09x 铺满——但账号所有者定了
# 「封面不要虚化」，垫层就是虚化的。所以退回裁切：914x1219，0.85x，放大 18%。
# 这是**用分辨率换掉虚化**，一个明写的取舍，不是回归。
#
# 裁哪一边也是渲出来比的：保住奖杯右缘（x≈1040）的窗口都够不到摄影署名的右端
# （x≈1169），所以「保全署名、左肩收在画框边」和「人完整、署名切一半」二选一。
# 选了前者——**残的署名比没有更糟**。
# 详见 assets/explainer/lucky-loser/credits.json。


def _fill(slug: str) -> float:
    path = chk.cover_image(slug)
    assert path is not None, f"{slug} 找不到封面图"
    return chk.fill_factor(path)


@pytest.mark.parametrize("slug", sorted(_SCRIPTS))
def test_封面图不许被放大(slug):
    """原图比显示区域小，等于一上来就在插值。这和推不推近无关，是底线。"""
    got = _fill(slug)
    if slug in _UNDERSIZED:
        was = _UNDERSIZED[slug]
        assert got >= was - 0.02, (
            f"{slug} 的封面图从 {was:.2f}x 变小到 {got:.2f}x——名单里的只许变大。")
        return
    assert got >= chk.FLOOR, (
        f"{slug} 的封面图只有 {got:.2f}x，铺满卡片就得放大 {1 / got:.0%}。\n"
        f"换一张至少 {chk.CARD_W}x{chk.CARD_H} 的原图，"
        f"或者把它加进 _UNDERSIZED 并说明为什么只能用这张。")


def test_不合格名单只能变短():
    """换了大图就要把它从名单里删掉，否则名单会留着一个假的下限。"""
    fixed = {s: v for s, v in _UNDERSIZED.items()
             if s in _SCRIPTS and _fill(s) >= chk.FLOOR}
    assert not fixed, (
        f"{'、'.join(fixed)} 已经够铺满了，从 _UNDERSIZED 里删掉——名单只该变短。")


def test_不合格名单里不许有不存在的片子():
    ghosts = set(_UNDERSIZED) - set(_SCRIPTS)
    assert not ghosts, f"_UNDERSIZED 里这些片子不存在了：{'、'.join(sorted(ghosts))}"


def test_基准是成片里的卡片不是二倍截图():
    """第一次量就错在这里，差点判定整批素材不合格。

    卡片用 `device_scale_factor=2` 截图（2160×2880），但那是**为了文字锐利**；
    成片里卡片只占 1080×1440。拿 2 倍图当基准，14 张里 13 张都会被判成「在
    放大」——一个全红的结论，正好是最容易让人放弃这条检查的那种。
    """
    assert (chk.CARD_W, chk.CARD_H) == (1080, 1440)
    # 反过来验：按 2 倍图算的话，绝大多数都会跌破底线——说明基准选错会全红
    doubled = sum(1 for s in _SCRIPTS if _fill(s) / 2 >= chk.FLOOR)
    # 上限按**比例**写，不写死个数。原来是 `<= 1`，那个 1 是按当时 15 条片子
    # 标出来的；thiem-football 的封面是 4103x3336 的捧杯原图（铺满倍数 2.32），
    # 一加进来就变成 2 条，测试红了——而它红的不是「基准选错了」，是
    # 「有人换了张特别大的图」。硬编码的计数会把「素材变好」误报成回归，
    # 于是下一个人要么去改判据、要么去换一张更小的图，两条路都错。
    # 两成这条线仍然把反例撑得住：多数不合格才说明基准选错会全红。
    assert doubled * 5 <= len(_SCRIPTS), (
        f"按 2 倍图当基准时仍有 {doubled}/{len(_SCRIPTS)} 条合格，超过两成——"
        "这个反例撑不住了，回去确认基准是不是真的该用 1080x1440。")


def test_能推近的片子是算出来的不是手写的():
    """哪几条能用推近，由分辨率决定，不该另维护一张名单——两处一旦不同步，
    就会给一张经不起推的图加上动效，而且没人会发现。
    """
    eligible = [s for s in sorted(_SCRIPTS) if _fill(s) / chk.PUSH >= chk.FLOOR]
    # 当前这批：不够推的有 7 条（4 张本来就在放大 + 3 张够铺满推不动）。
    # 加选题会动这个数——它跟着实际分辨率走，不是另维护的名单。
    assert len(eligible) == len(_SCRIPTS) - 7
    for slug in _UNDERSIZED:
        assert slug not in eligible, f"{slug} 本来就在放大，不该被判成能推近"


def test_够铺满但推不动的要能被单独认出来():
    """这一类不是错——它可以照常出片，只是那一条得用静止封面。

    和「在放大」混为一谈会让人去换根本不用换的图。
    """
    floor_ok = {s for s in _SCRIPTS if _fill(s) >= chk.FLOOR}
    push_ok = {s for s in _SCRIPTS if _fill(s) / chk.PUSH >= chk.FLOOR}
    static_only = floor_ok - push_ok
    # wildcard 的封面是澳网签表的屏摄，官方原图上限就是 1080×810（见
    # assets/explainer/wildcard/credits.json 里的取舍说明）；它是唯一一张
    # 「WC 两个字母清楚可读」的候选，所以按静止封面出片，不加推近。
    assert static_only == {"queue", "ten-champions", "wildcard"}, (
        f"够铺满但推不动的这一档变了：现在是 {sorted(static_only)}。"
        f"确认是换了图还是改了 PUSH，再更新这条。")


def test_命令行对不合格的报非零而对推不动的不报():
    """退出码要分得开：在放大是错，推不动只是提示。"""
    import subprocess
    run = lambda *a: subprocess.run(
        [sys.executable, str(_TOOLS / "check_cover_resolution.py"), *a],
        capture_output=True, text=True)
    assert run("--only", "rufus").returncode == 2          # 在放大
    assert run("--only", "queue").returncode == 0          # 只是推不动
    assert run("--only", "hawkeye").returncode == 0        # 全过
