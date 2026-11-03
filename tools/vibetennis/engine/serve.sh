#!/bin/bash
# 给一集的 r3d/ 起静态服务（已起着就不重起）：bash serve.sh <集目录> [端口=8766]
# 容器重启会把它弄没（cap.js 报 ERR_CONNECTION_REFUSED 就是这个），所以渲染脚本每次先调它。
R="$(cd "$1" && pwd)/r3d"; P=${2:-8766}
curl -sf -o /dev/null "http://127.0.0.1:$P/index.html" && exit 0
# setsid ＋ 三个标准流全重定向：否则后台服务占着调用方的管道，`review_pack.py … | tail` 永远等不到 EOF（2026-11-03 踩过）
(cd "$R" && exec setsid python3 -m http.server "$P" --bind 127.0.0.1 </dev/null >/dev/null 2>&1) &
for i in $(seq 1 20); do curl -sf -o /dev/null "http://127.0.0.1:$P/index.html" && exit 0; sleep 0.5; done
echo "静态服务起不来：$R :$P" >&2; exit 1
