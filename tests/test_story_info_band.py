from pathlib import Path
import sys

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from render_story_info_band import (  # noqa: E402
    BRAND_GREEN, SetScore, display_units, metric_runs, render,
    score_line, set_score_wins,
)


def test_story_info_band_is_typography_not_a_large_panel(tmp_path):
    out = render("第一关", "尤晓迪", "六安W100冠军 · 擅长苦战",
                 tmp_path / "band.png", metric="世界第198", variant="player")
    with Image.open(out) as image:
        assert image.size == (1200, 340)
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0
        alpha = image.getchannel("A")
        opaque = sum(alpha.histogram()[25:])
        assert opaque > 10_000, "文字锁定渲空了"
        assert opaque / (image.width * image.height) < 0.40, (
            "不许退回覆盖大半画面的实色圆角板")


def test_story_info_band_requires_all_three_levels(tmp_path):
    with pytest.raises(SystemExit, match="都必须填写"):
        render("第一关", "尤晓迪", "", tmp_path / "bad.png")


def test_story_info_band_separates_fields_and_caps_copy(tmp_path):
    with pytest.raises(SystemExit, match="不要用竖线"):
        render("第一关", "尤晓迪｜世界第198", "擅长苦战",
               tmp_path / "pipe.png")
    with pytest.raises(SystemExit, match="一屏只留一个记忆点"):
        render("第一关", "尤晓迪", "这是一行明显长到不能扫读完的屏幕解释文字还在继续",
               tmp_path / "long.png")
    assert display_units("世界No.127") < display_units("世界第一百二十七")


def test_story_info_band_uses_the_brand_green_as_its_only_accent(tmp_path):
    """2026-09-05 账号所有者「文字贴图也要重新设计好看些」。上一版是球场蓝＋网球黄两个
    强调色，和封面/章节卡/片尾那套墨绿＋品牌绿不是一家；现在只留品牌绿一个强调色
    （短轨、标签、硬数据都是它），名字暖白，证据冷灰白。判据钉在渲出来的像素上。"""
    out = render("2026 美网第三轮", "郑钦文 vs 凯斯", "凯斯发球胜赛局 40-30",
                 tmp_path / "band.png", metric="决胜盘 1-5 赛点", variant="player")
    with Image.open(out) as image:
        rgb = image.convert("RGBA")
        assert rgb.getpixel((1173, 170))[:3] == BRAND_GREEN[:3], "默认短轨在右缘，而且是品牌绿"
        assert rgb.getpixel((27, 170))[:3] != BRAND_GREEN[:3], "默认不再画左轨"
        # 全图里饱和的彩色像素只许是品牌绿那一族：不许再出现球场蓝 / 网球黄
        chroma = [p for p in rgb.getdata()
                  if p[3] > 200 and max(p[:3]) - min(p[:3]) > 90]
        assert chroma, "强调色得真的画出来了"
        off_brand = [p for p in chroma if not (p[1] > p[0] > p[2])]   # 绿 > 红 > 蓝 才是那一族
        assert len(off_brand) / len(chroma) < 0.02, f"混进了别的强调色：{off_brand[:5]}"
    assert metric_runs("决胜盘 1-5 赛点") == [("决胜盘 ", False), ("1-5", True), (" 赛点", False)]
    assert metric_runs("盘分 2-2") == [("盘分 ", False), ("2-2", True)]


def _metric_ink(path):
    """量 metric 那一带的绿/白墨。

    量框是**标定出来的**不是拍的：1200 宽的卡上，得意黑的四字主标题收在
    x≈470，三盘比分落在 480~880、基线那一带 y 120~225。第一版把左缘写成 600，
    正好把丢掉的那一盘（`4-6`，x≈490~600）切在框外，量出「白 44」——
    而卡本身是对的。两个数打架先怀疑探测，别怀疑产物。
    """
    green = white = 0
    with Image.open(path) as image:
        for pixel in list(image.convert("RGBA").crop((480, 120, 900, 225)).getdata()):
            if pixel[3] < 200:
                continue
            if pixel[1] > pixel[0] > pixel[2] and pixel[1] > 180:
                green += 1
            elif min(pixel[:3]) > 190:
                white += 1
    return green, white


