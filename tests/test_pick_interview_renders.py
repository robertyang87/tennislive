"""tools/pick_interview_renders.py —— 挑待 dispatch 的采访 spec。

三层判据，缺一层都出过真事故：

1. 已 render / 已 dispatch 的不再投——否则定时任务每 30 分钟把历史采访重渲一遍；
2. **终审没补齐的不许投**：render 有三道人工编辑闸（opening /
   transcript_verified / takeaway），字段不全的 spec 投出去必死在闸上、又被
   永久记成「已 dispatch」——`swiatek-shnaider-tor2026-qf` 就这么卡死过：
   既不算已 render（没有 render.json），又因为记了状态永远不会再被投；
3. **先投后记 + 查产物**：dispatch 失败的不许记（先记后投＝那条从此消失且
   不吭声）；投出去很久没有 render.json 的要能点出来（「投了」是信号，
   render.json 才是产物）。
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


def _complete_body() -> dict:
    """能过 render 三道编辑闸的最小 spec 形状（和 `missing_for_render` 同口径）。"""
    from interview_source_gate import finalize_source_contract

    spec = {
        "slug": "fixture",
        "url": "https://example.test/oncourt",
        "requested_content_type": "on_court",
        "interview_kind": "赛后场上采访",
        "source_verification": {
            "status": "verified", "detected_type": "on_court",
            "method": "human_visual_verdict",
            "source_url": "https://example.test/oncourt",
            "evidence": [{"kind": "visual_verdict", "by": "test"}],
        },
        "match": {
            "id": "2026:test:qf:winner", "event": "测试赛", "round": "四分之一决赛",
            "winner": "赢家", "loser": "输家", "participants": ["赢家", "输家"],
        },
        "opening": {"kind": "match_end", "lead_in": 10.0,
                    "why": "正文源开头含同场赛点和现场解说"},
        "zh": ["第一行"],
        "transcript_verified": True,
        "takeaway": {"close": {"point": "x"}},
        "cover": {"frame_at": 1.0},
    }
    return finalize_source_contract(spec)


def _write_spec(specs: Path, slug: str, body: dict, *, xhs: bool = True) -> None:
    body = json.loads(json.dumps(body))
    body["slug"] = slug
    if body.get("match"):
        body["match"]["id"] = f"2026:test:qf:{slug}"
        from interview_source_gate import finalize_source_contract
        body = finalize_source_contract(body)
    (specs / f"{slug}.json").write_text(
        json.dumps(body, ensure_ascii=False), encoding="utf-8")
    if xhs:
        (specs / f"{slug}.xhs.txt").write_text("文案", encoding="utf-8")


@pytest.fixture()
def tool(monkeypatch, tmp_path):
    sys.path.insert(0, str(_TOOLS))
    import pick_interview_renders as p  # noqa: PLC0415

    specs = tmp_path / "specs" / "interviews"
    specs.mkdir(parents=True)
    # 一个已 render、一个补齐待投、一个草稿、一个只有骨架（等终审）
    _write_spec(specs, "a-done", _complete_body())
    _write_spec(specs, "b-todo", _complete_body())
    (specs / "c-draft.draft.json").write_text("{}")
    _write_spec(specs, "d-bare", {}, xhs=False)
    monkeypatch.setattr(p, "SPECS", specs)
    monkeypatch.setattr(p, "STATE",
                        tmp_path / "data" / "interview_render_dispatched.json")
    monkeypatch.setattr(p, "OUTPUT", tmp_path / "output" / "interviews")
    monkeypatch.setattr(
        p, "LEGACY_INPUT_BASELINE",
        tmp_path / "data" / "interview_render_legacy_baseline.json")
    monkeypatch.setattr(p, "_rendered_slugs", lambda: {"a-done"})
    # 夹具里的 spec 只有「过得了三道编辑闸」的骨架，没有字幕、文案、顶栏——真跑
    # dispatch 前的离线预检必红。预检的接线由 `test_预检红的spec不dispatch_进等待名单`
    # 单独钉，其余测试钉的是状态与指纹逻辑，这里让预检放行。
    import interview_preflight  # noqa: PLC0415
    monkeypatch.setattr(interview_preflight, "spec_problems",
                        lambda spec, **kw: ([], []))
    return p


def test_todo排除已render和草稿(tool):
    """a-done 已 render、c-draft 是草稿，只有 b-todo 该 dispatch。"""
    ready, _ = tool.todo_slugs()
    assert ready == ["b-todo"]


def test_旧产物没有QC继续按已render兼容(tool):
    """上线输入指纹不能把 58 条 QC 诞生前的历史采访一起重渲。"""
    assert not (tool.OUTPUT / "a-done" / "qc_attestation.json").exists()
    ready, _ = tool.todo_slugs()
    assert "a-done" not in ready


def _write_qc(tool, slug: str, spec_sha256: str) -> None:
    path = tool.OUTPUT / slug / "qc_attestation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"status": "pass", "slug": slug,
                                "spec_sha256": spec_sha256}), encoding="utf-8")


def test_同slug的spec指纹变化后自动重新成为候选(tool):
    spec = tool.SPECS / "a-done.json"
    old_sha = tool._sha256(spec)
    _write_qc(tool, "a-done", old_sha)
    assert "a-done" not in tool.todo_slugs()[0], "QC 绑定当前 spec 时不该重渲"

    body = json.loads(spec.read_text(encoding="utf-8"))
    body["cover"]["frame_at"] = 180.0
    spec.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    ready, _ = tool.todo_slugs()
    assert "a-done" in ready, (
        "render.json 还在但 QC 绑定的是旧 spec；绿产物不能把新输入永久挡住")


def test_QC不是pass或指纹损坏都不能冒充当前成片(tool):
    spec = tool.SPECS / "a-done.json"
    path = tool.OUTPUT / "a-done" / "qc_attestation.json"
    _write_qc(tool, "a-done", tool._sha256(spec))
    qc = json.loads(path.read_text(encoding="utf-8"))
    qc["status"] = "fail"
    path.write_text(json.dumps(qc), encoding="utf-8")
    assert "a-done" in tool.todo_slugs()[0]

    path.write_text("[]", encoding="utf-8")
    assert "a-done" in tool.todo_slugs()[0]


def test_已发布旧片可按明确spec指纹迁移但下一次修改立即失效(tool):
    spec = tool.SPECS / "a-done.json"
    _write_qc(tool, "a-done", "0" * 64)
    tool.LEGACY_INPUT_BASELINE.parent.mkdir(parents=True, exist_ok=True)
    tool.LEGACY_INPUT_BASELINE.write_text(json.dumps({
        "schema_version": 1,
        "slugs": {"a-done": {"spec_sha256": tool._sha256(spec)}},
    }), encoding="utf-8")
    assert "a-done" not in tool.todo_slugs()[0], (
        "规则上线不能把已发布但旧 QC 天生错位的内容重新推一遍")

    body = json.loads(spec.read_text(encoding="utf-8"))
    body["cover"]["frame_at"] = 222.0
    spec.write_text(json.dumps(body), encoding="utf-8")
    assert "a-done" in tool.todo_slugs()[0], (
        "迁移基线只认那一份 SHA，未来 spec 修改必须自动重渲")

def test_新spec已经dispatch则定时班次不重复投(tool):
    spec = tool.SPECS / "a-done.json"
    _write_qc(tool, "a-done", "0" * 64)  # 明确是旧输入的成片
    tool.mark_one("a-done", now="2026-08-30T12:00:00Z")
    state = json.loads(tool.STATE.read_text(encoding="utf-8"))
    assert state["spec_sha256"]["a-done"] == tool._sha256(spec)

    now = datetime(2026, 8, 30, 12, 20, tzinfo=timezone.utc)
    ready, _ = tool.todo_slugs(now=now)
    assert "a-done" not in ready, (
        "当前 spec 已投出 20 分钟、旧 QC 尚未被替换时，不许每 10 分钟重复 dispatch")


def test_旧dispatch指纹不能拦住后来修改的spec(tool):
    spec = tool.SPECS / "a-done.json"
    _write_qc(tool, "a-done", "0" * 64)
    tool.mark_one("a-done", now="2026-08-30T12:00:00Z")
    body = json.loads(spec.read_text(encoding="utf-8"))
    body["cover"]["frame_at"] = 181.0
    spec.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    ready, _ = tool.todo_slugs(
        now=datetime(2026, 8, 30, 12, 5, tzinfo=timezone.utc))
    assert "a-done" in ready, "状态认领的是旧 SHA，新 spec 必须立即释放"


def test_mark记录dispatch防重(tool):
    """记录过 dispatch 的 slug 不能再 dispatch（否则每 30 分钟重渲历史）。"""
    tool.mark_one("b-todo")
    ready, _ = tool.todo_slugs()
    assert ready == [], "记录过 dispatch 的不能再 dispatch"
    state = json.loads(tool.STATE.read_text(encoding="utf-8"))
    assert state["slugs"] == ["b-todo"]
    assert state["at"]["b-todo"], "投出时刻要记下来——stale 反查靠它"
    assert state["spec_sha256"]["b-todo"] == tool._sha256(
        tool.SPECS / "b-todo.json"), "dispatch 状态必须绑定实际输入"


def test_终审没补齐的不许投而且要说缺什么(tool):
    """**这条就是 swiatek-shnaider 卡死事故的判据。** 骨架 spec 不进
    dispatch 名单，进「等终审」并逐项点出缺什么——「不投」和「忘了投」
    必须分得开。"""
    ready, waiting = tool.todo_slugs()
    assert "d-bare" not in ready
    by_slug = dict(waiting)
    assert "d-bare" in by_slug
    missing = "、".join(by_slug["d-bare"])
    for want in ("opening", "zh", "transcript_verified", "takeaway", "cover",
                 "xhs"):
        assert want in missing, f"缺 {want} 没被点出来：{missing}"


def test_判定和闸共用同一张豁免表(tool):
    """老 spec 靠 `_LEGACY_NO_OPENING` / `_NO_TAKEAWAY_LEGACY` 过闸——判定
    比闸更严的话，会把这些本来渲得动的 spec 拦在门外永远不投。
    拿表里**真实的** slug 验（表自带自检：写错名字当场 KeyError 式失败）。
    """
    import build_interview_clip as clip  # noqa: PLC0415

    legacy_open = sorted(clip._LEGACY_NO_OPENING)[0]
    legacy_tk = sorted(clip._NO_TAKEAWAY_LEGACY)[0]
    assert legacy_open, "豁免表空了，判据失效"

    body = _complete_body()
    del body["opening"]
    _write_spec(tool.SPECS, legacy_open, body)
    body2 = _complete_body()
    del body2["takeaway"]
    _write_spec(tool.SPECS, legacy_tk, body2)
    ready, waiting = tool.todo_slugs()
    assert legacy_open in ready, "在 _LEGACY_NO_OPENING 里的不该因缺 opening 被拦"
    assert legacy_tk in ready, "在 _NO_TAKEAWAY_LEGACY 里的不该因缺 takeaway 被拦"
    # 反向：同样缺 opening 但不在表里的（d-bare）仍然在等终审
    assert "d-bare" in dict(waiting)


def test_stale判产物不判信号(tool, monkeypatch):
    """投出去超过 STALE_MINUTES 还没有当前成片的要点出来；有当前成片的、
    刚投的都不算。老状态（bulk mark 时代）没记时刻的一律算 stale。"""
    now = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    old = (now - timedelta(minutes=tool.STALE_MINUTES + 1)).strftime("%FT%TZ")
    fresh = (now - timedelta(minutes=tool.STALE_MINUTES - 1)).strftime("%FT%TZ")
    tool.mark_one("old-no-render", now=old)
    tool.mark_one("fresh-no-render", now=fresh)
    tool.mark_one("old-rendered", now=old)
    # 手写一个没有 at 的老条目
    state = json.loads(tool.STATE.read_text(encoding="utf-8"))
    state["slugs"] = sorted({*state["slugs"], "ancient"})
    tool.STATE.write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(tool, "_rendered_slugs", lambda: {"old-rendered"})

    stale = dict(tool.stale_dispatches(now=now))
    assert "old-no-render" in stale, "投了 4 小时没产物的没被点出来"
    assert "ancient" in stale, "老状态没记时刻的要一律算 stale"
    assert "fresh-no-render" not in stale, "刚投 20 分钟的不该报"
    assert "old-rendered" not in stale, "render.json 落库了就不是 stale——判产物"


def test_stale自动释放回dispatch队列而新任务不重复(tool, monkeypatch):
    now = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    old = (now - timedelta(minutes=tool.STALE_MINUTES + 1)).strftime("%FT%TZ")
    fresh = (now - timedelta(minutes=tool.STALE_MINUTES - 1)).strftime("%FT%TZ")
    tool.mark_one("b-todo", now=old)
    ready, _ = tool.todo_slugs(now=now)
    assert "b-todo" in ready, "超过 STALE_MINUTES 无当前成片要自动重投，不能只报警等人"

    tool.mark_one("b-todo", now=fresh)
    ready, _ = tool.todo_slugs(now=now)
    assert "b-todo" not in ready, "刚投出的还在跑，不许并发重复 dispatch"


def test_无产物满窗口释放但差一分钟仍保护长片(tool):
    now = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
    before = now - timedelta(minutes=tool.STALE_MINUTES - 1)
    tool.mark_one("b-todo", now=before.strftime("%FT%TZ"))
    assert "b-todo" not in tool.todo_slugs(now=now)[0]

    after = now - timedelta(minutes=tool.STALE_MINUTES + 1)
    tool.mark_one("b-todo", now=after.strftime("%FT%TZ"))
    assert "b-todo" in tool.todo_slugs(now=now)[0], (
        "固定 3 小时恢复太慢；无产物满窗口必须自动释放")


def test_重投窗口必须长于渲染job的超时否则会掐掉在跑的长片(tool):
    """interview-clip.yml 是 cancel-in-progress：窗口比 job 的 timeout-minutes
    短，一趟还在跑的长片会在满窗那一刻被重投的那趟掐掉——和当年 45 对 49
    那次是同一个形状。上限也钉住：固定 3 小时会让一次红灯拖掉半天。"""
    body = Path(".github/workflows/interview-clip.yml").read_text(encoding="utf-8")
    job_timeout = int(re.search(r"^    timeout-minutes: (\d+)", body, re.M).group(1))
    assert "cancel-in-progress: true" in body
    assert tool.STALE_MINUTES > job_timeout, (
        f"STALE_MINUTES={tool.STALE_MINUTES} 不长于 job 超时 {job_timeout}")
    assert tool.STALE_MINUTES <= 120


def test_stdout第二行起是名单等终审走stderr(tool, monkeypatch, capsys):
    """workflow 拿 `tail -n +2` 切 stdout 当 dispatch 名单——等终审的一旦混进
    stdout，就会把一条不齐的 spec 投出去，正是这次修的卡死。"""
    monkeypatch.setattr(sys, "argv", ["pick_interview_renders.py"])
    assert tool.main() == 0
    out, err = capsys.readouterr()
    lines = out.splitlines()
    assert lines[0].startswith("待 dispatch")
    assert lines[1:] == ["b-todo"], f"stdout 第二行起必须只有名单：{lines!r}"
    assert "等自动补齐 / 例外复核" in err and "d-bare" in err


def test_workflow监听正式spec并写明恢复窗口(tool):
    body = Path(".github/workflows/interview-auto-render.yml").read_text(
        encoding="utf-8")
    assert '"specs/interviews/*.json"' in body, (
        "同 slug 改 spec 后必须立即唤醒自动重渲，不能只等 schedule")
    assert '"tools/build_interview_clip.py"' in body, (
        "渲染器修顶栏、封面或发布闸后必须立即唤醒自动重渲")
    assert f"超过 {tool.STALE_MINUTES} 分钟还没有当前成片" in body
    assert "超过 3 小时" not in body


def test_已推送的旧请求覆盖不能触发自动重渲(tool):
    path = tool.SPECS / "a-done.json"
    _write_qc(tool, "a-done", "old-spec-sha")
    marker = tool.OUTPUT / "a-done" / "pushed.json"
    marker.write_text(json.dumps({"status": "accepted", "film_sha256": "published-film"}))
    ready, _ = tool.todo_slugs()
    assert "a-done" not in ready
    spec = json.loads(path.read_text())
    spec["_publication_revision"] = {"id": "new-user-revision", "base_film_sha256": "published-film"}
    path.write_text(json.dumps(spec))
    ready, _ = tool.todo_slugs()
    assert "a-done" in ready
    spec["_publication_revision"]["base_film_sha256"] = "older-film"
    path.write_text(json.dumps(spec))
    ready, _ = tool.todo_slugs()
    assert "a-done" not in ready


_STDLIB_ONLY = r"""
import importlib.abc, runpy, sys
from pathlib import Path
tools = Path(sys.argv[1])
ok = set(sys.stdlib_module_names) | {"tennislive"} | {p.stem for p in tools.glob("*.py")}

