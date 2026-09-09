#!/usr/bin/env python3
"""把人工指定的“赛后开麦”视频请求转成可渲染正式 spec。

请求文件只写已经核实的内容身份、赛果、封面和发布文案；本工具在 runner 上完成
音频下载、第一份 ASR、正式切行与逐行中文翻译，然后落正式 spec 和
``output/interviews/<slug>/cap_asr.json3``。同场比赛结尾由
``attach_interview_lead_in.py`` 在下一步补齐。

用法：
    python tools/build_interview_request.py --count-pending
    python tools/build_interview_request.py --pending-slugs
    python tools/build_interview_request.py --write
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time

from production_cache import atomic_json, cached_json, digest, file_digest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

REQUESTS = ROOT / "requests" / "interviews"
SPECS = ROOT / "specs" / "interviews"
OUTDIR = ROOT / "output" / "interviews"
DOWNLOAD_TIMEOUT = 300


def _read(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} 顶层必须是对象")
    return data


def _youtube_id(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    if host == "youtu.be":
        return parsed.path.strip("/").split("/")[0]
    if host == "youtube.com" or host.endswith(".youtube.com"):
        query = parse_qs(parsed.query)
        if query.get("v"):
            return query["v"][0]
        return parsed.path.rstrip("/").rsplit("/", 1)[-1]
    return ""


def _request_paths() -> list[Path]:
    return sorted(REQUESTS.glob("*.json")) if REQUESTS.is_dir() else []


def _slug(req: dict, path: Path) -> str:
    slug = str(req.get("slug") or "").strip()
    if not slug or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        raise ValueError(f"{path}: slug 非法：{slug!r}")
    return slug


def _exists_or_tracked(path: Path) -> bool:
    """稀疏 checkout 没把 output 拉下来时，也要从 git index 看见已有产物。"""
    if path.is_file():
        return True
    try:
        rel = path.relative_to(ROOT).as_posix()
    except ValueError:
        return False
    proc = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel],
        cwd=ROOT, capture_output=True, text=True, timeout=20,
    )
    return proc.returncode == 0


def _production_contract(data: dict) -> dict:
    """提取人工请求与正式 spec 之间不允许漂移的用户合同。

    请求文件和正式 spec 都保存了人物、片头与封面。今天改费德勒封面时两处要
    分别修改；只改请求、已有 spec 仍在时，旧逻辑会把请求判成“已经处理”，
    继续用旧封面生产。这里只比较会改变内容身份或最终画面的语义字段，忽略
    ``opening.why``、运营文案等允许在正式 spec 中继续编辑的说明文字。
    """
    subject = data.get("subject") or {}
    opening = data.get("opening") or {}
    cover = data.get("cover") or {}
    push = data.get("push") or {}
    contract = {
        "url": str(data.get("url") or "").strip(),
        "requested_content_type": str(data.get("requested_content_type") or ""),
        "ceremony_subtype": str(data.get("ceremony_subtype") or ""),
        "interview_kind": str(data.get("interview_kind") or ""),
        "event": str(data.get("event") or ""),
        "winner": str(data.get("winner") or ""),
        "featured_player": str(data.get("featured_player") or ""),
        "subject": {
            key: subject.get(key)
            for key in ("id", "event", "name", "role")
            if key in subject
        },
        "opening_kind": opening.get("kind"),
        "requested_lead_in": data.get("lead_in"),
        "cover": {
            key: cover.get(key)
            for key in ("frame_at", "subject", "title", "sub", "tag", "topic",
                        "shot_type", "zoom", "focus_y")
            if key in cover
        },
        "push_auto": push.get("auto"),
        "segment_budget_px": data.get("segment_budget_px"),
        "topbar_layout": str(data.get("topbar_layout") or (
            "subject_primary"
            if data.get("ceremony_subtype") == "hall_of_fame_induction"
            else "event_primary"
        )),
    }
    return contract


def _request_contract_changed(req: dict, spec_path: Path) -> bool:
    try:
        spec = _read(spec_path)
    except (OSError, ValueError):
        return True
    expected = _production_contract(req)
    actual = _production_contract(spec)
    # 这些字段允许正式化阶段补出默认值；只有请求明确写过时，它们才是用户
    # 合同。否则会把历史 spec 的正常默认值误判成漂移并触发昂贵的全文重转写。
    for key in ("ceremony_subtype", "interview_kind", "winner",
                "featured_player", "segment_budget_px"):
        if key not in req:
            expected.pop(key, None)
            actual.pop(key, None)
    if not isinstance(req.get("subject"), dict) or not req.get("subject"):
        expected.pop("subject", None)
        actual.pop("subject", None)
    if not (req.get("opening") or {}).get("kind"):
        expected.pop("opening_kind", None)
        actual.pop("opening_kind", None)
    if "lead_in" not in req:
        expected.pop("requested_lead_in", None)
        actual.pop("requested_lead_in", None)
    if not isinstance(req.get("cover"), dict) or not req.get("cover"):
        expected.pop("cover", None)
        actual.pop("cover", None)
    if "auto" not in (req.get("push") or {}):
        expected.pop("push_auto", None)
        actual.pop("push_auto", None)
    if expected != actual:
        return True
    # 不写 start/end 表示完整采用源片，正式 spec 会把它展开成实际秒数；只有
    # 请求显式裁切时才比较，防止“全文翻译”被后来静默改成节选。
    for key in ("start", "end"):
        if key in req and float(req[key]) != float(spec.get(key, -1)):
            return True
    return False


def _request_identity(req: dict) -> str:
    return digest({k: v for k, v in req.items()
                   if k not in {"_rebuild_once", "expected_spec_sha256"}})


def _protected(spec: dict, slug: str) -> bool:
    return bool(spec.get("transcript_verified") or spec.get("_verified_clean")
                or _exists_or_tracked(OUTDIR / slug / "pushed.json"))


def _explicit_revision(req: dict, spec_path: Path, spec: dict) -> bool:
    return bool(req.get("revision")
                and req.get("revision") != (spec.get("_request_origin") or {}).get("revision")
                and req.get("expected_spec_sha256") == file_digest(spec_path))


def is_pending(path: Path) -> bool:
    req = _read(path)
    slug = _slug(req, path)
    spec_path = SPECS / f"{slug}.json"
    if not _exists_or_tracked(spec_path):
        return True
    # A sparse or unreadable formal spec is not permission to overwrite it.
    if not spec_path.is_file():
        return False
    spec = _read(spec_path)
    origin = spec.get("_request_origin") or {}
    if _protected(spec, slug) and not _explicit_revision(req, spec_path, spec):
        return False
    if origin.get("request_sha256") == _request_identity(req):
        return bool(req.get("_rebuild_once")) or not _exists_or_tracked(
            OUTDIR / slug / "cap_asr.json3")
    if origin.get("request_sha256"):
        return True  # The request changed, rather than the refined formal spec.
    return (bool(req.get("_rebuild_once")) or _request_contract_changed(req, spec_path)
            or not _exists_or_tracked(OUTDIR / slug / "cap_asr.json3"))


def pending_paths(only_slug: str = "") -> list[Path]:
    out = []
    for path in _request_paths():
        req = _read(path)
        slug = _slug(req, path)
        if only_slug and slug != only_slug:
            continue
        if is_pending(path):
            out.append(path)
    return out


def _resolve_media_url(url: str) -> str:
    """Tennis TV 页面先换成可下载媒体；YouTube 等来源原样返回。"""
    from tennislive.video.official import media_url  # noqa: PLC0415

    try:
        return media_url(url)
    except Exception:  # noqa: BLE001 — 非 Tennis TV 来源不该被解析器挡住
        return url


def _download_attempts(url: str) -> list[tuple[str, list[str]]]:
    """无业务素材依赖的轻量 YouTube client 梯子。

    不能从完整 match-reel / interview renderer 导入这张表：自动请求任务使用
    sparse checkout，不含它们渲海报时读取的 ``assets/``。2026-08-29 锦织圭
    请求实跑时，导入完整梯子先因缺 Munar 人脸素材失败，再静默退成单档默认。
    下载判据必须只依赖 URL 和 yt-dlp，本函数因此故意保持纯数据。
    """
    if not _youtube_id(url):
        return [("direct", [])]
    return [
        ("默认", []),
        ("web_safari", ["--extractor-args", "youtube:player_client=web_safari"]),
        ("ios", ["--extractor-args", "youtube:player_client=ios"]),
        ("android_vr", ["--extractor-args", "youtube:player_client=android_vr"]),
        ("web", ["--extractor-args", "youtube:player_client=web"]),
        ("tv", ["--extractor-args", "youtube:player_client=tv"]),
    ]


def _downloaded_audio(workdir: Path) -> Path | None:
    """找本档真正下载完成的原始音轨，排除 yt-dlp 临时/续传文件。"""
    candidates = [
        path
        for path in workdir.glob("audio.*")
        if path.is_file()
        and path.stat().st_size > 0
        and not path.name.endswith((".part", ".ytdl", ".temp"))
    ]
    return max(candidates, key=lambda path: path.stat().st_size) if candidates else None


def _download_audio(url: str, workdir: Path) -> Path:
    """带 cookies、Node JS runtime 和 client 梯子下载原始音轨。

    这里不把音轨转成 MP3：``-x --audio-format mp3`` 会调用系统 ffmpeg，而轻量
    请求任务没有安装它；faster-whisper 自带的 PyAV 能直接读取 webm/m4a/opus。
    每一档失败都打印真实尾部错误并继续，只有所有档都失败才抛异常。
    """
    workdir.mkdir(parents=True, exist_ok=True)
    dl_url = _resolve_media_url(url)
    template = str(workdir / "audio.%(ext)s")
    cookie_args: list[str] = []
    cookies = os.environ.get("YT_COOKIES") or ""
    if cookies and Path(cookies).is_file():
        cookie_args = ["--cookies", cookies]

    failures: list[str] = []
    deadline = time.monotonic() + DOWNLOAD_TIMEOUT
    for label, extra in _download_attempts(url):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            failures.append("音频下载总预算耗尽")
            break
        # 失败档可能留下 .part / .ytdl / 原始容器；下一档必须从干净状态开始，
        # 不能把上一档的半截文件误认成这次成功产物。
        for partial in workdir.glob("audio.*"):
            partial.unlink(missing_ok=True)
        cmd = [
            "yt-dlp",
            "--no-warnings",
            "--no-playlist",
            "--js-runtimes", "node",
            "--extractor-retries", "3",
            "-f", "bestaudio/best",
            "-o", template,
            *cookie_args,
            *extra,
            dl_url,
        ]
        try:
            proc = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=min(60, remaining),
            )
        except subprocess.TimeoutExpired:
            tail = f"本档超过 {min(60, remaining):g}s（总预算 {DOWNLOAD_TIMEOUT}s）"
            print(f"[人工请求音频] {label} 没成：{tail}")
            failures.append(f"{label}: {tail}")
            continue

        audio = _downloaded_audio(workdir)
        if proc.returncode == 0 and audio is not None:
            if failures:
                print(f"[人工请求音频] {label} 成功（前面 {len(failures)} 档没成）")
            else:
                print(f"[人工请求音频] {label} 成功")
            print(f"[人工请求音频] 原始容器：{audio.name}，{audio.stat().st_size} bytes")
            return audio

        raw = (proc.stderr or proc.stdout or "（没有 yt-dlp 输出）").strip()
        tail_lines = raw.splitlines()[-3:]
        tail = " | ".join(line.strip() for line in tail_lines if line.strip())
        if proc.returncode == 0 and audio is None:
            tail = "exit 0 但没有生成完整原始音轨" + (f"；{tail}" if tail else "")
        tail = tail[-900:] or "（没有 yt-dlp 输出）"
        print(f"[人工请求音频] {label} 没成：{tail[:240]}")
        failures.append(f"{label}: {tail}")

    raise RuntimeError(
        f"yt-dlp 音频下载 {len(failures)} 档全部失败：\n  "
        + "\n  ".join(failures)
    )


def _transcribe_request(
    url: str, workdir: Path, model: str = "small.en"
) -> tuple[list[dict], float]:
    """可靠下载人工请求音频，再用第一份 faster-whisper 产逐词时间码。"""
    audio = _download_audio(url, workdir)
    from faster_whisper import WhisperModel  # noqa: PLC0415

    model_inst = WhisperModel(model, compute_type="int8")
    segments, info = model_inst.transcribe(
        str(audio), vad_filter=True, word_timestamps=True
    )
    duration = float(getattr(info, "duration", 0.0) or 0.0)
    rows: list[dict] = []
    for segment in segments:
        words = list(getattr(segment, "words", None) or [])
        if words:
            rows.extend(
                {
                    "t": round(float(word.start), 2),
                    "end": round(float(word.end), 2),
                    "text": str(word.word).strip(),
                }
                for word in words
                if str(word.word).strip()
            )
            continue
        tokens = str(segment.text or "").strip().split()
        span = max(0.01, float(segment.end) - float(segment.start))
        for index, token in enumerate(tokens):
            start = float(segment.start) + span * index / max(len(tokens), 1)
            end = float(segment.start) + span * (index + 1) / max(len(tokens), 1)
            rows.append({
                "t": round(start, 2),
                "end": round(end, 2),
                "text": token,
            })
    return rows, duration


def _verification(req: dict) -> dict:
    """请求里的官方明确标题证明；签名仍由 source gate 统一生成。"""
    from interview_source_gate import explicit_title_type  # noqa: PLC0415

    url = str(req.get("url") or "").strip()
    title = str(req.get("source_title") or "").strip()
    source = str(req.get("source") or "").strip()
    requested = str(req.get("requested_content_type") or "").strip()
    video_id = _youtube_id(url)
    if not video_id:
        raise ValueError("人工指定请求目前只接受可核验的 YouTube URL")
    explicit = explicit_title_type(title)
    if explicit != requested:
        raise ValueError(
            f"官方标题只能证明 {explicit or 'unknown'}，请求却声明 {requested}：{title}"
        )
    method = {
        "on_court": "official_explicit_oncourt",
        "ceremony": "official_explicit_ceremony",
        "farewell": "official_explicit_farewell",
    }[requested]
    return {
        "source_id": f"youtube:{video_id}",
        "source_url": url,
        "source": source,
        "title": title,
        "status": "verified",
        "detected_type": requested,
        "method": method,
        "evidence": [
            {
                "kind": "official_explicit_title",
                "title": title,
                "source": source,
                "video_id": video_id,
            }
        ],
    }


def build_spec(req: dict, zh: list[str], duration: float) -> dict:
    """已经正式切行的中文 + 请求元数据 → 带 L0 签名的正式 spec。"""
    from interview_source_gate import (  # noqa: PLC0415
        REQUESTED_KINDS,
        finalize_source_contract,
        validate_source_contract,
    )

    slug = str(req["slug"])
    requested = str(req["requested_content_type"])
    if requested not in REQUESTED_KINDS:
        raise ValueError(f"未登记的 requested_content_type：{requested}")
    start = max(0.0, float(req.get("start") or 0.0))
    requested_end = req.get("end")
    end = float(requested_end) if requested_end not in (None, "") else float(duration)
    end = min(float(duration), end)
    if end <= start:
        raise ValueError(f"无效时间窗：{start}-{end}（源长 {duration}）")
    if not zh:
        raise ValueError("中文字幕为空")

    match = dict(req.get("match") or {})
    verification = _verification(req)
    spec = {
        "slug": slug,
        "_production": {"received_at": req.get("received_at") or (req.get("_production") or {}).get("received_at", "")},
        "url": str(req["url"]),
        "source_title": str(req["source_title"]),
        "start": round(start, 2),
        "end": round(end, 2),
        "asr_model": "small.en",
        "whisper_model": "medium.en",
        "segment_budget_px": req.get("segment_budget_px"),
        "transcript_verified": False,
        "transcript_verification": "auto_pending",
        "column": "赛后开麦",
        "requested_content_type": requested,
        "interview_kind": str(req.get("interview_kind") or REQUESTED_KINDS[requested]),
        "event": str(req["event"]),
        "winner": str(req.get("winner") or ""),
        "featured_player": req.get("featured_player"),
        "ceremony_subtype": req.get("ceremony_subtype"),
        "topbar_layout": str(req.get("topbar_layout") or (
            "subject_primary"
            if req.get("ceremony_subtype") == "hall_of_fame_induction"
            else "event_primary"
        )),
        "subject": dict(req.get("subject") or {}),
        "opening": dict(req.get("opening") or {}),
        "zh": zh,
        "_zh_draft": zh,
        "_zh_draft_note": (
            "第一份 faster-whisper small.en 逐词时间码经正式 segment() 切行后，"
            "由 DeepSeek 逐行翻译；render 时用 medium.en 做第二份独立 ASR。"
        ),
        "_notes": list(req.get("_notes") or []),
        "_facts": list(req.get("_facts") or []),
        "_tactical_research": dict(req.get("_tactical_research") or {}),
        "cover": dict(req.get("cover") or {}),
        "takeaway": dict(req.get("takeaway") or {}),
        "push": dict(req.get("push") or {}),
        "match": match,
        "source_verification": verification,
    }
    if req.get("caption_gaps_ok"):
        spec["caption_gaps_ok"] = dict(req["caption_gaps_ok"])
    if req.get("lead_in"):
        # Preserve the user's reviewed source, time window and bilingual commentary.
        # The renderer still validates the lead-in and same-match contract.
        import copy
        spec["lead_in"] = copy.deepcopy(req["lead_in"])
    finalize_source_contract(spec)
    validate_source_contract(spec)
    return spec


def _apply_request_delta(current, before, after):
    """Apply only user-edited leaves; keep refinements to other cover/copy fields."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        return after
    result = dict(current) if isinstance(current, dict) else {}
    for key in before.keys() | after.keys():
        if before.get(key) == after.get(key) and (key in before) == (key in after):
            continue
        if key not in after:
            result.pop(key, None)
        else:
            result[key] = _apply_request_delta(result.get(key), before.get(key), after[key])
    return result