def test_整场比分按盘上色赢的盘绿丢的盘白(tmp_path):
    """账号所有者 2026-09-11 给了一张参考样式：「以后都用这种样式的贴图」。

    它比原来那版硬在一处——**绿有语义了**：主标题只写赢家，metric 写整场比分，
    赢下的那几盘才是绿的。和封面比分板的 `.setwin`（赢盘绿）是同一条规矩，
    所以贴图和海报是一套系统。判据钉在**渲出来的像素**上，不是源码文本。
    """
    def band(metric, name):
        return _metric_ink(render(
            "2023.01.28 · 澳网决赛", "萨巴伦卡", "第四个冠军点才落地，生涯第一个大满贯",
            tmp_path / name, metric=metric, variant="player",
            layout="classic", align="left"))

    # 同样三盘、同样的字形（6/4/3 和连字符），只有输赢不同——所以墨量可比，
    # 差别只可能来自颜色。
    mixed_green, mixed_white = band("4-6 6-3 6-4", "mixed.png")
    won_green, won_white = band("6-4 6-3 6-4", "won.png")
    lost_green, lost_white = band("4-6 3-6 4-6", "lost.png")

    assert won_white == 0 and won_green > 3000, "三盘全赢，metric 里不该有白的"
    assert lost_green == 0 and lost_white > 3000, "三盘全丢，metric 里不该有绿的"
    assert mixed_green > 0 and mixed_white > 0, "赢两盘丢一盘，两种颜色都得有"
    # 赢两盘 : 丢一盘 ≈ 2:1——只断言「两种颜色都有」的话，把上色写成
    # 「第一盘白、其余绿」这种和输赢无关的规则也能过。
    assert 1.5 < mixed_green / mixed_white < 2.5, (
        f"绿白比例 {mixed_green / mixed_white:.2f} 不像「赢两盘丢一盘」")


def _fill_split(pixels):
    """把变色的像素分成品牌黄绿和暖白。描边是墨绿，两边一样，不进这堆。"""
    green = white = 0
    for pixel in pixels:
        if pixel[3] < 180:
            continue
        if pixel[1] > pixel[0] > pixel[2] and pixel[1] > 180:
            green += 1
        elif min(pixel[:3]) > 200 and max(pixel[:3]) - min(pixel[:3]) < 40:
            white += 1
    return green, white


def _pixels_that_differ(path_a, path_b):
    with Image.open(path_a) as image_a, Image.open(path_b) as image_b:
        a = list(image_a.convert("RGBA").getdata())
        b = list(image_b.convert("RGBA").getdata())
    return [ca for ca, cb in zip(a, b) if ca != cb]


def test_比分颜色只从结构化盘分算_主角赢的盘才是黄绿(tmp_path):
    """账号所有者 2026-10-12：比分角标里，只有主角赢下的盘涂品牌黄绿，
    丢掉的盘留白（梅德韦杰夫那张 ``1-6 6-4 7-5``，后两盘是黄绿）。

    颜色从 ``SetScore`` 算，不接受手写标记。同一串 ``6-4``，主角在左是赢
    （绿），主角在右是输（白）——若仍按「左边的数更大就涂绿」，这两张会一样。
    """
    assert "won" not in SetScore.__dataclass_fields__
    with pytest.raises(TypeError):
        SetScore((1, 6), won=True)
    with pytest.raises(SystemExit, match="SetScore"):
        score_line([{"games": (6, 4), "color": "green"}])

    # 抢七小分不翻盘：6-7(7) 是输，7-6(5) 是赢。
    assert SetScore((6, 7), tiebreak=7).won is False
    assert SetScore((7, 6), tiebreak=5).won is True
    assert SetScore((6, 7), tiebreak=7).token() == "6-7(7)"
    line, wins = score_line([
        SetScore((1, 6)), SetScore((6, 4)), SetScore((7, 5)),
    ])
    assert line == "1-6 6-4 7-5"
    assert wins == [False, True, True]
    # 同一组局数，主角换到右边，输赢整个翻过来，屏幕上的数字不动。
    flipped, flipped_wins = score_line([
        SetScore((1, 6), featured="right"),
        SetScore((6, 4), featured="right"),
        SetScore((7, 5), featured="right"),
    ])
    assert flipped == line
    assert flipped_wins == [True, False, False]

    def card(sets, name):
        return render("2018.01.13", "第1冠", "vs 德米纳尔", tmp_path / name,
                      highlight="ATP250 悉尼", sets=sets)

    base = card([
        SetScore((1, 6)), SetScore((6, 4)), SetScore((7, 5)),
    ], "medvedev.png")
    for index, won in enumerate(wins):
        sets = [
            SetScore((1, 6)), SetScore((6, 4)), SetScore((7, 5)),
        ]
        sets[index] = SetScore(sets[index].games, featured="right")
        other = card(sets, f"flip-{index}.png")
        changed = _pixels_that_differ(base, other)
        green, white = _fill_split(changed)
        assert green + white > 200, f"第 {index + 1} 盘没有涂出可辨的颜色"
        if won:
            assert green > white * 5 and white < 80, (
                f"主角赢的第 {index + 1} 盘应是黄绿，实际绿 {green} 白 {white}")
        else:
            assert white > green * 5 and green < 80, (
                f"主角丢的第 {index + 1} 盘应留白，实际绿 {green} 白 {white}")

    # 同一串字形 ``6-4``：左边是主角 → 绿；右边是主角 → 白。
    won_card = card([SetScore((6, 4), featured="left")], "won-6-4.png")
    lost_card = card([SetScore((6, 4), featured="right")], "lost-6-4.png")
    won_changed = _pixels_that_differ(won_card, lost_card)
    lost_changed = _pixels_that_differ(lost_card, won_card)
    won_green, won_white = _fill_split(won_changed)
    lost_green, lost_white = _fill_split(lost_changed)
    assert won_green > 200 and won_white < 80
    assert lost_white > 200 and lost_green < 80

    with pytest.raises(SystemExit, match="不一致"):
        render("2018.01.13", "第1冠", "vs 德米纳尔", tmp_path / "fork.png",
               metric="6-4 6-4 6-4", sets=[SetScore((1, 6)), SetScore((6, 4))])


