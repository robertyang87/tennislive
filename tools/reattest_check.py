#!/usr/bin/env python3
"""spec 渲完之后又改了：要重渲，还是**重核对**就够（`match-reel mode=reattest`）。

账号所有者 2026-09-27 选的「重核对，不重渲」（O1）：渲完之后只改了注解
（`_why` / `_facts` / `_score_inset_why`……）或推送字段（`push.auto` /
`push.summary`），成片一个像素都不会变，却因为质检凭证钉着 spec 的字节而不得不
再渲一趟 7~10 分钟。现在渲染会记下 `render_inputs.json`（见 `render_inputs.py`），
这个工具拿新 spec 按同一个口径重算、逐字节比：

    本地（写 spec 那一刻就知道派哪一档，不用猜）：
        python tools/reattest_check.py --slug <slug>
        退出码 0 ＝ 可以 reattest（或 spec 根本没变）；1 ＝ 要 mode=render；
        2 ＝ 判不了（这一版渲染没有清单 / 凭证链本身对不上），也按 render 走

    runner 上（`match-reel mode=reattest` 那一步）：
        python tools/reattest_check.py --slug <slug> --outdir <outdir> --apply --run <url>
        全部对得上才写一张**绑定新 spec 字节、指着同一份成片**的新凭证；
        对不上当场红，报出是哪一处动了渲染输入

**重核对不松的东西**（「发出去的必须和质检过的是同一份」，tennis-pipeline-ops
「哈希链」那几节）：

1. 旧凭证链自己要完整：`render.json` 指着这张凭证、成片 hash/字节三方一致、
   清单就是这次渲染写的（凭证和 `render.json` 都钉着它的 sha、它记的成片 hash
   和凭证一致）
2. 渲染那一刻落下的产物（`subtitles.ass` / `poster.jpg` / `topbar.ass` /
   `stat_card.jpg` / `scoreboard_qc.json`）逐字节没动
3. 新 spec 的渲染投影、认领注解、引用素材的字节和渲染那一刻逐字节相同
4. **Release 上那份成片现下载、现算 sha256**，必须就是凭证里那一份——跨天重渲
   会 `--clobber` 掉 tag 上的附件（CLAUDE.md「跨天重渲的另一半有闸」那节），
   按字节数猜不算数
5. spec 自己的闸照旧要过：工作流在这一步之前跑 `production_preflight` 和
   `--dry-run`，红了根本走不到这儿

⚠️ **发布账本一个字都不松**：账本按成片 hash 记，重核对之后还是同一份成片——
已经 `sent` 的照样拦住，「没有真改动就不该有新消息」（CLAUDE.md 9/22 那节）。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_inputs as ri  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
QC_NAME = "qc_attestation.json"


@dataclass
class Assessment:
    """`status`：same（spec 没变）/ reattest（可以）/ render（要重渲）/ unknown（判不了）。"""
    status: str
    reasons: list[str] = field(default_factory=list)
    qc: dict = field(default_factory=dict)
    qc_bytes: bytes = b""
    render: dict = field(default_factory=dict)
    manifest: dict = field(default_factory=dict)
    manifest_bytes: bytes = b""
    spec_bytes: bytes = b""


def latest_outdir(repo: Path, slug: str) -> Path | None:
    """按 slug 反查最新那一份产物目录（和 `mode=push` 同一个口径：日期排序取最新）。"""
    hits = sorted((repo / "output").glob(f"*/reel/{slug}/render.json"))
    return hits[-1].parent if hits else None


def _load(path: Path) -> tuple[bytes, dict] | None:
    if not path.is_file():
        return None
    data = path.read_bytes()
    try:
        obj = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        return data, {}
    return data, obj if isinstance(obj, dict) else {}


def assess(repo: Path, slug: str, outdir: Path, spec_path: Path) -> Assessment:
    """只读：这条 slug 眼下能不能重核对。"""
    unknown = Assessment("unknown")

    loaded = _load(outdir / QC_NAME)
    if not loaded:
        unknown.reasons.append(f"{outdir}/{QC_NAME} 不在——这一版没过 L2 质检，谈不上重核对")
        return unknown
    qc_bytes, qc = loaded
    if qc.get("status") != "pass" or qc.get("slug") != slug:
        unknown.reasons.append("旧凭证状态不是 pass 或 slug 对不上")
        return unknown

    loaded = _load(outdir / "render.json")
    if not loaded:
        unknown.reasons.append("render.json 不在")
        return unknown
    _, render = loaded
    if render.get("qc_attestation_sha256") != ri.sha256_bytes(qc_bytes):
        unknown.reasons.append("render.json 指着的不是眼前这张凭证")
    film = str(qc.get("film_sha256") or "")
    if not film or render.get("film_sha256") != film:
        unknown.reasons.append("render.json 和凭证记的不是同一份成片")
    if int(render.get("video_bytes") or 0) != int(qc.get("film_bytes") or 0):
        unknown.reasons.append("Release 字节数和凭证里的成片对不上")
    if not render.get("video_url"):
        unknown.reasons.append("render.json 没有 Release video_url")

    loaded = _load(outdir / ri.MANIFEST_NAME)
    if not loaded:
        unknown.reasons.append(
            f"没有 {ri.MANIFEST_NAME}——这一版是 2026-09-27 之前渲的（那时渲染还不记"
            "渲染输入），判不了哪些字段进了成片")
        return _with(unknown, qc, qc_bytes, render)
    manifest_bytes, manifest = loaded
    digest = ri.sha256_bytes(manifest_bytes)
    if manifest.get("version") != ri.VERSION:
        unknown.reasons.append(f"{ri.MANIFEST_NAME} 版本 {manifest.get('version')!r} 不认")
    if render.get("render_inputs_sha256") != digest:
        unknown.reasons.append(f"render.json 记的 {ri.MANIFEST_NAME} 不是眼前这一份（渲完之后被改过）")
    if qc.get("render_inputs_sha256") != digest:
        unknown.reasons.append(f"凭证没有钉住眼前这份 {ri.MANIFEST_NAME}")
    if manifest.get("film_sha256") != film or manifest.get("slug") != slug:
        unknown.reasons.append(f"{ri.MANIFEST_NAME} 描述的不是凭证里那份成片")

    # 产物：渲染那一刻落下的，逐字节没动
    for name, want in sorted((manifest.get("artifacts") or {}).items()):
        path = outdir / name
        got = ri.sha256_file(path) if path.is_file() else None
        if got != want:
            unknown.reasons.append(f"{name} 和渲染那一刻不是同一份（换过或删了）")
    ass = outdir / "subtitles.ass"
    if not ass.is_file() or ri.sha256_file(ass) != qc.get("ass_sha256"):
        unknown.reasons.append("烧片字幕 subtitles.ass 和凭证钉的不是同一份")

    if not spec_path.is_file():
        unknown.reasons.append(f"{spec_path} 不在")
    if unknown.reasons:
        return _with(unknown, qc, qc_bytes, render, manifest, manifest_bytes)

    spec_bytes = spec_path.read_bytes()
    result = _with(Assessment("reattest"), qc, qc_bytes, render, manifest,
                   manifest_bytes, spec_bytes)
    if ri.sha256_bytes(spec_bytes) == qc.get("spec_sha256"):
        result.status = "same"
        return result
    problems = (ri.spec_problems(spec_bytes, manifest)
                + ri.asset_problems(spec_bytes, manifest, repo))
    if problems:
        result.status = "render"
        result.reasons = problems
    return result


def _with(a: Assessment, qc: dict, qc_bytes: bytes, render: dict,
          manifest: dict | None = None, manifest_bytes: bytes = b"",
          spec_bytes: bytes = b"") -> Assessment:
    a.qc, a.qc_bytes, a.render = qc, qc_bytes, render
    a.manifest, a.manifest_bytes, a.spec_bytes = manifest or {}, manifest_bytes, spec_bytes
    return a


def fetch_release_digest(url: str, timeout: float = 60.0) -> tuple[str, int]:
    """把 Release 上那份成片**现下载、现算** sha256（流式，不落盘）。

    按字节数判「还是不是那一份」不算数：同一个 tag 被跨天重渲 `--clobber` 过，
    字节数碰巧相近的两份成片也不是同一份。代价是把整份成片（60~200 MB）拉一遍——
    比重渲便宜得多，但不是零；实际耗时 2026-09-27 落地时还没在 runner 上量过。
    """
    import hashlib  # noqa: PLC0415

    req = urllib.request.Request(url, headers={"User-Agent": "tennislive-reattest"})
    h = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        for block in iter(lambda: resp.read(1024 * 1024), b""):
            h.update(block)
            size += len(block)
    return h.hexdigest(), size


def apply(repo: Path, slug: str, outdir: Path, spec_path: Path, *, run_url: str = "",
          now: str = "", fetch: Callable[[str], tuple[str, int]] = fetch_release_digest,
          ) -> Assessment:
    """runner 上那一步：全部对得上才写新凭证，并把 `render.json` 指向它。"""
    a = assess(repo, slug, outdir, spec_path)
    if a.status != "reattest":
        return a
    film = str(a.qc["film_sha256"])
    got_sha, got_size = fetch(str(a.render["video_url"]))
    if got_sha != film or got_size != int(a.qc.get("film_bytes") or 0):
        a.status = "unknown"
        a.reasons = [f"Release 上的成片已经不是凭证里那一份（现算 {got_sha[:12]}… / "
                     f"{got_size} 字节，凭证 {film[:12]}… / {a.qc.get('film_bytes')} 字节）"
                     "——多半被别的一趟渲染 --clobber 过，重核对不成立"]
        return a

    stamp = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_spec = ri.sha256_bytes(a.spec_bytes)
    payload = dict(a.qc)
    payload.update({
        "checked_at": stamp,
        "spec_sha256": new_spec,
        "render_inputs_sha256": ri.sha256_bytes(a.manifest_bytes),
        "reattest": {
            "previous_attestation_sha256": ri.sha256_bytes(a.qc_bytes),
            "previous_spec_sha256": a.qc.get("spec_sha256"),
            "render_spec_sha256": a.manifest.get("spec_sha256"),
            "projection_sha256": a.manifest.get("projection_sha256"),
            "film_verified": "release-sha256",
            "run": run_url,
        },
    })
    qc_path = outdir / QC_NAME
    qc_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    render = dict(a.render)
    render["qc_attestation_sha256"] = ri.sha256_file(qc_path)
    render["reattests"] = list(render.get("reattests") or []) + [
        {"at": stamp, "spec_sha256": new_spec, "run": run_url}]
    (outdir / "render.json").write_text(
        json.dumps(render, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return a


def _report(a: Assessment, slug: str, outdir: Path, *, applied: bool) -> int:
    print(f"[重核对] {slug}：产物目录 {outdir}")
    if a.status == "same":
        print("[重核对] spec 和质检过的是同一份字节——凭证链本来就是通的，什么都不用做。")
        return 0
    if a.status == "reattest":
        if applied:
            print("[重核对] 渲染输入逐字节没动、Release 成片现算 sha256 对得上——"
                  "已写新凭证（绑定新 spec，指着同一份成片），这一趟不重渲。")
        else:
            print("[重核对] 渲染输入逐字节没动：改的只有注解/推送字段。派这一档就够，不用重渲：\n"
                  "  gh workflow run match-reel.yml --ref <分支> "
                  f"-f mode=reattest -f slug={slug}\n"
                  "  （runner 上照旧先跑 production_preflight 和 --dry-run，红了就不会重核对）")
        return 0
    if a.status == "render":
        print("[要重渲] 这次改动动到了渲染输入，成片会变——走 mode=render：")
    else:
        print("[判不了] 按 mode=render 走：")
    for reason in a.reasons[:20]:
        print(f"  - {reason}")
    if len(a.reasons) > 20:
        print(f"  …… 另有 {len(a.reasons) - 20} 处")
    return 1 if a.status == "render" or applied else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--outdir", default="", help="产物目录；默认按 slug 反查最新那一份")
    ap.add_argument("--spec", default="", help="默认 specs/reels/<slug>.json")
    ap.add_argument("--repo", default=str(ROOT))
    ap.add_argument("--apply", action="store_true",
                    help="runner：核对通过就现算 Release 成片 sha256 并写新凭证")
    ap.add_argument("--run", default="", help="--apply：这次运行的地址，记进凭证")
    args = ap.parse_args(argv)

    repo = Path(args.repo)
    outdir = Path(args.outdir) if args.outdir else latest_outdir(repo, args.slug)
    if outdir is None:
        print(f"[判不了] output/*/reel/{args.slug}/render.json 一份都没有——先 mode=render")
        return 2
    spec_path = Path(args.spec) if args.spec else repo / "specs" / "reels" / f"{args.slug}.json"
    if args.apply:
        a = apply(repo, args.slug, outdir, spec_path, run_url=args.run)
    else:
        a = assess(repo, args.slug, outdir, spec_path)
    return _report(a, args.slug, outdir, applied=args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
