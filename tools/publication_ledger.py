"""不可撤回发布的持久账本；独立于会被重渲替换的 output 目录。"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

BLOCKING = frozenset({"sending", "sent", "uncertain"})

#: 采访线账本里「这条已经发出去、正在发、或状态不明」的全部状态。比 `BLOCKING` 多
#: `accepted` / `delivered`：采访线的 `auto_push_interview_gate` 把 PushPlus 接收写成
#: 这两个（main 上采访账本绝大多数条目就是 `accepted`）。两个读者共用这一份：
#: `wants_auto_push` 拿它挡重发，`build_interview_request._protected` 拿它认「已推送」
#: ——各写一份就会分叉（2026-09-27 评审：锦织圭那条账本 `sent`、没有 pushed.json，
#: 被当成「自动链还没核没发」，全库测试对这条已发、手改过的 spec 只报）。
INTERVIEW_PUBLISHED = frozenset({"sending", "accepted", "delivered", "sent", "uncertain"})

#: 把 `interview_published` 读的采访账本目录钉到别处的环境变量——**只给测试用**，
#: 生产上没人设它（`tests/conftest.py::_empty_interview_ledger` 设）。
#:
#: **判据测试一律不许读真账本**（`reel_facts.REEL_LEDGER_DIR` 那条，竖版短片线早就是
#: 这个规矩）：真账本每推一条就变一次。来路（2026-09-27 评审）：
#: `build_interview_request._protected` 开始认账本之后，main 上
#: `test_人工请求的_claims跟进正式spec_没认领在build那一刻就红` 第 ③ 段——只把
#: `SPECS` / `OUTDIR` 指到 tmp_path、用的是**真的已发 slug**
#: `alcaraz-fritz-laver-cup-2026-interview`——读到了真账本里的 `accepted`，
#: `RuntimeError: 已确认版本受保护` 顶掉了它要测的 `ValueError("全称断言")`。
#: 分支自己的 CI 看不见（那条测试在分支的基点上还不存在），合进去才红。
#:
#: 每次调用时读环境变量，不在 import 时读：同一个文件会被按 `publication_ledger`
#: 和 `tools.publication_ledger` 两个名字各 import 一份，测试起的子进程也要认得到。
INTERVIEW_LEDGER_ENV = "TENNISLIVE_INTERVIEW_LEDGER_DIR"


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


def interview_published(repo: Path, slug: str) -> bool:
    """这条采访在发布账本里有没有任何一次「发出去 / 正在发 / 状态不明」。

    账本是权威发布状态（`output/…/pushed.json` 只是上一份成片的兼容标记，会被重渲
    替换、也可能从来没写过）。稀疏检出下文件不在盘上时 `load` 从 git index / HEAD 读。
    **账本读不了算「发过」**：状态不明时宁可当成已经不归自动链管。
    设了 `INTERVIEW_LEDGER_ENV` 就只读那个目录（测试用，见那行注释），不碰 `repo`。
    """
    pinned = os.environ.get(INTERVIEW_LEDGER_ENV)
    try:
        if pinned:
            path = Path(pinned) / f"{slug}.json"
            if not path.is_file():
                return False
            attempts = json.loads(path.read_text(encoding="utf-8")).get("attempts") or []
        else:
            attempts = load(repo, "interview", slug)["attempts"]
    except (ValueError, UnicodeDecodeError, AttributeError):
        return True
    return any(isinstance(row, dict) and row.get("status") in INTERVIEW_PUBLISHED
               for row in attempts)


def key(column: str, slug: str, fingerprint: str) -> str:
    return f"pushplus:{column}:{slug}:{fingerprint}"


def blocking_attempt(repo: Path, column: str, slug: str,
                     fingerprint: str) -> dict | None:
    wanted = key(column, slug, fingerprint)
    return next((row for row in load(repo, column, slug)["attempts"]
                 if row.get("key") == wanted and row.get("status") in BLOCKING), None)


def receipt_fields(receipt: str) -> dict:
    """流水号 + 这条微信推送的网页（PushPlus 消息详情页）。没有流水号就是空 dict。"""
    receipt = (receipt or "").strip()
    if not receipt:
        return {}
    from tennislive.publish.pushplus import message_url

    return {"pushplus_receipt": receipt, "message_url": message_url(receipt)}


def read_receipt_file(path: str) -> str:
    """读 push_reel / `tennislive publish pushplus` 写下的流水号 JSON；读不到返回空串。"""
    if not path:
        return ""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return str(data.get("receipt") or "").strip() if isinstance(data, dict) else ""


def write(repo: Path, column: str, slug: str, fingerprint: str, *,
          status: str, run_url: str, now: str, receipt: str = "") -> Path:
    ledger = load(repo, column, slug)
    wanted = key(column, slug, fingerprint)
    row = next((item for item in ledger["attempts"] if item.get("key") == wanted), None)
    if row is None:
        row = {"key": wanted, "fingerprint": fingerprint}
        ledger["attempts"].append(row)
    row.update({"status": status, "at": now, "run": run_url})
    if status == "sent" and receipt:
        row.update(receipt_fields(receipt))
    path = path_for(repo, column, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[自动推送] {column} 发布账本 {status}：{path}")
    return path
