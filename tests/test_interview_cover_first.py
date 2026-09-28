"""赛后开麦：封面排在编码之前、挑帧一趟扫一段、第二份 ASR 在 subs 就跑。

来路（2026-09-27 返工审计，按 run 日志逐趟分类的账）：

- **14 趟 interview-clip（74.8 runner-分钟）红在「验封面视觉」**，而那一步排在
  「剪 + 烧字幕」后面——每次封面不合格都先付了一整趟编码
  （中位 148 秒，`bu-jodar` 那趟 487.9 秒）
- 封面是对着 160×90 的缩略图墙盲挑的，monfils 换了 10 版（fcc6c385「前九趟都在
  赌」），alcaraz-fritz 最后是手工逐帧过同一道闸定下的（a4db65b4）
- **10 趟 render（41.7 runner-分钟）红在转写分歧／空档**，而第二份 ASR 只在
  render 跑——每趟装完依赖、下完源片才知道英文漏了一句

判据分三组：工作流的**顺序**（真跑那几步的 bash，按调用顺序断言，不查措辞）、
`--stage verify` 在没中文时也要跑、扫描记录的对账。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import interview_cover_scan as scan  # noqa: E402

WORKFLOW = ROOT / ".github" / "workflows" / "interview-clip.yml"
COVER_STEP = "出封面并验视觉（完全本地，排在转写和编码之前）"
FINAL_COVER_STEP = "终审封面视觉（出片后的最终海报，完全本地）"
SUBS_VERIFY_STEP = "第二份 ASR 交叉校验并提交报告（subs）"


# ---------------------------------------------------------------- 工作流

def _steps() -> list[dict]:
    import yaml  # noqa: PLC0415

    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return wf["jobs"]["render"]["steps"]


def _names() -> list[str]:
    return [str(s.get("name") or "") for s in _steps()]


def _step(name: str) -> dict:
    hits = [s for s in _steps() if s.get("name") == name]
    assert len(hits) == 1, f"「{name}」这一步有 {len(hits)} 条——判据的主语没了或重复了"
    return hits[0]


def _holds(expr, mode: str) -> bool:
    """只认这几步用到的写法：`mode == 'x'` 用 `||` 连起来。"""
    if not expr:
        return True
    py = (str(expr).replace("github.event.inputs.mode", repr(mode))
          .replace("||", " or ").replace("&&", " and "))
    return bool(eval(py, {"__builtins__": {}}, {}))  # noqa: S307


_PY_SHIM = """#!/usr/bin/env bash
echo "python $*" >> "$SHIM_LOG"
case "$*" in
  *audit_interview_cover.py*)
    # AUDIT_SEQ：一次一个退出码按顺序吐（「第一次红、换帧之后绿」）；没给就用 AUDIT_RC
    if [ -n "$AUDIT_SEQ" ]; then
      set -- $AUDIT_SEQ
      k=$(grep -c audit_interview_cover.py "$SHIM_LOG")
      eval "rc=\\${$k:-0}"
      exit "$rc"
    fi
    exit "${AUDIT_RC:-0}" ;;
  *"interview_cover_scan.py --check"*) exit "${CHECK_RC:-0}" ;;
  *"--stage cover-scan"*) exit "${SCAN_RC:-0}" ;;
  *"--stage cover"*) exit "${COVER_RC:-0}" ;;
  *"--stage verify"*) exit "${VERIFY_RC:-0}" ;;
esac
exit 0
"""
_LOG_SHIM = """#!/usr/bin/env bash
echo "{name} $*" >> "$SHIM_LOG"
{extra}
exit 0
"""


def _run_step(tmp_path: Path, name: str, *, mode: str, env: dict | None = None,
              cwd: Path | None = None,
              ref: str = "main") -> tuple[subprocess.CompletedProcess, list[str]]:
    """把一步的 `run:` 原文用 `bash -e`（Actions 的默认 shell）真跑一遍。

    `python` / `pip` / `git` 换成只记账的替身：要验的是**调用顺序和退出码**，
    不是工具本身。`${{ }}` 一律替换掉，替不掉就报错——跑的必须是真脚本。
    `ref` 是 `github.ref_name`（默认 main；停车账只在 main 上记）。
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "python").write_text(_PY_SHIM, encoding="utf-8")
    (bin_dir / "pip").write_text(_LOG_SHIM.format(name="pip", extra=""), encoding="utf-8")
    # `git diff --cached --quiet` 回 1＝有改动，才走得到提交那一支
    (bin_dir / "git").write_text(_LOG_SHIM.format(
        name="git",
        extra='if [ "$1 $2 $3" = "diff --cached --quiet" ]; then exit 1; fi'),
        encoding="utf-8")
    for f in bin_dir.iterdir():
        f.chmod(0o755)
    body = (str(_step(name)["run"])
            .replace("${{ github.event.inputs.slug }}", "demo")
            .replace("${{ github.ref_name }}", ref))
    assert "${{" not in body, f"「{name}」里还有没替换的表达式：{body}"
    script = tmp_path / "step.sh"
    script.write_text(body, encoding="utf-8")
    log = tmp_path / "calls.log"
    log.write_text("", encoding="utf-8")
    full_env = dict(os.environ)
    full_env.update({"PATH": f"{bin_dir}{os.pathsep}{full_env['PATH']}",
                     "SHIM_LOG": str(log), "MODE": mode,
                     "RUNNER_TEMP": str(tmp_path)})
    full_env.update(env or {})
    done = subprocess.run(["bash", "-e", str(script)], cwd=cwd or tmp_path,
                          env=full_env, capture_output=True, text=True, timeout=60)
    return done, [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln]


def _kinds(calls: list[str]) -> list[str]:
    """把替身记下的调用压成好读的几类。"""
    out = []
    for c in calls:
        if "--stage cover-scan" in c:
            out.append("scan" + (" keep" if "--keep-source" in c else "")
                       + (" autopick" if "--autopick" in c else ""))
        elif "--stage cover" in c:
            out.append("cover" + (" keep" if "--keep-source" in c else ""))
        elif "audit_interview_cover.py" in c:
            out.append("audit")
        elif "interview_cover_scan.py --check" in c:
            out.append("check")
        elif "interview_cover_scan.py --report" in c:
            out.append("report")
        elif "--stage verify" in c:
            out.append("verify")
    return out


def test_封面前置排在转写校验和编码之前():
    """**顺序就是这条的全部**：原来「验封面视觉」排在「剪 + 烧字幕」后面，
    14 趟 run 每一趟都先付了整趟编码才红。按步骤序号判，不按措辞。"""
    names = _names()
    cover = names.index(COVER_STEP)
    for later in ("转写交叉校验", "剪 + 烧字幕", FINAL_COVER_STEP, "验成片（L2 成片落地闸）"):
        assert cover < names.index(later), (
            f"「{COVER_STEP}」排在第 {cover + 1} 步，却在「{later}」"
            f"（第 {names.index(later) + 1} 步）之后——封面又回到了编码后面")
    step = _step(COVER_STEP)
    assert _holds(step.get("if"), "render") and _holds(step.get("if"), "cover"), (
        "封面前置那一步 render 和 cover 两档都要跑——同一份实现、同一把闸")
    assert not _holds(step.get("if"), "subs") and not _holds(step.get("if"), "push")
    assert not step.get("continue-on-error"), "封面闸不许 fail-open"
    # 出片之后那一次只是对最终海报重写凭证，只在 render
    final = _step(FINAL_COVER_STEP)
    assert _holds(final.get("if"), "render") and not _holds(final.get("if"), "cover")
    assert "audit_interview_cover.py" in str(final.get("run"))


