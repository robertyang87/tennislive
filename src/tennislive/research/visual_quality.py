"""Deterministic visual quality checks for social cover photography.

The checks deliberately avoid generative or hosted vision models so the same
decision can be reproduced inside GitHub Actions. Metadata establishes who and
what is pictured; OpenCV verifies that the downloaded file is sharp, readable,
and can survive the 3:4 cover crop without cutting the main face.
"""

from __future__ import annotations

import math
from pathlib import Path


MOTION_TERMS = (
    "in action",
    "action shot",
    "during the match",
    "during match",
    "serving",
    "serves",
    "serve against",
    "hits a forehand",
    "hits a backhand",
    "hits a return",
    "plays a forehand",
    "plays a backhand",
    "returning",
    "return of serve",
    "volley",
    "smash",
    "running",
    "sliding",
    "reaches for",
    "stretches for",
    "match point",
)

REACTION_TERMS = (
    "celebrates",
    "celebrating",
    "celebration",
    "fist pump",
    "reacts after",
    "victory reaction",
    "after winning",
    "wins the match",
    "match win",
)

TROPHY_TERMS = (
    "lifts the trophy",
    "holds the trophy",
    "with the trophy",
    "champion trophy",
    "trophy celebration",
)

# These scenes are related to tennis, but they make weak daily-news covers.
# They are hard failures even when the athlete name is correct.
STATIC_OR_GROUP_TERMS = (
    "pre-match photo",
    "pre match photo",
    "prematch photo",
    "pre-match group",
    "team photo",
    "group photo",
    "group portrait",
    "players pose",
    "poses for photographers",
    "posing for photographers",
    "photo call",
    "photocall",
    "press conference",
    "media day",
    "headshot",
    "studio portrait",
    "official portrait",
    "coin toss",
    "pre-match handshake",
    "prematch handshake",
    "red carpet",
    "podium group",
    "trophy presentation group",
    "award ceremony group",
    "end card",
    "end screen",
    "closing slate",
    "outro",
    "title card",
    "channel logo",
    "tournament logo",
    "logo only",
    "scoreboard only",
    "empty court",
)


def classify_cover_scene(text: str) -> dict:
    """Classify an image from source metadata using conservative phrases."""
    normalized = " ".join(text.lower().replace("_", " ").replace("-", " ").split())

    def hits(terms: tuple[str, ...]) -> list[str]:
        return [term for term in terms if term.replace("-", " ") in normalized]

    rejected = hits(STATIC_OR_GROUP_TERMS)
    motion = hits(MOTION_TERMS)
    reaction = hits(REACTION_TERMS)
    trophy = hits(TROPHY_TERMS)
    if rejected:
        scene = "static_or_group"
    elif motion:
        scene = "match_action"
    elif reaction:
        scene = "on_court_reaction"
    elif trophy:
        scene = "solo_trophy"
    else:
        scene = "unknown"
    return {
        "scene": scene,
        "motion_terms": motion,
        "reaction_terms": reaction,
        "trophy_terms": trophy,
        "rejected_terms": rejected,
    }


def _entropy(gray, np) -> float:
    histogram = np.bincount(gray.ravel(), minlength=256).astype("float64")
    probabilities = histogram[histogram > 0] / histogram.sum()
    return float(-(probabilities * np.log2(probabilities)).sum())


def _cover_crop(width: int, height: int, center_x: float, center_y: float) -> tuple[int, int, int, int]:
    target_ratio = 3 / 4
    if width / height > target_ratio:
        crop_width = int(round(height * target_ratio))
        left = int(round(center_x - crop_width * 0.58))
        left = max(0, min(width - crop_width, left))
        return left, 0, left + crop_width, height
    crop_height = int(round(width / target_ratio))
    top = int(round(center_y - crop_height * 0.32))
    top = max(0, min(height - crop_height, top))
    return 0, top, width, top + crop_height


def _overlap_ratio(first: tuple[int, int, int, int], second: tuple[int, int, int, int]) -> float:
    """Return intersection over the smaller box for face-detector de-duplication."""
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    left = max(ax, bx)
    top = max(ay, by)
    right = min(ax + aw, bx + bw)
    bottom = min(ay + ah, by + bh)
    intersection = max(0, right - left) * max(0, bottom - top)
    return intersection / max(1, min(aw * ah, bw * bh))


