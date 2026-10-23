---
name: tennis-reel-production
description: Produce and audit “赛场之上” tennis videos with human-written copy, human-reviewed visual evidence, deterministic rendering, QC, PushPlus delivery, and publication-state proof. Use for reel production, quality gates, or pipeline repair.
---

# Tennis Reel Production

## 2026-10-23：三栏目统一使用品牌前缀片尾

账号所有者要求“统一替换掉这个片尾动画，按栏目分类”，并确认账号是网球时差。三栏目正式片尾统一为原版账号logo减速滚入、停稳后显示“网球时差 · 栏目名”和“时差归我 好球归你”；大字使用同一字号。赛场之上、赛后开麦、网球有故事按实际栏目选择不同母版，包括走比赛剪辑产线的网球有故事。背景球场按标准尺寸投影，发球线止于单打边线，中线只在发球区内；球网单独虚线表示。固定口播仍为“关注网球时差，时差归我，好球归你。”，本次从原母版精确复制AAC音轨，不重合成、不处理响度。新母版约4.12秒，60fps/48000Hz双声道；出片按目标流参数转码，口播较长时保持最终画面，不截断。方案与重建命令见[三栏目片尾](../../docs/global-column-outros.md)。已发布影片不重渲、不重推。


Use this as the production contract shared by the human editor, renderer, QC, and publisher.

## 2026-10-21：全局文案与原声补充

所有栏目写稿、改稿和审稿执行[共享口味规则](../../.claude/skills/tennis-owner-taste/SKILL.md)的10-21「文案、姓名读音与原声对应」及[写稿指南](../../.claude/skills/tennis-editorial/SKILL.md)的当前口径：比赛说轮次；个人成绩从8强起说8强、4强、亚军、冠军，较早出局说实际第几轮。费塞特的「塞」按用户指定读sai，显示姓名不改，声调不擅自补定。精彩原声保留完整语意并逐句配中英文字幕；旁白指向具体赛后发言时核对应采访，缺失只记内部待补，不能冒称已经采用。文案、转场以因果和时间连贯衔接，让真实原声承接情绪。

规则同步不代表当期音频、字幕或采访已修复；必须分别记录实际完成状态，不能继承改稿前的配音审批或成片QC。

## Owner global voice update 2026-10-19

All columns' new narration must plan semantic emphasis and pauses, resolve polyphonic characters in context, and verify the actual delivered audio. Follow [the global voice workflow](../../docs/global-voice-quality.md): script → semantic reading plan → a few representative samples → all actual audio inputs reviewed → scoped rewrites/pronunciation fixes → frozen reuse → final-film seam review. Unsupported required backend controls fail before synthesis; optional degradation must warn explicitly. ASR, word marks and F0 are bounded evidence, never a fabricated full listening approval. Historical published films are not automatically rerendered or resent.

## Owner update 2026-10-13: remove loudness processing and checks

For ordinary native match reels, preserve source audio at unity and remove automatic gain, ducking and normalization. Do not scan source/final loudness, predict threshold silence, compare source gain/PCM, or repair naturally quiet audio based on those checks. Keep pronunciation review, complete source speech, caption timing, audio-stream presence and duration, visual QC, artifact hashes and unique PushPlus receipts. Historical loudness rules are superseded for this production path; other pipelines and explicitly approved special audio modes retain their own contracts. Do not rerender or resend published movies merely to apply the new rule.

1. Build a verified match fact packet and derive winner-perspective score once.
2. Write editorial and PushPlus copy by hand against the verified fact packet.
3. Probe the complete source and sample contact sheets across its full duration.
4. Record cold-open, ending, and cover evidence by human review of the contact sheets.
5. Apply `references/quality-gates.md`; never promote on an unreviewed draft alone.
6. Render, run deterministic QC, send PushPlus, and record `pushed.json` only after every gate passes.

The human editor owns wording and story structure, not footage or factual truth. Visible classification is a human review task recorded as evidence, not structured results. Deterministic code owns score direction, timing, schema, freshness, render, QC, and publication state. Missing evidence must wait or fail; no one may guess.

Check editorial-rule changes against the published reference sample without rendering, publishing, dispatching another workflow, or writing publication state.

## Avoid repeated preparation and false rework

Use [the measured speed review](../../docs/reel-speed-review-2026-10-12.md) when production is slow. Read native stage timings and the current CI duration list before changing encoding or removing tests.

