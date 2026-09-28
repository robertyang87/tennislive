"""tools/interview_draft_hold.py —— 「这份草稿停着没」：auto-render 早退探针和 promote 共用一个判据。

来路（2026-09-28 量的，run 日志逐趟解析）：`interview-auto-render.yml` 的「没活就早退」原来按
**文件数**数草稿。main 上 4 份草稿自 8/30 起一份都提升不了（两份挂人工复核、两份过了赛果窗口），
DRAFTS 恒为 4——9/25~9/28 的 60 趟 run 里 39 趟跑满全量（平均 98 秒，早退一趟 9~16 秒）、
「提升 0 条 / 跳过 4 条」、什么都没提交也没 dispatch。

判据钉三件事：
  ① 停着的草稿不算活；标记一去掉，下一趟就算（没有任何缓存记着「它停过」）；
  ② 探针和 promote 用的是**同一个函数**——promote 跳过的原因就是探针报的原因；
  ③ 工作流那一步的 `run:` 原文真跑一遍：只剩停着的草稿 → work=false，停着的印进日志和摘要。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_TOOLS = ROOT / "tools"
_WF = ROOT / ".github" / "workflows" / "interview-auto-render.yml"


@pytest.fixture()
def hold():
    sys.path.insert(0, str(_TOOLS))
    import interview_draft_hold as h  # noqa: PLC0415

    return h


def _draft(**extra) -> dict:
    """promote 能拿去查赛果的最小自动草稿（形状照 `draft_interview_spec.build_spec`）。"""
    base = {
        "_draft": True,
        "slug": "zverev-cincinnati-2026-r3",
        "url": "https://example.test/oncourt",
        "source_title": "Cincinnati 2026 R3 Alexander Zverev Interview",
        "requested_content_type": "on_court",
        "zh": ["a"],
        "_zh_draft": ["a"],
        "_interviewee_en": "Alexander Zverev",
        "source_verification": {"status": "verified", "detected_type": "on_court"},
        "match": {"id": "2026:cincinnati:r3:alexander-zverev", "event": "辛辛那提大师赛"},
    }
    base.update(extra)
    return base


# ── ① 判据本身 ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("extra", "needle"), [
    ({"manual_review_required": "等同场集锦的 lead_in"}, "已标记人工复核"),
    ({"zh": [], "_zh_draft": []}, "连译文草稿都没有"),
    ({"source_verification": {"status": "candidate", "detected_type": "on_court"}},
     "来源身份尚未确认"),
    ({"source_verification": {"status": "verified", "detected_type": "presser"}},
     "来源身份尚未确认"),
    ({"_interviewee_en": "", "source_title": "hello there"}, "认不出受访者"),
])
def test_停着的草稿各有一句原因(hold, extra, needle):
    assert hold.draft_hold_reason(_draft()) == "", "对照组：完整的自动草稿要算活"
    assert needle in hold.draft_hold_reason(_draft(**extra))


def test_人工复核排在没译文前面_人写的原因不许被盖掉(hold):
    """`wang-vekic-singapore-2026-r1-interview` 的 `zh` 是刻意清空的，它自己的
    `manual_review_required` 写着「这不是『翻译没成』」。"""
    why = hold.draft_hold_reason(_draft(zh=[], _zh_draft=[], manual_review_required="等官方场上采访"))
    assert why.startswith("已标记人工复核（等官方场上采访")


def test_过了赛果窗口的草稿停着_窗口内和没盖章的照旧算活(hold):
    """promote 只翻「今天往前 DIGEST_DAYS_BACK 天」的赛果；建草稿那天早于窗口，这场球只会更早，
    promote 再也查不到。留 1 天余量：宁可多空转一天，不许把还查得到的草稿停掉。"""
    today = date(2026, 9, 28)
    # 窗口是 today-3..today（DIGEST_DAYS_BACK=3），再留 1 天：4 天前建的算活，5 天前的停
    edge = today - timedelta(days=hold.DIGEST_DAYS_BACK + 1)
    stale = edge - timedelta(days=1)

    def at(day: date) -> str:
        return f"{day.isoformat()}T04:00:00Z"  # 北京当天中午

    assert hold.draft_hold_reason(_draft(_drafted_at=at(edge)), today=today) == ""
    assert "赛果回看窗口" in hold.draft_hold_reason(_draft(_drafted_at=at(stale)), today=today)
    # 北京日期按 UTC+8 算：UTC 前一天 20:00 已经是北京这一天
    late = (edge - timedelta(days=1)).isoformat() + "T20:00:00Z"
    assert hold.drafted_day({"_drafted_at": late}) == edge
    assert hold.draft_hold_reason(_draft(_drafted_at=late), today=today) == ""
    # 老草稿没盖章 / 章读不懂：不按年龄停（宁可多跑全量）
    assert hold.draft_hold_reason(_draft(), today=today) == ""
    assert hold.draft_hold_reason(_draft(_drafted_at="上周"), today=today) == ""
    assert hold.STALE_AFTER_DAYS > hold.DIGEST_DAYS_BACK, "余量不许拿掉"


def test_读不了的草稿记停着_不炸(hold, tmp_path):
    (tmp_path / "bad.draft.json").write_text("{", encoding="utf-8")
    (tmp_path / "list.draft.json").write_text("[]", encoding="utf-8")
    (tmp_path / "ok.draft.json").write_text(json.dumps(_draft()), encoding="utf-8")
    (tmp_path / "formal.json").write_text(json.dumps(_draft()), encoding="utf-8")
    actionable, held = hold.scan(tmp_path)
    assert [p.name for p, _ in actionable] == ["ok.draft.json"], "正式 spec 不是草稿，不数"
    assert sorted((p.name, why) for p, why in held) == [
        ("bad.draft.json", "读不了"), ("list.draft.json", "读不了")]


def _cli(specs: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_TOOLS / "interview_draft_hold.py"), "--count-actionable",
         "--specs", str(specs)], capture_output=True, text=True, timeout=60)


def test_停着的草稿去掉标记_下一趟就数得到(tmp_path):
    """探针每一趟都从 checkout 现判，没有「停过」的记忆：人改完、删掉 `manual_review_required`，
    下一趟 `--count-actionable` 就是 1（push 到 `specs/interviews/*.json` 本身也叫醒工作流）。"""
    path = tmp_path / "buse-winston-salem-2026-r.draft.json"
    path.write_text(json.dumps(_draft(manual_review_required="等 lead_in")), encoding="utf-8")
    first = _cli(tmp_path)
    assert first.returncode == 0, first.stderr
    assert first.stdout.strip() == "0"
    assert first.stderr.startswith("[草稿停着] 1 份") and "buse-winston-salem-2026-r" in first.stderr
    assert "\n  buse-winston-salem-2026-r.draft.json：已标记人工复核（等 lead_in）" in first.stderr

    fixed = json.loads(path.read_text(encoding="utf-8"))
    del fixed["manual_review_required"]
    path.write_text(json.dumps(fixed), encoding="utf-8")
    second = _cli(tmp_path)
    assert second.returncode == 0, second.stderr
    assert second.stdout.strip() == "1"
    assert second.stderr == "", "没有停着的就一个字都不印"


_STDLIB_ONLY = r"""
import importlib.abc, runpy, sys
from pathlib import Path
tools = Path(sys.argv[1])
ok = set(sys.stdlib_module_names) | {p.stem for p in tools.glob("*.py")}

