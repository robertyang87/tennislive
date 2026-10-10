# 德约科维奇 21 个赛季 v2 · 配音试听

2026-10-10。给主代理 `djokovic-21-seasons-2026-v2` 用。三句只测声音，事实不在这里核。

后端：这台机器没有 `AZURE_SPEECH_KEY`，九条都是 **edge-tts 7.2.8**、`zh-CN-YunjianNeural`、`boundary=WordBoundary`。这就是 `src/tennislive/video/tts.py` 里 `_tts_one_uncached` 在没有 Azure 时走的那条路。喂给合成器的年份把 `〇` 换成 `零`（`pronounce.py` 的 `ling` 那一行，`speakable()` 会做同一件事）。

## 推荐

**用 B。** 云见，语速 `+18%`，音高 `+10Hz`，落点单独成句（句号，不跟前一句逗号连读）。

| | |
|---|---|
| voice | `zh-CN-YunjianNeural` |
| rate | `+18%` |
| pitch | `+10Hz` |
| style / styledegree / lead_pause | 留空 |

男声只有四把：云见 Passion、云希 Lively、云扬 Professional、云夏 Cute。云见已经是 Passion 那把。云希偏亮、偏年轻，不适合「执念」。`style` 和 `lead_pause` 只有 Azure 有；edge-tts 会把 `<break>` 当字读出来，而且 `tts.py` 在没 Azure 时见到这两个键会直接抛错。栏目基调表里「网球有故事」也是空风格（`azure_tts.COLUMN_BASE_STYLE`）。

B 相对现行 `+6%` 的差别，是三件同时发生的事：整段稍快、整段略高、落点前面多停一拍。句号把落点从上一句拆开之后，WordBoundary 上「纳达尔 → 他」的空隙从逗号版的约 0.31 秒变成约 0.50 秒。同一句「追费德勒」在逗号版稳定切成 `追费｜德勒`，句号版切成 `追｜费德勒`。

## 怎么接进渲染

这条是「网球有故事」的剪辑片，走 `tools/build_match_reel.py`，不是字卡那条 `explainer`（字卡默认已经是 `+22%`）。剪辑片默认就是被嫌弃的云见 `+6%`。

1. **语速，一个开关。** 渲染命令加 `--rate +18%`。工作流入口是 `.github/workflows/match-reel.yml` 的 input `rate`（现在的 default 是 `+6%`）。代码默认在 `tools/build_match_reel.py` 的 `render` 子命令 `--rate`（约第 11549 行）。封面和片尾跟这个全局语速走（`synth_cover` / `synth_outro`）。
2. **音高，写在每一段旁白上。** 剪辑片没有全局 `--pitch`。`synthesize()` 用的是 `seg.voice_pitch or "+0Hz"`。每一段有旁白的 `segments[]` 写成：

```json
"voice": {
  "pitch": "+10Hz",
  "_why": "2026-10-10 试听 B：云见 +6% 听感平，正文抬 10Hz。见 research/djokovic-21-seasons-2026-v2/voice_trials.md"
}
```

`_why` 必填，否则 `--dry-run` 会红。不要写 `style`，也不要写 `lead_pause`。
3. **封面和片尾仍是 +0Hz。** `synth_cover` 和 `synth_outro` 只把 `voice, rate` 传进 `tts_one`，不传 pitch。正文抬了 10Hz、封面没抬，两处会差一截。要一起抬，改这两个函数，给 `tts_one` 补上 `pitch="+10Hz"`。位置：`tools/build_match_reel.py` 的 `synth_cover`（约第 5617 行）和 `synth_outro`（约第 5650 行）。
4. **落点用句号断开，** 旁白原文就这么写。字幕会去掉标点，停顿只留在声音里。三句的 B 稿：

- 二〇一一年。四十一连胜。那一年，他不是在追费德勒和纳达尔。他是把他们甩在了身后。
- 两个赛点。对面是费德勒。中央球场几乎都在为对手欢呼。他一分一分地扛了下来。
- 三十九岁，还在拿冠军。这已经不只是天赋了。这是一种不肯停下的执念。

