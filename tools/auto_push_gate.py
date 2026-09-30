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
   文件大小完全一致；`render.json` 只是流程信号，不能冒充“质检通过”。
   凭证钉着渲染输入清单的（2026-09-27 起渲的都钉），另外复核清单、`render.json`
   钉的那一份，并**每次**拿当前 spec 重算渲染投影——不只在 `mode=reattest` 重出的
   凭证上算，见 `_validate_render_inputs`
3. spec 里必须显式写 `"push": {"auto": true}` ——**默认关**，
   和 `mixed_fps` / `silent_source` 一个形状：认领这一步把「想清楚了」和
   「凑合一下」分开。**这是六道里唯一一道 `--forced` 放得宽的**（它问的是
   意图，而表单上勾「强制推送」就是把意图说出口）；其余五道问的是事实，
   `--forced` 一道都拦得住——详见 `wants_auto_push` 的 docstring
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

from publication_ledger import (blocking_attempt, read_receipt_file, receipt_fields,
                                write as write_ledger)

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
    _validate_render_inputs(repo, slug, outdir, qc, render, spec_path)
    return film_hash


def _validate_render_inputs(repo: Path, slug: str, outdir: Path, qc: dict,
                            render: dict, spec_path: Path) -> None:
    """凭证钉着渲染输入清单时，清单本身也要对得上，而且**每次都重算一遍投影**。

    账号所有者 2026-09-27 选了「重核对，不重渲」（`match-reel mode=reattest`，
    `tools/reattest_check.py`）：spec 渲完之后只改注解/推送字段时，不重渲，
    重出一张绑定新 spec 字节、指着同一份成片的凭证。**上面那几道一道都没松**
    （spec / 字幕 / 成片 hash / Release 字节照旧逐一比），这里只**加**：

    - 凭证写了 `render_inputs_sha256`，仓库里那份 `render_inputs.json` 就必须
      是它、`render.json` 钉的也必须是它，而且描述的是同一份成片
    - 清单记的 spec 和凭证记的 spec 不是同一份字节，就**只能**是重核对出的凭证
      （带 `reattest`）——普通渲染里两者是同一个文件先后读两次，不一样就是链被
      动过手脚
    - **不看凭证带不带 `reattest`，一律**拿当前 spec 按同一个口径重算渲染投影和
      认领、和清单逐字节比（评审 2026-09-27：原来只在带 `reattest` 时才算，删掉
      那一段、再把 spec 字节补进凭证，就绕过去了）。普通渲染 spec 没变，这一步
      恒过、不花钱。素材字节这一半这里核不了（这条工作流稀疏检出，不拉
      assets/），它由 runner 那一步现算
    - 清单是**旧口径**写的——`version` 比今天的 `render_inputs.VERSION` 小，或者版本号
      一样、渲染那一刻的口径指纹（`rules`）和今天的 `render_inputs.rules_digest()` 对不上
      （有人往 `RENDER_ANNOTATIONS` / `PUBLISH_FIELDS` 里加了键、没升版本号）：不重算
      （拿新口径比旧清单只会误判），普通渲染退回 spec 字节那道；重核对凭证不认
    - spec 字节**就是**清单记的那一份：投影照算，认领**不**按今天的 `Gate.rule` 重判
      （闸口径收严不进指纹，重判会把没动过的片子卡成不推）；spec 改过才重判
    """
    digest = qc.get("render_inputs_sha256")
    if qc.get("reattest") and not digest:
        raise Skip(f"{slug}：重核对凭证没有钉住渲染输入清单，不认")
    if not digest:
        return
    tools = str(Path(__file__).resolve().parent)
    if tools not in sys.path:            # 多个 --changed 每个都调一次，别往 sys.path 里堆重复项
        sys.path.insert(0, tools)
    import render_inputs  # noqa: PLC0415

    name = render_inputs.MANIFEST_NAME
    if render.get("render_inputs_sha256") != digest:
        raise Skip(f"{slug}：render.json 钉的 {name} 和凭证钉的不是同一份")
    manifest_path = outdir / name
    if not tracked(repo, manifest_path):
        raise Skip(f"{slug}：凭证钉着 {name}，而它不在仓库里")
    manifest_bytes = _tracked_bytes(repo, manifest_path)
    if _sha256_bytes(manifest_bytes) != digest:
        raise Skip(f"{slug}：{name} 在质检后变过")
    try:
        manifest = json.loads(manifest_bytes)
    except (ValueError, UnicodeDecodeError) as exc:
        raise Skip(f"{slug}：{name} 不是有效 JSON") from exc
    if manifest.get("film_sha256") != qc.get("film_sha256"):
        raise Skip(f"{slug}：渲染输入清单描述的不是凭证里那份成片")
    if manifest.get("spec_sha256") != qc.get("spec_sha256") and not qc.get("reattest"):
        raise Skip(f"{slug}：{name} 记的 spec 和凭证记的不是同一份，而凭证不是重核对出的")
    version = manifest.get("version")
    if not render_inputs.same_rules(manifest):
        # 清单是旧口径写的：拿今天的 `project` 重算去比，比出来的差异是口径变了、不是
        # spec 变了（v1→v2 那次「按原顺序比」就会把每一份 v1 清单判成「键的顺序变了」；
        # 往 `RENDER_ANNOTATIONS` 加一个键而没升版本号，也会把改之前渲的每一份判成
        # 「渲染参数变了」——评审 2026-09-27 第三轮复现的，自动链上只印一行 `[跳过]`）。
        # 重核对凭证判不了就不认（`reattest_check` 本来就不给旧清单出凭证）；普通渲染的
        # 凭证照旧由上面那道 spec 字节逐字节钉着——退回的正是加清单之前的那道闸。
        # 要借「改版本号」绕过去就得改清单、重钉三处 sha，而改得动清单的人本来就能把
        # 投影一起改掉——重算防的是「只手搓凭证、没动清单」那一种，这里一点没松。
        if qc.get("reattest"):
            raise Skip(f"{slug}：重核对凭证钉的 {name} 是旧口径（版本 {version!r}、口径指纹 "
                       f"{str(manifest.get('rules'))[:12]}），现在的口径是版本 "
                       f"{render_inputs.VERSION}——判不了，不认")
        if not (isinstance(version, int) and not isinstance(version, bool)
                and 0 < version <= render_inputs.VERSION):
            raise Skip(f"{slug}：{name} 的版本 {version!r} 不认")
        return
    spec_bytes = spec_path.read_bytes()
    # spec 字节**就是**清单记的那一份（普通渲染的常态）：认领不按今天的闸口径重判。
    # 那一刻闸认了才渲得出来；之后哪条分支把某个 `Gate.rule` 收严（`text_str` → `text`）
    # 而口径指纹不变（`GATE_ANNOTATIONS` 故意不进指纹），重判就会把一条 spec 一个字节
    # 没动过的片子判成「认领没了」——自动链只印一行 `[跳过]`，永远不推（复审 fix 轮）。
    # 投影照旧每次重算：清单里的 `spec_sha256` 手搓得动（`_forge(manifest_too=True)`），
    # 投影才是那道拦得住的；而改得动清单的人本来也改得动清单里的认领表，这里不松什么。
    same_spec = _sha256_bytes(spec_bytes) == manifest.get("spec_sha256")
    problems = render_inputs.spec_problems(spec_bytes, manifest, claims=not same_spec)
    if problems:
        what = "重核对凭证不成立" if qc.get("reattest") else "spec 和渲染那一刻的渲染输入对不上"
        raise Skip(f"{slug}：{what}——" + "；".join(problems[:3]))


