# Djokovic–Zverev production audit

审核者：production_qc；2026-10-04；只读生产审计，最终 MP4 尚未验收。

代码基线：8acb85564971d28ad77edafbcafe304659fe947f（origin/main 与本 worktree HEAD）。
本地名为 main 的 ref 较旧，不作为最新规则依据。

已读 CLAUDE.md、tennis-owner-taste、tennis-pipeline-ops 与 tennis-video-craft 的当前相关规则，以及 docs/forward-production-quality.md。

## 可复用输入

- probe37208304068 的机械探测：1920×1080、25fps、319.181497秒；scene_cuts、contact/score墙、silent_audio、audio_levels、board扫描。均为辅助证据，不替代完整原声核验或最后成片抽检。
- 已实际打开 score_00、score_07 及精确源片抽帧，不能以“JSON有数据”代替实帧。
- 精确源片：`/workspace/djokovic-cja-research/source/cjaHThpISKk.mp4`，122255880字节。
- SHA256：`2a62a85fb499f153e97fa3074294eb1be476a818aa480291b65b43a3e94484e2`。
- source-manifest.json 说明为原 Actions cache 的逐字节复制，绑定原 probe run；重新下载的同 URL 若字节不同，不能沿用原声 review。
- probe 的标定 ATP 搜索框 `[98,920,519,1029]`：1596帧，1396有板，24未解决。不要直接抄较窄的 guess `[98,920,394,1029]` 作为全片框。
- `point_ends=[]`，只有 point_ends_guess，不能把 guessed 死球当已确认完整得分。
- `captions=null` 与 captions_debug 中429错误说明未拿到字幕，不表示源片没有英文解说。

## 不能直接复用的自动产物

- pending draft 的 `_notes` 明确使用 deepseek-v4-pro；`_visual_evidence.model=MiniMax-M3`。按2026-09-27禁令，新工作需重新依据实际素材和事实制作。
- `scoreboard.json` 来自带 MiniMax 的 prepare_alignment 步骤，无源SHA或模型证据自证，且已出现实帧事实错误：0.5秒原板为首局AD，10.5秒原板局分1:0，14.5秒已2:1；JSON前30秒多次写0:0。
- 自动三段旁白、窗口、标题、turning-point选择、模型冷开场与 ending 判断都不能未经重核转正。模型 cold_open 285.58开始已在赛点之后；真正终局完整窗口须由源动作确认。
- draft 无 Winners/UE、无完整日期、无正式高清封面、无本条 audio review；`editorial` 不符合完整合同（缺mode，human_context是字符串）。

## 必备字段与硬闸

正式slug复用 `zverev-djokovic`，避免同视频并发认领冲突。

- `source_url=https://www.youtube.com/watch?v=cjaHThpISKk`；多源时用有序 `sources`，明确每段source；官方身份与本场来源另留事实记录。
- `cover.eyebrow=赛场之上`，cover.matchup 每人 `name/name_en/country/rank`；`cover.winner=德约科维奇`，`cover.result=4-6 6-4 6-4`，高清正式照片、来源与裁切参数；名字列序与stats.a/b一致。
- `_match` 保留 verified结果、源id、两人、分盘；增加已核实标准日期或带时区start_utc。自然北京时间日期与时段写入坐标旁白；发布时刻不冒充开球时刻。
- `editorial.mode=match_review`，question必须问句；thesis非空；beats至少三个非空进程节点；`human_context={angle,facts:[...],sources:[HTTP(S)...]}`。
- topbar.line1明确赛事/轮次，line2须为赢家视角结果，ATP tour身份能被确定性profile识别。
- `stats.a/b.winners` 与 `.ue` 为四个已核实非负整数；不能以null、0、blocked替代未知值。
- `stats._winners_ue_evidence`：`period=Match`、provider、method(api/page/broadcast/user_screenshot)、source_url或source_path+完整source_sha256、match_date、checked_at(时区)、winner_result、matchup两列、winners两值与ue两值；唯一映射cover.matchup。此slug无单片省略授权。
- 视频段每段start/end/取景/旁白或quote，关键点保留发球开始至结果反应；源关键点缺失以原生title_card诚实说明，不用其他回合冒充。正文不用任意photo/image。
- scorebox搜索框可复用；score_inset按真实有板段声明，必要时段级框。源板全部信息、提示出现/消失、主板缩放一致、轮廓外透明要用最终MP4核。
- quote显式 `{at,end,text:"English\n中文"}`，at/end是段内秒数；不能同段同时有narration和quote，不能字幕块重叠，不给自配TTS添加英文译文。
- 原声证据 `data/audio_reviews/zverev-djokovic.json`：schema=`tennislive.foreground-audio-review.v1`，plan_sha256=`foreground_audio_gate.plan_hash(spec)`，每个视频窗口对应零基index/transcript_path/transcript_sha256（含有TTS、mute窗口）。
- transcript JSON：source_url、完整source_sha256、真实method、实际reviewer、带时区reviewed_at、status=complete、reviewed_from/to覆盖全窗口、foreground_english每句绝对source start/end/en/zh；确实无英语时空数组+真实no_foreground_english_reason。不得编造人工听审或把ASR-only当complete。
- 正式 `push.auto=true` 按root已确认完整流程授权保留；native分支上input push=false，分支自动微信门禁负责阻挡。root负责正式发布。