class OnlyStdlib(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        top = name.split(".")[0]
        if top not in ok and not top.startswith("_sysconfigdata"):
            raise ModuleNotFoundError(f"No module named {name!r}（探针的系统 python3 上没有）")
        return None

sys.meta_path.insert(0, OnlyStdlib())
sys.argv = [str(tools / "interview_draft_hold.py"), "--count-actionable"]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


def test_探针那一侧只用标准库():
    """探针跑在 runner 的**系统 python3** 上，那时 pip 还没装（`tennislive` 包也没装）——
    所以判据不能留在 `promote_interview_draft`（它顶层 import `tennislive.zh`）。"""
    proc = subprocess.run([sys.executable, "-c", _STDLIB_ONLY, str(_TOOLS)], cwd=ROOT,
                          env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert re.fullmatch(r"\d+\n", proc.stdout), proc.stdout


# ── ② promote 用的是同一个判据 ───────────────────────────────────────────────


@pytest.fixture()
def promote(monkeypatch):
    sys.path.insert(0, str(_TOOLS))
    import promote_interview_draft as p  # noqa: PLC0415

    return p


def test_promote跳过的原因就是探针报的原因_全停着就不抓赛果(promote, hold, monkeypatch, tmp_path):
    (tmp_path / "a.draft.json").write_text(
        json.dumps(_draft(manual_review_required="等 lead_in")), encoding="utf-8")
    (tmp_path / "b.draft.json").write_text(
        json.dumps(_draft(_drafted_at="2026-08-29T21:16:56Z")), encoding="utf-8")
    monkeypatch.setattr(promote, "SPECS", tmp_path)

    def _boom():
        raise AssertionError("全都停着还去抓赛果")

    monkeypatch.setattr(promote, "_collect_digests", _boom)
    promoted, skipped = promote.promote_all(write=True)
    _, held = hold.scan(tmp_path)
    assert promoted == []
    assert skipped == [f"{p.name}: {why}" for p, why in held]
    assert len(skipped) == 2 and "赛果回看窗口" in skipped[1]
    assert (tmp_path / "a.draft.json").exists() and (tmp_path / "b.draft.json").exists()


def test_promote有能动的才抓赛果_停着的照旧列在跳过里(promote, monkeypatch, tmp_path):
    (tmp_path / "a.draft.json").write_text(
        json.dumps(_draft(manual_review_required="等 lead_in")), encoding="utf-8")
    (tmp_path / "b.draft.json").write_text(json.dumps(_draft()), encoding="utf-8")
    monkeypatch.setattr(promote, "SPECS", tmp_path)
    calls = []

    class _Empty:
        results = []

    monkeypatch.setattr(promote, "_collect_digests", lambda: calls.append(1) or [_Empty()])
    promoted, skipped = promote.promote_all(write=False)
    assert calls == [1], "有一份能动的，就要去查赛果"
    assert promoted == []
    assert skipped[0].startswith("a.draft.json: 已标记人工复核")
    assert skipped[1].startswith("b.draft.json: 在近 4 天赛果里找不到 zverev")


def test_promote的取姓和窗口只有一处定义(promote, hold):
    assert promote.DIGEST_DAYS_BACK is hold.DIGEST_DAYS_BACK
    assert promote._surname_en is hold._surname_en


def test_自动草稿落盘时盖上建草稿的时刻(monkeypatch, tmp_path):
    """没有这个章，过了赛果窗口的自动草稿就认不出来、又回到每一趟跑满全量。"""
    sys.path.insert(0, str(_TOOLS))
    import draft_interview_spec as dis  # noqa: PLC0415
    import interview_draft_hold as h  # noqa: PLC0415

    monkeypatch.setattr(dis, "SPECS", tmp_path / "specs")
    monkeypatch.setattr(dis, "OUTDIR", tmp_path / "out")
    rows = [{"t": 1.0, "end": 1.4, "text": "Hello"}, {"t": 9.7, "end": 10.0, "text": "thanks."}]
    monkeypatch.setattr(dis, "transcribe", lambda url, td: (rows, 20.0))
    monkeypatch.setattr(dis, "translate", lambda lines, chat: ["译文"] * len(lines))
    cal = [{"en": "Cincinnati Open", "zh": "辛辛那提大师赛", "start": "08-16",
            "end": "08-23", "pat": "cincinnati"}]
    cand = {"title": "Cincinnati 2026 R3 Alexander Zverev Interview",
            "url": "https://example.test/x"}
    before = h.beijing_today()
    slug, ok, msg = dis._build_one(cand, None, cal, write=True)
    after = h.beijing_today()
    assert ok, msg
    draft = json.loads((tmp_path / "specs" / f"{slug}.draft.json").read_text(encoding="utf-8"))
    # 前后各取一次「今天」：正好跨过北京零点（16:00Z）时两个都算对（复审 nit：原来偶发红）
    assert h.drafted_day(draft) in {before, after}, draft.get(h.DRAFTED_AT_KEY)


# ── ③ 工作流那一步真跑一遍 ───────────────────────────────────────────────────


def _workflow() -> dict:
    import yaml  # noqa: PLC0415

    return yaml.safe_load(_WF.read_text(encoding="utf-8"))


def _gate_run() -> str:
    steps = _workflow()["jobs"]["auto"]["steps"]
    return next(st["run"] for st in steps if st.get("name") == "没活就早退")


_PICK_STUB = """import sys
if "--probe" in sys.argv:
    print("待 dispatch 0 条：")
elif "--stale" in sys.argv:
    print("投出去超过 70 分钟还没有当前成片的：0 条")
"""


def _run_gate(tmp_path: Path, drafts: dict[str, dict], *, broken_hold: bool = False):
    """把「没活就早退」的 `run:` 原文用 `bash -e`（Actions 的默认 shell）真跑一遍。

    另外两路探针（人工请求、待 dispatch）换成报 0 的替身——这里要验的只是草稿那一路；
    停车判据用的是**真脚本**（拷进临时仓库根，它按自己的位置找 `specs/interviews`）。"""
    root = tmp_path / "repo"
    (root / "tools").mkdir(parents=True)
    (root / "specs" / "interviews").mkdir(parents=True)
    if broken_hold:
        (root / "tools" / "interview_draft_hold.py").write_text(
            "import sys\nsys.exit('boom')\n", encoding="utf-8")
    else:
        shutil.copy(_TOOLS / "interview_draft_hold.py", root / "tools")
    (root / "tools" / "build_interview_request.py").write_text("print(0)\n", encoding="utf-8")
    (root / "tools" / "pick_interview_renders.py").write_text(_PICK_STUB, encoding="utf-8")
    for name, doc in drafts.items():
        (root / "specs" / "interviews" / name).write_text(json.dumps(doc), encoding="utf-8")
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    body = _gate_run().replace("/tmp/", f"{scratch}/")
    assert "${{" not in body, body
    script = tmp_path / "gate.sh"
    script.write_text(body, encoding="utf-8")
    out, summary = tmp_path / "gh_output", tmp_path / "gh_summary"
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env.update({"GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": str(summary),
                "HOME": str(tmp_path / "home")})
    done = subprocess.run(["bash", "-e", str(script)], cwd=root, env=env,
                          capture_output=True, text=True, timeout=120)
    return (done, out.read_text(encoding="utf-8") if out.exists() else "",
            summary.read_text(encoding="utf-8") if summary.exists() else "")


def test_早退探针_只剩停着的草稿就早退_停着的印进日志和摘要(tmp_path):
    parked = {
        "buse-winston-salem-2026-r.draft.json": _draft(manual_review_required="等 lead_in"),
        "bonzi-winston-salem-2026-r.draft.json": _draft(_drafted_at="2026-08-29T21:16:56Z"),
    }
    done, out, summary = _run_gate(tmp_path, parked)
    assert done.returncode == 0, done.stderr
    assert "work=false" in out and "work=true" not in out, (out, done.stdout)
    assert "[早退]" in done.stdout
    head = done.stdout.splitlines()[0]
    assert head.startswith("[草稿停着] 2 份") and "buse-winston-salem-2026-r" in head \
        and "bonzi-winston-salem-2026-r" in head, "停着的要在日志里有一行总括"
    assert "## 🅿️ 停着的草稿" in summary
    assert "- buse-winston-salem-2026-r.draft.json：已标记人工复核（等 lead_in）" in summary
    assert "- bonzi-winston-salem-2026-r.draft.json：建于 2026-08-30" in summary

    # 人把标记去掉：下一趟就叫醒全量
    fixed = {**parked, "buse-winston-salem-2026-r.draft.json": _draft()}
    done, out, summary = _run_gate(tmp_path / "next", fixed)
    assert done.returncode == 0, done.stderr
    assert "work=true" in out, (out, done.stdout)
    assert "能提升的草稿=1，" in done.stdout
    assert "buse" not in summary and "bonzi-winston-salem-2026-r.draft.json" in summary


def test_早退探针_判据跑不起来就按文件数算_不许把活漏掉(tmp_path):
    done, out, _ = _run_gate(tmp_path, {"x.draft.json": _draft(manual_review_required="m")},
                             broken_hold=True)
    assert done.returncode == 0, done.stderr
    assert "work=true" in out, (out, done.stdout, done.stderr)
    assert "::warning::草稿停车判据跑不起来" in done.stdout
    assert "boom" in done.stderr


def test_auto_render每个run块语法都过_改了判据会叫醒():
    """`bash -n` 过每一步的 `run:`（`${{ }}` 换成占位）；停车判据和用它的 promote 在 push paths 里。"""
    wf = _workflow()
    steps = wf["jobs"]["auto"]["steps"]
    runs = [st["run"] for st in steps if "run" in st]
    assert len(runs) >= 10, "扫描面坏了"
    for body in runs:
        text = re.sub(r"\$\{\{[^}]*\}\}", "X", body)
        proc = subprocess.run(["bash", "-n"], input=text, capture_output=True, text=True)
        assert proc.returncode == 0, (proc.stderr, body[:200])
    paths = (wf.get(True) or wf.get("on"))["push"]["paths"]
    assert "tools/interview_draft_hold.py" in paths
    assert "tools/promote_interview_draft.py" in paths
    gate = _gate_run()
    assert "interview_draft_hold.py --count-actionable" in gate
    assert "find specs/interviews" in gate.split("if [ -s")[0], "兜底那一支还在"
