# 配音不脱节的完整方案：逐分数据 = 内容，比分板 = 定位

2026-08-17。账号所有者的核心要求：「根据数据网站提供的逐分数据，结合视频里的
比分板，判定播放视频的信息做配音，不然视频和配音是脱节的。」

## 1. 成品视频的叙事结构（从 swiatek-kostyuk / shelton-tien 两条总结）

```
第①屏  冷开场：赛点/逆转那一分，无旁白只留现场声（全片最抓人）
第②屏  落点：赢球那一刻的表情/庆祝，配「这场胜利最硬的数字反差」
第③屏  坐标：北京时间 + 赛事 + 轮次
第④屏  身份：种子 + 排名
第⑤屏  首盘走势（beat 1）
第⑥屏  中段转折（beat 2）
第⑦屏  结局（beat 3，赛点/锁定比分）
第⑧屏  场外切口（H2H / 复仇 / 纪录，一句带过）
第⑨屏  收尾一问（互动）
```

⚠️ **旁白按叙事顺序排，时间戳乱序**：第①屏是赛点（257s），第③屏跳回开场
（4.5s），再一路按比赛时间走到结尾。这是「先给结果，再倒叙」的固定结构。

⚠️ **旁白高度依赖逐分数据**：「保发四次全部失败」「两个赛点救回」「连破两局」
——全来自逐分，字幕给不了这些。

## 2. 为什么「数死球跳变」对齐不了逐分（实测）

wangxiyu-timofeeva 这场：

- WTA 逐分：66 分，真实比赛跨度 3320 秒
- 视频死球跳变（point_ends）：296 个，跨度 2527 秒
- 296 个跳变的相邻间隔：163 个 <2s（翻牌动画 + 镜头切换记分条闪没）、
  78 个 2~15s、54 个 ≥15s

**296 ≠ 66 的原因**：一个真死球的翻牌动画会被检测成 2~4 个连续跳变；
慢放回放时记分条反复消失重现又添一批。单纯调 merge 阈值（实测 5s）只能压到
120，压不到 66——**死球跳变这个信号噪声太大，不能单独用来对齐逐分**。

## 3. 可靠的对齐信号：比分板上的「比分数字」

逐分数据和比分板**唯一都直接给出、且语义唯一**的信号是**比分序列**：

- 逐分数据：`gameScore: {teamAScore: "15", teamBScore: "40"}`（每一分）
- 比分板：烧着的 15 / 30 / 40 / AD

两者能精确对应，不受慢放、翻牌动画、换边干扰。所以对齐 = **读比分板数字，
得到「视频第 X 秒 → 比分是 15-40」，再和逐分数据的比分序列匹配**。

「读比分板数字」需要视觉——MiniMax M3（实测可读图，probe_minimax_vision 确认）。
账号所有者早就埋了这个方向（「minimax apikey 可以做视觉吗」）。

## 4. 完整自动化链（目标状态）

```
逐分数据（fetch_match_pbp，WTA 每分）
  → 算关键转折点：赛点/破发点在第几分、保发失败、连破几局、每盘比分
  → 生成旁白素材（「保发四次全失败」「两个赛点救回」）

比分板（视频画面，score_*.jpg 记分条条带）
  → MiniMax 视觉读「第几秒比分是几比几」
  → 和逐分数据的比分序列对齐，把「赛点那一分」定位到「视频第 X 秒」

两者对齐 → 按叙事模板裁剪（冷开场=赛点画面，第⑤屏=首盘走势画面…）
  → 旁白挂到对应窗口 → 配音和画面不脱节
```

## 5. 已实现 / 待实现

