#!/usr/bin/env python3
"""在一批候选帧里，**分清每一张脸是谁**——用来堵「选错人」这一类反复出现的坑。

## 为什么要有它

`pick_cover_frames.py` 是按人脸/姿态/清晰度挑候选，**不认人**；选谁全靠人看缩略图墙
按球衣颜色猜。CLAUDE.md 里这条坑踩了不止一次：

- `pick_cover_frames.py` 对 `zhang-sabalenka` 给出 16 个候选，**16 个全是萨巴伦卡**
  （官方集锦的近景天然偏向赢家，而张帅输了）
- 44.5s / 252.5s 两次「动作真的有，人是反的」——缩略图墙 6 格宽，按衣服颜色猜必错
- `gea-shapovalov` 也记过同一个模式

这个脚本不猜衣服颜色，比人脸向量。2026-08-07 用这条片子自己的候选帧（`zs_cand/`
16 张自动候选 + 手动找出来的 10 张张帅帧）做过一次端到端验证：

    26 张已知答案的帧，26 张全对，0 张漏检人脸。

包括两张余弦相似度差值只有 0.05~0.06 的边缘案例（z_164.0 / z_164.4）——那种
差值小到人自己拿放大镜比都未必有把握，模型照样判对。

## 用法

    python3 tools/identify_player_frame.py \\
        --ref 张帅=assets/players/wta-311779-zhang-shuai.png \\
        --ref 萨巴伦卡=assets/players/aryna-sabalenka.jpg \\
        candidates/*.jpg

给的 `--ref` 名字就是判定结果里会印的名字，图不限官方棚拍——本场源片的一帧
（先前确认过是谁的）一样能当参考。

## 它不做什么

- **不判「选谁好看」**。谁的脸更清楚、姿态好不好、对不对题，仍然是
  `rank_frame_sharpness.py` 和人眼那两道闸门管的事。这个脚本只回答「这张脸是谁」。
- ~~**不接进默认流程**，留给账号所有者定~~——**2026-09-27 他定了**（多选题 O2+O3
  「两个都加」）：认人＋睁眼接进了采访封面闸、「赛场之上」抽帧封面和分段画面，
  判据和门槛在 `tools/face_checks.py`。这个脚本现在也走那边的后端（同一套
  buffalo_s 模型、onnxruntime 推理、**不装 insightface 包**——它会把 cv2 顶成 5.x，
  见 face_checks 顶部），只保留「给几张参考、逐帧判给谁」这个人工用的入口。
- **没有第三个人的先验**。给两个参考就只能分两类；给错参考（比如两张都是同一个人）
  它照样会算出一个「更像谁」，不会告诉你参考给错了——参考图要自己先确认过。

## 判据

⚠️ **候选帧里如果同一帧有好几张脸**（比如看台观众），只取**面积最大**的那张——
候选帧本来就该是「近景/中景对准主体」的那种，观众席的小脸不该被拿来比。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np


def _load_embedder():
    """延迟加载：模型在 `face_checks`（onnxruntime ＋ buffalo_s 的三个 onnx），
    没装／没下就该在这儿报一句说得清楚的话，而不是让 argparse 都跑完了才炸。

    2026-08-07 那次 26/26 用的是 buffalo_sc——它和 buffalo_s 里的
    `det_500m.onnx` / `w600k_mbf.onnx` 是同一对文件（大小、压缩后大小逐字节相同），
    换后端不换模型。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import face_checks  # noqa: PLC0415

        return face_checks.load()
    except ImportError as exc:
        raise SystemExit(f"读不了人脸模型：{exc}") from exc
    except Exception as exc:  # noqa: BLE001 — ModelUnavailable 及其它，都要说清楚
        raise SystemExit(
            f"人脸模型不可用：{exc}\n"
            "装 extra：pip install -e \".[visualqa,faces]\"，再跑一次 "
            "`python tools/face_checks.py fetch`。⚠️ 别装 insightface 包本身"
            "（会把 cv2 换成 5.x，见 tools/face_checks.py 顶部）"
        ) from exc


