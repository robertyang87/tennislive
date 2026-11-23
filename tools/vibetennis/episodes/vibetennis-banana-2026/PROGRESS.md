# EP14 不是补钾（vibetennis-banana-2026）进度

时区：Asia/Shanghai。禁止：推微信、`push.auto=true` 的发布 PR、提交 `docs/vibetennis.md`、删除成品（覆盖前先改名备份）、付费 API。

## 口径（2026-11-23 审核后已锁）

资料包：`/workspace/tennislive/papers/vibetennis-banana-2026/{sources.md,storyboard.md}`
备份：`sources.md.bak-20261123-audit`、`storyboard.md.bak-20261123-audit`

标题仍用「不是补钾」。关闭句不用绝对的「补的是糖，不是钾」，改为：钾是真的，防抽筋还没有被证明；27 克碳水才是更站得住的理由。只上台账里的强／中主张。

## 已完成

- 旁白 `narration.json` 35 句；TTS 云健 +18%（`voice/`）；`plan.py` TOTAL **253.47 s**，HIT 13.051
- `r3d/src/shots.js` + `build.py` 已组装 `r3d/scene.js`；香蕉模型改过（平滑管体＋三瓣皮，钩子段侧面构图）
- `sfx.py` / `voice.py`：人声 −16、音效 −22、BGM −26 LUFS，混音约 −16.2，床在 `sfx/sfx_bed_zh.wav`
- 封面 A/B/C 的 3:4、16:9、9:16 已出（`cover/opt_*_zh.jpg`）；片头用 `cover/thumb_16x9_zh.jpg`
- 看门狗：`render_zh.sh`（STALL=600，MAXT=5400，TRIES=3，K=4，端口 8780）
- 段文件在 `/tmp/ep14_seg`，`r3d/seg` 为指向它的符号链接

## 渲染（已完成）

- 进程：`bash render_zh.sh` pid **343707**（2026-11-23 13:58 左右启动）
- 共 32 段（0–7604 帧，每段 240 帧）
- 2026-11-23 **15:59** 中文 3D **32/32 段全部完成**（render_zh.sh 已退出）。32/32 完成。**assemble.sh zh** pid 394347：overlay 已完成（r3d/full_ov_zh.mp4，7604 帧，910 MB，16:05）。16:09 正在 vfx → r3d/full_vfx_zh.mp4。不要重开 assemble。
- 进行中：1200、1440、1920、2160。文件仍在增长，未见卡死。
- 预置：`VT_PRESET=veryfast VT_CRF=14`
- 注意：4 路 swiftshader 会把 8 核打到高负载，后期段约 3–7 s/帧。若某段 **10 分钟文件大小不增长**，只杀该段进程组并重试，不要新开整片渲染。

## 待做

1. 等 32 段全部带 `.anchors.json`
2. `bash assemble.sh zh`（overlay + vfx + 混音到 −14 LUFS，真峰值 ≤ −1 dBTP，片头 3 帧封面）
3. 自检：`qc.py` 0 failures、`motion_check`、contact sheet、抽帧看片、台账核对每一个上屏数字、多音字
4. 720p 预览放到 `/workspace/ep14_preview/`
5. 中文汇报路径、时长、响度、质检和已知瑕疵；**不推微信、不开自动发布 PR**


## 合成（已完成，2026-11-23 16:21 CST）

- `assemble.sh zh` pid 394347 已正常退出（done）。
- overlay：`r3d/full_ov_zh.mp4` 7604 帧，910 MB
- vfx：`r3d/full_vfx_zh.mp4`，4 flares + 6 sweeps
- 混音：late max 0.00 s；人声/音效/BGM −16.0/−22.0/−26.0 LUFS，mix −16.2，再归一到成片
- `vibetennis-banana-2026_master.mp4` 1.4 GB（1413644762 B），253.53 s / 7606 帧（正文 7604 + 片头约 2 帧封面）
- `vibetennis-banana-2026_push.mp4` 237 MB（247766000 B），7500 kbps
- 响度（assemble ebur128）：**−14.8 LUFS / 真峰值 −4.2 dBTP**（两条一样）
- 装配 contact sheet：`contact_sheet_zh.jpg`
- 自检进行中：motion_check 已在后台跑；接着 qc.py、抽帧看片、台账对数字、720p 预览。不推微信、不开自动发布 PR。


