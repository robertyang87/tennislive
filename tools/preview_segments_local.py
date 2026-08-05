#!/usr/bin/env python3
"""把每一段**选的窗口里到底是什么画面**摆出来，配上那一段的旁白——本地，
不碰源片、不上 runner。

## 为什么要有它

账号所有者 2026-08-05：「这些工作耗时没问题，主要是**不要返工重新来**，
只需要微调其中的部分就行」。

这条线现在渲之前能看见的：封面（`render_cover_local.py`，7 秒）、旁白装不装
得下（`--check-narration`，29 秒）、段落越界／跨切点／死球（`--dry-run`，
0.2 秒）。**看不见的最大一块是「这一段画面到底是什么」**——而 spec 改得最多的
就是 `start`/`end`（九条已发 spec 的历史里改了 255 次）。判据摆在眼前却没人用：
probe 的缩略图墙**已经提交进仓库了**（228 张），只是它按源片时间轴摊开，
没有按你选的段摆过。

于是「这一段配的话和画面搭不搭」只能靠渲一趟四分钟的成片再看——又一次
「工具写出来了、产物已经落库了，就是没人在该用的时候用它」。

## 用法

    PYTHONPATH=src python3 tools/preview_segments_local.py --slug shang-rublev

    # 只看改动过的那两段（这才是「微调其中的部分」）
    PYTHONPATH=src python3 tools/preview_segments_local.py --slug shang-rublev --seg 3,7

出来是几张 JPEG，一行一段：**时间窗 + 这段窗口里的缩略图 + 那一段的旁白**。
用 `Read` 打开看。改完 spec 直接重跑，零点几秒一版。

## ⚠️ 它看不见什么——别拿它当渲完了

- **时间分辨率就是抓帧的间隔**（默认 2 秒一格）。所以显示的第一格是
  「`start` 之后的第一格」，**不是** `start` 那一帧——真正的边界最多能差
  一个间隔。「死球之后再切」那种半秒级的判断，仍然要看 `--dry-run` 报的
  `point_ends`
- **字幕压在画面上什么样**（断行、会不会盖住记分条）——只有渲完才知道
- **接缝的溶解、闪避混音、整片节奏**——同上
- 记分条读不出来：整幅缩到 360 宽时比分只有几个像素高。要读比分看 probe 另
  出的那份 `score_*.jpg`（裁出记分条单独放大拼的）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_match_reel import (  # noqa: E402
    CUT_EDGE_TOL,
    SHEET_BG,
    SHEET_LEAD,
    SHEET_COLUMNS,
    SHEET_PAD,
    SHEET_ROWS,
    Segment,
    claim_probes,
    load_spec,
    sheet_stamps,
    spec_sources,
    validate_spec,
)

ROOT = Path(__file__).resolve().parent.parent

# 版式。**页宽是从「一段最多摆几格」倒推的**，别反过来拍一个页宽再塞。
TILE_W = 300              # 摆满 MAX_TILES 格时每格多宽
TILE_MAX = 440            # 格子少的时候放大到这儿为止——一行两格却只画 300 宽，
                          # 就是白扔一千多像素，而「近端是谁」正是要看清的那件事
MAX_TILES = 7
GAP = 8
MARGIN = 24
ROWS_PER_PAGE = 6
PAGE_W = MAX_TILES * TILE_W + (MAX_TILES - 1) * GAP + 2 * MARGIN
ROW_W = PAGE_W - 2 * MARGIN

# 配色照 CLAUDE.md 那条「一屏只留一个强调色」：底色就用缩略图墙自己的
# 那个深绿（`SHEET_BG`），拼上去看不出接缝；正文近白、次级灰绿；
# **唯一的强调色留给「这一段有事」**（跨切点、窗口比间隔还短）。
BG = (0x11, 0x22, 0x1B)
FG = (0xE7, 0xF3, 0xEC)
DIM = (0xA9, 0xBC, 0xB2)
WARN = (0xF5, 0xB1, 0x3D)
QUOTE = (0xC3, 0xDC, 0x4A)          # 原声段（quote）用品牌绿，和旁白分开
_BG_RGB = tuple(int(SHEET_BG[2:][i:i + 2], 16) for i in (0, 2, 4))

F_HEAD = 30
F_BODY = 30
LINE = 40


def _rel(path: Path) -> str:
    """打路径尽量用仓库相对的。**认领 probe 用的是相对路径**（`Path("output")`），
    而给 `--out` 的可能是绝对路径——`relative_to` 混着用会抛，
    而那会在「只是打一行日志」的地方把整个工具带崩。"""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _fonts():
    from PIL import ImageFont  # noqa: PLC0415

    from tennislive.render.cards import _find_font  # noqa: PLC0415

    reg, r_idx = _find_font(False)
    bold, b_idx = _find_font(True)
    return (ImageFont.truetype(bold, F_HEAD, index=b_idx),
            ImageFont.truetype(reg, F_BODY, index=r_idx))


def _wrap(draw, text: str, font, width: int) -> list[str]:
    """按**量出来的宽度**折行，不按字数。

    中文一个字一格、拉丁字母半格上下，按字数折出来的行宽差得能到一倍——
    而溢出的那一半会被画到页面外面，**不报错**。
    """
    lines: list[str] = []
    cur = ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if draw.textlength(cur + ch, font=font) > width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur or not lines:
        lines.append(cur)
    return lines


#: 反推抓帧间隔时试这几个值。`--every` 收的是浮点数，但人手打进去的
#: 只会是这几个整数／半数——真跑过的三个是 1、2、3。
EVERY_CANDIDATES = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0)


class SheetGrid:
    """一条源片的缩略图墙：把「第几秒」翻成「第几张图的第几格」。

    ⚠️ **抓帧间隔不许假设，要么读到、要么反推出来并自证。**

    我第一版写的是「存量的 probe.json 没记 `every`，退默认值 2.0 就行」。
    **量了一遍，那句话是错的**：33 份已落库的 probe 里 13 份对不上 2 秒，
    两个方向都有——`hewitt-giron` / `lleyton-uso2001` 的格数正好是两倍
    （`--every 1`），`jodar-fritz` 四条源、`wong-gea`、`eala-svitolina`、
    `fritz-jodar-final` 正好是三分之二（`--every 3`）。
    **假设一次就会稳稳地画错一段，而画面看着完全正常。**

    所以真正的锚点是**格子的个数**——它数得出来（末页没填满的格子是纯背景色），
    而 `格数 = ceil((hi − lo) / every)` 把 `every` 卡在一个很窄的区间里
    （区间宽 `(hi−lo)/(N(N−1))`，几十格的时候不到 0.1 秒），
    上面那几个候选值里最多只活得下来一个。
    """

    def __init__(self, outdir: Path, probe: dict) -> None:
        from PIL import Image  # noqa: PLC0415

        self.dir = outdir
        self.probe = probe
        self.duration = float(probe["duration"])
        self.lo = float(probe.get("clip_from") or 0.0) + SHEET_LEAD
        clip_to = probe.get("clip_to")
        self.hi = (self.duration if clip_to is None
                   else min(float(clip_to), self.duration))
        self.clip_to = None if clip_to is None else float(clip_to)
        self.sheets = sorted(outdir.glob("contact_*.jpg"))
        self.per_sheet = SHEET_COLUMNS * SHEET_ROWS
        if not self.sheets:
            raise SystemExit(
                f"{_rel(outdir)} 里没有 contact_*.jpg。\n"
                "这一趟 probe 是在缩略图墙落库之前跑的，或者产物没检出——"
                "跑一趟 `match-reel mode=probe` 就有了。")

        first = Image.open(self.sheets[0])
        self.tile_w = (first.width - (SHEET_COLUMNS - 1) * SHEET_PAD) // SHEET_COLUMNS
        # ⚠️ **格高要从源片的长宽比算，不能从墙的高度反解**——反解是有歧义的：
        # 一张 410 高的墙既是「2 行 × 202」也是「4 行 × 98」，而两种读法
        # 画出来的是完全不同的格子。拼图那步写的是 `scale=360:-2`
        # （等比缩到偶数高），所以这个数是**算得出来的**。
        iw, ih = int(probe["width"]), int(probe["height"])
        self.tile_h = int(round(self.tile_w * ih / iw / 2)) * 2
        # **除了末页，每一页都该是满的 5 行。** 对不上就说明这几张墙不是同一趟
        # probe 出的——后一趟只覆盖了前几张，剩下的还是上一趟的
        # （`hewitt-interview` 就是这样：`contact_00` 两行、`01~08` 五行）。
        # 那种目录反推出来的任何间隔都是错的，而画面看着完全正常。
        full = SHEET_ROWS * self.tile_h + (SHEET_ROWS - 1) * SHEET_PAD
        odd = [q.name for q in self.sheets[:-1]
               if Image.open(q).height != full]
        if odd:
            raise SystemExit(
                f"{_rel(outdir)}：这几张缩略图墙不是满页（{odd}，满页该是 "
                f"{full}px）——说明它们不是同一趟 probe 出的，"
                "后一趟只覆盖了前几张。\n**不照画**：混着的目录反推出来的"
                "间隔一定是错的。重跑一趟 `mode=probe`。")
        self.tiles = self._count_tiles()

        recorded = probe.get("every")
        self.every, self.derived = self._resolve_every(recorded)
        # ⚠️ **末尾那一格可能根本没抓出来**：`-ss` 落在最后一帧之后时
        # ffmpeg 不报错、也不写文件，而拼图那步数的是**真文件**
        # （`frames.glob("*.jpg")`），不是时刻表。三份已落库的 probe 正是这样
        # （`eala-zheng` 末格 309.5s / 片长 309.568s，差 0.068 秒）。
        # **少的一定在末尾**，所以前面每一格的对应关系一个都不动——截掉即可。
        self.dropped_tail = len(self._stamps(self.every)) - self.tiles
        self.stamps = self._stamps(self.every)[:self.tiles]
        self._cache: dict[int, object] = {}

    def _count_tiles(self) -> int:
        """图上到底有几格。**末页没填满的格子是纯背景色**（`tile` 滤镜拿
        `SHEET_BG` 填的），所以数得出来——而这个数是反推间隔唯一的锚点。"""
        from PIL import Image  # noqa: PLC0415

        last = Image.open(self.sheets[-1]).convert("RGB")
        rows = round((last.height + SHEET_PAD) / (self.tile_h + SHEET_PAD))
        used = rows * SHEET_COLUMNS
        for pos in range(rows * SHEET_COLUMNS - 1, -1, -1):
            r, c = divmod(pos, SHEET_COLUMNS)
            cell = last.crop((c * (self.tile_w + SHEET_PAD),
                              r * (self.tile_h + SHEET_PAD),
                              (c + 1) * self.tile_w + c * SHEET_PAD,
                              (r + 1) * self.tile_h + r * SHEET_PAD))
            px = cell.resize((1, 1), Image.BOX).getpixel((0, 0))
            lo, hi = cell.convert("L").getextrema()
            # 门槛是量出来的，不是拍的（`shang-rublev` 末页 18 格逐格量）：
            #   填充格   离背景色 1、明暗差 0
            #   真画面   离背景色 28~129、明暗差 250~255
            # 中间隔着两个数量级，**因为每一格都烧着白底黑框的时间码**——
            # 再黑的一帧也必然有接近满量程的明暗差。
            filler = (max(abs(a - b) for a, b in zip(px, _BG_RGB)) < 6
                      and hi - lo < 10)
            if not filler:
                break
            used = pos
        return (len(self.sheets) - 1) * self.per_sheet + used

    def _stamps(self, every: float) -> list[float]:
        """⚠️ **一律走 `sheet_stamps()`，别用闭式的 ceil。**

        闭式解在整除边界上和它差一格：`_frange` 的条件是 `value < stop`，
        而 `ceil((hi−lo)/e)` 在 `(hi−lo)` 恰好是整数倍时多算一个——
        再叠上浮点（`486.0` 其实是 `486.04`），四条已落库的源片就是这么被
        判成「反推不出唯一间隔」的。同一个公式只许有一处出处。
        """
        return sheet_stamps(self.duration, every=every,
                            start=self.lo - SHEET_LEAD, stop=self.clip_to)

    def _resolve_every(self, recorded) -> tuple[float, bool]:
        """间隔：记下来的直接用（但要验），没记就从格数反推。"""
        span = self.hi - self.lo
        if recorded:
            every = float(recorded)
            n = len(self._stamps(every))
            if n - self.tiles not in (0, 1):
                raise SystemExit(
                    f"{_rel(self.dir)}：probe.json 记着 every={every}s，"
                    f"按它算该有 {n} 格，图上数出来是 {self.tiles} 格。\n"
                    "**不照画**：这两个数对不上，说明缩略图墙和 probe.json "
                    "不是同一趟出的。重跑一趟 `mode=probe`。")
            return every, False
        fits = [e for e in EVERY_CANDIDATES
                if len(self._stamps(e)) - self.tiles in (0, 1)]
        if len(fits) == 1:
            return fits[0], True
        raise SystemExit(
            f"{_rel(self.dir)}：probe.json 没记 `every`，"
            f"而 {self.tiles} 格 / {span:.1f}s 反推不出唯一的间隔"
            f"（合得上的有 {fits or '一个都没有'}）。\n"
            "**不照画**：猜错一次就会稳稳地画错一段，而画面看着完全正常。"
            "重跑一趟 `mode=probe`，它会把 `every` 记进去。")

    def tile(self, index: int):
        """第 `index` 格的图（原尺寸）。"""
        from PIL import Image  # noqa: PLC0415

        n, pos = divmod(index, self.per_sheet)
        row, col = divmod(pos, SHEET_COLUMNS)
        if n not in self._cache:
            self._cache[n] = Image.open(self.sheets[n]).convert("RGB")
        x = col * (self.tile_w + SHEET_PAD)
        y = row * (self.tile_h + SHEET_PAD)
        return self._cache[n].crop((x, y, x + self.tile_w, y + self.tile_h))

    def within(self, start: float, end: float) -> tuple[list[int], bool]:
        """窗口 [start, end] 里的格子。第二个返回值＝**没有一格落在里面**。"""
        inside = [i for i, t in enumerate(self.stamps) if start <= t <= end]
        if inside:
            return inside, False
        mid = (start + end) / 2
        nearest = min(range(len(self.stamps)),
                      key=lambda i: abs(self.stamps[i] - mid))
        return [nearest], True


def _thin(indexes: list[int]) -> list[int]:
    """摆不下就抽稀，**但两头一格都不许丢**。

    两头正是你在看的东西——这一段从哪儿开始、到哪儿结束。中间抽掉几格只是
    少看几眼回合，抽掉两头等于把要检查的那件事本身裁掉了。
    """
    if len(indexes) <= MAX_TILES:
        return indexes
    step = (len(indexes) - 1) / (MAX_TILES - 1)
    return [indexes[round(k * step)] for k in range(MAX_TILES)]


#: 标题行上最多列几个切点。**再多就只报个数**——一条 53 秒的段落能压着
#: 十几个死球，全列出来会把标题画到画布外面（而画到画布外面不报错）。
MAX_MARKS = 4


def _marks(seg: Segment, spec_seg: dict, probe: dict) -> list[tuple[str, tuple]]:
    """这一段值得在标题行上说一句的事。**只报事实，判断交给 `--dry-run`。**"""
    out: list[tuple[str, tuple]] = []
    cuts = [float(t) for t in (probe.get("scene_cuts") or [])
            if seg.start + CUT_EDGE_TOL < float(t) < seg.end - CUT_EDGE_TOL]
    if cuts:
        why = spec_seg.get("crosses_cut")
        head = " ".join(f"{t:.2f}" for t in cuts[:MAX_MARKS])
        more = f" …共 {len(cuts)}" if len(cuts) > MAX_MARKS else ""
        out.append((("已认领跨切点 " if why else "⚠ 跨切点 ") + head + more,
                    DIM if why else WARN))
    ends = [float(t) for t in (probe.get("point_ends") or [])
            if seg.start <= float(t) <= seg.end]
    if ends:
        # **段尾那一个才是要判的。** 「段尾切在一分打完之前」是这条线上真出过事
        # 的那一类（wong-brooksby 三处），而它只跟**最后一个**死球有关；
        # 中间那十几个是回合的节拍，列出来只会把标题挤爆。
        out.append((f"死球 {len(ends)} 处，末 {ends[-1]:.1f}"
                    f"（段尾 {seg.end - ends[-1]:+.1f}s）", DIM))
    return out


def build(slug: str, only: set[int] | None, out_prefix: Path) -> list[Path]:
    from PIL import Image, ImageDraw  # noqa: PLC0415

    spec_path = ROOT / "specs" / "reels" / f"{slug}.json"
    if not spec_path.is_file():
        raise SystemExit(f"找不到 spec：{spec_path}")
    spec = load_spec(spec_path)
    segments = validate_spec(spec)
    raw = list(spec.get("segments") or [])
    urls = spec_sources(spec)
    claimed, missing = claim_probes(spec)
    if missing:
        print(f"[注意] 这几条源片没认领到 probe.json：{missing}——"
              "用到它们的段只能空着（跑一趟 `mode=probe` 就有了）")

    grids: dict[str, SheetGrid] = {}
    for key, url in urls.items():
        if url in claimed:
            outdir, probe = claimed[url]
            grids[key] = SheetGrid(outdir, probe)
            g = grids[key]
            note = "（probe.json 没记 every，从格数反推并已自证）" if g.derived else ""
            if g.dropped_tail:
                note += f"（末尾 {g.dropped_tail} 格 ffmpeg 没抓出来，已截掉）"
            print(f"[源 {key or '主'}] {_rel(outdir)}："
                  f"{len(g.sheets)} 张墙、{len(g.stamps)} 格、"
                  f"每 {g.every}s 一格，覆盖 {g.stamps[0]:.1f}~{g.stamps[-1]:.1f}s"
                  f"{note}")

    head_f, body_f = _fonts()
    picked = [(i, s, raw[i]) for i, s in enumerate(segments)
              if only is None or (i + 1) in only]
    if not picked:
        raise SystemExit(f"--seg 挑出来是空的（这条 spec 只有 {len(segments)} 段）")

    pages: list[Path] = []
    scratch = Image.new("RGB", (10, 10))
    probe_draw = ImageDraw.Draw(scratch)
    for page_no in range(0, len(picked), ROWS_PER_PAGE):
        chunk = picked[page_no:page_no + ROWS_PER_PAGE]
        # 先量高度再开画布：一段的旁白可能折成三行，也可能一行都没有。
        plan = []
        height = MARGIN
        for index, seg, spec_seg in chunk:
            grid = grids.get(seg.source)
            text = seg.narration or seg.quote or ""
            lines = _wrap(probe_draw, text, body_f, ROW_W) \
                if text else ["（这一段没有旁白，也没有原声字幕）"]
            shown: list[int] = []
            outside = False
            n_all = 0
            tw = th = 0
            if grid:
                idxs, outside = grid.within(seg.start, seg.end)
                n_all = len(idxs)
                shown = _thin(idxs)
                # 摆得下就摆大点。**同一行里的格子一定同宽**（它们要并排比），
                # 行与行之间不同宽无所谓——每一行问的是它自己那一段的事。
                tw = min(TILE_MAX, (ROW_W - (len(shown) - 1) * GAP) // len(shown))
                th = round(tw * grid.tile_h / grid.tile_w)
            row_h = LINE + (th + 10 if grid else LINE) + len(lines) * LINE + 18
            plan.append((index, seg, spec_seg, grid, lines,
                         shown, outside, n_all, tw, th, height))
            height += row_h
        height += MARGIN
        canvas = Image.new("RGB", (PAGE_W, height), BG)
        draw = ImageDraw.Draw(canvas)
        for (index, seg, spec_seg, grid, lines,
             shown, outside, n_all, tw, th, y) in plan:
            head = (f"{index + 1:>2}  {seg.start:.2f} → {seg.end:.2f}s"
                    f"  （{seg.length:.2f}s）")
            if seg.source:
                head += f"  源:{seg.source}"
            if seg.track:
                head += "  横摇"
            # **抽稀了要说。** 「摆了 7 格」和「这一段总共就 7 格」长得一模一样，
            # 而前者意味着中间有没看到的画面——一次不出声的截断，
            # 读起来就是「全看过了」。
            if n_all > len(shown):
                head += f"  {len(shown)}/{n_all} 格"
            draw.text((MARGIN, y), head, font=head_f, fill=FG)
            x = MARGIN + draw.textlength(head + "   ", font=head_f)
            for label, color in (_marks(seg, spec_seg, grid.probe) if grid else []):
                # **画不下就别画。** 超出画布的字不会报错，它只是消失——
                # 而「这一段没有跨切点」和「跨切点被画到画布外面了」
                # 在成品图上长得一模一样。
                if x + draw.textlength(label, font=head_f) > PAGE_W - MARGIN:
                    draw.text((x, y), "…（还有，见 --dry-run）",
                              font=head_f, fill=WARN)
                    break
                draw.text((x, y), label, font=head_f, fill=color)
                x += draw.textlength(label + "   ", font=head_f)
            y += LINE
            if grid is None:
                draw.text((MARGIN, y), "（这条源片没有 probe.json，画面看不见）",
                          font=body_f, fill=WARN)
                y += LINE
            else:
                for col, i in enumerate(shown):
                    tile = grid.tile(i).resize((tw, th), Image.LANCZOS)
                    canvas.paste(tile, (MARGIN + col * (tw + GAP), y))
                tail = MARGIN + len(shown) * (tw + GAP)
                if outside:
                    draw.text((tail, y),
                              f"⚠ 窗口（{seg.length:.2f}s）比抓帧间隔"
                              f"（{grid.every}s）还短。\n"
                              "这一格**不在窗口里**，只是离得最近——\n"
                              "这一段的画面本工具看不见。",
                              font=body_f, fill=WARN)
                y += th + 10
            color = QUOTE if (seg.quote and not seg.narration) else FG
            for line in lines:
                draw.text((MARGIN, y), line, font=body_f,
                          fill=color if seg.narration or seg.quote else DIM)
                y += LINE
        out = out_prefix.with_name(
            f"{out_prefix.name}_{page_no // ROWS_PER_PAGE:02d}.jpg")
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out, quality=88, optimize=True)
        pages.append(out)
    return pages


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--seg", default="",
                    help="只看这几段（1 起，逗号分隔）。改了哪段就看哪段")
    ap.add_argument("--out", default="",
                    help="存哪儿（不含 _NN.jpg 后缀）；默认写进产物目录")
    args = ap.parse_args()

    only = None
    if args.seg:
        only = {int(v) for v in args.seg.replace("，", ",").split(",") if v.strip()}

    if args.out:
        prefix = Path(args.out)
    else:
        hits = sorted(ROOT.glob(f"output/*/reel/{args.slug}"), reverse=True)
        prefix = (hits[0] if hits else Path("/tmp")) / "segments_local"
    pages = build(args.slug, only, prefix)
    print("\n[预览] " + "  ".join(str(p) for p in pages))
    print("  用 Read 打开看。⚠️ 缩略图是 2 秒一格的，**第一格是 start 之后的"
          "第一格、不是 start 那一帧**——半秒级的段尾判断看 `--dry-run` 的死球时刻。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
