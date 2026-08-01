#!/usr/bin/env python3
"""从本场源片里挑封面用的人物近景，给「赛场之上」的抠图用。

**为什么要有这个工具**：封面的两个人以前用官方棚拍抠图（WTA 的
`<Name>-Torso_<id>.png`、ATP 的 `player-gladiator-image`）。棚拍的毛病是
**和这场球没关系**——衣服不是本场的，光也不是本场的，压在本场画面上像两张
贴纸。账号所有者的原话：「因为更贴近比赛的服装，感觉会更好，用之前资料就有点
脱节」。

顺带还赢在分辨率，这个能量：ATP 官方抠图裁到胯只有 265×410，铺到模板 634px
的槽位是 **1.55× 放大**；同一场源片抓的近景是 660×1040，**0.61× 缩小**。
棚拍图看着"正规"，实际是全套素材里最软的一档。

挑帧的判据是账号所有者给的三条，这里逐条落成可计算的量：

1. **正脸或稍微侧脸** —— 正面人脸检测命中，且**两只眼睛都检出**。
   侧脸只能检出一只眼（或零只），这一条就是拿它分开的
2. **上半身直立** —— 头在人像框的上部，且这一小段**帧间运动小**：
   跑动、挥拍、扑救的瞬间身体是斜的，静止下来才立得直
3. **能看到表情** —— 脸够大（默认 ≥110px）且够清楚（脸部区域的
   Laplacian 方差）。糊掉的脸没有表情可言

还有一条不是账号所有者说的、是踩出来的：**排除观众席**。看台近景里一帧能检出
七八张脸，尺寸和球员近景一样大。同帧检出的人脸数超过 `--max-faces` 就整帧丢掉。

**不合格的也要列出来**，并写明卡在哪一条——只报成功的检查没法证明它真看过。

    python tools/pick_cover_frames.py --video src.mp4 --out /tmp/cand --top 12

产物是一张 contact sheet 加每个候选的原图裁切，**最后一步是人打开看**：
谁是谁、表情对不对题，机器判不了。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 判据的默认值，**都是在这条源片上量出来的**，不是拍的。改之前先重量一遍。
MIN_FACE = 110          # 脸的边长（px）。再小表情就读不出来了
# 清晰度要**把脸缩到同一个尺寸再算**。第一版直接在原尺寸 ROI 上求 Laplacian
# 方差，结果和放大倍率成反比——371px 的近景 17.6，198px 的中景 123.9，
# 于是 40 这个门槛把**所有近景**都判成"糊"，过闸 0 帧。缩到 128×128 之后：
#
#     已经打开看过、判为可用的近景   170 ~ 245
#     真糊的那一档（远景、动态模糊）    5 ~  25
#
# 60 落在两者中间。这就是「门槛的数要在同一个口径下量」那条。
SHARP_SIDE = 128
MIN_SHARP = 60.0
MAX_FACES = 2           # 同帧检出的人脸数上限，超了当观众席丢掉
HEAD_ROOM = 0.55        # 脸的中心要落在人像框的上 55% 里（上半身直立）
# 运动量**只参与排序，不设闸**。同样是量出来的：几帧我已经打开看过、确认是
# 站着不动的近景，与 0.2 秒前那帧的平均绝对差是 19~25——把门槛设在 12 会把
# 正确答案全部拒掉。转播机位本身在微调、看台一直在动，这个数量的不是球员。


def _cascades():
    import cv2  # noqa: PLC0415

    base = cv2.data.haarcascades
    return (cv2.CascadeClassifier(base + "haarcascade_frontalface_default.xml"),
            cv2.CascadeClassifier(base + "haarcascade_eye.xml"))


def scan(video: Path, step: float, min_face: int, max_faces: int) -> list[dict]:
    """逐帧过一遍，把每个候选连同它卡在哪一条一起记下来。"""
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    face_cc, eye_cc = _cascades()
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    stride = max(1, int(round(fps * step)))
    lag = max(1, int(round(fps * 0.2)))

    ring: dict[int, "np.ndarray"] = {}
    out: list[dict] = []
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        ring[idx] = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        ring.pop(idx - lag * 3, None)
        if idx % stride == 0:
            grey = ring[idx]
            faces = face_cc.detectMultiScale(grey, 1.15, 6,
                                             minSize=(min_face, min_face))
            rec = {"t": round(idx / fps, 2), "faces": len(faces)}
            if len(faces) == 0:
                out.append({**rec, "drop": "没有正面人脸"})
            elif len(faces) > max_faces:
                out.append({**rec, "drop": f"同帧 {len(faces)} 张脸，观众席"})
            else:
                x, y, w, h = max(faces, key=lambda f: f[2])
                roi = grey[y:y + h, x:x + w]
                eyes = eye_cc.detectMultiScale(roi, 1.1, 6,
                                               minSize=(h // 8, h // 8))
                sharp = float(cv2.Laplacian(
                    cv2.resize(roi, (SHARP_SIDE, SHARP_SIDE)), cv2.CV_64F).var())
                prev = ring.get(idx - lag)
                motion = 0.0
                if prev is not None:
                    band = (slice(max(0, y - h), min(grey.shape[0], y + h * 3)),
                            slice(max(0, x - w), min(grey.shape[1], x + w * 2)))
                    motion = float(np.mean(np.abs(
                        grey[band].astype(np.int16) - prev[band].astype(np.int16))))
                out.append({**rec, "x": int(x), "y": int(y), "w": int(w),
                            "h": int(h), "eyes": int(len(eyes)),
                            "sharp": round(sharp, 1),
                            "motion": round(motion, 2)})
        idx += 1
    cap.release()
    return out


def judge(rec: dict, *, min_face: int, min_sharp: float, height: int) -> str:
    """三条闸门，返回卡在哪一条；空串＝全过。"""
    if rec.get("drop"):
        return rec["drop"]
    if rec["eyes"] < 2:
        return f"侧脸（只检出 {rec['eyes']} 只眼）"
    if rec["h"] < min_face:
        return f"脸太小 {rec['h']}px"
    if rec["sharp"] < min_sharp:
        return f"脸糊 {rec['sharp']}"
    if (rec["y"] + rec["h"] / 2) / height > HEAD_ROOM:
        return "头压在画面下半"
    return ""


def score(rec: dict) -> float:
    """过闸之后按「脸大 + 清楚 + 站得住」排。运动量是罚分，不是闸。"""
    return rec["h"] * 2.0 + min(rec["sharp"], 400.0) * 0.3 - rec["motion"] * 2.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--step", type=float, default=0.4, help="采样间隔（秒）")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--min-face", type=int, default=MIN_FACE)
    ap.add_argument("--min-sharp", type=float, default=MIN_SHARP)
    ap.add_argument("--max-faces", type=int, default=MAX_FACES)
    ap.add_argument("--until", type=float, default=None,
                    help="只看这一秒之前。片尾的订阅卡/静态图里也会检出人脸，"
                         "而且分数极高（同一张图连着几十帧、数值一模一样）")
    args = ap.parse_args()

    try:
        import cv2  # noqa: PLC0415, F401
    except ImportError:
        print("要 opencv：pip install -e '.[visualqa]'（别直接装 "
              "opencv-python-headless，5.x 里没有 CascadeClassifier）",
              file=sys.stderr)
        return 2
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415

    args.out.mkdir(parents=True, exist_ok=True)
    probe = cv2.VideoCapture(str(args.video))
    height = int(probe.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080
    probe.release()

    recs = scan(args.video, args.step, args.min_face, args.max_faces)
    if args.until is not None:
        recs = [r for r in recs if r["t"] <= args.until]
    for rec in recs:
        rec["why"] = judge(rec, min_face=args.min_face, min_sharp=args.min_sharp,
                           height=height)
    keep = sorted((r for r in recs if not r["why"]), key=score, reverse=True)

    # **不合格的也报出来**：只列通过的检查，没法证明它真看过整条片子。
    dropped: dict[str, int] = {}
    for rec in recs:
        if rec["why"]:
            dropped[rec["why"].split("（")[0].split(" ")[0]] = (
                dropped.get(rec["why"].split("（")[0].split(" ")[0], 0) + 1)
    print(f"采样 {len(recs)} 帧，过闸 {len(keep)} 帧")
    for why, n in sorted(dropped.items(), key=lambda kv: -kv[1]):
        print(f"  丢弃 {n:4d}  {why}")

    picks = keep[:args.top]
    tiles = []
    for i, rec in enumerate(picks):
        cap = cv2.VideoCapture(str(args.video))
        cap.set(cv2.CAP_PROP_POS_MSEC, rec["t"] * 1000)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            continue
        # **候选帧存 JPEG，不是 PNG。** 量出来（1920×1080 的转播帧）：
        # PNG 单张 0.7~0.8 MB，12 张约 9 MB；q92 的 JPEG 单张 132 KB，
        # 12 张 1.6 MB，**小六倍**。挑帧是给人看的中间物，看不出差别。
        # 两种都过得了清理那道「单个 8 MB」的兜底——按单张设的闸拦不住按批次
        # 累积的量，所以整帧另外还要显式删掉，见工作流里的清理步骤。
        path = args.out / f"cand_{i:02d}_t{rec['t']}.jpg"
        Image.fromarray(frame[:, :, ::-1]).save(path, quality=92)
        print(f"  #{i:02d} {rec['t']:7.2f}s 脸 {rec['h']}px 清晰 {rec['sharp']} "
              f"运动 {rec['motion']} → {path.name}")
        tiles.append((f"#{i:02d} {rec['t']}s {rec['h']}px", Image.open(path)))

    if tiles:
        # 一格 640px：候选墙是**唯一进仓库的那份**，得看得出正脸和表情。
        # 420px 那一版，371px 的脸缩到 81px，判不了「能不能看到表情」。
        tw = 640
        thumbs = [(t, im.resize((tw, round(im.height * tw / im.width))))
                  for t, im in tiles]
        cols = 4
        rows = (len(thumbs) + cols - 1) // cols
        th = thumbs[0][1].height
        sheet = Image.new("RGB", (tw * cols, (th + 34) * rows), "#111")
        d = ImageDraw.Draw(sheet)
        try:
            f = ImageFont.truetype(
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 22)
        except OSError:
            f = ImageFont.load_default()
        for i, (t, im) in enumerate(thumbs):
            x, y = (i % cols) * tw, (i // cols) * (th + 34)
            d.text((x + 8, y + 6), t, font=f, fill="#c6f65a")
            sheet.paste(im, (x, y + 34))
        sheet.save(args.out / "sheet.jpg", quality=88)
        print(f"contact sheet → {args.out / 'sheet.jpg'} {sheet.size}")

    (args.out / "candidates.json").write_text(
        json.dumps(recs, ensure_ascii=False, indent=1), encoding="utf-8")
    # **最后一步是人打开看**：谁是谁、表情对不对题，机器判不了。
    return 0 if picks else 1


if __name__ == "__main__":
    sys.exit(main())
