# 罗马 2025 同类事件：官方素材取证与剪辑窗口

检索 / 实际下载日期：2026-10-05（UTC）。此资料是内部制作证据，非发布文案。

## 已取得的官方源

- 官方发布者：Tennis Channel（`@TennisChannel`）。是持权转播方官方账号，非转载账号。
- 正确原帖：<https://x.com/TennisChannel/status/1921973328903860370>。
- yt-dlp 返回的 `webpage_url`：<https://twitter.com/TennisChannel/status/1921973328903860370>。
- **不要使用**初次线索中的 `1921972358131028099`：本任务并未核实该 ID。
- 原帖视频 media ID：`1921973159768559616`。media ID 与帖子 ID 不相同，不能拼成帖子链接。
- yt-dlp 标题：`Tennis Channel - Mirra Andreeva hit a winner but was forced to replay the point after ...`。
- 原帖完整文案：`Mirra Andreeva hit a winner but was forced to replay the point after the court lights turned on mid-rally. Do you agree with the umpire's call? 🤔 #IBI25 https://t.co/1KcxQyrtv7`。
- 返回的发布日期：2025-05-12；时间戳 `1747069124` = **2025-05-12 16:58:44 UTC**。
- 1080p MP4 解析直链（仅作 fallback/provenance）：<https://video.twimg.com/amplify_video/1921973159768559616/vid/avc1/1920x1080/Zg2l5SYxE4pKO_oK.mp4?tag=16>。
- scratch 原片：`/workspace/scratch/sun-replay/rome.mp4`，**不进入 Git**。
- SHA-256：`a2833fecdf30910f5b8ea765e4b9eede8ff04a87340caf169f14324f3f83b292`。
- ffprobe：1920×1080、H.264 + AAC、`30000/1001` fps、容器时长 **118.037333 秒**。平台元数据时长 117.984 秒，差别是容器封装，不应把二者混写。
- 原始平台解析元数据：`/workspace/scratch/sun-replay/rome-source.json`。
- 原始命令：`yt-dlp -f http-10368 -o /workspace/scratch/sun-replay/rome.mp4 'https://twitter.com/TennisChannel/status/1921973328903860370'`；yt-dlp `2026.08.19`。
- 原帖网页直开 403，但 yt-dlp guest GraphQL 真实解出了发布者、文案、日期和视频格式，并成功下载。不是从网文截图拼接、也不是从其他人的帖子替换。

## 历史身份交叉核实

<https://tennisuptodate.com/wta/video-mirra-andreeva-tears-up-over-controversial-umpire-call-in-rome-victory>：文章日期 2025-05-12 21:30；明确为罗马 Andreeva–Tauson 比赛、决胜盘 1–1、Andreeva 正手 winner 后因为灯光在击球前打开被要求重打。该文嵌入上述 Tennis Channel 帖子与原文，故身份与事件可交叉核实。

场上：蓝色衣服、近端发球者为 Andreeva；淡紫色衣服、远端接发球者为 Tauson。源片比分条可见决胜盘 1–1，前两盘 5–7、6–3。历史比赛最终结果仅用于内部身份交叉验证，本事件视频不需要复盘全场。

## 实际画面与完整关键窗口

**重要：前 14 秒是同一争议回合的循环回放。不能把回放循环讲成“重赛后又打了同样的球”。** 用 1 / 2 / 5 fps contact sheet 实际核画面，不是凭 ASR 时间猜。

- `0.00–5.50`：首遍完整回放，开头已在发球动作中，之后接发、Andreeva 上前正手、Tauson 在底线远端，回合结束。
- `5.52–11.48`：第二遍完整回放，从发球动作开始，接发、向前的正手 winner、回合结果都有；这是保留单次完整关键画面的首选窗口。
- `11.50–约14.00`：又回到同一发球动作，第三遍回放尚未完整结束就切换到主裁 / 对手；不应再拼一次充当比赛新回合。
- `约14.00–19.70`：主裁、Tauson 的真实反应镜头；解说质疑判罚，见下面双语 cue。
- `21.02–25.86`：解说问 Tauson 如果不开灯是否真能够到球，接着说她离球很远。
- `26.50–34.00`：主裁公开说明三句，完成“为什么重打”的判罚说明，句尾安全收束在 34 秒。
- `约34–104`：Andreeva 向主裁交涉，较多低音量 / 场噪 / 重叠语音。两模型对许多句子分歧明显，**本任务没有把这一整段标为可用字幕或已听审**。
- `约105–118`：解说谈主裁 Yamila Halle 的打球背景，两模型姓名等有分歧。本片不需要此段。

已生成并实际查看的联系表在 scratch：`rome-contact.jpg`、`rome-point-timed.jpg`、`rome-cut-contact.jpg`、`rome-replay-contact.jpg`、`rome-decision-contact.jpg`。它们用于判断窗口，不是比赛画面的官方替代源。

## 真实转写方法、证据与边界

平台字幕字段为空 `{}`，没有自动字幕。没有声称存在官方字幕。

实际运行 faster-whisper `1.2.1`，CPU int8、4 线程、英语、beam 5、逐词时间戳、VAD：

1. 第一份 **small.en**：`/workspace/scratch/sun-replay/rome-small.en.json`。
2. 独立第二份 **medium.en**：`/workspace/scratch/sun-replay/rome-medium.en.json`。

原片经 ffmpeg 提取到 16kHz 单声道 PCM：`/workspace/scratch/sun-replay/rome.wav`。解码步骤曾遇到 PyAV 19.0.1 不接受 `metadata_errors` 参数，已通过读真实 PCM numpy 音频避开该 API 不兼容后完成两份转写，没有假填结果。