## 自检与修正（进行中，2026-11-23 16:36 CST）

assemble 第一版成片：push 237 MB / 253.53 s / −14.8 LUFS / −4.2 dBTP。未推送。

已发现并在修：
- motion_check 3 处不合格：8.00 s 段缝（c00000/c00240 光照跳变 19.0；将在成片上做 8 帧 fade-to-R）；141.33 s 单帧闪白（c04080 第 160 帧，将用前后帧平均替换）
- 多音字：p0「部分」改为「果肉」；k3/e4 避开「差」。voice_check 已 0 不合格。新配音床已出（late max 0.13 s）
- 字幕：GI 行去掉易误解的「生香蕉」；0.7 g·kg⁻¹·h⁻¹ 改成 0.7 g/kg/h（字体缺上标）
- 片尾 422 mg 与 27 g 叠在一起：shots.js 已把钾标淡出改为完全淡出，正在重渲 c06960 / c07200 / c07440（旧段备份在 /tmp/ep14_seg_bak_endfade）
- 待：三端段完成 → 重跑 overlay + vfx → 补段缝和闪白 → 混音出 master/push → qc.py / motion_check / 720p 预览

已知暂不重渲的瑕疵：
- 试验段 McRae 卡在 Nieman / 空卡出现后仍留在画面中间，有叠字
- 钠钾段「盖得住这次钾损失…」与钾柱接近
- 补糖段大号 27 g 压到 30–60 g/h 说明上
- 片头 0.1 s 封面（与前集成片流程相同）


## 叠字必须修（2026-11-23 17:00 CST）

所有者要求画面精美酷炫，原先「暂不重渲」的三处叠字改为必修。这三处都在 3D `shots.js`（不是 overlay.py 字幕），只重渲相关段：

- 钠钾「盖得住这次钾损失…」下移到 y=−2.42、字号 0.28，避开短钾柱。段：c02160、c02400
- 补糖大号 27 g 上移到 yb+1.60，避开「30–60 g/h」说明。段：c03840
- 试验卡：`trial()` 增加透明度系数；McRae 随 phase2 淡出，Nieman 在空卡出现前淡出。段：c05040、c05280、c05520、c05760

备份：`shots.js.bak-overlap-20261123`、`/tmp/ep14_seg_bak_overlap`
片尾淡出、多音字、GI 用词、上标、段缝/闪白补丁仍保留。
`finish_v2.sh` 的段缝补丁（ffmpeg 426967）先让它跑完，不要重开；补丁结束后停掉 finish_v2 的成片编码，先重渲上述 7 段，再 overlay + vfx + 补丁 + 混音 + qc。

## 叠字第二轮（2026-11-23 17:18 CST）

第一轮 7 段重渲：钠钾/补糖段（c02160、c02400、c03840）和试验首段 c05040 已完成；试验后三段 c05280 / c05520 / c05760 正在渲（约 17:12 开第二波）。

抽帧核过第一轮钠钾/补糖：
- 大号 27 g 与「30–60 g/h」说明已经错开（这一处第一轮有效）。
- 但「大概刚够下限」仍压在右上角 120 s / 盘间上。
- 「盖得住这次钾损失…」仍压在柱脚「钾」上。原因：`layoutText()` 会把 y<−1.95（字幕带）的字抬回 y≈−1.95，第一轮把 sMiss 下移到 −2.42 等于白做。

已改（`shots.js.bak-overlap2-20261123`，scene.js 已重建；正在跑的 McRae 三段仍用开渲时载入的旧 scene，不受影响）：
- 钠/钾柱脚标签挪到柱子侧面；「一根香蕉 422 mg 钾」上移；判语拆成两行，放在右下安全区 (2.25, −1.12) / (2.25, −1.50)，不再进字幕带。
- 27 g 标记线改为 HUD `hline`（与数字对齐）；「大概刚够下限」改到 27 g 左侧；「一小时一根…」收到 y=−1.68。

