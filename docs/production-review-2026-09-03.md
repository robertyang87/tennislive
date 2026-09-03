# 全库 review 与视频生产流程梳理（2026-09-03）

账号所有者：「整体 review 当前库代码，同时对各个视频制作的完整流程进行梳理，
做到及时高效优质快速产出视频，同时在内容和剪辑上能有 BBC / CNN 那种纪录片的
质感和爆款的潜质」。

这份文档分三层：**量出来的现状**（不是印象）、**代码和流程的真问题**（已修的
和没修的分开写）、**内容往纪录片走要改哪几处**（每一条钉到具体文件）。
先前的四份盘点（`thirty-minute-pipeline.md`、`orchestration-observability.md`、
`qa-contract.md`、`short-video-benchmark-strategy.md`）里已经写过的不重复，
这里只写它们之后发生了变化、或者它们没量到的东西。

---

## 0. 一页看完

| 结论 | 证据 |
|---|---|
| **单趟机器时间早就不是瓶颈** | 32 趟 render 中位 226s、最慢 402s；接单→成片 SLA 30/30 条 `met: true`（`tools/pipeline_timing.py`、`render.json.production_sla`） |
| **无人值守链在美网期间结构性地一条都产不出** | 最近发出的 30 条「赛场之上」里 **29 条是会话手写的 spec**，只有 1 条走了自动链；`specs/reels/pending/` 里 **49 份草稿零通过**，49/49 卡在「赛果源缺 court」、47/49 卡在「缺 round」——而编排器当前能通的赛程源（flashscore）**从设计上就不给这两个字段** |
| **真正的产能是「会话 × 每条一小时」** | 自动链在旁边跑 probe（57 次 dispatch）产草稿，会话另起炉灶写正式 spec，两条路互不复用，还会撞车（CLAUDE.md 2026-09-01 记过 6 份重复） |
| **代码健康：测试面很厚，但两个万行文件是一切改动的税** | 2933 passed / 0 failed / 124 skipped；`build_match_reel.py` 8258 行（`render()` 534 行、圈复杂度约 71），`explainer.py` 10481 行里 **72% 是数据字面量**（手写脚本和 SVG） |
| **内容：证据只被「说」出来，从不「亮」出来** | 131 条 spec 带完整技术统计，**0 条**烧进片子；慢镜、推近、关键分脉冲、贴图、字卡五种已有能力在最近 8 条里**零使用**；旁白铺满 71–84% 的时长 |

**优先级只有三件事**（第 4 节展开）：① 把自动链在大满贯期间救活（round/court 有源、或者闸改成可推导）；
② 把「证据上屏」做成渲染能力而不是后期图；③ 给模型的教材加叙事结构和镜头语汇。
其余都是第二梯队。

---

## 1. 现状怎么量的

### 1.1 三条线的真实产出（2026-08-26 → 09-03）

| 线 | 发出条数 | 其中自动链 | 自动链现状 |
|---|---|---|---|
| 赛场之上（reel） | 30 | **1**（`zheng-burel`，8/27） | orchestrate 每 10 分钟真 dispatch，probe 正常落库，**草稿全部卡在 promote 闸** |
| 赛后开麦（interview） | 5 | 5（happy path 已全自动） | `oncourt-interviews` 15 分钟一班；**美网的场上采访在 @usopen 频道，采集器只扫 tennistv.com——大满贯期间这条线结构性失明**（`orchestration-observability.md` 已记） |
| 知识解说 / 网球有故事（explainer） | 4（ledger 3 + 1 未记账） | 0 | **三道人工闸**：手写 `_SCRIPTS`、手动 dispatch、手动合并；没有任何起草工具 |

### 1.2 一条 reel 的时间账（会话手写路径，这是当前的主路）

拿 `wu-duckworth-us-open-2026-r2` 这类当天的片子按产物时间戳倒推：

    probe dispatch → probe 落库          ~4 分（机器）
    会话写 spec（读逐分、写旁白、挑窗口、找封面）   30–60 分（人/agent）
    --dry-run + 目标测试                  秒级
    render dispatch → 成片落库           211s render + 139s 准备 = **350s**（SLA 记录）
    QC → Release → 提交 → 自动 push       ~2 分
    ─────────────────────────────────
    机器合计 ≈ 12 分；**其余全是写 spec**

