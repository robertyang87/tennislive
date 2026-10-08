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
from publication_ledger import interview_published
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
# 自动链的探测那一步在装依赖（pip install -e .）之前就 import 这里，tennislive 包要能从源码树找到。
sys.path.insert(0, str(ROOT / "src"))

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
    """这条正式 spec 已经不归自动链改了：人核过，或者**已经发出去**。

    「发出去」认两处：**发布账本**（`data/interview_publish_ledger/<slug>.json`，
    `auto_push_interview_gate` 称它为权威状态）里有任何一次发出/在发/状态不明，
    或者老的 `pushed.json` 兼容标记。⚠️ 只认 `pushed.json` 漏过一条真的：
    `nishikori-sakamoto-us-open-2026-q3-farewell` 账本 `sent`（2026-08-29 06:53Z，
    run 33239487051）、账号所有者手改过（7c6110dd2），但 `pushed.json` 从来没有过——
    于是 6 小时后自动链把这条已发、已精修的 spec 重建了一遍（519816362，给一条
    `opening.why` 写着「按账号所有者明确要求不补冷开场」的片子挂上了 `lead_in`），
    全库测试也把它当成「自动链还没核没发」只报。判据
    `tests/test_interview_clip.py::test_自动spec的判据_章在而且没核没发才算`。
    """
    return bool(spec.get("transcript_verified") or spec.get("_verified_clean")
                or _exists_or_tracked(OUTDIR / slug / "pushed.json")
                or (slug and interview_published(ROOT, slug)))


#: 三个自动写手给采访 spec 盖的同一个章：本文件 `build_spec`、
#: `draft_interview_spec`（草稿）、`promote_interview_draft`（草稿转正，原样保留）。
#: ⚠️ **没有任何代码会把它改掉**——人工修 spec（#1130 修拉沃尔杯捧杯那条）也不改，
#: main 上 17 条正式 spec 带着它、**17 条全都推过**（2026-09-27 晚按发布账本量的；
#: 其中锦织圭那条只有账本、没有 `pushed.json`）。
#: 所以「过没过那一关」不能只看这个章，要看 `_protected`：人核过
#: （`transcript_verified` / `_verified_clean`）或已经推送（发布账本 / `pushed.json`）。
AUTO_PENDING = "auto_pending"


# 类定义在 tennislive 包里：pytest-xdist 主控要按 __module__ 重新 import 它才能反序列化
# worker 发回的 warning，而主控的 sys.path 里没有 tools/（来路见 tennislive/findings.py）。
from tennislive.findings import UnverifiedAutoSpecFinding  # noqa: E402,F401


def unverified_auto_spec(spec: dict, slug: str | None = None) -> bool:
    """自动链直接提交到 main、还没过人工核对也还没发出去的采访 spec（含草稿）。

    **全库测试对它只报，拦它的是渲染闸。** 来路（2026-09-27 17:33Z）：
    `interview-auto-render` 把 `laver-cup-2026-trophy-ceremony` 的自动正式 spec
    （01684ef0，`zh` 是 DeepSeek 初译，11 行超 952px）直接推上 main。GITHUB_TOKEN 推的
    提交不触发 ci.yml，于是它不红在自己身上，红在下一个无关的人工合并上
    （run 36337538392，#1127），再把所有开着的 PR 一起打红 38 分钟——而那条片子
    **早就被渲染闸拦住了**（run 36337385713 停在 `write_ass` →「中文字幕过不了」），
    全库测试只是把同一个缺陷重复报了一遍。9/20~9/27 这样的「自动正式 spec」提交
    六次全红（main 四次、PR 两次），**六次渲染闸都先拦下了**。

    判据只用已有的标记，不新发明：章是 `transcript_verification == "auto_pending"`，
    销章是 `_protected`（人核过或已推送——发布账本或 `pushed.json`；也就是这条 spec
    已经不归自动链改了，`is_pending` 用它挡重建，这里用它认「过了那一关」）。

    ⚠️ 还有一段缝它认不出：自动 spec 被人手修过、但还没推（#1130 修拉沃尔杯那条，
    ba28735dc 到推送之间约 19 分钟）。手修不改章，这段时间里对手修的回归全库测试
    也只报——渲染闸照拦，只是 PR 上的绿不代表这几条判据查过它。

    ⚠️ **只管那几条「渲染闸拦得住同一个缺陷」的全库测试**；没有渲染闸的（比如
    `test_人名要以译名表为准`）照旧全判，别拿它当通用豁免。清单写在
    `.claude/skills/tennis-pipeline-ops/SKILL.md`「自动链直接提交到 main 的草稿 spec
    不许把 main 打红」那一节。判据 `tests/test_interview_clip.py::
    test_自动链刚提交的采访spec只报_销章就红_渲染闸照拦`。
    """
    if spec.get("transcript_verification") != AUTO_PENDING:
        return False
    return not _protected(spec, str(slug or spec.get("slug") or ""))