**已实现**：
- 逐分数据抓取 + 走势计算（fetch_match_pbp.summarise：破发点/连得分/保发/逐盘局分）
- 转折点候选（find_turning_points：破发点/盘点/赛点密度排序，但它是**局级**不是分级）
- 叙事文案起草（draft_spec：hook/thesis/beats/human_context/narration）
- 死球检测（find_point_ends + detect_scorebox，但信号有噪声，见 §2）
- ✅ **读比分板**（`read_scoreboard.py`）：MiniMax 视觉读**整帧** `contact_*.jpg`
  （自己找比分板，不依赖预裁剪的 `score_*.jpg`），输出 `[{t, score}]`
- ✅ **比分序列对齐**（`tools/align_points.py`）：`point_states()` 从 WTA 逐分
  重建每一分的局分+小分 + 标记破发/盘点/赛点；`parse_scoreboard()` 把比分板原文
  抽成 (局分,小分)；`align()` 把每个关键分定位到视频秒。纯函数离线可测。
- ✅ **叙事模板化裁剪 + 旁白窗口挂载**（`align_points.screen_anchors()` +
  `segment_skeleton()`）：把 9 屏里**有逐分锚点的四屏**（①冷开场/⑤首盘/⑥转折/
  ⑦结局）映射到视频秒，再生成 `[锚点±margin]` 的 segments 草稿，旁白按 beats
  顺序挂。②③④⑧⑨ 要么复用邻近锚点、要么留终审挑空镜。
- ✅ **整链接线**：`prepare_alignment.py`（probe 后跑 `fetch_match_pbp` + `read_scoreboard`
  备好 pbp.json + scoreboard.json）→ `assemble_spec.py --pbp --scoreboard`（用
  align_points 出 segments）→ `match-reel.yml` 的 probe 段已接上。没料就降级回
  DeepSeek 读字幕，对齐是加料不是硬闸。

**待实现（只剩边界，不是核心链）**：
- **窗口边界收口**：`segment_skeleton` 给的是 `[锚点±margin]` 草稿，真正的
  start/end 还要按旁白时长（speech_seconds）和切点（scene_cuts）收——成片 spec
  里那些「8.7s 窗口装 8.35s 旁白只剩 0.35s」的 `_why` 就是这一步的手工活。
- **ATP 逐分**：`fetch_match_pbp` 只通 WTA（ATP 没有免鉴权的逐分通路，见
  `fetch_match_pbp.py` docstring）。ATP 场自然降级读字幕，暂不机械对齐。

### align_points 的五个函数

- `point_states(points)`：WTA 逐分 → 每分 `{games_A, games_B, point_A, point_B,
  break_point, game_point, set_point, match_point}`。局分从 set/game 变化重建
  （不能用 `scoreAfterPoint.sets`，那是终局比分）。
- `parse_scoreboard(text)`：比分板原文 → `(局分A, 局分B, 小分A, 小分B)`，抽数字
  分类（含 15/30/40 是小数，否则局数）。
- `align(reads, states)`：关键分（破发/盘点/赛点）→ 命中的视频秒。局分精确、
  小分读到了也对上；一个关键分命中多个秒全保留（慢放/回放会重复出现）。
- `screen_anchors(states, aligned, clip_end)`：9 屏锚点——①赛点/⑤首盘首个关键分/
  ⑥最后一个破发点/⑦最后一个盘点赛点/⑨视频结尾。
- `segment_skeleton(anchors, narration, margin)`：锚点+旁白 → segments 草稿。

边界（v1 不解析）：比分板 AD 优势分、抢七 `7-6(5)`、三盘比显示——这些读不出
单局比分时返回 None 不猜，交给下游。

## 6. 一个可完整跑通的例子

wangxiyu-timofeeva（王曦雨 vs Timofeeva，WTA 辛辛那提，LS077）：
- 逐分 66 分（含 timestamp、每分 gameScore）✅
- probe.json（死球 296 + 切点 10 + 缩略图墙 4 张 + score_*.jpg 记分条条带 5 张）✅
- captions.txt ✅
素材齐全，是验证「读比分板 → 对齐 → 裁剪」的完整样本。
