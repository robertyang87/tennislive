# Forward production quality contract

The owner’s 2026-09-30 instruction is to leave old films alone and prevent new
production failures. Historical inventory diagnostics are not validation passes;
see `data/production_history_snapshot.json` and the CI-only tests helper. Actual
preflight, render and final QC never consult that snapshot.

## Global time wording

All columns use fact-checked date and a natural Beijing-time daypart: 夜里、凌晨、
清晨、早上、上午、中午、下午、傍晚、晚上、深夜. No specific hour or minute is required.
Keep the real event date/timezone; publication time and a scheduled Not Before
bound do not establish actual start time. Canonical owner-taste/editorial docs
and the generation prompt use this same rule.

## Match statistics

New 赛场之上 production requires both players’ Match-level Winners and UE with
provenance, date, score and uniquely mapped player columns. A reliable complete
source is enough; do not wait for every provider. Query official stats/editorial,
broadcast, available MCP or normally accessible TNNS. A blocked challenge is a
stop for that source, not absence. Missing, blocked, unknown and numerical zero
are different states. If exact values remain missing, the item is waiting_stats;
source-check notes do not waive the requirement.

## Original English and our narration

Every selected video window, including TTS-bearing windows and attenuated `mute` windows, needs a retained full-window audio
review. Foreground English needs original English plus Chinese, including clauses
before/after an existing cue. Our own Chinese TTS has Chinese-only subtitles;
split foreground source speech into separate windows rather than overlaying an
English translation of our TTS. A bare skip-reason or an ASR-only flag is not a
completed review. Official timed captions or cross-checked ASR are accepted as
evidence when the entire window has been checked and no uncertain span remains;
uncertain words/timecodes stay blocked. Reviewers must actually inspect the
claimed evidence; do not fill status or reviewer fields just to satisfy validation.

The producer records `data/audio_reviews/<slug>.json` with:

- schema: `tennislive.foreground-audio-review.v1`
- plan_sha256: `foreground_audio_gate.plan_hash(spec)`
- one segments entry per retained original-audio window, with zero-based index,
  transcript_path inside the repository, and its exact transcript_sha256

Each retained transcript JSON contains source_url, source_sha256, method
(`listened_with_transcript`, `asr_then_listened`, `verified_source_captions` or `asr_cross_checked`), actual reviewer, reviewed_at
with timezone, complete status, reviewed_from/reviewed_to source seconds covering
the whole selected window, and all foreground_english utterances. Each utterance
has absolute source start/end, faithful en and zh. If there is genuinely no
foreground English, record an empty list and the actual
no_foreground_english_reason. Do not use “only scores” to omit audible English.

The spec's original-audio quote cues must cover every recorded utterance with
explicit timing and both languages. Unresolved wording or missing evidence stays
waiting_audio_review. Additional `source_audio` is rejected until premuxed into an identified source and reviewed again; it cannot reuse an earlier review. The renderer verifies actual downloaded source bytes before
encoding and writes audio_review_binding.json. Final QC binds that record to the
same plan/review, checks the render-time film/ASS/audio-binding hash seal (so editing an ASS sidecar after encoding cannot manufacture a pass), then rejects missing cues or overlapping
bilingual blocks, and rejects added English translation lines in our TTS windows.

These checks verify evidence and subtitle coverage; they cannot certify a false
human review, discover speech omitted from a fabricated transcript, or replace
watching/listening to the final mix. Missing evidence is a blocker, never a pass.

## Footage

赛场之上 defaults to match video throughout. Arbitrary inserted photo/image segments
are rejected; native statistical and chapter cards remain supported. Cover photos
are unaffected. A requested exceptional photo treatment requires a separate
reviewed change, not a hidden exemption flag.

## Complete process and turning-point coverage (2026-10-03)

The owner requires every future video to explain the process clearly, retain complete footage of turning points and key moments, and convey emotion through editing, original sound, evidence-backed narration and genuine reactions. Duration follows the story; do not shorten necessary beats to meet an arbitrary short runtime or pad it with repeated shots. See the owner’s exact instruction in `.claude/skills/tennis-owner-taste/SKILL.md`. Record each key turning point, the preceding situation, complete action, outcome and immediate reaction. The owner’s 2026-10-04 update applies to every column’s future production: use official footage only. Search available official sources first and record coverage. If a key point remains missing, continue with a native `title_card` and evidence-backed narration explaining its score/context, event and outcome, explicitly stating the official highlight does not include the complete action. This is an honest text explanation, not a claim of complete visual coverage. Never substitute another rally for the missing point. Preserve complete available official key actions and genuine reactions; do not pad static cards or repeat shots. The footage fallback does not waive statistics, audio-review, bilingual-subtitle, final-QC or publication-evidence requirements. Existing cover-photo policy continues to admit official galleries and established professional agency/photographer sources such as AP, Getty and Jimmie48; it is not restricted to the WTA website. Reassign agents to current production gaps and finish actual film review before publishing. Reach/virality remains a creative goal, not a guaranteed quality result.

## Key commentary and bilingual subtitles (2026-10-03)

All columns should actively retain as much compelling original commentary during key moments as the story supports, with accurately checked Chinese and English subtitles. Keep complete sentences and reactions, and place our explanatory narration between source-commentary windows. Subtitle English speech with the original English and faithful Chinese translation. Do not replace exciting source commentary merely to simplify TTS or captions; preserve the full action and inspect the actual final mix and caption timing. The owner’s exact instruction is retained in the canonical owner-taste skill. Existing source-audio evidence and honest review-method requirements remain in force.

全栏目封面标题与字卡按完整语义分行，不拆人名、固定词语或比分，不留孤字末行。两行居中、共用字号并尽量视觉平衡，不能为了等长拆开意思。显式换行必须保留，禁止浏览器二次自动折行；先简化和调整文案，必要时按最长行真实宽度适度统一缩字号，仍放不下制作预检就拦住。逐张检查实际原生预览和最终字幕帧，正文、字幕和底部品牌各有空间，不以 JSON 的换行符作为已正确显示的证据。章节卡上方小框用契合当前内容的短标题（如“错失机会”“上次交手”“素材说明”），不要每张都写“赛场之上”等栏目名；逐卡拟定，不机械重复。没有合适的小标题时省略小框，不用栏目名凑数。封面栏目标签沿用既有口径。2026-10-04 用户再次确认固定为全局规则，原话见 owner-taste 的 10-03 分行条目。

字卡品牌“网球时差 · TENNIS JETLAG”放在画布底部安全边距内；检查实际字幕帧，确保品牌在字幕下方且不遮挡，不把品牌抬到页面中段。

## 2026-10-04：原生比分板的紧边界和透明提示条

用户要求按源板实际宽高回贴，并指出多裁入球场产生“膏药”观感。源搜索框与最终可见蒙版分开：主板及短关键分提示分别测真实边界，保留所有可读原生信息和相对位置，使用同一缩放比例；周围球场、提示条右侧和圆角外像素透明。不要为提示条出现而缩小主板，也不把缺损源提示补造成完整文字。具体规则和实帧检查见 tennis-owner-taste 的同日条目。