和 `thirty-minute-pipeline.md` 当年算的账形状一样：**慢在趟数和人工写作，不在编码**。
唯一变了的是：当年「人工」是账号所有者，现在是 agent 会话——而会话仍然在做
自动链本该做完的事（读逐分、找封面、写钩子）。

### 1.3 自动链卡在哪儿（49 份 pending 草稿逐份跑 `waiting_reasons`）

| 命中 | 闸 | 是不是这条线自己能解 |
|---|---|---|
| 49 | 赛果源缺 `court` | ❌ flashscore / WTA 都不给 court；ESPN 给，但 ESPN 对机房 IP 403（8/4 起） |
| 47 | 赛果源缺 `round` | ❌ 同上（flashscore 的 `AC` 不是轮次，WTA `RoundID` 不可靠——两条都是量过的） |
| 48 | MiniMax 视觉证据未过 | ⚠️ 依赖前一条：缺 round/court 时草稿本身就残 |
| 41 | 官方高清封面未落库 | ⚠️ 美网官方图封顶 1280×720，`_low_res_why` 要人写 |
| 36 | 第 1 段不是无旁白冷开场 | 模型教材问题（第 3 节） |
| 30 | 超过 20 小时 | 上面四条的后果 |

**也就是说，在四大满贯期间，promote 闸要求的两个字段是自动链永远拿不到的。**
它不是「模型不够好」，是**一道对着不存在的数据源立的闸**。`orchestrate.py:239-252`
从 `Match.round_name / court` 取值，而 `sources/__init__.py` 的链在 ESPN 倒下之后
只剩 flashscore（round=None, court=None）和 WTA（court 有、round 空）。

美网官方 `players/matches` feed 有 `roundName` / `courtName`（CLAUDE.md 2026-09-02
用它核过袁悦那条），**但从这台沙箱今天取是 403**（`config_web.json` 200、
`players.json` 403，`requests` 换 UA 也一样），runner 上通不通没验——
这是第 4 节第 ① 条要先做的事。

---

## 2. 代码与流程：审查结果

四条线各扫了一遍（reel / interview / explainer / 共享发布层），下面按
「已直接修掉」「明确但这次没修」「口径选择要账号所有者定」三档列。

### 2.1 这次直接修掉的（PR 里的第一个提交，都有目标测试）

| 线 | 问题 | 后果 |
|---|---|---|
| interview | `webcards._chromium_executable` 只认 `chrome-linux`，新版 playwright 是 `chrome-linux64` | 片尾页渲不出来，被 `except` 吞成一句日志，run 照绿，成片少一页 |
| interview | `--stage sheet` 在 choices 里却没有分支 | 落成「subs 少一面墙」，和名字相反 |
| interview | 重投窗口 60 分钟 < job 超时 65 分钟，且 `cancel-in-progress` | 一趟还在跑的长片在第 60 分钟被掐掉。改 70，判据从常量推导并新增「窗口必须长于 job 超时」 |
| interview | 周一来源发现只钉小时，cron 已改成 15 分钟 | 每周一搜索配额烧四遍 |
| reel | `promote_reel_draft.main` 把真崩溃和「证据没齐」印成同一句 `[waiting]` | 三个调用方全按 0 读，KeyError 在报表上就是「还在等」 |
| reel | `assemble_spec.matchup_order` 同姓时两边都命中 home，`[home, home]` 长度也是 2 | away 静默消失；三条退路原来一句都不出声 |
| reel | `reel-auto-ready` 扫 pending 是 `bash -e` 的 for 循环 | 一份草稿的 MiniMax 4xx 让这一班剩下的全部跳过 |
| reel | `finalize-reel` 裸 pull/push、无 concurrency | 撞车一次正式 spec 躺在 main 上没人渲 |
| reel | `check_reel_landed` 短片上 `min(空序列)`；`auto_push_gate` 坏 `pushed.json` 抛 JSONDecodeError 越过 `Skip`；`orchestrate._report_rank_coverage` 的 `p.rank` | 合格 QC 炸成崩溃 / 该拦的没拦 / 编排器被带崩 |

### 2.2 明确的问题，这次没修（每条都够单独一个 PR，混进来会拖这份 review）

**发布层（三条线共有）**