def assess_cover_image(path: Path) -> dict:
    """Return a JSON-safe 3:4 crop and image-quality audit."""
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return {
            "status": "fail",
            "score": 0,
            "quality_score": 0,
            "crop_score": 0,
            "hard_failures": ["opencv-unavailable"],
            "focus": "50% 28%",
        }

    image = cv2.imread(str(path))
    if image is None:
        return {
            "status": "fail",
            "score": 0,
            "quality_score": 0,
            "crop_score": 0,
            "hard_failures": ["unreadable-image"],
            "focus": "50% 28%",
        }

    height, width = image.shape[:2]
    scale = min(1.0, 960.0 / max(width, height))
    preview = cv2.resize(
        image,
        (max(1, int(width * scale)), max(1, int(height * scale))),
        interpolation=cv2.INTER_AREA,
    )
    gray = cv2.cvtColor(preview, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(preview, cv2.COLOR_BGR2HSV)
    p05, p95 = (float(value) for value in np.percentile(gray, (5, 95)))
    tonal_range = p95 - p05
    mean_luma = float(gray.mean())
    black_ratio = float((gray < 18).mean())
    white_ratio = float((gray > 242).mean())
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    edge_ratio = float((cv2.Canny(gray, 70, 160) > 0).mean())
    entropy = _entropy(gray, np)
    saturation = float(hsv[:, :, 1].mean())

    detections: list[tuple[int, int, int, int, str]] = []
    cv2_data = getattr(cv2, "data", None)
    cascade_dir = getattr(cv2_data, "haarcascades", "")
    if cascade_dir:
        minimum = (
            max(28, preview.shape[1] // 18),
            max(28, preview.shape[0] // 18),
        )
        # Sports photographs frequently show a three-quarter/profile face. The
        # alternate frontal cascade catches those while remaining available in
        # the standard headless OpenCV wheel used by GitHub Actions.
        for filename, label in (
            ("haarcascade_frontalface_default.xml", "frontal-default"),
            ("haarcascade_frontalface_alt2.xml", "frontal-alt2"),
        ):
            cascade = cv2.CascadeClassifier(str(Path(cascade_dir) / filename))
            if cascade.empty():
                continue
            found = cascade.detectMultiScale(
                gray,
                scaleFactor=1.06,
                minNeighbors=5,
                minSize=minimum,
            )
            detections.extend((*map(int, box), label) for box in found)
    faces: list[tuple[int, int, int, int]] = []
    face_detectors: list[str] = []
    preview_area = preview.shape[0] * preview.shape[1]
    for x, y, face_width, face_height, detector in sorted(
        detections,
        key=lambda item: item[2] * item[3],
        reverse=True,
    ):
        preview_box = (x, y, face_width, face_height)
        if face_width * face_height / preview_area < 0.004:
            continue
        scaled_box = (
            int(x / scale),
            int(y / scale),
            int(face_width / scale),
            int(face_height / scale),
        )
        if any(_overlap_ratio(scaled_box, existing) >= 0.55 for existing in faces):
            continue
        faces.append(scaled_box)
        face_detectors.append(detector)
    faces.sort(key=lambda box: box[2] * box[3], reverse=True)

    if faces:
        x, y, face_width, face_height = faces[0]
        center_x = x + face_width / 2
        center_y = y + face_height / 2
    else:
        center_x = width * 0.64
        center_y = height * 0.32
    crop = _cover_crop(width, height, center_x, center_y)
    left, top, right, bottom = crop
    crop_retention = ((right - left) * (bottom - top)) / (width * height)

    face_safe = True
    if faces:
        x, y, face_width, face_height = faces[0]
        margin = max(10, int(face_height * 0.10))
        face_safe = (
            x - margin >= left
            and x + face_width + margin <= right
            and y - margin >= top
            and y + face_height + margin <= bottom
        )

    failures: list[str] = []
    short_side, long_side = sorted((width, height))
    if short_side < 900 or long_side < 1200:
        failures.append("resolution-below-900x1200")
    if sharpness < 35:
        failures.append("soft-or-blurred")
    if tonal_range < 55:
        failures.append("low-contrast")
    if black_ratio > 0.28:
        failures.append("too-dark")
    if white_ratio > 0.28:
        failures.append("too-bright")
    # A low edge count can be a desirable shallow-depth-of-field sports photo.
    # Keep rejecting truly empty frames while allowing a sharp athlete against
    # a smooth court or crowd background.
    if entropy < 4.2 or edge_ratio < 0.01:
        failures.append("low-visual-information")
    if len(faces) > 2:
        failures.append("multiple-prominent-faces")
    if not faces:
        failures.append("no-prominent-face")
    if not face_safe:
        failures.append("unsafe-head-crop")
    if crop_retention < 0.32:
        failures.append("unsafe-vertical-crop")

    resolution_points = min(3.0, math.log2(max(1, width * height) / (900 * 1200)) + 2.0)
    sharpness_points = max(0.0, min(4.0, (sharpness - 35) / 45 * 4))
    tone_points = max(0.0, min(3.0, (tonal_range - 55) / 60 * 3))
    information_points = max(0.0, min(3.0, (entropy - 4.2) / 2.0 * 3))
    color_points = max(0.0, min(2.0, saturation / 90 * 2))
    quality_score = round(
        resolution_points + sharpness_points + tone_points + information_points + color_points,
        1,
    )

    retention_points = min(8.0, crop_retention / 0.58 * 8)
    face_points = 7.0 if faces and face_safe else 3.0 if not faces else 0.0
    face_center_x = center_x / width
    text_space_points = 5.0 if face_center_x >= 0.52 else 2.0
    crop_score = round(retention_points + face_points + text_space_points, 1)
    score = round(quality_score + crop_score, 1)
    return {
        "status": "pass" if not failures else "fail",
        "score": score,
        "quality_score": quality_score,
        "crop_score": crop_score,
        "hard_failures": failures,
        "width": width,
        "height": height,
        "sharpness": round(sharpness, 1),
        "tonal_range": round(tonal_range, 1),
        "mean_luma": round(mean_luma, 1),
        "black_ratio": round(black_ratio, 4),
        "white_ratio": round(white_ratio, 4),
        "entropy": round(entropy, 2),
        "edge_ratio": round(edge_ratio, 4),
        "saturation": round(saturation, 1),
        "prominent_faces": len(faces),
        "face_detectors": sorted(set(face_detectors)),
        "crop": [left, top, right, bottom],
        "crop_retention": round(crop_retention, 3),
        "face_safe": face_safe,
        "focus": f"{center_x / width * 100:.0f}% {center_y / height * 100:.0f}%",
    }
