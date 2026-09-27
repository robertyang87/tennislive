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
#
# ⚠️⚠️ **2026-09-27：上面这套缓存从 #452 上线起一次都没命中过。**
# 84 份 run 日志（match-reel 成功/失败、CI、采访线）里「缓存命中：零网络」
# 出现 0 次、「缓存没有或不全」出现 84 次。两个根子，都不吭声：
#
#   ① **存不上**：`sudo apt-get` 在这两个目录里留下 root 的 `lock`（0640）和
#      `partial/`（0700），`actions/cache` 回写时是 runner 用户跑 tar——
#      `tar: …/apt-archives/lock: Cannot open: Permission denied`，
#      `Failed to save`，只是一行 warning（run 36284220097 的 post job）。
#      修法：每次 apt 跑完把目录所有权交还给调用者（`_apt_cache_handback`）。
#   ② **存下的是空的**：probe 那几档只 `ensure_ffmpeg`（走静态构建、不碰
#      apt），目录是空的、runner 自己的，于是**反而存得上**——243 字节的空
#      缓存挂在滚动键最新那一格上，下一趟 render 恢复的就是它
#      （`Cache restored from key: …-36276804834`，那是一趟 probe；
#      `Cache Size: ~0 MB (243 B)`），然后 `E: Unable to locate package`。
#      修法：工作流不再用 `actions/cache@v4` 的自动回写，拆成
#      `actions/cache/restore` ＋ 显式的 `actions/cache/save`，**只在这一趟
#      真的摸了网、下了新东西时才存**——这份脚本在那条路上置
#      `APT_CACHE_DIRTY=1`（写进 `$GITHUB_ENV`，后面的 save 步骤读它）。
#      顺带：命中的那几趟不再每趟重传一份一模一样的缓存去挤 10 GB 的池子。
#
# 判据 `tests/test_runner_setup_cache.py`。
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

# sudo 跑的 apt 会在两个缓存目录里留下 root 的 `lock` 和 `partial/`，
# actions/cache 回写时是 runner 用户跑 tar，读不动就整份存不上（见顶部
# 2026-09-27 那段 ①）。**每次 apt 跑完就把所有权交还给调用者**——成败都交：
# 失败那一趟不回写，但同一个 job 后面可能还有一步会摸网、会回写。
_apt_cache_handback() {
  sudo chown -R "$(id -u):$(id -g)" "$APT_CACHE_DIR" "$APT_LISTS_DIR" 2>/dev/null || true
}

# 这一趟摸了网、目录里多了新东西——告诉后面的 `actions/cache/save` 步骤
# 「这份值得存」。没摸网的那几趟（缓存命中、或者压根没调 apt）不置，
# save 步骤就跳过：不再把空目录或一模一样的旧缓存再传一遍（顶部 ②）。
_apt_cache_mark_dirty() {
  export APT_CACHE_DIRTY=1
  if [ -n "${GITHUB_ENV:-}" ]; then
    echo "APT_CACHE_DIRTY=1" >> "$GITHUB_ENV"
  fi
}

