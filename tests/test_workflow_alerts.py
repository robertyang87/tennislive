"""定时工作流的开关与告警规则（CLAUDE.md：规则要落成测试）。

2026-07-25 审查确认的静默故障：flash.yml / news-radar.yml 失败与空产零告警，
（news-radar 2026-08-05 改名 news-brief：两条推送合成一条，告警要求不变。）
诊断只存在于会过期的 Actions 日志里。

（另一条「daily.yml 把视频开关硬编码成 'off'」随日报 2026-07-31 停产一起删了。）

2026-08-13 又抓到一条同族的：flash / knowledge-adhoc / news-brief 三处推送步骤
挂着 `continue-on-error: true`，把上面那两条告警**自己废掉了**——job 不进入
failed 状态，`if: failure()` 恒假。见 `test_吞掉微信推送失败的步骤都要按outcome重抛`。

"""

import ast
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
    for name in ("flash.yml", "news-brief.yml"):
        workflow = _workflow(name)
        failure_step = workflow.index("if: failure()")
        # 失败告警必须同时具备：PushPlus 主动推送 + 运行摘要兜底
        assert "pushplus.plus/send" in workflow[failure_step:], name
        assert "GITHUB_STEP_SUMMARY" in workflow[failure_step:], name


def test_scheduled_radar_workflows_summarize_empty_runs():
    for name in ("flash.yml", "news-brief.yml"):
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

    ⚠️ **两边都要先 `_yaml_only` 去掉整行注释**（本文件其余几条早就这么做了，
    只有这条一直读的是原文）。2026-08-14 补 `permissions:` 时当场撞上：
    `ci.yml` 新写的注释里有一句「这一条只跑 pytest：不 `git commit`、不
    `git push`」——**一条明说自己不提交的注释，把 ci.yml 判成了会提交的**，
    然后要它装体积闸。这正是 CLAUDE.md 里记了五遍的那个形状：工作流的注释是
    这个仓库存放教训的地方，连注释一起扫，「把坑记下来」会被判成「又踩了这个坑」。
    ⚠️ 下面那半边同样要剥——注释掉的闸不算装了闸，那是**假绿**的方向。
    """
    bodies = {path: _yaml_only(path.read_text(encoding="utf-8"))
              for path in sorted(Path(".github/workflows").glob("*.yml"))}
    committers = [path for path, body in bodies.items() if "git commit" in body]
    assert len(committers) >= 8, f"只找到 {len(committers)} 条会提交的工作流，判据可能失效了"
    for path in committers:
        assert "python tools/check_staged_file_sizes.py" in bodies[path], (
            f"{path.name} 会 git commit 却没有体积闸——"
            "渲完一整趟才被 GitHub 拒收是最贵的失败")


# 走 Python 那条推送路（`prepare_image_delivery`）的两个入口。
# 只认这两个，是因为图床分支只在它们底下：news-brief / source-health 是
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


def test_工作流不许裸调apt要走共享脚本():
    """**硬超时只做对了一半，而这一层的逻辑现在只活在一个地方。**

    2026-08-19 起，`装 ffmpeg`／`装中文字体` 那批步骤全部改成
    `source tools/ci_apt_install.sh && apt_install_cached <包名...>`——
    重试、超时、缓存这套逻辑收进了共享脚本（见
    `test_装ffmpeg和字体一律先试本地缓存不能只靠重试` 和
    `test_共享的apt安装脚本形状要对`），工作流文件里不该再出现任何一处
    直接调用 `apt-get` 的命令。

    ⚠️ **只拦真的在跑 apt-get 那个命令，不拦提到它的**：`pw_wait_apt()`
    （装 Chromium 那条路，PR #447）里有 `pgrep -x apt-get` 和
    `pkill -9 apt-get`——那是在**查/杀一个叫这个名字的进程**，不是在
    **执行**这个命令，判据要放过它们，否则会把一条正当的安全网也拦下。

    ⚠️ 扫之前先去掉整行注释：工作流的注释正是这个仓库记教训的地方，正文里
    必然写着当年那些错写法，连它一起扫会把「把坑记下来」判成「又踩了这个坑」。
    """
    naked = []
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        for line in _yaml_only(path.read_text(encoding="utf-8")).splitlines():
            if "apt-get" not in line or "apt_install_cached" in line:
                continue
            if "pkill" in line or "pgrep" in line:
                continue
            naked.append(f"{path.name}: {line.strip()[:70]}")

    assert not naked, (
        "这些地方还在直接调 apt-get，卡住就是一次红，而且绕开了共享脚本的"
        "缓存和重试：\n  " + "\n  ".join(naked)
        + "\n改成 `source tools/ci_apt_install.sh` + `apt_install_cached <包名>`")


def test_装ffmpeg和字体那批步骤都走共享脚本不留手搓的调用():
    """**「每个用到它的文件都要够格」是这条线唯一还留在工作流层面的判据。**

    重试预算够不够跑得完（≥150s/次、总预算 ≤ 步骤 timeout-minutes）、
    `update`/`install` 两行是不是都带了 `Acquire::http::Timeout`——这些
    以前是逐个工作流文件各查一遍，现在**这套逻辑只有一份**
    （`tools/ci_apt_install.sh`），`test_共享的apt安装脚本形状要对` 管住了
    脚本本身；这条测试只管调用方——**每一处 `apt_install_cached` 或
    `ensure_ffmpeg` 调用**，它所在的步骤必须给够 `timeout-minutes`。

    共享脚本的最坏路径是固定的：`apt_install_cached` 先试一次本地安装
    （`timeout 150`），没成功才退到 `apt_retry(update)` + `apt_retry(install)`，
    每个 `apt_retry` 最多两轮、每轮 `timeout 150 + sleep 10`——
    **150 + 2 × 2 × 160 = 790 秒 ≈ 13.2 分**。

    这条判据是「装 ffmpeg 和字体一律先试本地缓存不能只靠重试」那条测试
    自己没管到的另一半：那条测试钉的是「缓存步骤在不在、source 语句在不在」，
    这条钉的是「就算缓存全没命中，这一步跑不跑得完」。2026-08-19 装缓存
    那天就在这儿踩过一次真的——`match-reel.yml`／`preview-reel.yml` 各有一处
    字体步骤留着改缓存之前的 `timeout-minutes: 7`，而新的 `apt_install_cached`
    在缓存没命中时会退到 update+install 两段，7 分钟装不完。

    ⚠️ **同一天傍晚第二次涨预算**：`apt_install_cached` 最前面那句「先试
    本地安装」原来没有 `timeout` 包着（当时的假设是「本地缓存命中，几秒钟
    的事，不用防」），run 32290505356 撞出这个假设不成立——同一个 job 里
    前一步刚摸过网、索引是新的，不代表这一批包的 `.deb` 也已经在盘上，这句
    照样可能悄悄发起真下载，而它一旦卡住**没有任何超时**，只能靠外层
    `timeout-minutes` 硬杀，而且会连累后面本该重试的 `apt_retry` 一起陪葬。
    补上 `timeout 150` 之后，最坏预算从 640 秒涨到了这儿的 790 秒——
    **这也是为什么这条判据比 `apt_retry` 的两段乘积多出一个 150**。

    ⚠️⚠️ **同一天晚上第三次：ffmpeg 这个包单独反复失灵，`ensure_ffmpeg`
    先试 GitHub Releases 上的静态构建（`timeout 90` 的 curl），失败了才落回
    `apt_install_cached ffmpeg` 那条老路**——所以调 `ensure_ffmpeg` 的步骤
    最坏预算要再加这 90 秒（`90 + 790 = 880 秒`）。这条测试原来只认
    `apt_install_cached` 这一个名字，`ensure_ffmpeg` 上线的当天就把
    `checked` 从两位数砍到 7——**主语没了一半，判据要跟着两个名字一起认**，
    不然「换个函数名」会悄悄把这条闸对一半步骤变成哑的。
    """
    APT_ONLY_BUDGET = 150 + 2 * 2 * (150 + 10)  # 790 秒：本地安装那句(150) + update/install 两段重试(640)
    ENSURE_FFMPEG_BUDGET = 90 + APT_ONLY_BUDGET  # 880 秒：静态构建的 curl(90) 落空才轮到上面那条老路

    checked, over = [], []
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for name in re.findall(r"^      - name: (.+)$", text, re.M):
            block_m = re.search(
                rf"\n      - name: {re.escape(name)}\n(.*?)(?=\n      - name:|\Z)",
                text, re.S)
            block = _strip_shell_comments(block_m.group(1)) if block_m else ""
            calls_ensure_ffmpeg = bool(re.search(r"(?<![\w-])ensure_ffmpeg(?![\w-])", block))
            calls_apt_cached = "apt_install_cached" in block
            if not (calls_ensure_ffmpeg or calls_apt_cached):
                continue
            budget = ENSURE_FFMPEG_BUDGET if calls_ensure_ffmpeg else APT_ONLY_BUDGET
            checked.append(f"{path.name}「{name}」")
            m = re.search(r"timeout-minutes:\s*(\d+)", block)
            limit = int(m.group(1)) * 60 if m else 0
            if limit < budget:
                over.append(
                    f"{path.name}「{name}」timeout-minutes="
                    f"{limit // 60 if limit else '(没写)'}，要 ≥ {budget // 60 + 1} 分钟")

    assert len(checked) >= 10, f"只校到 {len(checked)} 处 apt_install_cached/ensure_ffmpeg，判据可能失效了"
    assert not over, (
        f"这些步骤调了 apt_install_cached 或 ensure_ffmpeg，但 timeout-minutes 撑不住"
        f"缓存/静态构建全落空时的最坏预算：\n  "
        + "\n  ".join(over) + "\n第二次重试会在中途被步骤超时杀掉，"
        "而那和「apt 真挂死了」长得一模一样。")


def test_job级超时要兜得住各步骤自己声明的最坏预算之和():
    """上一条测试管的是「每一步自己够不够」，这条管**加起来还装不装得进
    外层那道 job 级预算**——2026-08-19 就在 `ci.yml` 上真的撞过：

        装字体/ffmpeg（apt_install_cached，本 PR 刚从 7 分钟提到 12） + 12
        装 Chromium（`timeout-minutes: 10`）                          + 10
                                                          小计 22 分钟
        而 job 级 `timeout-minutes` 当时是 15

    两步各自的预算都是**认真量出来、有出处的数**（12 是共享脚本的
    `WORST_CASE_BUDGET`，10 是「2×240s + 110s 等锁」），可**谁都没检查过
    加起来还塞不塞得进 job 级那道壳**。当天真撞上了：run 32232302155
    连着两次在 15 分钟整被砍掉，一次是 pytest 卡在 98%（多给几分钟大概率
    跑完），一次是装 Chromium 第二次还没跑完（也没有死循环，只是被砍早了）。

    ⚠️ **这条不检查「没写 timeout-minutes 的步骤」**——那些多半是 checkout /
    pip 这类正常几秒到几分钟的步骤，没有一个「最坏预算」的出处可核，硬编一个
    只会制造假警报。只加总**明确写了 timeout-minutes 的步骤**，job 级预算
    至少要覆盖这些已知的最坏情况，再加上没写超时的那些步骤的正常余量——
    所以判据留了 50% 的宽松空间（job 预算 ≥ 步骤之和，不要求等于）。
    """
    import yaml  # noqa: PLC0415

    paths = sorted(Path(".github/workflows").glob("*.yml"))
    checked, over = [], []
    for path in paths:
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in (spec.get("jobs") or {}).items():
            job_limit = job.get("timeout-minutes")
            if not job_limit:
                continue  # 没写 job 级超时的那一半，另一条测试已经在拦
            step_sum = sum(
                int(step.get("timeout-minutes") or 0)
                for step in job.get("steps") or [])
            if step_sum == 0:
                continue  # 没有任何一步声明过「最坏预算」，没有基线可比
            checked.append(f"{path.name}:{job_name}")
            if job_limit < step_sum:
                over.append(
                    f"{path.name}:{job_name} job={job_limit}min "
                    f"< 步骤之和={step_sum}min")

    assert len(checked) >= 1, "一个有步骤级超时可加总的 job 都没扫到，判据可能失效了"
    assert not over, (
        "这些 job 的 timeout-minutes 撑不住它自己各步骤声明的最坏预算之和：\n  "
        + "\n  ".join(over) + "\n某一步的预算被人加宽过（比如缓存没命中时的重试），"
        "但外层这道 job 级的壳没跟着调宽——步骤自己还在正常重试的时候，"
        "job 超时先把整趟砍了，看起来和「卡死了」一模一样。")


def _strip_shell_comments(run: str) -> str:
    """去掉 run 脚本里的整行注释。

    和 `_yaml_only` 同一个理由，只是这次剥的是 shell 那一层：本文件要找的
    `continue-on-error` / `tennislive publish` 这些词，正**写在**被修好的那几个
    步骤的注释里（那是这个仓库记教训的地方）。连注释一起扫，「把坑记下来」
    会被判成「又踩了这个坑」——同一个错这个仓库犯过五次。
    """
    return "\n".join(
        line for line in str(run or "").splitlines()
        if not line.lstrip().startswith("#")
    )


def _wechat_sender_pattern() -> re.Pattern[str]:
    """「这一步会发微信吗」——**从仓库自己推导，不维护工作流白名单**。

    三种发送形态，前一种是推出来的，后两种是字面量且各自说得出为什么：

    1. `tools/<script>.py` —— **AST 推导**：凡是 import 了
       `tennislive.publish.pushplus` 的 tools 脚本都算。2026-08-13 跑出来正好
       两个（`oncourt_feed.py` / `push_reel.py`），以后新写一个自动被盖住。
       ⚠️ 用 AST 不用正则：这几个脚本的 docstring 和注释里都反复提到
       pushplus，按文本扫会把「提到」判成「调用」。
    2. `tennislive publish ` —— CLI 那条路。`cli.py` 同样 import 了 pushplus，
       但它的命令行形态是 `tennislive`，而 `tennislive content` /
       `tennislive brief` 这些不发微信的子命令满仓库都是，推不出来只能写死
       子命令名。
    3. `pushplus.plus/send` —— YAML 里裸 curl 那条（news-brief 的推送、
       以及几条工作流的失败告警）。

    ⚠️ 这个函数**只回答「发不发微信」，不回答「该不该拦」**。
    `frame-grab.yml` / `match-reel.yml` 那两处 `continue-on-error` 挂的是
    「起 PO token provider」——最佳努力的 docker 旁路服务，失败时自己
    `echo ::warning::` 并 dump docker logs，是正当的。它们**天然落不进这个
    集合**（run 脚本里一个发送形态都没有），所以不需要为它们写例外——
    这正是「判据宁可窄」买来的东西：2026-08-13 的评审报告把六处
    `continue-on-error` 并列，照它一刀切会把那两处也删掉，而删掉的代价是
    一次 docker pull 抖动就打红整趟 render。
    """
    senders = []
    for path in sorted(Path("tools").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and "publish.pushplus" in (
                    node.module or ""):
                senders.append(path.name)
                break
    assert len(senders) >= 2, (
        f"只从 tools/ 里推出 {len(senders)} 个发微信脚本，AST 推导可能失效了")
    return re.compile("|".join(
        [re.escape(name) for name in senders]
        + [r"tennislive publish ", r"pushplus\.plus/send"]))


def _logical_lines(text: str):
    """把行尾反斜杠续行拼回一条**逻辑命令**。

    `curl ... \\` + `-d "$BODY" \\` + `|| echo ...` 在源文件里是三行，
    而「这次调用有没有被 `||` 兜住」只有拼回一条之后才判得出来。
    """
    out, buf = [], ""
    for line in text.splitlines():
        buf += line.rstrip()
        if buf.endswith("\\"):
            buf = buf[:-1] + " "
            continue
        out.append(buf)
        buf = ""
    if buf:
        out.append(buf)
    return out


def _steps_with_index(spec: dict):
    """摊平成 (job 名, 步骤序号, 步骤) —— 序号用来判先后。"""
    for job_name, job in (spec.get("jobs") or {}).items():
        for index, step in enumerate(job.get("steps") or []):
            yield job_name, index, step


def test_吞掉微信推送失败的步骤都要按outcome重抛():
    """`continue-on-error` 吞掉发微信的失败，就必须有人把它重新抛出来。

    ## 来路（2026-08-13）

    审查发现三处推送步骤挂着 `continue-on-error: true`：
    `flash.yml`「推送小红书待发布包到微信」、`knowledge-adhoc.yml`
    「PushPlus 推送到微信」、`news-brief.yml`「推送简报到微信」。

    **要害不是「没记录」**（失败步骤在 UI 上有红叉、日志里有报错），
    是 **flash 和 news-brief 各自写了 `if: failure()` 的 PushPlus 告警步骤，
    专为无人值守准备，而 continue-on-error 让 job 保持绿色，那两个告警
    永远不会触发**——工作流自己装的那道闸被自己废掉了。knowledge-adhoc
    更彻底：推送是文件最后一步，后面什么都没有，这条线一次红灯都不会有。

    flash 那行原来还带着一句 `# 单次推送抖动不应让整轮内容雷达失败`，
    **而那个前提不成立**：抖动（网络异常、5xx）早在库层重试过了
    （`src/tennislive/publish/pushplus.py` 的重试预算，只重试「没送到」），
    能走到步骤失败这一层的已经是硬失败——恰恰是最该出声的那一类。

    ## 修法：延迟失败，不是不失败

    形状抄 `oncourt-interviews.yml`（本仓库唯一做对的一条推送，
    `tests/test_oncourt_feed.py` 已经把它钉住了）：保留 continue-on-error
    让后面的落库/摘要步骤跑完，跑完之后按 `outcome` 重新 `exit 1`。

    ## 这条判据钉四样，都是硬的

    1. 吞掉失败的推送步骤必须有 `id`（没有 id，下面那个 `outcome` 检查
       就是一盏恒真的绿灯）
    2. 后面必须有一步 `if: steps.<id>.outcome == 'failure'`
    3. 那一步必须真的 `exit 1`（只 echo 不退出，job 照样是绿的）
    4. **排在推送之后的** `if: failure()` 步骤，必须排在重抛之后——
       否则告警读不到失败状态，等于没修
       ⚠️ 只管「排在推送之后的」：`knowledge-adhoc.yml` 的「上传失败诊断」
       也挂 `if: failure()`，但它排在推送**之前**（管的是生成那几步的失败），
       无论重抛放哪儿它都看不到推送的 outcome。判据宁可窄。

    ## 故意不钉的

    - **不要求重抛步骤写 `GITHUB_STEP_SUMMARY`。** 我改的三处都写了
      （把诊断留在不会过期的地方），但 oncourt 那条是靠另一个 `if: always()`
      的「摘要」步骤兜的，两种都成立。硬凑一条「必须写在重抛里」会把对的
      写法判成错的。
    - **不要求推送步骤必须挂 continue-on-error。** 直接删掉它、让 job 自然
      变红，也是对的修法（flash / knowledge-adhoc 的落库步骤本来就排在推送
      前面，删了不损失什么）。所以「没有任何一步吞失败」时这条判据**正当地
      空过**，下面那句人口普查负责证明扫描本身还活着。

    ## 软的部分，别当实测读

    「continue-on-error 使 `if: failure()` 不触发」**没有真跑一次 Actions
    验证**（这台沙箱跑不了）。依据两条：(a) Actions 的标准语义——
    continue-on-error 让步骤 conclusion 变成 success、job 不失败，
    而 `outcome` 保留真实结果；(b) **本仓库自己的书面理解**：
    `oncourt-interviews.yml` 那句「提交后会再次按 outcome 让整个 run 红灯
    告警」的注释、以及 `test_push_failure_is_reported_after_collected_data_is_committed`
    的存在本身就是证明——如果 continue-on-error 之后 job 还会红，
    那条重抛步骤和它的测试就没有存在的理由。
    真要坐实，成本很低：仿 `pages-selftest.yml` 起一条只有「故意 exit 1 的
    continue-on-error 步骤 + if: failure() 步骤」的自检工作流，十几秒自证。
    """
    import yaml  # noqa: PLC0415

    sends = _wechat_sender_pattern()
    outcome_of = re.compile(
        r"steps\.\s*([A-Za-z_][\w-]*)\s*\.\s*outcome\s*==\s*['\"]failure['\"]")

    population, swallowed = 0, []
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        steps = list(_steps_with_index(spec))
        for job_name, index, step in steps:
            if not sends.search(_strip_shell_comments(step.get("run"))):
                continue
            population += 1
            if not step.get("continue-on-error"):
                continue
            swallowed.append((path, job_name, index, step, steps))

    # ⚠️ **判据自己的判据，而且只能钉在人口上、不能钉在违规数上。**
    # 钉「至少有 N 个 continue-on-error」会把「有人把它们全删了」这个
    # **正当的修法**判成红；钉人口才是在证明「这个扫描还找得到发微信的步骤」。
    # 主语没了（正则写坏、工作流删光），它当场出声，而不是变成恒真的绿灯。
    assert population >= 12, (
        f"全仓只扫到 {population} 个发微信的步骤，判据可能失效了——"
        "先确认 _wechat_sender_pattern() 还认得出这几种发送形态")

    for path, job_name, index, step, steps in swallowed:
        where = f"{path.name}「{step.get('name')}」"
        step_id = step.get("id")
        assert step_id, (
            f"{where} 用 continue-on-error 吞掉了微信推送的失败，却没有 id——"
            "没有 id 就没法按 outcome 重抛，这个失败会一路绿到底")

        rethrow = None
        for other_job, other_index, other in steps:
            if other_job != job_name or other_index <= index:
                continue
            found = outcome_of.search(str(other.get("if") or ""))
            if found and found.group(1) == step_id:
                rethrow = (other_index, other)
                break
        assert rethrow, (
            f"{where} 吞掉了微信推送的失败，后面却没有一步"
            f" `if: steps.{step_id}.outcome == 'failure'` 把它重抛。\n"
            "这条工作流自己写的 `if: failure()` 告警因此永远不会响——"
            "闸被自己废掉了。形状抄 oncourt-interviews.yml。")

        rethrow_index, rethrow_step = rethrow
        assert "exit 1" in _strip_shell_comments(rethrow_step.get("run")), (
            f"{where} 的重抛步骤「{rethrow_step.get('name')}」没有 `exit 1`——"
            "只 echo 不退出的话 job 还是绿的，等于没修")

        # 排在推送**之后**的 failure() 告警，必须能读到失败状态。
        late_alerts = [
            (other_index, other)
            for other_job, other_index, other in steps
            if other_job == job_name and other_index > index
            and "failure()" in str(other.get("if") or "")
        ]
        for alert_index, alert in late_alerts:
            assert rethrow_index < alert_index, (
                f"{where} 的重抛步骤排在「{alert.get('name')}」后面了。"
                "那一步挂着 `if: failure()`，要先有人把 job 打红它才读得到"
                "失败状态——顺序反了等于没修")


def test_裸curl发微信要检查返回体里的code():
    """`code != 200` 时 HTTP 仍然是 200、curl 退出码仍然是 0。

    2026-08-13 抓到的第二条，和 continue-on-error 无关、删不删它都存在：
    `news-brief.yml` 的推送**绕开了** `src/tennislive/publish/pushplus.py`
    的 `push()`，自己裸 curl，然后 `echo "PushPlus 返回：$RESP"` 就结束了。
    于是 token 错、内容超限、频率限制这类**服务端明确拒绝**全都是绿的，
    日志里只有一行没人看的返回体。**又一次「查产物，不查信号」**——
    判据是返回体里的 `code`，不是 curl 的退出码。

    ⚠️ **只判，不在 YAML 里重试。** 「只重试没送到、拒绝不重发」已经在库层
    实现了；YAML 里再套一层循环会把 `code != 200` 也重发，
    而微信那条消息发出去收不回来。所以这条判据要求 `code` 检查，
    **同时禁止**在同一步里出现重试循环。

    判据自己推导：凡是 run 脚本里真的 POST 了 pushplus 的步骤都要过这一关。
    ⚠️ 扫之前先剥 shell 注释——被修好的那一步的注释里正写着
    `code != 200` 和「不重试」，连注释一起扫会把「把坑记下来」判成假绿。

    ## ⚠️ 边界：**已经被 `||` 兜住的那次调用不算**

    第一版只排除了字面的 `|| true`，当场误伤 `source-health.yml`
    「所有来源失效时通知」——它写的是 `|| echo "::warning::…"`，同一个意思
    不同拼法。**那是告警通道，不是投递通道**：发的是纯文字、没有产物可丢，
    而且「告警自己发不出去」不该再制造一次失败（flash / news-brief 的
    `if: failure()` 告警是同一族，写的是 `|| true`）。

    所以判据认的是**这次 curl 有没有被 `||` 兜住**——被兜住＝作者已经
    显式声明「这一发失败了也不要紧」，那就不该反过来要求它检查 code。
    没被兜住的那些才是在投递内容，它们的失败必须看得见。
    ⚠️ 要先把行尾续行拼成一条逻辑命令再判，`||` 常常单独占一行。
    又一次「判据宁可窄，不可宽」：按名字或按 `|| true` 字面去分，
    都会把对的写法判成错的。
    """
    import yaml  # noqa: PLC0415

    checked = []
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        for _job, _index, step in _steps_with_index(spec):
            run = _strip_shell_comments(step.get("run"))
            if "pushplus.plus/send" not in run:
                continue
            degraded = any(
                "pushplus.plus/send" in line and "||" in line
                for line in _logical_lines(run)
            )
            if degraded:
                continue
            checked.append((path.name, step.get("name"), run))

    assert checked, "一个投递内容的裸 curl 都没扫到，判据可能失效了"

    for name, step_name, run in checked:
        where = f"{name}「{step_name}」"
        assert re.search(r"\.code\s*==\s*200", run), (
            f"{where} 裸 curl 发微信却没检查返回体里的 code。"
            "PushPlus 拒绝时 HTTP 还是 200、curl 退出码还是 0，"
            "这一步会全绿而消息一个人都没收到")
        assert re.search(r"exit 1", run), (
            f"{where} 检查了 code 却没有 `exit 1`，等于没检查")
        assert not re.search(r"for\s+\w+\s+in\b|while\s+", run), (
            f"{where} 在工作流层加了重试循环。"
            "「只重试没送到、拒绝不重发」已经在 publish/pushplus.py 里实现了；"
            "这儿再套一层会把 `code != 200` 也重发，"
            "而微信那条消息发出去收不回来")


def _workflow_bodies() -> dict[Path, str]:
    """全部工作流，**去掉整行注释**再给出来。

    这个仓库的注释是存放教训的地方，正文里必然写着当年那些错值、别的工作流的
    名字、以及「这里不装 X」这种话。连注释一起扫，「把坑记下来」会被判成
    「又踩了这个坑」——本文件里的体积闸那条 2026-08-14 刚栽过一次。
    """
    return {path: _yaml_only(path.read_text(encoding="utf-8"))
            for path in sorted(Path(".github/workflows").glob("*.yml"))}


def _top_level_permissions(body: str) -> dict[str, str] | None:
    """顶层那个 `permissions:` 块，`{范围: 级别}`；没写就是 None。

    **只认顶层**（顶格的 `permissions:`）：job 级也能写，但这个仓库全在顶层，
    而「没写」和「写在别处」要分得开——前者是继承仓库默认（可能是读写），
    后者是想清楚过的。
    """
    match = re.search(r"^permissions:[ \t]*$", body, re.M)
    if match is None:
        return None
    out: dict[str, str] = {}
    for line in body[match.end():].splitlines()[1:]:
        if not line.strip():
            continue
        got = re.match(r"^[ \t]+([\w-]+):[ \t]*([\w-]+)[ \t]*$", line)
        if got is None:                      # 缩进结束 = 这个块完了
            break
        out[got.group(1)] = got.group(2)
    return out


def test_每条工作流都要自己写permissions():
    """**不写这一块，token 有多大权限就取决于仓库设置里那个开关。**

    2026-08-14 盘出来：24 条工作流里有 4 条压根没有 `permissions:`——
    `ci` / `probe` / `probe-blocked` / `verify-names`。而 GitHub 的老默认是
    「读写」，也就是说它们可能一直在用一个能推 main 的 token 跑；其中
    **`probe-blocked` 握着 `YT_COOKIES_TXT`、`probe` 握着
    `SPORTRADAR_API_KEY` + `RAPIDAPI_KEY`**——密钥和可写 token 落在同一个
    job 里是最不该省的那一处。

    ⚠️ **这个漏洞的样子是「什么都没发生」**：那个开关不在这个仓库里，改了它
    也不会有任何一次 run 变红，翻工作流文件更是一个字都看不出来。又一次
    「兜底出事的时候不吭声」，只不过这次不吭声的是一个默认值。

    判据**自己推导，不维护白名单**：`.github/workflows/` 下每一个 `.yml` 都要
    有顶层 `permissions:`。新加一条工作流自动被盖住——CLAUDE.md 里
    「一个会过期的名单和一条常年红的检查是同一个毛病」说的就是这个。
    """
    missing = [path.name for path, body in _workflow_bodies().items()
               if _top_level_permissions(body) is None]
    assert not missing, (
        f"这几条工作流没写 `permissions:`，于是继承仓库默认（可能是读写）："
        f"{missing}\n"
        "按它真正要做的事显式写死：只读代码就 `contents: read`；"
        "要 `git commit`/`git push`/发 Release 才给 `contents: write`；"
        "要点 `pages.yml` 的 workflow_dispatch 才给 `actions: write`。")


def test_不提交产物也不发Release的工作流不许要写权限():
    """`contents: write` 要有**它自己**的理由，不是随手抄上一条工作流。

    能正当要到写权限的只有两件事，两件都在 `run:` 里看得见：
    **`git commit`**（往仓库里写产物）和**发 Release**（成片 2026-08-13 起
    一律走 Release 附件，`gh release` 同样吃 `contents: write`）。

    判据**自己推导，不维护白名单**。拿改之前的现状扫过一遍确认不误伤：
    9 条带 `contents: write` 的**全都**真的 `git commit`（archive-media /
    assets / auto-push-* / explainer / flash / frame-grab / interview-clip /
    knowledge-adhoc / match-reel / news-brief / oncourt-interviews /
    player-name-sync / voice-sample），一条误伤都没有；而
    `pages-selftest` / `push-existing` / `source-health` / `video-localize`
    本来就写着 `contents: read`。

    ⚠️ 发 Release 那一支是**故意留着的**：今天每条发 Release 的工作流恰好也都
    `git commit`，所以只认 `git commit` 也能过——但那是**碰巧对**，而
    「碰巧对」和「真的接上了」长得一模一样，还会一直绿。哪天出现一条只传
    Release 不提交的工作流，只认 commit 的判据会把它误判成越权。
    """
    offenders = []
    for path, body in _workflow_bodies().items():
        perms = _top_level_permissions(body) or {}
        if perms.get("contents") != "write":
            continue
        commits = "git commit" in body
        releases = bool(re.search(r"gh release|action-gh-release", body))
        if not commits and not releases:
            offenders.append(path.name)
    assert not offenders, (
        f"这几条要了 `contents: write`，却既不 `git commit` 也不发 Release："
        f"{offenders}\n"
        "写权限要有它自己的理由——只读代码的改成 `contents: read`。")

    # **判据自己也要有判据。** 主语没了它会变成一盏恒真的绿灯：真扫到过
    # 带写权限的工作流，这条断言才说明上面那个循环跑过。
    writers = [path.name for path, body in _workflow_bodies().items()
               if (_top_level_permissions(body) or {}).get("contents") == "write"]
    assert len(writers) >= 8, f"只扫到 {len(writers)} 条带写权限的工作流，判据失效了"


def test_四条只读工作流不许悄悄要回写权限():
    """上一条管「有没有理由」，这条管**这四条具体的**。

    它们 2026-08-14 之前一个 `permissions:` 都没有，补的时候逐条核过它们真正
    做什么：`ci` 只跑 pytest；`probe` / `probe-blocked` 只探源、把报告传成
    artifact（`upload-artifact` 走 runtime token，不吃 `GITHUB_TOKEN` 的权限）；
    `verify-names` 只拿维基百科核一遍译名表、**结果打印到日志**。四条都不
    `git commit`、不 `git push`、不发 Release、不调 GitHub API。

    ⚠️ **`verify-names` 最容易被名字骗**：会写译名表的是
    `player-name-sync.yml`（那条真的提交推送，所以它有 `contents: write`）。
    两条名字很像、权限差一档——所以这里钉的是**实测出来的那一档**，
    别让下一个人按名字猜。
    """
    bodies = _workflow_bodies()
    for name in ("ci.yml", "probe.yml", "probe-blocked.yml", "verify-names.yml"):
        path = Path(".github/workflows") / name
        assert path in bodies, f"{name} 不在了——主语没了就得换判据，别留着一条常年红"
        perms = _top_level_permissions(bodies[path])
        assert perms == {"contents": "read"}, (
            f"{name} 的权限现在是 {perms}，应该只有 `contents: read`。"
            "要改就先说清楚它新做了什么需要更大权限的事。")
        # 反过来钉一次：真做了写的事却还挂着只读，是另一头的坏（会红在 runner 上）
        assert "git commit" not in bodies[path] and "git push" not in bodies[path], (
            f"{name} 开始提交/推送了，那 `contents: read` 会让它在 runner 上红——"
            "两边要一起改")


def test_CI要把最慢的测试打进日志():
    """`ci.yml` 那行 pytest 必须带 `--durations`，不然这一步没有诊断出口。

    **来路（2026-08-14）：** 同一个 commit（45975571）两个口径差 5.3 倍——

        沙箱 4 核    1884 passed, 34 skipped in 108.91s
        runner 4 核  1883 passed, 35 skipped in 581.55s   （run 31783930140）

    同一棵树、同样的条数、同样的核数，所以**不是代码变慢了**；同一条分支相隔
    四分钟的两趟（178s / 647s）更直白。也就是说这一步的耗时主要由 runner 当时
    的状态决定，而它**排在每一次合并前面**。

    在这之前，慢的那趟在日志里只有一串点：既查不出是哪几条测试，也证明不了
    「不是这次改的」。这个仓库为「只在成功时出声的检查没法证明它真的看过」
    记过好几笔——**一个没有诊断出口的关键路径，慢起来只能靠猜**，而猜出来的
    结论会被下一个人当判据用。

    ⚠️ 判据只钉「有这个出口」，**不钉具体条数**（25 是拍的，改成 30 没有意义
    上的差别）；也**不钉时长上限**——把一个含 runner 抖动的总时长写成硬闸，
    等于每隔几趟就红一次，而「一条常年红的检查和没有检查是同一个毛病」。
    """
    body = _yaml_only(_workflow("ci.yml"))
    line = [ln for ln in body.splitlines() if "pytest" in ln and "run:" in ln]
    assert len(line) == 1, f"ci.yml 里跑 pytest 的行不是一条：{line}"
    assert "--durations" in line[0], (
        "ci.yml 那行 pytest 不再打印最慢的测试了：\n  " + line[0].strip()
        + "\n\nCI 排在每次合并前面，而它的耗时在 runner 上会 3~10 分钟乱跳"
          "（同一个 commit 实测 108.91s vs 581.55s）。没有这份榜单，"
          "「今天怎么这么慢」既查不出是哪几条，也证明不了不是这次改的。")