def _build_one_unlocked(path: Path, chat, *, write: bool) -> tuple[str, int, float]:
    from build_interview_clip import segment, strip_hesitation_lines  # noqa: PLC0415
    from draft_interview_spec import cap_json3, translate  # noqa: PLC0415

    req = _read(path)
    slug = _slug(req, path)
    spec_path = SPECS / f"{slug}.json"
    observed = {p: file_digest(p) for p in (
        path, spec_path, SPECS / f"{slug}.xhs.txt", OUTDIR / slug / "cap_asr.json3")}
    existing = _read(spec_path) if spec_path.is_file() else {}
    if write and existing and _protected(existing, slug) and not _explicit_revision(req, spec_path, existing):
        raise RuntimeError(f"{slug}: 已确认版本受保护；新修订需 revision 和 expected_spec_sha256")
    origin = existing.get("_request_origin") or {}
    previous = origin.get("request") or {}
    transcript_keys = ("url", "start", "end", "segment_budget_px", "max_zh_chars",
                       "source_title", "source", "requested_content_type", "match", "subject")
    metadata_only = (bool(previous) and not req.get("_rebuild_once")
                     and all(previous.get(k) == req.get(k) for k in transcript_keys)
                     and (OUTDIR / slug / "cap_asr.json3").is_file())
    research_job = None
    if metadata_only:
        # Apply only fields the user changed, preserving refined translations/lead-in.
        spec = dict(existing)
        for key in ("cover", "push", "takeaway", "opening", "lead_in", "event",
                    "winner", "subject", "featured_player", "ceremony_subtype",
                    "topbar_layout", "interview_kind", "requested_content_type"):
            if req.get(key) != previous.get(key):
                spec[key] = _apply_request_delta(spec.get(key), previous.get(key), req.get(key))
        from interview_source_gate import finalize_source_contract, validate_source_contract
        finalize_source_contract(spec)
        validate_source_contract(spec)
        if write:
            from production_preflight import check_request
            copy_path = SPECS / f"{slug}.xhs.txt"
            copy_text = (str(req.get("xhs") or "") if req.get("xhs") != previous.get("xhs")
                         else copy_path.read_text(encoding="utf-8"))
            check_request({**req, **spec, "xhs": copy_text})
        rows = None
        lines = existing.get("zh") or []
        duration = float(origin.get("duration") or existing.get("end") or 0)
    else:
        if write:
            from production_preflight import check_request
            check_request(req)
        if write and not metadata_only and not req.get("_tactical_research"):
            match = req.get("match") or {}
            if match.get("winner_en") and match.get("loser_en"):
                from tactical_research import start_research
                research_job = start_research(home=match["winner_en"], away=match["loser_en"],
                    event=match.get("event_search") or req.get("event", ""), year=match.get("year", 0))
        def transcribe():
            with tempfile.TemporaryDirectory() as td:
                return _transcribe_request(str(req["url"]), Path(td), model="small.en")
        # Dry runs remain isolated and do not persist checkpoints.
        rows, duration = (cached_json("interview-asr", {
            "source": _youtube_id(str(req["url"])) or req["url"],
            "model": "small.en", "implementation": file_digest(Path(__file__)),
        }, transcribe) if write else transcribe())

        if not rows:
            raise RuntimeError(f"{slug}: 第一份 ASR 为空")
        start = max(0.0, float(req.get("start") or 0.0))
        requested_end = req.get("end")
        end = float(requested_end) if requested_end not in (None, "") else float(duration)
        end = min(float(duration), end)
        lines = segment(
            [(row["t"], row["text"]) for row in rows], start, end,
            budget=req.get("segment_budget_px"),
        )
        # render/verify 会在切行后清掉 um/uh 等犹豫音；初次翻译必须走完全相同的
        # 正文行，否则长讲话会出现“中文 656 行、英文 673 行”这种必然无法渲染的
        # spec。清理必须发生在 translate 前，不能事后硬补空行。
        strip_hesitation_lines(lines)
        if not lines:
            raise RuntimeError(f"{slug}: 正式切行为空")
        translation_rows = [{"t": row["a"], "text": row["en"]} for row in lines]
        def translate_once():
            return translate(translation_rows, chat, max_zh_chars=req.get("max_zh_chars"))
        zh = (cached_json("interview-translation", {
            "rows": translation_rows, "max_zh_chars": req.get("max_zh_chars"),
            "channel": getattr(chat, "channel", ""),
            "model": getattr(chat, "model", os.environ.get("TENNISLIVE_BRIEF_MODEL", "deepseek-chat")),
            "translator": file_digest(ROOT / "tools/draft_interview_spec.py"),
            "contract": file_digest(ROOT / "skills/tennis-interview-production/references/deepseek.md"),
        }, translate_once) if write else translate_once())
        if len(zh) != len(lines):
            raise RuntimeError(f"{slug}: 中英文行数不一致 {len(zh)} != {len(lines)}")
        spec = build_spec(req, zh, duration)
    if write:
        if research_job is not None:
            spec["_tactical_research"] = research_job.result()
        if any(file_digest(p) != sha for p, sha in observed.items()):
            raise RuntimeError(f"{slug}: 输入或正式稿已被另一任务修改，拒绝覆盖")
        if _explicit_revision(req, spec_path, existing):
            marker = OUTDIR / slug / "pushed.json"
            if marker.is_file():
                pushed = _read(marker)
                if pushed.get("film_sha256"):
                    spec["_publication_revision"] = {
                        "id": req["revision"], "base_film_sha256": pushed["film_sha256"]}
        spec["_request_origin"] = {
            "request_sha256": _request_identity(req), "request": {
                k: v for k, v in req.items() if k not in {"_rebuild_once", "expected_spec_sha256"}},
            "revision": req.get("revision"), "duration": duration,
        }
        atomic_json(spec_path, spec)
        copy_path = SPECS / f"{slug}.xhs.txt"
        if not metadata_only or req.get("xhs") != previous.get("xhs"):
            copy_path.write_text(str(req.get("xhs") or "").rstrip() + "\n", encoding="utf-8")
        if rows is not None:
            atomic_json(OUTDIR / slug / "cap_asr.json3", cap_json3(rows))
        if req.pop("_rebuild_once", None) is not None:
            atomic_json(path, req)
    return slug, len(lines), duration


