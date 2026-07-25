"""生成《网球四大满贯》竖屏科普样片（1080×1920）。

按 data/grand_slam_video.json 的分镜规格，用 Pillow 合成每个镜头（电影感「灯光球场」
背景 + 亮色大标题 + 赛事分区 + 底部描边字幕），再用 ffmpeg 加轻微 Ken Burns、
淡入淡出并拼接成片。

版权：静态画面只用仓库内可复用授权图（CC / 公有领域），片中**不烧录署名**，署名改由
`发布文案.txt` 的致谢承载（CC 许可要求署名，公有领域/CC0 除外）；需要官方比赛画面的
镜头输出醒目占位卡，由你在拿到授权后填入。脚本没有下载器，不抓取任何受版权保护的视频。

用法：
    pip install Pillow imageio-ffmpeg
    python tools/build_grand_slam_short.py --overwrite

可选：--voiceover a.mp3（自备/授权配音）、--tts（edge-tts，需可访问语音服务）、--overwrite
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

YELLOW = (245, 190, 40)
YELLOW_SHADOW = (110, 20, 10)
WHITE = (245, 247, 250)
MUTED = (155, 167, 182)


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover
        sys.exit(f"找不到 ffmpeg，请 `pip install imageio-ffmpeg`（{exc}）")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def F_BLACK(sz):
    return font("NotoSerifSC-Black-sub.ttf", sz)


def F_BOLD(sz):
    return font("NotoSansSC-Bold-sub.ttf", sz)


def F_REG(sz):
    return font("NotoSansSC-Regular-sub.ttf", sz)


def F_LATIN(sz):
    return font("BarlowCondensed-Bold.ttf", sz)


def hex2rgb(s: str):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------------------
# 电影感背景：深色渐变 + 球场聚光 + 透视球场线 + 暗角
# ---------------------------------------------------------------------------
def cinematic_bg(w: int, h: int, accent=(245, 190, 40)) -> Image.Image:
    top, mid, bot = (6, 8, 13), (14, 19, 28), (4, 6, 10)
    col = Image.new("RGB", (1, h))
    cpx = col.load()
    for y in range(h):
        t = y / h
        if t < 0.5:
            f, a, b_ = t / 0.5, top, mid
        else:
            f, a, b_ = (t - 0.5) / 0.5, mid, bot
        cpx[0, y] = tuple(int(a[k] + (b_[k] - a[k]) * f) for k in range(3))
    base = col.resize((w, h))

    # 上方聚光晕（用 accent 淡淡上色）
    glow = Image.new("L", (w, h), 0)
    gd = ImageDraw.Draw(glow)
    cx, cy, rad = w // 2, int(h * 0.30), int(w * 0.72)
    gd.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=90)
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    tint = Image.new("RGB", (w, h), tuple(min(255, int(c * 0.9 + 30)) for c in accent))
    base = Image.composite(Image.blend(base, tint, 0.5), base, glow)

    # 透视球场线（低透明度，营造“站在场上”）
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    lc = (*accent, 46)
    yb, yf = int(h * 0.92), int(h * 0.60)
    bl, br = int(w * 0.06), int(w * 0.94)
    fl, fr = int(w * 0.40), int(w * 0.60)
    od.line([(bl, yb), (fl, yf)], fill=lc, width=3)   # 左边线
    od.line([(br, yb), (fr, yf)], fill=lc, width=3)   # 右边线
    od.line([(bl, yb), (br, yb)], fill=lc, width=3)   # 底线
    ys = int(yf + (yb - yf) * 0.45)                    # 发球线
    sl = bl + (fl - bl) * 0.45
    sr = br + (fr - br) * 0.45
    od.line([(sl, ys), (sr, ys)], fill=lc, width=2)
    od.line([((bl + br) / 2, yb), ((fl + fr) / 2, yf)], fill=(*accent, 30), width=2)  # 中线
    base = Image.alpha_composite(base.convert("RGBA"), ov).convert("RGB")

    # 暗角
    vig = Image.new("L", (w, h), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse([-int(w * 0.35), -int(h * 0.18), int(w * 1.35), int(h * 1.18)], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(220))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    base = Image.composite(base, dark, vig)
    return base


def fit_cover(img, box_w, box_h, focal=(0.5, 0.5)):
    src_w, src_h = img.size
    scale = max(box_w / src_w, box_h / src_h)
    nw, nh = int(src_w * scale + 0.5), int(src_h * scale + 0.5)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = max(0, min(int((nw - box_w) * focal[0]), nw - box_w))
    top = max(0, min(int((nh - box_h) * focal[1]), nh - box_h))
    return img.crop((left, top, left + box_w, top + box_h))


def rounded(img: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width, img.height], radius, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def wrap_cjk(text, fnt, max_w):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if fnt.getlength(cur + ch) <= max_w or not cur:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def center(draw, cx, y, text, fnt, fill, shadow=None, off=(6, 7)):
    x = cx - fnt.getlength(text) / 2
    if shadow:
        draw.text((x + off[0], y + off[1]), text, font=fnt, fill=shadow)
    draw.text((x, y), text, font=fnt, fill=fill)


def outline(draw, xy, text, fnt, fill=WHITE, oc=(0, 0, 0), width=5):
    x, y = xy
    for dx in range(-width, width + 1):
        for dy in range(-width, width + 1):
            if dx * dx + dy * dy <= width * width:
                draw.text((x + dx, y + dy), text, font=fnt, fill=oc)
    draw.text((x, y), text, font=fnt, fill=fill)


def brand_mark(img, brand):
    d = ImageDraw.Draw(img)
    f = F_BOLD(34)
    pad = 44
    d.rounded_rectangle([pad, pad, pad + 26 + f.getlength(brand) + 40, pad + 64],
                        radius=14, fill=(0, 0, 0), outline=YELLOW, width=2)
    d.ellipse([pad + 16, pad + 22, pad + 36, pad + 42], fill=YELLOW)
    d.text((pad + 48, pad + 12), brand, font=f, fill=WHITE)


def progress_dots(img, active):
    if not active:
        return
    d = ImageDraw.Draw(img)
    W = img.width
    gap, r = 46, 9
    x0 = W / 2 - (3 * gap) / 2
    y = img.height - 150
    for i in range(4):
        cx = x0 + i * gap
        on = (i + 1) == active
        if on:
            d.ellipse([cx - r - 3, y - r - 3, cx + r + 3, y + r + 3], fill=(0, 0, 0))
        d.ellipse([cx - r, y - r, cx + r, y + r], fill=YELLOW if on else (70, 78, 92))


def section_header(img, section):
    d = ImageDraw.Draw(img)
    W = img.width
    color = hex2rgb(section["color"])
    y = 150
    center(d, W / 2, y, section.get("en", ""), F_LATIN(60), YELLOW)
    center(d, W / 2, y + 74, section.get("zh", ""), F_BOLD(46), WHITE)
    surface = section.get("surface", "")
    if surface:
        ft = F_BOLD(32)
        tw = ft.getlength(surface) + 56
        bx0 = W / 2 - tw / 2
        by0 = y + 150
        d.rounded_rectangle([bx0, by0, bx0 + tw, by0 + 52], radius=26, fill=color)
        center(d, W / 2, by0 + 8, surface, ft, (8, 10, 14))


def caption_band(img, caption):
    if not caption:
        return
    d = ImageDraw.Draw(img, "RGBA")
    W, H = img.size
    fnt = F_BOLD(60)
    lines = wrap_cjk(caption, fnt, W - 150)
    lh = 82
    y0 = H - 300 - lh * len(lines)
    for i, ln in enumerate(lines):
        x = W / 2 - fnt.getlength(ln) / 2
        outline(d, (x, y0 + i * lh), ln, fnt, fill=WHITE, oc=(0, 0, 0), width=6)


def render_title(meta, scene, W, H):
    accent = hex2rgb(scene.get("accent", "#f2b32a"))
    img = cinematic_bg(W, H, accent)
    d = ImageDraw.Draw(img)
    big = scene.get("big", [])
    fnt = F_BLACK(180)
    y = H / 2 - len(big) * 105 - 130
    for line in big:
        center(d, W / 2, y, line, fnt, YELLOW, shadow=YELLOW_SHADOW, off=(8, 10))
        y += 210
    if scene.get("sub"):
        center(d, W / 2, y + 24, scene["sub"], F_BOLD(50), WHITE)
    brand_mark(img, meta["brand"])
    return img


def render_section(meta, scene, W, H):
    accent = hex2rgb(scene.get("accent", "#f2b32a"))
    img = cinematic_bg(W, H, accent)
    d = ImageDraw.Draw(img, "RGBA")
    sec = scene["section"]
    # 背景大写城市水印
    word = sec.get("word", "")
    if word:
        fw = F_LATIN(220)
        center(d, W / 2, H / 2 - 250, word, fw, (*accent, 40))
    # 主标题
    center(d, W / 2, H / 2 - 40, sec["en"], F_LATIN(120), YELLOW,
           shadow=YELLOW_SHADOW, off=(6, 8))
    center(d, W / 2, H / 2 + 120, sec["zh"], F_BOLD(58), WHITE)
    # 场地条
    surf = sec.get("surface", "")
    ft = F_BOLD(38)
    tw = ft.getlength(surf) + 64
    bx0 = W / 2 - tw / 2
    by0 = H / 2 + 214
    d.rounded_rectangle([bx0, by0, bx0 + tw, by0 + 60], radius=30, fill=accent)
    center(d, W / 2, by0 + 9, surf, ft, (8, 10, 14))
    brand_mark(img, meta["brand"])
    progress_dots(img, scene.get("index", 0))
    return img


def render_photo(meta, scene, W, H):
    accent = hex2rgb(scene.get("accent", "#f2b32a"))
    img = cinematic_bg(W, H, accent)
    # 照片卡：圆角 + accent 发光边，浮在背景上
    card_w, card_h = W - 120, int(H * 0.52)
    card_x, card_y = 60, int(H * 0.24)
    src = Image.open(ROOT / scene["image"]).convert("RGB")
    photo = fit_cover(src, card_w, card_h, scene.get("focal", [0.5, 0.5]))
    card = rounded(photo, 32)
    # 发光
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle([card_x - 6, card_y - 6, card_x + card_w + 6, card_y + card_h + 6],
                         radius=38, outline=(*accent, 180), width=6)
    glow = glow.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img.convert("RGBA"), glow)
    img.paste(card, (card_x, card_y), card)
    img = img.convert("RGB")
    # 卡内上下压暗，便于分区标题/字幕
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(90):
        a = int(150 * (1 - i / 90))
        d.line([(card_x, card_y + i), (card_x + card_w, card_y + i)], fill=(6, 8, 12, a))
    section_header(img, scene["section"])
    caption_band(img, scene.get("caption", ""))
    brand_mark(img, meta["brand"])
    progress_dots(img, scene.get("index", 0))
    return img


def render_placeholder(meta, scene, W, H):
    accent = hex2rgb(scene.get("accent", "#f2b32a"))
    img = cinematic_bg(W, H, accent)
    d = ImageDraw.Draw(img)
    section_header(img, scene["section"])
    slot = scene["slot"]
    bx0, by0, bx1, by1 = 90, int(H * 0.34), W - 90, int(H * 0.70)
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=28, outline=accent, width=4)
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2 - 60
    d.ellipse([cx - 70, cy - 70, cx + 70, cy + 70], outline=accent, width=5)
    d.polygon([(cx - 24, cy - 34), (cx - 24, cy + 34), (cx + 40, cy)], fill=accent)
    center(d, W / 2, cy + 92, "插入官方授权集锦", F_BOLD(48), accent)
    for i, ln in enumerate(wrap_cjk(slot["desc"], F_REG(34), bx1 - bx0 - 80)):
        center(d, W / 2, cy + 162 + i * 46, ln, F_REG(34), WHITE)
    center(d, W / 2, by1 - 58, f"素材：{slot['source']} · 约 {slot['secs']} 秒", F_REG(30), MUTED)
    caption_band(img, scene.get("caption", ""))
    brand_mark(img, meta["brand"])
    progress_dots(img, scene.get("index", 0))
    return img


RENDERERS = {"title": render_title, "section": render_section,
             "photo": render_photo, "placeholder": render_placeholder}


def srt_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(scenes, path):
    out, t, idx = [], 0.0, 1
    for sc in scenes:
        vo = sc.get("vo", "").strip()
        dur = float(sc["dur"])
        if vo:
            out += [str(idx), f"{srt_time(t)} --> {srt_time(t + dur)}", vo, ""]
            idx += 1
        t += dur
    path.write_text("\n".join(out), encoding="utf-8")


def write_description(scenes, meta, path):
    """发布文案：标题候选 + 简介 + 话题 + 图片致谢（CC 许可需署名，放这里）。"""
    credits = []
    for sc in scenes:
        c = (sc.get("credit") or "").strip()
        if c:
            credits.append(f"· {c}")
    lines = [
        "【标题候选】",
        "网球四大满贯，一个视频看懂它们的性格",
        "四大满贯，网球人一生想征服的四座球场",
        "硬地·红土·草地，四大满贯到底有什么不同？",
        "",
        "【简介】",
        "澳网的热烈、法网的坚韧、温网的优雅、美网的疯狂——"
        "四片战场，四种荣耀。关注@" + meta["brand"] + "，一起看懂每一场巅峰对决。",
        "",
        "【话题】",
        "#网球 #四大满贯 #澳网 #法网 #温网 #美网 #网球科普 #网球时差",
        "",
        "【画面素材致谢（CC 许可要求署名，故放在简介）】",
    ]
    lines += credits if credits else ["·（若全部替换为自有/授权素材，可删除本段）"]
    lines += [
        "· 公有领域/CC0 素材无需署名；官方集锦请按你取得的授权标注。",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def try_tts(scenes, meta, outdir, ff):
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
        tdir = outdir / "_tts"
        tdir.mkdir(exist_ok=True)
        clips = []

        async def synth(text, dst):
            await edge_tts.Communicate(text, voice, rate=rate).save(str(dst))

        for i, sc in enumerate(scenes):
            vo = sc.get("vo", "").strip()
            raw = tdir / f"vo_{i:02d}.mp3"
            if vo:
                asyncio.run(synth(vo, raw))
            else:
                subprocess.run([ff, "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                                "-t", "0.5", str(raw)], check=True, capture_output=True)
            pad = tdir / f"pad_{i:02d}.mp3"
            subprocess.run([ff, "-y", "-i", str(raw), "-af",
                            f"apad=whole_dur={float(sc['dur'])}", "-t", str(float(sc["dur"])),
                            str(pad)], check=True, capture_output=True)
            clips.append(pad)
        lst = tdir / "list.txt"
        lst.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
        out = outdir / "voiceover.mp3"
        subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                        str(out)], check=True, capture_output=True, cwd=str(tdir))
        return out
    except Exception as exc:
        print(f"  · TTS 不可用，跳过自动配音（{type(exc).__name__}）。用 captions.srt / narration.txt 自行配音。")
        return None


def storyboard_sheet(frames, path, cols=4):
    thumbs = [Image.open(p).resize((270, 480)) for p in frames]
    rows = (len(thumbs) + cols - 1) // cols
    pad = 12
    sheet = Image.new("RGB", (cols * 270 + (cols + 1) * pad, rows * 480 + (rows + 1) * pad),
                      (16, 18, 24))
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
    frames_dir, clips_dir = outdir / "frames", outdir / "_clips"
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
        nframes = int(dur * FPS)
        clip = clips_dir / f"{i:02d}.mp4"
        vf = (
            f"scale={W}:{H},zoompan=z='min(zoom+0.00045,1.05)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={nframes}:s={W}x{H}:fps={FPS},"
            f"fade=t=in:st=0:d=0.3,fade=t=out:st={dur-0.3:.2f}:d=0.3,format=yuv420p"
        )
        subprocess.run([ff, "-y", "-loop", "1", "-i", str(fp), "-t", f"{dur}", "-r", str(FPS),
                        "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)],
                       check=True, capture_output=True)
        clip_paths.append(clip)
        print(f"  [{i+1:2d}/{len(scenes)}] {sc['id']} ({dur:.0f}s)")

    lst = clips_dir / "concat.txt"
    lst.write_text("".join(f"file '{c.name}'\n" for c in clip_paths), encoding="utf-8")
    silent = outdir / "_silent.mp4"
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                    str(silent)], check=True, capture_output=True, cwd=str(clips_dir))

    total = sum(float(s["dur"]) for s in scenes)
    audio = None
    if args.voiceover:
        audio = ROOT / args.voiceover
    elif args.tts:
        audio = try_tts(scenes, meta, outdir, ff)

    if audio and Path(audio).exists():
        subprocess.run([ff, "-y", "-i", str(silent), "-i", str(audio), "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)],
                       check=True, capture_output=True)
    else:
        subprocess.run([ff, "-y", "-i", str(silent), "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                        "-c:v", "copy", "-c:a", "aac", "-t", f"{total:.2f}", "-shortest",
                        str(final)], check=True, capture_output=True)

    write_srt(scenes, outdir / "captions.srt")
    (outdir / "narration.txt").write_text(
        "\n".join(s["vo"].strip() for s in scenes if s.get("vo")), encoding="utf-8")
    write_description(scenes, meta, outdir / "发布文案.txt")
    shutil.copy(frame_paths[0], outdir / "cover.png")
    storyboard_sheet(frame_paths, outdir / "storyboard.png")

    shutil.rmtree(clips_dir, ignore_errors=True)
    silent.unlink(missing_ok=True)
    shutil.rmtree(outdir / "_tts", ignore_errors=True)

    print(f"\n完成：{final}  ({total:.0f}s, {final.stat().st_size/1e6:.1f} MB)")
    print(f"  分镜连拍：{outdir/'storyboard.png'} · 字幕：{outdir/'captions.srt'} · 发布文案：{outdir/'发布文案.txt'}")
    if not (audio and Path(audio).exists()):
        print("  · 当前为静音样片：用剪映/CapCut 文本朗读或人声，按 captions.srt 配音即可。")


if __name__ == "__main__":
    main()
