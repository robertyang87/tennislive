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


def test_采访账本钉到别处之后不读真账本(tmp_path: Path, monkeypatch, _empty_interview_ledger):
    """`_empty_interview_ledger` 把 `interview_published` 钉到空目录——拿真的已发 slug
    走 `build_interview_request` 的测试，不许读到真账本（2026-09-27 合并 main 时
    `test_人工请求的_claims跟进正式spec_没认领在build那一刻就红` 就是被真账本的
    `accepted` 顶掉的）。主语钉在一条**真的推过**的采访上：不钉就是 True。
    """
    from tools.publication_ledger import INTERVIEW_LEDGER_ENV, interview_published

    repo = Path(__file__).resolve().parents[1]
    slug = "alcaraz-fritz-laver-cup-2026-interview"
    assert not interview_published(repo, slug), "钉了空账本，却还是读到了真账本"
    # 钉住的目录照常认状态：发过 / 读不了都算「发过」，空的不算
    ledger = _empty_interview_ledger / f"{slug}.json"
    ledger.write_text('{"attempts": []}', encoding="utf-8")
    assert not interview_published(repo, slug)
    ledger.write_text('{"attempts": [{"status": "accepted"}]}', encoding="utf-8")
    assert interview_published(repo, slug)
    ledger.write_text("{坏的", encoding="utf-8")
    assert interview_published(repo, slug), "账本读不了：状态不明，按发过算"
    # 对照组：不钉就读真账本——这条真的推过（主语不是空转）
    monkeypatch.delenv(INTERVIEW_LEDGER_ENV)
    assert interview_published(repo, slug), "对照组：真账本里这条是 accepted"
