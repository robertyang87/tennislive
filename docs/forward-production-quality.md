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

## Approved one-film decision: Zheng–Shi, 2026-10-01

For `zheng-shi-beijing-2026-r1` (WTA 1020/2026/LS070), the approved
single-film editorial decision omits both Winners/UE rows. The gate binds the
exact episode identity, date, result and decision record. Unknown values are
removed, never zero-filled. Other episodes and all other production gates
remain unchanged.
