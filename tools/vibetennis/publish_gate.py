#!/usr/bin/env python3
"""vibetennis 合进 main 之后该不该自动推微信——以及推前预占、推后记账。

和 `tools/auto_push_gate.py`（赛场之上）同一个形状、同一套账本
（`tools/publication_ledger.py`，栏目键 `vibetennis`），闸一道不少：

1. 路径形状必须是 `output/<日期>/vibetennis/<slug>/render.json`，而且还在仓库里
2. spec 和文案在 `specs/vibetennis/`
3. `qc_attestation.json` 受跟踪、`status=pass`，并且 spec / 文案 / 海报 / 成片的
   sha256 与字节数和凭证一致；`render.json` 钉的是这份凭证、有 Release `video_url`
4. spec 里显式写了 `push.auto=true`（默认关）
5. 没推过：持久账本没有挡路的记录、`pushed.json` 不在仓库里（查 `git ls-files`）
6. 海报 `poster.jpg` 在仓库里（推送第一屏）
7. 一趟最多一条

    publish_gate.py --changed <文件…>        # 选出该发的那一条（写 GITHUB_OUTPUT）
    publish_gate.py --reserve <outdir> --run URL --now T
    publish_gate.py --record <outdir> --run URL --now T --receipt-file R
    publish_gate.py --uncertain <outdir> --run URL --now T
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "src"))

from common import LEDGER_COLUMN, MARKER, POSTER_NAME, RENDER_JSON, SPEC_DIR  # noqa: E402
from publication_ledger import (blocking_attempt, read_receipt_file,  # noqa: E402
                                receipt_fields, write as write_ledger)


class Skip(Exception):
    """这一条不发，而且要说出为什么。"""


def tracked(repo: Path, path: Path) -> bool:
    rel = path.relative_to(repo) if path.is_absolute() else path
    out = subprocess.run(["git", "-C", str(repo), "ls-files", "--error-unmatch", "--", str(rel)],
                         capture_output=True)
    return out.returncode == 0


def blob(repo: Path, path: Path) -> bytes:
    rel = path.relative_to(repo) if path.is_absolute() else path
    try:
        return subprocess.check_output(["git", "-C", str(repo), "show", f":{rel.as_posix()}"],
                                       stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as exc:
        raise Skip(f"{rel} 在索引里但读取不到") from exc


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_qc(repo: Path, slug: str, outdir: Path) -> str:
    att = outdir / "qc_attestation.json"
    if not tracked(repo, att):
        raise Skip(f"{slug}：没有受跟踪的 qc_attestation.json（render.json 不能冒充质检通过）")
    qc_bytes = blob(repo, att)
    qc = json.loads(qc_bytes)
    if qc.get("status") != "pass" or qc.get("slug") != slug:
        raise Skip(f"{slug}：QC 凭证状态/slug 不匹配")
    spec, copy = SPEC_DIR / f"{slug}.json", SPEC_DIR / f"{slug}.xhs.txt"
    for name, path in (("spec", spec), ("copy", copy), ("poster", outdir / POSTER_NAME)):
        if not tracked(repo, path):
            raise Skip(f"{slug}：{path} 不在仓库里")
        if qc.get(f"{name}_sha256") != _sha(blob(repo, path)):
            raise Skip(f"{slug}：{path} 在质检后变过，重跑 tools/vibetennis/qc.py")
    render = json.loads(blob(repo, outdir / "render.json"))
    if render.get("qc_attestation_sha256") != _sha(qc_bytes):
        raise Skip(f"{slug}：render.json 指向的不是当前 QC 凭证")
    if not qc.get("film_sha256") or render.get("film_sha256") != qc["film_sha256"]:
        raise Skip(f"{slug}：render.json 与 QC 不是同一份成片")
    if int(render.get("video_bytes") or 0) != int(qc.get("film_bytes") or -1):
        raise Skip(f"{slug}：Release 文件大小与 QC 成片不一致")
    if not str(render.get("video_url") or "").startswith("https://github.com/"):
        raise Skip(f"{slug}：render.json 没有 Release video_url")
    return qc["film_sha256"]


def wants_auto_push(repo: Path, slug: str, outdir: Path) -> None:
    if not tracked(repo, outdir / "render.json"):
        raise Skip(f"{slug}：render.json 已不在仓库里")
    spec, copy = repo / SPEC_DIR / f"{slug}.json", repo / SPEC_DIR / f"{slug}.xhs.txt"
    if not spec.is_file() or not copy.is_file():
        raise Skip(f"{slug}：{SPEC_DIR}/ 里缺 spec 或文案")
    film_hash = validate_qc(repo, slug, outdir)
    auto = (json.loads(spec.read_text(encoding="utf-8")).get("push") or {}).get("auto")
    if auto is not True:
        raise Skip(f"{slug}：spec 里没写 push.auto=true（布尔量），不自动发")
    previous = blocking_attempt(repo, LEDGER_COLUMN, slug, film_hash)
    if previous:
        raise Skip(f"{slug}：发布账本已有 {previous.get('status')}（{previous.get('at')}），不重复发")
    if tracked(repo, outdir / MARKER):
        raise Skip(f"{slug}：已经推过了（{outdir / MARKER} 在仓库里）")
    if not tracked(repo, outdir / POSTER_NAME):
        raise Skip(f"{slug}：海报不在仓库里——推送第一屏就是它")


def pick(changed: list[str], repo: Path):
    picked, skipped = [], []
    for path in changed:
        m = RENDER_JSON.match(path)
        if not m:
            continue
        slug = m.group(2)
        outdir = Path(path).parent
        try:
            wants_auto_push(repo, slug, outdir)
            picked.append((slug, outdir))
        except Skip as why:
            skipped.append(str(why))
    for s in skipped:
        print(f"[跳过] {s}")
    if len(picked) > 1:
        print(f"::error::一次合并带进来 {len(picked)} 条 vibetennis 成片，一条都不自动发，请逐条手动")
        raise SystemExit(1)
    return picked[0] if picked else None


def ledger(repo: Path, outdir: Path, status: str, run: str, now: str, receipt: str = "") -> None:
    slug = outdir.name
    film_hash = validate_qc(repo, slug, outdir)
    previous = blocking_attempt(repo, LEDGER_COLUMN, slug, film_hash)
    if status == "sending" and previous:
        raise SystemExit(f"{slug} 已有 {previous.get('status')} 发布记录，禁止盲目重发")
    write_ledger(repo, LEDGER_COLUMN, slug, film_hash, status=status, run_url=run, now=now,
                 receipt=receipt)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--changed", nargs="*", default=[])
    ap.add_argument("--reserve", default="")
    ap.add_argument("--record", default="")
    ap.add_argument("--uncertain", default="")
    ap.add_argument("--run", default="")
    ap.add_argument("--now", default="")
    ap.add_argument("--receipt-file", default="")
    ap.add_argument("--repo", default=".")
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve()
    action = args.reserve or args.record or args.uncertain
    if action:
        outdir = Path(action)
        status = "sending" if args.reserve else "sent" if args.record else "uncertain"
        receipt = read_receipt_file(args.receipt_file) if args.record else ""
        try:
            ledger(repo, outdir, status, args.run, args.now, receipt)
        except Skip as why:
            raise SystemExit(str(why)) from why
        if args.record:
            fields = receipt_fields(receipt)
            (repo / outdir / MARKER).write_text(json.dumps(
                {"at": args.now, "run": args.run, **fields}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            print(f"[vibetennis] 记下已推送：{outdir / MARKER} {fields.get('message_url', '')}")
        return 0
    found = pick(args.changed, repo)
    if found:
        slug, outdir = found
        print(f"[vibetennis] 这次要发：{slug}（{outdir}）")
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            with open(out, "a", encoding="utf-8") as fh:
                fh.write(f"slug={slug}\noutdir={outdir.as_posix()}\nfound=true\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
