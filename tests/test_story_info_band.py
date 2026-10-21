from pathlib import Path
import sys

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from render_story_info_band import (  # noqa: E402
    BRAND_GREEN, WHITE, SetScore, display_units, metric_runs, render,
    score_line, score_number_colors, set_number_runs, set_score_wins,
)


def test_story_info_band_is_typography_not_a_large_panel(tmp_path):
    out = render("第一关", "尤晓迪", "六安W100冠军 · 擅长苦战",
                 tmp_path / "band.png", metric="世界第198", variant="player")
    with Image.open(out) as image:
        assert image.width == 1200 and image.height >= 340 and image.height % 2 == 0
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


def _score_xs(path, *, x_max=1150):
    """Measure the third visible row, excluding metadata and winner names.

    The people row can now contain green too. Taking the last green row would
    measure the names instead of the score and silently pass the wrong test.
    """
    from render_story_info_band import MUTED
    with Image.open(path) as image:
        pixels = image.convert("RGBA")
        colors = {BRAND_GREEN, WHITE, MUTED}
        active = [y for y in range(image.height)
                  if any(pixels.getpixel((x, y)) in colors
                         for x in range(60, min(x_max, image.width)))]
        bands = []
        start = previous = active[0]
        for y in active[1:]:
            if y - previous > 4:
                bands.append((start, previous))
                start = y
            previous = y
        bands.append((start, previous))
        assert len(bands) == 4, "topic/meta/score/people must be distinct visible rows"
        top, bottom = bands[2]
        return tuple([x for y in range(top, bottom + 1)
                      for x in range(min(x_max, image.width))
                      if pixels.getpixel((x, y)) == color]
                     for color in (BRAND_GREEN, WHITE))


def _median(xs):
    ordered = sorted(xs)
    return ordered[len(ordered) // 2]


def test_比分按局数上色_赢的那个数黄绿(tmp_path):
    """账号所有者 2026-10-12 改过一次：颜色按每一个局数，不按整盘，也不看主角在哪一侧。

    `6-4` 的 6 黄绿、4 白；`2-6` 反过来；`7-6(5)` 的 7 黄绿，6 和 `(5)` 白；
    `6-7(7)` 的 6 白、7 黄绿、括号白。连字符留白。平局两个局数都白。
    """
    assert set_number_runs("6-4") == [("6", True), ("-", False), ("4", False)]
    assert set_number_runs("2-6") == [("2", False), ("-", False), ("6", True)]
    assert set_number_runs("7-6(5)") == [
        ("7", True), ("-", False), ("6", False), ("(5)", False)]
    assert set_number_runs("6-7(7)") == [
        ("6", False), ("-", False), ("7", True), ("(7)", False)]
    assert set_number_runs("6-6") == [("6", False), ("-", False), ("6", False)]
    assert score_number_colors("决胜盘 1-5 赛点") is None

    def card(metric, name):
        return render("2026.10.11", "摔拍警告", "布勃利克 vs 中岛布兰登",
                      tmp_path / name, metric=metric)

    def sides(metric, name):
        green, white = _score_xs(card(metric, name))
        assert green and white, f"{metric} 两种颜色都要画出来"
        return green, white

    green, white = sides("6-4", "six-four.png")
    assert _median(green) < _median(white)
    green, white = sides("2-6", "two-six.png")
    assert _median(green) > _median(white)
    green, white = sides("7-6(5)", "seven-six.png")
    assert min(green) < min(white) and max(white) > max(green)
    green, white = sides("6-7(7)", "six-seven.png")
    assert min(white) < min(green) and max(white) < min(green), "6的抢七小分在左侧6的右上角，不在整盘末尾"
    assert _score_xs(card("6-6", "level.png"))[0] == []


def test_比分颜色只从局数大小算_主角在哪一侧不改像素(tmp_path):
    """颜色从结构化盘分的局数大小算，不接受手写标记，也不看 featured。

    同一组 ``6-4``，把主角从左边换到右边，``.won`` 会翻，像素必须一个不动。
    """
    assert "won" not in SetScore.__dataclass_fields__
    with pytest.raises(TypeError):
        SetScore((1, 6), won=True)
    with pytest.raises(SystemExit, match="SetScore"):
        score_line([{"games": (6, 4), "color": "green"}])
    assert score_line([
        SetScore((1, 6)), SetScore((6, 4)), SetScore((7, 5), tiebreak=None),
    ]) == "1-6 6-4 7-5"
    assert SetScore((6, 7), tiebreak=7).token() == "6-7(7)"
    # featured 仍然记着这一屏在讲谁，但上色不读它。
    assert SetScore((6, 4), featured="left").won is True
    assert SetScore((6, 4), featured="right").won is False

    def card(featured, name):
        return render("2018.01.13", "第1冠", "vs 德米纳尔", tmp_path / name,
                      highlight="ATP250 悉尼",
                      sets=[SetScore((6, 4), featured=featured)])

    left = card("left", "left.png")
    right = card("right", "right.png")
    with Image.open(left) as image_a, Image.open(right) as image_b:
        assert image_a.tobytes() == image_b.tobytes()
    green, white = _score_xs(left)
    assert green and white and _median(green) < _median(white)

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
    # 独立行仍按局数上色：4-6 里 4 白 6 绿，7-6(2) 里 7 绿、6 和括号白。
    with Image.open(paths["right"]) as image:
        pixels = list(image.crop((0, 230, 1150, 325)).getdata())
        assert sum(p[:3] == WHITE[:3] and p[3] > 200 for p in pixels) > 1000
        assert sum(p[:3] == BRAND_GREEN[:3] and p[3] > 200 for p in pixels) > 2000


def test_split_metric_requires_an_actual_metric(tmp_path):
    with pytest.raises(SystemExit, match="必须填写 metric"):
        render("2026 中网", "第31胜", "胜布云朝克特", tmp_path / "bad.png",
               split_metric=True)
