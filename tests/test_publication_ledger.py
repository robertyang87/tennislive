import subprocess
from pathlib import Path

from tools.publication_ledger import blocking_attempt, load, write


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_ledger_survives_sparse_checkout_and_blocks_unknown_retry(tmp_path: Path):
    _git(tmp_path, "init", "-q")
    ledger = write(tmp_path, "reel", "demo", "film-hash", status="sending",
                   run_url="run-1", now="2026-08-24T00:00:00Z")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "ledger")
    ledger.unlink()  # index/HEAD 有，稀疏工作区没有

    previous = blocking_attempt(tmp_path, "reel", "demo", "film-hash")
    assert previous and previous["status"] == "sending"


def test_same_slug_new_fingerprint_has_independent_idempotency_key(tmp_path: Path):
    _git(tmp_path, "init", "-q")
    write(tmp_path, "explainer", "demo", "v1", status="sent", run_url="r", now="t")
    assert blocking_attempt(tmp_path, "explainer", "demo", "v1")
    assert blocking_attempt(tmp_path, "explainer", "demo", "v2") is None
    assert load(tmp_path, "explainer", "demo")["channel"] == "pushplus"


def test_reel_and_explainer_reserve_before_irreversible_send():
    reel = Path(".github/workflows/auto-push-reel.yml").read_text(encoding="utf-8")
    irreversible = reel.index("python tools/push_reel.py", reel.index("- name: 推送到微信"))
    assert reel.index("--reserve") < irreversible
    assert "--uncertain" in reel and "data/reel_publish_ledger" in reel

    explainer = Path(".github/workflows/auto-push-explainer.yml").read_text(encoding="utf-8")
    assert explainer.index("--reserve") < explainer.index("tennislive publish pushplus")
    assert "--uncertain" in explainer and "data/explainer_publish_ledger" in explainer
