#!/usr/bin/env python3
"""源片的 probe 覆盖与几何：`--dry-run` 拿 probe.json 里的宽高帧率预演
`check_sources_match`，新写的手写 spec 每条源都要先 probe。

## 来路：7 趟几何红，runner 上的 dry-run 一份 probe 都没看见

2026-09-16 ~ 09-26 多源的「网球有故事」剪辑片在 render 里红了 7 趟
（38.9 runner 分钟），全是 `check_sources_match` 那一句「这些源片和主源的
尺寸／帧率对不上」——而它排在**所有源片下完之后**（中位 230 秒）：

    hsieh-chan-handshake-feud-2026  36260393395  uso3 1298×720  vs 1920×1080
    prozorova-concussion-…-2026     36216817183  hit 1282×720、mia25 1280×720
    sinner-beijing-withdrawal-2026  36133328467  xvid 480×852（没 probe）
    crowd-noise-hindrance           36091036879  nadal 1280×720、swiatekc 608×1080
    davis-cup-china-…-group-1       35072955589 / 35074495144  拨 run 时一条都没 probe

**7 趟的 runner dry-run 全都打印了「一份 probe.json 都没认领上」**。可前四条的
每一条源（sinner 除了 xvid）在拨 run **之前**就 probe 过、`probe.json` 早就落了库、
宽高帧率都在——只是落在别的 slug 目录下（`hsieh-chan-uso3`、`proz-mia25`、
`quiet-src-nadal-uso17`……），而工作流那一步只把 `output/*/reel/<本 slug>/probe.json`
拉回稀疏检出。**数据一直在，runner 按 URL 认领的那层看不见它**；本地看得见，
但 dry-run 从来不拿宽高帧率比一比。

## 三件事

- **几何**（`geometry_findings`）：宽高帧率从 probe.json 读，喂给 render 里
  **同一个** `check_sources_match`（`dims=` 那条入口，一个字的规则都不抄）——
  认领 `conform` 的按基准尺寸算（和 `conform_sources` 同一个基准：第一条没认领的源）。
  对谁都硬：这是 render 那道硬闸的提前预演，出路（`conform`／`archival`＋contain／
  `mixed_fps`）和那边一模一样。
- **覆盖**（`coverage_findings`）：spec 里的每条源都要认领得到 probe.json。
  没有就**硬**（新的手写 spec），`--dry-run` 那一刻就说「先跑一趟 mode=probe」；
  确实 probe 不了的源在 spec 顶层写 `"_no_probe_why": {"源键": "<为什么>"}` 认领。
  老 probe 没记宽高帧率只报不拦；自动产的 spec 只报（它们本来就先 probe 后 promote，
  真缺了是链路的毛病，硬了只会把自动链卡成「今天没有候选」）；
  定规矩之前已有的挂在 `data/legacy_no_probe_sources.json`，**只许减不许加**。
- **runner 看得见**（`materialize`）：工作流 dry-run 那一步按 URL 把认领这条 spec
  的 probe.json 从 HEAD 的树里取出来落盘——**只取 probe.json**，不拉缩略图墙；
  稀疏检出是 `blob:none` 的部分克隆，所以先一趟批量 fetch 把这几百份小 blob
  取回来（逐个懒取要几百次往返），再一次 `cat-file --batch` 读完。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
LEGACY_PATH = ROOT / "data" / "legacy_no_probe_sources.json"
CLAIM_KEY = "_no_probe_why"
PROBE_SUFFIX = "/probe.json"


def spec_urls(spec: dict) -> dict[str, str]:
    """`{源键: url}`——和 `probe_dry_run` 同一个宽容写法（spec 有毛病也别在这儿
    先抛，让 `validate_spec` 去报人话）。"""
    return ({str(k): str(v) for k, v in (spec.get("sources") or {}).items()}
            or {"": str(spec.get("source_url", ""))})


def is_auto(spec: dict) -> bool:
    return (spec.get("_production") or {}).get("status") == "ready_for_render"


def is_imported_master(spec: dict) -> bool:
    """已经渲好的导入成片（`_import.kind`）不从源片渲，覆盖这一层不管它。"""
    return (spec.get("_import") or {}).get("kind") == "finished_master_inspection"


def legacy_no_probe(path: Path = LEGACY_PATH) -> dict[str, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): sorted(v) for k, v in (data.get("reels") or {}).items()}


def missing_probe_keys(spec: dict, probes: dict[str, dict]) -> list[str]:
    """认领不到 probe.json 的源键（按 URL）。"""
    return sorted(k for k, url in spec_urls(spec).items() if url not in probes)


def _fps_value(expr: str, stored: object) -> float:
    """帧率数值按**分数式**算，和 render 的 `resolve_fps`（`float(Fraction)`）同一个口径。

    `fps_value` 这个字段新 probe 存的是 `round(fps, 3)`、老 probe 存的是全精度，
    拿它比会把 `30000/1001` 对 `30000/1001` 判成不一样（29.97 vs 29.97002997，
    相对差 1e-6，`check_sources_match` 按 1e-6 的容差比）——`zheng-rybakina`
    两条源在全库扫描里就这么被误报过。分数式解不出来才退回存的数。
    """
    try:
        return float(Fraction(expr))
    except (ValueError, ZeroDivisionError):
        return float(stored)


def source_dims(spec: dict, probes: dict[str, dict],
                ) -> tuple[dict[str, tuple[int, int, str, float]], list[str]]:
    """`({源键: (宽, 高, fps 写法, fps 数值)}, 没记宽高帧率的源键)`。

    顺序跟着 spec 的 `sources`（主源是第一条，和 render 里 `check_sources_match`
    拿到的 `paths` 同序）。认领了 `conform` 的源按基准尺寸算——基准是第一条
    **没认领**的源，和 `conform_sources` 取的同一条。
    """
    dims: dict[str, tuple[int, int, str, float]] = {}
    lacking: list[str] = []
    for key, url in spec_urls(spec).items():
        probe = probes.get(url)
        if probe is None:
            continue
        try:
            expr = str(probe["fps"])
            dims[key] = (int(probe["width"]), int(probe["height"]), expr,
                         _fps_value(expr, probe["fps_value"]))
        except (KeyError, TypeError, ValueError):
            lacking.append(key)
    declared = spec.get("conform") or {}
    if isinstance(declared, dict) and declared:
        ref = next((k for k in spec_urls(spec) if k not in declared), None)
        if ref in dims:
            rw, rh = dims[ref][:2]
            for key in declared:
                if key in dims:
                    dims[key] = (rw, rh, *dims[key][2:])
    return dims, lacking


def coverage_findings(spec: dict, probes: dict[str, dict], *,
                      legacy: dict[str, list[str]] | None = None,
                      ) -> tuple[list[str], list[str]]:
    """每条源都认领得到 probe.json 没有。返回 `(硬, 软)`。"""
    hard: list[str] = []
    soft: list[str] = []
    if is_imported_master(spec):
        return hard, soft
    legacy = legacy_no_probe() if legacy is None else legacy
    grandfathered = set(legacy.get(str(spec.get("slug") or ""), []))
    claims = spec.get(CLAIM_KEY) or {}
    if not isinstance(claims, dict):
        claims = {}
    urls = spec_urls(spec)
    for key in missing_probe_keys(spec, probes):
        label = key or "(主源)"
        why = str(claims.get(key) or "").strip()
        line = (f"  源 {label}（{urls[key][:90]}）一份 probe.json 都认领不上——"
                "宽高帧率、切点、死球、静音这几层对它全是哑的")
        if why:
            soft.append(f"{line}\n    已认领 {CLAIM_KEY}：{why}")
        elif key in grandfathered:
            soft.append(f"{line}（定规矩之前就有的，挂在 legacy_no_probe_sources）")
        elif is_auto(spec):
            soft.append(f"{line}（自动产的 spec 只报）")
        else:
            hard.append(f"{line}。\n    先跑一趟 `match-reel.yml mode=probe url=<这条>`"
                        "（多源的每一条都要，可以并排拨）；真 probe 不了就在 spec 顶层写 "
                        f"`\"{CLAIM_KEY}\": {{\"{key}\": \"<为什么>\"}}` 认领")
    _dims, lacking = source_dims(spec, probes)
    for key in lacking if len(urls) > 1 else ():     # 单源没有「对得上」可比
        soft.append(f"  源 {key or '(主源)'}：probe.json 是老的，没记宽高帧率——"
                    "几何这一层对它没查（重跑一趟 mode=probe 就有）")
    return hard, soft


def geometry_findings(spec: dict, probes: dict[str, dict],
                      check: Callable[..., None], error: type[Exception],
                      ) -> tuple[list[str], list[str]]:
    """拿 probe 的宽高帧率跑 render 里那道 `check_sources_match`。返回 `(硬, 软)`。

    只在**每条源都有宽高帧率**时才判——缺一条就等于拿半张表比，
    缺的那条由 `coverage_findings` 去报。
    """
    dims, lacking = source_dims(spec, probes)
    urls = spec_urls(spec)
    if len(urls) < 2 or lacking or set(dims) != set(urls):
        return [], []
    try:
        check(dict.fromkeys(dims), spec, dims=dims)
    except error as exc:
        return ["  按 probe.json 的宽高帧率预演 check_sources_match——render 下完源片后"
                "必红在同一句：\n    " + str(exc).replace("\n", "\n    ")], []
    return [], []


# ── 工作流用：按 URL 把认领这条 spec 的 probe.json 从 HEAD 的树里取出来 ─────────

def _git(args: list[str], cwd: Path, stdin: bytes | None = None,
         env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, input=stdin,
                          capture_output=True, env=env)


def committed_probes(ref: str = "HEAD", cwd: Path = ROOT,
                     ) -> dict[str, tuple[str, bytes]]:
    """HEAD 的树里每一份 `output/*/reel/*/probe.json`：`{路径: (blob, 内容)}`。

    **不需要检出 `output/`**：`ls-tree` 只读树。部分克隆（runner 的稀疏检出是
    `blob:none`）里 blob 不在本地，逐个懒取是几百次往返——先一趟批量 fetch
    （git 自己懒取时用的就是这条命令），再 `cat-file --batch` 一次读完；
    读的那一步关掉懒取，fetch 没取回来的就当没有，别退回逐个往返。
    """
    listing = _git(["ls-tree", "-r", ref, "--", "output"], cwd).stdout.decode()
    wanted: dict[str, str] = {}
    for line in listing.splitlines():
        meta, _, path = line.partition("\t")
        parts = path.split("/")
        if (len(parts) == 5 and parts[2] == "reel" and parts[4] == "probe.json"
                and meta.split()[1:2] == ["blob"]):
            wanted[path] = meta.split()[2]
    if not wanted:
        return {}
    oids = "".join(f"{oid}\n" for oid in sorted(set(wanted.values()))).encode()
    promisor = _git(["config", "--get", "remote.origin.promisor"], cwd).stdout.strip()
    if promisor == b"true":
        # gc/maintenance 关掉：一趟 fetch 落一个包，别在 runner 上后台打包（ci.yml
        # 那段注释记过逐个懒取反复触发 gc.auto 比逐个 `git show` 还慢）。
        fetched = _git(["-c", "fetch.negotiationAlgorithm=noop", "-c", "gc.auto=0",
                        "-c", "maintenance.auto=false", "fetch", "-q",
                        "--no-tags", "--no-write-fetch-head", "--recurse-submodules=no",
                        "--filter=blob:none", "--stdin", "origin"], cwd, stdin=oids)
        if fetched.returncode:
            print("::warning::批量取 probe.json 失败："
                  + fetched.stderr.decode("utf-8", "replace")[-300:], file=sys.stderr)
    env = {**os.environ, "GIT_NO_LAZY_FETCH": "1"}
    out = _git(["cat-file", "--batch"], cwd, stdin=oids, env=env).stdout
    blobs: dict[str, bytes] = {}
    pos = 0
    while pos < len(out):
        head_end = out.index(b"\n", pos)
        head = out[pos:head_end].split()
        if len(head) < 3 or head[1] != b"blob":
            pos = head_end + 1          # `<oid> missing`
            continue
        size = int(head[2])
        blobs[head[0].decode()] = out[head_end + 1:head_end + 1 + size]
        pos = head_end + 1 + size + 1
    return {path: (oid, blobs[oid]) for path, oid in wanted.items() if oid in blobs}


def claim_paths(spec: dict, ref: str = "HEAD", cwd: Path = ROOT,
                ) -> dict[str, bytes]:
    """HEAD 的树里，`url` 是这条 spec 某一条源的那几份 probe.json：`{路径: 内容}`。
    按 `url` 字段精确比对——**不按 slug 猜**，否则会拿别的片子的切点来判。"""
    urls = {u for u in spec_urls(spec).values() if u}
    out: dict[str, bytes] = {}
    for path, (_oid, blob) in committed_probes(ref, cwd).items():
        try:
            if json.loads(blob).get("url") in urls:
                out[path] = blob
        except ValueError:
            continue
    return out


def materialize(spec: dict, ref: str = "HEAD", cwd: Path = ROOT) -> list[str]:
    """把认领这条 spec 的 probe.json 落到工作区（已经在的不动），返回它们的路径。"""
    written = []
    for path, blob in sorted(claim_paths(spec, ref, cwd).items()):
        dest = cwd / path
        if not dest.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob)
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("materialize",
                       help="按源片 URL 把 HEAD 里认领这条 spec 的 probe.json 落到工作区")
    m.add_argument("spec")
    m.add_argument("--ref", default="HEAD")
    args = ap.parse_args(argv)
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    paths = materialize(spec, args.ref)
    urls = spec_urls(spec)
    print(f"按 URL 认领到 {len(paths)} 份 probe.json（spec 有 {len(urls)} 条源）：")
    for path in paths:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
