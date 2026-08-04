"""定时工作流的开关与告警规则（CLAUDE.md：规则要落成测试）。

2026-07-25 审查确认的静默故障：flash.yml / news-radar.yml 失败与空产零告警，
诊断只存在于会过期的 Actions 日志里。

（另一条「daily.yml 把视频开关硬编码成 'off'」随日报 2026-07-31 停产一起删了。）

"""

import re
from pathlib import Path


def _workflow(name: str) -> str:
    return (Path(".github/workflows") / name).read_text(encoding="utf-8")


def _yaml_only(text: str) -> str:
    """去掉整行注释。

    工作流的注释正是这个仓库记教训的地方，正文里必然写着当年那些错值和
    步骤名——连注释一起扫，「把坑记下来」会被判成「又踩了这个坑」。
    反过来同样坏：注释里出现 `PUSHPLUS_SECRET_KEY` 会让漏配的工作流假绿。
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def test_scheduled_radar_workflows_alert_on_failure():
    for name in ("flash.yml", "news-radar.yml"):
        workflow = _workflow(name)
        failure_step = workflow.index("if: failure()")
        # 失败告警必须同时具备：PushPlus 主动推送 + 运行摘要兜底
        assert "pushplus.plus/send" in workflow[failure_step:], name
        assert "GITHUB_STEP_SUMMARY" in workflow[failure_step:], name


def test_scheduled_radar_workflows_summarize_empty_runs():
    for name in ("flash.yml", "news-radar.yml"):
        workflow = _workflow(name)
        empty_step = workflow.index("空产摘要")
        # 空产必须把原因写进运行摘要，而不是只留在会过期的日志正文里
        assert "GITHUB_STEP_SUMMARY" in workflow[empty_step:], name


def test_external_source_health_is_strict_and_separate_from_pr_ci():
    ci = _workflow("ci.yml")
    health = _workflow("source-health.yml")

    # PR 单测必须可重复，不依赖实时比分源；运行时健康由独立定时任务负责。
    assert "tennislive today" not in ci
    assert "真实抓取" not in ci

    assert 'cron: "17 */6 * * *"' in health
    assert "fetch_day(day)" in health
    assert "source_status" in health
    assert "if: failure()" in health
    assert "GITHUB_STEP_SUMMARY" in health
    assert "pushplus.plus/send" in health
    # 主探测不能吞失败；只有告警通道自身允许降级为 warning。
    probe = health.split("- name: 严格检查比分数据源", 1)[1].split("- name:", 1)[0]
    assert "||" not in probe


def test_every_workflow_that_commits_generated_files_has_a_size_gate():
    """跑完一整趟再被 GitHub 拒收，是最贵的一种失败。

    **判据自己推导，不维护白名单。** 原来这里手写着十一个文件名，daily.yml
    停产删掉之后它当场变成 FileNotFoundError——**一个会过期的名单，和一条
    常年红的检查是同一个毛病**。现在改成「凡是 `git commit` 的工作流都要有
    这道闸」，新加工作流自动被覆盖。

    加这条推导的当天就抓到一个：我自己新写的 `push-reel.yml` 漏了闸。
    """
    committers = [
        path for path in sorted(Path(".github/workflows").glob("*.yml"))
        if "git commit" in path.read_text(encoding="utf-8")
    ]
    assert len(committers) >= 8, f"只找到 {len(committers)} 条会提交的工作流，判据可能失效了"
    for path in committers:
        assert "python tools/check_staged_file_sizes.py" in path.read_text(
            encoding="utf-8"), (
            f"{path.name} 会 git commit 却没有体积闸——"
            "渲完一整趟才被 GitHub 拒收是最贵的失败")


# 走 Python 那条推送路（`prepare_image_delivery`）的两个入口。
# 只认这两个，是因为图床分支只在它们底下：news-radar / source-health 是
# 裸 curl 发纯文字告警，没有 `<img>`，配这个 Secret 一点用都没有。
_PUSHPLUS_IMAGE_ENTRIES = re.compile(r"tennislive publish |push_reel\.py")


def test_走图床那条路的工作流都要配SECRET_KEY():
    """漏配不报错，只是悄悄退回 jsDelivr——慢，而且会整条不发。

    `prepare_image_delivery` 有两条分支：配了 `PUSHPLUS_SECRET_KEY` 就走
    PushPlus 自己的图床（上传完当场可取）；没配就退回 jsDelivr，然后
    `wait_for_images` 最多轮询 20×15s = **5 分钟**，轮满还取不到就
    `PushPlusError` **整条推送取消**。也就是说漏配的代价不只是慢，是
    「这一轮内容白生成」。

    而两条分支的日志长得差不多，所以它一直没被发现：flash.yml（内容雷达的
    赛前焦点，跑 `tennislive publish content`）从上线起就没配，而同样走这条
    路的另外五条工作流全配了。

    **判据自己推导，不维护白名单**（见上一条：一个会过期的名单和一条常年红的
    检查是同一个毛病）。新加一条走 `tennislive publish` / `push_reel.py` 的
    工作流，它自动被盖住。
    """
    users = []
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        body = _yaml_only(path.read_text(encoding="utf-8"))
        if _PUSHPLUS_IMAGE_ENTRIES.search(body):
            users.append((path.name, body))

    assert len(users) >= 6, f"只找到 {len(users)} 条走图床的工作流，判据可能失效了"
    for name, body in users:
        assert "PUSHPLUS_SECRET_KEY" in body, (
            f"{name} 会走 PushPlus 图床却没配 PUSHPLUS_SECRET_KEY——"
            "会悄悄退回 jsDelivr，轮询 5 分钟，取不到就整条不发")


def test_每条工作流都要有超时且apt那一步单独有():
    """卡住要失败，不要空转——而 GitHub 的默认是**烧六小时**。

    2026-08-04 实测：`interview-clip` 的「装系统依赖」这一步（就三个包，
    `fonts-noto-cjk fonts-noto-core ffmpeg`）在同一天四趟里分别花了
    **18 秒 / 53 秒 / 13 分 42 秒 / 18 秒**。同一个工作流、同一份包列表、
    二十分钟之内——所以卡的不是我们，是那台 runner 上的 apt 镜像。

    但代价是我们的：那一趟 `timeout-minutes` 一个都没有（job 级也没有），
    于是它就那么静静地烧了十三分半。**而 `-qq` 把 apt 的输出全吞了**，
    日志里一个字都没有——「卡住」和「正常在装」长得一模一样，又一次
    「兜底出事的时候不吭声」。

    ⚠️ **这条规矩本来就有，只是只管一个文件。**
    `test_渲染专用的依赖不许挂在probe路径上` 的 docstring 里写着
    「`apt-get install fonts-noto-cjk` 挂死那次把 probe 拖了二十分钟」
    ——**一模一样的故障，一模一样的结论**，可那条测试 `WORKFLOW` 只指
    `match-reel.yml`。于是 match-reel 补上了，另外七条一条都没有。
    这就是本仓库的老形状：「规矩只写在了其中一半」（storyboard.jpg 那条同一天
    刚犯过）。所以这条**扫全部工作流，不维护白名单**。

    两层各管各的：
    - **job 级**：兜住整趟，防「默认 360 分钟」
    - **步骤级**：apt 是已知会挂的那一步，让它快速失败而不是拖垮整趟
    """
    import yaml  # noqa: PLC0415

    paths = sorted(Path(".github/workflows").glob("*.yml"))
    assert len(paths) >= 15, f"只扫到 {len(paths)} 条工作流，判据可能失效了"

    no_job, no_step, apt_seen = [], [], 0
    for path in paths:
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in (spec.get("jobs") or {}).items():
            if not job.get("timeout-minutes"):
                no_job.append(f"{path.name}:{job_name}")
            for step in job.get("steps") or []:
                # 只看**真正会跑的**那几行，注释里提到 apt 不算——工作流的注释
                # 正是这个仓库记教训的地方，连它一起扫会把「把坑记下来」判成
                # 「又踩了这个坑」。同一个错这个仓库犯过五次。
                run = "\n".join(ln for ln in str(step.get("run") or "").splitlines()
                                if not ln.lstrip().startswith("#"))
                if "apt-get" not in run:
                    continue
                apt_seen += 1
                if not step.get("timeout-minutes"):
                    no_step.append(f"{path.name}「{step.get('name')}」")

    assert apt_seen >= 7, f"只找到 {apt_seen} 个 apt 步骤，判据可能失效了"
    assert not no_job, (
        f"这些 job 没有 timeout-minutes：{no_job}。"
        "GitHub 的默认是 360 分钟——卡住会烧六小时，而且看起来和「还在跑」一样")
    assert not no_step, (
        f"这些 apt 步骤没有 timeout-minutes：{no_step}。"
        "实测同一步能从 18 秒变成 13 分 42 秒，而 `-qq` 让它卡的时候不吭声")


def test_apt一律走重试包装不许裸调():
    """**硬超时只做对了一半。**

    2026-08-04 两小时内 apt 卡了两次：一次静静烧 **13 分 42 秒**（那时没有闸），
    一次被 `timeout-minutes: 6` 掐掉（run 30878555571）——而正常只要
    **18~53 秒**，重跑那趟 34 秒就过了。

    也就是说硬超时把「静静烧半小时」换成了「6 分钟红掉、要人重跑」。方向对，
    但卡住的正确处置是**换一次重试**，不是整趟失败：镜像抽风是它那头的事，
    不该变成我们这头的一次红。

    所以裸的 `sudo apt-get` 一律不许出现，要走 `apt_retry`
    （每次 100 秒超时、最多三次、共 5.5 分钟——仍在步骤的 6 分钟超时以内，
    那道闸还在兜底）。

    ⚠️ 扫之前先去掉整行注释：工作流的注释正是这个仓库记教训的地方，正文里
    必然写着当年那些错写法，连它一起扫会把「把坑记下来」判成「又踩了这个坑」。
    """
    naked, wrapped = [], 0
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        for line in _yaml_only(path.read_text(encoding="utf-8")).splitlines():
            if "apt-get" not in line:
                continue
            if "sudo apt-get" in line:
                naked.append(f"{path.name}: {line.strip()[:60]}")
            elif "apt_retry apt-get" in line:
                wrapped += 1

    assert wrapped >= 12, f"只找到 {wrapped} 处 apt_retry，判据可能失效了"
    assert not naked, (
        "这些地方还在裸调 apt，卡住就是一次红：\n  " + "\n  ".join(naked)
        + "\n改成 `apt_retry apt-get ...`（函数定义抄同一个步骤里那份）")
