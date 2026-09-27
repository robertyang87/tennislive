"""runner 的准备工作（Chromium / apt / ffmpeg）和渲染耗时台账的判据。

来路是 2026-09-27 的全库 review 量出来的四笔 runner 开销，**每一笔都不吭声**：

1. **Chromium 缓存 09-15 起每趟重装**。键是 `hashFiles('pyproject.toml')`，
   pyproject 写 `playwright>=1.40`、08-08 之后没动过，主键永远命中旧缓存
   （chromium-1234）；pip 装上的新 playwright 要 1243，launch 探针落空、每趟
   重下两个浏览器还跑一遍 `--with-deps` 的 apt——而主键命中时 post 步骤
   「not saving cache」，缓存永远修不好自己（run 36284220097）。「装 Chromium」
   09-15 前中位 1s（n=10），之后 18s（n=189）；解说片「安装 Chromium」9s → 17s。
2. **apt 缓存（#452）从来没命中过**：84 份日志「缓存命中：零网络」0 次。
   render 存不上（root 的 `lock`/`partial` 让 runner 用户的 tar 读不动），
   probe 存得上的是 243 字节的空目录，下一趟 render 恢复的正是它。
3. **`ensure_ffmpeg` 每趟 30 秒**（p90 31s），下载只占 1.3 秒，其余是把
   518 MB 的包整个解三遍（两遍 `tar -tJf` 找名字、一遍取文件）。
4. **耗时台账把 4 个 worker 的累加当墙钟**：「分段编码」占 63%、三项加起来
   超过 100%，真实墙钟只占 18%；比分板蒙版那次逐段扫描（中位 20 秒）一直
   没计时。

判据都**自己推导、不维护名单**：扫全部工作流，以后多一条线会自动被管到。
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SCRIPT = ROOT / "tools" / "ci_apt_install.sh"


def _jobs():
    """[(文件名, job 名, [step...])]，按文件名排序。"""
    import yaml  # noqa: PLC0415

    out = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job_name, job in (spec.get("jobs") or {}).items():
            out.append((path.name, job_name, list(job.get("steps") or [])))
    return out


def _code(run) -> str:
    """run 脚本去掉整行注释——注释正是这个仓库记教训的地方，连它一起扫会把
    「把坑记下来」判成「又踩了这个坑」（同一个错这个仓库犯过五次）。"""
    return "\n".join(ln for ln in str(run or "").splitlines()
                     if not ln.lstrip().startswith("#"))


def _paths(step) -> str:
    return str(((step.get("with") or {}).get("path")) or "")


# ---------------------------------------------------------------------------
# 1. Chromium 缓存键
# ---------------------------------------------------------------------------

def test_Chromium缓存键跟着装上的playwright版本走不跟pyproject():
    """键钉在 `hashFiles('pyproject.toml')` 上，pyproject 不动主键就永远命中——
    playwright 自己升了版本，缓存里的浏览器对不上，每趟重下 300 MB，而主键
    命中时 actions/cache 不回写，**这份缓存永远修不好自己**。

    判据钉四头：键里不许有 hashFiles；键要引用前面某一步读出来的 playwright
    版本；那一步的 `if` 和缓存那步一样（跳过了版本就是空的，键退化成一格
    固定的旧键）；读版本之前 playwright 已经 pip 装上（不然那一步当场红）。
    """
    checked = []
    for fname, job, steps in _jobs():
        for i, step in enumerate(steps):
            if not str(step.get("uses", "")).startswith("actions/cache"):
                continue
            if "ms-playwright" not in _paths(step):
                continue
            where = f"{fname}::{job}「{step.get('name')}」"
            key = str(step["with"].get("key", ""))
            assert "hashFiles" not in key, (
                f"{where} 的 Chromium 缓存键还是按文件哈希算的：{key}——"
                "决定装哪个浏览器的只有 playwright 的版本")
            m = re.search(r"steps\.([\w-]+)\.outputs\.([\w-]+)", key)
            assert m, f"{where} 的键没引用任何一步读出来的版本：{key}"
            sid = m.group(1)
            before = steps[:i]
            src = [s for s in before if s.get("id") == sid]
            assert src, f"{where} 的键引用 steps.{sid}，但它前面没有 id 为 {sid} 的步骤"
            ver = src[0]
            assert re.search(r"version\(\s*[\"']playwright[\"']\s*\)", _code(ver.get("run"))), (
                f"{where} 引用的 {sid} 那一步没读装上的 playwright 版本")
            assert ver.get("if") == step.get("if"), (
                f"{where} 和读版本那一步的 if 不一样（{ver.get('if')!r} vs "
                f"{step.get('if')!r}）——读版本被跳过时键退化成一格固定的旧键")
            upto = before[:before.index(ver) + 1]
            installs = [s for s in upto
                        if re.search(r"pip install[^\n]*(webrender|playwright)",
                                     _code(s.get("run")))]
            assert installs, (
                f"{where}：读版本那一步之前没有 pip 装 playwright 的步骤——"
                "`importlib.metadata.version` 会当场报 PackageNotFoundError")
            restore = str(step["with"].get("restore-keys", "")).strip()
            assert restore and key.startswith(restore), (
                f"{where} 没有（或对不上键的）restore-keys——换版本那一趟要靠它退到"
                "上一份，`playwright install` 才只补差的那一版")
            checked.append(where)
    assert len(checked) >= 5, f"只扫到 {len(checked)} 处 Chromium 缓存，判据的主语像是没了：{checked}"


# ---------------------------------------------------------------------------
# 2. apt 缓存：restore ＋ 只在摸了网时 save
# ---------------------------------------------------------------------------

_CONSUMER = re.compile(r"(?<![\w-])(apt_install_cached|ensure_ffmpeg)(?![\w-])")


def test_apt缓存只在这趟真下了新包时回写():
    """actions/cache@v4 的 post 自动回写把这份缓存废了两次：

    - probe 那几档只 `ensure_ffmpeg`（静态构建，不碰 apt），目录是空的、存得上，
      243 字节的空缓存挂在滚动键最新那一格，下一趟 render 恢复的正是它；
    - render 摸了网、目录里真有东西，却因为 root 的 `lock`/`partial` 存不上。

    现在拆成 `actions/cache/restore` ＋ 显式 `actions/cache/save`，save 只在
    共享脚本置了 `APT_CACHE_DIRTY` 时跑（它只在「走网络」那条路成功后置位）。
    判据钉三头：apt 目录一律不许再用会自动回写的 `actions/cache@v4`；每个
    restore 都有一个认它 `cache-primary-key` 的 save、条件里认 `APT_CACHE_DIRTY`；
    **每一处调 apt_install_cached / ensure_ffmpeg 的步骤都夹在某一对
    restore 和 save 之间**——save 排在装包之前，这一趟下的包就存不进去。
    """
    restores = 0
    for fname, job, steps in _jobs():
        pairs = []
        for i, step in enumerate(steps):
            if "apt-archives" not in _paths(step):
                continue
            uses = str(step.get("uses", ""))
            where = f"{fname}::{job}「{step.get('name')}」"
            assert uses != "actions/cache@v4", (
                f"{where} 还在用 actions/cache@v4——它的 post 步骤每趟都回写：命中的趟"
                "白传一份，只装 ffmpeg 的趟把空目录存成最新那一格。拆成 restore ＋ save")
            if uses.startswith("actions/cache/restore"):
                sid = step.get("id")
                assert sid, f"{where} 没有 id，save 那一步拿不到它的 cache-primary-key"
                restores += 1
                saves = [
                    j for j, s in enumerate(steps)
                    if j > i and str(s.get("uses", "")).startswith("actions/cache/save")
                    and f"steps.{sid}.outputs.cache-primary-key" in str((s.get("with") or {}).get("key", ""))
                ]
                assert saves, f"{where} 恢复了 apt 缓存，后面却没有认它的 save——缓存永远不更新"
                save = steps[saves[0]]
                cond = str(save.get("if", ""))
                assert "env.APT_CACHE_DIRTY == '1'" in cond, (
                    f"{fname}::{job} 的 apt save 没认 APT_CACHE_DIRTY：{cond!r}——"
                    "每趟都存就又回到「空目录存成最新那一格」")
                assert set(_paths(save).split()) == set(_paths(step).split()), (
                    f"{fname}::{job} 的 apt save 和 restore 缓存的目录不一样")
                pairs.append((i, saves[0]))
        for c, step in enumerate(steps):
            if not _CONSUMER.search(_code(step.get("run"))):
                continue
            assert any(r < c < v for r, v in pairs), (
                f"{fname}::{job}「{step.get('name')}」调了 apt_install_cached/ensure_ffmpeg，"
                "但它不在任何一对 apt 缓存 restore 和 save 之间——要么没恢复缓存，"
                "要么 save 排在它前面、这一趟下的包存不进去")
    assert restores >= 14, f"只扫到 {restores} 处 apt 缓存恢复，判据的主语像是没了"


# ---- 缓存按 ref 隔离：分支上看得见的只有本分支和 main 的那几份 --------------

_RUN_ID = "${{ github.run_id }}"
_COND_KEY = re.compile(
    r"\$\{\{\s*\((?P<cond>.+?)\)\s*&&\s*format\('(?P<fmt>[^']*)',\s*runner\.os\)"
    r"\s*\|\|\s*''\s*\}\}")


def _restore_keys(step) -> list[tuple[str, str | None]]:
    """[(前缀, 条件或 None)]——`${{ (条件) && format('…{0}…', runner.os) || '' }}`
    这种按 mode 开关的一格，按「条件成立时」的样子还原成字面前缀。"""
    out = []
    for line in str((step.get("with") or {}).get("restore-keys") or "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = _COND_KEY.fullmatch(line)
        if m:
            out.append((m.group("fmt").replace("{0}", "${{ runner.os }}"),
                        " ".join(m.group("cond").split())))
        else:
            out.append((line, None))
    return out


def _path_list(step) -> list[str]:
    # actions/cache 的「版本」是**按顺序**拼起来的路径列表再哈希——顺序不同、
    # 前缀再对也匹配不上（不报错，只是永远 miss）
    return [p.strip() for p in _paths(step).splitlines() if p.strip()]


def _apt_packages(steps) -> set[str]:
    pkgs: set[str] = set()
    for s in steps:
        for m in re.finditer(r"(?<![\w-])apt_install_cached\s+([^\n;&|]+)", _code(s.get("run"))):
            pkgs |= set(m.group(1).split())
    return pkgs


def _apt_restores():
    for fname, job, steps in _jobs():
        for step in steps:
            if ("apt-archives" in _paths(step)
                    and str(step.get("uses", "")).startswith("actions/cache/restore")):
                yield fname, job, steps, step


def test_装字体的apt缓存都能退到CI在main上存的那份():
    """各条线的 apt 缓存键各是各的前缀（`…-ffmpeg-fonts-v3-` / `…-explainer-v2-`…），
    而 **actions/cache 按 ref 隔离**：分支上的 run 只看得见本分支和 main 存的那几份。
    render / 采访 / 解说都在会话分支上跑，存进的是各自的分支——**每条新分支的第一趟
    都是冷的**，照样摸那个会抽风的镜像。

    main 上真有一份完整的只有 CI：`ci.yml` 每次合并都在 main 上跑，装的是
    cjk ＋ core ＋ emoji。所以凡是装的字体是它子集的那一步，restore-keys 里要有
    CI 那个前缀，而且缓存目录的**顺序**要和 CI 一模一样（版本号按顺序哈希，
    顺序一换就永远 miss，不报错）。

    按 mode 开关的那一格（match-reel 只给 render / cover 加：probe、narration 不装
    字体，捞一百来 MB 回来白下）——开关的条件必须和装字体那一步的 `if` 一字不差，
    差一点就是「该退的时候不退」或者「白下」。
    """
    ci = [(steps, step) for fname, _job, steps, step in _apt_restores() if fname == "ci.yml"]
    assert len(ci) == 1, f"ci.yml 里应该恰好有一处 apt 缓存恢复，找到 {len(ci)} 处"
    ci_steps, ci_step = ci[0]
    ci_key = str(ci_step["with"]["key"])
    assert ci_key.endswith(_RUN_ID), f"CI 的 apt 缓存键不是滚动键：{ci_key}"
    ci_prefix = ci_key[: -len(_RUN_ID)]
    ci_pkgs = _apt_packages(ci_steps)
    ci_paths = _path_list(ci_step)
    assert ci_pkgs, "ci.yml 那个 job 一个包都不装了？判据的主语没了"

    checked = []
    for fname, job, steps, step in _apt_restores():
        if fname == "ci.yml":
            continue
        pkgs = _apt_packages(steps)
        if not pkgs or not pkgs <= ci_pkgs:
            continue
        where = f"{fname}::{job}「{step.get('name')}」"
        keys = _restore_keys(step)
        hit = [(p, cond) for p, cond in keys if p == ci_prefix]
        assert hit, (
            f"{where} 装的 {sorted(pkgs)} 是 CI 那份的子集，restore-keys 却退不到 "
            f"{ci_prefix}——每条新分支的第一趟都是冷缓存：{keys}")
        assert keys[0][0] != ci_prefix, (
            f"{where} 的第一格是 CI 的前缀——本线自己存的（可能多装了包）要排在前面")
        assert _path_list(step) == ci_paths, (
            f"{where} 缓存的目录（或顺序）和 CI 不一样：{_path_list(step)} vs {ci_paths}"
            "——版本号对不上，退到 CI 那一格永远 miss")
        cond = hit[0][1]
        if cond is not None:
            installers = {" ".join(str(s.get("if") or "").split()) for s in steps
                          if re.search(r"(?<![\w-])apt_install_cached\s", _code(s.get("run")))}
            assert installers == {cond}, (
                f"{where} 退到 CI 那一格的开关条件 {cond!r} 和装字体那一步的 if "
                f"{sorted(installers)} 不一样")
        checked.append(where)
    assert len(checked) >= 6, f"只扫到 {len(checked)} 处装字体的 apt 缓存：{checked}"


# 这些前缀在 **main** 上存着 probe 那几趟的空壳（`Cache Size: ~0 MB (243 B)`，
# run 36276804834 / 36216426100）。空壳每被恢复一次就续一次命（7 天没人读才会被
# 清），而按前缀退的时候它排在所有后面的回退键前面——认这个前缀，就永远捞回空壳。
# **只许加不许减**：再发现一个被污染的前缀，加进来、换新版本号。
_POLLUTED_APT_PREFIXES = frozenset({
    "apt-pkgs-${{ runner.os }}-24.04-ffmpeg-fonts-v2-",
})


def test_apt缓存不许再认被空壳污染的前缀():
    """match-reel 的 v2 前缀在 main 上只有 probe 存的空目录：会话分支上每条新分支
    的第一趟 render 按前缀退到 main，捞回来的就是它，排在后面的 CI 回退键轮不到。
    换成 v3 之后，这条判据防的是有人照着旧注释把 v2 抄回来。"""
    assert all(p.startswith("apt-pkgs-") and p.endswith("-") for p in _POLLUTED_APT_PREFIXES)
    seen = 0
    for fname, job, _steps, step in _apt_restores():
        seen += 1
        key = str(step["with"].get("key", ""))
        for prefix in _POLLUTED_APT_PREFIXES:
            assert not key.startswith(prefix), (
                f"{fname}::{job} 的 apt 缓存键又用回了被空壳污染的前缀 {prefix}")
            assert all(p != prefix for p, _c in _restore_keys(step)), (
                f"{fname}::{job} 的 restore-keys 认 {prefix}——main 上那个前缀下只有"
                "243 字节的空壳，捞回来就是冷缓存")
    assert seen >= 14, f"只扫到 {seen} 处 apt 缓存恢复，判据的主语像是没了"


# ---------------------------------------------------------------------------
# 3. 共享脚本：交还所有权、标脏、--no-download（真跑一遍，拿桩代替 sudo/apt）
# ---------------------------------------------------------------------------

def _stub_bin(tmp: Path) -> Path:
    b = tmp / "bin"
    b.mkdir()
    stubs = {
        "sudo": 'exec "$@"',
        # --no-download 那一次（缓存快路）按 CACHED_RC 返回；update 总成功；
        # 走网络的 install 按 NET_RC 返回
        "apt-get": ('echo "apt-get $*" >> "$STUB_LOG"\n'
                    'case " $* " in *" --no-download "*) exit "${CACHED_RC:-100}";; esac\n'
                    'case " $* " in *" update "*) exit 0;; esac\n'
                    'exit "${NET_RC:-0}"'),
        "chown": 'echo "chown $*" >> "$STUB_LOG"',
        "dpkg": "exit 0",
        "sleep": "exit 0",
    }
    for name, body in stubs.items():
        p = b / name
        p.write_text("#!/bin/bash\n" + body + "\n", encoding="utf-8")
        p.chmod(0o755)
    return b


def _run_apt(tmp: Path, **env) -> tuple[int, str, str]:
    stub = _stub_bin(tmp)
    log = tmp / "stub.log"
    ghenv = tmp / "github_env"
    ghenv.write_text("", encoding="utf-8")
    e = dict(os.environ, PATH=f"{stub}:{os.environ['PATH']}", STUB_LOG=str(log),
             GITHUB_ENV=str(ghenv), APT_CACHE_DIR=str(tmp / "archives"),
             APT_LISTS_DIR=str(tmp / "lists"), **env)
    proc = subprocess.run(
        ["bash", "-c", f"source {SCRIPT}; apt_install_cached fonts-demo"],
        env=e, capture_output=True, text=True, timeout=60)
    return proc.returncode, log.read_text(encoding="utf-8") if log.exists() else "", \
        ghenv.read_text(encoding="utf-8")


@pytest.mark.skipif(not shutil.which("bash"), reason="要 bash")
def test_apt共享脚本命中不标脏_走网络才标脏_每次都交还目录所有权(tmp_path):
    """三件事各钉一个方向：

    - **命中**（`--no-download` 那一次就装上了）：不置 `APT_CACHE_DIRTY`——
      save 跳过，不再把一模一样的缓存重传一遍去挤 10 GB 的池子；
    - **走网络**：置 `APT_CACHE_DIRTY=1`（写进 `$GITHUB_ENV`，后面的 save 读它）；
    - **不管命中还是走网络**，apt 跑完都要把两个目录 `chown -R` 还给调用者——
      sudo 留下的 root `lock`/`partial` 正是 render 那趟存不上的原因
      （`tar: …/apt-archives/lock: Cannot open: Permission denied`）。

    缓存快路必须带 `--no-download`：不带它，「本地安装」会悄悄去下缺的
    .deb（run 32290505356 卡满 12 分钟），下了新包却没走「走网络」那条路，
    标脏就不准，新下的包永远存不进去。
    """
    who = f"{os.getuid()}:{os.getgid()}"

    hit = tmp_path / "hit"
    hit.mkdir()
    rc, log, ghenv = _run_apt(hit, CACHED_RC="0")
    assert rc == 0, log
    assert "--no-download" in log.splitlines()[0], (
        f"缓存快路没带 --no-download，它会在「本地安装」的名义下悄悄下载：\n{log}")
    assert "update" not in log, f"命中了还去 apt-get update：\n{log}"
    assert "APT_CACHE_DIRTY" not in ghenv, "命中缓存也标了脏——save 会把同一份缓存再传一遍"
    assert f"chown -R {who}" in log and str(hit / "archives") in log \
        and str(hit / "lists") in log, f"命中那条路没把目录所有权交还：\n{log}"

    miss = tmp_path / "miss"
    miss.mkdir()
    rc, log, ghenv = _run_apt(miss, CACHED_RC="100", NET_RC="0")
    assert rc == 0, log
    assert "APT_CACHE_DIRTY=1" in ghenv, (
        f"走了网络却没标脏——save 那一步不会跑，这趟下的包白下了：\n{log}")
    lines = log.splitlines()
    last_apt = max(i for i, ln in enumerate(lines) if ln.startswith("apt-get"))
    assert any(ln.startswith(f"chown -R {who}") for ln in lines[last_apt:]), (
        f"走网络那条路 apt 跑完没交还所有权——root 的 lock/partial 让 save 存不上：\n{log}")

    fail = tmp_path / "fail"
    fail.mkdir()
    rc, log, ghenv = _run_apt(fail, CACHED_RC="100", NET_RC="100")
    assert rc != 0, "网络那条路装失败了，函数却返回 0"
    assert "APT_CACHE_DIRTY" not in ghenv, "装失败的那趟也标了脏"
    assert f"chown -R {who}" in log, "装失败也要交还所有权——同一个 job 后面可能还有一步会回写"


# ---------------------------------------------------------------------------
# 4. ensure_ffmpeg：成员名算死、--occurrence 拿够就停、xz 多线程
# ---------------------------------------------------------------------------

_TOP = "ffmpeg-master-latest-linux64-gpl"


def _fake_build(tmp: Path, top: str) -> Path:
    """一个和 BtbN 同样排法的小包：presets/ doc/ bin/ffmpeg bin/ffprobe bin/ffplay。"""
    src = tmp / "src"
    for rel, body in (("presets/libvpx-720p.ffpreset", "x\n"),
                      ("doc/ffmpeg.html", "<html></html>\n"),
                      ("bin/ffmpeg", "#!/bin/sh\necho 'ffmpeg version test'\n"),
                      ("bin/ffprobe", "#!/bin/sh\necho 'ffprobe version test'\n"),
                      ("bin/ffplay", "#!/bin/sh\necho 'ffplay version test'\n")):
        p = src / top / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        p.chmod(0o755)
    archive = tmp / "ff.tar.xz"
    with tarfile.open(archive, "w:xz") as tar:
        for rel in ("presets/libvpx-720p.ffpreset", "doc/ffmpeg.html",
                    "bin/ffmpeg", "bin/ffprobe", "bin/ffplay"):
            tar.add(src / top / rel, arcname=f"{top}/{rel}")
    return archive


def _logging_wrappers(tmp: Path) -> tuple[Path, Path]:
    """tar / xz 换成「记下参数再调真的」——看得见它到底把整包过了几遍。"""
    b = tmp / "wrap"
    b.mkdir()
    log = tmp / "calls.log"
    for name in ("tar", "xz"):
        real = shutil.which(name)
        if not real:
            pytest.skip(f"这台机器没有 {name}")
        p = b / name
        p.write_text(f'#!/bin/bash\necho "{name} $*" >> "{log}"\nexec {real} "$@"\n',
                     encoding="utf-8")
        p.chmod(0o755)
    return b, log


def _extract(tmp: Path, archive: Path, top: str) -> tuple[subprocess.CompletedProcess, str, Path]:
    wrap, log = _logging_wrappers(tmp)
    dest = tmp / "dest"
    dest.mkdir()
    proc = subprocess.run(
        ["bash", "-c", f"set -euo pipefail; source {SCRIPT}; "
                       f"_ffmpeg_extract {archive} {dest} {top}"],
        env=dict(os.environ, PATH=f"{wrap}:{os.environ['PATH']}",
                 APT_CACHE_DIR=str(tmp / "a"), APT_LISTS_DIR=str(tmp / "l")),
        capture_output=True, text=True, timeout=60)
    return proc, log.read_text(encoding="utf-8") if log.exists() else "", dest


@pytest.mark.skipif(not shutil.which("bash"), reason="要 bash")
def test_ensure_ffmpeg只解两个成员不许整包过好几遍(tmp_path):
    """这一步原来每趟 30 秒，下载只占 1.3 秒：两遍 `tar -tJf` 把 518 MB 整包
    解完找名字，再整包解一遍取两个文件。沙箱实测同一个包 99.1s → 15.0s。

    判据钉三头：
    - **快路一遍都不许列**（`tar -t`），成员名按包名算死；用 `--occurrence=1`
      两个拿到就停（排在最后的 ffplay 176 MB 不用解）；xz 走 `-T0` 多线程；
    - 取出来的两个真能跑、ffplay 没被解出来；
    - 包的结构变了（顶层目录改名）时退回老办法，但**只列一遍**，照样取对。
    """
    fast = tmp_path / "fast"
    fast.mkdir()
    proc, calls, dest = _extract(fast, _fake_build(fast, _TOP), _TOP)
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout.split()
    assert out == [str(dest / _TOP / "bin/ffmpeg"), str(dest / _TOP / "bin/ffprobe")], proc.stdout
    assert not (dest / _TOP / "bin/ffplay").exists(), "ffplay 也被解出来了——只要两个"
    tar_calls = [ln for ln in calls.splitlines() if ln.startswith("tar ")]
    assert not any(re.search(r"(^| )-\w*t", ln[4:]) for ln in tar_calls), (
        f"快路还在整包列一遍找名字：\n{calls}")
    assert any("--occurrence=1" in ln for ln in tar_calls), (
        f"快路的 tar 没带 --occurrence=1——拿够了也会把后面的 176 MB 解完：\n{calls}")
    assert any(re.search(r"^xz .*-T0", ln) for ln in calls.splitlines()), (
        f"xz 没走多线程（这个包是 22 个独立块，能并行解）：\n{calls}")

    moved = tmp_path / "moved"
    moved.mkdir()
    proc, calls, dest = _extract(moved, _fake_build(moved, "ffmpeg-n8.0-renamed"), _TOP)
    assert proc.returncode == 0, f"顶层目录改了名就取不出来了：{proc.stderr}"
    assert proc.stdout.split() == [str(dest / "ffmpeg-n8.0-renamed/bin/ffmpeg"),
                                   str(dest / "ffmpeg-n8.0-renamed/bin/ffprobe")]
    listings = [ln for ln in calls.splitlines()
                if ln.startswith("tar ") and re.search(r" -\w*t", ln)]
    assert len(listings) == 1, f"退回老办法时列了 {len(listings)} 遍，一遍就够：\n{calls}"


# ---------------------------------------------------------------------------
# 5. 耗时台账：墙钟和并行累加分开
# ---------------------------------------------------------------------------

def _timing():
    sys.path.insert(0, str(ROOT / "tools"))
    import pipeline_timing  # noqa: PLC0415
    return pipeline_timing


def test_耗时台账按墙钟排_并行累加不许冒充最慢那一步():
    """「分段编码」是 4 个 worker 的线程池，原来每段各记一行、台账当它是这一步
    的耗时：最近 40 条成功 timing.json 里它占整趟墙钟的 63%，三项加起来过 100%，
    而 14 份日志按时间戳重建的真实墙钟只有 18%——大头是烧字幕＋成片（51%），
    还有 8% 根本没有 stage 包着（比分板蒙版的逐段扫描）。

    判据钉三头：并行那几行不进墙钟、不进「哪一步最慢」；没被 stage 包住的时间
    以「（未计时）」上榜；schema 1 的旧行里「分段编码」同样按累加处理。
    """
    pt = _timing()
    par = "分段编码" + pt.PARALLEL_MARK
    stages = [("下载源片", 10.0), ("TTS 合成", 5.0), ("比分板蒙版", 20.0)]
    stages += [(par, 38.0)] * 4 + [("分段编码", 42.0), ("拼接", 32.0), ("烧字幕+成片", 120.0)]
    row = pt.build_record(pipeline="match-reel", slug="demo", mode="render",
                          outcome="success", stages=stages, elapsed_seconds=240.0)
    assert row["schema"] >= 2
    assert row["parallel_stages"] == [par]
    assert row["stage_seconds"][par] == 152.0, "每段那几行的原始粒度要留着"
    assert row["untimed_seconds"] == pytest.approx(240 - (10 + 5 + 20 + 42 + 32 + 120)), (
        "没被 stage 包住的时间没算出来——下一次漏包一段扫描还是看不见")

    legacy = {"schema": 1, "slug": "old", "outcome": "success", "elapsed_seconds": 240.0,
              "stage_seconds": {"分段编码": 150.0, "烧字幕+成片": 120.0, "拼接": 32.0}}
    report = pt.summarize([row, legacy])
    ranked = report.split("哪一步最慢", 1)[1].split("并行累加", 1)[0]
    first = next(ln for ln in ranked.splitlines() if re.match(r"\s+\d", ln))
    assert "烧字幕+成片" in first, f"最慢那一步应该是烧字幕+成片（墙钟 120s）：\n{report}"
    assert par not in ranked, f"并行累加混进了「哪一步最慢」：\n{report}"
    assert "分段编码" in ranked, "新行的墙钟「分段编码」应该在榜上"
    assert pt.UNTIMED in ranked, f"没被 stage 包住的时间没上榜：\n{report}"
    tail = report.split("并行累加", 1)[1]
    assert par in tail and "分段编码" in tail, (
        f"并行累加要单列出来（新行的 {par}、旧行的「分段编码」）：\n{report}")
    legacy_only = pt.summarize([legacy]).split("哪一步最慢", 1)[1].split("并行累加", 1)[0]
    assert "分段编码" not in legacy_only, "schema 1 的「分段编码」是累加，不许当墙钟排"

    table = pt.stage_table(stages)
    shares = [float(x) for x in re.findall(r"s\s+([\d.]+)%", table)]
    assert shares and abs(sum(shares) - 100) < 0.6, (
        f"report_timings 那张表的份额加起来不是 100%（{sum(shares):.1f}%）：\n{table}")
    assert par in table and "不计份额" in table


def _render_fn() -> tuple[ast.Module, ast.FunctionDef]:
    tree = ast.parse((ROOT / "tools" / "build_match_reel.py").read_text(encoding="utf-8"))
    return tree, next(n for n in tree.body
                      if isinstance(n, ast.FunctionDef) and n.name == "render")


def _stage_names(node: ast.With) -> list[str]:
    names = []
    for item in node.items:
        for sub in ast.walk(item.context_expr):
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                    and sub.func.id == "stage" and sub.args
                    and isinstance(sub.args[0], ast.Constant)):
                names.append(sub.args[0].value)
    return names


def test_渲染的计时包住比分板蒙版和分段编码的墙钟():
    """位置判据（只测台账的行为拦不住 render 里包错地方）：

    - 四种转播的 `resolve_*_masks` 都在 `with stage("比分板蒙版")` 里——原来
      没包，中位 20 秒报表上看不见，死在这儿时 `last_stage` 指着上一步 TTS；
    - 线程池在 `with stage("分段编码")` 里（墙钟）；
    - 每段那一行用 `SEGMENT_STAGE`，它带着并行记号。
    """
    tree, render = _render_fn()
    mask_calls = {"resolve_masks", "resolve_atp_masks", "resolve_wta_masks",
                  "resolve_itf_masks", "resolve_laver_masks", "resolve_board_insets"}
    covered, pool_in_wall = set(), False
    for node in ast.walk(render):
        if not isinstance(node, ast.With):
            continue
        names = _stage_names(node)
        inner = {c.func.id for c in ast.walk(node) if isinstance(c, ast.Call)
                 and isinstance(c.func, ast.Name)}
        if "比分板蒙版" in names:
            covered |= inner & mask_calls
        if "分段编码" in names and "ThreadPoolExecutor" in inner:
            pool_in_wall = True
    assert covered == mask_calls, (
        f"这些扫板调用没被 stage(\"比分板蒙版\") 包住：{sorted(mask_calls - covered)}")
    assert pool_in_wall, "分段编码的线程池外面没有记墙钟的 stage(\"分段编码\")"

    sys.path.insert(0, str(ROOT / "tools"))
    pt = _timing()
    src = (ROOT / "tools" / "build_match_reel.py").read_text(encoding="utf-8")
    for fn in ("cut_segment", "cut_still_segment"):
        body = src[src.index(f"def {fn}("):]
        body = body[:body.index("\ndef ", 1)]
        assert "with stage(SEGMENT_STAGE)" in body, f"{fn} 每段那一行没用 SEGMENT_STAGE"
    seg = re.search(r'^SEGMENT_STAGE = "([^"]+)"( \+ PARALLEL_MARK)?$', src, re.M)
    assert seg, "找不到 SEGMENT_STAGE 的定义"
    value = seg.group(1) + (pt.PARALLEL_MARK if seg.group(2) else "")
    assert pt.is_parallel_stage(value), (
        f"SEGMENT_STAGE={value!r} 不带并行记号——4 个 worker 的累加又会冒充墙钟")
