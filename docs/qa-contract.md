# 统一 QA 契约

> 三条生产线（赛场之上 / 赛后开麦 / 网球有故事）**必须对着同一份契约验收**。
> 之前每线各有一套闸，形状不同、覆盖不同。2026-08-23 已给 interview 补上
> L0 内容身份、L1 前置、L2 成片凭证和 L3 独立发布账本。**统一它们，是为了让
> "生产失败"提前到 0.2 秒、"验证不过"有同一把尺。**

## 一、四层闸（每条线都必须有，缺一层就是缺口）

| 层 | 时机 | 统一判据 | reel | interview | explainer |
|---|---|---|---|---|---|
| **L0 内容身份闸** | 进入生产前 | 请求类型、实际内容类型、来源证据、同场 match_id 必须一致 | 来源/赛果窄匹配 | ✅ `interview_source_gate` | 来源/事实引用 |
| **L1 spec 前置闸** | 渲染前，0.2 秒 | spec 形状：字段、段落引用、窗口、闸级认领（见 §二） | ✅ `validate_spec` | ✅ `check_source_contract` + opening/lead-in/takeaway | ⚠️ 分散在 builder |
| **L2 成片落地闸** | 渲染后，推送前 | 产物本身：分辨率/音画等长/双语正文/来源可回查（见 §三） | ✅ `check_reel_landed` | ✅ `check_interview_landed` | ✅ `check_explainer_landed` |
| **L3 发布闸** | 推送前 | QC 凭证、链接、复制页、幂等状态留档（见 §四） | ✅ | ✅ 独立 ledger | ✅ |

**验收**：新加一条生产线，必须把 L0/L1/L2/L3 四层都接上，否则不许并进编排器。

### Interview 的 L0 不变量

- `requested_content_type` 固定为机器枚举 `on_court`，展示字段固定为“赛后场上采访”。
- 只有人工画面结论、Tennis TV 结构化 interviews、已注册官方源的明确
  `on-court interview` 能进入生产。WTA 集锦片尾即使已知含采访，只要逐条采访
  起点尚未证明，就只能进复核队列，不能把五分钟集锦从 0 秒当采访正文转写。
- 发布会、演播室、颁奖致辞、unknown 全部进入待复核队列；找不到就不制作、不推送。
- `source_verification` 与赛事、轮次、胜负双方和 `match.id` 一起签名；正式 spec
  任一身份字段变化都会让签名失效，必须重新核验。

## 二、L1 spec 前置闸：统一的"要么有 X、要么说清为什么"

这是「忘了写」和「想清楚了不写」分家的地方。统一形状，不是统一字段名：

| 认领项 | 有 → 过 | 没有 → 必须写 | 已落测试 |
|---|---|---|---|
| 数据统计图 | `stats` | `_no_stats_why` | `test_赛场之上要么带数据统计图要么说清为什么不带` |
| 狠数据 | `_hit_data` | `_no_hit_data_why` | `test_赛场之上要么有狠数据要么说清为什么没有` |
| 自动推送 | `push.auto: true` | `push._no_auto_why` | `test_赛场之上要么开自动推送要么说清走哪条路` |
| 栏目登记 | `column`/`cover.eyebrow` | 报错（栏目名必须登记） | `test_栏目名不能只活在代码里` |

interview 的自动推送不再靠人补容易忘记的开关：草稿在赛果和 L0 都通过后默认
`push.auto: true`；发布资格仍由 L0、L2 attestation 和 L3 ledger 决定，开关不能
绕过质量门禁。explainer 的认领项仍需继续统一。

## 三、L2 成片落地闸：统一的核心不变量

三条线成片**共享**这五条（从 `check_reel_landed` 抽出，其余线照抄形状）：

1. **画布对**：分辨率必须是 1080×1440（裁切/缩放被绕过会退回 16:9）
2. **音画等长**：成片时长 ≈ 各段之和（超长/截短都不吭声，要量出来）
3. **字幕有字**：没有解说的段不许是数字静音（`-91 dB` 那类"有音轨没声音"）
4. **响度有形状**：逐秒扫，中段大片空必须被抓出来（只抽几个点会漏）
5. **来源可回查**：文案里的数字/排名/全称断言能回到 `_facts`/`_claims` 的出处

