"""orchestrate state 推送重试的三方合并判据。

来路（2026-08-26 run #360）：orchestrate 点完 run 提交 state，push 被拒后拿
`git pull --rebase` 重试，而冲突就发生在 `data/orchestration_state.json`
本身（另一方是 match-reel 的失败自愈 release_orchestration_claim）。rebase
对同一个 JSON 的内容冲突无解——abort 之后什么都没变，五次全撞同一个冲突，
state 丢失、下一班重复 dispatch。修法是 JSON 级三方合并；这里钉合并的语义，
工作流那头的接线钉在 test_orchestrate.test_编排工作流并发锁pipefail和state推送重试。
"""

import json
import subprocess
import sys
from pathlib import Path

from tools.merge_orchestration_state import merge_states


def _entry(day: str) -> dict:
    return {"column": "reel", "score": 60, "date": day}


def test_本趟新增的条目要落进远端最新的底子():
    base = {"dispatched": {}, "last_dispatch_at": "2026-08-25T20:00:00Z"}
    ours = {"dispatched": {"a-b": _entry("2026-08-26")},
            "last_dispatch_at": "2026-08-26T01:04:38Z"}
    theirs = {"dispatched": {"c-d": _entry("2026-08-26")},
              "last_dispatch_at": "2026-08-25T23:00:00Z"}
    merged = merge_states(base, ours, theirs)
    assert merged["dispatched"]["a-b"] == _entry("2026-08-26"), (
        "本趟点过的 run 没落库——下一班失忆重点，正是 run #360 的后果")
    assert merged["dispatched"]["c-d"] == _entry("2026-08-26"), (
        "远端别的班次记的条目被抹掉了")
    assert merged["last_dispatch_at"] == "2026-08-26T01:04:38Z", (
        "last_dispatch_at 要取两边较大的——它是「无人值守链最近一次真的"
        "点过 run」的唯一可见处")


def test_远端刚release的claim不许被合并复活():
    """**这一条是三方合并存在的全部理由。** 裸 union 也能让「本趟新增」落库，
    但它会把 match-reel 失败自愈刚从远端摘掉的 claim（base/ours 里都有、
    theirs 里没有、本趟没碰它）原样放回去——那条失败的 probe 从此永远不重试。
    """
    stuck = {"column": "reel", "score": 55, "date": "2026-08-25"}
    base = {"dispatched": {"stuck-slug": stuck}}
    ours = {"dispatched": {"stuck-slug": stuck,
                           "new-slug": _entry("2026-08-26")}}
    theirs = {"dispatched": {}}   # match-reel 的自愈刚把 stuck-slug 摘掉
    merged = merge_states(base, ours, theirs)
    assert "stuck-slug" not in merged["dispatched"], (
        "release 掉的 claim 被合并复活了——那条失败的 probe 永远不会重试")
    assert "new-slug" in merged["dispatched"]


def test_本趟的TTL清理不带进合并():
    """ours 相对 base 的**删除**不传播：TTL 清理下一趟 load_state 还会做，
    晚一轮无所谓；把删除混进合并会把「谁删的、为什么删」搅浑。"""
    old = {"column": "reel", "score": 40, "date": "2026-08-01"}
    base = {"dispatched": {"expired": old}}
    ours = {"dispatched": {}}          # load_state 按 TTL 清掉了 expired
    theirs = {"dispatched": {"expired": old}}
    merged = merge_states(base, ours, theirs)
    assert merged["dispatched"] == {"expired": old}


def test_本趟改写过的条目要盖过远端():
    base = {"dispatched": {"a-b": _entry("2026-08-20")}}
    ours = {"dispatched": {"a-b": _entry("2026-08-26")}}   # 同对手再交手
    theirs = {"dispatched": {"a-b": _entry("2026-08-20")}}
    merged = merge_states(base, ours, theirs)
    assert merged["dispatched"]["a-b"]["date"] == "2026-08-26"


def test_CLI缺文件坏JSON一律按空state不许抛(tmp_path):
    """这个工具跑在 push 重试的路上，抛异常等于把重试整个带崩——
    首次落库时 HEAD 上还没有 state 文件，就是「缺文件」这一支。"""
    ours = tmp_path / "ours.json"
    ours.write_text(json.dumps(
        {"dispatched": {"a-b": _entry("2026-08-26")}}), encoding="utf-8")
    bad = tmp_path / "theirs.json"
    bad.write_text("{not json", encoding="utf-8")
    out = tmp_path / "out.json"
    proc = subprocess.run(
        [sys.executable, "tools/merge_orchestration_state.py",
         "--base", str(tmp_path / "missing.json"), "--ours", str(ours),
         "--theirs", str(bad), "--out", str(out)],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent)
    assert proc.returncode == 0, proc.stderr
    merged = json.loads(out.read_text(encoding="utf-8"))
    assert merged["dispatched"] == {"a-b": _entry("2026-08-26")}