- **Release tag 按 slug 建，`--clobber` 覆盖**（`explainer.yml:352`、`match-reel.yml:1133`、`interview-clip.yml` 同形）。重渲一次，**所有已经发出去的微信消息从此播放新片**。解说片线量到 **42 条里 8 条**已经是这个状态（同一 URL 两份 `render.json` 字节数不同）。这和「已发的不重渲」那条规矩互为因果：规矩之所以硬，是因为机制上没有版本。修法是 tag 带上成片哈希前八位（ledger 本来就按 `film_sha256` 记），旧消息永远指向旧文件。⚠️ 这是口径选择的一半：换封面重发（`wu-walton`）时账号所有者**要的就是旧链接播新片**——所以要分「重发」和「静默替换」两种，前者保留 clobber。
- **四段发布步骤在 `match-reel.yml` / `auto-push-reel.yml` / `interview-clip.yml` / `auto-push-interview.yml` 各抄一份**（预占账本 → 推送 → 记账 → 失败标记），已经分叉（一边 `push_with_rebase_retry`、一边手搓五次循环）。收成 `tools/publish_steps.sh` 一份。
- **每次推送三次串行提交到 main**（复制页、预占、记账），各自五次 rebase 重试。合并成两次（预占必须在 POST 前、记账必须在 POST 后，复制页可以并进预占那一笔）。

**赛场之上**

- **`mode=render` 按今天的日期算 `OUT_DIR`，而 `probe.json` 在 probe 那天的目录**（`match-reel.yml:678-712`）。跨日渲染时 `repair_reel_spec.py` 读不到 probe 事实，模型修窗口是盲修。`mode=push` 2026-08-07 修过同一个坑（按 slug 反查），render 没跟上。
- **`--cover-only` 在 `resolve_crop` 之前就 return**（`build_match_reel.py:6497 vs 6525`），拿默认 `LAYOUT` / `FPS_EXPR` 渲封面；并且白编一段 `part_cover.mp4` 再删掉。
- **`render()` 534 行、`main()` 472 行、`parse_segments` 274 行**，模块级可变全局 `LAYOUT / CROP_* / FPS_EXPR` 被 8 个函数读。这个文件每条新规矩都往里加一道闸，已经是「改一行要跑三分钟全量才敢推」的状态。拆法见 2.4。
- 阈值三份：`HEAT_TOP_RANK = 20` 写在两处；20 小时新鲜窗写在三处（`promote_reel_draft.py:26`、`reel-auto-ready.yml:69`、`orchestrate.py:67`）；`_surname` 四份且已分叉（只有 orchestrate 认 `Kenin S.`）。
- `match-reel.yml` 的 `dry-run` 排在装 ffmpeg、字体、抠图模型**之后**——它存在的意义是「第 30 秒红」，现在前面站着两段各 15 分钟最坏预算的 apt。挪到 checkout 之后、装依赖之前。
- 自动 dispatch 一律不传 `matchup/score/summary/push_lead`，25 个 dispatch 输入里这五个只有人手动才填——**每一条自动推送都带着空标题参数**，全靠 `push_meta` 从 spec 读退路撑着。删掉这五个输入，给 26 项上限腾位置。
- `orchestrate.assemble_draft` 已弃用零调用，删。

**赛后开麦**

- **采访 takeaway 口播走 `explainer.synthesize_narration`**：edge-tts 单后端、无重试、无缓存、失败被 `except` 吞成静音卡——而 reel 线的 `tts_one` 有 Azure 优先、内容缓存、退避重试。同一个仓库两套 TTS，差的那套在采访线上。
- `interview-auto-render` 每 10 分钟一班，只要有一条 `READY` 就装 faster-whisper 和起 Docker（2–3 分钟），哪怕这一班只需要 `gh workflow run`。
- `attach_interview_lead_in` 扫描模式全失败返回 0；`_one` 只捕三类异常，别的异常会把同批已完成的结果一起扔掉。
- `already_accepted` 输出写了没人读；`validate_qc` 一次推送跑三遍。

**知识解说 / 网球有故事**

