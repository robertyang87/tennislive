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
    "wimbledon-whites": 0.87,  # 937x1250，全套最小
    "shang-nishikori": 0.95,   # 1023x1365
}
# lucky-loser 的封面不在这张名单上，但它的做法值得记一句，因为**这条 1.00x 的
# 地板正是那张图的垫层能减到多小的下界**。
#
# 原图是 1179×1219 的截图（干净原图四条路全走完都取不到），比例 0.967 几乎是
# 方的。卡片是 3:4，要不裁宽地铺满就得垫高，纯垫要 353px——占图高 22.5%，
# 台头底下露出一大条虚化。垫和裁可以换，保持 3:4 就是 `c = 264.75 - 0.75p`：
# 拿一点左边的背景（他左肩起于 x≈156）换掉一大截垫层。
#
# p=221 时正好 1080×1440，也就是**贴着这条地板**；再往下减垫层就得放大。
# 现在取 p=225 / c=96 → 1083×1444，垫层 15.6%，铺满 1.003x，留一点余量，
# 不必往 _UNDERSIZED 里加例外。
#
# 底部和右侧一个像素不动是账号所有者定的：奖杯底座在底下，摄影署名
# `© MERLO DE GRAIA` 右边缘到 x=1170 而图宽才 1179。交界羽化 7% 画布高，
# 顶栏与下方只差 +1.6（硬贴那版是 +33.7）。
# 详见 assets/explainer/lucky-loser/credits.json。


def _fill(slug: str) -> float:
    path = chk.cover_image(slug)
    assert path is not None, f"{slug} 找不到封面图"
    return chk.fill_factor(path)


def _two_x_slugs() -> list[str]:
    """铺满 ≥2.0x 的片子——「按 2 倍图当基准也仍然合格」的那些。"""
    return sorted(s for s in _SCRIPTS if _fill(s) / 2 >= chk.FLOOR)


def _two_x_budget() -> tuple[int, int]:
    """(已用, 上限)。上限由 `doubled * 5 <= len(_SCRIPTS)` 反解。"""
    return len(_two_x_slugs()), len(_SCRIPTS) // 5


def _envelope() -> str:
    """换封面图时的**完整窗口**，两头都说。

    2026-08-02 为一张封面来回改了三轮，每一轮只知道自己撞了哪一条：
    0.95x 撞地板 → 换成 2.10x 的裁图 → 撞「2 倍图不是基准」那条反例 →
    才明白正解是**故意降到 1.85x**。三条闸互相拉扯，而报错一次只说一头，
    于是每一轮都要先渲一次才知道下一头在哪。

    这个函数只在报错时求值（assert 的消息是惰性的），所以那 23 次读图
    不会落在正常那条路上。
    """
    used, cap = _two_x_budget()
    room = cap - used
    tail = (
        f"还剩 {room} 个名额" if room > 0
        else "已经满了，再来一张 ≥2x 的会把那条反例判红"
    )
    return (
        f"窗口两头：下界 {chk.CARD_W}x{chk.CARD_H}（铺满 {chk.FLOOR:.2f}x）；"
        f"上界别越过 {2 * chk.FLOOR:.2f}x——「2 倍图不是基准」那条反例的预算"
        f"现在是 {used}/{cap}，{tail}。"
    )


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
        f"{_envelope()}\n"
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
    over = _two_x_slugs()
    doubled = len(over)
    # 上限按**比例**写，不写死个数。原来是 `<= 1`，那个 1 是按当时 15 条片子
    # 标出来的；thiem-football 的封面是 4103x3336 的捧杯原图（铺满倍数 2.32），
    # 一加进来就变成 2 条，测试红了——而它红的不是「基准选错了」，是
    # 「有人换了张特别大的图」。硬编码的计数会把「素材变好」误报成回归，
    # 于是下一个人要么去改判据、要么去换一张更小的图，两条路都错。
    # 两成这条线仍然把反例撑得住：多数不合格才说明基准选错会全红。
    assert doubled * 5 <= len(_SCRIPTS), (
        f"按 2 倍图当基准时仍有 {doubled}/{len(_SCRIPTS)} 条合格，超过两成——"
        "这个反例撑不住了，回去确认基准是不是真的该用 1080x1440。\n"
        f"越过 {2 * chk.FLOOR:.2f}x 的是：{'、'.join(over)}。\n"
        "刚换过封面的话多半就是新加的那张。**它不是错**，只是把这条反例挤爆了；"
        f"把它缩到 {2 * chk.FLOOR:.2f}x 以下即可——"
        "不该为了让一张图更大，去拆一条用来自证基准的判据。")


def test_能推近的片子是算出来的不是手写的():
    """哪几条能用推近，由分辨率决定，不该另维护一张名单——两处一旦不同步，
    就会给一张经不起推的图加上动效，而且没人会发现。
    """
    eligible = [s for s in sorted(_SCRIPTS) if _fill(s) / chk.PUSH >= chk.FLOOR]
    # 当前这批：不够推的有 8 条（3 张本来就在放大 + 5 张够铺满推不动）。
    # 加选题会动这个数——它跟着实际分辨率走，不是另维护的名单。
    assert len(eligible) == len(_SCRIPTS) - 8
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
    #
    # lucky-loser 是**主动换进这一档的**，不是分辨率不够。它原来 1179×1572、
    # 1.09x，推得动；但那是靠顶部垫 353px 撑出来的，垫层占了 22.5%，台头底下
    # 露出一大条虚化（账号所有者：「顶部虚化那么多」）。垫和裁能换，减垫层就
    # 得减像素，两者**不可兼得**：要留住 1.08x 的余量，垫层至少 336px（21.6%），
    # 也就是几乎回到原样。
    # 换的是「今天看得见的封面」对「一个还没实现的效果」——`zoompan` 在整个仓库
    # 里一次都没出现过，PUSH 是留给以后的容量，不是在用的功能。所以取 15.6%
    # 的垫层，进这一档。详见 assets/explainer/lucky-loser/credits.json。
    #
    # mandatory-1000 复用的是 ten-champions 那张辛纳温网捧杯（1121×1495），
    # **原图正好 3:4**，所以铺满 1.00x、一个像素的垫层都不用——和 lucky-loser
    # 那次「拿推近的余量换掉顶部虚化」是同一个取舍，只不过这张天生就不用垫。
    # 同一张图两条片子在用，落在这一档是必然的，不是谁换了图。
    assert static_only == {
        "lucky-loser", "mandatory-1000", "queue", "ten-champions", "wildcard"
    }, (
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