**这属于真实双模型 ASR 交叉验证 + 图像核验，不属于人工听审。** 两模型姓名存在典型拼写误识别（`Mira/Mirror` → `Mirra`，`Towson` → `Tauson`，`and I ever` → `Andreeva`）；根据已确认的真实人物身份和音节语境做姓名规范化，并保留原始 JSON 供复核。转写完全未认可 34–104 秒的弱语音内容。

`5.86–11.92` 两份 ASR 对部分词、重叠说话和分句有差别（`let/lab`，`wrong`，`No she's going to get a let here Tom / I know she is`）。已补跑前 21 秒 medium.en、关闭 VAD、beam 8、加网球人名与 `let/hindrance` 的领域提示，补跑确实完成，证据文件为 `/workspace/scratch/sun-replay/rome-medium-recheck.json`。**补跑不是第三个独立模型，也不能用领域提示本身证明某句话说过。未解决前，此区不得挂 pass 或旁白覆盖后假称已核清。**

## 已可审核的原声双语 cue（源片绝对时轴）

以下主体内容两模型一致；`14.1` 的 Yeah 和 `19.5–20.06` 的 Yeah 是简单附和，若窗口包含就保留字幕，勿声称这两处有信息性观点。

| 源片起止 / 秒 | 说话人 | 英文（规范人名拼写） | 中文 |
|---|---|---|---|
| 12.30–13.72 | 解说 | Mirra could absolutely unravel | 米拉的情绪可能完全失控 |
| 14.10–14.20 | 解说 | Yeah | 是啊 |
| 14.30–16.84 | 解说 | I feel very sorry for the 18 year old | 我真为这个 18 岁姑娘感到遗憾 |
| 17.30–18.76 | 解说 | She's the one that was hindered | 她才是受到干扰的那个人 |
| 19.50–20.06 | 解说 | Yeah | 是啊 |
| 21.02–24.36 | 解说 | Was Tauson going to get to that had they not turned the lights on | 如果不开灯 陶森真的够得到那个球吗 |
| 24.50–25.86 | 解说 | She was a mile away | 她离那个球远得很 |
| 26.70–29.50 | 主裁 | The lights were turned on before Andreeva hit the ball | 安德列娃击球之前 灯就打开了 |
| 29.50–32.00 | 主裁 | That means there was a hindrance | 这意味着出现了干扰 |
| 32.00–33.82 | 主裁 | We will replay the point | 这一分需要重打 |

`unravel`、`她才是受到干扰的人`、`Tauson 是否够得到球` 都是**现场解说的观点**，不应由旁白当成已证明的规则认定 / 心理诊断。主裁原句可直接证明她当时如何解释裁决，却不能单凭这段视频证明哪一个人操作了灯光控制，也不能证明主办方受到了某项处罚。

可直接复制的 **三句主裁** `quotes`（暂存供本次项目 spec 使用；结束 34.00）：

```json
[
  {"start":26.70,"end":29.50,"en":"The lights were turned on before Andreeva hit the ball","zh":"安德列娃击球之前 灯就打开了"},
  {"start":29.50,"end":32.00,"en":"That means there was a hindrance","zh":"这意味着出现了干扰"},
  {"start":32.00,"end":33.82,"en":"We will replay the point","zh":"这一分需要重打"}
]
```

## 终版窗口建议

如果前景原声差异无法在制作阶段解决，可靠的最小引用是 **`26.50–34.00` 完整主裁说明**（7.50 秒）；用独立旁白转述旧案。

如果前景原声差异核清，保留 **`5.52–11.48` 单次完整回合 + `14.30–34.00` 人物反应 / 解说 / 裁决**，合计约 **25.66 秒**；避免原帖循环回放造成重复。`0–34` 是原官方剪辑自身的重复回放，不能标成 34 秒的原始实时完整争议过程。

本片聚焦孙心然事件，旧案只需说明“这类外部干扰，确实曾让已经打出的 winner 被重打”，不把 Andreeva 全场胜负另展开。未查当年规则书前，不能用 2026 规则替 2025 的判罚追加断言；当年规则由 rules/history 分工负责。

## 本次终版已锁定的保留窗口与仓库证据

制作方最终选择 **26.50–34.00** 完整主裁三句，共 21 个英文词。其他窗口不进入本次成片，也不以静音或旁白遮盖替代未解决的原声审核。

仓库内已写入：

- `data/audio_reviews/sun-gauff-replay-2026/rome-source-review.json`：`method=asr_cross_checked`；只覆盖 26.50–34.00；实际 reviewer / UTC 时间戳；原片 hash；姓名校正原因；无人工听审声明；未绑定未知生产 plan。SHA-256 `324ec1fa233eb1747925b832d72ef14afaea5165a702c23c9d4352dc1e4f804f`。
- `data/audio_reviews/sun-gauff-replay-2026/rome-quotes.json`：三句绝对源片时轴双语 cue。SHA-256 `eabb045192f4a3f8acca2c41ea100cc39bde49782b30667a9b08f2009f999d4a`。
- `data/audio_reviews/sun-gauff-replay-2026/rome-small.en.json`、`rome-medium.en.json`：真实完整源片 ASR 原始证据，保留两模型自己的识别词及时间轴。

制作方须将此 review 的文件哈希绑定到最终 plan 和实际 segment index；不得仅根据此份窄窗口证据把其他历史画面标 pass。