- **脚本活在代码里**（`_SCRIPTS` 4444 行、`_OPENINGS` 788 行、`_CAPTIONS` 317 行、45 张 SVG 约 1700 行），另外两条线的 spec 化、起草工具、自动推送认领在这条线上全部不存在；`AUTO_PUSH_SLUGS` 是硬编码的 frozenset。**这条线没有任何模型起草**——每一条都是人从零写。`import tennislive.video.explainer` 要 507ms，被 12 个模块引用。
- 不在 `_SCRIPTS` 里的 slug 走退路：三拍、无封面、序号药丸印「0」（跑 `slug=umag` 验过），71 个 `STORIES` 里 28 个是这条路，测试只遍历 `_SCRIPTS`。
- edge-tts 零重试，一次异常烧掉 10–14 分钟渲染；`azure_tts` 在这个文件里零引用。
- `output/*/explainer/` 提交进 git 的中间物：223 份 `voice_*.words.json`、223 份 `sub_*.ass`、**11 个 `_outro.mp4`**（违反「成片不进 git」）。
- `pipeline_health` 不监控 `explainer.yml` 和 `knowledge-adhoc.yml`（后者是全库唯一的定时产出线）；explainer 的 `render.json` 没有 `production_sla`，600 秒 SLA 对它是零覆盖。
- `_MISCALL_DIAGRAM` 零引用；`_SUB_TRIM/_SUB_DROP` 零读者。

### 2.3 口径选择，要账号所有者定

| 问题 | 方向 A | 方向 B |
|---|---|---|
| 大满贯期间 round/court 从哪来 | 接美网/澳网官方 feed（要先在 runner 上验通不通、封顶 1280 的封面要接受 `_low_res_why` 自动写） | promote 闸对四大满贯放宽：round 从赛程日期＋签表推、court 允许空（顶栏不印球场） |
| 已发消息要不要永远播旧片 | tag 带哈希，重渲不影响旧链接；换封面重发走显式「重发」 | 维持现状（重渲即替换），把「已发不重渲」继续当规矩守 |
| 解说片要不要 spec 化 | 把 `_SCRIPTS` 迁成 `specs/explainers/*.json`，接 `draft_spec` 同款起草，`push.auto` 认领 | 维持手写；只把 SVG 和脚本拆出 `explainer.py` 减轻 import |
| 背景音乐 | 平台曲库（2026-08-29 定的） | —— |

### 2.4 结构上的一刀：`build_match_reel.py` 怎么拆才不伤判据

现在的判据有一半是「源码里某个函数在某个位置」（`test_…排在…之前`），所以不能
一次大搬家。可行的顺序：

1. **先拆纯函数**：`_ass_timestamp/_escape`（和 explainer、interview 各一份）、
   `_chromium`（五份）、`_surname`（四份）、TTS（两套）收进 `src/tennislive/video/`
   下的 `ass.py / chromium.py / names.py / tts.py`。每一份合并都是「一个数写两处必
   分叉」那条的兑现，而且已经分叉过。
2. **再把 `render()` 按阶段切成模块**（`cover / cut / mix / burn / qc`），全局
   `LAYOUT/CROP/FPS` 收进一个 `RenderContext` 传下去。`parse_segments` 的 33 个 `if`
   是 spec 形状校验，本来就该和 `validate_spec` 一起住。
3. 每一步只动一处，跑目标测试＋一次全量，**不合并两步**。

---

## 3. 内容与剪辑：离「纪录片质感」差在哪

先说清楚哪些**已经在做对**（别再改）：冷开场取全片最强一格（8 条里 7 条）、
钩子讲过程不讲身份、旁白有立场、收尾一问、现场声＋闪避、封面官方实拍、
事实两个源。这些是地基，下面的差距全在地基之上。

### 3.1 量出来的差距（最近 8 条「赛场之上」）

| 维度 | 现状 | 纪录片的做法 |
|---|---|---|
| 旁白密度 | **71–84%** 时长在说话；`MAX_SILENT_GAP=4.0` 把任何 >4 秒的留白判成「哑场」 | 留白是手段：关键分前一秒安静，赢球后让现场声顶三秒 |
| 结构 | 9–20 段按时间线一局一局走；`beats` 三拍在 schema 里，**不会进段落** | 三幕：设问 → 反转/中点 → 兑现；每一幕有一个可见的转场 |
| 证据 | 131 条 spec 有 `stats`，**0 条上屏**（`render_stat_card` 在成片之后才渲，只是推送图）；`inset` 4/200、`story_text` 1/200、`speed` 0/200、`crop_zoom` 0/200、`topbar.pulse_at` 0/200 | 一发得分率 47% 这种数字**印在画面上停两秒**，慢镜回放那一拍，关键分推近 |
| 论点 | `thesis` 只被念出来，没有 title card / lower-third 把它印出来 | 开场 3 秒内一行字把「这条片子要证明什么」压在画面上 |
| 主角 | `_SYSTEM_RULES` 明写「背景一句带过，别展开」 | 一个人的一条因果链（`story-video-reference-xiaosigua.md` 那两条就是样板） |
| 收尾 | 8/8 收在一个反问 | 先兑现开场的论点，再抛问 |
| 声音 | 一档：`BED_LOUD=0.72` 全程闪避 | 至少三档：对话下压、回合抬起、庆祝拉满 |
| 模式 | 166 条全是 `match_review` | 至少两种合同：赛报（快）、人物/事件纪录（慢、有章节） |

