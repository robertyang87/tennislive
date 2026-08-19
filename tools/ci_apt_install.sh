#!/usr/bin/env bash
# 供工作流 `source` 的共享脚本，别在各个 .github/workflows/*.yml 里各写一份。
#
# ⚠️ 2026-08-19 一天里连中两次，`Acquire::http::Timeout=20` 这道防线双双失守：
#   - PR #448（run 32218612883）：ci.yml 的 `apt-get install` 连着两次吃满
#     150 秒，零字节进度
#   - PR #451（bouzkova-jovic 那趟 render）：match-reel.yml 的 `apt-get update`
#     同样连着两次吃满 150 秒，零字节进度
# 两次都是 apt 镜像整段不响应，不是「在推进只是慢」——`timeout 150` 之内让
# apt 自己换镜像这条防线，对着一个彻底没有响应的 host 不生效（连接本身没
# 按配置的超时收敛，具体是 DNS 还是 TCP 层面卡住，从这台机器上看不出来）。
#
# 继续把重试调得更聪明治不了根：**真正的杠杆是大多数 run 根本不用碰这个
# 镜像。** `apt-get update` 和 `apt-get install` 的产物（索引 + 下载好的
# .deb）缓存住之后，`apt-get install` 能完全从本地满足，一个字节都不用下。
#
# 索引和下载缓存**不用系统路径**（`/var/cache/apt/archives`、
# `/var/lib/apt/lists`）——那两个目录是 root 建的，`actions/cache@v4` 的
# save/restore 步骤是普通用户跑的，写不进去。改用
# `Dir::Cache::Archives` / `Dir::State::lists` 把 apt 的这两块状态
# 重定向到 `$HOME/.cache/apt-*`，那两个目录由这份脚本自己先 `mkdir -p`
# （普通用户建的，普通用户能写），`sudo apt-get` 写进去的文件默认
# 644（世界可读），缓存步骤读得到。
#
# ⚠️⚠️ **2026-08-19：这个重定向本身撞上了 apt 自己的沙箱机制。**
# apt 默认把真正的下载动作降权到 `_apt` 这个系统用户去做（`APT::Sandbox::User`），
# 而 `$HOME/.cache/apt-lists` 是 `runner`（或调用这份脚本的那个用户）的
# 主目录底下建的目录——`_apt` 根本进不去 `runner` 的主目录，更别说写。
# 症状是这一行（run 32236503405 attempt 4 才第一次露出来，之前几次大概率
# 是同一件事，只是 `-qq` 把警告吞掉了）：
#
#   W: Download is performed unsandboxed as root as file
#   '…/apt-lists/partial/packages.microsoft.com_repos_azure-cli_dists_noble_InRelease'
#   couldn't be accessed by user '_apt'. - pkgAcquire::Run (13: Permission denied)
#
# apt 会**逐个文件**降级成「直接用 root 下」这条兜底路径——GitHub 的
# `ubuntu-latest` 镜像预配置了好几个第三方源（azure-cli、chrome-stable……），
# `update`/`install` 会去刷新全部配置过的源，不止我们要装的那几个包，
# 于是这套「先撞权限、警告、再退回 root」的动作在多个源上反复发生，
# 表现就是「apt 一直在卡，两次 150 秒都吃满」——**和真正的镜像不响应
# 长得一模一样，但根子在我们自己重定向的目录权限上，不是网络**。
#
# 修法很直接：**告诉 apt 别费劲降权了，本来就是拿 sudo 跑的，直接用 root
# 做下载**（`APT::Sandbox::User=root`）。这跳过整套「先撞权限再退回」的
# 折腾，不影响缓存目录本身怎么建、谁读得到——**跟「继续调重试参数治不了根」
# 是同一个道理，这次要治的不是重试次数，是权限模型本身**。
#
# ⚠️⚠️ **2026-08-19 傍晚又撞了一次，这次是`apt_install_cached` 自己那句
# 「先试一次零网络的本地安装」没有 `timeout` 包着。** run 32290505356：
# `装中文字体` 那一步整整 12 分钟**零输出**，被外层 `timeout-minutes: 12`
# 硬杀——不是 `apt_retry` 那种「第 1 次没跑完」的警告刷两轮再报错（那种
# 好歹每 150~160 秒打一行），是从进这个函数起**一个字都没打印过**，说明
# 卡的就是最前面那句裸的 `sudo apt-get … install …`。
#
# 根子在于这句话的注释一直是错的：它说「零网络」，但**只有索引和 .deb 都
# 在盘上才成立**。同一个 job 里前一步（装 ffmpeg）缓存也没命中、摸了网、
# 刷新过 `Dir::State::lists` 里的索引——那份索引现在是新的，**但 ffmpeg
# 自己的 .deb 已经下好了，字体包的 .deb 从来没被请求过**。于是这句「本地
# 安装」看着像会命中缓存，实际上还是要去下字体包的 .deb，而它**不经过
# `apt_retry`，没有 `timeout` 包着**——这跟前面两次「镜像不响应」是同一个
# 底层风险，只是这次连累的是一条完全没有防护的代码路径。
#
# 修法是把这句也用 `timeout` 包起来，让它顶多卡 150 秒就摔回退路，
# 而不是一直卡到外层 `timeout-minutes` 才被杀掉、把后面 `apt_retry`
# 那条真正会摸网重试的路一起陪葬。**代价是最坏预算从 640 秒涨到
# 790 秒**（150 + 640），调用方的 `timeout-minutes` 要跟着涨，
# 判据在 `tests/test_workflow_alerts.py` 的 `WORST_CASE_BUDGET`。
set -uo pipefail