字卡线如果改走 `tennislive explainer`：`--voice zh-CN-YunjianNeural --rate +18% --pitch +10Hz`（`src/tennislive/cli.py` 的 `explainer` 子命令）。那条线的代码默认是 `+22%` / `+0Hz`（`explainer.DEFAULT_RATE`）。

## 三个候选

音色三档都是云见。A、B 是 edge-tts 原文件。C 是分句合成后去掉首尾静音、句间垫 0.32 秒再接上的，编码是 lame 48 kbps。

### 示例 1

「二〇一一年。四十一连胜。那一年，他不是在追费德勒和纳达尔，他是把他们甩在了身后。」

| 文件 | 参数 | 时长 | 合成文本 |
|---|---|---|---|
| `s1-a-control.mp3` | rate `+6%`，pitch `+0Hz` | 8.35s | 原文，逗号连着落点 |
| `s1-b-drive.mp3` | rate `+18%`，pitch `+10Hz` | 7.94s | 落点前改句号 |
| `s1-c-punch.mp3` | 见下 | 7.61s | 两句分开合成 |

C：前句 `+6%` `+0Hz`；静音 0.32s；「他是把他们甩在了身后。」`+24%` `+12Hz`。

### 示例 2

「两个赛点。对面是费德勒，中央球场几乎都在为对手欢呼。他一分一分地扛了下来。」

| 文件 | 参数 | 时长 | 合成文本 |
|---|---|---|---|
| `s2-a-control.mp3` | rate `+6%`，pitch `+0Hz` | 7.75s | 原文 |
| `s2-b-drive.mp3` | rate `+18%`，pitch `+10Hz` | 7.61s | 「费德勒」后改句号 |
| `s2-c-punch.mp3` | 见下 | 6.57s | 两句分开合成 |

C：铺垫整句 `+6%` `+0Hz`；静音 0.32s；「他一分一分地扛了下来。」`+24%` `+12Hz`。

### 示例 3

「三十九岁，还在拿冠军。这已经不只是天赋了，这是一种不肯停下的执念。」

| 文件 | 参数 | 时长 | 合成文本 |
|---|---|---|---|
| `s3-a-control.mp3` | rate `+6%`，pitch `+0Hz` | 7.30s | 原文 |
| `s3-b-drive.mp3` | rate `+18%`，pitch `+10Hz` | 7.10s | 「天赋了」后改句号 |
| `s3-c-punch.mp3` | 见下 | 6.37s | 三句分开合成 |

C：「三十九岁，还在拿冠军。」`+4%` `-2Hz`；静音 0.32s；「这已经不只是天赋了。」`+14%` `+6Hz`；静音 0.32s；「这是一种不肯停下的执念。」`+24%` `+12Hz`。

## 为什么不推荐 C 当全片默认

C 把落点单独加快、加重，试听里反差最大。渲染器一段旁白只有一套 `rate` / `pitch`（`synthesize()` 每段调用一次 `tts_one`）。要复现 C，得把落点拆成下一段，并在那段写：

```json
"voice": {
  "rate": "+24%",
  "pitch": "+12Hz",
  "_why": "落点单独加快加重。铺垫段保持全片 --rate。"
}
```

段与段之间是画面切点，不会自动垫这 0.32 秒气口。全片都拆开，节奏会碎。C 留作某一两句落点要特别顶上去时的写法，不作为全片基调。

## 可调参数在哪

| 旋钮 | 谁认 | 这条片子怎么用 |
|---|---|---|
| voice | `match-reel.yml` input `voice`；`build_match_reel.py render --voice` | 保持 `zh-CN-YunjianNeural` |
| rate | 同上，`--rate`；段级 `voice.rate` 盖过全局 | 全局 `+18%` |
| pitch | 段级 `voice.pitch`，形如 `+10Hz`。封面/片尾函数不收 | 旁白段 `+10Hz` |
| 停顿 | 旁白标点。edge-tts 不收 SSML `<break>` | 落点前用句号 |
| style / styledegree | 段级 `voice.style`，只在 Azure；须同时写 `_heard` | 不用 |
| lead_pause | 段级，0–2 秒，段首真 `<break>`，只在 Azure | 不用 |