### 3.2 要改的地方（每条钉到文件；标注是「教模型」「新渲染能力」还是「顺序」）

**A. 证据上屏——最大的一块，且大半是顺序问题**

1. **stat card 变成一段**（顺序）：`build_match_reel.py:6968` 现在是 `final` 写完
   之后才渲 `stat_card.jpg`。把它提前到 `cut_segment` 之前，允许 spec 写
   `{"kind": "stat_card", "seconds": 2.5, "fields": ["first_in", "second_won"]}`
   当一个整屏证据段（`image + seconds` 那条路 `:2131` 已经存在，只差一个「从 stats
   块现渲」的入口）。
2. **beat/story_text 卡预制进自动链**（顺序）：`render_beat_card.py` 已能出图，
   `zheng-us-open-outlook` 手工预渲了 13 张才用上。让 `assemble_spec` 在 probe
   之后按 `_hit_data` 自动出 2–3 张（总分差、破发点、一发对比），写进
   `assets/beatcards/<slug>/`，模型只决定放在哪一段。
3. **教材加插入语汇**（教模型）：`skills/tennis-reel-production/SKILL.md` 19 行全是
   闸合同，`_SYSTEM_RULES` 一个字没提 `inset / story_text / speed / crop_zoom /
   pulse_at`。加一节「每条片子至少一处数字上屏、至少一处慢镜或推近、关键分
   `pulse_at`」，并把它落成 `promote` 的软报告（不拦，报「零证据上屏」）。

**B. 结构——教模型，外加一个渲染能力**

4. **三幕落进段落**（教模型）：`draft_spec.py` SCHEMA 给每段加 `act: 1|2|3`，
   要求第 2 幕开头是转折点那一分（`find_turning_points` 已经算出来）。
   `docs/reel-narrative-template.md` 的九屏骨架**不在 prompt 路径里**
   （`system_prompt()` 只拼 `_SYSTEM_RULES` + deepseek.md），把它接进去。
5. **章节卡 / 论点卡**（新渲染能力）：一种 `kind: "title_card"` 段，深底、一行
   `thesis`、0.8–1.2 秒，用 `outro_page` 那套 HTML 渲染即可。小丝瓜那两条的
   「01/02/03」章节卡就是这个，账号所有者 8/29 点名要学。
6. **收尾先兑现再抛问**（教模型）：`_SYSTEM_RULES`【收尾一问】前面加一句
   「先用一个上屏的数字回答开场的 question，再问」。

**C. 留白与声音——一处闸的语义要改**

7. **可声明的留白**（顺序）：`MAX_SILENT_GAP` 那道闸加一个和 `archival /
   silent_source` 同形的认领：段上写 `"beat_silence": "赢球后让现场声顶 3 秒"`，
   闸对这一段放行且不报哑场。现在的闸把纪录片最常用的手段判成缺陷。
8. **三档音床**（新渲染能力）：`BED_LOUD` 变成每段可写的 `bed: "low|mid|high"`，
   三个常量，闪避阈值不变。`mute` 已经有，只差中间两档。

**D. 主角与模式——教模型**

9. **第二种 `editorial.mode`**：`person_story`（网球有故事）——允许背景展开、
   要求章节卡、要求 ≥2 张上屏证据、收尾书挡（两个年龄/年份）。
   `_SYSTEM_RULES`「背景一句带过」只对 `match_review` 成立。
10. **镜头语汇进 MiniMax 教材**（教模型）：`references/minimax.md` 只按
    `match_point|winning_shot|celebration` 选帧，加「输家的脸」「教练席」
    「握手」三类反应镜头的要求——纪录片的情绪几乎全在反应镜头里。

