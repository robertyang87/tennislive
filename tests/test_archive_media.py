"""archive-media.yml（媒体归档 / 历史重写）的判据。

来路：账号所有者 2026-08-13——「当前代码库太大了」「可以全部删掉，因为之前的
视频都已经发布了」「后面新的视频全部走新的架构不要放在代码里面」。量出来
.git 6.0 GB（mp4 blob 4.93 GB×130），历史里待清路径 3331 条，全在 output/ 下。

purge 是**不可逆**的 force push：这里的判据全在钉「不可逆那一步之前的闸
一个都不许少、一个都不许挪到它后面」。只测「有没有」拦不住位置错——
「复制页那道闸装在渲的那一步不是发的那一步」这一课仓库里上过一次，
所以确认闸和备份 ref 都按**文本索引**钉在 `git filter-repo` 之前。
"""

import re
from pathlib import Path

WORKFLOW = Path(".github/workflows/archive-media.yml")


def _yaml_only(text: str) -> str:
    """去掉整行注释（写法照 tests/test_workflow_alerts.py 那份抄的）。

    工作流的注释正是这个仓库记教训的地方：archive-media.yml 的注释里就写着
    `PURGE`、`git filter-repo`、`refs/keep/…` 这些词——连注释一起扫，
    「把坑记下来」会被判成「又踩了这个坑」，位置判据也会被注释里的提前出现
    搅成假绿。同一个错这个仓库犯过五次。
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def _body() -> str:
    return _yaml_only(WORKFLOW.read_text(encoding="utf-8"))


def test_确认闸要拦在重写历史之前():
    """purge 重写全史、老 ▶ 链接全部失效（账号所有者认领过这个代价）——
    但认领是「他在 confirm 里亲手输入 PURGE」，不是「有人点了 dispatch」。

    钉两头：闸存在（`!= "PURGE"` 那个比较，不是 description 里顺嘴提到的
    PURGE），**而且按文本索引排在 `git filter-repo` 之前**——排在后面的话
    历史已经写完了，闸就成了摆设。
    """
    body = _body()
    gate = body.find('!= "PURGE"')
    # ⚠️ 锚在真正的命令上（--invert-paths），不锚裸的「git filter-repo」：
    # 确认闸的 ::error 文案里就写着这五个字（它在向人解释这一步做什么），
    # 锚裸串会把「闸在解释重写」当成「重写本身」，位置判据整个错位。
    rewrite = body.find("git filter-repo --invert-paths")
    assert gate != -1, "确认闸没了：找不到 != \"PURGE\" 那个比较"
    assert rewrite != -1, "找不到 git filter-repo 那一步——判据的主语没了"
    assert gate < rewrite, (
        "确认闸排在了 git filter-repo 之后。闸要装在不可逆动作之前，"
        "装在后面等于没装。")


def test_备份ref要在重写之前推出去():
    """refs/keep/pre-purge-<日期> 是 purge 唯一的回退杠杆，也是已发消息里
    钉 SHA 的图片链接活下去的机制（对象被任意 ref 引住就不 GC，raw/jsDelivr
    按 SHA 照样取得到）。它必须在 filter-repo **之前**推出去——重写完本地
    HEAD 已经是新历史，那时再推钉住的就是错的东西。
    """
    body = _body()
    keep = body.find('refs/keep/pre-purge-')
    push = body.find('git push origin "HEAD:$KEEP_REF"')
    # ⚠️ 锚在真正的命令上（--invert-paths），不锚裸的「git filter-repo」：
    # 确认闸的 ::error 文案里就写着这五个字（它在向人解释这一步做什么），
    # 锚裸串会把「闸在解释重写」当成「重写本身」，位置判据整个错位。
    rewrite = body.find("git filter-repo --invert-paths")
    assert keep != -1, "找不到 refs/keep/pre-purge- 的备份 ref"
    assert push != -1, (
        "备份 ref 只算了个名字没推出去——不 push，对象照样会被 GC")
    assert rewrite != -1, "找不到 git filter-repo 那一步——判据的主语没了"
    assert push < rewrite, (
        "备份 ref 的 push 排在了 filter-repo 之后——那时 HEAD 已经是"
        "重写后的历史，钉住的不是要保的老对象。")


def test_清单只许扫output底下且有自检():
    """历史里 assets/ 下也有 mp4（assets/brand/outro_master.mp4、
    assets/explainer/eala-mcnally/intro_toronto_crowd.mp4）——那是渲染的
    **输入素材**，清掉以后的片子就渲不出来。所以：

    - 清单的 grep 模式必须锚死 `^output/`
    - 还要有「非 output 行数必须为 0」的自检（`grep -vc '^output/'`）——
      模式将来被人放宽时，自检当场拦住，而不是安静地把 assets 清掉
    - 自检必须排在 filter-repo 之前：排在后面等于验尸
    """
    body = _body()
    assert re.search(r"grep -E '\^output/.*\\\.\(mp4\|webm\|mov\|jpg\|jpeg\|png\)\$'",
                     body), (
        "清单的 grep 模式没锚在 ^output/ 上（或后缀表变了）——"
        "不锚的话 assets/ 的输入素材会被一起清掉")
    selfcheck = body.find("grep -vc '^output/'")
    # ⚠️ 锚在真正的命令上（--invert-paths），不锚裸的「git filter-repo」：
    # 确认闸的 ::error 文案里就写着这五个字（它在向人解释这一步做什么），
    # 锚裸串会把「闸在解释重写」当成「重写本身」，位置判据整个错位。
    rewrite = body.find("git filter-repo --invert-paths")
    assert selfcheck != -1, (
        "缺「非 output 行数必须为 0」的自检——模式被放宽时没有东西出声")
    assert rewrite != -1, "找不到 git filter-repo 那一步——判据的主语没了"
    assert selfcheck < rewrite, "自检排在了 filter-repo 之后，等于验尸"


def test_main和tags都要force推():
    """tags 不跟着重写后的历史一起 force 推的话，老 tag 还钉在老历史上，
    会把整条老历史重新拽进每一个 clone——6 GB 的瘦身白做。两条都要在。
    """
    body = _body()
    assert "git push --force origin main" in body, "重写后没 force 推 main"
    assert "git push --force origin --tags" in body, (
        "重写后没 force 推 --tags——老 tag 会把老历史整条拽回每个 clone")


def test_checkout要拉全史连tags():
    """purge 的业务就是重写**每一个**提交和 tag：浅克隆 filter-repo 做不了，
    tags 不 fetch 下来就没得重写。这条工作流是全仓库唯一允许
    `fetch-depth: 0` 的（豁免记在 tests/test_match_reel.py 那条判据里）。
    """
    body = _body()
    assert re.search(r"fetch-depth:\s*0\b", body), (
        "checkout 没拉全史——filter-repo 只会重写拉下来的那半截")
    assert re.search(r"fetch-tags:\s*true\b", body), (
        "checkout 没拉 tags——老 tag 不重写重推，会把老历史拽回每个 clone")


def test_upload要有重试探活和体积闸():
    """upload 那半的三道闸：

    - **传附件要重试**（二次方退避）：一次 GitHub 自己的 HTTP 500 不该报销
      整趟（match-reel.yml 同一步的教训，2026-08-13 李娜那条）
    - **`-r 0-99` 探活**：传完只下 100 字节确认 206/200 才算真的在——
      purge 预检信的就是这条 URL，传完不探等于把「在不在」留给 purge 去赌
    - **体积闸排在 git commit 之前**：凡是会 git commit 的工作流都要有
      `check_staged_file_sizes`（test_workflow_alerts 那条自动推导的判据），
      而且要排在 commit 前面才拦得住
    """
    body = _body()
    assert re.search(r"if gh release upload .*--clobber", body), (
        "传 Release 附件没走重试循环（或没用 --clobber）")
    assert "WAIT=$((5 * i * i))" in body, (
        "重试没有二次方退避——连着打一个正在 5xx 的接口只会连着挨打")
    assert "-r 0-99" in body, (
        "传完没探活（-r 0-99 只下 100 字节）——purge 预检信的就是这条 URL")
    gate = body.find("python tools/check_staged_file_sizes.py")
    commit = body.find("git commit ")
    assert gate != -1, "缺体积闸 check_staged_file_sizes"
    assert commit != -1, "找不到 git commit——判据的主语没了"
    assert gate < commit, (
        "体积闸排在了 git commit 之后——staged 的检查要在 commit 前跑才算数")
