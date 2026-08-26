import json
from pathlib import Path

from tools.release_orchestration_claim import release_claim


def test_失败claim从远端最新state释放且幂等(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({
        "dispatched": {"medvedev-damm": {"date": "2026-08-25"}},
        "last_dispatch_at": "2026-08-26T01:04:38Z",
    }), encoding="utf-8")

    assert release_claim(path, "medvedev-damm") is True
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["dispatched"] == {}
    assert saved["last_dispatch_at"] == "2026-08-26T01:04:38Z"
    assert release_claim(path, "medvedev-damm") is False


def test_失败自愈工作流必须先读远端最新state再摘():
    body = Path(".github/workflows/match-reel.yml").read_text(encoding="utf-8")
    block = body.split("- name: probe 失败摘 state（自愈）", 1)[1]
    block = block.split("- name:", 1)[0]
    assert block.index('git fetch origin "$BRANCH"') < block.index(
        "release_orchestration_claim.py"), (
        "workflow_dispatch checkout 是派发前的旧 SHA；不先 fetch 最新 main，"
        "仍会把已经写入远端的 claim 看成不存在")
    assert 'git switch --detach "origin/$BRANCH"' in block
    assert "for attempt in $(seq 1 10)" in block