**E. 解说片线——先 spec 化，否则上面所有东西它一样都吃不到**

11. `_SCRIPTS` 迁成 `specs/explainers/<slug>.json`，起草走 `draft_spec` 同款
    （教材换成 `skills/tennis-story-production/`），`push.auto` 认领，
    `AUTO_PUSH_SLUGS` 删掉。这是 2.3 的口径选择，但**不做这一步，网球有故事
    这条线永远是手工线**，而它恰恰是最像纪录片的那条。

### 3.3 「爆款潜质」和「纪录片质感」不冲突的地方

平台后台量过的三个数（`short-video-benchmark-strategy.md` §1.3、CLAUDE.md
「开场三格」）：2 秒跳出 27%、完播 2–3%、评论/赞 40% 上下。纪录片手法里
**恰好**压在这三个数上的：

- 冷开场（已做）压 2 秒跳出
- **数字上屏 + 章节卡**压中段流失——完播只有 2–3%，中段每一屏都要给「再看
  一屏」的理由，一个印在画面上的数字比一句旁白便宜得多
- 收尾兑现再抛问——评论率本来就不低，缺的是转发，转发靠「这条片子证明了一件事」

所以 A 组（证据上屏）既是质感也是完播，排第一不是审美偏好。

---

## 4. 路线：按「先止血、再产能、再质感」

| 序 | 做什么 | 改哪儿 | 成本 | 判据 |
|---|---|---|---|---|
| ① | **救活大满贯期间的自动链**：runner 上验美网/澳网官方 feed；通就接 round/court，不通就按 2.3 方向 B 放宽 promote 闸 | `tools/orchestrate.py`、`promote_reel_draft.waiting_reasons`、新 `tools/slam_feed.py` | 半天 | 一条草稿真的 promote 并 render，不经会话 |
| ② | 会话和自动链**合流**：会话写 spec 前先读 pending 草稿（probe、逐分、封面已经在里面），不再从零 probe | `skills/tennis-reel-production/SKILL.md` 加一节「先看 pending」 | 一小时 | 同一场球 probe 次数 = 1 |
| ③ | 2.2 里的发布层三条（tag 带哈希、发布步骤收一份、三笔提交并两笔） | 四个 yml + `tools/publish_steps.sh` | 一天 | 已发消息重渲后仍播旧片 |
| ④ | 3.2 的 A 组（stat card 成段、beat 卡进自动链、教材加语汇） | `build_match_reel.py`、`assemble_spec.py`、SKILL.md | 两天 | 新片子 100% 有 ≥1 处数字上屏 |
| ⑤ | 3.2 的 B/C 组（三幕、章节卡、留白认领、三档音床） | `draft_spec.py`、渲染器 | 三天 | dry-run 报告出「幕」和「留白」 |
| ⑥ | `build_match_reel.py` 按 2.4 拆；采访线 TTS 换到 reel 那套 | 见 2.4 | 分三次 PR | 全量测试条数不变、目标测试各自跑 |
| ⑦ | 解说片 spec 化 + 起草 + `person_story` 模式（3.2 的 D/E） | 新 `specs/explainers/`、`skills/tennis-story-production/` | 一周 | 网球有故事从选题到推送不经手写 |

⑦ 最贵也最值：它是「BBC 那种质感」真正长出来的地方，而今天那条线连起草工具
都没有。①②是产能，③是安全，④⑤是质感的机械那一半。

---

## 5. 这次没做、别当成做过

- ~~美网官方 feed 只在沙箱试了（403），runner 上通不通没验。~~ **2026-09-03 晚补上了**：
  `probe-blocked` run 33726027891 / 33726235409 在 runner 上取到 `players.json`（200，
  1259 个球员）和 `players/matches/<id>_matches.json`（`roundName` / `courtName` /
  `duration` / `team1`/`team2` 都在）——**403 只是沙箱的事**。`tools/slam_feed.py`
  接上，`orchestrate.enrich_slam_fields` 在候选出来之后、dispatch 之前补 round/court
  （只对 `SLAM_FEEDS` 认得的赛事查，查不到出声继续）。路线 ① 的「有源」那一支
  落地；**下一条自动草稿真的 promote 并 render 才算数**，那是判据。
  ⚠️ 合并当天（07:37Z，orchestrate run 33728989031 干跑）第一次在真产物上看见它工作：
  `[sakamoto-tiafoe] 官方 feed 补上 round=第二轮、court=Louis Armstrong Stadium`——
  同一班次里四条「开球之前」候选（还没打的场次）feed 里没有，照旧空着、照旧出声。
  澳网/法网/温网各自的 feed 还没探，往 `SLAM_FEEDS` 加一行的事。