def test_出片档封面前置要留源片_红了就地扫候选自动换帧(tmp_path):
    """真跑那一步：render 档必须 `--keep-source`（后面的编码复用，不下第二遍）。

    闸红了**就地扫并自动换帧**（`--autopick`，rework_audit_0928：9 趟 run 红在封面帧，
    cobolli-mensik 就地扫出的第一名正是人后来写进 spec 的那一格）：换上之后**同一把
    终审再过一遍**、再对账，然后接着出片（退出 0）并留下「换过帧」的标记给「提交成片」。
    扫不出能换的（`--autopick` 非零）、或者换上的那一帧终审还红，才非零退出。
    这一步里不提交 spec 和扫描记录——换过的 spec 和记录跟成片一起提交；红了只提交停车账。"""
    done, calls = _run_step(tmp_path, COVER_STEP, mode="render")
    assert done.returncode == 0, done.stderr
    assert _kinds(calls) == ["cover keep", "audit", "check"], calls
    assert not (tmp_path / "cover-autopicked").exists(), "没换帧却留了换帧标记"

    swap = tmp_path / "swap"
    swap.mkdir()
    done, calls = _run_step(swap, COVER_STEP, mode="render", env={"AUDIT_SEQ": "1 0"})
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert _kinds(calls) == ["cover keep", "audit", "scan keep autopick", "audit", "check"], calls
    assert (swap / "cover-autopicked").is_file(), "换过帧却没留标记——提交成片那一步不会带上 spec"
    assert not any(c.startswith("git commit") for c in calls), calls

    none = tmp_path / "none"
    done, calls = _run_autopick_failure(none, "3")
    assert done.returncode != 0, "一格都换不了，这一步却退出 0——编码照样会开跑"
    assert _kinds(calls) == ["cover keep", "audit", "scan keep autopick"], calls
    assert not (none / "cover-autopicked").exists()
    # 退出 3（一格都挑不出来）才记停车账：只提交状态文件，推的是 dispatch 账本那条合并重试（D2）
    assert _parked_kinds(calls) == ["autopick"], calls
    assert any(c.startswith("python tools/pick_interview_renders.py --autopick-failed demo --kind autopick")
               for c in calls), calls
    commits = [c for c in calls if c.startswith("git commit")]
    assert len(commits) == 1 and "停车账" in commits[0], calls
    assert "git add data/interview_render_dispatched.json" in calls, calls
    assert not any(c.startswith("git add") and "cover_candidates" in c for c in calls), (
        "红着的 render 提交了扫描记录")
    assert any(c.startswith("git push origin HEAD:main") for c in calls), calls
    # 模型整趟不可用（4）、扫描工具自己坏了（别的非零）：环境／工具的事，不记停车账
    for rc in ("4", "1"):
        done, calls = _run_autopick_failure(tmp_path / f"rc{rc}", rc)
        assert done.returncode != 0, rc
        assert not any("--autopick-failed" in c for c in calls), (rc, calls)
        assert not any(c.startswith("git commit") for c in calls), (rc, calls)

    diverged = _parking_dir(tmp_path / "diverged")
    done, calls = _run_step(diverged, COVER_STEP, mode="render", env={"AUDIT_SEQ": "1 1"})
    assert done.returncode != 0, "换上的那一帧终审还红，却接着出片了"
    assert _kinds(calls) == ["cover keep", "audit", "scan keep autopick", "audit"], calls
    assert not (diverged / "cover-autopicked").exists()
    # 换上的那一帧终审还红也记停车账（同一个封面再投一趟换上的还是它）——只提交状态文件
    assert _parked_kinds(calls) == ["audit"], calls
    commits = [c for c in calls if c.startswith("git commit")]
    assert len(commits) == 1 and "停车账" in commits[0], calls


def _parking_dir(where: Path) -> Path:
    """停车账那一支要 `source tools/git_push_retry.sh`、`cp` 状态文件，工作目录里备一份。"""
    (where / "tools").mkdir(parents=True)
    shutil.copy(ROOT / "tools" / "git_push_retry.sh", where / "tools" / "git_push_retry.sh")
    (where / "data").mkdir()
    (where / "data" / "interview_render_dispatched.json").write_text(
        '{"slugs": [], "at": {}, "spec_sha256": {}}', encoding="utf-8")
    return where


def _parked_kinds(calls: list[str]) -> list[str]:
    """替身记下的停车账调用 → 各是哪种红（`--kind`）。"""
    return [c.split("--kind ")[1].split()[0] for c in calls if "--autopick-failed" in c]


def _run_autopick_failure(where: Path, scan_rc: str, ref: str = "main"):
    """封面前置那一步在 render 档红、`--autopick` 以 `scan_rc` 退出。"""
    return _run_step(_parking_dir(where), COVER_STEP, mode="render", ref=ref,
                     env={"AUDIT_RC": "1", "SCAN_RC": scan_rc})


def test_换上的终审还红和对账红也记同一笔停车账(tmp_path):
    """复审 2026-09-28：只在 `--autopick` 退出 3 时记账，另外两条「再投一趟照样红」的路照旧
    70 分钟一趟、永远红——

    - 自动换上的那一帧终审还红（扫描和终审分叉）
    - 终审过了、`--check` 对账红：D3 的边——已提交的记录说 frame_at 没过、预检因为「render
      会换上一格」放行，runner 上这一帧却过了闸、不换帧，对账拿那份记录一比就红

    两条都记进同一个计数（`--kind audit／check`），指纹按**派发时**那份 spec（HEAD 里的）
    算；只认退出 1（判了不合格），2（输入缺了）不记；cover 档不记（picker 不投 cover 档）。"""
    cases = {
        # 名字: (mode, env, 该记哪种, 调用顺序)
        "check": ("render", {"CHECK_RC": "1"}, ["check"], ["cover keep", "audit", "check"]),
        "swap_check": ("render", {"AUDIT_SEQ": "1 0", "CHECK_RC": "1"}, ["check"],
                       ["cover keep", "audit", "scan keep autopick", "audit", "check"]),
        "audit_rc2": ("render", {"AUDIT_SEQ": "1 2"}, [],
                      ["cover keep", "audit", "scan keep autopick", "audit"]),
        "check_rc2": ("render", {"CHECK_RC": "2"}, [], ["cover keep", "audit", "check"]),
        "cover_mode": ("cover", {"CHECK_RC": "1"}, [], ["scan keep", "cover", "audit", "check"]),
    }
    for name, (mode, env, kinds, order) in cases.items():
        done, calls = _run_step(_parking_dir(tmp_path / name), COVER_STEP, mode=mode, env=env)
        assert done.returncode != 0, (name, "封面那一步红了却退出 0")
        assert _kinds(calls) == order, (name, calls)
        assert _parked_kinds(calls) == kinds, (name, calls)
        commits = [c for c in calls if c.startswith("git commit")]
        assert len(commits) == len(kinds), (name, calls)
        if kinds:
            rec = next(c for c in calls if "--autopick-failed" in c)
            i_show = calls.index("git show HEAD:specs/interviews/demo.json")
            assert i_show < calls.index(rec), (name, "指纹要按派发时（HEAD）那份 spec 算", calls)
            assert "--dispatched-spec" in rec, (name, rec)
            assert any(c.startswith("git push origin HEAD:main") for c in calls), (name, calls)


def test_停车账只在main上记_分支上只告警(tmp_path):
    """picker 只在 main 上投、只读 main 上的账。分支上跑的 render（会话在分支上 `push=false`
    渲一版）红在封面那一步，记一笔会推到分支、跟着合并进 main，替一条在 main 上没红过的封面
    停车——分支上不记、不提交、不推，只印一行 `::warning::`。三种红都一样。"""
    runs = {
        "autopick": lambda d: _run_autopick_failure(d, "3", ref="wp/some-branch"),
        "audit": lambda d: _run_step(_parking_dir(d), COVER_STEP, mode="render",
                                     ref="wp/some-branch", env={"AUDIT_SEQ": "1 1"}),
        "check": lambda d: _run_step(_parking_dir(d), COVER_STEP, mode="render",
                                     ref="wp/some-branch", env={"CHECK_RC": "1"}),
    }
    for kind, run in runs.items():
        done, calls = run(tmp_path / kind)
        assert done.returncode != 0, kind
        assert not any("--autopick-failed" in c for c in calls), (kind, "分支上记了停车账", calls)
        assert not any(c.split()[:2] in (["git", "commit"], ["git", "add"], ["git", "push"])
                       for c in calls), (kind, calls)
        assert "::warning::" in done.stdout and "不记停车账" in done.stdout, (kind, done.stdout)
        assert "wp/some-branch" in done.stdout, (kind, done.stdout)
    # 同一个红在 main 上照记（对照组）
    done, calls = _run_autopick_failure(tmp_path / "main", "3")
    assert _parked_kinds(calls) == ["autopick"], calls


