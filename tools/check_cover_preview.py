#!/usr/bin/env python3
"""Read-only cover-preview checks; this never validates or publishes a final video."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path


def read_inputs(root: Path, slug: str) -> tuple[Path, dict]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,119}", slug):
        raise ValueError("Unsafe or empty preview slug")
    path = root / "specs" / "reels" / f"{slug}.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("slug") != slug:
        raise ValueError("Spec slug does not match requested preview")
    if spec.get("push", {}).get("auto") is not False:
        raise ValueError("Preview inputs must explicitly set push.auto=false")
    cover = spec.get("cover") or {}
    if cover.get("layout") != "solo" or cover.get("eyebrow") != "赛场之上":
        raise ValueError("This preview route only accepts native solo 赛场之上 covers")
    if cover.get("approved_image") or cover.get("versus"):
        raise ValueError("This route requires the existing native photo template")
    portrait = cover.get("portrait") or {}
    if "frame_at" in portrait or not portrait.get("image"):
        raise ValueError("Preview requires an existing photo; no source download or frame extraction")
    image = (root / str(portrait["image"])).resolve()
    if not image.is_relative_to((root / "assets" / "reel").resolve()) or not image.is_file():
        raise ValueError("Preview photo must exist inside assets/reel")
    if cover.get("hook_accent_color") != "#FFD600":
        raise ValueError("Preview title accent must explicitly be #FFD600")
    if not cover.get("hook_accent"):
        raise ValueError("Preview must explicitly select title accent text")
    for font in ("SmileySans-Oblique.ttf", "SmileySans-Oblique.woff2",
                 "NotoSansSC-Regular-sub.ttf", "NotoSansSC-Bold-sub.ttf",
                 "NotoSerifSC-Black-sub.ttf", "TLScore-Light.ttf", "TLScore-Regular.ttf",
                 "TLScore-Bold.ttf", "BarlowCondensed-Medium.ttf",
                 "BarlowCondensed-SemiBold.ttf", "BarlowCondensed-Bold.ttf",
                 "Montserrat-latin-500.woff2", "Montserrat-latin-600.woff2"):
        if not (root / "assets" / "fonts" / font).is_file():
            raise ValueError(f"Missing native font: {font}")
    return path, spec


def check_cover(spec: dict) -> list[str]:
    # Call production's existing cover checks individually. Do not catch-and-ignore
    # validate_spec failures or change any final-video gate.
    import build_match_reel as reel
    import reel_asset_gates as assets
    import reel_facts as facts
    import taste_gates as taste
    import taste_gates_extra as extra
    import versus_poster as poster

    if "hook_accent_color" not in reel._REAL_FIELDS["cover"]:
        raise ValueError("The reviewed native title-accent patch must be present")
    poster._hook_accent_color(spec["cover"])
    reel._hook_lines_fit_the_title(spec)
    reel._solo_scoreboard_shape(spec)
    problems = poster.cover_style_problems(spec)
    # Drafts may not have video topbars yet. The cover topic still has its own
    # native format; use its existing event text, never invent a video topbar.
    if not (spec.get("topbar") or {}).get("line1"):
        topic = str(spec["cover"].get("topic") or "")
        expected = facts.cover_topic(topic.split(" · ", 1)[0], spec["cover"])
        if not expected or topic != expected:
            problems.append(f"cover.topic must use the native event + matchup format: {expected}")
    checks = (
        reel.cover_photo_problem, facts.result_direction_problem,
        facts.verified_result_problem, facts.bare_tiebreak_problem,
        facts.decider_tiebreak_problem, facts.cover_topic_problem,
        assets.duration_problem,
        taste.hook_result_problem, taste.hook_jargon_problem,
        taste.rank_claim_problem, extra.cover_fit_problem, extra.solo_layout_problem,
        extra.total_margin_problem,
    )
    for check in checks:
        if problem := check(spec):
            problems.append(problem)
    reuse = assets.cover_reuse_finding(spec)
    if reuse and reuse[1]:
        problems.append(reuse[0])
    elif reuse:
        print("[封面复用] 跨栏目，只报：" + reuse[0])
    # Only cover assets are in scope, not segment/technical-stat-card images.
    problems.extend(assets.image_problems({"cover": spec["cover"]}))
    if problems:
        raise ValueError("\n\n".join(problems))
    return ["native_hook_size", "native_scoreboard_shape", "native_cover_style",
            "native_cover_images", "native_cover_reuse"] + [check.__name__ for check in checks]


def write_report(path: Path, spec_path: Path, spec: dict, checks: list[str]) -> None:
    from PIL import Image

    photo = Path(spec["cover"]["portrait"]["image"])
    preview = path.parent / "preview.jpg"
    with Image.open(preview) as image:
        image.load()
        if image.size != (1080, 1440) or image.format != "JPEG":
            raise ValueError("Native preview must be a decoded 1080x1440 JPEG")
    report = {
        "kind": "cover_preview_only", "slug": spec["slug"],
        "revision": os.environ.get("GITHUB_SHA"),
        "status": "rendered_pending_human_visual_review",
        "final_video_qc": "NOT_RUN", "publication_eligible": False,
        "checked": checks + ["native_render_cover_local", "jpeg_1080x1440"],
        "still_requires": ["same_match_photo_and_identity_evidence_review",
                           "face_eyes_focus_and_crop_review", "text_and_photo_overlap_review",
                           "all_final_video_and_publication_gates"],
        "winners_ue": {key: {field: (spec.get("stats", {}).get(key) or {}).get(field)
                            for field in ("winners", "ue")} for key in ("a", "b")},
        "sha256": {label: hashlib.sha256(file.read_bytes()).hexdigest()
                   for label, file in (("spec", spec_path), ("photo", photo), ("preview", preview))},
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--inputs-only", action="store_true")
    parser.add_argument("--report-to", type=Path)
    args = parser.parse_args()
    path, spec = read_inputs(Path.cwd(), args.slug)
    if args.inputs_only:
        print("Read-only preview inputs checked; no dependencies installed or browser started")
        return 0
    # Use the exact native loader before the cover-scoped checks too.
    from build_match_reel import load_spec
    spec = load_spec(path)
    checks = check_cover(spec)
    if args.report_to:
        write_report(args.report_to, path, spec, checks)
    print("Cover-only checks passed; final-video QC NOT RUN; publication NOT authorized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