def wants_auto_push(repo: Path, slug: str, outdir: Path,
                    forced: bool = False) -> None:
    """六道闸，过不了就 `Skip`（带理由）。

    `forced` 是**表单上那个「强制推送」勾选**（`match-reel` 的 `push=true`）。
    它只放宽第 3 道——「spec 里没写 `push.auto=true`」——因为那一道问的是
    **意图**（这条要不要自动发），而人勾了那个框就是把意图说出口了。

    ⚠️ **其余五道一个字都不松，`forced` 也拦得住**，因为它们问的是**事实**：
    成片是不是这一版（`validate_qc`）、账本里有没有记录、`pushed.json` 在不在。
    「已经发过了」是事实不是意图，人再想发一遍也不该由一个勾选来放行——
    要重发就先把 `pushed.json` 从仓库里删掉，**那才是显式的决定**。

    来路（2026-09-09）：在这之前 `push=true` 不是「放宽一道」，是**整套门禁
    连跑都不跑**——`match-reel.yml` 的派发条件写着
    `(inputs.push == 'true' || 门禁说该发)`，前一半为真就直接派 `mode=push`。
    于是 `shelton-alcaraz` 那条已经推送过的片子，每重渲一趟就派一趟注定撞在
    `pushed.json` 上的 push，**每趟都记一条 failure**：近 10 次失败率 80%、
    连续失败 4（微信告警 18:09）。消息一条都没重复发（闸拦住了），可
    `pipeline_health` 的失败率是按 conclusion 算的，于是**闸生效的样子和真出错
    长得一模一样**，而一条常年红的告警会把真正的失败淹掉。

    ⚠️ 更要紧的是那个旁路本身：`--reserve` **不做任何校验**（只写账本），
    而 `mode=push` 那头的预检只查「成片在不在、`pushed.json` 在不在」——
    **不查 L2 凭证**。也就是说 `pushed.json` 恰好不在时（第一次渲、或有人删了
    它），勾一下 `push=true` 就能让一条 QC 没过、成片 hash 对不上的片子一路
    走到 POST。那道门禁的注释自己写着「复用完整发布门禁，不在 YAML 里另写一份
    简化判断」，而 `inputs.push == 'true'` 正是在 YAML 里另写的一份，
    简化到只剩一个布尔。
    """
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
    # 只插一次：多个 --changed 逐条走这里，原来每条插一次（复审 nit，同 production_preflight）
    if (tools := str(Path(__file__).resolve().parent)) not in sys.path:
        sys.path.insert(0, tools)
    from push_reel import POSTER_NAME, push_is_auto  # noqa: PLC0415

    if not push_is_auto(copy_path):
        # 唯一一道 `forced` 放得宽的闸——它问的是意图，而勾选就是意图。
        if not forced:
            raise Skip(f"{slug}：spec 里没写 push.auto=true，不自动发"
                       f"（要开：在 {spec.name} 的 push 块里加一行 \"auto\": true）")
        print(f"[强制] {slug}：spec 没写 push.auto，但表单勾了强制推送——"
              "只放宽这一道，成片身份/账本/pushed.json 照旧要过")
    from publication_revision import RevisionError, resolve as resolve_revision  # noqa: PLC0415
    try:
        revision = resolve_revision(repo, slug, outdir, film_hash)
    except RevisionError as exc:
        raise Skip(f"{slug}：消息修订不成立——{exc}") from exc
    fingerprint = revision.fingerprint if revision else film_hash
    previous = blocking_attempt(repo, LEDGER_COLUMN, slug, fingerprint)
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
        except (OSError, ValueError):  # ValueError 含 JSONDecodeError：标记坏了也要拦住
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


