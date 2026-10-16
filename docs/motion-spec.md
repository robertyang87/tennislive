# 网球时差 · 动效规格（草稿）

> 本文的动效命名与部分参数改编自 **Motion Prompt**（https://github.com/showheyohtaki/motion-prompt），
> MIT License, Copyright (c) 2026 Shohei Ohtaki。编号 #NNN 对应原库条目。
> 原许可要求保留版权与许可声明；本文只借用规格文字，不含原库代码。

## 0. 通用约束（所有动效都必须满足）

- 画布 **1080×1440**、30fps；渲染方式：HTML 页暴露确定性的 `window.renderAt(t)`（只由 t 决定画面，无 CSS transition / requestAnimationFrame / 随机数），Playwright 逐帧截图 → ffmpeg（libx264, yuv420p, crf 16）。
- 风格：苹果发布会式——深色底 `background #080e1d`，可加一层 `hero-glow #304d76` 低透明径向光；**一屏只一个强调色：黄绿 `#c6f65a`**；正文 `#f4fbf7`，次级 `#cfe6d8`，元信息 `#a9bcb2`，面 `card #15243a`（均出自 `src/tennislive/design_tokens.py`）。
- 字体：中文与标题用品牌标题同款 `NotoSansSC-Bold-sub.ttf`（正文 Regular）；**只有比分 / 数字**用 `BarlowCondensed-Bold.ttf`（`assets/fonts/`），数字等宽（`tabular-nums`）、右对齐，滚动时不左右抖。
- 角标（**只用于贴在比赛画面上的叠加字卡**；全屏图表卡 / H2H 交手卡一律不用角标，账号所有者 2026-10-16：「这种字卡是在视频里贴的」）：右上角，距上/右 72px，右侧 8px 黄绿竖条，文字右对齐；行序固定 **主题 / 日期+赛事 / 比分 / 人物**。
- 比分：每盘胜方局数用黄绿，负方用正文色，抢七小分 `(4)` 用元信息色。
- 缓动只用三种：`easeOutCubic = 1-(1-p)^3`（进场）、`easeOutQuart = 1-(1-p)^4`（数值）、`spring(u)=1-e^(-7u)·cos(14u)`（弹入）；落定回弹 `1+0.07·e^(-7u)·cos(15u)`。禁止线性进场、禁止 >8% 的超调。
- 质检：最后一帧上的所有数字必须与 spec / 旁白定稿逐字相等（渲染脚本断言，失败即不出片）。动效不得遮挡官方画面主体超过 0.6 秒。

## 1. 动效清单

| # | 名称（原库） | 参数 | 何时用 |
|---|---|---|---|
| M1 | 角标进场（#004 Line draw + #002 Stagger） | 竖条高度 0→100%，0.05–0.50s，easeOutCubic；四行依次淡入+右移 24px→0，行间隔 0.06s，每行 0.30s | 比赛画面上的右上角叠加字卡（全屏图表卡不用） |
| M2 | 大数字弹入（#001 Pop-in） | scale 0.85→1 按 spring，opacity 0→1 于前 0.2s；transform-origin 左中 | 「6—0」「150 胜」这类标题数字 |
| M3 | 列表依次弹入（#002 Stagger） | 每行起点 0.8s + i·0.18s；opacity 0→1（0.18s），translateY 30px→0 按 spring | 交手记录、赛程、名单（≤8 行） |
| M4 | 数字滚动（#007 Count-up） | 值 = round(目标·easeOutQuart(p))，时长 1.2s；起点晚于所在面板进场 0.2s；千分位、等宽 | 盘数局数、积分、奖金、胜场 |
| M5 | 落定回弹（#010 Overshoot） | 数到终值瞬间 scale = 1+0.07·e^(-7u)·cos(15u)，约 0.5s 衰减到 1 | 紧接 M4；每屏最多一处 |
| M6 | 条形生长（#009 Easing） | 宽度 0→目标，0.9s，easeOutCubic；多根时间隔 0.12s；只有关键那根用黄绿，其余 `muted #20324e` | 积分榜、排名、数据对比 |
| M7 | 遮罩揭示（#005 Mask reveal） | 文字从右向左揭开（clip-path inset），0.45s，easeOutCubic | 比分卡、结论句、引语 |
| M8 | 扫光（#022 Light sweep） | 45° 白色 18% 透明高光带，宽 120px，0.6s 扫过一次，不循环 | 冠军 / 纪录数字落定后点睛，每片 ≤2 次 |
| M9 | 定格+比分卡（#040 Freeze frame） | 赛点击球帧定格 0.8–1.2s，叠 M7 比分卡；定格时长计入"官方画面"统计 | 赛场之上的赛点、关键分 |
| M10 | 变速（#038 Speed ramp） | 1.0x→0.4x 于 0.25s，保持 ≤1.0s，0.25s 回 1.0x；声音保持原速或静音 | 制胜分、救赛点回合 |
| M11 | 溶解转场（#044 Cross dissolve） | `xfade=fade`，0.3s；旁白不动（沿用 explainer.py 现有实现） | 段落之间；禁止花哨转场 |
| M12 | 匹配剪辑（#042 Match cut） | 两段同动作 / 同构图硬切，零时长 | 历史与今天对照（如 2019 vs 2025 同一人） |