def test_预览档先扫一段再出海报再验(tmp_path):
    """cover 档：扫描先下源片并留着 → `--stage cover` 复用、用完删 → 同一把闸 →
    对账。扫描排在海报之前，是因为 `--stage cover` 用完会删源片。"""
    done, calls = _run_step(tmp_path, COVER_STEP, mode="cover")
    assert done.returncode == 0, done.stderr
    assert _kinds(calls) == ["scan keep", "cover", "audit", "check"], calls

    # 红了：记录**照样先提交**（下一帧挑哪个、推送前对账都要它），排名在错误
    # 旁边再印一遍，然后才非零退出——红了之后「提交成片」那一步不会跑
    red = _red_cover_dir(tmp_path)
    done, calls = _run_step(red, COVER_STEP, mode="cover", env={"AUDIT_RC": "1"})
    assert done.returncode != 0
    assert _kinds(calls) == ["scan keep", "cover", "audit", "report"], calls
    adds = [c for c in calls if c.startswith("git add")]
    assert adds == [f"git add output/interviews/demo/{scan.RECORD_NAME}"], (
        f"红着退出前没把扫描记录交上去（或者连墙一起交了）：{calls}")
    i_add = calls.index(adds[0])
    i_commit = next(i for i, c in enumerate(calls) if c.startswith("git commit"))
    i_push = next(i for i, c in enumerate(calls) if c.startswith("git push"))
    assert i_add < i_commit < i_push, calls


def _red_cover_dir(tmp_path: Path) -> Path:
    """一个 `bash -e` 真跑得到提交那一支的目录：有 `git_push_retry.sh`、有一份扫描记录。"""
    red = tmp_path / "red"
    shutil.copytree(ROOT / "tools", red / "tools",
                    ignore=lambda d, names: [n for n in names if n != "git_push_retry.sh"])
    rec = red / "output" / "interviews" / "demo" / scan.RECORD_NAME
    rec.parent.mkdir(parents=True)
    rec.write_text('{"method": "cover_scan_v1"}', encoding="utf-8")
    return red


def test_预览档渲不出海报也先交扫描记录(tmp_path):
    """`--stage cover` **自己**红了（frame_at 越过视频流最后一帧抛 NoFrameAt、
    Chromium 起不来……），扫描记录照样先提交再非零退出。

    第一版提交那几行只写在「像素闸没过」那一支里：`--stage cover` 一红，
    `bash -e` 当场结束这一步，刚写好的 `cover_candidates.json` 跟着 runner
    一起没了——而 frame_at 越过片尾那一种，扫描**刚好**把那一格记成了「没有画面」，
    正是最该交上去的那份（review 2026-09-27）。"""
    red = _red_cover_dir(tmp_path)
    done, calls = _run_step(red, COVER_STEP, mode="cover", env={"COVER_RC": "1"})
    assert done.returncode != 0, "海报都没渲出来，这一步却退出 0"
    assert _kinds(calls) == ["scan keep", "cover", "report"], (
        f"渲不出海报之后不该再跑像素闸，要先印排名：{calls}")
    adds = [c for c in calls if c.startswith("git add")]
    assert adds == [f"git add output/interviews/demo/{scan.RECORD_NAME}"], (
        f"`--stage cover` 红了，扫描记录没交上去：{calls}")
    i_commit = next(i for i, c in enumerate(calls) if c.startswith("git commit"))
    i_push = next(i for i, c in enumerate(calls) if c.startswith("git push"))
    assert calls.index(adds[0]) < i_commit < i_push, calls

    # render 档照旧只红不交：自动链只拨 render，它认领不了一份机器记录
    solo = tmp_path / "render"
    solo.mkdir()
    done, calls = _run_step(solo, COVER_STEP, mode="render", env={"COVER_RC": "1"})
    assert done.returncode != 0
    assert _kinds(calls) == ["cover keep"], calls
    assert not any(c.startswith("git ") for c in calls), calls


def test_第二份ASR在subs那一趟跑_排在切行提交之后(tmp_path):
    """subs 这一趟就跑第二份 ASR：只要音轨，跟出片无关。

    ⚠️ 排在「提交成片」之后——lines.json 是写中文要等的那一份，照旧一分多钟
    落库；第二份 ASR 三到五分钟，报告第二次提交。
    """
    names = _names()
    at = names.index(SUBS_VERIFY_STEP)
    assert names.index("取字幕切行") < names.index("提交成片") < at, names
    step = _step(SUBS_VERIFY_STEP)
    assert _holds(step.get("if"), "subs")
    for mode in ("render", "cover", "push"):
        assert not _holds(step.get("if"), mode), f"subs 那一步在 mode={mode} 也跑了"
    # 模型名那一步两档都要算，缓存两档同一把键
    assert _holds(_step("算第二份 ASR 模型").get("if"), "subs")
    keys = [s["with"]["key"] for s in _steps()
            if str(s.get("uses", "")).startswith("actions/cache")
            and s.get("with", {}).get("path") == "~/.cache/huggingface/hub"]
    assert len(keys) == 2 and len(set(keys)) == 1, (
        f"第二份 ASR 的模型缓存 subs 和 render 要同一把键：{keys}")


#: `--stage` 各档要不要 ffmpeg：会走 `yt_download` 下源片或音轨的要（Brightcove
#: HLS、合流、抽帧都靠它）；只拉字幕／故事板的不要。新加一档必须在这儿归类——
#: 下面那条先拿 argparse 的 `choices` 对一遍，漏归类当场红。
_MEDIA_STAGES = {"verify", "cover", "cover-scan", "render"}
_CAPTION_ONLY_STAGES = {"subs", "sheet"}


