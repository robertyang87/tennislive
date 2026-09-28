#!/usr/bin/env bash
# YouTube 还下不下得动——真下三秒媒体流。match-reel.yml 的 `mode=cookies` 跑它；
# source-health.yml 每 6 小时定时派发一趟 `mode=cookies`（无人值守 → 红了走
# pipeline_health 的阻塞推送，按 `match-reel:cookies` 这一处去重，不重复推）。
#
# 用法：bash tools/yt_cookie_check.sh [URL]
#   URL 空着就用下面那条默认视频；cookie 文件走环境变量 YT_COOKIES（工作流「落 cookies」那步给）。
#
# **cookie 会过期，而过期时的表现和「没配」一模一样。** 所以要有一条随时能跑、
# 不产生任何产物的验证：真下三秒媒体流。
# 注意 `--skip-download` 那种探活是**假的**——不带 cookie 也拿得到标题和格式表，
# 只有真去取媒体流才会撞上 "Sign in to confirm you're not a bot"。
#
# 2026-09-19 17:15Z cookie 失效，一直到 22:52Z 都是**会话手动拨的 probe 红了**才发现
# （5 趟：两趟 probe、三趟手动 cookies）——没有任何定时的东西在看它。
# 2026-09-20 00:20Z 那趟（run 35478525370）表单里填的是 `ytsearch8:…` 搜索词：
# 搜出 0 条，报的是「没下到媒体流」，看着像 cookie 又坏了。所以先验入参是不是一条视频。
#
# 这段逻辑原来直接写在 match-reel.yml 那一步里；抽出来是因为定时自检要跑**同一段**，
# 同一件事写两处必然分叉。判据 test_cookie自检只有一份_定时派发走阻塞推送。
set -u

URL="${1:-}"
DEFAULT_URL="https://www.youtube.com/watch?v=HyKTXynnI9c"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 "$HERE/source_url_check.py" --mode cookies --url "$URL" || exit 1
[ -n "$URL" ] || URL="$DEFAULT_URL"

ARGS=()
if [ -n "${YT_COOKIES:-}" ] && [ -f "$YT_COOKIES" ]; then
  ARGS=(--cookies "$YT_COOKIES")
  echo "带 cookie 试（$(wc -l < "$YT_COOKIES") 行）"
else
  echo "::warning::没有 YT_COOKIES_TXT，这次只验 client 梯子（cookies 模式不起 PO token provider）"
fi

WORK="${RUNNER_TEMP:-$(mktemp -d)}"
rm -rf "$WORK/ytcheck" && mkdir -p "$WORK/ytcheck"
yt-dlp "${ARGS[@]}" --js-runtimes node --download-sections "*0-3" \
  --force-keyframes-at-cuts \
  -f "bv*[height<=720]+ba/b[height<=720]/b" \
  -o "$WORK/ytcheck/probe.%(ext)s" "$URL" 2>&1 | tee "$WORK/yt.log" || true
FILE=$(ls -S "$WORK/ytcheck" 2>/dev/null | head -1)
if [ -z "$FILE" ]; then
  # **别把「没下到」一律说成「cookie 过期」**——第一次跑就栽在这上面：
  # 真实原因是没装 yt-dlp-ejs，n challenge 解不了，只剩图片格式，
  # 而我的报错写着「cookie 可能过期了」，方向反了。所以按日志分因。
  if grep -q "not a bot\|Sign in to confirm" "$WORK/yt.log"; then
    echo "::error::撞上了机器人验证——cookie 无效或已过期，重新导一份存进 Secret YT_COOKIES_TXT"
  elif grep -q "n challenge solving failed\|Only images are available" "$WORK/yt.log"; then
    echo "::error::n challenge 解不了：yt-dlp 缺 yt-dlp-ejs 或没有 JS 运行时，和 cookie 无关"
  elif grep -q "Video unavailable\|This video is private\|has been removed" "$WORK/yt.log"; then
    echo "::error::这条自检视频本身不可用（下架／私享）——换一条再验，和 cookie 无关：$URL"
  else
    echo "::error::没下到媒体流，原因见下面的格式表"
  fi
  yt-dlp "${ARGS[@]}" --js-runtimes node --list-formats "$URL" 2>&1 | tail -25 || true
  exit 1
fi
SIZE=$(stat -c%s "$WORK/ytcheck/$FILE")
echo "拿到 $FILE，$SIZE 字节"
# 几百字节的「文件」多半是错误页，不是媒体
[ "$SIZE" -gt 51200 ] || { echo "::error::文件只有 $SIZE 字节，不是媒体流"; exit 1; }
if command -v ffprobe >/dev/null; then
  ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 \
    "$WORK/ytcheck/$FILE"
fi
echo "YouTube 下载可用。"
