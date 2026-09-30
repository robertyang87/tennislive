"""Explicit message-only correction for an already-published reel.

This does not re-attest video or loosen native QC. The original film, spec,
render inputs and old ledger remain immutable. Only an exact, tracked correction
manifest may have a separate delivery identity. Native reservation is still
required before POST; changing a revision label cannot bypass deduplication.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from publication_ledger import BLOCKING, key, load

NAME = "publication_revision.json"
THEME_SOURCES = frozenset({
    "src/tennislive/design_tokens.py", "src/tennislive/render/push_style.py",
    "tools/push_reel.py", "tools/publication_revision.py", "tools/auto_push_gate.py",
})


class RevisionError(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _head(repo: Path, rel: str) -> bytes | None:
    done = subprocess.run(["git", "-C", str(repo), "show", f"HEAD:{rel}"],
                          capture_output=True, check=False)
    return done.stdout if done.returncode == 0 else None


def _read(repo: Path, rel: str) -> bytes:
    path = repo / rel
    if path.resolve().is_relative_to(repo) is False or path.is_symlink():
        raise RevisionError(f"revision path escapes repository: {rel}")
    data = _head(repo, rel)
    if data is None:
        raise RevisionError(f"revision input is not committed: {rel}")
    if path.exists() and path.read_bytes() != data:
        raise RevisionError(f"revision input changed after checkout: {rel}")
    return data


def _json(data: bytes, label: str) -> dict:
    try:
        result = json.loads(data)
    except (ValueError, UnicodeDecodeError) as exc:
        raise RevisionError(f"invalid revision JSON: {label}") from exc
    if not isinstance(result, dict):
        raise RevisionError(f"revision JSON must be an object: {label}")
    return result


def _asset(repo: Path, rel_dir: str, descriptor: dict, *, suffix: str) -> bytes:
    if not isinstance(descriptor, dict):
        raise RevisionError("missing revision asset descriptor")
    name = descriptor.get("path")
    if (not isinstance(name, str) or Path(name).name != name or name in {"", ".", ".."}
            or not name.endswith(suffix) or "/" in name or "\\" in name):
        raise RevisionError("revision assets must be basenames in the original output directory")
    data = _read(repo, f"{rel_dir}/{name}")
    if descriptor.get("sha256") != sha(data) or descriptor.get("bytes") != len(data):
        raise RevisionError(f"revision asset hash/size mismatch: {name}")
    return data


def has_revision(repo: Path, outdir: Path) -> bool:
    repo = repo.resolve()
    directory = (outdir if outdir.is_absolute() else repo / outdir).resolve()
    if not directory.is_relative_to(repo):
        if (directory / NAME).exists():
            raise RevisionError("output directory escapes repository")
        return False  # no correction: preserve legacy standalone sender behavior
    rel = (directory.relative_to(repo) / NAME).as_posix()
    return (directory / NAME).exists() or _head(repo, rel) is not None


@dataclass(frozen=True)
class Revision:
    fingerprint: str
    stat_card_name: str
    manifest: dict


def resolve(repo: Path, slug: str, outdir: Path, film_sha256: str, *,
            phase: str = "gate", run_url: str = "") -> Revision | None:
    """Validate one frozen correction; phase is gate/reserve/send/finish.

    The content identity excludes revision_id, parent receipt and provenance-only
    fields. Relabelling identical content cannot create another sendable revision.
    Every stage validates the same committed manifest and assets. The sending
    reservation must itself already exist at HEAD before a POST is allowed.
    """
    repo = repo.resolve()
    outdir = (outdir if outdir.is_absolute() else repo / outdir).resolve()
    if not outdir.is_relative_to(repo):
        raise RevisionError("output directory escapes repository")
    rel_dir = outdir.relative_to(repo).as_posix()
    manifest_rel = f"{rel_dir}/{NAME}"
    raw = _head(repo, manifest_rel)
    if raw is None and not (outdir / NAME).exists():
        return None
    if phase not in {"gate", "reserve", "send", "finish"}:
        raise RevisionError("unknown revision validation phase")
    if not re.fullmatch(r"output/\d{4}-\d\d-\d\d/reel/" + re.escape(slug), rel_dir):
        raise RevisionError("message correction is restricted to the original reel output")
    m = _json(_read(repo, manifest_rel), NAME)
    if (m.get("version") != 1 or m.get("kind") != "message-correction"
            or m.get("slug") != slug or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}",
                                                        str(m.get("revision_id", "")))):
        raise RevisionError("invalid message-correction identity")
    render = _json(_read(repo, f"{rel_dir}/render.json"), "render.json")
    film = m.get("film")
    if film != {"sha256": film_sha256, "url": render.get("video_url"),
                "bytes": render.get("video_bytes")}:
        raise RevisionError("revision does not describe the original QC-validated film")
    archive_desc = m.get("previous_pushed", {})
    if archive_desc.get("path") == "pushed.json":
        raise RevisionError("previous receipt must be archived, not the active marker")
    archive = _json(_asset(repo, rel_dir, archive_desc, suffix=".json"), "previous_pushed")
    parent = m.get("parent_receipt")
    if not re.fullmatch(r"[a-fA-F0-9]{32}", str(parent or "")) or archive.get("pushplus_receipt") != parent:
        raise RevisionError("archived marker does not match the exact parent receipt")
    card_desc = m.get("stat_card", {})
    if card_desc.get("path") == "stat_card.jpg":
        raise RevisionError("corrected card must not overwrite the original render input")
    _asset(repo, rel_dir, card_desc, suffix=".jpg")
    _json(_asset(repo, rel_dir, m.get("stats_source", {}), suffix=".json"), "stats_source")
    copy = _read(repo, f"specs/reels/{slug}.xhs.txt")
    page = _read(repo, f"{rel_dir}/copy.html")
    if m.get("copy_sha256") != sha(copy) or m.get("copy_page_sha256") != sha(page):
        raise RevisionError("revision copy changed after approval")
    sources = m.get("theme_sources")
    if not isinstance(sources, dict) or set(sources) != THEME_SOURCES:
        raise RevisionError("revision must pin every shared theme source")
    for path, expected in sources.items():
        if expected != sha(_read(repo, path)):
            raise RevisionError(f"revision theme changed after approval: {path}")
    identity = {"film": film, "stat_card_sha256": card_desc["sha256"],
                "copy_sha256": m["copy_sha256"], "copy_page_sha256": m["copy_page_sha256"],
                "theme_sources": sources}
    fingerprint = "content-revision:" + sha(json.dumps(identity, sort_keys=True,
                                                     separators=(",", ":")).encode())
    wanted = key("reel", slug, fingerprint)
    ledger_rel = f"data/reel_publish_ledger/{slug}.json"
    # HEAD proof is mandatory at send; local dirty receipt/reservation cannot authorize POST.
    if phase == "send":
        ledger = _json(_read(repo, ledger_rel), "publication ledger")
    else:
        ledger = load(repo, "reel", slug)
    rows = ledger.get("attempts")
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise RevisionError("invalid publication ledger")
    own = [r for r in rows if r.get("key") == wanted]
    if len(own) > 1:
        raise RevisionError("duplicate content identity in publication ledger")
    other = [r for r in rows if r.get("key") != wanted]
    if any(r.get("status") in {"sending", "uncertain"} for r in other):
        raise RevisionError("another publication attempt is pending or uncertain")
    sent = [r for r in other if r.get("status") == "sent" and r.get("pushplus_receipt")]
    latest = max(enumerate(sent), key=lambda ir: (str(ir[1].get("at", "")), ir[0]))[1] if sent else None
    if latest is None or latest.get("pushplus_receipt") != parent:
        raise RevisionError("revision parent is not the latest confirmed publication")
    if any(archive.get(field) != latest.get(field) for field in ("at", "run")):
        raise RevisionError("archive is not the exact historical parent marker")
    # v1 deliberately handles one correction of the original film publication,
    # not a generalized correction chain with unproven film lineage.
    if latest.get("fingerprint") != film_sha256:
        raise RevisionError("v1 correction parent must be the original film publication")
    if phase == "send" and ((outdir / "pushed.json").exists()
                             or _head(repo, f"{rel_dir}/pushed.json") is not None):
        raise RevisionError("active pushed.json already exists; correction POST is forbidden")
    if phase in {"gate", "reserve"} and own and own[0].get("status") in BLOCKING:
        raise RevisionError("this exact correction has already been reserved or sent")
    if phase in {"send", "finish"}:
        allowed = {"sending"} if phase == "send" else {"sending", "uncertain", "sent"}
        if (not run_url or not own or own[0].get("status") not in allowed
                or own[0].get("run") != run_url):
            raise RevisionError("correction requires its own persisted reservation in this run")
    return Revision(fingerprint, card_desc["path"], m)


def claim_post(revision: Revision, run_url: str, directory: Path) -> Path:
    """At most one POST invocation per reserved correction in this runner.

    Durable ledger reservation blocks another job/run; this exclusive local claim
    also blocks accidental repeated sender invocations before outer bookkeeping.
    A claim left by a failed/unknown POST is deliberately not cleared automatically.
    """
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / ("reel-correction-" + sha((revision.fingerprint + run_url).encode()) + ".json")
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise RevisionError("this runner has already started the correction POST; do not retry blindly") from exc
    with os.fdopen(fd, "w") as stream:
        json.dump({"fingerprint": revision.fingerprint, "run": run_url, "status": "post-started"}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    return target