def test_会下载媒体的每一档都先装ffmpeg():
    """`test_会下载媒体的工作流都要装ffmpeg` 按 **job** 查——这条工作流只有一个
    job，render/cover 那一步装了 ffmpeg，整个 job 就算「装了」。而 2026-09-27
    第二份 ASR 挪进 `mode=subs` 之后，subs 那一档**一个 ffmpeg 都没装**，
    job 级的判据照样绿（review 指出：tennistv.com 那 12 条是 Brightcove HLS）。

    所以按 **mode** 推：对 dispatch 表单里的每一档，走一遍它真会跑的步骤，
    凡是跑 `build_interview_clip.py --stage <要下媒体的那几档>` 的，前面必须
    有一步真调了 `ensure_ffmpeg`（去掉注释再认——注释里写着 ffmpeg 不算装了）。"""
    import ast  # noqa: PLC0415
    import re  # noqa: PLC0415

    import yaml  # noqa: PLC0415

    tree = ast.parse((ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8"))
    choices = next(
        ast.literal_eval(kw.value) for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_argument"
        and node.args and getattr(node.args[0], "value", None) == "--stage"
        for kw in node.keywords if kw.arg == "choices")
    assert set(choices) == _MEDIA_STAGES | _CAPTION_ONLY_STAGES, (
        f"--stage 的档位变了（{choices}）：新的那一档要不要 ffmpeg，先在上面两张表里归类")

    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    modes = (wf.get("on") or wf[True])["workflow_dispatch"]["inputs"]["mode"]["options"]
    checked = []
    for mode in modes:
        ready = False
        for step in _steps():
            code = "\n".join(ln for ln in str(step.get("run") or "").splitlines()
                             if not ln.lstrip().startswith("#"))
            # 只有「跑 --stage」和「装 ffmpeg」这两类步骤是主语；别的步骤的 if 里有
            # push／ref_name／always() 这类 `_holds` 不认的写法，本来也不用算
            if "build_interview_clip.py" not in code and "ensure_ffmpeg" not in code:
                continue
            if not _holds(step.get("if"), mode):
                continue
            for stage in re.findall(r"build_interview_clip\.py[^\n]*--stage\s+([\w-]+)", code):
                if stage in _MEDIA_STAGES:
                    checked.append(f"{mode}:{stage}")
                    assert ready, (
                        f"mode={mode} 的「{step.get('name')}」跑 --stage {stage}（要下媒体），"
                        "前面却没有一步 `ensure_ffmpeg`——缺了它报的是 yt-dlp 下不动，"
                        "看起来像源的问题")
            if re.search(r"(?<![\w-])ensure_ffmpeg(?![\w-])", code):
                ready = True
    assert {"subs:verify", "render:verify", "cover:cover", "render:cover"} <= set(checked), (
        f"判据的主语没了：只校到 {sorted(set(checked))}")


def test_subs的第二份ASR红了也要先交报告再红(tmp_path):
    """真跑那一步：verify 没跑成（退出 1），报告照样 add → commit → push，
    然后这一步以 verify 的退出码结束。红着把报告扔掉，这一趟就白跑了。

    ⚠️ 只报了分歧／空档（`VERIFY_FINDINGS_EXIT`）**不算红**——那是人核之前的常态，
    红了会把 pipeline_health 的失败率顶上去、推微信告警。见下一条。"""
    shutil.copytree(ROOT / "tools", tmp_path / "tools",
                    ignore=lambda d, names: [n for n in names if n != "git_push_retry.sh"])
    outdir = tmp_path / "output" / "interviews" / "demo"
    outdir.mkdir(parents=True)
    (outdir / "_audio.m4a").write_bytes(b"audio")
    (outdir / "whisper.json").write_text("[]", encoding="utf-8")
    (outdir / "transcript_diff.md").write_text("# diff", encoding="utf-8")
    done, calls = _run_step(tmp_path, SUBS_VERIFY_STEP, mode="subs",
                            env={"VERIFY_RC": "1"}, cwd=tmp_path)
    assert done.returncode == 1, (done.returncode, done.stdout, done.stderr)
    assert "::error::" in done.stdout
    order = [c.split()[0] + " " + c.split()[1] for c in calls]
    assert "pip install" in order[0], calls
    i_verify = next(i for i, c in enumerate(calls) if "--stage verify" in c)
    i_add = next(i for i, c in enumerate(calls) if c.startswith("git add"))
    i_commit = next(i for i, c in enumerate(calls) if c.startswith("git commit"))
    i_push = next(i for i, c in enumerate(calls) if c.startswith("git push"))
    assert i_verify < i_add < i_commit < i_push, calls
    # 中间物不进仓库：和「提交成片」同一套清法
    assert not (outdir / "_audio.m4a").exists() and not (outdir / "whisper.json").exists()
    assert (outdir / "transcript_diff.md").exists(), "报告被清掉了"

    green = tmp_path / "green"
    shutil.copytree(tmp_path / "tools", green / "tools")
    (green / "output" / "interviews" / "demo").mkdir(parents=True)
    done, calls = _run_step(green, SUBS_VERIFY_STEP, mode="subs", cwd=green)
    assert done.returncode == 0, done.stderr


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                           *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout


def _commit_step_in_real_git(tmp_path: Path, mode: str, *,
                             race: bool = False) -> tuple[subprocess.CompletedProcess,
                                                          Path, Path]:
    """「提交成片」那一步在**真 git 仓库**里跑一遍（只有 python/sleep 换替身）。

    判的是**产物进没进仓库**，不是脚本里写没写 `rm`：候选墙在 `mode=cover` 要
    留在盘上给 artifact、又不许进 git——两件事只有真 `git add` 一遍才分得清。
    `race=True` 时远端先被别人推过一次，逼它走「重放到最新分支上」那条路。
    """
    remote, work = tmp_path / "remote.git", tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    shutil.copy(ROOT / ".gitignore", work / ".gitignore")
    _git(work, "add", ".gitignore")
    _git(work, "commit", "-qm", "base")
    _git(work, "remote", "add", "origin", str(remote))
    _git(work, "push", "-q", "origin", "main")
    if race:
        other = tmp_path / "other"
        subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
        (other / "README.md").write_text("别人刚推过\n", encoding="utf-8")
        _git(other, "add", "README.md")
        _git(other, "commit", "-qm", "race")
        _git(other, "push", "-q", "origin", "main")
    outdir = work / "output" / "interviews" / "demo"
    outdir.mkdir(parents=True)
    (outdir / "poster.jpg").write_bytes(b"poster")
    (outdir / scan.RECORD_NAME).write_text('{"method": "cover_scan_v1"}', encoding="utf-8")
    (outdir / scan.SHEET_NAME).write_bytes(b"sheet" * 1000)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("python", "sleep"):
        (bin_dir / name).write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        (bin_dir / name).chmod(0o755)
    body = (str(_step("提交成片")["run"])
            .replace("${{ github.event.inputs.slug }}", "demo")
            .replace("${{ github.ref_name }}", "main"))
    assert "${{" not in body, body
    (tmp_path / "step.sh").write_text(body, encoding="utf-8")
    env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
               MODE=mode, RUNNER_TEMP=str(tmp_path))
    done = subprocess.run(["bash", "-e", str(tmp_path / "step.sh")], cwd=work, env=env,
                          capture_output=True, text=True, timeout=120)
    return done, remote, outdir


@pytest.mark.parametrize("race", [False, True], ids=["直推", "撞车重放"])
def test_候选墙只走artifact_扫描记录进仓库(tmp_path, race):
    """`cover_scan_sheet.jpg` 一张约 0.6 MB、每趟 mode=cover 一张——和缩略图墙
    同一种工作台，不许进 git（`test_缩略图墙两头都不许进仓库`）。几 KB 的
    `cover_candidates.json` 要进（推送前对账的就是它）。

    ⚠️ `mode=cover` 那趟墙还得**留在盘上**：「提交成片」排在 upload-artifact
    之前，删了 artifact 里就没墙了——人挑帧两手空空。撞车重放那条路
    （`rm -rf "$D"` 再从本趟提交里放回来）同样不许把它弄丢。"""
    done, remote, outdir = _commit_step_in_real_git(tmp_path, "cover", race=race)
    assert done.returncode == 0, (done.stdout, done.stderr)
    tree = _git(remote, "ls-tree", "-r", "--name-only", "main").split()
    assert f"output/interviews/demo/{scan.RECORD_NAME}" in tree, tree
    assert "output/interviews/demo/poster.jpg" in tree, tree
    assert not any(p.endswith(scan.SHEET_NAME) for p in tree), (
        f"候选墙进了仓库：{tree}——每趟 mode=cover 往 git 里塞 0.6 MB")
    assert (outdir / scan.SHEET_NAME).is_file(), (
        "mode=cover 那趟把候选墙从盘上删了——upload-artifact 排在后面，人就看不到墙了")
    if race:
        assert "README.md" in tree, "重放没落在别人推过的那一版上"

    other = tmp_path / "render"
    other.mkdir()
    done, remote, outdir = _commit_step_in_real_git(other, "render")
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert not (outdir / scan.SHEET_NAME).exists(), "别的档留下了候选墙"


def test_subs只报了要人核的发现不算红(tmp_path):
    """`--stage verify` 退出 `VERIFY_FINDINGS_EXIT`＝只有分歧／空档，工具本身跑完了。

    刚切出来、没人核过的转写有分歧是常态。第一版让这一步红，而
    `tools/pipeline_health.py` 按 run 的 conclusion 数失败率（近 10 趟红 40% 或
    连着红 3 趟就推微信）——常态红会把告警顶成狼来了。所以：报告照样提交，
    `::warning::` 收尾，退出 0；render 那一步照旧拦。"""
    import tools.build_interview_clip as clip  # noqa: PLC0415

    shutil.copytree(ROOT / "tools", tmp_path / "tools",
                    ignore=lambda d, names: [n for n in names if n != "git_push_retry.sh"])
    outdir = tmp_path / "output" / "interviews" / "demo"
    outdir.mkdir(parents=True)
    (outdir / "transcript_diff.md").write_text("# diff", encoding="utf-8")
    done, calls = _run_step(tmp_path, SUBS_VERIFY_STEP, mode="subs", cwd=tmp_path,
                            env={"VERIFY_RC": str(clip.VERIFY_FINDINGS_EXIT)})
    assert done.returncode == 0, (done.returncode, done.stdout, done.stderr)
    assert "::warning::" in done.stdout and "::error::" not in done.stdout, done.stdout
    assert any(c.startswith("git push") for c in calls), f"报告没交：{calls}"


# ---------------------------------------------------------------- --stage verify

def _drive_main(monkeypatch, tmp_path: Path, spec: dict, stage: str,
                gaps: list[tuple[float, float]], verify_raises=None) -> dict:
    """直接跑 `build_interview_clip.main()`，网络和 whisper 那几样换成替身。"""
    import tools.build_interview_clip as clip  # noqa: PLC0415

    calls: dict = {"verify": 0, "fetch_words": 0}
    for name in ("check_source_contract", "check_topline_format", "check_opening",
                 "check_lead_in", "check_trail_in", "check_copy_page",
                 "check_human_quote", "storyboard_sheet"):
        monkeypatch.setattr(clip, name, lambda *a, **k: None)
    monkeypatch.setattr(clip, "OUTDIR", tmp_path / "out")
    def fake_fetch(*a, **k):
        calls["fetch_words"] += 1
        return []

    monkeypatch.setattr(clip, "fetch_words", fake_fetch)
    monkeypatch.setattr(clip, "segment", lambda *a, **k: [
        {"a": 10.0, "b": 12.0, "en": "Thank you so much"},
        {"a": 16.0, "b": 18.0, "en": "It was a tough match"}])
    monkeypatch.setattr(clip, "caption_gaps", lambda *a, **k: list(gaps))

    def fake_verify(*a, **k):
        calls["verify"] += 1
        if verify_raises is not None:
            raise verify_raises

    monkeypatch.setattr(clip, "verify_transcript", fake_verify)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["build_interview_clip.py", "--spec", str(spec_path),
                                      "--stage", stage])
    try:
        calls["rc"] = clip.main()
    except SystemExit as exc:
        calls["exit"] = str(exc)
    calls["outdir"] = tmp_path / "out" / spec["slug"]
    return calls


