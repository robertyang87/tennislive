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

from tennislive.video.explainer import _SCRIPTS, explainer_script  # noqa: E402
from tennislive.render.tournament_story import find_story_by_slug  # noqa: E402

#: 封面是**自己画的示意图**、没有照片的那些。
#:
#: 这一整个文件量的是「照片铺满卡片要放大多少倍」——而 SVG 是分辨率无关的，
#: 这个问题对它根本不存在。所以下面所有断言的主语是**有照片封面的片子**，
#: 不是全部片子。
#:
#: ⚠️ **只许减不许加。** 「这条本来就没有照片」和「这条的照片配漏了」
#: 在代码里长得一模一样，而后者是必须红的。加一条要么带着照片来，
#: 要么显式把这张表加长——让「又退回示意图封面」变成一次看得见的决定
#: （和场馆库那条 `LANDMARK_BUDGET` 一个形状）。
_DRAWN_COVERS = {
    # 讲的是一张奖金表：任何一张球员实拍都会把「第一轮出局的那些人」
    # 缩回到某一张脸上，而那正是这条选题要反对的看法。
    "equal-pay",
    # 这场球唯一能核实的实拍（Getty）只有 612×408 的免费预览，铺满封面要
    # 放大 2.65 倍以上；国家银行公开赛官网的赛后图是 1200×800，同样铺不满。
    # 两条路都会让封面明显发糊，所以封面改用示意图——正好回答封面自己
    # 提的问题（医疗暂停认哪几种情况）。三张实拍都在正文屏，credits.json
    # 的 `_cover_why` 里记着完整取舍。
    "cramp-timeout",
    # 封面那一问是「为什么每一站的球都不一样」，而它的答案是一组**分布**：
    # 2023 赛季 10 个品牌、19 种型号，美网前四周 4 种。没有任何一张照片能
    # 表达「19 种」——一张球的实拍只能证明「有球」。这不是找不到照片的
    # 退路（正文第①屏就是实拍），是「示意图的触发条件是照片讲不清」那条
    # 本身。而且 19 是全片最硬的事实，按「最硬的那个事实放第①屏」它本来
    # 就该压在最前面。
    "tour-balls",
    # 封面那一问是「「盘外招」算犯规吗？」。把某一个球员的脸压在这句话下面，
    # 等于替读者认定了他就是那个使盘外招的人——而账号所有者对这条片子的要求
    # 就是「按最稳妥的方式去表达」。所以封面画的是**证据本身**：gamesmanship
    # 在 ATP 2026 规则书里的三处原文摘句加页码（p.105 / p.108 / p.110）。
    # 霍达尔那张 ATP 官方实拍留在第 ① 屏，那一屏只有比分、轮次和双方的原话。
    # ⚠️ 那张图 1920×1080，铺满 1080×1440 要放大 133%，本来也过不了下面那条
    # 1.00x 的地板——**但换掉它的理由是上一条，分辨率只是碰巧站在同一边**。
    # 两件事别混：混了的话，下次找到一张够大的实拍就会把人脸又放回封面。
    "gamesmanship",
    # 封面那一问是「资格赛最远能打到哪儿？」，而它的答案是**两个数摆在一起**：
    # 女子那条走到冠军，男子那条停在半决赛。任何一张球员实拍都会把这一问
    # 缩回到某一个人身上——读者读到的会变成「这个人最远走到哪儿」，那是
    # 另一个问题，而且答错了（片子里出现的六个人没有一个是那个天花板本身）。
    # 两张实拍（郑钦文、赫瓦林斯卡）都在正文屏，那儿没有铺满整卡的分辨率门槛。
    "qualifier-ceiling",
}

#: 有照片封面的片子。**推导出来的，不是另维护一张名单。**
_PHOTO_COVERS = sorted(set(_SCRIPTS) - _DRAWN_COVERS)

