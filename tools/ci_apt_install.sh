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
set -uo pipefail

APT_CACHE_DIR="${APT_CACHE_DIR:-$HOME/.cache/apt-archives}"
APT_LISTS_DIR="${APT_LISTS_DIR:-$HOME/.cache/apt-lists}"
mkdir -p "$APT_CACHE_DIR" "$APT_LISTS_DIR"

_apt_opts=(-o "Dir::Cache::Archives=$APT_CACHE_DIR" -o "Dir::State::lists=$APT_LISTS_DIR/")

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
# 先试一次「只用本地缓存装，不碰网络」——`Dir::Cache::Archives` /
# `Dir::State::lists` 指到的两个目录如果被 actions/cache 命中过，索引和
# .deb 都已经在盘上，这一步几秒钟就装完，一次 HTTP 请求都不发。
# 缓存没命中、或者装到一半发现缺包/索引太旧，才回退到会摸网的那条老路
# （apt-get update + install，各自 `apt_retry` 兜两次）。
apt_install_cached() {
  if sudo apt-get "${_apt_opts[@]}" install -y -qq --no-install-recommends "$@" \
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
