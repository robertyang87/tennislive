#!/bin/bash
# 每次新会话把这台机器配到「能跑全量测试、能本地渲封面、能本地合语音」。
#
# **为什么要有它**：账号所有者 2026-08-05「之前好像有好几次都要重新安装配置
# 环境……浪费了很多时间」。容器每次是干净的，而这个仓库真跑起来要三样东西
# （项目依赖、中文字体、ffmpeg），手动装一遍五到十分钟，还会踩下面那两个坑。
#
# ⚠️ **装的东西要和 `ci.yml` 那一行对齐。** 这个仓库反复栽在「本地装着不等于
# CI 装着」上（playwright、Chromium、cv2、fonts-noto-core、pip 行漏了 `-e .`）。
# 沙箱装少了 → 本地绿 CI 红；沙箱装多了 → 本地绿而 CI 缺依赖，同样看不出来。
# 判据在 `test_会话启动钩子装的东西要和CI对齐`。
set -euo pipefail

# 本地开发机不归它管（钩子只为 Claude Code on the web 那种一次性容器）
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"

need_apt=0
# 判据是**产物**（字体在不在、ffmpeg 在不在），不是「装过没有」这种信号。
#
# ⚠️ **不许写成 `fc-list | grep -qi X`。** `grep -q` 一命中就退出，`fc-list`
# 随即吃 SIGPIPE，而 `set -o pipefail` 把整条管道判成失败（退出码 141）——
# 于是**匹配上了反而被判成「没装」**。实测过，第一版就是这么写的。
# 它错的方向是「白跑一次 apt」，所以慢一点、永远不报错、**永远没人发现**。
# 和 CLAUDE.md 里 `until ! pgrep -f 'X'` 那条同一个形状：检查自己的机制
# 把检查本身废掉了。所以先落成变量再匹配，整条路上没有管道。
fonts="$(fc-list 2>/dev/null || true)"
case "$fonts" in *NotoSansCJK*) ;; *) need_apt=1 ;; esac
case "$fonts" in *NotoColorEmoji*) ;; *) need_apt=1 ;; esac
command -v ffmpeg >/dev/null 2>&1 || need_apt=1

if [ "$need_apt" = 1 ]; then
  echo "[启动] 装中文字体和 ffmpeg…"
  # ⚠️ **`update` 必须排在前面。** 镜像里的索引是构建时的，直接 install 会去取
  # 已经被删掉的旧版本，报的是 `404 Not Found` 而不是「索引过期」——
  # 2026-08-05 就是这么失败一次的（i965-va-driver / va-driver-all）。
  sudo apt-get update -qq
  # ⚠️ **`--no-install-recommends` 不是洁癖。** ffmpeg 的 recommends 拖着一串
  # VA-API 驱动，而那正是上面 404 的那两个包；这台机器又根本没有硬件解码可用。
  sudo apt-get install -y -qq --no-install-recommends \
    fonts-noto-cjk fonts-noto-core fonts-noto-color-emoji ffmpeg
else
  echo "[启动] 字体和 ffmpeg 都在，跳过 apt"
fi

echo "[启动] 装项目依赖（和 ci.yml 那一行对齐）…"
pip install -q -e ".[dev,webrender,visualqa]"
# `cffi` 是 rembg/onnxruntime 那条链上的，缺了它七条测试报
# `pyo3_runtime.PanicException`——**和「这里跑不了」长得一模一样**。
# `edge-tts` 是本地查旁白要的（`render --check-narration`，实测 29 秒）。
pip install -q cffi edge-tts

# **查产物，不查信号。** `pip install` 退出码 0 不保证 import 得进来
# （装错版本就是这样：opencv 5.x 装上了，`CascadeClassifier` 没了，
# 红得和「没装」一模一样）。所以在这儿真 import 一遍。
python3 - <<'PY'
import shutil, subprocess, sys
bad = []
for mod in ("rich", "PIL", "cv2", "playwright", "pypdf", "cffi", "edge_tts",
            "certifi", "numpy", "tennislive"):
    try:
        __import__(mod)
    except Exception as exc:                      # noqa: BLE001
        bad.append(f"{mod}: {type(exc).__name__} {exc}")
if not shutil.which("ffmpeg"):
    bad.append("ffmpeg 不在 PATH 上")
fonts = subprocess.run(["fc-list"], capture_output=True, text=True).stdout
for tag in ("NotoSansCJK", "NotoColorEmoji"):
    if tag not in fonts:
        bad.append(f"字体缺 {tag}")
if bad:
    print("[启动] ⚠️ 配好了一半，下面这些还不行：\n  " + "\n  ".join(bad))
    sys.exit(1)
print("[启动] ✅ 全套就绪：全量测试、本地渲封面、本地查旁白都能跑了")
PY
