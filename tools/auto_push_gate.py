#!/usr/bin/env python3
"""合进 main 之后，判断该不该自动把这条片子推到微信。

**为什么要有这一步。** 出片和发消息是两次动作：分支上 `push=false` 渲片
（六到十四分钟），合进 main 之后 `mode=push` 只推不渲（实测 **43 秒**，
run 30755226229）。43 秒不值得优化，真正的成本是**人的往返**——渲完、开 PR、
合并、再记得回来点一次 dispatch。这个脚本要省掉的是最后那一下。

**而它是这条链上唯一新增的风险点**，因为微信那条消息发出去收不回来。
所以判据全部收在这儿（不写进 YAML，那儿测不了），六道闸一道都不能省：

1. **路径形状**必须是 `output/<日期>/reel/<slug>/render.json`
2. **L2 不可变凭证**必须与当前 spec、烧片字幕、成片 hash/bytes 以及 Release
   文件大小完全一致；`render.json` 只是流程信号，不能冒充“质检通过”
3. spec 里必须显式写 `"push": {"auto": true}` ——**默认关**，
   和 `mixed_fps` / `silent_source` 一个形状：认领这一步把「想清楚了」和
   「凑合一下」分开
4. 这条**没推过**：`<outdir>/pushed.json` 在仓库里就说明发过了。
   查产物，不查信号——「工作流跑过一次」证明不了消息发出去了。
   ⚠️ 查的是 **`git ls-files`，不是 `test -f`**，两个原因缺一不可：
   ① 这条工作流是稀疏检出的，判断时 `output/` 那一格**还没加回工作区**，
   按文件存不存在判**恒为假**——那道闸等于没装，会重复发；
   ② 只活在工作区里的标记本来就不算数（同一个毛病在复制页上踩过两次：
   日志印着链接、步骤 success、人点开 404）
5. **海报在仓库里**：`<outdir>/poster.jpg` 是推送正文的第一屏，没有它这条
   消息只剩两个按钮，看不出这是谁打谁。见 `wants_auto_push` 里那一段
6. 一趟**最多一条**。一次合并带进来两条成片就一条都不发，报出来让人手动。
   批量自动发微信，错一次就是错一片

判据在 `tests/test_auto_push.py`，每一道都反向验证过。

用法：

    auto_push_gate.py --changed <改动的文件…>     # 列出该发的那一条
    auto_push_gate.py --record <outdir> --run <运行地址>   # 发完记一笔
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from publication_ledger import blocking_attempt, write as write_ledger

# `output/2026-08-03/reel/eala-pegula/render.json`
_RENDER_JSON = re.compile(
    r"^output/(\d{4}-\d\d-\d\d)/reel/([^/]+)/render\.json$")

SPEC_DIR = Path("specs/reels")
MARKER = "pushed.json"
LEDGER_COLUMN = "reel"


class Skip(Exception):
    """这一条不发，而且**要说出为什么**。

    「跳过了」和「压根没看到」在日志里长得一模一样——这个仓库里那类不吭声的
    兜底已经栽过很多次，所以每一条跳过都带着理由打出来。
    """


def candidate(path: str, repo: Path) -> tuple[str, Path]:
    """一个改动的文件 → (slug, outdir)，不合格就 `Skip`。"""
    match = _RENDER_JSON.match(path)
    if not match:
        raise Skip(f"{path}：不是 output/<日期>/reel/<slug>/render.json")
    slug = match.group(2)
    outdir = repo / "output" / match.group(1) / "reel" / slug
    return slug, outdir


def tracked(repo: Path, path: Path) -> bool:
    """这个文件在**仓库**里吗（不是在工作区里）。

    稀疏检出下这两件事会分家：`output/` 那一格不在工作区，`test -f` 一律为假，
    而 `git ls-files` 照样认得——索引里的条目只是被标了 skip-worktree。
    合成仓库上验过两种写法。
    """
    rel = path.relative_to(repo) if path.is_absolute() else path
    done = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--error-unmatch", str(rel)],
        capture_output=True, text=True, check=False)
    return done.returncode == 0


def _spec_paths(repo: Path, slug: str) -> tuple[Path, Path]:
    return (repo / SPEC_DIR / f"{slug}.json",
            repo / SPEC_DIR / f"{slug}.xhs.txt")


def _tracked_bytes(repo: Path, path: Path) -> bytes:
    """读取待发布的仓库版本；兼容 output 未被 sparse checkout 检出的场景。"""
    rel = path.relative_to(repo) if path.is_absolute() else path
    local = repo / rel
    if local.is_file():
        return local.read_bytes()
    proc = subprocess.run(
        ["git", "-C", str(repo), "show", f"HEAD:{rel.as_posix()}"],
        capture_output=True, check=False)
    if proc.returncode:
        raise Skip(f"{rel} 在索引里但读取不到仓库内容")
    return proc.stdout


def _tracked_json(repo: Path, path: Path) -> dict:
    try:
        return json.loads(_tracked_bytes(repo, path))
    except (ValueError, UnicodeDecodeError) as exc:
        raise Skip(f"{path} 不是有效 JSON") from exc


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_qc(repo: Path, slug: str, outdir: Path) -> str:
    """发布前复核：L2 检查、spec、字幕、Release 字节必须是同一份产物。"""
    qc_path = outdir / "qc_attestation.json"
    if not tracked(repo, qc_path):
        raise Skip(f"{slug}：没有受跟踪的 qc_attestation.json；render.json 是渲染信号，"
                   "不能代替 L2 成片质检")
    qc_bytes = _tracked_bytes(repo, qc_path)
    try:
        qc = json.loads(qc_bytes)
    except (ValueError, UnicodeDecodeError) as exc:
        raise Skip(f"{slug}：qc_attestation.json 不是有效 JSON") from exc
    if qc.get("status") != "pass" or qc.get("slug") != slug:
        raise Skip(f"{slug}：QC 凭证状态/slug 不匹配")

    spec_path, _ = _spec_paths(repo, slug)
    if qc.get("spec_sha256") != _sha256_bytes(spec_path.read_bytes()):
        raise Skip(f"{slug}：spec 在质检后发生过变化，必须重新渲染并质检")
    ass_path = outdir / "subtitles.ass"
    if not tracked(repo, ass_path):
        raise Skip(f"{slug}：烧片使用的 subtitles.ass 不在仓库里")
    if qc.get("ass_sha256") != _sha256_bytes(_tracked_bytes(repo, ass_path)):
        raise Skip(f"{slug}：字幕在质检后发生过变化，必须重新渲染并质检")

    render = _tracked_json(repo, outdir / "render.json")
    if render.get("qc_attestation_sha256") != _sha256_bytes(qc_bytes):
        raise Skip(f"{slug}：render.json 指向的不是当前 QC 凭证")
    film_hash = str(qc.get("film_sha256") or "")
    if not film_hash or render.get("film_sha256") != film_hash:
        raise Skip(f"{slug}：render.json 与 QC 不是同一份成片")
    if int(render.get("video_bytes") or 0) != int(qc.get("film_bytes") or 0):
        raise Skip(f"{slug}：Release 文件大小与 QC 成片不一致")
    if not render.get("video_url"):
        raise Skip(f"{slug}：render.json 没有 Release video_url")
    return film_hash


def wants_auto_push(repo: Path, slug: str, outdir: Path) -> None:
    """六道闸，过不了就 `Skip`（带理由）。"""
    # **render.json 必须还在仓库里。** 工作流那头已经用 --diff-filter=AM 滤掉了
    # 删除项，这儿再兜一层：被删的旧产物（清理被顶替的版本）不是新渲完的片子，
    # 它的 spec 往往还写着 auto:true、目录里又没有 pushed.json——不拦的话会
    # 凑成「一次 N 条」把真该发的一起拦死（2026-08-12 差点在 zheng-lanlana
    # 的合并上踩到）。用 tracked() 不用 is_file()：稀疏检出下两者分家。
    if not tracked(repo, outdir / "render.json"):
        raise Skip(f"{slug}：{outdir}/render.json 已不在仓库里"
                   "（这次合并删掉的旧产物），不是新渲的片子")
    spec, copy_path = _spec_paths(repo, slug)
    if not spec.is_file():
        raise Skip(f"{slug}：没有 {spec}，不知道该发什么")
    if not copy_path.is_file():
        raise Skip(f"{slug}：没有文案 {copy_path}")

    # 必须在 auto 开关之前复核产物身份。否则一个只写了 render.json 的失败/半成品
    # 会被当成“已渲完”；而微信消息发出后不可撤回。
    film_hash = validate_qc(repo, slug, outdir)

    # 复用 push_reel 那份读法，别在这儿另解一遍 JSON——「一个数写两处必分叉」。
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from push_reel import POSTER_NAME, push_is_auto  # noqa: PLC0415

    if not push_is_auto(copy_path):
        raise Skip(f"{slug}：spec 里没写 push.auto=true，不自动发"
                   f"（要开：在 {spec.name} 的 push 块里加一行 \"auto\": true）")
    previous = blocking_attempt(repo, LEDGER_COLUMN, slug, film_hash)
    if previous:
        raise Skip(f"{slug}：持久发布账本已有 {previous.get('status')}（"
                   f"{previous.get('at', '时间未记')}，{previous.get('run', '地址未记')}），"
                   "不自动重复发送")
    marker = outdir / MARKER
    if tracked(repo, marker):
        # 稀疏检出下这个文件可能不在工作区，读不到内容也要能拦住——
        # **拦住是主要的，时间和运行地址是加餐**。
        try:
            stamp = json.loads(marker.read_text(encoding="utf-8"))
            when = f"{stamp.get('at', '时间未记')}，{stamp.get('run', '地址未记')}"
        except OSError:
            when = "详情在仓库里，这次没检出"
        raise Skip(f"{slug}：已经推过了（{when}），不重复发")

    # 海报是推送正文的**第一屏**，`push_reel.POSTER_NAME` 那行注释写着
    # 「没有它的推送只有两个按钮，看不出这是谁打谁」。
    #
    # **来路（2026-08-13）**：`archive-media.yml mode=purge` 用 git filter-repo
    # 从全史抹掉了 output/ 下所有 mp4/jpg/jpeg/png/webm/mov（账号所有者认领过的
    # 取舍，17 GB → 789 MB）。副作用是**仓库里一张 poster.jpg 都不剩了**
    # （量过：122 个 reel 目录，122 个都没有）。新渲的片子没事——render 会重新
    # 生成并提交；有风险的是**purge 之前渲好、purge 之后才推**的老片子。
    #
    # **为什么整条不发，而不是发一条没有海报的**：这不是我现挑的口径，是
    # **手动那条路早就定了的**——`match-reel.yml` 的「push 模式先确认成片真的
    # 落地了」那一步写着 `test -f .../poster.jpg || { echo "::error::海报不在
    # ——推送第一屏就是它，没有它只剩两个按钮"; exit 1; }`。同一个问题两条路
    # 给两个答案，就是「一个数写两处必分叉」的政策版：同一条片子手动推被拦下、
    # 自动推却降级发了出去，而微信那条消息收不回来。
    #
    # ⚠️ **`push_reel.py` 那条软降级不算数。** 它确实在缺海报时打了一行
    # `[封面] … 不在`，但那是**发之前最后一步**的一句 print，而且这一趟是绿的
    # ——「没有人会去读一条绿 run 的日志」。更要紧的是它拦不住：
    # `prepare_image_delivery` 遇到 `not sources` 直接返回、`wait_for_images`
    # 遇到 `not pending` 直接返回（都实测过），因为没有海报就没有 `<img>`，
    # **没有链接可探，两道现成的闸一道都走不到**。
    #
    # ⚠️ **查 `tracked()` 不查 `is_file()`**，和上面那道「已经推过」同一个理由，
    # 而且这里更硬：这个脚本跑在工作流的「挑出该自动发的那一条」那一步，
    # 排在 `git sparse-checkout add` **之前**，`output/` 那一格根本不在工作区。
    # 按 `is_file()` 判就是**恒为假**——那不是漏发一条，是**每一条都不发**，
    # 整条自动推送静静地死掉。判据 `test_稀疏检出下海报也要认得出`。
    poster = outdir / POSTER_NAME
    if not tracked(repo, poster):
        raise Skip(
            f"{slug}：{poster} 不在仓库里，不发——推送第一屏就是海报，"
            "没有它这条消息只剩两个按钮，看不出这是谁打谁。\n"
            "        来路：2026-08-13 那次 purge 从全史抹掉了所有 jpg，"
            "purge 之前渲好、之后才推的片子都会撞上这条。\n"
            "        出路：重跑一次 match-reel mode=render（push=false）"
            "把海报渲回来，它会随 PR 进 main，这条闸自然就过了。")


def pick(changed: list[str], repo: Path) -> tuple[str, Path] | None:
    """从这次合并带进来的改动里挑出**唯一**该发的那一条。"""
    picked: list[tuple[str, Path]] = []
    for path in changed:
        try:
            slug, outdir = candidate(path.strip(), repo)
            wants_auto_push(repo, slug, outdir)
        except Skip as why:
            print(f"[跳过] {why}")
            continue
        picked.append((slug, outdir))

    if not picked:
        print("[自动推送] 这次没有该自动发的片子。")
        return None
    if len(picked) > 1:
        names = "、".join(slug for slug, _ in picked)
        print(f"::error::一次带进来 {len(picked)} 条该自动发的片子（{names}），"
              "一条都不发。")
        print("::error::批量自动发微信错一次就是错一片，而消息收不回来——"
              "手动一条一条跑 match-reel mode=push。")
        raise SystemExit(1)
    return picked[0]


def _emit(slug: str, outdir: Path) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    lines = [f"slug={slug}", f"outdir={outdir.as_posix()}", "found=true"]
    print(f"[自动推送] 这次要发：{slug}（{outdir}）")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


def record(outdir: Path, run_url: str, now: str) -> Path:
    """发完记一笔。**这就是「已经发过」的唯一判据**，所以它必须进仓库。"""
    marker = outdir / MARKER
    marker.write_text(json.dumps(
        {"at": now, "run": run_url}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(f"[自动推送] 记下已推送：{marker}")
    return marker


def ledger_status(repo: Path, outdir: Path, status: str, run_url: str, now: str) -> Path:
    slug = outdir.name
    film_hash = validate_qc(repo, slug, outdir)
    if status == "sending":
        previous = blocking_attempt(repo, LEDGER_COLUMN, slug, film_hash)
        if previous:
            raise SystemExit(f"{slug} 已有 {previous.get('status')} 发布记录，禁止盲目重发")
    return write_ledger(repo, LEDGER_COLUMN, slug, film_hash, status=status,
                        run_url=run_url, now=now)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--changed", nargs="*", default=[],
                    help="这次合并改动的文件（仓库相对路径）")
    ap.add_argument("--record", default="",
                    help="发完之后在这个 outdir 里记一笔")
    ap.add_argument("--reserve", default="", help="发送前持久预占 sending")
    ap.add_argument("--uncertain", default="", help="发送失败后记状态不明")
    ap.add_argument("--run", default="", help="--record：这次运行的地址")
    ap.add_argument("--now", default="", help="--record：时间戳")
    ap.add_argument("--repo", default=".", help="仓库根目录")
    args = ap.parse_args(argv)

    repo = Path(args.repo)
    action = args.reserve or args.record or args.uncertain
    if action:
        outdir = Path(action)
        status = "sending" if args.reserve else "sent" if args.record else "uncertain"
        ledger_status(repo, outdir, status, args.run, args.now)
        if args.record:
            record(outdir, args.run, args.now)  # 兼容历史消费者
        return 0

    found = pick(args.changed, repo)
    if found:
        _emit(*found)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
