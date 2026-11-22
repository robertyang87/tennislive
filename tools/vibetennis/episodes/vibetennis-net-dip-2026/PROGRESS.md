# EP13 网中间矮 · 制作进度（断点文件）

续跑：`nohup setsid bash run_rest.sh > /workspace/ep13_run.log 2>&1 &`（幂等；先 `pgrep -fa cap.js` 确认没有渲染在跑）
环境（box 重启会丢）：`cd /workspace/nodetools && npm i playwright@1.49 three@0.170 gsap@3.15.1 puppeteer-core@24 && npx playwright install chromium-headless-shell chromium`

## 已完成
- 调研包 papers/vibetennis-net-dip-2026/；narration.json 35 句＋英文字幕（en_subs.py）；TTS voice/ 35 句；voice_check 0 项不合格
- plan.py → r3d/timeline.json：总长 242.01 s，HIT 17.80 s（BGM 第 8 小节），段落起点对齐拍点
- 场景 r3d/src/shots.js（8 个镜头）→ build.py → scene.js
- 工具升级：GSAP 3.15 标题逐字动画（kinTitle）；Three.js MeshPhysical 网带 sheen／网柱清漆金属；快动作子帧运动模糊（slowIn：扯断、拉带、穿越球、两球过网）；EffectCraft 0.24.1 光效 vfx/vfx.jsx → flare.mov / sweep.mov，vfx.py 按拍点 screen 叠加
- 音频：sfx.py（92 事件，BGM＝VT-1 first+loop，第 8 小节落 HIT，节拍偏差中位 ~30 ms）；voice.py 混音（人声 -16 / 音效 -22 / BGM -26，duck 8 dB）
- 封面：cover/opt_{A,B,C}_tall_{zh,en}.jpg（3:4 三款）、thumb_16x9_{zh,en}.jpg、thumb_9x16_{zh,en}.jpg
- specs/vibetennis/vibetennis-net-dip-2026{,-en}.json＋.xhs.txt；data/vibetennis_episodes.json 登记 13
- 中文 3D 渲染进行中（r3d/seg，6 进程，日志 r3d/seg/w*.log）

## 待办
- 中文 v2（标签修正）：en_patch/zh_fix_v2.sh 后台；之后重跑 finalize.py＋qc.py
- 英文：en_patch/render_en.sh（局部重渲）→ en_patch/en_chain.sh 补缺＋合成英文（后台）
- QC：glow_check --pair、motion_check、qc.py、finalize.py；QC 静帧
- 分支 vibetennis-net-dip-2026 提交（不含 docs/vibetennis.md、mp4、node_modules）；不推微信、不合并

## 日志
- 11-22 03:05 glow_check --pair 13 帧＋2 帧：只有 25.0 s（扯断字强拍闪光，TE+0.28 s）gain 1.12 超标，25.2 s 已回到 0.50 ✓——属 ≤0.45 s 刻意闪光，豁免；静帧在 /workspace/scratch/glow
- 11-22 06:46 中文 3D 渲完（r3d/seg_zh，31 块）
- 11-22 08:17 中文成片合成完：vibetennis-net-dip-2026_push.mp4（日志 /workspace/ep13_assemble_zh.log）
- 11-22 08:32 中文 QC 全绿（qc.py 0 项不合格、motion_check 最大 11.9≤12、-14.8 LUFS/-3.1 dBTP），预览 /workspace/ep13_preview/；英文改为局部重渲：probe.js 逐帧比字 → en_patch/jobs.txt（6383 帧重渲、877 帧复用中文块），en_patch/render_en.sh 后台跑（日志 /workspace/ep13_en_render.log）
- 11-22 08:37 修：标题段「中央带／宽≤5厘米」标签被白带子挡住 → 挪到带子左侧（shots.js 215–216）；中文局部重渲 870–1000 帧（r3d/patch_zh），英文对应段需在英文渲完后重渲
- 11-22 08:40 本地提交 ac6afa9ae（分支 vibetennis-net-dip-2026，未推送；不含 docs/vibetennis.md、output/、mp4）
- 11-22 10:34 中文 v2 完成（标签修正）：vibetennis-net-dip-2026_push.mp4、预览 /workspace/ep13_preview/EP13_网中间矮_zh_preview_v2.mp4；旧版 *_v1；motion 见 /workspace/scratch/motion_zh_v2.log
- 11-22 10:43 第2步：v2 finalize.py＋qc.py 0 项不合格（-14.8 LUFS / -3.1 dBTP / 242.10s，film ded513b8）；motion_check 最大 12.0≤12、硬切 0（/workspace/ep13_tmp/motion_zh_v2.log）；海报已换 B（opt_B_tall_zh），spec cover 已改，旧 A 改名 *_A_v1
- 11-22 10:46 glow_check --pair 修正段 29.7/30.5/31.5/32.5s 全 ✓（gain ≤0.21；/workspace/ep13_tmp/glow）。下一步 release.py
- 11-22 10:47 第4步：release.py 已传 Release vibetennis-vibetennis-net-dip-2026（236.2 MB），写 copy.html；接着提交、推分支、开 PR
