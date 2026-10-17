# 动效与电影感出片规格（motion-spec）

> 账号所有者 2026-10-17「加一些出片工具」「同时要有电影或宣传片的质感」。
> 全部 **opt-in、spec 驱动**：不写就和原来逐字节一致。实现在 `tools/reel_cinematic.py`，
> 接线在 `tools/build_match_reel.py`，判据在 `tests/test_reel_cinematic.py`。

## 硬规矩（先看）

- **分一律原速。不慢放、不定格、不变速。**（账号所有者 2026-10-17 明令）`cinematic` 里没有任何变速键；
  推镜只放大不改帧数。原来的 `speed` 键在正常制作里本来就会被原声闸拦下。
- **不加配乐、不加音效**（risers / hits / whoosh 一律不做）。成片只有比赛原声＋旁白；BGM 由账号所有者后期自己垫，
  所以给了分轨导出。
- **全屏图表卡不做**（2026-10-17「不要动画卡」）。数据只走右上角标准角标。预告片卡只放一句话。
- 调色、颗粒、暗角**只作用于比赛画面段**：封面、章节卡、片尾、角标、字幕、品牌色都不被染。

## 1. 调色（grade）与逐源拉齐（match）

```json
"cinematic": {
  "grade": "teal_orange",        // teal_orange | moody | neutral
  "grade_strength": 0.8,         // 0~1，默认 1
  "match": {"iw21": {"exposure": -0.04, "temperature": 5800, "saturation": 0.95}}
}
```

- 预设是内建 ffmpeg 滤镜（`colorbalance` + `eq`），BtbN 和沙箱同一套，不依赖 .cube 文件。
- `match` 先把每条源拉到同一基线（曝光 −0.3~0.3、色温 3000~9000K、饱和 0.6~1.4），再统一上预设——
  不同赛事、不同转播的白平衡差异先抹平，整片一个色调。
- 链路顺序：`conform 放大(+锐化)` → `match` → 裁 3:4 → 铺画布 → `grade` → 暗角 → 颗粒 → 推镜 → 角标叠加。

## 2. 胶片颗粒与暗角

`"grain": 0~1`（`noise` 时域颗粒，0.3 左右肉眼可见不脏）、`"vignette": 0~1`（`vignette` 角度 0.25~0.98）。

## 3. 预告片式片头/片尾卡

段落：`{"title_card": "第七次 你押谁？", "kicker": "武汉", "title_style": "trailer", "seconds": 1.6}`

- 黑底、上下宽银幕黑边（各 11%）、金属细线、字距拉开，品牌字体（TL Display SC）。
- 只许一句话（沿用章节卡 18 字上限）——**它不是数据卡**。
- 画面占比：和章节卡一样算**非比赛画面**。dry-run 会打印 `[画面占比]`（`reel_cinematic.footage_ratio`）；
  非官方源在 spec 顶层 `_unofficial: {"源键": "为什么"}` 认领，官方占比不算它。
- 宽银幕黑边只在这张卡上出现；比赛画面照旧铺满 1080×1440。

## 4. 接缝转场

段落 `"transition_in"`（这一段**进场**那条接缝）：

| 值 | 效果 | xfade |
|---|---|---|
| `dissolve`（默认） | 原来的 0.18s 溶解 | `fade` |
| `cut` | 硬切（在溶解窗正中切） | `custom` |
| `flash` | 闪白 | `fadewhite` |
| `whip` | 甩镜模糊 | `hblur` |

- 时长一律沿用 `SEG_FADE`，长度账、旁白 `adelay`、字幕 cue 一处不变。
- 转场只落在**段与段之间**；段的边界本身已经过「一分打完再切」和「不切断解说」两道硬闸，
  所以转场不可能切断一分或一句解说。转场窗吃的是前一段的自然延续（tail）。
- 2×2 融合拼接（`reel_join_fusion`）认得这四种写法，不会掉回慢路。

## 5. 分轨导出（stems）

`"cinematic": {"stems": true}` → 成片目录多出三条 48 kHz/24-bit WAV，和成片逐样本对齐、同长：

- `<slug>.narration.wav`：只有旁白
- `<slug>.original.wav`：只有拼好的现场原声（增益 1.0，不闪避）
- `<slug>.mix.wav`：成片那条混音

本地落在成片目录（`.gitignore` 挡在 git 外）；runner 上落在 `$RUNNER_TEMP/stems/`，避开成片目录的大文件闸。要它们自动进 Release，需把
`docs/patches/match-reel-stems-release.patch` 应用到 `.github/workflows/match-reel.yml`（改 workflow 要带
`workflow` 权限的令牌，本次提交的令牌没有，所以留成补丁）。默认不带任何音乐。

## 6. 低清放大与锐化（白名单）

```json
"conform": {"iw21": "720p 官方集锦放大铺满"},
"conform_sharpen": {"iw21": "放大后轻度锐化"},
"source_quality_exceptions": {"<URL>": {"min_height": 720, "approved_by": "user", "reason": "…"}}
```

- `conform_sharpen` 三条都要满足：键在 `conform` 里（被放大）、理由非空、URL 在
  `APPROVED_LOW_RES_SOURCES` 白名单（账号所有者按 URL 点名）。1080p 源不许锐化。
- 锐化固定 `unsharp=5:5:0.6:5:5:0.0`（只锐亮度、轻度），不开放强度。

## 7. 反应镜头推近（Ken Burns）

段落 `"push_in": 1.0~1.15`：段内从 1.0 匀速推到该倍数，中心不变。

- 只给普通比赛画面段（反应、庆祝、看台）；跟拍、回贴记分条、图片/卡片段写了当场红。
- 带式版式（band）不推（会把上下带一起推）。
- 静态放大继续用原来的 `crop_zoom`。