# 现在就在放大的三张，只许变大不许变小。换了更大的原图就从这里删掉。
# 值是当前的铺满倍数，留 0.02 的容差给不同 Pillow 版本的读取差异。
_UNDERSIZED = {
    "rufus": 0.83,             # 1600x1200
    "wimbledon-whites": 0.87,  # 937x1250，全套最小
    "shang-nishikori": 0.95,   # 1023x1365
    # 2000x1333。⚠️ **不是「懒得找更大的」**：2026-08-15 那天赛事官网媒体库
    # 59 个文件全扫过，**德约只有这一张**；那一批也没有 `-scaled` 变体
    # （8/14 那批才有，去掉后缀能到 4000~6335 像素），所以 2000×1333 就是原图。
    # ATP 那条路同一天量过：总站 403、`/en/news/` 在赛事域名上不镜像、
    # 媒体库四种命名全 302（同时拿规则书 PDF 当对照组返回 200，证明路没断）。
    # 换上它的理由是账号所有者「最好再减少示意图」——原来封面画的是
    # `wbgt_recipe()`，**和第 ③ 屏一模一样的那张图**，三十秒内给了两遍。
    "heat-rule": 0.93,         # 2000x1333
    # 2000x1334，和上一条同一个图库、同一个形状。⚠️ **不是「懒得找更大的」**：
    # 赛事官网媒体库 `?search=Fonseca` 只有三张比赛照，**全部 2000 像素**；
    # 三个文件名各探一次 `-scaled` 变体，**全部 404**（8/14 那批才有，去掉后缀
    # 能到四五千像素，这三张没有），也就是 2000 就是原图。媒体库里高度 ≥1440 的
    # 那 87 张逐条读过 `alt_text`，**没有一张是丰塞卡**；The Enquirer 8/16、8/17
    # 两天的 sitemap 里一条网球报道都没有；ATP 那条路照旧 403。
    # ⚠️ 本届唯一一张过得了这条地板的当日照（`…JM022042_PS2.jpg`，2000×1500）
    # **认不出是谁**——为了过分辨率那道闸去用一张认不出人的照片，是把第 4 道闸门
    # 放到第 1 道前面，方向反了。完整取舍在
    # assets/explainer/fonseca-oconnell/credits.json 的 `_cover_is_underscale_why`。
    "fonseca-oconnell": 0.93,  # 2000x1334
    # 1280×720，铺满 1080×1440 是 2.0 倍放大——**美网官方图片接口的天花板**
    # （`f_` 前缀就是顶，CLAUDE.md 记着十二个前缀、六个目录、三种 width 参数都
    # 探过）。同一轮 `find_cover_photo.py` 跑过 09-02 / 09-03 两天：AP 对这一场
    # 是零、WTA photo-resources 不收大满贯、USA TODAY 当日图集没有他。封面主体
    # 只能是布云朝克特（那一问的主语就是他），所以这一档是这条片子的上限，
    # 不是没找；完整取舍在 assets/explainer/bu-lucky-loser/credits.json。
    "bu-lucky-loser": 0.50,     # 1280x720
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
    return sorted(s for s in _PHOTO_COVERS if _fill(s) / 2 >= chk.FLOOR)


def _two_x_budget() -> tuple[int, int]:
    """(已用, 上限)。上限由 `doubled * 5 <= len(_PHOTO_COVERS)` 反解。"""
    return len(_two_x_slugs()), len(_PHOTO_COVERS) // 5


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


@pytest.mark.parametrize("slug", _PHOTO_COVERS)
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


def test_画封面那张表自己也要有判据():
    """⚠️ **这条不在，`_DRAWN_COVERS` 就是一张能蒙混过关的白名单。**

    上面所有断言的主语被它减掉了一部分。要是有人只是**忘了配封面照片**，
    往这张表里一加，整组分辨率检查就对那条片子彻底闭嘴——而「本来就没有照片」
    和「照片配漏了」在代码里长得一模一样。

    所以两头都钉：表里的每一条**必须真的有示意图封面**（不是空着），
    而且**不许有幽灵**（片子删了表还留着，那就成了一条永远为真的豁免）。
    """
    ghosts = _DRAWN_COVERS - set(_SCRIPTS)
    assert not ghosts, f"_DRAWN_COVERS 里这些片子不存在了：{'、'.join(sorted(ghosts))}"

    for slug in sorted(_DRAWN_COVERS):
        cover = explainer_script(find_story_by_slug(slug))[0]
        assert not cover.image, (
            f"{slug} 其实有封面照片，从 _DRAWN_COVERS 里删掉——这张表只许变短")
        assert cover.diagram, (
            f"{slug} 的封面既没有照片也没有示意图。"
            "它不该待在 _DRAWN_COVERS 里躲开分辨率检查，它该被修好。")

    # 反过来：**没进这张表的，一张不许缺照片**。
    # 少了这一句，漏配封面的片子会在 `_fill()` 里报「找不到封面图」——
    # 那句话读起来像素材问题，而真正的毛病是它压根没登记。
    missing = [s for s in _PHOTO_COVERS
               if not explainer_script(find_story_by_slug(s))[0].image]
    assert not missing, (
        f"{'、'.join(missing)} 没有封面照片，却也不在 _DRAWN_COVERS 里——"
        "要么补一张照片，要么显式认领它用示意图封面。")


def test_不合格名单只能变短():
    """换了大图就要把它从名单里删掉，否则名单会留着一个假的下限。"""
    fixed = {s: v for s, v in _UNDERSIZED.items()
             if s in _PHOTO_COVERS and _fill(s) >= chk.FLOOR}
    assert not fixed, (
        f"{'、'.join(fixed)} 已经够铺满了，从 _UNDERSIZED 里删掉——名单只该变短。")


def test_不合格名单里不许有不存在的片子():
    ghosts = set(_UNDERSIZED) - set(_PHOTO_COVERS)
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
    assert doubled * 5 <= len(_PHOTO_COVERS), (
        f"按 2 倍图当基准时仍有 {doubled}/{len(_PHOTO_COVERS)} 条合格，超过两成——"
        "这个反例撑不住了，回去确认基准是不是真的该用 1080x1440。\n"
        f"越过 {2 * chk.FLOOR:.2f}x 的是：{'、'.join(over)}。\n"
        "刚换过封面的话多半就是新加的那张。**它不是错**，只是把这条反例挤爆了；"
        f"把它缩到 {2 * chk.FLOOR:.2f}x 以下即可——"
        "不该为了让一张图更大，去拆一条用来自证基准的判据。")


def test_能推近的片子是算出来的不是手写的():
    """哪几条能用推近，由分辨率决定，不该另维护一张名单——两处一旦不同步，
    就会给一张经不起推的图加上动效，而且没人会发现。
    """
    eligible = [s for s in _PHOTO_COVERS if _fill(s) / chk.PUSH >= chk.FLOOR]
    # 当前这批：不够推的有 11 条（5 张本来就在放大 + 6 张够铺满推不动）。
    # 加选题会动这个数——它跟着实际分辨率走，不是另维护的名单。
    # ⚠️ 2026-08-17 从 9 变 10：`heat-rule` 的封面从示意图换成了实拍
    # （账号所有者「最好再减少示意图」），而那张 2000×1333 铺满是 0.93x，
    # 于是 `_PHOTO_COVERS` 和「在放大」那一档同时各多一条。
    # ⚠️ 同日从 10 变 11：`fonseca-oconnell` 的封面同样是赛事图库那一批
    # 2000 像素的实拍（见 `_UNDERSIZED` 里那段），形状和 `heat-rule` 一模一样。
    # ⚠️ 2026-09-03 从 11 变 12：`bu-lucky-loser` 的封面是美网官方图片接口那一档
    # 1280×720 的实拍（那条渠道的天花板，见 `_UNDERSIZED` 里那段），铺满 0.50x。
    assert len(eligible) == len(_PHOTO_COVERS) - 12
    for slug in _UNDERSIZED:
        assert slug not in eligible, f"{slug} 本来就在放大，不该被判成能推近"


def test_够铺满但推不动的要能被单独认出来():
    """这一类不是错——它可以照常出片，只是那一条得用静止封面。

    和「在放大」混为一谈会让人去换根本不用换的图。
    """
    floor_ok = {s for s in _PHOTO_COVERS if _fill(s) >= chk.FLOOR}
    push_ok = {s for s in _PHOTO_COVERS if _fill(s) / chk.PUSH >= chk.FLOOR}
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
    # shang-rublev 的封面不是照片，是 tools/versus_poster.py 渲出来的 VS 海报
    # （两人官方抠图 + 国旗 + 即时排名），**渲染器的输出就是 1080×1440**，
    # 所以铺满 1.00x、推不动是必然的，跟素材够不够清晰无关：想让它推得动，
    # 只能把海报渲成更大的画布，而画布尺寸是版式定死的那一部分。
    assert static_only == {
        "lucky-loser", "mandatory-1000", "queue", "shang-rublev",
        "ten-champions", "wildcard",
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