def report_unverified_auto(check: str, found: dict) -> None:
    """把自动 spec 的发现**印出来并挂一条 warning**——只报不是不报。

    `print` 在 pytest 里通过时会被吞掉，所以另挂一条 `UnverifiedAutoSpecFinding`：
    CI 的 warnings 汇总里每一条都看得见是哪条 spec、哪个判据、差在哪。
    """
    import warnings  # noqa: PLC0415

    for name in sorted(found):
        msg = (f"[自动 spec 只报] {check} · {name}：{found[name]}"
               "（渲染闸会拦它；人核过或推送之后这条判据对它照判）")
        print(msg)
        warnings.warn(msg, UnverifiedAutoSpecFinding, stacklevel=2)


def _explicit_revision(req: dict, spec_path: Path, spec: dict) -> bool:
    return bool(req.get("revision")
                and req.get("revision") != (spec.get("_request_origin") or {}).get("revision")
                and req.get("expected_spec_sha256") == file_digest(spec_path))


def _awaiting_round_review(req: dict, slug: str) -> bool:
    """同一份请求上一趟建出来的 spec 因为机器译文把轮次写成「N 强」，落成了
    `<slug>.draft.json`＋`manual_review_required`，在等人改译文——别每一趟再建一遍、
    把人改到一半的草稿盖掉（见 `_round_name_review`）。请求一改（身份变了）就照常重建。"""
    draft = SPECS / f"{slug}.draft.json"
    if not draft.is_file():
        return False
    try:
        doc = _read(draft)
    except (OSError, ValueError):
        return False
    return bool(doc.get("manual_review_required")) and (
        (doc.get("_request_origin") or {}).get("request_sha256") == _request_identity(req))