## 生产入口与命令（此审计未执行render/workflow）

```bash
PYTHONPATH=src python tools/production_preflight.py --spec specs/reels/zverev-djokovic.json --column 赛场之上
PYTHONPATH=src python tools/build_match_reel.py render --dry-run --spec specs/reels/zverev-djokovic.json --outdir output/2026-10-04/reel/zverev-djokovic --voice zh-CN-YunjianNeural --rate +6%
PYTHONPATH=src python tools/taste_preflight.py --slug zverev-djokovic
PYTHONPATH=src python tools/preview_segments_local.py --slug zverev-djokovic --out data/research/djokovic-cja-20261004/qc/segments-preview.jpg
PYTHONPATH=src python tools/render_cover_local.py --slug zverev-djokovic --out data/research/djokovic-cja-20261004/qc/cover-preview.jpg
```

若root采用本地render，`build_match_reel.py render --source /workspace/djokovic-cja-research/source/cjaHThpISKk.mp4` 可以锁定审听源片字节。

match-reel dispatch有25项；render实际仅需mode/render与slug，voice/rate可显式确认；url等赛事字段仅probe自动备料使用。分支render会上传Release，并非私有预览；root已负责授权流程。
若只是补机械probe，CLI build_match_reel.py probe无内容模型；workflow mode=probe只在home非空时启用MiniMax alignment、DeepSeek assemble与模型visuals。新工作不要带home/away去触发该自动内容链。
main上render失败还有DeepSeek自动修复；分支该step跳过。

## 比分板真实发现（已发给独占ATP工程代理）

实际六帧与5帧scan/mask证据在本目录：source-atp-samples.json、unchanged-atp-mask-samples.json、source-*.jpg、board-*.jpg、mask-*.mkv。

|源时刻|实帧|旧scan结果|判断|
|---|---|---|---|
|0.5|首盘宽景，有AD|右缘393|与真板匹配|
|10.5|暗蓝背景兹维列夫特写，无小分|右缘342–343|与真板匹配|
|32.5|德约近景，无小分|右缘342–343|与真板匹配|
|108.5|首盘结束6:4、AD，无饱和蓝格|None 5/5|源板实际仍在，签名漏检|
|280.5|决胜盘5:4、AD，暗衣物背景|右缘519 5/5|实际约485，多约34源px|
|282.5|终局6:4，小分已消失|右缘519 5/5|实际约435，多约84源px|

六帧主板垂直约920–1029，搜索框高度109px，未见类似WTA旧框45px球场被搬回的问题。问题集中于暗背景横向兜底与盘末无蓝签名；实际修后再核，不因此改无关公共工具。

ATP当前proof只记录mask_sha256/segment/frames/edges/right，无source_sha256/spec_sha256。L2验证mask和scoreboard_qc hash，却不能独立证明每份mask源身份或本场真边界；最终独立QC须结合音频source绑定、真实源片与MP4取景核查。不得把pass或mask hash当视觉通过。

## 最终独立QC计划

root交实际MP4与完整输出sidecars后，在本目录记录最后hash和报告。

1. 核render.json、render_inputs.json、audio_review_binding.json、ASS、scoreboard_qc与所有score_masks；核film/ASS/binding封印与当前spec/plan/review及本源SHA一致，逐句缺口或不确定仍blocked。
2. 技术完整解码：`ffmpeg -v error -xerror -i <actual.mp4> -map 0:v:0 -map 0:a:0 -f null -`，输出log和退出状态；ffprobe核1080×1440、帧率、视频/音频时长、完整音轨。
3. 执行 `PYTHONPATH=src python tools/check_reel_landed.py --slug zverev-djokovic --spec specs/reels/zverev-djokovic.json --film <actual.mp4>`；注意脚本会先撤旧qc_attestation、全绿再签名，root知悉后在实际输出上运行。看输出统计，不只看返回值。
4. 抽全画布首帧、封面稳定帧、坐标头条、每张title/stat卡及字幕帧、尾部稳定帧；逐卡核深蓝、语义两行/同字号、内容小标题、底部品牌在字幕之下及安全区。
5. 实际MP4宽景、亮/暗背景特写、首/次/末盘宽度、当前分出现消失、盘末无蓝格、原生stats变化、关键分提示出现/消失；逐点对源内容和透明轮廓，不截成小图只看板。
6. 关键点前情、完整动作、结果、即时人物反应与叙事一致；冷开场与终局兑现，缺官方动作的说明如实呈现；不能误称团队庆祝是球员本人。
7. 按源英文字句与ASS实际时间轴检查中英字幕、句头句尾、读完时间及混音；ASR交叉核验只能声明真实方法。纯图片和结构验证不能声称已完整听看片。

当前结论：生产输入未齐且原ATP扫描存在已证实问题；没有最终MP4视觉通过结论。此审计未发布、未触发workflow、未更改公共工具或正式spec。
