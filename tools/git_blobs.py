#!/usr/bin/env python3
"""按 git 对象读别的 ref 上的文件——稀疏检出、部分克隆、浅克隆里都能用。

来路（2026-09-27，P6）：「同一条源片别 probe 两遍」要读的东西都不在工作区里——
编排器的检出是稀疏的（`output/` 不在），probe 那一步要看 `origin/main` 上的
认领，会话要翻别人分支上的草稿和封面。工作区里没有 ≠ 仓库里没有
（CLAUDE.md「空结果 ≠ 不存在」），所以一律按对象读：

- `git ls-tree` 读的是对象库，**不受稀疏检出影响**（match-reel.yml「算出目录」
  那一步早就这么反查日期目录）
- runner 上的检出是 `--filter=blob:none` 的部分克隆：缺的 blob 会被 git 一个一个
  懒取，一个一个就是一个个来回。`prefetch` 把要读的那批 oid 一次取回——
  命令行和 git 自己的 `promisor_remote_get_direct` 一字不差，是它懒取时用的
  同一条路，只是一次给齐

只用标准库和 git；不许 `|| true` 式吞错——读不出来要说读不出来。
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

#: 工作流里提交用的身份（`test_提交产物的工作流一律用Claude的身份` 那条口径）。
BOT_ENV = {
    "GIT_AUTHOR_NAME": "Claude", "GIT_AUTHOR_EMAIL": "noreply@anthropic.com",
    "GIT_COMMITTER_NAME": "Claude", "GIT_COMMITTER_EMAIL": "noreply@anthropic.com",
}


class GitError(RuntimeError):
    pass


def git(*args: str, cwd: Path | str | None = None, input: bytes | str | None = None,
        env: dict | None = None, check: bool = True, text: bool = True) -> str | bytes:
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    if isinstance(input, str) and not text:
        input = input.encode()
    res = subprocess.run(["git", *args], cwd=cwd, input=input, env=full_env,
                         capture_output=True, text=text)
    if check and res.returncode != 0:
        err = res.stderr if text else res.stderr.decode(errors="replace")
        raise GitError(f"git {' '.join(args)} 失败（{res.returncode}）：{err.strip()}")
    return res.stdout


def rev(ref: str, cwd: Path | str | None = None) -> str | None:
    out = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
                         cwd=cwd, capture_output=True, text=True)
    return out.stdout.strip() or None


def ls_tree(ref: str, pathspecs: list[str], cwd: Path | str | None = None) -> list[tuple[str, str]]:
    """`[(oid, path), ...]`，只列 blob。pathspec 为空就一个都不列（别把整棵树列出来）。"""
    if not pathspecs:
        return []
    out = git("ls-tree", "-r", "-z", ref, "--", *pathspecs, cwd=cwd)
    rows = []
    for rec in out.split("\0"):
        if not rec:
            continue
        meta, path = rec.split("\t", 1)
        _mode, typ, oid = meta.split()
        if typ == "blob":
            rows.append((oid, path))
    return rows


def is_shallow(cwd: Path | str | None = None) -> bool:
    out = subprocess.run(["git", "rev-parse", "--is-shallow-repository"],
                         cwd=cwd, capture_output=True, text=True)
    return out.stdout.strip() == "true"


def fetch_ref(remote: str, branch: str, cwd: Path | str | None = None) -> str:
    """把 `<remote>/<branch>` 取到 `refs/remotes/<remote>/<branch>`，返回那个 ref 名。

    ⚠️ 只在**本来就是浅克隆**时带 `--depth=1`：runner 的检出是浅的，要的只是
    最新那一个提交；本地完整克隆里带 `--depth` 会把它变成浅克隆，丢历史。
    """
    ref = f"refs/remotes/{remote}/{branch}"
    depth = ["--depth=1"] if is_shallow(cwd) else []
    git("fetch", "--quiet", *depth, remote, f"+refs/heads/{branch}:{ref}", cwd=cwd)
    return ref


def is_partial_clone(cwd: Path | str | None = None) -> bool:
    out = subprocess.run(["git", "config", "--get", "remote.origin.promisor"],
                         cwd=cwd, capture_output=True, text=True)
    return out.stdout.strip() == "true"


def prefetch(oids: list[str], cwd: Path | str | None = None, remote: str = "origin") -> None:
    """部分克隆里把一批缺的 blob 一次取回；不是部分克隆就什么都不做。

    ⚠️ 取失败**不吞**成功：抛出去，调用方决定是退回逐个懒取还是报错。
    """
    oids = sorted({o for o in oids if o})
    if not oids or not is_partial_clone(cwd):
        return
    git("-c", "fetch.negotiationAlgorithm=noop", "fetch", remote, "--no-tags",
        "--no-write-fetch-head", "--recurse-submodules=no", "--filter=blob:none",
        "--stdin", cwd=cwd, input="\n".join(oids) + "\n")


def read_blobs(oids: list[str], cwd: Path | str | None = None) -> dict[str, bytes]:
    """一个 `cat-file --batch` 进程读完一批 blob；读不到的 oid 不在结果里。"""
    oids = [o for o in dict.fromkeys(oids) if o]
    if not oids:
        return {}
    try:
        prefetch(oids, cwd)
    except GitError as exc:  # 退回 git 自己逐个懒取——慢，但结论不变
        print(f"[git] 批量预取失败，退回逐个懒取：{exc}")
    raw = git("cat-file", "--batch", cwd=cwd, input="\n".join(oids) + "\n", text=False)
    out: dict[str, bytes] = {}
    pos = 0
    for oid in oids:
        nl = raw.index(b"\n", pos)
        header = raw[pos:nl].decode()
        pos = nl + 1
        if header.endswith(" missing"):
            continue
        size = int(header.split()[2])
        out[oid] = raw[pos:pos + size]
        pos += size + 1
    return out


def show(ref: str, path: str, cwd: Path | str | None = None) -> bytes | None:
    """`<ref>:<path>` 的内容；那个 ref 上没有这个文件就是 None。"""
    res = subprocess.run(["git", "cat-file", "blob", f"{ref}:{path}"], cwd=cwd,
                         capture_output=True)
    return res.stdout if res.returncode == 0 else None
