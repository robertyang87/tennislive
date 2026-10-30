#!/bin/bash
# 工作进程重启时 s1 段（第 2440–4880 帧）没写完、文件损坏：拆 3 小段重渲。s1a/s1b/s1c 按名字排序正好接在 s0 与 s2 之间。
cd "$(dirname "$0")"
node cap.js 2440 3254 seg/s1a.mp4 > seg/s1a.log 2>&1 &
node cap.js 3254 4067 seg/s1b.mp4 > seg/s1b.log 2>&1 &
node cap.js 4067 4880 seg/s1c.mp4 > seg/s1c.log 2>&1 &
wait; echo done
