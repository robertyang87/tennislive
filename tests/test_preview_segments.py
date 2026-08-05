"""本地看选段那条路的规矩（`tools/preview_segments_local.py`）。

它做的事只有一件：把「第几秒」翻成「第几张缩略图墙的第几格」，再切出来摆好。
**翻错了不报错**——切出来仍然是一张网球照片，仍然烧着一个时间码，
只是那不是你选的那一段。所以这份判据几乎全在钉这个映射。
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

Image = pytest.importorskip("PIL.Image")

import build_match_reel as reel  # noqa: E402
import preview_segments_local as prev  # noqa: E402

TOOL = Path("tools/preview_segments_local.py")


def _sheet(dirpath: Path, tiles: int) -> Path:
    """造一张真的缩略图墙：每一格一个能认出来的纯色。

    **不手搓几何**——按 `contact_sheet` 真正用的那几个常量拼，
    所以这张图和 ffmpeg 出来的那张是同一个版式。手搓 fixture 只能验
    「函数没崩」，验不了它和真产物对不对得上（CLAUDE.md 那条
    「判据喂了假产物」栽过一次）。
    """
    cols, pad = reel.SHEET_COLUMNS, reel.SHEET_PAD
    tw, th = 360, 202
    rows = -(-tiles // cols)
    # ⚠️ **底色要用真的那个**（`tile` 滤镜的 `color=`）：末页没填满的格子就是
    # 这个颜色，而「数得出几格」全靠认它。拿黑色当底的 fixture 会让每一格都
    # 像真画面，于是「少抓了一格」那条路根本测不到。
    bg = tuple(int(reel.SHEET_BG[2:][i:i + 2], 16) for i in (0, 2, 4))
    img = Image.new("RGB", (cols * tw + (cols - 1) * pad,
                            rows * th + (rows - 1) * pad), bg)
    for i in range(tiles):
        r, c = divmod(i, cols)
        cell = Image.new("RGB", (tw, th), _color(i))
        # 真格子必然带一个白底黑框的时间码——这正是它和填充格的分界
        cell.paste(Image.new("RGB", (60, 26), (0, 0, 0)), (8, 8))
        cell.paste(Image.new("RGB", (40, 14), (255, 255, 255)), (18, 14))
        img.paste(cell, (c * (tw + pad), r * (th + pad)))
    out = dirpath / "contact_00.jpg"
    img.save(out, quality=95)
    return out


def _color(i: int) -> tuple[int, int, int]:
    return (8 + i * 8, 240 - i * 8, 128)


def _probe(dirpath: Path, **over) -> dict:
    # 1920×1080 → `scale=360:-2` 出来正好是 360×202，和 `_sheet` 拼的一致
    data = {"url": "u", "duration": 60.0, "every": 2.0,
            "width": 1920, "height": 1080,
            "clip_from": None, "clip_to": None,
            "scene_cuts": [], "point_ends": []}
    data.update(over)
    (dirpath / "probe.json").write_text(json.dumps(data), encoding="utf-8")
    return data


def test_按秒数反推格子要和拼图那条路走同一个公式(tmp_path):
    """**真造一张墙、真切一格出来比颜色。**

    60 秒、每 2 秒一格 → 30 格，第 i 格烧的是 `0.5 + 2i` 秒
    （`SHEET_LEAD` 那半秒是躲开头的黑场／台标）。
    """
    _sheet(tmp_path, 30)
    grid = prev.SheetGrid(tmp_path, _probe(tmp_path))
    assert len(grid.stamps) == 30
    assert grid.stamps[0] == pytest.approx(reel.SHEET_LEAD)
    assert grid.stamps[7] == pytest.approx(0.5 + 2 * 7)

    for i in (0, 5, 7, 23, 29):
        px = grid.tile(i).resize((1, 1), Image.BOX).getpixel((0, 0))
        want = _color(i)
        assert max(abs(a - b) for a, b in zip(px, want)) < 12, (
            f"第 {i} 格切出来是 {px}，该是 {want}——格子算错了，"
            "而切出来仍然是一张正常的图，没有任何东西会报错")


def test_窗口里的格子要按秒数挑不是按下标猜(tmp_path):
    _sheet(tmp_path, 30)
    grid = prev.SheetGrid(tmp_path, _probe(tmp_path))
    idxs, outside = grid.within(10.0, 20.0)
    assert not outside
    assert [grid.stamps[i] for i in idxs] == [10.5, 12.5, 14.5, 16.5, 18.5]

    # 窗口比抓帧间隔还短：**要说「这一格不在窗口里」，不许当成在**。
    idxs, outside = grid.within(11.0, 12.0)
    assert outside and len(idxs) == 1


def test_起点偏移要跟着clip_from走(tmp_path):
    """只探源片的一段时（`--from/--to`），缩略图烧的仍是**源片绝对秒数**。

    反推不认这一头的话，整条片子的画面会整体错位一个 `clip_from`——
    王欣瑜那条就是从 61 分钟的 Day 2 合集里取 2371–2553 秒。
    """
    _sheet(tmp_path, 12)
    grid = prev.SheetGrid(tmp_path, _probe(
        tmp_path, duration=3000.0, clip_from=2371.0, clip_to=2394.0))
    assert grid.stamps[0] == pytest.approx(2371.5)
    idxs, _ = grid.within(2375.0, 2380.0)
    assert [grid.stamps[i] for i in idxs] == [2375.5, 2377.5, 2379.5]


def test_缩略图对不上就不许照画(tmp_path):
    """⚠️ **抓帧间隔不许假设。**

    我第一版写的是「存量都没记 `every`，退默认值 2.0 就行」——**量了一遍，
    那句话是错的**：33 份已落库的 probe 里 13 份不是 2 秒（1、2、3 都有）。
    所以记着的要验、没记的要反推，两条路对不上都不许照画。
    """
    _sheet(tmp_path, 30)
    with pytest.raises(SystemExit) as err:
        prev.SheetGrid(tmp_path, _probe(tmp_path, every=1.0))
    assert "缩略图墙" in str(err.value) and "不照画" in str(err.value)

    empty = tmp_path / "空"
    empty.mkdir()
    with pytest.raises(SystemExit) as err:
        prev.SheetGrid(empty, _probe(empty))
    assert "contact_*.jpg" in str(err.value)


def test_抽稀不许丢掉两头():
    """摆不下就抽稀，**但第一格和最后一格一格都不许丢**。

    两头正是在看的那件事——这一段从哪儿开始、到哪儿结束。中间少看几眼回合
    只是少看几眼；抽掉两头等于把要检查的东西本身裁掉了。
    """
    for n in (1, 2, 7, 8, 27, 100):
        idxs = list(range(n))
        got = prev._thin(idxs)
        assert len(got) <= prev.MAX_TILES
        assert got[0] == idxs[0] and got[-1] == idxs[-1], f"{n} 格抽成了 {got}"
        assert got == sorted(set(got)), f"{n} 格抽出重复或乱序：{got}"


def test_预览选段那条路一个源片字节都不碰():
    """它的全部价值就是「不用等 runner」——碰了源片这条路就白开了。

    **判据自己推导**：扫 AST 里真正的调用名，不搜文本——这份文件的注释里
    正写着「不碰源片」「不上 runner」，连注释一起搜会把「把规矩记下来」
    判成「又违反了规矩」（同一个形状这个仓库栽过五次）。
    """
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    called = {node.func.id for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    called |= {node.func.attr for node in ast.walk(tree)
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    banned = called & {"run", "download", "yt_download", "probe_duration",
                       "probe_size", "scene_changes", "contact_sheet",
                       "check_output", "Popen"}
    assert not banned, (
        f"预览用不着这些：{sorted(banned)}。它读的是**已经提交进仓库的**"
        "缩略图墙和 probe.json，源片一个字节都不必在场。")
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import)
                 for a in n.names}
    assert "subprocess" not in imported


def test_缩略图墙的版式只有一处出处():
    """「第几秒在第几格」是从行列数和 padding 反推的。

    这几个数**写两处必分叉**，而分叉的样子是「预览里画的不是你选的那一段」：
    不报错、看着完全正常。所以预览这头只许 import，不许自己再定义一份。
    """
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    assigned = {t.id for node in ast.walk(tree)
                if isinstance(node, ast.Assign) for t in node.targets
                if isinstance(t, ast.Name)}
    shared = {"SHEET_ROWS", "SHEET_PAD", "SHEET_COLUMNS", "SHEET_LEAD"}
    assert not (assigned & shared), (
        f"这几个数在 build_match_reel 里已经有了，别再定义一份："
        f"{sorted(assigned & shared)}")
    src = TOOL.read_text(encoding="utf-8")
    assert "from build_match_reel import" in src
    for name in ("SHEET_COLUMNS", "SHEET_PAD", "SHEET_ROWS"):
        assert name in src, f"没用上 {name}——那就是自己另算了一遍格子"
    # 时间戳也要走同一个函数，别再写一遍 `start + 0.5 + n * every`
    assert "sheet_stamps" in src


def test_probe要把抓帧间隔记下来():
    """没有它，反推只能猜——而猜错的样子是「画错一段」，不是报错。"""
    src = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    assert '"every": args.every' in src, "probe.json 里没记 every"
    # 存量的读不到，只能从格数反推——判据在 test_没记间隔就从格数反推。
    assert 'probe.get("every")' in TOOL.read_text(encoding="utf-8")


def test_本地预览的产物不许进仓库():
    """`output/` 是要提交的，而这两样是看一眼就丢的。

    不挡的话，某次 `git add output/...` 会把它们一起带进去——
    而仓库里多一张「本地预览」和多一张真产物，下一个人分不出来。
    """
    ignored = Path(".gitignore").read_text(encoding="utf-8")
    for pattern in ("segments_local", "poster_local"):
        assert pattern in ignored, f".gitignore 里没挡 {pattern}"


def test_没记间隔就从格数反推(tmp_path):
    """存量的 probe.json 没有 `every`，而它**不能假设**（量过：1/2/3 都有）。

    锚点是**格子的个数**——末页没填满的是纯背景色，数得出来；
    而「格数 = 按这个间隔排出来的时刻数」把间隔卡得很死。
    """
    _sheet(tmp_path, 30)
    probe = _probe(tmp_path)
    del probe["every"]
    (tmp_path / "probe.json").write_text(json.dumps(probe), encoding="utf-8")
    grid = prev.SheetGrid(tmp_path, probe)
    assert grid.derived and grid.every == 2.0
    assert grid.stamps[7] == pytest.approx(0.5 + 2 * 7)

    # 同一批格子、把片长翻倍 → 只有 4 秒一格解释得通
    probe2 = dict(probe, duration=120.0)
    assert prev.SheetGrid(tmp_path, probe2).every == 4.0


def test_末尾那一格没抓出来也要认得(tmp_path):
    """⚠️ `-ss` 落在最后一帧之后时，ffmpeg **不报错也不写文件**。

    而拼图那步数的是真文件，不是时刻表——三份已落库的 probe 就这样少了末尾
    一格（`eala-zheng` 末格 309.5s / 片长 309.568s）。
    **少的一定在末尾**，所以前面每一格的对应关系一个都不动。
    """
    _sheet(tmp_path, 29)                      # 按 2 秒一格该有 30 格
    grid = prev.SheetGrid(tmp_path, _probe(tmp_path))
    assert grid.tiles == 29 and grid.dropped_tail == 1
    assert len(grid.stamps) == 29
    assert grid.stamps[7] == pytest.approx(0.5 + 2 * 7), "前面的格子被挪动了"
    px = grid.tile(28).resize((1, 1), Image.BOX).getpixel((0, 0))
    assert max(abs(a - b) for a, b in zip(px, _color(28))) < 12

    # 少两格就不是这个原因了——**不许照画**
    _sheet(tmp_path, 28)
    with pytest.raises(SystemExit):
        prev.SheetGrid(tmp_path, _probe(tmp_path))


def test_几张墙不是同一趟出的要报错(tmp_path):
    """后一趟只覆盖了前几张时，目录里会混着两种版式。

    `hewitt-interview` 就是这样（`contact_00` 两行、`01~08` 五行）。
    这种目录反推出来的任何间隔都是错的，而画出来看着完全正常。
    """
    _sheet(tmp_path, 30)
    (tmp_path / "contact_00.jpg").rename(tmp_path / "contact_01.jpg")
    _sheet(tmp_path, 12)                      # contact_00 只有 2 行
    with pytest.raises(SystemExit) as err:
        prev.SheetGrid(tmp_path, _probe(tmp_path, duration=120.0))
    assert "不是同一趟" in str(err.value)


def test_格高要从长宽比算不许从墙高反解(tmp_path):
    """⚠️ 一张 410px 高的墙既是「2 行 × 202」也是「4 行 × 98」。

    两种读法切出来是完全不同的格子，而**都不报错**。拼图那步写的是
    `scale=360:-2`，所以格高是从源片长宽比**算得出来**的，不用去猜行数。
    """
    _sheet(tmp_path, 12)                      # 2 行
    grid = prev.SheetGrid(tmp_path, _probe(tmp_path, duration=24.5))
    assert grid.tile_h == 202 and grid.tiles == 12
    px = grid.tile(11).resize((1, 1), Image.BOX).getpixel((0, 0))
    assert max(abs(a - b) for a, b in zip(px, _color(11))) < 12


def test_重探一遍不许留下上一趟的缩略图墙(tmp_path):
    """⚠️ 拼图那步是**按序号覆盖**的，所以上一趟出得多就会留下尾巴。

    `deminaur-hewitt` / `hewitt-interview` 就是这么坏的（`contact_00` 两行、
    `01~08` 五行，两趟不同 `--every` 的产物摞在一起）。混着的目录里，两趟的
    图**看起来一模一样**——都是网球缩略图、都烧着时间码，谁也认不出来。

    后果不只是机器读错：**人翻缩略图墙挑段时，翻到的也是上一趟的画面。**

    ⚠️ **真跑一遍 ffmpeg**。查源码里有没有那句 `unlink` 只能防「有人把它删了」，
    防不住「它从来没工作过」——这个仓库为这个区别栽过。
    """
    import subprocess

    video = tmp_path / "src.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=10:duration=5",
         "-pix_fmt", "yuv420p", str(video)], check=True)

    out = tmp_path / "out"
    out.mkdir()
    stale = [out / "contact_01.jpg", out / "contact_07.jpg"]
    other = out / "score_03.jpg"          # 另一个 prefix，**不许被顺手清掉**
    for p in [*stale, other]:
        p.write_text("上一趟留下的", encoding="utf-8")

    sheets = reel.contact_sheet(video, out, every=2.0)      # 3 格 → 1 张

    assert [p.name for p in sheets] == ["contact_00.jpg"]
    left = sorted(p.name for p in stale if p.exists())
    assert not left, (
        f"上一趟的墙还在：{left}。下一个人挑段时会翻到上一趟的画面，"
        "而两趟的图长得一模一样，没有任何东西会告诉他。")
    assert other.exists(), (
        "把 score_* 也清掉了——`contact` 和 `score` 是两次独立调用，"
        "互相清就是把对方刚写好的删了")
