"""生成《网球四大满贯》竖屏科普样片（1080×1920）。

按 data/grand_slam_video.json 的分镜规格，用 Pillow 合成每个镜头的画面，
再用 ffmpeg 加轻微的 Ken Burns 运动、淡入淡出并拼接成片。所有静态画面均来自
仓库内“可复用授权”图片并在片中署名；标注为占位的镜头输出一张醒目的占位卡，
提示在获得授权后由官方集锦替换——脚本本身没有下载器，不会抓取任何受版权保护的视频。

用法：
    pip install Pillow imageio-ffmpeg
    python tools/build_grand_slam_short.py \
        --spec data/grand_slam_video.json \
        --outdir output/grand-slam-vertical

可选：
    --voiceover path.mp3   叠加自备/授权配音音轨（不改动分镜时长）
    --tts                  尝试用 edge-tts 生成中文配音（需可访问微软语音服务）
    --overwrite            覆盖已存在的输出

输出：grand-slam.mp4、captions.srt、narration.txt、cover.png、storyboard.png。
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / "assets" / "fonts"

# ---- 视觉主题（对齐参考视频的暗色网格 + 亮黄标题风格，但为原创配色/排版）----
BG_TOP = (11, 15, 22)
BG_BOTTOM = (5, 7, 11)
GRID = (30, 46, 66)
YELLOW = (247, 191, 36)
YELLOW_SHADOW = (120, 22, 14)
WHITE = (245, 247, 250)
MUTED = (150, 162, 176)
CAPTION_BG = (0, 0, 0)


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover - 环境缺失时给出清晰指引
        sys.exit(f"找不到 ffmpeg，请 `pip install imageio-ffmpeg`（{exc}）")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def F_BLACK(sz):  # 标题：思源黑体 Black
    return font("NotoSerifSC-Black-sub.ttf", sz)


def F_BOLD(sz):
    return font("NotoSansSC-Bold-sub.ttf", sz)


def F_REG(sz):
    return font("NotoSansSC-Regular-sub.ttf", sz)


def F_LATIN(sz):
    return font("BarlowCondensed-Bold.ttf", sz)


def gradient_bg(w: int, h: int) -> Image.Image:
    base = Image.new("RGB", (w, h), BG_TOP)
    top = Image.new("RGB", (w, 1), BG_TOP)
    grad = Image.new("L", (1, h))
    for y in range(h):
        grad.putpixel((0, y), int(255 * y / h))
    bottom = Image.new("RGB", (w, h), BG_BOTTOM)
    base = Image.composite(bottom, base, grad.resize((w, h)))
    draw = ImageDraw.Draw(base)
    step = 84
    for x in range(0, w + step, step):
        draw.line([(x, 0), (x, h)], fill=GRID, width=1)
    for y in range(0, h + step, step):
        draw.line([(0, y), (w, y)], fill=GRID, width=1)
    return base


def fit_cover(img: Image.Image, box_w: int, box_h: int, focal=(0.5, 0.5)) -> Image.Image:
    """等比裁剪填满目标框，按焦点定位。"""
    src_w, src_h = img.size
    scale = max(box_w / src_w, box_h / src_h)
    new_w, new_h = int(src_w * scale + 0.5), int(src_h * scale + 0.5)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    fx, fy = focal
    left = int((new_w - box_w) * fx)
    top = int((new_h - box_h) * fy)
    left = max(0, min(left, new_w - box_w))
    top = max(0, min(top, new_h - box_h))
    return img.crop((left, top, left + box_w, top + box_h))


def wrap_cjk(text: str, fnt: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        trial = cur + ch
        if fnt.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def draw_center_text(draw, cx, y, text, fnt, fill, shadow=None, shadow_off=(6, 7)):
    w = fnt.getlength(text)
    x = cx - w / 2
    if shadow:
        draw.text((x + shadow_off[0], y + shadow_off[1]), text, font=fnt, fill=shadow)
    draw.text((x, y), text, font=fnt, fill=fill)
    bbox = fnt.getbbox(text)
    return bbox[3] - bbox[1]


def outline_text(draw, xy, text, fnt, fill=WHITE, outline=(0, 0, 0), width=4):
    x, y = xy
    for dx in range(-width, width + 1):
        for dy in range(-width, width + 1):
            if dx * dx + dy * dy <= width * width:
                draw.text((x + dx, y + dy), text, font=fnt, fill=outline)
    draw.text((x, y), text, font=fnt, fill=fill)


def brand_mark(img: Image.Image, brand: str):
    d = ImageDraw.Draw(img)
    W = img.width
    f = F_BOLD(34)
    pad = 44
    # 左上角品牌条
    d.rounded_rectangle([pad, pad, pad + 26 + f.getlength(brand) + 40, pad + 64],
                        radius=14, fill=(0, 0, 0), outline=YELLOW, width=2)
    d.ellipse([pad + 16, pad + 22, pad + 36, pad + 42], fill=YELLOW)
    d.text((pad + 48, pad + 12), brand, font=f, fill=WHITE)


def progress_dots(img: Image.Image, active: int):
    """底部四个进度点，标示当前是第几站（1..4）。"""
    if not active:
        return
    d = ImageDraw.Draw(img)
    W = img.width
    n = 4
    gap = 46
    r = 9
    total = (n - 1) * gap
    x0 = W / 2 - total / 2
    y = img.height - 150
    for i in range(n):
        cx = x0 + i * gap
        on = (i + 1) == active
        d.ellipse([cx - r, y - r, cx + r, y + r],
                  fill=YELLOW if on else (60, 68, 80))


def section_header(img: Image.Image, section: dict):
    d = ImageDraw.Draw(img)
    W = img.width
    color = tuple(int(section["color"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    y = 150
    en = section.get("en", "")
    zh = section.get("zh", "")
    surface = section.get("surface", "")
    fe = F_LATIN(60)
    draw_center_text(d, W / 2, y, en, fe, YELLOW)
    fz = F_BOLD(46)
    draw_center_text(d, W / 2, y + 74, zh, fz, WHITE)
    # 场地/城市小标签
    if surface:
        ft = F_BOLD(32)
        tw = ft.getlength(surface) + 56
        bx0 = W / 2 - tw / 2
        by0 = y + 150
        d.rounded_rectangle([bx0, by0, bx0 + tw, by0 + 52], radius=26, fill=color)
        draw_center_text(d, W / 2, by0 + 8, surface, ft, (10, 12, 16))


def caption_band(img: Image.Image, caption: str):
    if not caption:
        return
    d = ImageDraw.Draw(img, "RGBA")
    W, H = img.size
    fnt = F_BOLD(58)
    lines = wrap_cjk(caption, fnt, W - 160)
    line_h = 78
    block_h = line_h * len(lines)
    y0 = H - 300 - block_h
    for i, ln in enumerate(lines):
        y = y0 + i * line_h
        w = fnt.getlength(ln)
        x = W / 2 - w / 2
        outline_text(d, (x, y), ln, fnt, fill=WHITE, outline=(0, 0, 0), width=5)


def render_title(spec_meta, scene, W, H) -> Image.Image:
    img = gradient_bg(W, H)
    d = ImageDraw.Draw(img)
    big = scene.get("big", [])
    fnt = F_BLACK(180)
    total_h = len(big) * 210
    y = H / 2 - total_h / 2 - 120
    for line in big:
        draw_center_text(d, W / 2, y, line, fnt, YELLOW, shadow=YELLOW_SHADOW, shadow_off=(8, 10))
        y += 210
    sub = scene.get("sub", "")
    if sub:
        fs = F_BOLD(52)
        draw_center_text(d, W / 2, y + 30, sub, fs, WHITE)
    brand_mark(img, spec_meta["brand"])
    return img


def render_section(spec_meta, scene, W, H) -> Image.Image:
    img = gradient_bg(W, H)
    d = ImageDraw.Draw(img)
    idx = scene.get("index", 0)
    big = F_BLACK(320)
    draw_center_text(d, W / 2, H / 2 - 320, str(idx), big, YELLOW,
                     shadow=YELLOW_SHADOW, shadow_off=(10, 12))
    sec = scene["section"]
    fe = F_LATIN(72)
    draw_center_text(d, W / 2, H / 2 + 120, sec["en"], fe, WHITE)
    fz = F_BOLD(56)
    draw_center_text(d, W / 2, H / 2 + 210, sec["zh"], fz, YELLOW)
    ft = F_BOLD(38)
    draw_center_text(d, W / 2, H / 2 + 310, sec.get("surface", ""), ft, MUTED)
    brand_mark(img, spec_meta["brand"])
    progress_dots(img, idx)
    return img


def _photo_layer(scene, W, H) -> Image.Image:
    img = gradient_bg(W, H)
    src = Image.open(ROOT / scene["image"]).convert("RGB")
    focal = scene.get("focal", [0.5, 0.5])
    box_h = int(H * 0.62)
    box_y = int(H * 0.20)
    photo = fit_cover(src, W, box_h, focal)
    img.paste(photo, (0, box_y))
    # 顶部/底部渐隐，便于压字
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(box_y, box_y + 160):
        a = int(255 * (1 - (i - box_y) / 160))
        d.line([(0, i), (W, i)], fill=(8, 11, 16, a))
    for i in range(box_y + box_h - 220, box_y + box_h):
        a = int(255 * ((i - (box_y + box_h - 220)) / 220))
        d.line([(0, i), (W, i)], fill=(6, 8, 12, a))
    return img


def render_photo(spec_meta, scene, W, H) -> Image.Image:
    img = _photo_layer(scene, W, H)
    d = ImageDraw.Draw(img)
    section_header(img, scene["section"])
    caption_band(img, scene.get("caption", ""))
    # 授权署名（小字，左下）
    credit = scene.get("credit", "")
    if credit:
        fc = F_REG(24)
        d.text((44, H - 92), credit, font=fc, fill=(150, 160, 172))
    # 若该镜头还需叠加官方集锦，右下角给出提示（与左下署名分居两侧，互不遮挡）
    slot = scene.get("slot")
    if slot:
        fnt = F_BOLD(26)
        tag = "示意图 · 可替换 / 叠加官方集锦"
        tw = fnt.getlength(tag) + 40
        ty = H - 100
        d.rounded_rectangle([W - 44 - tw, ty, W - 44, ty + 46], radius=10,
                            fill=(0, 0, 0), outline=YELLOW, width=2)
        d.text((W - 44 - tw + 20, ty + 8), tag, font=fnt, fill=YELLOW)
    brand_mark(img, spec_meta["brand"])
    progress_dots(img, scene.get("index", 0))
    return img


def render_placeholder(spec_meta, scene, W, H) -> Image.Image:
    img = gradient_bg(W, H)
    d = ImageDraw.Draw(img)
    section_header(img, scene["section"])
    slot = scene["slot"]
    # 居中占位框
    bx0, by0, bx1, by1 = 90, int(H * 0.34), W - 90, int(H * 0.70)
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=28, outline=YELLOW, width=4)
    for gx in range(bx0 + 20, bx1, 60):  # 斜纹表示待填充
        d.line([(gx, by0 + 4), (max(bx0 + 4, gx - (by1 - by0)), by1 - 4)],
               fill=(38, 46, 60), width=2)
    play_c = ((bx0 + bx1) / 2, (by0 + by1) / 2 - 60)
    d.ellipse([play_c[0] - 70, play_c[1] - 70, play_c[0] + 70, play_c[1] + 70],
              outline=YELLOW, width=5)
    d.polygon([(play_c[0] - 24, play_c[1] - 34), (play_c[0] - 24, play_c[1] + 34),
               (play_c[0] + 40, play_c[1])], fill=YELLOW)
    f1 = F_BOLD(48)
    draw_center_text(d, W / 2, play_c[1] + 90, "插入官方授权集锦", f1, YELLOW)
    f2 = F_REG(34)
    for i, ln in enumerate(wrap_cjk(slot["desc"], f2, bx1 - bx0 - 80)):
        draw_center_text(d, W / 2, play_c[1] + 160 + i * 46, ln, f2, WHITE)
    f3 = F_REG(30)
    draw_center_text(d, W / 2, by1 - 60, f"素材来源：{slot['source']} · 约 {slot['secs']} 秒",
                     f3, MUTED)
    caption_band(img, scene.get("caption", ""))
    brand_mark(img, spec_meta["brand"])
    progress_dots(img, scene.get("index", 0))
    return img


RENDERERS = {
    "title": render_title,
    "section": render_section,
    "photo": render_photo,
    "placeholder": render_placeholder,
}


def srt_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(scenes, path: Path):
    lines, t = [], 0.0
    idx = 1
    for sc in scenes:
        vo = sc.get("vo", "").strip()
        dur = float(sc["dur"])
        if vo:
            lines.append(str(idx))
            lines.append(f"{srt_time(t)} --> {srt_time(t + dur)}")
            lines.append(vo)
            lines.append("")
            idx += 1
        t += dur
    path.write_text("\n".join(lines), encoding="utf-8")


def try_tts(scenes, meta, outdir: Path, ff: str) -> Path | None:
    """尽力用 edge-tts 合成中文配音；网络不可用时返回 None。"""
    try:
        import asyncio
        import ssl

        import edge_tts
        import edge_tts.communicate as ec

        ca = "/root/.ccr/ca-bundle.crt"
        if Path(ca).exists():
            ec._SSL_CTX = ssl.create_default_context(cafile=ca)

        voice = meta.get("voice", "zh-CN-YunjianNeural")
        rate = meta.get("voice_rate", "+8%")
        clips = []

        async def synth(text, dst):
            await edge_tts.Communicate(text, voice, rate=rate).save(str(dst))

        tdir = outdir / "_tts"
        tdir.mkdir(exist_ok=True)
        for i, sc in enumerate(scenes):
            vo = sc.get("vo", "").strip()
            dst = tdir / f"vo_{i:02d}.mp3"
            if vo:
                asyncio.run(synth(vo, dst))
            else:  # 无台词镜头填静音，保持与画面对齐
                subprocess.run([ff, "-y", "-f", "lavfi", "-i",
                                f"anullsrc=r=24000:cl=mono", "-t", "0.6",
                                str(dst)], check=True, capture_output=True)
            # 垫到镜头时长，确保音画同步
            padded = tdir / f"pad_{i:02d}.mp3"
            subprocess.run([ff, "-y", "-i", str(dst), "-af",
                            f"apad=whole_dur={float(sc['dur'])}", "-t",
                            str(float(sc["dur"])), str(padded)],
                           check=True, capture_output=True)
            clips.append(padded)
        listf = tdir / "list.txt"
        listf.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
        out = outdir / "voiceover.mp3"
        subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(listf),
                        "-c", "copy", str(out)], check=True, capture_output=True,
                       cwd=str(tdir))
        return out
    except Exception as exc:
        print(f"  · TTS 不可用，跳过自动配音（{type(exc).__name__}）。"
              f"请用 captions.srt / narration.txt 自行配音。")
        return None


def storyboard_sheet(frame_paths, path: Path, cols=4):
    thumbs = [Image.open(p).resize((270, 480)) for p in frame_paths]
    rows = (len(thumbs) + cols - 1) // cols
    pad = 12
    sheet = Image.new("RGB", (cols * 270 + (cols + 1) * pad,
                              rows * 480 + (rows + 1) * pad), (18, 20, 26))
    for i, th in enumerate(thumbs):
        r, c = divmod(i, cols)
        sheet.paste(th, (pad + c * (270 + pad), pad + r * (480 + pad)))
    sheet.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="data/grand_slam_video.json")
    ap.add_argument("--outdir", default="output/grand-slam-vertical")
    ap.add_argument("--voiceover", default=None)
    ap.add_argument("--tts", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    ff = _ffmpeg()
    spec = json.loads((ROOT / args.spec).read_text(encoding="utf-8"))
    meta = spec["meta"]
    W, H, FPS = meta["width"], meta["height"], meta["fps"]
    scenes = spec["scenes"]

    outdir = ROOT / args.outdir
    final = outdir / "grand-slam.mp4"
    if final.exists() and not args.overwrite:
        sys.exit(f"{final} 已存在，加 --overwrite 覆盖。")
    frames_dir = outdir / "frames"
    clips_dir = outdir / "_clips"
    for d in (outdir, frames_dir, clips_dir):
        d.mkdir(parents=True, exist_ok=True)

    print(f"合成 {len(scenes)} 个镜头 …")
    frame_paths, clip_paths = [], []
    for i, sc in enumerate(scenes):
        img = RENDERERS[sc["type"]](meta, sc, W, H)
        fp = frames_dir / f"{sc['id']}.png"
        img.save(fp)
        frame_paths.append(fp)

        dur = float(sc["dur"])
        clip = clips_dir / f"{i:02d}.mp4"
        nframes = int(dur * FPS)
        # 轻微 Ken Burns（整帧缓慢放大 5%）+ 淡入淡出
        vf = (
            f"scale={W}:{H},zoompan=z='min(zoom+0.00045,1.05)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={nframes}:s={W}x{H}:fps={FPS},"
            f"fade=t=in:st=0:d=0.3,fade=t=out:st={dur-0.3:.2f}:d=0.3,"
            f"format=yuv420p"
        )
        subprocess.run([ff, "-y", "-loop", "1", "-i", str(fp), "-t", f"{dur}",
                        "-r", str(FPS), "-vf", vf, "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", str(clip)],
                       check=True, capture_output=True)
        clip_paths.append(clip)
        print(f"  [{i+1:2d}/{len(scenes)}] {sc['id']} ({dur:.0f}s)")

    listf = clips_dir / "concat.txt"
    listf.write_text("".join(f"file '{c.name}'\n" for c in clip_paths), encoding="utf-8")
    silent = outdir / "_silent.mp4"
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(listf),
                    "-c", "copy", str(silent)], check=True, capture_output=True,
                   cwd=str(clips_dir))

    total = sum(float(s["dur"]) for s in scenes)

    # 配音音轨
    audio = None
    if args.voiceover:
        audio = ROOT / args.voiceover
    elif args.tts:
        audio = try_tts(scenes, meta, outdir, ff)

    if audio and Path(audio).exists():
        subprocess.run([ff, "-y", "-i", str(silent), "-i", str(audio),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-shortest", str(final)], check=True, capture_output=True)
    else:  # 无配音：写入静音轨，方便平台上传
        subprocess.run([ff, "-y", "-i", str(silent), "-f", "lavfi", "-i",
                        f"anullsrc=r=44100:cl=stereo", "-c:v", "copy",
                        "-c:a", "aac", "-t", f"{total:.2f}", "-shortest",
                        str(final)], check=True, capture_output=True)

    # 附属产物
    write_srt(scenes, outdir / "captions.srt")
    (outdir / "narration.txt").write_text(
        "\n".join(s["vo"].strip() for s in scenes if s.get("vo")), encoding="utf-8")
    shutil.copy(frame_paths[0], outdir / "cover.png")
    storyboard_sheet(frame_paths, outdir / "storyboard.png")

    # 清理中间产物
    shutil.rmtree(clips_dir, ignore_errors=True)
    silent.unlink(missing_ok=True)
    shutil.rmtree(outdir / "_tts", ignore_errors=True)

    size_mb = final.stat().st_size / 1e6
    print(f"\n完成：{final}  ({total:.0f}s, {size_mb:.1f} MB)")
    print(f"  分镜连拍：{outdir/'storyboard.png'}")
    print(f"  字幕：{outdir/'captions.srt'}  文案：{outdir/'narration.txt'}")
    if not (audio and Path(audio).exists()):
        print("  · 当前为静音样片：用剪映/CapCut 的文本朗读或人声，按 captions.srt 配音即可。")


if __name__ == "__main__":
    main()
