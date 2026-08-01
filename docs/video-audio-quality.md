# 全工程视频音频转场基线

这份规则适用于仓库里的所有视频产线，而不只适用于“网球有故事”。只要一条成片
拼接了两个以上的原声、环境声或配乐资产，就必须先生成结构化转场计划，再由共享
音频模块完成拼接；不得把多段音频裸 `concat` 或 `-c copy` 后直接交付。

## 音频角色

- `speech`：中文旁白、采访、现场讲话。不得用交叉淡化掩盖跨段或抢话，必须保持
  字幕时间轴同步。
- `music`：独立配乐。连续使用同一首时维持一条时间线；换曲时才做转场。
- `ambience`：球声、观众声、场馆底噪。
- `mixed`：官方集锦里无法拆开的音乐、现场声和讲话混合轨。按配乐边界的严格规则
  处理，不能假设可以无损分离。
- `silence`：封面或静态资料段的显式静音。

未标注的多段来源按 `mixed` 处理并关闭裸拼接；这比把未知轨道误当作连续原声安全。
调用共享转场函数时 `audio_role` 是必填参数；底层会拒绝未知角色。`speech` 只允许
`keep` 或不超过 30 ms 的 `declick`，误用任何长淡化或重叠模式都会立即失败。

## 默认转场

1. `music/mixed → music/mixed` **优先**使用 0.45 秒、`qsin` 等功率
   `lcut_crossfade`：后一段
   从画面切点开始淡入，前一段使用源片切点后的额外音频 handle 继续并淡出。差异
   特别大的两段可在单个边界显式提高到 `0.60` 秒。
2. L-cut 的重叠只作用于 bed，不得淡掉旁白或采访。没有合法的切点后 tail handle
   时使用全工程安全回退 `fade_through_silence`：前段 0.40 秒淡出、后段 0.30 秒
   淡入；报告里的 `fallback_count` 和 `reason` 必须让这次降级可见。
3. `ambience → ambience` 可缩短到 0.20 秒；同一来源且时间连续只做 10–30 ms
   de-click。整条 bed 的片头和片尾各保留 0.30 秒淡入淡出。
4. 很短的片段把转场限制在短段时长的四分之一以内。小于 0.15 秒仍无法安全处理时，
   换素材或写逐边界例外，不能静默硬切。
5. 交付视频不接受未处理的 `hard_cut`。即使要卡点，也用 5–30 ms `declick` 明确
   处理数字点击；确实需要完整 A/V 叠化时走下一节的显式时间线，不在单条脚本里
   偷加例外。

## 时间轴硬约束

- 音频转场不得改变画面、旁白或字幕的章节起点。直接串联 FFmpeg `acrossfade`
  会让每个边界缩短一个淡化时长，禁止用于未同步重算画面的时间线。
- 默认使用额外 tail handle 在固定时间线上重叠 bed；最终音视频时差不得超过 50 ms。
- 若确需音画一起叠化，必须使用显式 A/V xfade 模式，并由同一函数返回总时长变化；
  不允许音频单独偷走时长。

## 自动验收

每条成片都要在 `qa.json` 或独立 `audio-qa.json` 中记录：

- `policy_version`、音频角色和总体 `status`；
- 每个边界的时间、前后来源、模式、时长、曲线以及是否拿到 tail handle；
- `transition_count`、交叉淡化数、显式降级数和获批硬切数；
- 最终音视频时差；多段音频不得存在未规划的边界。

统一从 `audio_qa_for_graph()` 或 `not_applicable_audio_qa()` 生成 schema，不能在各脚本
复制一份近似字段。一目录只有一条成片时用 `audio-qa.json`；同一目录可能有多条视频
时用 `<成片 stem>.audio-qa.json`，避免一条视频覆盖另一条的审计。

报告存在还不算交付通过。上传 artifact、提交或推送之前，工作流必须调用
`python tools/check_audio_qa.py --report … --video …` 对**最终 MP4**执行硬门禁：校验
schema 与计数、拒绝硬切和语音长淡化、用 ffprobe 分别读取视频/音频 stream，并把
A/V 时差限制在 50 ms。只检查旁白混音前的中间片等同于没检查最终交付物。

CI 使用合成的不同频率音轨钉住以下合同：

- 默认转场不改变总时长，短段会自动限幅；
- 多段 `music/mixed` 没有计划或仍走裸音频 concat 时失败；
- 旁白不参与 bed 交叉淡化；
- 单一连续源、纯 TTS 或无音频视频明确写 `not_applicable`，不能把“没检查”伪装成
  “无需检查”。

最终仍需戴耳机抽听所有音乐边界。波形和静音检测只能证明实现没有明显坏掉，不能替代
对节奏、曲调和情绪连续性的判断。

## 当前管线接入范围

- `tools/build_video_story.py`：多官方来源的 `mixed` bed，必须使用带 handle 的 L-cut。
- `tools/build_match_reel.py`：非连续选段可能切断集锦内音乐，不能再把 part 音轨裸
  `concat -c copy`。
- `tennislive.video.official.render_wta_video`：官方长片四段抽样属于多段 `mixed`。
- `tools/build_grand_slam_v2.py`：场景内多段 ambient 和场景间 bed 都要走共享规则。
- `build_interview_clip` 只有静音封面到连续采访原声这一处边界，只允许 20 ms
  `declick`；`daily_point`、`video-localize` 是单一连续原声，标记
  `not_applicable`。以后加入 BGM 才进入长转场规则。
- `explainer` 的逐段 TTS 属于 `speech`，禁止套长淡化；只有检测到数字 click 时使用
  10–30 ms de-click。
- 旧版 `build_grand_slam_short` 的逐段 TTS 同样按 `speech/keep`；不能因为它是旧入口
  就保留裸音频拼接。
- `video_digest` 的静音片、`daily_point` 的单一连续原声、`video-localize` 的音轨
  passthrough 也必须写 N/A 报告，并由最终媒体探测验证“确实无声/确实有声”。

新增视频入口时，CI 会扫描 `src/` 和 `tools/build_*.py` 中实际调用 FFmpeg 的生成器；
缺少 `audio_qa` 声明会直接失败。新增工作流还必须把最终音频门禁放在 artifact、提交
和推送之前，不能只靠“渲染步骤成功”。

## 加拿大站暴露的问题

加拿大站旧版把 24 段官方混合原声在 23 个章节边界处切换，每段只有 0.08 秒淡入和
0.12 秒淡出。20 个切点瞬间降到接近静音：它消除了数字爆音，却没有解决音乐和场馆
声被抽空后换轨的听感。由此固定两条经验：

1. **de-click fade 不是音乐转场**；音乐边界必须是一等时间线对象。
2. 任何会改变音频总时长的转场，都必须同步重算画面、旁白和字幕；不能靠最终
   `silencedetect` 才猜是否做对。