APT_CACHE_DIR="${APT_CACHE_DIR:-$HOME/.cache/apt-archives}"
APT_LISTS_DIR="${APT_LISTS_DIR:-$HOME/.cache/apt-lists}"
mkdir -p "$APT_CACHE_DIR" "$APT_LISTS_DIR"

_apt_opts=(-o "Dir::Cache::Archives=$APT_CACHE_DIR" -o "Dir::State::lists=$APT_LISTS_DIR/"
           -o "APT::Sandbox::User=root")

apt_retry() {
  for i in 1 2; do
    sudo timeout 150 "$@" && return 0
    echo "::warning::apt 第 $i 次没跑完（卡住或超时）：$*"
    sudo dpkg --configure -a || true   # 上一次被 SIGTERM 打断可能留下半装状态
    sleep 10
  done
  echo "::error::apt 两次都没成功：$*"
  return 1
}

# 用法：apt_install_cached <包名...>
#
# 先试一次「优先吃本地缓存」——`Dir::Cache::Archives` / `Dir::State::lists`
# 指到的两个目录如果被 actions/cache 命中过、且这批包的 .deb 也真的在盘上，
# 这一步几秒钟就装完，一次 HTTP 请求都不发。
#
# ⚠️ **它不保证零网络**：索引是新的（比如同一个 job 里前一步刚 `apt-get
# update` 过）不等于这批包的 .deb 也已经下过——前一步装的是另一批包，
# 索引里认得这批包不代表本地就有它们的安装文件，这句仍然可能去摸网。
# 正因为「像是本地安装，其实在下载」这件事分不清楚，它才**必须**包一层
# `timeout`：卡住的时候不吭声，和真的在装一样，只有超时兜底才拦得住。
# 缓存没命中、或者装到一半发现缺包/索引太旧，才回退到会摸网的那条老路
# （apt-get update + install，各自 `apt_retry` 兜两次）。
apt_install_cached() {
  if sudo timeout 150 apt-get "${_apt_opts[@]}" install -y -qq --no-install-recommends "$@" \
       2>/tmp/apt_install_cached.log; then
    echo "[apt] 缓存命中：零网络请求装上了 $*"
    return 0
  fi
  echo "[apt] 缓存没有或不全，走网络（$*）："
  cat /tmp/apt_install_cached.log || true
  apt_retry apt-get "${_apt_opts[@]}" update -qq \
    -o Acquire::Retries=3 -o Acquire::http::Timeout=20
  apt_retry apt-get "${_apt_opts[@]}" install -y -qq --no-install-recommends \
    -o Acquire::Retries=3 -o Acquire::http::Timeout=20 "$@"
}

