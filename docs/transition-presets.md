# 转场动画库

账号所有者 2026-10-27：「多准备一些转场动画作为过渡效果，后续做视频需要的时候直接套用」。

代码：`src/tennislive/video/transitions.py`（`PRESETS`），剪辑片的拼接图 `build_match_reel.dissolve_filtergraph` 按段套用。
样片：`python3 tools/preview_transitions.py --out /tmp/transitions.mp4`。每个预设播两遍，先是真实速度，再慢放 4 倍。

## 怎么用

在 spec 的某一段上写 `"transition": "<名字>"`，表示**接进这一段**的那个接缝用这个动画。

```json
{"source": "uso26", "start": 137.4, "end": 146.5, "transition": "memory", ...}
```

- 不写 `transition` 就是默认的 `dissolve`（溶解），存量片子一条都不受影响。
- 第 1 段的 `transition` 管的是封面到第 1 段那一刀。接进片尾那一刀固定溶解。
- 名字写错时 `--dry-run` 会报错，并列出所有能用的名字。

## 预设

| 名字 | 中文 | 什么时候用 |
|---|---|---|
| `dissolve` | 溶解 | 默认。同一场里两个回合之间，不想让人注意到剪辑的地方 |
| `slide_left` | 左推 | 时间往前走：下一盘、下一场、下一年 |
| `slide_right` | 右推 | 倒回去：插叙一段更早的比赛 |
| `slide_up` | 上推 | 从比赛画面推到数据卡、字卡 |
| `slide_down` | 下推 | 从字卡落回比赛画面 |
| `smooth_left` | 柔推 | 比左推更软的推进，用在情绪段之间 |
| `whip` | 快甩 | 同一场里跳到下一个关键分，带一点速度感 |
| `iris` | 圈开 | 揭晓：赛点、结果、捧杯那一下 |
| `iris_close` | 圈收 | 收束：一段故事讲完，收进下一段 |
| `clock` | 时钟扫 | 时间流逝：伤停、空白期、几个月之后 |
| `memory` | 褪色回忆 | 切进历史画面：当年那场、多年以前 |
| `diagonal` | 斜切 | 两个人、两条线对照着讲 |
| `reveal_left` | 擦出 | 干净利落地换场：换赛事、换人物 |

**用法上的克制**：动画是给叙事转折用的，不是每一刀都换。一条片子里大多数接缝仍然是溶解，只在时间跳转、插叙、揭晓这类地方用。同一个动画连用三次以上，就成了噪音。

## 两条硬边界

1. **时长固定 0.18 秒（`SEG_FADE`），只换形状。** part 多切的溶解底料、旁白 adelay、字幕 cue、现场声 `acrossfade`、死球后的 ghost 检查，全都按 0.18 秒记账。0.18 秒在 60 fps 上是 11 帧，推、甩、圈开都看得清（2026-10-27 逐帧量过）。
2. **中间一帧黑都不许有**（老规矩，「接缝画面的时候有轻微的闪烁」）。所以 `fadeblack`、`fadewhite`、`zoomin`、`pixelize` 不收：`zoomin` 在 0.18 秒里会把前一画面放大成满屏一块纯色，观感和闪一下一样。判据 `tests/test_transitions.py::test_每个转场中间都不闪黑不闪成一块纯色` 会真跑 ffmpeg 逐帧量。同一把尺子反向量过，`fadeblack`、`fadewhite`、`zoomin` 都能被拦下。要加新预设，先过这一条。

## 覆盖范围

- **剪辑片**（赛场之上、网球有故事的剪辑片，`build_match_reel.py`）：已接入。
- **赛后开麦**（`build_interview_clip.py`）、**字卡解说**（`explainer.py`）：仍然只用溶解。采访片是连续的一段原声，不适合换场动画。字卡线以后要用时，接同一个 `PRESETS`，不要另起一份名单。
- **转场卡**（章节卡、数据卡里的动画）是另一回事，见 [全局转场卡方案](global-transition-cards.md)。它管的是卡片本身怎么动；这份文档管的是段与段之间那一刀怎么接。