`finish_v3.sh`（只在等 anchors、尚未 overlay）已停，避免用仍叠字的钠钾/补糖段合成。备份：`/tmp/ep14_seg_bak_overlap2`。待 McRae 三段完成并抽帧确认后，再重渲 c02160 / c02400 / c03840（`render_overlap2.sh`），然后 `finish_v4.sh`：overlay → vfx → 段缝/闪白补丁 → 混音 master/push → qc / motion_check / 720p 预览。不推微信。

## 叠字第二轮开渲（2026-11-23 17:24 CST）

抽帧确认：McRae 中卡已按 phase2 淡出，但 Vergauwen / Mitchell 侧卡滑出画面后被 `layoutText()` 拉回左右安全区，一直留到 Nieman 和空卡上；Nieman 卡中间的成绩行也被挤掉。已改为两侧与 McRae 一样按 fade 淡出，不再滑出。

`render_overlap2.sh`（pid 442006）正在重渲全部 7 段：c02160 / c02400 / c03840 / c05040 / c05280 / c05520 / c05760。备份在 `/tmp/ep14_seg_bak_overlap2`。第一波 cap.js：2160、2400、3840、5040。

`finish_v4.sh` 等这 7 段出 anchors 并抽帧核过后再开，避免再用未核过的段合成。不推微信。

## 抽帧核第一波 overlap2（2026-11-23 17:35 CST）

钠钾右下两行判语已离开钾柱，不再叠字。补糖 27 g 与 30–60 g/h、120 s 已错开，标记线与数字对齐。但「一小时一根，不是五盘的全部」压在刻度 30 上；对照卡进入后「抽筋」压住 1,565 mg。shots.js 已再改：fAll 上移到刻度上方 y=−0.92；柱状图和判语在对照卡出现时淡出。待 proof 后三段完成并核过 Nieman/空卡后，再重渲 c02160 / c02400 / c03840，然后才跑 finish_v4。

## Nieman 成绩行缺失（2026-11-23 17:41 CST）

proof 后三段重渲后：Vergauwen / Mitchell / McRae 已正确淡出，空卡干净。但 Nieman 卡中间「香蕉 2 小时 41 分 · 等量碳水饮料 2 小时 36 分 · 没有明显差别」仍不出现。原因是 `trial('n')` 的 body 键是 `nb`，后面「更饱、更胀」也用了 `lab('nb')`；`tx()` 按键缓存，后一次每帧把 opacity 置 0。已改名为 `nBlo`。

`render_overlap3.sh`（pid 451801）重渲 6 段：c02160 / c02400 / c03840（柱图淡出 + fAll 上移）以及 c05280 / c05520 / c05760（成绩行）。备份在 `/tmp/ep14_seg_bak_overlap3`。c05040 保留 overlap2 成品。核过再跑 finish_v4。不推微信。

## overlap3 前四段抽帧（2026-11-23 17:51 CST）

c02160 / c02400 / c03840 / c05280 已核过（c05520、c05760 仍在渲）：
- 钠钾 73 s：右下两行「盖得住这次钾损失 / 盖不住那些钠」离开钾柱，不叠字。
- 钠钾 82 s、86.5 s：对照卡出现后柱状图和 1,565 mg 已淡出，「抽筋 / 对照 / 血清钾：没有可靠差别」干净。
- 补糖 132 s：27 g 与 30–60 g/h、120 s 错开，标记线与数字对齐，「大概刚够下限」在 27 g 左侧。
- 补糖 134.5 s：「一小时一根，不是五盘的全部」在指南说明和刻度条之间，不再压住 30。
- Nieman 176.8 s、182 s：成绩行「香蕉 2 小时 41 分 · 等量碳水饮料 2 小时 36 分 · 没有明显差别」已出现，侧卡已淡出。

待后两段完成，核 188 s 饱胀说明和 196 s 空卡后启动 finish_v4。不推微信。

## 启动 finish_v4（2026-11-23 17:56 CST）

overlap3 6/6 已于 17:53:15 CST 完成。后两段抽帧：
- 188 s：Nieman 成绩行仍在，「吃香蕉的人更饱、更胀」在卡下方，无侧卡叠字。
- 195 s：Nieman 开始淡出，文字仍完整。
- 196.8 s：空卡「网球场上，还没找到香蕉对照试验」干净。