- Run `production_preflight.py` before TTS and encoding. Custom scoreboxes need real same-source calibration for every declared box; a bounded scan establishes calibration only, never full-window visual approval. In sparse checkouts, materialize the source's existing probe JSON before diagnosing missing evidence.
- Run `reel_review_files.py --slug <slug>` before publication and use its `--stage` path for audio evidence. Follow the index's actual transcript paths, not an assumed sibling directory.
- After changing card narration or quote layout, run the audio-review readiness check **before dispatch**. Use explicit `--rebind-plan` only to validate the entire current plan against unchanged, complete packets; it updates the index hash, never review conclusions or timestamps. Changed source bytes still need their original matching archive or a new review. See [the 2026-10-14 preparation review](../../docs/reel-speed-review-2026-10-14.md).
- Preview the actual native ASS with the frozen TTS bundle before the full render. Declared English match-player names now use display-only nonbreaking spaces; inspect long captions, explicit line breaks and bottom placement in real frames. Text/time evidence remains unchanged.
- Freeze editorial audio inputs before expensive review. Reuse exact unchanged content caches and review evidence only while their source, voice, parameters, audio-plan and artifact hashes still match. Recheck changed inputs; do not turn cache reuse into a new listening claim.
- Assign disputed visual findings to an exact movie SHA, frame index and original PNG from the existing manifest. Inspect that PNG before requesting a rerender; a neighboring contact-sheet tile cannot establish the finding. Close a finding when the original frame disproves it.
- Run targeted checks during implementation and one complete check on the final code/evidence before merging. Do not keep rerunning passed checks without a changed input, new failure or unresolved concern. Rendering and publication must still use fresh on-disk duplicate detection, not a persisted batch-validation inventory.

## Official footage and missing key points (owner update 2026-10-04)

For every column’s future production, use official footage only. Search available official sources first and record key-point coverage. If a key point remains missing, use a native `title_card` and fact-checked narration to explain the situation and outcome. Owner update 2026-10-05: keep footage gaps in internal production and QC records only. Do not mention missing official highlights or footage in audience-facing narration, subtitles, title cards or publication copy; directly explain the verified match progression and turning points. Never substitute another rally or claim complete visual coverage. Preserve complete available official key actions and reactions. This fallback does not waive statistics, full-window audio review, bilingual subtitles, final QC or publication evidence. Cover photos retain the existing official-gallery and professional agency/photographer policy (including AP, Getty and Jimmie48), not a WTA-website-only restriction.

## Global semantic line layout (owner reconfirmation 2026-10-04)

All columns, cover titles and native text cards must break lines at complete meanings. Prefer one or two lines for title/thesis cards. Never split a player name, fixed phrase or score, or leave an orphan character. Balance the two lines visually without sacrificing meaning; center them and use a shared font size. Explicit newlines are authoritative and must survive rendering; browser rewrapping is forbidden. Simplify/rewrite first, then reduce the shared size moderately to fit the longest line if necessary; if it still cannot fit, fail production preflight. Inspect actual native previews and final captioned frames, keeping main text, subtitles and bottom branding separate. For the Sabalenka card, preserve “5次反扑机会落空” / “萨巴伦卡两盘出局” as two complete lines.

The small framed `kicker` above each native chapter card is a short title specific to that card’s content (e.g. “错失机会”, “上次交手”, “素材说明”). Do not repeat the column name (“赛场之上”, “赛后开麦”, “网球有故事”) on every card. Write each title for its own topic; omit the optional frame if no useful title is available. Existing cover column labels are unaffected.

## Global navy card design (owner update 2026-10-04)

All columns use a redesigned, visually pleasant navy system for native cards: blue-black foundations, soft low-saturation blue lighting, blue information surfaces, readable white text and restrained neutral dividers. This includes chapter/stat cards, interview explainers, 网球有故事 static image cards and video diagrams/backdrops, outro cards, Pillow fallbacks and the cached outro master. The supplied image is inspiration for color and finish, not a layout to copy. Use shared `design_tokens.DARK` and `CARD_BACKGROUND_CSS`; do not leave independent green backgrounds or large lime/mint washes. Lime remains the brand/key emphasis and mint retains its win semantics. Verify actual native previews and cached-master frames. Existing semantic line breaks, contextual kicker titles and brand/subtitle safe spaces remain mandatory. This replaces the former green-background policy.


### 2026-10-13：预检与正式渲染复用实际配音

赛场之上预检用 `--check-narration --tts-bundle-out ZIP` 保留真实 MP3 和 WordBoundary；审音以这份实际字节为准，正式渲染用 `--tts-bundle-in ZIP` 严格复用。工作流 narration 完整生成配音后发布有限小包，render 从 narration record 自动恢复并在下载源片前查当前声音请求。无记录允许首次合成；有记录但引用、哈希或声音参数不匹配必须修复或重新预检，不允许静默重合成。只改取景、字幕或时间窗不使声音失效。快照不是 QC 通过凭据，不恢复响度、静音或增益检查。完整用法见 `docs/reel-frozen-tts-bundle.md`。



## Owner update 2026-10-23: shared content-adaptive transition cards

All future transition cards in every column must reference and reuse [the global transition-card contract](../../docs/global-transition-cards.md) and `tennislive.video.transition_cards`. Editorial binds complete semantic lines and one relationship to verified facts; the component chooses geometry and matching motion for turns, scores, comparisons, chronology or a sourced person photo. Preserve existing navy, native fonts, subtitle/brand/story-label safe areas, fixed scoreboard and complete narration. Native `title_card` uses motion by default; explainer transitions declare `visual.layout=transition`. Reuse exact caches; do not manufacture facts, roll through fake scores or rerender/resend historical movies.