_SPEC = {"slug": "demo", "url": "https://example.test/x.mp4", "start": 8.0, "end": 20.0}


def test_verify在中文还空着的时候也要跑第二份ASR(monkeypatch, tmp_path):
    """subs 那一趟 zh 必然还空着，而那正是第二份 ASR 该跑的时候——
    指纹里本来就没有中文（`transcript_fingerprint`）。"""
    got = _drive_main(monkeypatch, tmp_path, dict(_SPEC), "verify", [])
    assert got["verify"] == 1, "zh 空着 verify 就提前退出了——第二份 ASR 又只能等到 render"
    assert got.get("rc") == 0, got
    assert (got["outdir"] / "verify_fingerprint.json").is_file(), "验过了却没落指纹"

    # 反过来：别的 stage 在没中文时照旧只打印行、不往下走
    got = _drive_main(monkeypatch, tmp_path, dict(_SPEC), "subs", [])
    assert got["verify"] == 0 and got.get("rc") == 0


def test_verify按出片那道空档闸把会红的报出来(monkeypatch, tmp_path, capsys):
    """render 会红的空档，verify 这一步就按**同一个函数**报——键要印出来。
    指纹照样先落（报告和指纹是 subs 那一趟要交的东西）。退出码是
    `VERIFY_FINDINGS_EXIT`：subs 那一步靠它分清「要人核」和「工具坏了」。"""
    import tools.build_interview_clip as clip  # noqa: PLC0415

    got = _drive_main(monkeypatch, tmp_path, dict(_SPEC), "verify", [(12.0, 15.5)])
    assert got.get("rc") == clip.VERIFY_FINDINGS_EXIT, got
    assert "12.0-15.5" in capsys.readouterr().out, "空档的键没印出来——照着提示写不出销账"
    assert (got["outdir"] / "verify_fingerprint.json").is_file()

    settled = dict(_SPEC, caption_gaps_ok={"12.0-15.5": "听过：掌声"})
    got = _drive_main(monkeypatch, tmp_path, settled, "verify", [(12.0, 15.5)])
    assert "exit" not in got and got.get("rc") == 0, got

    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    render_stage = src.split('if args.stage == "render":')[1]
    assert "blocking_gaps(spec, lines, outdir)" in render_stage, (
        "render 那道空档闸没走 blocking_gaps——verify 报的和 render 拦的就不是同一个判据")
    assert clip.blocking_gaps  # 名字在


def test_verify分歧和空档一起报_工具坏了照样抛(monkeypatch, tmp_path, capsys):
    """分歧超闸（`ReviewFindings`）不再一抛就走：和空档收齐一起印、退出码
    `VERIFY_FINDINGS_EXIT`、**不落指纹**（没验过的不许留「验过了」的标记）。
    而配置／工具的毛病（同一个模型跑两遍、下不动音轨）是普通 `SystemExit`，
    照样抛出去——subs 那一步对它照样红，不许混进「常态发现」里被 warning 吞掉。"""
    import tools.build_interview_clip as clip  # noqa: PLC0415

    got = _drive_main(monkeypatch, tmp_path, dict(_SPEC), "verify", [(12.0, 15.5)],
                      verify_raises=clip.ReviewFindings("两份转写对不上 23.0%"))
    out = capsys.readouterr().out
    assert got.get("rc") == clip.VERIFY_FINDINGS_EXIT, got
    assert "23.0%" in out and "12.0-15.5" in out, f"两类发现没收齐：{out}"
    assert not (got["outdir"] / "verify_fingerprint.json").exists(), "分歧超闸还落了指纹"

    (tmp_path / "broken").mkdir()
    got = _drive_main(monkeypatch, tmp_path / "broken", dict(_SPEC), "verify", [],
                      verify_raises=SystemExit("`whisper_model` 和 `asr_model` 都是 small.en"))
    assert "small.en" in got.get("exit", "") and "rc" not in got, got
    assert issubclass(clip.ReviewFindings, SystemExit), "render 那头靠它照样非零退出"


def test_中文还空着也能出封面(monkeypatch, tmp_path):
    """「封面排在最前面、紧跟选题」正是 zh 还空着的那一刻。`--stage cover` 原来
    排在切行和 `if not zh: return 0` 后面——于是 0 退出、一张海报都没出，下一步
    的像素闸报「poster 不存在」，扫描白跑一分钟。封面不要字幕：也不许为它拉字幕。"""
    import tools.build_interview_clip as clip  # noqa: PLC0415

    made: list[Path] = []
    monkeypatch.setattr(clip, "yt_download", lambda url, dest, fmt, spec: dest)
    monkeypatch.setattr(clip, "_logo_filter", lambda *a, **k: "")

    def fake_poster(spec, src, outdir, logo="", **_k):
        poster = outdir / "poster.jpg"
        poster.write_bytes(b"jpg")
        made.append(poster)
        return poster

    monkeypatch.setattr(clip, "cover_poster", fake_poster)
    spec = dict(_SPEC, cover={"frame_at": 10.0})          # 没有 zh
    got = _drive_main(monkeypatch, tmp_path, spec, "cover", [])
    assert got.get("rc") == 0 and made and made[0].is_file(), (
        f"zh 空着 --stage cover 没出海报：{got}")
    assert got["fetch_words"] == 0, "出封面去拉了一趟字幕——封面不要字幕"


