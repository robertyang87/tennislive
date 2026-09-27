"""推送到微信之后，那条消息的网页链接要记下来、能发进对话。

账号所有者 2026-09-27：「推送到微信之后，把推送到微信的那个网页链接也给我。
发到这个对话里」。链接是 PushPlus 的消息详情页
`https://www.pushplus.plus/shortMessage/<流水号>`（官方 OpenAPI 文档「消息详情」；
2026-09-27 拿两条真实流水号实测 200、页面标题就是那条推送）。

在这之前只有采访线把流水号记进 pushed.json；赛场之上和解说片的自动推送连
`--receipt-out` 都没传，推完只剩 `{"at", "run"}`，链接无从谈起。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

from tennislive.publish.pushplus import message_url, write_receipt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import auto_push_gate  # noqa: E402
import push_link  # noqa: E402
from publication_ledger import load, receipt_fields, write  # noqa: E402

WF = Path(".github/workflows")


def _run_scripts(workflow: str) -> str:
    """只看 `run:` 脚本（CLAUDE.md：查工作流看 run，不搜整份 yml 的文本）。"""
    doc = yaml.safe_load((WF / workflow).read_text(encoding="utf-8"))
    runs = []
    for job in doc["jobs"].values():
        for step in job.get("steps", []):
            if "run" in step:
                runs.append(step["run"])
    return "\n".join(runs)


def _calls(runs: str, pattern: str) -> list[str]:
    """`run:` 脚本里每一次匹配到的命令调用，连同 `\\` 续行。"""
    calls = []
    for m in re.finditer(pattern, runs):
        out = []
        for line in runs[m.start():].split("\n"):
            out.append(line)
            if not line.rstrip().endswith("\\"):
                break
        calls.append("\n".join(out))
    return calls


def test_消息网页就是官方文档里那个形状():
    assert message_url("2f100670d7f742809ddf5ec8fb6dbb3d") == (
        "https://www.pushplus.plus/shortMessage/2f100670d7f742809ddf5ec8fb6dbb3d")
    # 没有流水号就没有链接——不编一个
    assert message_url("") == ""
    assert message_url("   ") == ""
    # 实测回「接口不存在」的那个形状不许出现
    assert "shortCode=" not in message_url("x") and ".html" not in message_url("x")


def test_流水号凭据带着消息网页(tmp_path: Path):
    path = write_receipt(tmp_path / "r.json", "abc123")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert data == {"receipt": "abc123",
                    "message_url": "https://www.pushplus.plus/shortMessage/abc123"}


def test_记下已推送时pushed_json里有message_url(tmp_path: Path, capsys):
    outdir = tmp_path / "output/2026-09-27/reel/demo"
    outdir.mkdir(parents=True)
    marker = auto_push_gate.record(outdir, "run-url", "2026-09-27T00:00:00Z", "abc123")
    data = json.loads(marker.read_text(encoding="utf-8"))
    assert data["pushplus_receipt"] == "abc123"
    assert data["message_url"] == message_url("abc123")
    assert data["at"] and data["run"] == "run-url"
    assert "微信推送网页：https://www.pushplus.plus/shortMessage/abc123" in capsys.readouterr().out


def test_没流水号也照样记已推送_但要出声(tmp_path: Path, capsys):
    """消息已经发了：不记 pushed.json 等于让自动闸以为没发过、再发一遍。"""
    outdir = tmp_path / "output/2026-09-27/reel/demo"
    outdir.mkdir(parents=True)
    marker = auto_push_gate.record(outdir, "run-url", "now")
    data = json.loads(marker.read_text(encoding="utf-8"))
    assert "message_url" not in data and data["run"] == "run-url"
    assert "::warning::" in capsys.readouterr().out


def test_账本的sent那一笔带着流水号和网页(tmp_path: Path):
    write(tmp_path, "reel", "demo", "fp", status="sending", run_url="r", now="t0")
    write(tmp_path, "reel", "demo", "fp", status="sent", run_url="r", now="t1", receipt="abc")
    row = load(tmp_path, "reel", "demo")["attempts"][0]
    assert row["status"] == "sent" and row["message_url"] == message_url("abc")
    # 预占 / 状态不明不许挂流水号——那两种状态下平台不一定收下过
    write(tmp_path, "reel", "demo2", "fp", status="uncertain", run_url="r", now="t", receipt="abc")
    assert "message_url" not in load(tmp_path, "reel", "demo2")["attempts"][0]
    assert receipt_fields("") == {}


def test_push_link按slug读出最近一次推送的网页(tmp_path: Path):
    old = tmp_path / "output/2026-09-26/reel/demo"
    new = tmp_path / "output/2026-09-27/reel/demo"
    for d in (old, new):
        d.mkdir(parents=True)
    (old / "pushed.json").write_text(json.dumps({"at": "2026-09-26T01:00:00Z", "run": "r"}),
                                     encoding="utf-8")
    auto_push_gate.record(new, "r", "2026-09-27T01:00:00Z", "fresh")
    rows = push_link.pushes(tmp_path, "demo")
    assert rows[0]["message_url"] == message_url("fresh")
    # 老的那一次没流水号：照实说取不到，不拼链接
    text = push_link.describe(rows[1])
    assert "取不到" in text and "pushplus.plus" not in text


def test_push_link把链接写进run摘要(tmp_path: Path):
    receipt = tmp_path / "r.json"
    write_receipt(receipt, "abc")
    summary = tmp_path / "summary.md"
    assert push_link.main(["--receipt-file", str(receipt), "--slug", "demo",
                           "--summary", str(summary)]) == 0
    assert message_url("abc") in summary.read_text(encoding="utf-8")


def test_三条线的推送步骤都把流水号传到记账那一步():
    """推送那一步 --receipt-out，记账那一步 --receipt-file，链接进 run 摘要。

    反过来：只要有一条线没接上，那条线推完 pushed.json 里就没有 message_url，
    会话就给不出链接——赛场之上和解说片在 2026-09-27 之前正是这样。
    """
    for workflow, sender in (("auto-push-reel.yml", "tools/push_reel.py"),
                             ("match-reel.yml", "tools/push_reel.py"),
                             ("auto-push-explainer.yml", "tennislive publish pushplus"),
                             ("auto-push-interview.yml", "tools/push_reel.py")):
        runs = _run_scripts(workflow)
        # 真发的那一次调用：跳过 `--stage page/check` 这些不发消息的
        calls = [c for c in _calls(runs, re.escape(sender)) if "--stage" not in c]
        assert calls, f"{workflow}：找不到发微信的那次 {sender}"
        for call in calls:
            assert "--receipt-out" in call, f"{workflow}：推送那一步没写流水号凭据：{call}"
        # 「记下已推送」那一次 gate 调用本身（连同续行）要带 --receipt-file——
        # 不能拿窗口扫：下一行 push_link.py 也带 --receipt-file，会冒充它。
        gates = [c for c in _calls(runs, r"python tools/auto_push\w*_gate\.py") if "--record" in c]
        assert gates, workflow
        assert all("--receipt-file" in c for c in gates), (
            f"{workflow}：记下已推送那一步没读流水号——pushed.json 里不会有 message_url")
        assert "tools/push_link.py" in runs and "$GITHUB_STEP_SUMMARY" in runs, (
            f"{workflow}：链接没进 run 摘要")


def test_摘要那一步挂了也不许挡住记账():
    """它排在微信已发之后、pushed.json 提交之前：崩了就是「消息发了、标记没落库」。"""
    for workflow in ("auto-push-reel.yml", "match-reel.yml", "auto-push-explainer.yml",
                     "auto-push-interview.yml", "push-existing.yml"):
        runs = _run_scripts(workflow)
        for m in re.finditer(r"python tools/push_link\.py[^\n]*\\\n[^\n]*\\\n\s*\|\|", runs):
            break
        else:
            raise AssertionError(f"{workflow}：push_link 那一行后面要带 `|| echo ::warning::`")


def test_解说线那条CLI推送也写流水号凭据(tmp_path: Path, monkeypatch):
    """auto-push-explainer 发微信走的是 `tennislive publish pushplus`，不是 push_reel。"""
    from types import SimpleNamespace

    from tennislive import cli

    package = tmp_path / "pkg"
    package.mkdir()
    (package / "xiaohongshu.txt").write_text("标题\n\n正文", encoding="utf-8")
    (package / "push.html").write_text("<div>稿</div>", encoding="utf-8")
    monkeypatch.setattr("tennislive.publish.pushplus.push", lambda *a, **k: "r-777")
    monkeypatch.setattr("tennislive.render.pushmsg.drop_dead_copy_button",
                        lambda html, expect="": (html, ""))
    out = tmp_path / "receipt.json"
    assert cli.cmd_publish_pushplus(SimpleNamespace(dir=str(package), receipt_out=str(out))) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["message_url"] == message_url("r-777")
    # 老调用方（不传 receipt_out）照旧能跑
    assert cli.cmd_publish_pushplus(SimpleNamespace(dir=str(package))) == 0