Interview 的 L2 会写 `output/interviews/<slug>/qc_attestation.json`，其中绑定
spec、L0 来源签名、正文 ASS、冷开场 ASS 和最终 MP4 的 SHA-256。采访正文及
获胜画面的原解说都必须 EN/ZH 逐 cue 同时间码，数量分别与 `spec.zh`、
`lead_in.subs` 完全一致；顶栏有字不能冒充双语字幕。音画绝对时长差必须 ≤0.30 秒，
不能再用单向比较放过音轨比画面更长的成片。

Reel 的 L2 同样写不可变 `qc_attestation.json`，绑定正式 spec、正文 ASS 和最终
MP4 的 hash/bytes；每次复检前先删除旧凭证。发布时重新计算当前文件并核对 Release
资源，旧 `render.json` 或替换后的成片都不能冒充本次质检成功。Interview 还会用
`volumedetect` 拒绝“有音轨但全程数字静音”的假通过。

## 四、L3 发布闸：QC 通过即自动推送，但必须幂等

三条线共用 `publish pushplus` 出口。发送前复核当前 spec hash、film hash/bytes 与
L2 attestation 完全一致；Interview 还要复核 L0 来源签名和 match_id。随后先把
`pushplus:<slug>:<film_sha256>` 以 `sending` 写入各自的
`data/{reel,interview,explainer}_publish_ledger/<slug>.json` 并提交到 main，才允许 POST。

POST 成功改为 `sent`；预占后任务失败改为 `uncertain`。三种状态都会阻断盲目
重发，必须先查原 run/平台回执。发布历史在 `data/`，重渲替换 output 目录也擦不掉。

## 五、落地顺序（按"先止血后统一"）

1. ✅ Interview L0/L1/L2/L3 已接通；旧的发布会/other 污染条目已从主库清除并加入 deny。
2. ✅ Interview 扫描改为每 15 分钟；一场一个 matrix runner，最多四场并行。
3. ✅ 冷开场从同场官方 1080p 单场集锦末段提取原解说，并按原 cue 生成中英字幕；
   多场最多四路并行，找不到精确同场素材的 spec 保持 waiting，不降级凑数。
4. ✅ 三条线发布 ledger 已统一；explainer 的 L0/L1 仍需提升到同一强度。

## 六、封面与文案（内容质量的统一要求）

账号所有者逐条追加的硬要求，每条都标现状：

| 要求 | 现状 | 缺口 |
|---|---|---|
| **赛场之上封面 = 当场比赛的高清大图** | 「当场比赛」靠 `cover.portrait.frame_at`（本场集锦抽帧）或 `fetch_wta_cover_photo.py`（WTA 赛后稿头图，4045×2685 真相机）；「高清」靠 `check_cover_resolution.py`（fill ≥ 1.00x 不放大） | ⚠️ **默认仍是集锦抽帧（1080p 压缩流），不是高清大图**——CLAUDE.md 明说「封面用真实照片，不要从视频里抽帧」。要改成：**WTA 头图优先、抽帧只当兜底**，并把「用了抽帧」当降级写进 spec 认领 |
| **文案正文 ≤ 1000 字** | `render/xiaohongshu.py` 有 `MAX_BODY`，`test_qa_xiaohongshu.py:220` 钉死 `len(body) <= MAX_BODY` | 只罩图文线；**视频线的 xhs.txt 要走同一道闸**，别各线各写一个字数上限 |
| **文案 = 小红书风格** | `render/xiaohongshu.py` 的 `build_post_plan`/`XhsPostPlan` + 测试 | 风格散在 playbook §3 和代码里；要统一成「钩子开场 → 单主线 → 互动提问结尾」一套，别每线自己发挥 |

**统一动作**：把这三条从「图文线专属」抬成「全栏目契约」，视频线的 xhs.txt 输出
走同一个 `plan_post`/`MAX_BODY`/封面来源认领，而不是各写一份。

## 七、判据

- 三条线的 workflow 里都出现 L0/L1/L2/L3 对应步骤（位置判据，仿 `test_复制页那道闸
  装在发的那一步`）。
- 三条线的 spec 都过同一套「要么有 X、要么说清为什么」测试（`test_reel_editorial.py`
  那套推广到 interview/explainer）。
- 故意删掉一条线的 L2 检查 → CI 红（自证）。