def test_命令行不给step就轮到spec里的scan_step(monkeypatch, tmp_path):
    """工作流那一步不传 `--step`，走的正是 spec 的 `cover.scan_step`——命令行的
    默认值要是 0.2，spec 那条路就一次都轮不到。"""
    got: dict = {}

    def fake_run_scan(spec, outdir, clip, *, window, step, keep_source, autopick, spec_path):
        got.update(step=step, window=window, keep=keep_source, autopick=autopick)
        return 0

    monkeypatch.setattr(scan, "run_scan", fake_run_scan)
    spec = dict(_SPEC, cover={"frame_at": 10.0, "scan_step": 0.5})
    res = _drive_main(monkeypatch, tmp_path, spec, "cover-scan", [])
    assert res.get("rc") == 0 and got["step"] is None and got["keep"] is False, got
    assert got["autopick"] is False, "没给 --autopick 就改写了 spec——mode=cover 只扫不换"
    assert scan.scan_step(spec, got["step"]) == 0.5


# ---------------------------------------------------------------- 扫描：纯逻辑

def test_候选时刻一定含spec现在那一帧_越过片尾的剔掉():
    times = scan.candidate_times(10.0, 11.0, 0.2, include=(10.33,), end=10.9)
    assert 10.33 in times, "spec 现在的 frame_at 不在扫描里，候选墙上就没有对照"
    assert times == [10.0, 10.2, 10.33, 10.4, 10.6, 10.8]
    with pytest.raises(SystemExit):
        scan.candidate_times(0.0, 100.0, 0.2)       # 501 格：窗口给宽了要出声


def test_扫描窗口的来源有先后():
    spec = {"cover": {"frame_at": 1.0}}
    assert scan.scan_window(spec) == (0.0, 3.0)     # 前后各 2 秒，夹在 0 以上
    spec["cover"]["scan_window"] = [30, 40]
    assert scan.scan_window(spec) == (30.0, 40.0)
    assert scan.scan_window(spec, "5:6") == (5.0, 6.0)
    assert scan.scan_step({"cover": {"scan_step": 0.5}}) == 0.5
    assert scan.scan_step({"cover": {"scan_step": 0.5}}, 0.2) == 0.2
    with pytest.raises(SystemExit):
        scan.scan_window({"cover": {"scan_window": [5]}})


def _face(sharp: float, eyes: int = 2) -> dict:
    """别的几项都给得宽，让清晰度成为最紧的那一条——排序才看得出按余量排。"""
    return {"box": [500, 300, 150, 150], "eyes": eyes, "face_height_ratio": 0.4,
            "face_area_ratio": 0.05, "sharpness": sharp, "contrast": 96.0,
            "center_x_ratio": 0.5, "center_y_ratio": 0.3}


def test_逐格量_量不出记不合格_渲不出照样抛(tmp_path):
    spec = {"slug": "demo", "cover": {"frame_at": 2.0, "shot_type": "close_up"}}
    rendered = []

    def poster_at(t, dest):
        rendered.append(t)
        dest.write_bytes(b"x")

    def audit(_path, spec_t):
        t = spec_t["cover"]["frame_at"]          # 每一格按自己的 frame_at 判合同
        if t == 1.0:
            raise RuntimeError("照片区域没有检出正面人脸")
        return {"face": _face(60.0 + t * 10)}, ([] if t >= 2.0 else ["只检出 1 只眼"])

    entries, posters = scan.measure(spec, [1.0, 1.5, 2.0, 2.5], poster_at, tmp_path, audit)
    assert rendered == [1.0, 1.5, 2.0, 2.5] and set(posters) == set(rendered)
    status = {e["frame_at"]: e["status"] for e in entries}
    assert status == {1.0: "fail", 1.5: "fail", 2.0: "pass", 2.5: "pass"}
    assert "正面人脸" in entries[0]["issues"][0]
    assert scan.ranked_passing(entries, 2.0) == [2.5, 2.0], "排序要按余量，不按离得近"

    def broken(_t, _dest):
        raise OSError("Chromium 起不来")

    with pytest.raises(OSError):
        scan.measure(spec, [1.0], broken, tmp_path, audit)


def _record(spec: dict, entries: list[dict]) -> dict:
    return json.loads(json.dumps(scan.build_record(spec, (1.0, 3.0), 0.5, entries)))


def test_扫描记录对账():
    spec = {"slug": "demo", "url": "u", "cover": {"frame_at": 2.0, "zoom": 1.5}}
    entries = [{"frame_at": 2.0, "status": "pass", "issues": [], "face": _face(90), "margin": 2.0},
               {"frame_at": 2.5, "status": "fail", "issues": ["只检出 1 只眼"],
                "face": _face(90, 1), "margin": 2.0}]
    record = _record(spec, entries)
    assert scan.record_problem(None, spec) == "", "没有记录不许拦——存量一份记录都没有"
    assert scan.record_problem(record, spec) == ""

    moved = json.loads(json.dumps(spec))
    moved["cover"]["frame_at"] = 7.0
    problem = scan.record_problem(record, moved)
    assert "没扫过" in problem
    # 记录外的帧：红的时候只给两条出路——重扫，或者认领（出路本身不许丢）
    assert "mode=cover" in problem and "_frame_scan_why" in problem, problem
    moved["cover"]["frame_at"] = 2.5
    problem = scan.record_problem(record, moved)
    assert "没过闸" in problem and "_frame_scan_why" in problem, problem
    moved["cover"]["_frame_scan_why"] = "候选墙外那一帧是颁奖瞬间，人工看过"
    assert scan.record_problem(record, moved) == "", "认领了还拦"

    reframed = json.loads(json.dumps(spec))
    reframed["cover"].update({"frame_at": 7.0, "zoom": 2.0})
    assert scan.record_problem(record, reframed) == "", (
        "取景变了的记录说的是另一张海报，管不到当前这张")
    assert "读不懂" in scan.record_problem({"method": "x"}, spec)


def test_换了尺子的旧记录不对账_旧的fail不许接着拦(monkeypatch):
    """审核器版本或阈值变过，记录里每一格的 pass/fail 说的就不是今天这道闸了。

    第一版 `record_problem` 只比取景、不比尺子：阈值放宽之后，一格旧的 `fail`
    照样把一帧**今天过得了闸**的封面挡在推送外面（review 2026-09-27）。"""
    spec = {"slug": "demo", "url": "u", "cover": {"frame_at": 2.5}}
    entries = [{"frame_at": 2.5, "status": "fail", "issues": ["清晰度 40，必须 ≥ 45"],
                "face": _face(40), "margin": 0.9}]
    record = _record(spec, entries)
    assert "没过闸" in scan.record_problem(record, spec), "同一把尺子下旧 fail 该拦"
    assert not scan.stale_ruler(record)

    import audit_interview_cover as auditor  # noqa: PLC0415

    monkeypatch.setattr(auditor, "MIN_FACE_SHARPNESS", 35.0)        # 阈值放宽
    assert "MIN_FACE_SHARPNESS" in scan.stale_ruler(record)
    assert scan.record_problem(record, spec) == "", "阈值变了，旧的 fail 还在拦"
    monkeypatch.undo()

    monkeypatch.setattr(auditor, "FACE_CENTER_Y_RANGE", (0.06, 0.80))  # 不在 MIN_* 里的阈值也算
    assert scan.record_problem(record, spec) == ""
    monkeypatch.undo()

    monkeypatch.setattr(auditor, "LOCAL_AUDITOR", "opencv-haar-v2")   # 换了审核器
    assert "审核器" in scan.stale_ruler(record)
    assert scan.record_problem(record, spec) == ""
    monkeypatch.undo()

    legacy = {k: v for k, v in record.items() if k != "thresholds"}  # 第一版写的记录
    assert scan.record_problem(legacy, spec) == ""