- 路线 ②（会话先读 pending）：`tools/find_pending_draft.py` ＋ CLAUDE.md 一节，PR #743。
- 路线 ④ 第一刀（本 PR）：`{"stat_card": true, "seconds": N, "narration": …}` 段——
  数据统计对照图**剪进片子**当整屏证据段，render 在切段之前现渲 `stat_card.jpg`
  换掉占位符，片尾那次「渲给推送用」的渲染对剪进片子的不再渲第二遍。
  ⚠️ 拿 alcaraz-faria（美网、带式）跑 `--dry-run` 才发现两件事，都修了：
  ① 归一化必须在 `load_spec` 里做（`seg_seconds` / 多源校验 / 片尾兑现闸 /
  `check_reel_landed` 那份抄的公式全按 `image` 认整屏段，晚一步就 KeyError）；
  ② **带式版式一直拒 `fit: contain`，而整屏证据段的 fit 写死 contain——也就是说
  美网期间整屏证据段整个用不了**，`cut_still_segment` 从没在带式上渲过一帧。
  现在带式放过整屏段，卡缩进画面带（`BAND_TOP` 起 1080×960）、底色 `BAND_BG`。
  还没做：数据图是 1080×1920 竖版，缩进 3:4 画布只剩 713px 宽、缩进带式画面带
  只剩约 475px 宽——**要一张 3:4／横版的数据图变体**（`render_stat_card` 画布
  定死 1080×1920），以及自动链里**谁来插这一段**：DeepSeek 不写 segments（窗口全是
  机械工具给的，`draft_spec.py` 第 12 行），所以该是 `assemble_spec` 在有 `stats` 块
  时机械地在转折 beat 之后插一段，不是教模型。
- 路线 ④ 第二刀（PR 待开）：**自动链把数据图剪进片子**。先量出一个挡在前面的
  洞：49 份 pending 草稿全带 `stats`、**零份带 `headshot`**，而 render 末尾那次
  「渲给推送用」的数据图缺 headshot 是 SystemExit——任何一份自动草稿转正都是一趟
  必红的 render（medvedev-damm 的头像是人手补的）。修法三处：`tools/headshot_index.py`
  从已发 spec 推「中文名→头像」（130 个名字，规则和头像判据同一条）复用、WTA 按名字
  现抓、ATP 留空出声；`assemble_spec` 在 stats 块之后调它；`promote` 缺头像留
  waiting（报错正文写着两条命令）。然后 `promote` 转正时在收官段之前机械插一段
  `stat_card`（旁白只讲总得分、汉字数字、方向机械算；段数到 10 或算不出就不插）。
  ⚠️ `spoken_integer` 从 draft_spec 挪到 spec_wording：promote 直接 import draft_spec
  会把 reel_skill 拖进 build_match_reel 的 import 图，frame-grab 被判成要教材。
- 路线 ④ 第三刀（PR 待开）：数据图多一个 **film 变体**（1080×1440，就是成片的
  3:4 画幅）——剪进片子的那张渲它，铺满宽度；推送页那张仍是 1080×1920。少掉的
  480px：footer、「全场数据对比」段标题、行距 33/23→20/13（五盘九行量到 1413，
  沿用旧行距 1615 溢出）。⚠️ 带式（美网）画面带只有 1080×960，film 版缩进去仍只有
  约 634px 宽——真要在带式里铺满得再做一张横版，这次没做。
- 路线 ⑤ 第一刀（PR 待开）：**章节卡 / 论点卡**——`tools/render_title_card.py`
  （片尾页那套品牌视觉：四色细杠、墨绿底、得意黑，可带 01/02/03 序号；屏幕上不写
  标点，逗号换成换行）＋ `build_match_reel` 的 `{"title_card": "一句话", "seconds": N}`
  段（旁白缺省就是卡上那句——章节卡不能是一段死寂，QC 的数字静音闸 1 秒就红），
  和 stat_card 走同一条「切段之前现渲」的路，带式按画面带 1080×960 渲。
  没做的一半：自动链里谁插它（`promote` 按 `editorial.beats` 在每幕开头插一张，
  是路线 ⑤「三幕落进段落」那条的事，和 `act` 字段一起做）。