# 用法：apt_install_cached <包名...>
#
# 先试一次「只吃本地缓存」——`Dir::Cache::Archives` / `Dir::State::lists`
# 指到的两个目录如果被 actions/cache 恢复过、且这批包的 .deb 也真的在盘上，
# 这一步几秒钟就装完，一次 HTTP 请求都不发。
#
# ⚠️ 原来这句**不保证零网络**：索引是新的不等于这批包的 .deb 也在盘上，
# 它会在「本地安装」的名义下悄悄去下载（run 32290505356 卡满 12 分钟就是
# 这么来的），所以才包了 `timeout 150`。**2026-09-27 起加了 `--no-download`**：
# 缺哪个 .deb 当场报错、零点几秒落到下面那条会摸网的路，不再在「像是本地
# 安装、其实在下载」上赌 150 秒——而且只有走了那条路才算「这趟下了新包」，
# 回写缓存的判断（`_apt_cache_mark_dirty`）才是准的。`timeout 150` 留着兜底。
# 缓存没命中、或者装到一半发现缺包/索引太旧，才回退到会摸网的那条老路
# （apt-get update + install，各自 `apt_retry` 兜两次）。
apt_install_cached() {
  if sudo timeout 150 apt-get "${_apt_opts[@]}" install -y -qq --no-install-recommends \
       --no-download "$@" 2>/tmp/apt_install_cached.log; then
    _apt_cache_handback
    echo "[apt] 缓存命中：零网络请求装上了 $*"
    return 0
  fi
  echo "[apt] 缓存没有或不全，走网络（$*）："
  cat /tmp/apt_install_cached.log || true
  local rc=0
  apt_retry apt-get "${_apt_opts[@]}" update -qq \
    -o Acquire::Retries=3 -o Acquire::http::Timeout=20
  apt_retry apt-get "${_apt_opts[@]}" install -y -qq --no-install-recommends \
    -o Acquire::Retries=3 -o Acquire::http::Timeout=20 "$@" || rc=$?
  _apt_cache_handback
  if [ "$rc" = 0 ]; then
    _apt_cache_mark_dirty
  fi
  return "$rc"
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
# ⭐ 2026-09-27：这一步每趟 30 秒（188 趟 render/cover ＋ 228 趟 probe，中位 30s、
# p90 31s，09-15 前后一样），而**下载只占 1.3 秒**——大头是解包：原来先
# `tar -tJf` 整包解两遍找名字（`grep -m1` 早退救不了 tar，它照样把 518 MB
# 解完），再整包解一遍取两个文件。包里的顺序是 presets/ doc/ … bin/ffmpeg
# bin/ffprobe bin/ffplay，ffplay（176 MB）排在最后。
#
# 现在：**成员名按下载地址算死**（`<包名>/bin/ffmpeg`），`--occurrence=1`
# 让 tar 两个都拿到就停，ffplay 那 176 MB 一个字节都不解；`xz -T0` 多线程解
# （这个包是 22 个 24 MiB 的块，能并行）。沙箱 4 核实测同一个包：老办法
# 99.1s，`--occurrence` 32.4s，再加 `xz -T0` 15.0s（沙箱被别的活占着，绝对值
# 偏大，比例才是要看的）。
#
# 包的结构变了（顶层目录改名……）就退回老办法：列一遍（只列一遍）找名字再取。
# 两条路取出来的都要**真跑一次 `-version`** 才算数——解到一半的截断文件
# `-f` 也是真的，只有跑得起来才不是。
#
# 用法：_ffmpeg_extract <包> <解到哪> <顶层目录名>，成功时把两个路径各打一行。
_ffmpeg_extract() {
  local archive="$1" dest="$2" top="$3"
  local ffbin="$top/bin/ffmpeg" ffprobebin="$top/bin/ffprobe"
  # tar 拿够就退，xz 会吃一个 SIGPIPE——管道的退出码不说明问题，下面按产物判。
  # `-f -` 要写明：不写时读 stdin 只是 GNU tar 编译进去的默认（`tar --show-defaults`
  # 里那个 `-f-`），环境里有 `TAPE` 就改读它、快路静静落空，退到下面「列一遍」的慢路
  { xz -T0 -dc "$archive" 2>/dev/null \
      | tar -x -f - -C "$dest" --occurrence=1 "$ffbin" "$ffprobebin" 2>/dev/null; } || true
  if ! _ffmpeg_runs "$dest/$ffbin" "$dest/$ffprobebin"; then
    echo "[ffmpeg] 包里没有 $ffbin（结构变了？），列一遍找名字" >&2
    local listing
    listing=$(tar -tJf "$archive" 2>/dev/null) || true
    ffbin=$(printf '%s\n' "$listing" | grep -m1 '/ffmpeg$' || true)
    ffprobebin=$(printf '%s\n' "$listing" | grep -m1 '/ffprobe$' || true)
    if [ -z "$ffbin" ] || [ -z "$ffprobebin" ]; then
      return 1
    fi
    tar -xJf "$archive" -C "$dest" --occurrence=1 "$ffbin" "$ffprobebin" 2>/dev/null || true
    _ffmpeg_runs "$dest/$ffbin" "$dest/$ffprobebin" || return 1
  fi
  printf '%s\n%s\n' "$dest/$ffbin" "$dest/$ffprobebin"
}

_ffmpeg_runs() {
  [ -f "$1" ] && [ -f "$2" ] || return 1
  chmod +x "$1" "$2" 2>/dev/null || true
  "$1" -version >/dev/null 2>&1 && "$2" -version >/dev/null 2>&1
}

ensure_ffmpeg() {
  if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
    echo "[ffmpeg] 已经在 PATH 上了，跳过"
    return 0
  fi
  local url="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
  local tmp ok=0 t0=$SECONDS
  tmp="$(mktemp -d)"
  if timeout 90 curl -fsSL "$url" -o "$tmp/ffmpeg.tar.xz" 2>"$tmp/dl.log"; then
    local bins ffbin ffprobebin
    if bins=$(_ffmpeg_extract "$tmp/ffmpeg.tar.xz" "$tmp" "$(basename "$url" .tar.xz)"); then
      ffbin=$(printf '%s\n' "$bins" | sed -n 1p)
      ffprobebin=$(printf '%s\n' "$bins" | sed -n 2p)
      sudo install -m 755 "$ffbin" /usr/local/bin/ffmpeg 2>/dev/null
      sudo install -m 755 "$ffprobebin" /usr/local/bin/ffprobe 2>/dev/null
      if command -v ffmpeg >/dev/null 2>&1 && ffmpeg -version >/dev/null 2>&1; then
        ok=1
      fi
    fi
  fi
  rm -rf "$tmp"
  if [ "$ok" = 1 ]; then
    echo "[ffmpeg] 走静态构建（BtbN，GPL 版含 drawtext），没碰 apt 镜像：下载＋解包 $((SECONDS - t0))s"
    return 0
  fi
  echo "[ffmpeg] 静态构建拿不到，退回 apt"
  apt_install_cached ffmpeg
}