## 2. 参考实现

- 试点：`/workspace/motion-pilot/card.html` + `render.py`（奥斯塔彭科对斯瓦泰克六战交手卡，用了 M1–M5）。
- 接入建议：新建 `src/tennislive/video/motion_frames.py`，供 `explainer.py` 图表屏输出动画片段，其余屏仍走静态截图。

## 3. 质感参数（v2，2026-10-16）

| 项 | 参数 |
|---|---|
| 底 | 纵向渐变 #0a1222 → #060a14 → #04060c |
| 光晕 | 上方 1400×1100 径向 #2c4a78aa→透明，blur 30px，缓慢漂移 ±60px；左下 1100×900 #3a5f9a55，blur 40px |
| 暗角 | radial 130%×95%，55% 起渐变到 #000000b0 |
| 颗粒 | 296×384 灰度噪点放大到画布，opacity 0.06，overlay；种子 = 帧号，可复现 |
| 毛玻璃卡 | 渐变 #ffffff12→#ffffff06，1px #ffffff1c 描边，圆角 28px，内高光 inset 0 1px #ffffff26，阴影 0 2px 6px #0006 + 0 24px 60px #0008，backdrop blur 24px |
| 字 | 大数字 Barlow Bold 330px、字距 -12px、强调色外发光 0 0 60px #c6f65a40；说明字 NSR 24px、字距 6–8px、#a9bcb2；比分分隔用 84×16 圆角条（55% 白），不用"—"字形 |
| 进场 | expo-out 1−2^(−10p)，0.7–1.0s；opacity 0→1 + y 12–40px→0 + blur 8–24px→0；层级错开 0.07–0.12s |
| 扫光 | 6—0 上 110px 宽、−20° 斜、#ffffff55 高光，0.7s ease-in-out 扫一次 |
| 镜头 | 全舞台 scale 1.00→1.03（ease-in-out，整段时长），原点 50% 38%；画面元素离下边至少 60px，防止推镜后出画 |
| 运动模糊 | 60fps 渲染，ffmpeg `tmix=frames=2,fps=30` |
| 结尾 | 数字落定（回弹 1+0.05·e^(−6u)·cos(14u)）后静止 ≥1.2s |

## 4. H2H 头像（v3）

- 素材：只用 WTA 官方半身抠图（`Surname-Torso_<id>.png`，两人须同一批次），文件名带 WTA ID。
- 版式：左＝比分在前的一方，右＝对手；圆盘 260px，底 radial #2a3f63→#121c30，内高光 inset 0 2px #ffffff30，外环 1px #ffffff22 + 8px #ffffff08，阴影 0 30px 60px #000a；靠内侧一边加 rim light inset ±6px 18px #cfe6ff66。抠图宽 450px、顶 6px（脸占圆盘约 40%）。
- 名字在头像下方 34px，下面国家 20px 英文、字距 4px、#8d9e96。
- 进场：头像 0.3s / 0.42s 起，从两侧各 120px 滑入 + blur 22px→0（expo，1.0s）；比分 1.0s 起落定，必须晚于头像。
- 全屏 H2H 卡没有角标：头像区顶边 y≈190，表格 640、数字卡 1060，上下留白大致相等（v4）。
