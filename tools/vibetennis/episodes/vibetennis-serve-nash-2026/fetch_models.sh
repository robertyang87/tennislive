#!/bin/bash
# EP07 的 3D 模型不进仓库（授权不允许当素材单独分发），渲染前用这个脚本下到 r3d/models/：
#  · 手：W3C Immersive Web 工作组 webxr-input-profiles 的 generic-hand（MIT），25 个关节，用来摆石头／剪刀／布
#  · 球员：BoQsc/Godot-Male-Base-Mesh 的写实男性基础人体（CC0），带 Rigify 骨骼、无动画；钉在提交 e7807327a8ebcc637831995a231dae701b6d4f56
#    （2026-11-04 换掉 three.js 示例里的 Mixamo X Bot：所有者「不要这个模型的人」）
set -e; M="$(cd "$(dirname "$0")" && pwd)/r3d/models"; mkdir -p "$M"
get(){ [ -s "$M/$2" ] || curl -sSLf -o "$M/$2" "$1"; }
get https://cdn.jsdelivr.net/npm/@webxr-input-profiles/assets@1.0.19/dist/profiles/generic-hand/left.glb hand_left.glb
get https://cdn.jsdelivr.net/npm/@webxr-input-profiles/assets@1.0.19/dist/profiles/generic-hand/right.glb hand_right.glb
get https://raw.githubusercontent.com/BoQsc/Godot-Male-Base-Mesh/e7807327a8ebcc637831995a231dae701b6d4f56/Original/male_base_mesh.glb male_base.glb
ls -la "$M"