def test_版式指纹跟着海报模板和画布几何走_只改说明不动(tmp_path):
    """尺子只比审核模块的阈值时，**换海报版式**（模板、钩子那条渐变带、照片区几何）
    的旧记录看起来还是新的——同一个 frame_at 渲出来已经是另一张海报，一格旧的 fail
    照样拦（review 2026-09-27：待合的 UI 包正要改赛后开麦封面的版式）。

    指纹按源码文本算：模板里一个数变了就变；只改 docstring／整行注释不变
    （这个仓库的注释天天在长，每长一句就让全部记录失效，闸就等于没有）；
    名单里的函数改名了要大声报错，不许悄悄少算一段。"""
    src = ROOT / "tools" / "build_interview_clip.py"
    text = src.read_text(encoding="utf-8")
    base = tmp_path / "base.py"
    base.write_text(text, encoding="utf-8")
    assert scan.layout(base) == scan.layout(), "同一份源码两个指纹"

    def variant(name: str, old: str, new: str) -> str:
        assert text.count(old) == 1, f"判据的锚点「{old}」没了或重复了"
        path = tmp_path / f"{name}.py"
        path.write_text(text.replace(old, new), encoding="utf-8")
        return scan.layout(path)

    fp = scan.layout(base)
    assert variant("band", "_COVER_BAND_H = 520\n", "_COVER_BAND_H = 560\n") != fp, "钩子带挪了，指纹没变"
    assert variant("title", "_TITLE_PX = 94\n", "_TITLE_PX = 90\n") != fp, "标题字号变了，指纹没变"
    assert variant("sub", ".sub{{margin-top:26px;", ".sub{{margin-top:30px;") != fp, (
        "cover_html 模板里的一个数变了，指纹没变——封面 HTML 在 cover_html 里，别只盯 build_cover")
    assert variant("top", "VIDEO_TOP = 150\n", "VIDEO_TOP = 170\n") != fp, "照片区挪了，指纹没变"
    assert variant("doc", '"""封面：本场抽一帧 + 文案', '"""封面（改个说法）：本场抽一帧 + 文案') == fp, (
        "只改了 build_cover 的 docstring，指纹却变了")
    assert variant("comment", "    cov = spec[\"cover\"]\n",
                   "    # 只是一句新注释\n\n    cov = spec[\"cover\"]\n") == fp, (
        "只加了一行注释，指纹却变了")
    assert variant("unrelated", '_FONT_SIZE = {"en": 46, "zh": 70}',
                   '_FONT_SIZE = {"en": 48, "zh": 70}') == fp, "字幕字号不在封面上，指纹却变了"
    renamed = tmp_path / "renamed.py"
    renamed.write_text(text.replace("def build_cover(", "def build_poster("), encoding="utf-8")
    with pytest.raises(SystemExit, match="build_cover"):
        scan.layout(renamed)


def test_换了版式或人脸模型的旧记录不对账(monkeypatch):
    """版式、人脸模型（main 上的 `face_checks`，并进来之后它的阈值和权重也决定
    一格过不过）都是尺子的一部分：变了，旧记录的 fail 不许接着拦。"""
    import types  # noqa: PLC0415

    monkeypatch.setitem(sys.modules, "face_checks", None)   # 这条分支上还没有
    spec = {"slug": "demo", "url": "u", "cover": {"frame_at": 2.5}}
    entries = [{"frame_at": 2.5, "status": "fail", "issues": ["只检出 1 只眼"],
                "face": _face(90, 1), "margin": 2.0}]
    record = _record(spec, entries)
    assert record["face_model"] is None
    assert "没过闸" in scan.record_problem(record, spec), "同一把尺子下旧 fail 该拦"

    real_layout = scan.layout
    monkeypatch.setattr(scan, "layout", lambda source=None: "0123456789abcdef")
    assert "版式" in scan.stale_ruler(record)
    assert scan.record_problem(record, spec) == "", "海报版式变了，旧的 fail 还在拦"
    monkeypatch.setattr(scan, "layout", real_layout)
    legacy = {k: v for k, v in record.items() if k != "layout"}      # 版式指纹之前写的记录
    assert "版式" in scan.stale_ruler(legacy)
    assert scan.record_problem(legacy, spec) == ""

    face = types.ModuleType("face_checks")
    face.CACHE_KEY, face.MATCH_SIM, face.EYE_OPEN_EAR = "face-models-a", 0.34, 0.16
    monkeypatch.setitem(sys.modules, "face_checks", face)
    assert "人脸模型" in scan.stale_ruler(record), "人脸模型并进来了，没它的旧记录还在对账"
    assert scan.record_problem(record, spec) == ""
    with_face = _record(spec, entries)
    assert with_face["face_model"]["cache_key"] == "face-models-a"
    assert "没过闸" in scan.record_problem(with_face, spec)
    monkeypatch.setattr(face, "EYE_OPEN_EAR", 0.18)                  # 睁眼阈值改了
    assert "人脸模型" in scan.stale_ruler(with_face)
    monkeypatch.setattr(face, "EYE_OPEN_EAR", 0.16)
    monkeypatch.setattr(face, "CACHE_KEY", "face-models-b")          # 换了权重
    assert scan.record_problem(with_face, spec) == ""


def test_候选墙贴原尺寸的脸(tmp_path):
    from PIL import Image  # noqa: PLC0415

    spec = {"slug": "demo", "url": "u", "cover": {"frame_at": 2.0}}
    posters = {}
    for t in (2.0, 2.5):
        p = tmp_path / f"{t}.jpg"
        Image.new("RGB", scan.CANVAS, (40, 90, 60)).save(p)
        posters[t] = p
    entries = [{"frame_at": 2.0, "status": "fail", "issues": ["x"], "face": None, "margin": None},
               {"frame_at": 2.5, "status": "pass", "issues": [], "face": _face(90), "margin": 2}]
    sheet = scan.contact_sheet(_record(spec, entries), posters, tmp_path / scan.SHEET_NAME)
    with Image.open(sheet) as im:
        assert im.format == "JPEG"
        assert im.width == 2 * scan.TILE_W, "一格要 640 宽——判得了表情才有用"


# ---------------------------------------------------------------- 扫描：走同一份实现

def test_扫描走cover_poster和audit_poster同一份实现(tmp_path, monkeypatch):
    """扫的那张必须就是终审审的那张：抽帧＋渲海报走 `clip.cover_poster`（带 `at`），
    量走 `audit_interview_cover.audit_poster`。另抄一份迟早分叉，而分叉的样子是
    「扫描说能过、终审红了」。"""
    from PIL import Image  # noqa: PLC0415

    outdir = tmp_path / "demo"
    outdir.mkdir()
    (outdir / "source.mp4").write_bytes(b"src")
    seen: list[tuple[float, Path]] = []

    class FakeClip:
        SOURCE_FMT = "fmt"

        @staticmethod
        def yt_download(url, dest, fmt, spec):
            assert fmt == "fmt"
            return dest

        class NoFrameAt(RuntimeError):
            pass

        @staticmethod
        def probe_video_duration(_src):
            return 30.0

        @staticmethod
        def _logo_filter(spec, src, out):
            return ""

        @staticmethod
        def canvas_page():
            import contextlib  # noqa: PLC0415
            return contextlib.nullcontext("page")

        @staticmethod
        def cover_poster(spec, src, out, logo, *, at, dest, page):
            assert page == "page", "没复用同一个浏览器页面"
            seen.append((at, dest))
            Image.new("RGB", scan.CANVAS, (30, 30, 30)).save(dest)
            dest.with_suffix(".html").write_text("<html>", encoding="utf-8")
            return dest

    measured = []

    def fake_audit(path, spec_t, *, face=False, rivals=()):
        assert face is True, "扫描那一格没跑认人＋睁眼——扫描的 pass 就不是终审的 pass"
        measured.append(spec_t["cover"]["frame_at"])
        return {"face": _face(90)}, []

    monkeypatch.setattr(scan, "audit_poster", fake_audit)
    spec = {"slug": "demo", "url": "u",
            "cover": {"frame_at": 10.0, "scan_window": [9.6, 10.4], "scan_step": 0.2}}
    assert scan.run_scan(spec, outdir, FakeClip) == 0
    assert [t for t, _ in seen] == [9.6, 9.8, 10.0, 10.2, 10.4] == measured
    assert all(not d.with_suffix(".html").exists() for _, d in seen), "12 MB 的 HTML 没删"
    record = json.loads((outdir / scan.RECORD_NAME).read_text(encoding="utf-8"))
    assert record["passing"][0] == 10.0 and len(record["passing"]) == 5
    assert (outdir / scan.SHEET_NAME).is_file()
    assert not (outdir / "source.mp4").exists(), "没给 --keep-source 却把源片留下了"

    text = (ROOT / "tools" / "interview_cover_scan.py").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    for own in ('"-frames:v"', "analyze_poster(", "validate_result("):
        assert own not in code, f"扫描自己写了一份 {own}——要走 cover_poster / audit_poster"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="要真 ffmpeg 造一条音轨比画面长的源片")
