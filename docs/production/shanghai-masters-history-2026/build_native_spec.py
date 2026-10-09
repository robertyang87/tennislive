#!/usr/bin/env python3
"""Assemble this episode's *draft* native reel from a production plan and EDL.

This tool writes inside this production directory only. It never writes final
specs, binds an audio-review pass, approves reuse rights, or modifies gates.

Plan shape (JSON):
  {"slug": "shanghai-masters-history-2026", "editorial": {...},
   "primary": "final2012", "mixed_fps": {"fedal2017": "actual reason"},
   "sequence": [
     {"kind": "title_card", "title_card": "大师杯时代", "kicker": "01",
      "seconds": 4.2, "narration": "..."},
     {"kind": "image", "image": "assets/reel/.../chapter.png",
      "seconds": 12.4, "narration": "..."},
     {"kind": "video", "edl_id": "2012-saving-match-point"}
   ]}
EDL shape: {"segments": [{"id": "2012-saving-match-point",
  "source": "final2012", "start": 10.0, "end": 24.0,
  "review": {"status": "complete", "reviewer": "actual reviewer",
             "reviewed_at": "2026-10-06T12:00:00+00:00"},
  "utterances": [{"start": 12.0, "end": 15.0, "en": "...", "zh": "..."}]
}]}. Absolute utterance seconds become native relative quote at/end cues.
Native quote arrays can instead be supplied directly; speech is never guessed.
Wordless video needs the actually reviewed `_quote_skip_why` explanation.

`--draft` permits pending EDL reviews, clearly recorded in draft metadata.
Without it every used video EDL entry must carry an explicit completed review.
That metadata is provenance, NOT a substitute for the renderer's separate
source-hash-bound foreground-audio review and sealed final audio gate.

Voice/rate are render CLI inputs, not native spec keys. Image/title_card seconds
must be chosen from measured TTS plus intentional reading room; no estimator
quietly shortens speech here. Their native base is digital silence (anullsrc);
check_reel_landed exempts the designed gap but requires each card to sound.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SLUG = "shanghai-masters-history-2026"
SEGMENT_FIELDS = {
    "audio_tail", "bed", "contain_keep", "crosses_cut", "crop_zoom", "cx",
    "end", "fill_y", "fit", "image", "image_kind", "inset", "mute",
    "narration", "point_end_ok", "quote", "score_inset", "score_inset_windows",
    "scorebox", "seconds", "source", "speed", "square_pan", "start",
    "stat_card", "title_card", "kicker", "track", "voice", "subtitle_bottom",
    "visual_image",
}
ROOT_FIELDS = {
    "archival", "conform", "crop_y", "crop_zoom", "layout", "mixed_fps",
    "primary", "stat_card_full_canvas", "revision_of", "scorebox",
    "scoreboard_profile", "source_scorebox", "source_fallbacks",
    "source_quality_exceptions", "stats", "subtitle_scrim", "subtitle_top",
    "topbar", "tts_backend", "editorial", "narration_audio_recipe",
    "scene_edl_recipe", "push", "outro",
}
WINDOW_FIELDS = {
    "source", "start", "end", "cx", "track", "fit", "quote", "speed",
    "mute", "audio_tail", "inset", "score_inset", "score_inset_windows",
    "scorebox", "crosses_cut", "point_end_ok", "crop_zoom",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_fields(raw: dict) -> dict:
    return deepcopy({k: v for k, v in raw.items()
                     if k in SEGMENT_FIELDS or k.startswith("_")})


def number(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return float(value)


def review_record(entry: dict, pending: bool) -> dict:
    review = entry.get("review") or entry.get("audio_review") or {}
    if not isinstance(review, dict):
        raise ValueError(f"EDL {entry['id']}: review must be an object")
    if not pending:
        if review.get("status") not in ("complete", "reviewed"):
            raise ValueError(f"EDL {entry['id']}: review pending; use --draft for a draft")
        if not str(review.get("reviewer", "")).strip():
            raise ValueError(f"EDL {entry['id']}: actual reviewer missing")
        try:
            when = datetime.fromisoformat(str(review["reviewed_at"]).replace("Z", "+00:00"))
            if when.tzinfo is None:
                raise ValueError("timezone missing")
        except (KeyError, ValueError) as exc:
            raise ValueError(f"EDL {entry['id']}: reviewed_at needs timezone ISO timestamp") from exc
    return deepcopy(review)


def video(entry: dict, pending: bool) -> tuple[dict, dict]:
    review = review_record(entry, pending)
    seg = native_fields(entry)
    start = number(seg.get("start"), f"{entry['id']}.start")
    end = number(seg.get("end"), f"{entry['id']}.end")
    if not 0 <= start < end:
        raise ValueError(f"EDL {entry['id']}: need 0 <= start < end")
    if not seg.get("source"):
        raise ValueError(f"EDL {entry['id']}: source ID missing")
    if "utterances" in entry:
        if seg.get("quote"):
            raise ValueError(f"EDL {entry['id']}: use utterances OR quote")
        cues = []
        for utterance in entry["utterances"]:
            a = number(utterance.get("start"), "utterance.start")
            b = number(utterance.get("end"), "utterance.end")
            en, zh = str(utterance.get("en", "")).strip(), str(utterance.get("zh", "")).strip()
            if not start <= a < b <= end or not en or not zh:
                raise ValueError(f"EDL {entry['id']}: each complete bilingual utterance must fit window")
            cues.append({"at": round(a - start, 4), "end": round(b - start, 4),
                         "text": en + "\n" + zh})
        if cues:
            seg["quote"] = cues
    if seg.get("quote") and seg.get("narration"):
        raise ValueError(f"EDL {entry['id']}: put Chinese explanation on a separate image/card")
    if not seg.get("quote") and not seg.get("narration") and not seg.get("_quote_skip_why"):
        raise ValueError(f"EDL {entry['id']}: wordless window needs its truthful _quote_skip_why")
    if seg.get("track") or (seg.get("cx") is not None and seg["cx"] != 0.5):
        raise ValueError(f"EDL {entry['id']}: this episode uses fixed centre crop")
    seg.update(cx=0.5, track=False)
    seg.setdefault("fit", "crop")
    seg["_edl_id"] = entry["id"]
    return seg, review


def fps(material: dict) -> Fraction | None:
    raw = (material.get("probe_metadata") or {}).get("fps")
    if not raw:
        streams = (material.get("media_metadata") or {}).get("streams", [])
        raw = next((s.get("r_frame_rate") for s in streams if s.get("width")), None)
    try:
        return Fraction(str(raw)) if raw else None
    except (ValueError, ZeroDivisionError):
        return None


def assemble(args) -> dict:
    plan, edl, manifest = read_json(args.plan), read_json(args.edl), read_json(args.manifest)
    if plan.get("slug", SLUG) != SLUG:
        raise ValueError("this generator is scoped to the Shanghai history episode")
    # Audio exceptions need actual owner authorization elsewhere; never generate them.
    forbidden = {"voice", "rate", "owner_approval", "original_audio_mode",
                 "audio_effects_review", "silent_source", "source_audio"}
    if bad := forbidden.intersection(plan):
        raise ValueError(f"unsupported plan root keys: {sorted(bad)}; voice/rate are CLI inputs")
    if plan.get("music") is not None:
        raise ValueError("episode follows owner default: no baked music; platform library on upload")
    if plan.get("_production", {}).get("status") == "ready_for_render":
        raise ValueError("do not tag this manual draft as automatic ready_for_render")
    rows = edl if isinstance(edl, list) else edl.get("segments", edl.get("windows", []))
    entries = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("id") or row["id"] in entries:
            raise ValueError("EDL entries need unique nonempty id strings")
        entries[row["id"]] = row
    sequence = plan.get("sequence", plan.get("segments"))
    if not isinstance(sequence, list) or not sequence:
        raise ValueError("plan.sequence must be a nonempty ordered list")
    spec = deepcopy({k: v for k, v in plan.items() if k in ROOT_FIELDS or k.startswith("_")})
    cover = deepcopy(plan.get("cover") or read_json(args.cover))
    if cover.get("eyebrow") != "网球有故事":
        raise ValueError("cover.eyebrow must be 网球有故事 for this history episode")
    spec.update(slug=SLUG, cover=cover, segments=[], track=False, music=None)
    spec.setdefault("outro", True)
    used, reviews = [], []
    for item in sequence:
        if not isinstance(item, dict):
            raise ValueError("each sequence item must be an object")
        kind = item.get("kind") or ("title_card" if item.get("title_card") else
                                    "image" if item.get("image") else "video")
        if kind == "video":
            ident = item.get("edl_id", item.get("id"))
            if ident not in entries:
                raise ValueError(f"unknown edl_id {ident!r}; windows are taken only from EDL")
            overrides = set(item) - {"kind", "id", "edl_id"}
            if overrides:
                raise ValueError(f"EDL {ident}: edit/review the EDL instead of overriding {sorted(overrides)}")
            seg, review = video(entries[ident], args.draft)
            if seg["source"] not in used:
                used.append(seg["source"])
            reviews.append({"edl_id": ident, "review": review})
        elif kind in ("image", "title_card"):
            seg = native_fields(item)
            if bad := WINDOW_FIELDS.intersection(seg):
                raise ValueError(f"{kind}: no source/audio window fields {sorted(bad)}")
            if number(seg.get("seconds"), kind + ".seconds") <= 0:
                raise ValueError(f"{kind}: seconds must be positive")
            if not str(seg.get("narration", "")).strip() or not seg.get(kind):
                raise ValueError(f"{kind}: actual visual and nonempty narration required")
        else:
            raise ValueError(f"unsupported segment kind {kind!r}")
        spec["segments"].append(seg)
    materials = {s["id"]: s for s in manifest["videos"]}
    if not used or any(s not in materials for s in used):
        raise ValueError("used sources must exist in manifest.videos")
    primary = plan.get("primary", used[0])
    if primary not in used:
        raise ValueError("primary must be a used source")
    ordered = [primary] + [s for s in used if s != primary]
    spec["sources"] = {s: materials[s]["url"] for s in ordered}
    native_fps = fps(materials[primary])
    for source in ordered[1:]:
        other_fps = fps(materials[source])
        if native_fps and other_fps and abs(float(native_fps - other_fps)) > 0.01:
            if not str(spec.get("mixed_fps", {}).get(source, "")).strip():
                raise ValueError(f"{source}: {other_fps} vs primary {native_fps}; plan.mixed_fps needs actual reason")
    spec["_draft_assembly"] = {
        "status": "pending_edl_review" if args.draft else "assembled_pending_native_gates",
        "plan_sha256": sha(args.plan), "edl_sha256": sha(args.edl),
        "manifest_sha256": sha(args.manifest), "edl_reviews": reviews,
        "render_voice": "zh-CN-YunjianNeural", "render_rate": "+6%",
        "note": "Provenance only. Not rights approval or a foreground-audio gate pass.",
    }
    return spec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--edl", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=HERE / "material-manifest.json")
    parser.add_argument("--cover", type=Path, default=HERE / "cover-plan.json")
    parser.add_argument("--out", type=Path, default=HERE / "native-spec.draft.json")
    parser.add_argument("--draft", action="store_true", help="explicitly allow EDL reviews still pending")
    parser.add_argument("--validate", action="store_true", help="run existing load_spec/validate_spec; NOT audio/QC/release approval")
    args = parser.parse_args()
    try:
        target = args.out.resolve()
        if not target.is_relative_to(HERE) or target.suffix != ".json":
            raise ValueError("--out must be a JSON file under this episode production directory")
        spec = assemble(args)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Draft written: {target.relative_to(ROOT)}")
        if args.validate:
            sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
            import build_match_reel as native
            native.validate_spec(native.load_spec(target))
            print("Native spec shape/taste validation passed; source-bound audio/QC still required.")
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"Draft assembly blocked: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
