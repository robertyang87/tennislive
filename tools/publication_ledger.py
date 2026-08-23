"""不可撤回发布的持久账本；独立于会被重渲替换的 output 目录。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

BLOCKING = frozenset({"sending", "sent", "uncertain"})


def _tracked(repo: Path, path: Path) -> bool:
    rel = path.relative_to(repo) if path.is_absolute() else path
    return subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--error-unmatch", str(rel)],
        capture_output=True, check=False).returncode == 0


def _bytes(repo: Path, path: Path) -> bytes:
    if path.is_file():
        return path.read_bytes()
    rel = path.relative_to(repo) if path.is_absolute() else path
    proc = subprocess.run(["git", "-C", str(repo), "show", f"HEAD:{rel.as_posix()}"],
                          capture_output=True, check=False)
    if proc.returncode:
        raise ValueError(f"读取不到发布账本 {rel}")
    return proc.stdout


def path_for(repo: Path, column: str, slug: str) -> Path:
    return repo / "data" / f"{column}_publish_ledger" / f"{slug}.json"


def load(repo: Path, column: str, slug: str) -> dict:
    path = path_for(repo, column, slug)
    if not path.is_file() and not _tracked(repo, path):
        return {"slug": slug, "channel": "pushplus", "attempts": []}
    try:
        data = json.loads(_bytes(repo, path))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"{path} 损坏，未知发布状态下禁止继续") from exc
    data.setdefault("attempts", [])
    return data


def key(column: str, slug: str, fingerprint: str) -> str:
    return f"pushplus:{column}:{slug}:{fingerprint}"


def blocking_attempt(repo: Path, column: str, slug: str,
                     fingerprint: str) -> dict | None:
    wanted = key(column, slug, fingerprint)
    return next((row for row in load(repo, column, slug)["attempts"]
                 if row.get("key") == wanted and row.get("status") in BLOCKING), None)


def write(repo: Path, column: str, slug: str, fingerprint: str, *,
          status: str, run_url: str, now: str) -> Path:
    ledger = load(repo, column, slug)
    wanted = key(column, slug, fingerprint)
    row = next((item for item in ledger["attempts"] if item.get("key") == wanted), None)
    if row is None:
        row = {"key": wanted, "fingerprint": fingerprint}
        ledger["attempts"].append(row)
    row.update({"status": status, "at": now, "run": run_url})
    path = path_for(repo, column, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[自动推送] {column} 发布账本 {status}：{path}")
    return path
