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


def test_不许再给工作流配PUSHPLUS_SECRET_KEY():
    """⚠️ **这条判据 2026-08-05 整个翻了个面。** 原来它要求每条走图床的工作流
    都配上 `PUSHPLUS_SECRET_KEY`；现在要求**一条都不许配**。

    账号所有者 2026-08-05：「如果没有任何用途的话，拿掉吧」。

    翻面的理由是那条路真的走了一趟之后才看清的（run 30903125364，纳达尔学院）：

        获取 PushPlus AccessKey 失败: code=401 请求未授权

    官方码表说 401 ＝「排查**开放接口功能是否启用**」，而开放接口
    **默认就是禁用的**，要去后台手动开；开完还有一道**安全 IP 白名单**，
    而 GitHub runner 的出口 IP 每趟都不一样——**那条路对 CI 基本无解**。
    就算全部打通，图床还有两条硬限制：**图片 30 天后自动删**（老推送到期变
    裂图）、**收费/会员**。

    而不配它走的 jsDelivr 退路，图片**钉在 commit 上、永久可取**——
    除了「发送前要等回源」这一点，每一维都更好。

    ⚠️ 原来那条判据的前提是「配了就能用」。前提没了，判据就得跟着翻，
    **不能留着一条要求配一个用不了的密钥的检查**。

    判据仍然**自己推导，不维护白名单**：凡是走 `tennislive publish` /
    `push_reel.py` 那条路的工作流都被扫到，新加一条自动盖住。
    """
    users = []
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        body = _yaml_only(path.read_text(encoding="utf-8"))
        if _PUSHPLUS_IMAGE_ENTRIES.search(body):
            users.append((path.name, body))

    # ⚠️ 这一句是**判据自己的判据**。主语没了（比如有人改了那个正则、
    # 或者把这些工作流删光），下面那个循环会一条都不跑，
    # 于是这条检查变成一盏恒真的绿灯。
    assert len(users) >= 6, f"只找到 {len(users)} 条走图床的工作流，判据可能失效了"

    for name, body in users:
        for key in ("PUSHPLUS_SECRET_KEY", "PUSHPLUS_ACCESS_KEY"):
            assert key not in body, (
                f"{name} 又配上了 {key}。这个密钥**是故意不配的**：\n"
                "  · 开放接口默认禁用，要去 PushPlus 后台手动开（401 就是这个）\n"
                "  · 开完还有安全 IP 白名单，而 GitHub runner 的 IP 每趟都变\n"
                "  · 图床的图 30 天后自动删，老推送到期变裂图\n"
                "不配它走 jsDelivr，图片钉在 commit 上永久可取。\n"
                "真要改回去，先把上面三条解决掉，再连这条判据一起改。")


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

    # ⚠️ **单次超时不许收得比「正常值」还紧。**
    # 第一版写 3 × 100 秒，当场把 CI 弄红（run 30880649692）：三次全跑满 100 秒
    # 被杀——也就是 apt **一直在推进、只是慢**。那个 100 秒是按「正常 18~53 秒」
    # 拍的，而那是**另一条工作流**的数；`ci.yml` 这一步正常 25~34 秒，镜像变慢时
    # 能到 100 秒以上仍在干活。**把「慢」误判成「挂死」，重试就从救场变成三倍浪费。**
    # 所以钉住：单次至少 150 秒（实测正常值的 4~6 倍），而且总时长要留在步骤超时以内。
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        body = _yaml_only(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"for i in ([\d ]+); do\n\s*sudo timeout (\d+) ", body):
            tries, per = len(m.group(1).split()), int(m.group(2))
            assert per >= 150, (
                f"{path.name} 的 apt 单次超时只有 {per} 秒——"
                "比实测的「慢但在推进」还紧，会把慢误判成挂死")
            assert tries * (per + 10) <= 6 * 60, (
                f"{path.name} 的 apt 重试总时长 {tries * (per + 10)} 秒，"
                "超过了步骤的 6 分钟超时——那道兜底的闸就废了")
    assert not naked, (
        "这些地方还在裸调 apt，卡住就是一次红：\n  " + "\n  ".join(naked)
        + "\n改成 `apt_retry apt-get ...`（函数定义抄同一个步骤里那份）")