def is_pending(path: Path) -> bool:
    req = _read(path)
    slug = _slug(req, path)
    # 在等人改译文（上一趟落了 `<slug>.draft.json`）：有没有正式 spec 都一样不重建——
    # 复审第三轮 nit：原来只在没有正式 spec 时认它，已有正式 spec 的请求改了之后撞上
    # 机器译文「N 强」，每 10 分钟重建一次、把人改到一半的草稿盖掉。
    if _awaiting_round_review(req, slug):
        return False
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
    """待 build 的请求。读不了的（JSON 坏了、顶层不是对象、slug 缺或非法）**照样列进来**，
    按文件名认 slug（`requests/interviews/<slug>.json`，存量全是这个约定）：交给 `main`
    那个逐条 try 记进失败清单、`::error file=` 指回它，同一趟其余请求照常 build。
    原来这里一抛，整趟连 `--count-pending` / `--pending-slugs` 一起炸，那个逐条兜底
    根本走不到——一条坏请求每 10 分钟卡死一整趟（复审 2026-09-27 nit）。"""
    out = []
    for path in _request_paths():
        slug, pending = path.stem, True
        try:
            slug = _slug(_read(path), path)
            pending = is_pending(path)   # 正式 spec 坏了也抛——一样交给 build 那一步报
        except Exception:  # noqa: BLE001 —— 读不了、形状不对（`"start": null` 在
            # `_request_contract_changed` 里是 TypeError，复审 nit 复现过）一律照样列进来，
            # 交给 build 那个逐条 try 记进失败清单；这里一抛就是整趟连名单一起炸
            pass
        if only_slug and slug != only_slug:
            continue
        if pending:
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
    # Explicit user requests may use the existing press-conference product.
    # Keep automatic discovery's title classifier unchanged.
    if requested == "press_conference":
        from interview_source_gate import _trusted_source_names
        metadata = req.get("source_metadata") or {}
        official_usopen = (
            source == "US Open"
            and metadata.get("video_id") == video_id
            and metadata.get("channel_id") == "UCXbboag48Qlr78zzz6SkzkQ"
            and metadata.get("source_url") == url
        )
        if (source not in _trusted_source_names() and not official_usopen
                or not re.search(r"\bpress\s+conference\b", title, re.I)):
            raise ValueError("发布会请求必须来自已核官方来源且标题明确为 Press Conference")
        explicit = "press_conference"
    if explicit != requested:
        raise ValueError(
            f"官方标题只能证明 {explicit or 'unknown'}，请求却声明 {requested}：{title}"
        )
    method = {
        "on_court": "official_explicit_oncourt",
        "ceremony": "official_explicit_ceremony",
        "farewell": "official_explicit_farewell",
        "press_conference": "official_explicit_press_conference",
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


def request_window(req: dict, duration: float,
                   rows: list[dict] | None = None) -> tuple[float, float]:
    """请求的时间窗。**没给 `end` 时不再取源片全长**，取最后一个词的词尾 ＋ 一口气
    （`interview_tail.default_end`）——拉沃尔杯那批第一版把片尾板剪进成片、两条推上
    微信又重推，全是 `else duration` 这一行默认出来的。切行（`_build_one_unlocked`）
    和写进 spec 的 `end`（`build_spec`）必须是同一个数，所以只算这一处。"""
    from interview_tail import default_end  # noqa: PLC0415

    start = max(0.0, float(req.get("start") or 0.0))
    requested_end = req.get("end")
    if requested_end not in (None, ""):
        end = float(requested_end)
    elif rows:
        end = default_end(rows, duration, start)
    else:
        end = float(duration)
    return start, min(float(duration), end)


def build_spec(req: dict, zh: list[str], duration: float) -> dict:
    """已经正式切行的中文 + 请求元数据 → 带 L0 签名的正式 spec。

    时间窗走 `request_window`；`_build_one_unlocked` 按逐词稿算好默认终点后
    以 `{**req, "end": end}` 传进来，所以切行用的窗和写进 spec 的是同一个数。
    """
    from interview_source_gate import (  # noqa: PLC0415
        REQUESTED_KINDS,
        finalize_source_contract,
        validate_source_contract,
    )

    slug = str(req["slug"])
    requested = str(req["requested_content_type"])
    if requested not in REQUESTED_KINDS:
        raise ValueError(f"未登记的 requested_content_type：{requested}")
    start, end = request_window(req, duration)
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
        "transcript_verification": AUTO_PENDING,
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
    if req.get("_claims"):
        # 全称断言的认领（「六次打进，六次全部首轮出局」要两个独立源）写在请求里，
        # 得跟着文案一起进正式 spec——不抄的话 push/takeaway 原样进去了、认领丢了，
        # render 前置检查（`production_preflight.check_interview_claims`）红在
        # 一条人已经核过源的断言上。
        spec["_claims"] = json.loads(json.dumps(req["_claims"]))
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


def _round_name_review(req: dict, spec: dict, existing: dict, copy_text: str,
                       existing_copy: str) -> tuple[list[str], list[str]]:
    """这一趟要写的 spec 新带进来的「N 强」轮次名：(请求自己写的, 只在机器译文里的)。

    全库测试 `test_轮次写分数式不写N强` 扫整份正式 spec **含 `zh`**、对自动 spec 也是硬的，
    而这里写的正式 spec 由 GITHUB_TOKEN 直推 main（CI 不跑）——放过去就是下一个不相干的 PR
    把 main 打红（复审 nit，01684ef0 那条事故的同一条路）。和 `promote_interview_draft`
    同一份面（`non_annotation_strings`）、同一个判据（`strength_round_hits`）。
    已经在现有正式 spec 里的（存量豁免）不算「新带进来」。"""
    from spec_wording import non_annotation_strings, strength_round_hits  # noqa: PLC0415

    def hits(obj, text: str) -> set[str]:
        return set(strength_round_hits([*non_annotation_strings(obj), text or ""]))

    fresh = hits(spec, copy_text) - hits(existing, existing_copy)
    from_request = fresh & hits(req, str(req.get("xhs") or ""))
    return sorted(from_request), sorted(fresh - from_request)


def _build_one_unlocked(path: Path, chat, *, write: bool) -> tuple[str, int, float]:
    from build_interview_clip import (  # noqa: PLC0415
        segment,
        segment_ruler,
        strip_hesitation_lines,
        transcript_language_windows,
    )
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
        # `_claims` 跟着文案走：只改了认领（或文案连同认领一起改）也要落进 spec。
        for key in ("cover", "push", "takeaway", "opening", "lead_in", "event",
                    "winner", "subject", "featured_player", "ceremony_subtype",
                    "topbar_layout", "interview_kind", "requested_content_type",
                    "_claims"):
            if req.get(key) != previous.get(key):
                if key not in req:
                    # 请求把这一项整个删了：spec 里也删，和下一层 `_apply_request_delta`
                    # 删叶子是同一个口径——原来写成 `"_claims": null` 留在 spec 里。
                    spec.pop(key, None)
                else:
                    spec[key] = _apply_request_delta(spec.get(key), previous.get(key), req[key])
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
        start, end = request_window(req, duration, rows)
        # 尺子和出片那一趟同一把：已渲过的 slug（显式修订重建）按它当年那把切，
        # 不然这里切出来、按行号写进 `zh` 的行，渲染时按老尺子重切就对不上
        lines = segment(
            [(row["t"], row["text"]) for row in rows], start, end,
            budget=req.get("segment_budget_px"), ruler=segment_ruler({"slug": slug}),
            **({"language_windows": transcript_language_windows({**req, "start": start, "end": end})}
               if req.get("transcript_languages") is not None else {}),
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
        # 默认终点按逐词稿算好再交给 build_spec（`_request_origin` 记的仍是原请求）
        spec = build_spec({**req, "end": end}, zh, duration)
        if req.get("end") in (None, "") and "end" in spec:
            # 请求没给 `end`：这个数是生成器算的。记下来，出片那一趟撞上片尾板时
            # 按它认「没人给过」、直接收到闸算出来的终点（interview_tail 第四节）。
            spec["_end_default"] = spec["end"]
    copy_file = SPECS / f"{slug}.xhs.txt"
    existing_copy = copy_file.read_text(encoding="utf-8") if copy_file.is_file() else ""
    copy_text = (str(req.get("xhs") or "") if not metadata_only or req.get("xhs") != previous.get("xhs")
                 else existing_copy)
    from_request, from_machine = _round_name_review(req, spec, existing, copy_text, existing_copy)
    if from_request or (from_machine and metadata_only):
        from production_preflight import RequestNotReady  # noqa: PLC0415
        raise RequestNotReady(
            f"请求里把轮次写成「N 强」（{'、'.join(from_request or from_machine)}）——"
            "改成 1/8决赛 / 1/4决赛 / 半决赛 / 决赛（「打进 8 强」这种成绩说法可以）")
    if from_machine:
        # 只在机器译文（`zh`）里：请求改不了它。不写正式 spec（直推 main 就是 main 红），
        # 落成 `<slug>.draft.json`＋`manual_review_required` 等人改译文——和 promote 转正闸
        # 见到译文「N 强」留草稿同一个处置；promote 见到这个键也不提升。
        print(f"::warning::{slug}: 机器译文把轮次写成「N 强」（{'、'.join(from_machine)}），"
              f"正式 spec 不写，落成 {slug}.draft.json 等人改译文")
        if write:
            if any(file_digest(p) != sha for p, sha in observed.items()):
                raise RuntimeError(f"{slug}: 输入或正式稿已被另一任务修改，拒绝覆盖")
            # 复审第三轮 nit：`<slug>.draft.json` 也是 `draft_interview_spec` 自动草稿的路径。
            # 那边落盘前会避撞，这边原来直接盖——而作废清理只删带 `_round_name_hits` 的，
            # 被盖掉的自动草稿就没了。不是自己落的那种，一个字节都不写。
            draft_path = SPECS / f"{slug}.draft.json"
            if draft_path.is_file():
                try:
                    mine = "_round_name_hits" in _read(draft_path)
                except (OSError, ValueError):
                    mine = False
                if not mine:
                    from production_preflight import RequestNotReady  # noqa: PLC0415
                    raise RequestNotReady(
                        f"{slug}.draft.json 已经是另一份草稿（不是请求生成器落的待复核稿），"
                        "不覆盖——先处理掉那份草稿，或者给请求换一个 slug")
            if research_job is not None:
                spec["_tactical_research"] = research_job.result()
            spec["manual_review_required"] = (
                "字幕译文把轮次写成了 N 强：改 zh 里那几行（1/8决赛 / 1/4决赛 / 半决赛 / 决赛），"
                f"删掉这个键，文件改名成 {slug}.json，再把 `_xhs` 存成 {slug}.xhs.txt")
            spec["_round_name_hits"] = from_machine
            spec["_xhs"] = copy_text
            spec["_request_origin"] = {
                "request_sha256": _request_identity(req), "request": {
                    k: v for k, v in req.items() if k not in {"_rebuild_once", "expected_spec_sha256"}},
                "revision": req.get("revision"), "duration": duration,
            }
            atomic_json(SPECS / f"{slug}.draft.json", spec)
            if rows is not None:
                atomic_json(OUTDIR / slug / "cap_asr.json3", cap_json3(rows))
        return slug, len(lines), duration
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
        # 上一版因为译文「N 强」落下的待复核草稿：正式 spec 写出来了，它就作废了——留着的话
        # promote 天天报「已标记人工复核」、自动链的草稿计数也一直不为 0。只删自己落的那种。
        stale = SPECS / f"{slug}.draft.json"
        if stale.is_file():
            try:
                if "_round_name_hits" in _read(stale):
                    stale.unlink()
            except (OSError, ValueError):
                pass
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


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _annotation(text: str) -> str:
    """GitHub 工作流命令的消息体：换行要编码，不然 `::error::` 只认第一行。"""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--count-pending", action="store_true")
    ap.add_argument("--pending-slugs", action="store_true")
    ap.add_argument("--slug", default="")
    ap.add_argument("--write", action="store_true")
    ap.add_argument(
        "--failed-list", default="",
        help="单条请求失败记进这个文件（每行：请求路径<TAB>slug<TAB>原因），退出码不再"
             "因为单条变 1——interview-auto-render 靠它让同一趟的其余请求照常提交，"
             "整趟到最后一步再标红。整趟跑不起来（没配 key）照旧非 0。")
    args = ap.parse_args()
    failed_list = Path(args.failed_list) if args.failed_list else None
    if failed_list:
        failed_list.write_text("", encoding="utf-8")

    paths = pending_paths(args.slug)
    if args.count_pending:
        print(len(paths))
        return 0
    if args.pending_slugs:
        for path in paths:
            try:
                print(_slug(_read(path), path))
            except (OSError, ValueError) as exc:
                # 不进 stdout（那是给 sparse-checkout add 的 slug 清单）；build 那一步会把它
                # 记进失败清单并 `::error`，这里只在日志里留一句
                print(f"[跳过] {_rel(path)} 读不了：{exc}", file=sys.stderr)
        return 0
    if not paths:
        print("没有待生成的人工采访请求。")
        return 0

    from tennislive.research.brief import Chat  # noqa: PLC0415

    chat = Chat()
    if not chat.ready:
        print("::error::没配 DEEPSEEK_API_KEY，中文字幕无法生成")
        return 2

    return build_all(paths, chat, write=args.write, failed_list=failed_list)


def build_all(paths: list[Path], chat, *, write: bool,
              failed_list: Path | None = None) -> int:
    """逐条建 spec → 退出码。一条失败不连坐：每条请求各自 try，失败的那条**什么都不写**
    （所有落盘都排在 `_build_one_unlocked` 末尾、所有闸之后），其余照常写。原来单条红就
    整步退出 1，同一趟后面的「补片头」「提交」全被跳过，别的请求白转写一遍、每 10 分钟重来一趟。

    ⚠️ 请求自己没过前置检查（`production_preflight.RequestNotReady`：解读卡写长了、
    全称断言没认领、时间窗无效……）**不算这一步失败**：这条留在待生成名单、报一句
    `::warning::`，退出码照旧看别的失败。这一步红了，工作流后面的提交和 dispatch 会被
    隐式的 success() 一起跳过——一条写错的请求会把所有别的 spec 每 10 分钟卡一趟。

    带 `failed_list`（interview-auto-render 的 `--failed-list`）时，**所有**失败——含
    `RequestNotReady`——都记进清单、`::error file=` 指回请求文件，退出码一律 0：提交和
    dispatch 按清单第二列跳过这几条，最后一步读清单写 run 摘要、把整趟标红。两种调法
    都不连坐；清单那条路上没过前置检查的请求也不会只剩一句被人略过的 warning。
    """
    from production_preflight import RequestNotReady  # noqa: PLC0415

    failed: list[tuple[str, str, str]] = []
    for path in paths:
        try:
            slug, n_lines, duration = _build_one(path, chat, write=write)
            mode = "已写入" if write else "干跑"
            print(f"✅ {slug}: {n_lines} 行，源长 {duration:.1f}s，{mode}")
        except Exception as exc:  # noqa: BLE001 — 一条失败不吞掉后续请求
            if isinstance(exc, RequestNotReady) and failed_list is None:
                print(f"::warning::{path.name}: 请求没过前置检查，留在待生成名单"
                      f"（改好请求下一趟自动接上，别的请求照常走）：{exc}")
                continue
            rel = _rel(path)
            try:
                slug = _slug(_read(path), path)
            except Exception:  # noqa: BLE001 — 请求本身读不了，原因里已经写了
                # 按文件名认（requests/interviews/<slug>.json，存量 17 条全是这个约定）。
                # 空着的话 dispatch／提交那两道按 `cut -f2` 过滤的闸拦不住它上一版的正式 spec
                # （复审 2026-09-27 nit）。
                slug = path.stem
            reason = f"{type(exc).__name__}: {exc}"
            failed.append((rel, slug, reason))
            print(f"::error file={rel}::{_annotation(f'{rel} 没过闸，不进这一趟的提交：{reason}')}")
    if failed_list:
        failed_list.write_text("".join(
            f"{rel}\t{slug}\t{' ⏎ '.join(reason.split(chr(10)))}\n"
            for rel, slug, reason in failed), encoding="utf-8")
        return 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
