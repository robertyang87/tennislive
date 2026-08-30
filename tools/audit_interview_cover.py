#!/usr/bin/env python3
"""完全本地审核《赛后开麦》最终封面；不调用任何模型或外部 API。

审核对象是已经渲成 1080×1440 的 ``poster.jpg``。本工具用 Pillow/OpenCV
完成可解码性、尺寸、构图合同、正面人脸、双眼、脸部大小与清晰度检查，并把
结果同时绑定当前 spec 和 poster 的 SHA-256。OpenCV 不可用、人脸检测不稳定、
证据缺字段或任一阈值不满足时一律 fail closed。

人物姓名来自已经过 L0 内容身份闸的 spec，不冒充人脸识别结果；本地闸证明的
是「这张与 spec 绑定的封面有一张足够大、正面、睁眼且清晰的人脸」。正确人物
由同源视频、精确 ``frame_at`` 和 spec 的 subject 合同共同约束。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

CANVAS = (1080, 1440)
PHOTO_TOP = 150
PHOTO_HEIGHT = 810
LOCAL_AUDITOR = "opencv-haar-v1"
MIN_ZOOM_CLOSE_UP = 1.50
MIN_FACE_HEIGHT_RATIO = 0.08
MIN_CLOSE_UP_FACE_HEIGHT_RATIO = 0.14
MIN_FACE_AREA_RATIO = 0.010
MIN_FACE_SHARPNESS = 45.0
MIN_FACE_CONTRAST = 32.0
MIN_EYES = 2
REPORT_NAME = "cover_visual_attestation.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _text(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("name") or value.get("value") or ""
    return str(value or "").strip()


def expected_subject(spec: dict) -> str:
    """从生产事实字段确定封面主角；认不出来就让调用方 fail closed。"""
    cover = spec.get("cover") or {}
    for value in (
        spec.get("subject"),
        spec.get("interviewee"),
        spec.get("speaker"),
        cover.get("subject"),
    ):
        if name := _text(value):
            return name

    match = spec.get("match") or {}
    kind = " ".join(
        (
            _text(spec.get("requested_content_type")),
            _text(spec.get("interview_kind")),
            _text(spec.get("source_title")),
            _text((spec.get("source_verification") or {}).get("title")),
        )
    ).lower()
    loser_content = any(
        mark in kind
        for mark in (
            "亚军",
            "告别",
            "runner-up",
            "runner up",
            "finalist",
            "farewell",
            "final match presentation",
        )
    )
    if loser_content and (loser := _text(match.get("loser"))):
        return loser

    participants = [_text(value) for value in (match.get("participants") or [])]
    participants = [value for value in participants if value]
    titles = cover.get("title") or []
    if isinstance(titles, str):
        titles = [titles]
    cover_copy = " ".join(
        _text(value) for value in (cover.get("tag"), cover.get("sub"), *titles)
    )
    named = [name for name in participants if name in cover_copy]
    if len(named) == 1:
        return named[0]
    return _text(spec.get("winner")) or _text(match.get("winner"))


def _number(value: object, default: float = -1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def framing_contract(spec: dict) -> tuple[dict, list[str]]:
    """把封面的编辑意图收敛成可机械复核的近景合同。"""
    cover = spec.get("cover") or {}
    shot_type = _text(cover.get("shot_type"))
    frame_at = _number(cover.get("frame_at"))
    # 与 build_interview_clip._cover_framing 的默认值保持同源；普通历史 spec
    # 没显式写 zoom/focus 时是 1.0/0.5，不能在审核层凭空改成非法值。
    zoom = _number(cover.get("zoom", 1.0))
    focus_y = _number(cover.get("focus_y", 0.5))
    contract = {
        "shot_type": shot_type,
        "frame_at": frame_at,
        "zoom": zoom,
        "focus_y": focus_y,
    }
    issues: list[str] = []
    if frame_at < 0:
        issues.append("cover.frame_at 必须是非负秒数")
    if not 1.0 <= zoom <= 2.4:
        issues.append(f"cover.zoom={zoom:g}，必须在 1.0–2.4")
    if not 0.0 <= focus_y <= 1.0:
        issues.append(f"cover.focus_y={focus_y:g}，必须在 0–1")
    if shot_type == "close_up" and zoom < MIN_ZOOM_CLOSE_UP:
        issues.append(f"近景封面 zoom={zoom:g}，必须 ≥ {MIN_ZOOM_CLOSE_UP:.2f}")
    return contract, issues


def _overlap_ratio(
    a: tuple[int, int, int, int], b: tuple[int, int, int, int]
) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    left, top = max(ax, bx), max(ay, by)
    right, bottom = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    intersection = max(0, right - left) * max(0, bottom - top)
    return intersection / max(1, min(aw * ah, bw * bh))


def analyze_poster(poster: Path) -> dict:
    """只用本地像素生成封面证据；依赖不完整或证据不足直接抛错。"""
    try:
        import cv2  # type: ignore  # noqa: PLC0415
        import numpy as np  # type: ignore  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "本地封面闸缺 OpenCV/Pillow；安装 pip install -e '.[visualqa]'"
        ) from exc

    try:
        with Image.open(poster) as image:
            image.verify()
        with Image.open(poster) as image:
            pil_size = image.size
            image_format = image.format or ""
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"poster 无法解码：{exc}") from exc

    raw = np.fromfile(str(poster), dtype=np.uint8)
    image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("OpenCV 无法解码 poster")
    height, width = image.shape[:2]
    if (width, height) != pil_size:
        raise RuntimeError("Pillow 与 OpenCV 读到的尺寸不一致")
    photo_bottom = min(height, PHOTO_TOP + PHOTO_HEIGHT)
    photo = image[PHOTO_TOP:photo_bottom, :]
    if photo.shape[:2] != (PHOTO_HEIGHT, CANVAS[0]):
        raise RuntimeError("poster 缺少完整的 1080×810 照片区域")
    gray = cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY)

    cascade_dir = getattr(getattr(cv2, "data", None), "haarcascades", "")
    if not cascade_dir:
        raise RuntimeError("OpenCV 未携带 Haar cascade 数据")
    found: list[tuple[int, int, int, int, str]] = []
    min_face = max(48, int(PHOTO_HEIGHT * 0.06))
    for filename, label in (
        ("haarcascade_frontalface_default.xml", "frontal-default"),
        ("haarcascade_frontalface_alt2.xml", "frontal-alt2"),
    ):
        cascade = cv2.CascadeClassifier(str(Path(cascade_dir) / filename))
        if cascade.empty():
            raise RuntimeError(f"人脸检测器不可用：{filename}")
        boxes = cascade.detectMultiScale(
            gray,
            scaleFactor=1.05,
            minNeighbors=5,
            minSize=(min_face, min_face),
        )
        found.extend((*map(int, box), label) for box in boxes)

    faces: list[tuple[int, int, int, int, str]] = []
    for item in sorted(found, key=lambda value: value[2] * value[3], reverse=True):
        box = item[:4]
        if any(_overlap_ratio(box, existing[:4]) >= 0.55 for existing in faces):
            continue
        faces.append(item)
    if not faces:
        raise RuntimeError("照片区域没有检出正面人脸")

    x, y, face_width, face_height, detector = faces[0]
    face = gray[y : y + face_height, x : x + face_width]
    if face.size == 0:
        raise RuntimeError("最大人脸区域为空")
    upper_face = face[: max(1, int(face_height * 0.68)), :]
    eyes_raw: list[tuple[int, int, int, int]] = []
    usable_eye_detectors = 0
    # 普通 eye cascade 在费德勒这张稍微眯眼的正面帧只命中一只；OpenCV 自带的
    # eyeglasses 版本能稳定命中两只。两者取并集再去重，仍然完全本地且可复现。
    for filename in ("haarcascade_eye.xml", "haarcascade_eye_tree_eyeglasses.xml"):
        eye_cascade = cv2.CascadeClassifier(str(Path(cascade_dir) / filename))
        if eye_cascade.empty():
            continue
        usable_eye_detectors += 1
        found_eyes = eye_cascade.detectMultiScale(
            upper_face,
            scaleFactor=1.03,
            minNeighbors=5,
            minSize=(max(8, face_width // 12), max(8, face_height // 12)),
        )
        eyes_raw.extend(tuple(map(int, eye)) for eye in found_eyes)
    if usable_eye_detectors != 2:
        raise RuntimeError("双眼检测器不完整")
    eyes: list[tuple[int, int, int, int]] = []
    for box in sorted(eyes_raw, key=lambda value: value[2] * value[3], reverse=True):
        if any(_overlap_ratio(box, existing) >= 0.55 for existing in eyes):
            continue
        eyes.append(box)

    normalized = cv2.resize(face, (128, 128), interpolation=cv2.INTER_AREA)
    sharpness = float(cv2.Laplacian(normalized, cv2.CV_64F).var())
    p05, p95 = (float(value) for value in np.percentile(normalized, (5, 95)))
    face_height_ratio = face_height / PHOTO_HEIGHT
    face_area_ratio = (face_width * face_height) / (CANVAS[0] * PHOTO_HEIGHT)
    face_center_x_ratio = (x + face_width / 2) / CANVAS[0]
    face_center_y_ratio = (y + face_height / 2) / PHOTO_HEIGHT
    return {
        "poster": {
            "decodable": True,
            "format": image_format,
            "width": width,
            "height": height,
            "photo_region": [0, PHOTO_TOP, CANVAS[0], PHOTO_HEIGHT],
        },
        "face": {
            "detector": detector,
            "box": [x, y + PHOTO_TOP, face_width, face_height],
            "detected_faces": len(faces),
            "eyes": len(eyes),
            "face_height_ratio": round(face_height_ratio, 5),
            "face_area_ratio": round(face_area_ratio, 5),
            "center_x_ratio": round(face_center_x_ratio, 5),
            "center_y_ratio": round(face_center_y_ratio, 5),
            "sharpness": round(sharpness, 3),
            "contrast": round(p95 - p05, 3),
        },
    }


def validate_result(result: object, spec: dict) -> list[str]:
    """机械复核本地证据；空列表才是通过。"""
    if not isinstance(result, dict):
        return ["本地审核器没有返回 JSON 对象"]
    issues: list[str] = []
    poster = result.get("poster")
    if not isinstance(poster, dict):
        issues.append("缺 poster 证据")
    else:
        if poster.get("decodable") is not True:
            issues.append("poster 不可解码")
        if poster.get("format") != "JPEG":
            issues.append(f"poster 实际格式是 {poster.get('format') or '空'}，必须是 JPEG")
        if (poster.get("width"), poster.get("height")) != CANVAS:
            issues.append(
                f"poster 尺寸为 {poster.get('width')}×{poster.get('height')}，"
                f"必须是 {CANVAS[0]}×{CANVAS[1]}"
            )
        if poster.get("photo_region") != [0, PHOTO_TOP, CANVAS[0], PHOTO_HEIGHT]:
            issues.append("poster 照片区域证据缺失或尺寸不符")

    contract, contract_issues = framing_contract(spec)
    issues.extend(contract_issues)
    if result.get("contract") != contract:
        issues.append("本地证据中的构图合同与当前 spec 不一致")

    face = result.get("face")
    if not isinstance(face, dict):
        issues.append("缺本地正面人脸证据")
        return issues
    if not str(face.get("detector") or "").startswith("frontal-"):
        issues.append("未由正面人脸检测器命中")
    eyes = int(_number(face.get("eyes"), -1))
    if eyes < MIN_EYES:
        issues.append(f"只检出 {eyes} 只眼，正面睁眼合同要求 ≥ {MIN_EYES}")
    face_height_ratio = _number(face.get("face_height_ratio"))
    face_area_ratio = _number(face.get("face_area_ratio"))
    required_height = (
        MIN_CLOSE_UP_FACE_HEIGHT_RATIO
        if contract["shot_type"] == "close_up"
        else MIN_FACE_HEIGHT_RATIO
    )
    if face_height_ratio < required_height:
        shot_label = "近景" if contract["shot_type"] == "close_up" else (
            contract["shot_type"] or "普通"
        )
        issues.append(
            f"脸部高度占照片区域 {face_height_ratio:.1%}，"
            f"{shot_label}构图要求 ≥ {required_height:.0%}"
        )
    if face_area_ratio < MIN_FACE_AREA_RATIO:
        issues.append(
            f"脸部面积占照片区域 {face_area_ratio:.2%}，"
            f"主体大小要求 ≥ {MIN_FACE_AREA_RATIO:.1%}"
        )
    sharpness = _number(face.get("sharpness"))
    if sharpness < MIN_FACE_SHARPNESS:
        issues.append(
            f"归一化脸部清晰度 {sharpness:g}，必须 ≥ {MIN_FACE_SHARPNESS:g}"
        )
    contrast = _number(face.get("contrast"))
    if contrast < MIN_FACE_CONTRAST:
        issues.append(f"脸部明暗跨度 {contrast:g}，必须 ≥ {MIN_FACE_CONTRAST:g}")
    center_x = _number(face.get("center_x_ratio"))
    center_y = _number(face.get("center_y_ratio"))
    if not 0.08 <= center_x <= 0.92 or not 0.06 <= center_y <= 0.72:
        issues.append(f"人脸中心 ({center_x:.1%}, {center_y:.1%}) 不在近景安全区")
    return issues


def write_report(
    out: Path,
    spec_path: Path,
    poster: Path,
    expected: str,
    result: object,
    issues: list[str],
    *,
    error: str = "",
) -> Path:
    payload = {
        "status": "pass" if not issues and not error else "fail",
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "auditor": LOCAL_AUDITOR,
        "expected_subject": expected,
        "identity_evidence": "L0-bound spec subject + same-source frame_at",
        "spec_sha256": sha256(spec_path),
        "poster_sha256": sha256(poster),
        "thresholds": {
            "close_up_zoom": MIN_ZOOM_CLOSE_UP,
            "face_height_ratio": MIN_FACE_HEIGHT_RATIO,
            "close_up_face_height_ratio": MIN_CLOSE_UP_FACE_HEIGHT_RATIO,
            "face_area_ratio": MIN_FACE_AREA_RATIO,
            "face_sharpness": MIN_FACE_SHARPNESS,
            "face_contrast": MIN_FACE_CONTRAST,
            "eyes": MIN_EYES,
        },
        "result": result,
        "issues": issues,
    }
    if error:
        payload["error"] = error
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--spec", required=True)
    parser.add_argument("--poster", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    spec_path, poster, out = Path(args.spec), Path(args.poster), Path(args.out)
    for label, path in (("spec", spec_path), ("poster", poster)):
        if not path.is_file():
            print(f"[不合格] 找不到 {label}：{path}")
            return 2
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"[不合格] spec 读不了：{exc}")
        return 2
    expected = expected_subject(spec)
    if not expected:
        print("[不合格] spec 无法确定封面主角；请写 subject/interviewee，不能猜")
        return 2

    try:
        result = analyze_poster(poster)
        contract, _ = framing_contract(spec)
        result["contract"] = contract
        issues = validate_result(result, spec)
        write_report(out, spec_path, poster, expected, result, issues)
    except Exception as exc:  # noqa: BLE001 — 本地证据不足必须留下失败凭据
        error = f"{type(exc).__name__}: {exc}"
        write_report(
            out,
            spec_path,
            poster,
            expected,
            None,
            ["本地封面像素审核失败"],
            error=error,
        )
        print(f"[不合格] {error}")
        return 1

    if issues:
        print("[不合格] 封面本地视觉终审：")
        for issue in issues:
            print(f"  - {issue}")
        print(f"失败凭据 → {out}")
        return 1
    face = result["face"]
    print(
        f"[ok] 封面人物合同={expected}；脸高={face['face_height_ratio']:.1%}；"
        f"双眼={face['eyes']}；本地凭据 → {out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