三处指定叠字及后续发现的对照卡压字、Nieman 成绩行缺失均已修好。已启动 `finish_v4.sh`：overlay → vfx → 段缝/闪白补丁 → 混音 master/push → qc / motion_check / 720p 预览。不推微信、不开自动发布 PR。

## finish_v4 进行中（2026-11-23 18:13 CST）

- overlay：7604 帧，253.466667 s，909 MB（18:00:05）
- vfx：4 flares + 6 sweeps，1.3 GB（18:05:49）
- 段缝/闪白补丁已写入 `r3d/full_vfx_zh.mp4`（18:10:03）：frames 232–239 fade-to-R，frame 4240 用前后帧平均替换
- 正在编 master（crf 16）。随后 2-pass push、motion_check、finalize、qc.py、720p 预览。不推微信。

## 段缝补丁实际未生效（2026-11-23 18:26 CST）

finish_v4 已编出 master / push（−14.8 LUFS / −4.3 dBTP），但 motion_check 在 8.10 s 仍报跳变 18.9（`set -e` 使后续 qc / 预览未跑）。闪白（原 141.3 s）已不在前五。

核对：`patch_vfx.py` 用 overlay+enable，重编码后 239→240 与未补丁几乎相同（平均差约 1，属于压缩误差），补丁等于没贴上。已改为 trim+concat（`patch_vfx2.py`）。混合后 239→240 的 320 灰度差为 0.00，淡化段最大 4.11。正在把补丁写入 `r3d/full_vfx_zh.mp4`，随后 `finish_v5.sh` 重编成片并跑 qc。v4 失败成片备份为 `*_v4_seamfail.mp4`。不推微信。

## finish_v5 进行中（2026-11-23 18:44 CST）

concat 段缝补丁已写入 `r3d/full_vfx_zh.mp4`（7604 帧，253.466667 s）。补丁后 7.4–8.4 s 最大帧差 4.34。`finish_v5.sh`（pid 479406）已于 18:41:16 编完 master（1.3 GB），正在做 2-pass push，随后 motion_check / finalize / qc.py / 720p 预览。不推微信。

## 成片完成（2026-11-23 18:47 CST）

`finish_v5.sh` 于 18:46:47 CST 结束。concat 段缝补丁生效：motion_check **0 处跳变**（最大 55.93 s = 9.1，低于门槛 12）。qc.py **0 项不合格**。未推微信、未开 push.auto PR。

成片路径与指标：
- 发布用 push：`/workspace/tennislive/tools/vibetennis/episodes/vibetennis-banana-2026/vibetennis-banana-2026_push.mp4`（247,805,657 B，237 MB，1920×1080，30 fps，253.57 s）
- master：同目录 `vibetennis-banana-2026_master.mp4`（1,387,456,961 B，1.3 GB，crf 16）
- 交付副本：`/workspace/tennislive/output/2026-11-23/vibetennis/vibetennis-banana-2026/vibetennis-banana-2026.mp4`（与 push 字节一致）
- 720p 预览：`/workspace/ep14_preview/EP14_zh_preview_720p.mp4`（79 MB）
- 总览与抽帧：`/workspace/ep14_preview/contact_sheet_zh.jpg`、`/workspace/ep14_preview/review/`
- 海报：`output/2026-11-23/vibetennis/vibetennis-banana-2026/poster.jpg`（方案 B，2160×2880）
- 响度：−14.8 LUFS / 真峰值 −4.3 dBTP（master 与 push 相同）

指定三处叠字已在成片中核过：钠钾判语离开钾柱；27 g 不压 30–60 g/h；McRae 不再留在 Nieman/空卡上，Nieman 成绩行完整。台上数字与台账一致（118 g、27 g、14 g、3 g、105 kcal、422 mg、GI 51、1,565 / 194 mg、30–60 与 60–90 g/h、McRae 68/66 与 65/61、Nieman 2h41 / 2h36 等）。

仍有的小瑕疵：
- 约 239.6 s 片尾 422 mg 与 27 g 有约 0.8 秒交叉淡出（随后只留 27 g）
- 补糖刻度右端「90 g/h」略贴画框边缘
- 成片前有 0.1 秒 16:9 封面帧（与前集成片流程相同；qc 已通过）