- 路线 ⑤ 第二刀（PR 待开）：**三档音床**——段上写 `"bed": "low" | "high"`
  （不写＝中档），乘在这一段自己的音轨上再进全局 `BED_LOUD` 和闪避，闪避阈值不动；
  和 mute 互斥。cut_segment 那两处 `-map` 判据收成 `_seg_audio_needs_filter` 一个
  出处（原来 `seg.speed != 1 or seg.mute` 写了两遍，漏改一处的样子是滤镜链算好了
  被 map 绕过去、不报错）。真切三段量过：low 比对照低 ≈6 dB，high 高 ≈2.6 dB。
- 路线 ⑤ 第三刀（PR 待开）：自动链的章节卡——DeepSeek 合同多一个 `chapters`
  （三条 ≤10 字、不带标点的章节标题，一条对应一个 beat；prompt 和
  references/deepseek.md 都教了），`promote_reel_draft.insert_chapter_cards`
  转正时按段上的 **`_beat`**（三条产窗口的路都标：align_points /
  draft_segments 合同 / scene_cut_segments；老草稿退回旁白原文）认出每个 beat 的
  第一段、在它前面插一张 `title_card`
  （kicker 01/02/03，秒数按念完标题算）。钥匙是逐字相同的 narration——
  ⚠️ 47 份 pending 草稿量过：模型写窗口那条路的旁白**全是改写过的**，按原文一条
  都认不到——`_beat` 是这个功能在主路上成立的前提；两把钥匙都认不到的 beat 不插、
  `_chapter_cards_why` 出声。形状不合（标点/超长/条数）不拦转正，只出声：章节卡是加分项，不该卡链。
  ⚠️ 49 份 pending 草稿全是旧合同产的（没有 chapters），要等下一批 assemble 才有。
- 路线 ⑥ 第一刀（PR 待开）：**找 Chromium 收成 `src/tennislive/chromium.py` 一份
  出处**（`find_chromium` / `require_chromium` / `launch_chromium`）。量出来在这之前
  是 **12 份**，四份写死 `chromium-1194`（`render_stat_card` / `render_evidence_card` /
  `render_beat_card` / `versus_poster`）、两份只认旧目录名 `chrome-linux`
  （`probe_atp_browser_stats` / `probe_venue_photos`）——runner 换一版 playwright
  就是「本地全绿、远端找不到」。判据 `tests/test_chromium.py` 钉行为（假目录树
  两种目录名、headless 兜底、`CHROMIUM_PATH` 优先）＋出处（别处字符串里不许再有
  `pw-browsers` / `chromium-1194` / `chrome-linux`，`launch(executable_path=` 不许
  写死）。`_surname` 收成 `tennislive/names.py::surname_en`（`Bu Y.` 姓在第一个词；
  `assemble_spec` / `prepare_alignment` 原来取末词，对缩写名是错的）。
  ⚠️ 顺手抓到一个真 bug：`build_interview_clip.py` 里 `_bare` **定义了两遍**
  （793 切行用 / 3673 比引文用），后一份静默盖掉前一份、不转小写，于是
  `And` / `The` 起头的词在英文字幕断点排序里一律认不出来——ruff F811 不报
  （前一份在被盖掉之前被引用过）。`orchestrate._surname` 同款（93 / 362）。
  新判据 `tests/test_no_duplicate_defs.py`：一个模块里同名顶层定义不许两次。
  ASS 时间戳那一份（2.4 里列的）实际只有 `build_match_reel` 一处 `def`，别处是
  内联格式化，没动；TTS 两套（2.4 的最后一项）留给下一刀。
- Release tag 改哈希没动（口径选择）。
- `build_match_reel.py` 没拆一行（要分三次 PR）。
- 内容那一节的 11 条没有一条落成代码，只落成了这份文档和路线表。
- 124 条 skipped 测试没逐条看（`-rs` 抽样看到的全是「这条 spec 没有 X 可比」
  一类的按 spec 参数化跳过，不是缺依赖）。