class OnlyStdlib(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        top = name.split(".")[0]
        # `_sysconfigdata_*` 是标准库按平台生成的私有模块，不在 stdlib_module_names 里
        if top not in ok and not top.startswith("_sysconfigdata"):
            raise ModuleNotFoundError(f"No module named {name!r}（探针的系统 python3 上没有）")
        return None

sys.meta_path.insert(0, OnlyStdlib())
sys.argv = [str(tools / "pick_interview_renders.py"), "--probe"]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


def test_探针的import链只用标准库(tmp_path):
    """interview-auto-render 的「没活就早退」跑在 runner 的**系统 python3** 上（没有 PIL，
    也没有别的第三方包）——`pick_interview_renders --probe` 连 import 带跑一遍，只许用
    标准库和仓库自己的代码；量宽度要 PIL 的那几项在函数里 import、判不了记成 unknown。

    来路：合并 main 时 `build_interview_clip` 顶层多了一行
    `from tennislive.video.subtitle_text import drop_punctuation`——那个模块只用标准库，
    可 `tennislive/video/__init__.py` 会把 pipeline → research → digest → sources → requests
    整串拉进来；探针一 import 就崩，workflow 退回「Work probe needs rendering dependencies」、
    每 10 分钟一趟全量 job，探针那一轮修正白做。"""
    import os
    import subprocess

    root = _TOOLS.parent
    env = {**os.environ, "PYTHONPATH": f"{root / 'src'}{os.pathsep}{_TOOLS}",
           "INTERVIEW_PREFLIGHT_CACHE": str(tmp_path / "verdicts.json")}
    proc = subprocess.run([sys.executable, "-c", _STDLIB_ONLY, str(_TOOLS)], cwd=root,
                          env=env, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert proc.stdout.startswith("待 dispatch"), proc.stdout[:500]


def _closed_record(tool, slug: str) -> None:
    """render 红在封面自动换帧那一趟就地写下的扫描记录（红着的 render 不提交它，可停车账
    要从它读原因）：近处全是闭眼。"""
    import interview_cover_scan as scan  # noqa: PLC0415

    spec = json.loads((tool.SPECS / f"{slug}.json").read_text(encoding="utf-8"))
    block = {"status": "ok", "identity": {"similarity": {"赢家": 0.6}, "missing": [],
                                          "face_px": 300.0, "verdict": "match", "name": "赢家"},
             "eyes": {"verdict": "closed", "ear": 0.09, "face_px": 300.0}}
    entries = [{"frame_at": t, "status": "fail", "issues": ["这张脸闭眼"], "face": None,
                "margin": 2.0, "face_model": block} for t in (1.0, 1.2)]
    out = tool.OUTPUT / slug
    out.mkdir(parents=True, exist_ok=True)
    (out / scan.RECORD_NAME).write_text(
        json.dumps(scan.build_record(spec, (0.0, 3.0), 0.2, entries)), encoding="utf-8")


def test_封面自动换帧连着三趟挑不出来就停车_换了封面从头数(tool, monkeypatch, capsys):
    """D2（2026-09-28）：render 的自动换帧一格都挑不出来（主角没头像、整段闭眼／是别人），
    同一个封面再投一趟量出来的是同一批格子——原来 70 分钟一趟、永远红。interview-clip 每红
    一趟记一笔（`note_autopick_failure`），同一个封面指纹满 `PARK_AFTER` 趟就停车：不进名单、
    进 `--parked`（run 摘要 🅿️ 那一栏）、不算 stale。改的不是封面（中文字幕）照旧停着；改了
    封面从头数。"""
    now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
    long_ago = (now - timedelta(minutes=tool.STALE_MINUTES + 1)).strftime("%FT%TZ")
    tool.mark_one("b-todo", now=long_ago)
    _closed_record(tool, "b-todo")
    assert tool.PARK_AFTER == 3
    for n in range(1, tool.PARK_AFTER):
        assert tool.note_autopick_failure("b-todo", now=long_ago)["count"] == n
        assert "b-todo" in tool.todo_slugs(now=now)[0], f"才 {n} 趟就停了车"
    row = tool.note_autopick_failure("b-todo", now=long_ago)
    assert row["count"] == tool.PARK_AFTER and "闭眼" in row["why"], row
    ready, _waiting = tool.todo_slugs(now=now)
    assert "b-todo" not in ready, "满 3 趟还在投"
    why = tool.parked_slugs()["b-todo"]
    assert "停车" in why and "no frame passes identity/eyes" in why and "闭眼" in why, why
    assert "b-todo" not in dict(tool.stale_dispatches(now=now)), "停车是故意不投，不是「投了没产物」"
    monkeypatch.setattr(sys, "argv", ["pick_interview_renders.py", "--parked"])
    assert tool.main() == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("封面自动换帧停车") and "  b-todo：" in out, out

    spec_path = tool.SPECS / "b-todo.json"
    body = json.loads(spec_path.read_text(encoding="utf-8"))
    body["zh"] = ["改过的第一行"]           # 不是封面：同一批格子，照旧停着
    spec_path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    assert "b-todo" not in tool.todo_slugs(now=now)[0], "改的不是封面却放行了——再投一趟还是红"
    body["cover"]["frame_at"] = 2.5          # 人换了封面：新的一局
    spec_path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    assert "b-todo" in tool.todo_slugs(now=now)[0], "换了封面还停着"
    assert tool.note_autopick_failure("b-todo", now=long_ago)["count"] == 1, "换了封面没从头数"
    # 当前 spec 已经出过片（没 QC 的老产物按已出片算）：不算停车
    for _ in range(2):
        tool.note_autopick_failure("b-todo", now=long_ago)
    assert "b-todo" in tool.parked_slugs()
    monkeypatch.setattr(tool, "_rendered_slugs", lambda: {"a-done", "b-todo"})
    assert "b-todo" not in tool.parked_slugs()


def test_停车账和指纹只用标准库(tmp_path):
    """interview-auto-render 的探针（系统 python3）和 `--parked` 都要算封面指纹——
    `interview_cover_scan.cover_fingerprint` 那一串 import 只许标准库，而且两头（interview-clip
    记账、auto-render 判停车）算出同一个数：不看头像文件在不在（auto-render 的检出没有
    assets/players）。"""
    import os
    import subprocess

    root = _TOOLS.parent
    code = _STDLIB_ONLY.split("sys.meta_path.insert(0, OnlyStdlib())")[0] + (
        "sys.meta_path.insert(0, OnlyStdlib())\n"
        "sys.path.insert(0, str(tools))\n"
        "import json, interview_cover_scan as scan\n"
        "spec = json.loads((tools.parent / 'specs/interviews/tien-cobolli-laver-cup-2026-interview.json')"
        ".read_text(encoding='utf-8'))\n"
        "print(scan.cover_fingerprint(spec))\n")
    env = {**os.environ, "PYTHONPATH": f"{root / 'src'}{os.pathsep}{_TOOLS}"}
    proc = subprocess.run([sys.executable, "-c", code, str(_TOOLS)], cwd=root, env=env,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    sys.path.insert(0, str(_TOOLS))
    import interview_cover_scan as scan  # noqa: PLC0415

    spec = json.loads((root / "specs/interviews/tien-cobolli-laver-cup-2026-interview.json")
                      .read_text(encoding="utf-8"))
    assert proc.stdout.strip() == scan.cover_fingerprint(spec)
    moved = json.loads(json.dumps(spec))
    moved["cover"]["frame_at"] = float(moved["cover"]["frame_at"]) + 1.0
    assert scan.cover_fingerprint(moved) != scan.cover_fingerprint(spec)


def test_封面指纹跟着主角和同场的人的头像走_别人补头像不算(monkeypatch):
    """停车账的出路之一是「补主角的官方头像」——补上之后指纹要变，picker 才会重投；同场的人
    （对手／搭档，`co_present`）补了头像同理：认人换了一批人一起比，挑出来的可能不一样。
    反过来，仓库里**别人**补了头像不许动这条的指纹（不然任何一条赛场之上 spec 多一张头像，
    全库停车一起解开）。头像索引打桩：只看名字和路径，不看文件在不在。"""
    sys.path.insert(0, str(_TOOLS))
    import interview_cover_scan as scan  # noqa: PLC0415

    spec = {"slug": "fp", "subject": "甲", "cover": {"frame_at": 3.0, "tag": "测试赛 · 甲"},
            "match": {"winner": "甲", "loser": "乙", "participants": ["甲", "乙"]},
            "start": 0.0, "end": 60.0}

    def fp(index: dict) -> str:
        monkeypatch.setattr(scan, "_headshot_index", lambda: dict(index))
        return scan.cover_fingerprint(spec)

    base = {"丙": "assets/players/c.png"}
    none = fp(base)
    with_subject = fp({**base, "甲": "assets/players/a.png"})
    assert with_subject != none, "补了主角的官方头像，指纹没变——停车的那条永远不会重投"
    with_rival = fp({**base, "乙": "assets/players/b.png"})
    assert with_rival != none, "补了同场对手的官方头像，指纹没变"
    both = fp({**base, "甲": "assets/players/a.png", "乙": "assets/players/b.png"})
    assert both not in (with_subject, with_rival)
    assert fp({**base, "甲": "assets/players/a-2026.png"}) != with_subject, "主角换了一版头像，指纹没变"
    assert fp({**base, "丁": "assets/players/d.png"}) == none, (
        "别人补了头像也动了这条的指纹——全库停车会被一张不相干的头像一起解开")


def _park(tool, kind: str, *, dispatched: Path | None = None) -> dict:
    return tool.note_autopick_failure("b-todo", kind=kind, dispatched=dispatched)


def test_换上的终审还红和对账红也记同一个停车计数_指纹按派发时那份spec算(tool, monkeypatch, capsys):
    """render 红在封面那一步、再投一趟照样红的另外两条路（2026-09-28 复审）也记进同一个计数：

    - `audit`：自动换上的那一帧终审还红——那时工作区的 spec 已经被就地改写（frame_at 换了），
      指纹要按**派发时**那份算（interview-clip 从 HEAD 取、`--dispatched-spec` 递过来），
      否则 picker 拿 main 上那份比永远对不上、永远不停车
    - `check`：终审过了、推送前对账红（D3 的边）

    三种红混着数，满 `PARK_AFTER` 趟停车；停车那一句按最近一趟是哪种红说出路。"""
    spec_path = tool.SPECS / "b-todo.json"
    original = spec_path.read_text(encoding="utf-8")
    dispatched = spec_path.parent.parent / "as_dispatched.json"
    dispatched.write_text(original, encoding="utf-8")
    _closed_record(tool, "b-todo")

    # 第 1 趟：挑不出来；第 2 趟：换上了 7.5 秒那一格、终审还红（工作区 spec 已改写）
    assert _park(tool, "autopick")["count"] == 1
    rewritten = json.loads(original)
    rewritten["cover"]["frame_at"] = 7.5
    spec_path.write_text(json.dumps(rewritten, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["pick_interview_renders.py", "--autopick-failed", "b-todo",
                                      "--kind", "audit", "--dispatched-spec", str(dispatched)])
    assert tool.main() == 0
    assert "第 2 趟" in capsys.readouterr().out
    # 第 3 趟：对账红
    row = _park(tool, "check", dispatched=dispatched)
    assert row["count"] == tool.PARK_AFTER and row["kind"] == "check", row
    assert "对账" in row["why"], row
    # picker 在 main 上：spec 还是派发时那份
    spec_path.write_text(original, encoding="utf-8")
    parked = tool.parked_slugs()
    assert "b-todo" in parked, "指纹拿改写过的 spec 算了——picker 比的是 main 上那份，永远不停车"
    fix = parked["b-todo"].rsplit("——停车，不再投；", 1)[-1]
    assert "对账" in parked["b-todo"] and "mode=cover" in fix, ("停车那一句没按对账红说出路", parked)
    assert "b-todo" not in tool.todo_slugs()[0]

    # 换帧之后终审还红那一句：说的是分叉，不是「一格都挑不出来」
    tool.note_autopick_failure("b-todo", kind="audit", dispatched=dispatched)
    why = tool.parked_slugs()["b-todo"]
    assert "终审还红" in why and "no frame passes" not in why, why
    assert "工具" in why.rsplit("——停车，不再投；", 1)[-1], why
    with pytest.raises(ValueError):
        tool.note_autopick_failure("b-todo", kind="model")   # 模型不可用（退出 4）故意不记


def test_对账红停车之后_重扫换了记录就从头数(tool, monkeypatch):
    """`check` 那种红的出路是 mode=cover 重扫——**只换已提交的扫描记录、不动 spec**。停车账的键
    只有封面指纹的话，重扫完照旧停着、永远不会重投。键里带着 HEAD 里那份记录的 blob 号
    （`_committed_record_blob`，只认 HEAD：runner 上 outdir 里那份是这一趟刚写、没提交的）。"""
    blob = {"b-todo": "1111"}
    monkeypatch.setattr(tool, "_committed_record_blob", lambda slug: blob.get(slug, ""))
    _closed_record(tool, "b-todo")
    for _ in range(tool.PARK_AFTER):
        tool.note_autopick_failure("b-todo", kind="check")
    assert "b-todo" in tool.parked_slugs()
    blob["b-todo"] = "2222"                   # mode=cover 重扫，main 上的记录换了
    assert "b-todo" not in tool.parked_slugs(), "重扫换了记录还停着"
    assert "b-todo" in tool.todo_slugs()[0]
    assert tool.note_autopick_failure("b-todo", kind="check")["count"] == 1, "换了记录没从头数"


def test_停车的只列在停车那一栏_等待名单里不再列一遍(tool, monkeypatch, capsys):
    """auto-render 的 run 摘要里 🅿️ 那一栏是 `--parked` 印的，⏳ 那一栏是 picker 的 stderr
    （等待名单）——原来停车的 slug 两栏各列一遍。停车的不进等待名单，picker 的题头数一句
    「另有 N 条停车」（stdout 第一行，workflow 切名单时跳过它），原因只在 `--parked` 里说。"""
    _closed_record(tool, "b-todo")
    for _ in range(tool.PARK_AFTER):
        tool.note_autopick_failure("b-todo")
    ready, waiting = tool.todo_slugs()
    assert "b-todo" not in ready and "b-todo" in tool.parked_slugs()
    assert "b-todo" not in dict(waiting), f"停车的又进了 ⏳ 等待名单：{waiting}"
    monkeypatch.setattr(tool, "save_verdicts", lambda: None)
    monkeypatch.setattr(sys, "argv", ["pick_interview_renders.py"])
    assert tool.main() == 0
    got = capsys.readouterr()
    head, *slugs = got.out.splitlines()
    assert "b-todo" not in slugs and "b-todo" not in got.err, got
    assert "另有 1 条封面自动换帧停车" in head and "--parked" in head, head


def test_auto_render的run摘要单列停车那一栏():
    """停车的要人动封面，不是等一等就好——run 摘要单列一栏（`--parked`），和「投了很久没产物」
    （本轮自动重投）分开。"""
    import yaml  # noqa: PLC0415

    wf = yaml.safe_load(Path(".github/workflows/interview-auto-render.yml").read_text(encoding="utf-8"))
    gate = next(s for s in wf["jobs"]["auto"]["steps"] if s.get("id") == "gate")
    body = str(gate["run"])
    assert "pick_interview_renders.py --parked" in body and "封面自动换帧停车" in body, body