def test_片尾按视频流剔_越过最后一帧记一格没有画面(tmp_path, monkeypatch):
    """2026-09-27 review 复现：8.0 秒画面 ＋ 8.3 秒音轨，`ffmpeg -ss 8.1` 退出码 0、
    一帧不出。原来按容器时长（＝最长那条流）剔片尾，8.1 那一格留着，渲海报时
    `build_cover` 的 `read_bytes()` 抛 FileNotFoundError，整趟扫描红——而
    `frame_at` 离片尾两秒以内时扫描窗口一定会盖到那儿。"""
    import tools.build_interview_clip as clip  # noqa: PLC0415

    src = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", "color=c=gray:s=320x240:d=8:r=25",
                    "-f", "lavfi", "-i", "sine=d=8.3",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(src)],
                   check=True, timeout=120)
    assert abs(clip.probe_duration(src) - 8.3) < 0.05, "造出来的源片音轨没比画面长，前提不成立"
    video_end = clip.probe_video_duration(src)
    assert abs(video_end - 8.0) < 0.05, f"视频流时长读成了 {video_end}"
    times = scan.candidate_times(7.6, 8.4, 0.1, include=(8.1,), end=video_end)
    assert max(times) < 8.0 and 8.1 not in times, times

    # 剔完还撞上（低帧率源最后一帧早于 end-0.05）：cover_poster 报一个**专门的**
    # 类型，不是 FileNotFoundError——后者和「ffmpeg 没装」长得一样
    with pytest.raises(clip.NoFrameAt, match="没有画面"):
        clip.cover_poster({"cover": {"frame_at": 8.1}}, src, tmp_path,
                          at=8.1, dest=tmp_path / "late.jpg")

    # 扫描把它记成一格不合格，别的格照量；墙上没有它
    def poster_at(t, dest):
        if t > 7.95:
            raise scan.NoFrame("越过视频流最后一帧")
        dest.write_bytes(b"x")

    def audit(_path, spec_t, **_kw):
        return {"face": _face(90)}, []

    spec = {"slug": "demo", "cover": {"frame_at": 7.8}}
    entries, posters = scan.measure(spec, [7.8, 7.9, 8.1], poster_at, tmp_path, audit)
    by_t = {e["frame_at"]: e for e in entries}
    assert by_t[8.1]["status"] == "fail" and "没有画面" in by_t[8.1]["issues"][0], by_t
    assert by_t[7.8]["status"] == by_t[7.9]["status"] == "pass"
    assert set(posters) == {7.8, 7.9}

    # run_scan 那一层：cover_poster 抛 NoFrameAt → 换成 NoFrame，整趟照样落记录
    def late_poster(spec, src, out, logo, *, at, dest, page):
        if at > 7.95:
            raise clip.NoFrameAt(f"源片在 {at} 秒没有画面")
        from PIL import Image  # noqa: PLC0415
        Image.new("RGB", scan.CANVAS, (30, 30, 30)).save(dest)
        return dest

    class Clip:
        SOURCE_FMT = "fmt"
        NoFrameAt = clip.NoFrameAt
        cover_poster = staticmethod(late_poster)
        yt_download = staticmethod(lambda url, dest, fmt, spec: src)
        probe_video_duration = staticmethod(lambda _s: 8.3)   # 故意报长：逼它撞上
        _logo_filter = staticmethod(lambda *a: "")

        @staticmethod
        def probe_duration(_s):
            raise AssertionError("扫描按容器时长（最长那条流）剔片尾了——要按视频流")

        @staticmethod
        def canvas_page():
            import contextlib  # noqa: PLC0415
            return contextlib.nullcontext("page")

    monkeypatch.setattr(scan, "audit_poster", audit)
    outdir = tmp_path / "demo"
    outdir.mkdir()
    spec = {"slug": "demo", "url": "u",
            "cover": {"frame_at": 7.8, "scan_window": [7.8, 8.2], "scan_step": 0.2}}
    assert scan.run_scan(spec, outdir, Clip, keep_source=True) == 0
    record = json.loads((outdir / scan.RECORD_NAME).read_text(encoding="utf-8"))
    status = {e["frame_at"]: e["status"] for e in record["candidates"]}
    assert status == {7.8: "pass", 8.0: "fail", 8.2: "fail"}, status
    assert record["passing"] == [7.8]


def test_check命令对账红了非零(tmp_path, monkeypatch, capsys):
    spec = {"slug": "demo", "url": "u", "cover": {"frame_at": 7.0}}
    outdir = tmp_path / "demo"
    outdir.mkdir()
    entries = [{"frame_at": 2.0, "status": "pass", "issues": [], "face": _face(90), "margin": 2}]
    (outdir / scan.RECORD_NAME).write_text(json.dumps(_record(spec, entries)), encoding="utf-8")
    spec_path = tmp_path / "demo.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    monkeypatch.setattr(scan, "OUTDIR", tmp_path)
    assert scan.main(["--check", "--spec", str(spec_path)]) == 1
    assert "没扫过" in capsys.readouterr().out
    # --report：mode=cover 红着收尾时把排名印在错误旁边（artifact 沙箱里下不下来）
    assert scan.main(["--report", "--spec", str(spec_path)]) == 0
    out = capsys.readouterr().out
    assert "过闸 1 格" in out and "余量最大的是 2 秒" in out, out
    (outdir / scan.RECORD_NAME).unlink()
    assert scan.main(["--check", "--spec", str(spec_path)]) == 0


def test_越过片尾不管ffmpeg退出码是几都记成没画面_别的错照样抛(tmp_path, monkeypatch):
    """CI（run 36315327779）：runner 上那版 ffmpeg 越过视频流末尾是**退出码 234**
    （编码器一帧没收到就打不开），不是本地那版的「退出码 0、不出文件」——
    `check=True` 让它炸成 CalledProcessError，扫描那一格没被记成「没有画面」。
    判据按「t 是不是越过了视频流末尾」认，不按退出码认；没越过的失败照原样抛。"""
    import tools.build_interview_clip as clip  # noqa: PLC0415

    def fake_run(args, **_kw):
        return subprocess.CompletedProcess(args, 234, "", "Error while opening encoder")

    monkeypatch.setattr(clip.subprocess, "run", fake_run)
    monkeypatch.setattr(clip, "probe_video_duration", lambda _src: 8.0)
    src = tmp_path / "src.mp4"
    src.write_bytes(b"")
    with pytest.raises(clip.NoFrameAt, match="没有画面"):
        clip.cover_poster({"cover": {"frame_at": 8.1}}, src, tmp_path,
                          at=8.1, dest=tmp_path / "late.jpg")
    with pytest.raises(subprocess.CalledProcessError):
        clip.cover_poster({"cover": {"frame_at": 3.0}}, src, tmp_path,
                          at=3.0, dest=tmp_path / "mid.jpg")