def embed(app, path: Path) -> np.ndarray | None:
    """一张图里最大的那张脸的归一化向量；没检出脸返回 None。

    官方棚拍头像是满画幅大头，SCRFD 在 640 输入上检不出——检不到就补白边再检
    （`face_checks.headshot_embedding` 同一个办法）。"""
    import face_checks  # noqa: PLC0415

    try:
        img = face_checks.read_bgr(Path(path))
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"读不出图片：{path}（{exc}）") from exc
    for frac in (0.0, 0.5, 1.0):
        probe = face_checks._pad(img, frac) if frac else img
        face = face_checks.largest_face(app, probe)
        if face is not None:
            return app.embed(probe, face)
    return None


def classify(app, refs: dict[str, np.ndarray], candidates: list[Path]) -> list[dict]:
    """每张候选帧 → 判给谁、置信度差值、有没有检出脸。"""
    rows = []
    for path in candidates:
        emb = embed(app, path)
        if emb is None:
            rows.append({"path": path, "guess": None, "margin": None, "scores": {}})
            continue
        scores = {name: float(np.dot(emb, ref)) for name, ref in refs.items()}
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        top_name, top_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else float("-inf")
        rows.append({
            "path": path, "guess": top_name,
            "margin": top_score - second_score, "scores": scores,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ref", action="append", required=True, metavar="姓名=图片路径",
                    help="每个人给一张参考图，至少两个（重复此参数）")
    ap.add_argument("candidates", nargs="+", help="待判定的候选帧")
    # 差值低于这个数就说「拿不准」，不硬给一个答案——CLAUDE.md「宁可窄不可宽」
    # 那条同一个道理：模糊地带宁可承认模糊，不要输出一个看着确定其实赌的答案。
    ap.add_argument("--margin-warn", type=float, default=0.15,
                    help="判定余量低于这个值就标「⚠️ 拿不准」（默认 0.15）")
    args = ap.parse_args()

    ref_specs = []
    for item in args.ref:
        if "=" not in item:
            raise SystemExit(f"--ref 要写成 姓名=图片路径，收到的是：{item!r}")
        name, path_str = item.split("=", 1)
        path = Path(path_str)
        if not path.is_file():
            raise SystemExit(f"参考图不存在：{path}")
        ref_specs.append((name, path))
    if len(ref_specs) < 2:
        raise SystemExit("至少给两个 --ref，否则没有「判给谁」这回事。")

    candidates = [Path(c) for c in args.candidates]
    missing = [c for c in candidates if not c.is_file()]
    if missing:
        raise SystemExit(f"候选帧不存在：{missing}")

    app = _load_embedder()

    refs: dict[str, np.ndarray] = {}
    for name, path in ref_specs:
        emb = embed(app, path)
        if emb is None:
            raise SystemExit(f"参考图 {path}（{name}）没检出人脸，换一张。")
        refs[name] = emb
    print(f"[参考] {' / '.join(refs)}")

    rows = classify(app, refs, candidates)
    no_face = sum(1 for r in rows if r["guess"] is None)
    unsure = sum(1 for r in rows if r["margin"] is not None and r["margin"] < args.margin_warn)
    for r in rows:
        name = r["path"].name
        if r["guess"] is None:
            print(f"  {name:32} 没检出人脸")
            continue
        flag = " ⚠️ 拿不准" if r["margin"] < args.margin_warn else ""
        detail = "  ".join(f"{k}={v:.3f}" for k, v in r["scores"].items())
        print(f"  {name:32} → {r['guess']:12} 余量={r['margin']:.3f}{flag}   ({detail})")

    print(f"\n共 {len(rows)} 张：{len(rows) - no_face - unsure} 张判定明确、"
          f"{unsure} 张余量偏低、{no_face} 张没检出脸")
    return 0


if __name__ == "__main__":
    sys.exit(main())