# ⚠️⚠️ 2026-08-19 下午到晚上，apt 镜像单单对 ffmpeg 这个包反复失灵——
# `apt-get update` 有时能成，但紧接着 `apt-get install ffmpeg` 两次
# 150 秒都拿不到那个 .deb（run 32300118619／32302142919／32304343522
# 连续三次都死在这儿，中间隔了 5～15 分钟冷却也没用）。这不是「慢」，
# 是这一个包的下载路径当天持续不通——`Acquire::http::Timeout=20` 这层
# 防线对着一个会接受连接、只是数据一直不来的源没用。
#
# **真正的杠杆是别去碰这条镜像。** 同一条流水线本来就靠
# `release-assets.githubusercontent.com` 发成片（「成片一律走 Release
# 不进 git」），这条路今天全程稳定——所以 ffmpeg 改成先试一个托管在
# GitHub Releases 上的静态构建。
#
# ⚠️⚠️ **第一版指的是 BtbN/FFmpeg-Builds 的 `latest` 标签，当场翻车**
# （run 32307313856）：那个标签**每天跟着 FFmpeg master 重新构建**，
# 不是一个钉死的版本——那天下到的 ffprobe 是 `N-126217-…-20260819`，
# 字面就是当天编的。它的 CSV writer 行为和我们用了很久的稳定版不一样：
# `-show_entries stream=duration -of csv=p=0` 吐出 `117.480000,`
# 带一个尾随逗号，`check_reel_landed.py` 拿它 `float()` 直接崩——
# **这正是「latest 不等于稳定」的活证据**，不是猜的。那个 crash 已经在
# `check_reel_landed.py` 里防御性地修了（只取逗号前第一个字段），
# 不管哪个 ffprobe 版本再吐这种尾巴都不会再崩。
#
# ⚠️⚠️ **第二版换成了 johnvansickle.com 的稳定版（7.0.2，两年没变过），
# 却在 CI 上当场撞了另一个坑**（PR #462）：这个 minimal 静态构建
# **没编 `drawtext` 滤镜**（`-filters` 里查不到，`--enable-libfreetype`
# 写在 buildconf 里却没用上——大概率是这份构建特意剔的），而
# `contact_sheet()` 烧时间码用的正是它。`mode=probe` 那条路直接死。
# **两个候选各缺一半**：BtbN 有全部滤镜（drawtext/ass/xfade 都实测过）
# 但版本不稳；johnvansickle 版本稳但滤镜不全。这条流水线要的是全部滤镜，
# 版本漂移那半坑已经用防御性解析堵住了——所以退回 BtbN，**不是绕了一圈
# 白折腾，是把两次真实失败各自的教训都吃进了最终方案**：URL 换回去，
# CSV 解析的防御不撤。
#
# ⚠️ **不是替换 apt，是多一条更快的路，apt 仍然是保底。** 静态构建
# 下载失败（那天也抽风、tar 包结构变了……）就原样退回
# `apt_install_cached ffmpeg`——旧路径一个字没删，坏的方向不会比现在更糟。
ensure_ffmpeg() {
  if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
    echo "[ffmpeg] 已经在 PATH 上了，跳过"
    return 0
  fi
  local url="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
  local tmp ok=0
  tmp="$(mktemp -d)"
  if timeout 90 curl -fsSL "$url" -o "$tmp/ffmpeg.tar.xz" 2>"$tmp/dl.log"; then
    local ffbin ffprobebin
    ffbin=$(tar -tJf "$tmp/ffmpeg.tar.xz" 2>/dev/null | grep -m1 '/ffmpeg$' || true)
    ffprobebin=$(tar -tJf "$tmp/ffmpeg.tar.xz" 2>/dev/null | grep -m1 '/ffprobe$' || true)
    if [ -n "$ffbin" ] && [ -n "$ffprobebin" ]; then
      tar -xJf "$tmp/ffmpeg.tar.xz" -C "$tmp" "$ffbin" "$ffprobebin" 2>/dev/null
      sudo install -m 755 "$tmp/$ffbin" /usr/local/bin/ffmpeg 2>/dev/null
      sudo install -m 755 "$tmp/$ffprobebin" /usr/local/bin/ffprobe 2>/dev/null
      if command -v ffmpeg >/dev/null 2>&1 && ffmpeg -version >/dev/null 2>&1; then
        ok=1
      fi
    fi
  fi
  rm -rf "$tmp"
  if [ "$ok" = 1 ]; then
    echo "[ffmpeg] 走静态构建（BtbN，GPL 版含 drawtext），没碰 apt 镜像"
    return 0
  fi
  echo "[ffmpeg] 静态构建拿不到，退回 apt"
  apt_install_cached ffmpeg
}