def _build_one(path: Path, chat, *, write: bool) -> tuple[str, int, float]:
    if not write:
        return _build_one_unlocked(path, chat, write=False)
    import fcntl
    lock = OUTDIR / _slug(_read(path), path) / ".request.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _build_one_unlocked(path, chat, write=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--count-pending", action="store_true")
    ap.add_argument("--pending-slugs", action="store_true")
    ap.add_argument("--slug", default="")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    paths = pending_paths(args.slug)
    if args.count_pending:
        print(len(paths))
        return 0
    if args.pending_slugs:
        for path in paths:
            print(_slug(_read(path), path))
        return 0
    if not paths:
        print("没有待生成的人工采访请求。")
        return 0

    from tennislive.research.brief import Chat  # noqa: PLC0415

    chat = Chat()
    if not chat.ready:
        print("::error::没配 DEEPSEEK_API_KEY，中文字幕无法生成")
        return 2

    failed = 0
    for path in paths:
        try:
            slug, n_lines, duration = _build_one(path, chat, write=args.write)
            mode = "已写入" if args.write else "干跑"
            print(f"✅ {slug}: {n_lines} 行，源长 {duration:.1f}s，{mode}")
        except Exception as exc:  # noqa: BLE001 — 一条失败不吞掉后续请求
            failed += 1
            print(f"::error::{path.name}: {type(exc).__name__}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