def pick(changed: list[str], repo: Path,
         forced: bool = False) -> tuple[str, Path] | None:
    """从这次合并带进来的改动里挑出**唯一**该发的那一条。"""
    picked: list[tuple[str, Path]] = []
    for path in changed:
        try:
            slug, outdir = candidate(path.strip(), repo)
            wants_auto_push(repo, slug, outdir, forced=forced)
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


def record(outdir: Path, run_url: str, now: str, receipt: str = "") -> Path:
    """发完记一笔。**这就是「已经发过」的唯一判据**，所以它必须进仓库。

    带上流水号时顺手记下这条微信推送的网页（`message_url`）：账号所有者要
    「推送到微信之后，把那个网页链接发到对话里」，会话推完用
    `tools/push_link.py --slug <slug>` 读的就是这一笔。
    """
    marker = outdir / MARKER
    fields = receipt_fields(receipt)
    marker.write_text(json.dumps(
        {"at": now, "run": run_url, **fields}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(f"[自动推送] 记下已推送：{marker}")
    if fields:
        print(f"[自动推送] 微信推送网页：{fields['message_url']}")
    else:
        # 消息已经发了，不能因为缺流水号就不记（不记＝自动闸以为没发过）；
        # 但要出声：没有流水号，就没有能发进对话的那个链接。
        print("::warning::这一趟没拿到 PushPlus 流水号（推送那步没传 --receipt-out？），"
              "pushed.json 里没有 message_url，推送网页链接取不到")
    return marker


def ledger_status(repo: Path, outdir: Path, status: str, run_url: str, now: str,
                  receipt: str = "") -> Path:
    slug = outdir.name
    film_hash = validate_qc(repo, slug, outdir)
    from publication_revision import RevisionError, resolve as resolve_revision  # noqa: PLC0415
    try:
        revision = resolve_revision(repo, slug, outdir, film_hash,
                                    phase="reserve" if status == "sending" else "finish",
                                    run_url=run_url)
    except RevisionError as exc:
        raise SystemExit(f"{slug}：消息修订不成立——{exc}") from exc
    fingerprint = revision.fingerprint if revision else film_hash
    previous = blocking_attempt(repo, LEDGER_COLUMN, slug, fingerprint)
    if status == "sending" and previous:
        raise SystemExit(f"{slug} 已有 {previous.get('status')} 发布记录，禁止盲目重发")
    if revision and previous and previous.get("status") == "sent":
        if status == "uncertain" or receipt == previous.get("pushplus_receipt"):
            # Known success must survive a later bookkeeping failure.
            return repo / "data" / "reel_publish_ledger" / f"{slug}.json"
        raise SystemExit("消息修订已发送，新的回执与原记录不一致")
    return write_ledger(repo, LEDGER_COLUMN, slug, fingerprint, status=status,
                        run_url=run_url, now=now, receipt=receipt)


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
    ap.add_argument("--receipt-file", default="",
                    help="--record：push_reel 写下的 PushPlus 流水号 JSON（记进 pushed.json 和账本）")
    ap.add_argument("--repo", default=".", help="仓库根目录")
    ap.add_argument("--forced", action="store_true",
                    help="表单勾了「强制推送」：只放宽 push.auto 那一道意图闸，"
                         "成片身份/持久账本/pushed.json 照旧要过")
    args = ap.parse_args(argv)

    repo = Path(args.repo)
    action = args.reserve or args.record or args.uncertain
    if action:
        outdir = Path(action)
        status = "sending" if args.reserve else "sent" if args.record else "uncertain"
        receipt = read_receipt_file(args.receipt_file) if args.record else ""
        ledger_status(repo, outdir, status, args.run, args.now, receipt=receipt)
        if args.record:
            record(outdir, args.run, args.now, receipt)  # 兼容历史消费者
        return 0

    found = pick(args.changed, repo, forced=args.forced)
    if found:
        _emit(*found)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