def test_按盘上色只认整场比分_这一刻的局分照旧整块一个色(tmp_path):
    """认得窄是故意的：`决胜盘 1-5` 是**画面上这一刻**的局分，没有「赢没赢」
    可言；按盘上色套上去就是给它编一个输赢。老合同（§6 2026-09-05 那版）
    的卡因此一个像素都不变。"""
    assert set_score_wins("4-6 6-3 6-4") == [False, True, True]
    assert set_score_wins("7-6(6) 3-6 7-6(6)") == [True, False, True]
    assert set_score_wins("决胜盘 1-5 赛点") is None
    assert set_score_wins("世界第198") is None
    assert set_score_wins("") is None

    # ⚠️ 主标题要和上一条判据一样是四个字：量框（x≥480）是按四字主标题标定的，
    # 换成「郑钦文 vs 凯斯」这种更长的，主标题自己就伸进量框，白墨会被算成
    # 「metric 里有白的」——量的是主标题，不是 metric。
    green, white = _metric_ink(render(
        "2026 美网第三轮", "萨巴伦卡", "凯斯发球胜赛局 40-30",
        tmp_path / "old.png", metric="决胜盘 1-5 赛点", variant="player",
        layout="classic", align="left"))
    assert white == 0 and green > 3000, "老合同那档 metric 要整块一个强调色"


def test_split_metric_has_four_right_aligned_rows_and_preserves_glyphs(tmp_path):
    """比分独立成行，四行右对齐；左右版字形一致而非镜像。"""
    from render_story_info_band import WHITE, MUTED
    paths = {align: render("2026第二轮 中网", "第31胜", "胜布云朝克特",
                           tmp_path / f"{align}.png", metric="4-6 7-6(2) 6-2",
                           align=align, split_metric=True)
             for align in ("left", "right")}
    colors = {WHITE[:3], MUTED[:3], BRAND_GREEN[:3]}
    masks = {}
    for align, path in paths.items():
        with Image.open(path) as image:
            assert image.mode == "RGBA" and image.size == (1200, 440)
            assert image.getpixel((27 if align == "left" else 1173, 380)) == BRAND_GREEN
            assert image.getpixel((0, 0))[3] == 0
            masks[align] = []
            for top, bottom in ((0, 90), (90, 230), (230, 325), (325, 440)):
                x0, x1 = (60, 1200) if align == "left" else (0, 1150)
                row = image.crop((x0, top, x1, bottom))
                mask = Image.new("L", row.size)
                mask.putdata([255 if p[3] >= 200 and p[:3] in colors else 0
                              for p in row.getdata()])
                box = mask.getbbox()
                assert box, "四行每行都必须有真实文字墨迹"
                if align == "right":
                    assert 1130 <= box[2] <= 1134, "各行右缘须在同一条线上"
                masks[align].append(mask.crop(box))
    for left, right in zip(masks["left"], masks["right"]):
        assert left.size == right.size and left.tobytes() == right.tobytes(), "只能平移，不许镜像"
    # 丢掉的第一盘仍白，赢下的两盘仍绿，独立行不改变比分颜色语义。
    with Image.open(paths["right"]) as image:
        pixels = list(image.crop((0, 230, 1150, 325)).getdata())
        assert sum(p[:3] == WHITE[:3] and p[3] > 200 for p in pixels) > 1000
        assert sum(p[:3] == BRAND_GREEN[:3] and p[3] > 200 for p in pixels) > 2000


def test_split_metric_requires_an_actual_metric(tmp_path):
    with pytest.raises(SystemExit, match="必须填写 metric"):
        render("2026 中网", "第31胜", "胜布云朝克特", tmp_path / "bad.png",
               split_metric=True)
