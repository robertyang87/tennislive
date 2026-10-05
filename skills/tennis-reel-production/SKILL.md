---
name: tennis-reel-production
description: Produce and audit “赛场之上” tennis videos with DeepSeek copy, MiniMax visual evidence, deterministic rendering, QC, PushPlus delivery, and publication-state proof. Use for automated reel generation, benchmarking, quality gates, or pipeline repair.
---

# Tennis Reel Production

Use this as the production contract shared by the text model, vision model, renderer, QC, and publisher.

1. Build a verified match fact packet and derive winner-perspective score once.
2. Load `references/deepseek.md` for editorial and PushPlus copy.
3. Probe the complete source and sample contact sheets across its full duration.
4. Load `references/minimax.md` for cold-open, ending, and cover evidence.
5. Apply `references/quality-gates.md`; never promote by model confidence alone.
6. Render, run deterministic QC, send PushPlus, and record `pushed.json` only after every gate passes.

DeepSeek owns wording and story structure, not footage or factual truth. MiniMax owns visible classification, not structured results. Deterministic code owns score direction, timing, schema, freshness, render, QC, and publication state. Missing evidence must wait or fail; neither model may guess.

Run prompt changes against the published shadow benchmark without rendering, publishing, dispatching another workflow, or writing publication state.

## Official footage and missing key points (owner update 2026-10-04)

For every column’s future production, use official footage only. Search available official sources first and record key-point coverage. If a key point remains missing, use a native `title_card` and fact-checked narration to explain the situation and outcome. Owner update 2026-10-05: keep footage gaps in internal production and QC records only. Do not mention missing official highlights or footage in audience-facing narration, subtitles, title cards or publication copy; directly explain the verified match progression and turning points. Never substitute another rally or claim complete visual coverage. Preserve complete available official key actions and reactions. This fallback does not waive statistics, full-window audio review, bilingual subtitles, final QC or publication evidence. Cover photos retain the existing official-gallery and professional agency/photographer policy (including AP, Getty and Jimmie48), not a WTA-website-only restriction.

## Global semantic line layout (owner reconfirmation 2026-10-04)

All columns, cover titles and native text cards must break lines at complete meanings. Prefer one or two lines for title/thesis cards. Never split a player name, fixed phrase or score, or leave an orphan character. Balance the two lines visually without sacrificing meaning; center them and use a shared font size. Explicit newlines are authoritative and must survive rendering; browser rewrapping is forbidden. Simplify/rewrite first, then reduce the shared size moderately to fit the longest line if necessary; if it still cannot fit, fail production preflight. Inspect actual native previews and final captioned frames, keeping main text, subtitles and bottom branding separate. For the Sabalenka card, preserve “5次反扑机会落空” / “萨巴伦卡两盘出局” as two complete lines.

The small framed `kicker` above each native chapter card is a short title specific to that card’s content (e.g. “错失机会”, “上次交手”, “素材说明”). Do not repeat the column name (“赛场之上”, “赛后开麦”, “网球有故事”) on every card. Write each title for its own topic; omit the optional frame if no useful title is available. Existing cover column labels are unaffected.

## Global navy card design (owner update 2026-10-04)

All columns use a redesigned, visually pleasant navy system for native cards: blue-black foundations, soft low-saturation blue lighting, blue information surfaces, readable white text and restrained neutral dividers. This includes chapter/stat cards, interview explainers, 网球有故事 static image cards and video diagrams/backdrops, outro cards, Pillow fallbacks and the cached outro master. The supplied image is inspiration for color and finish, not a layout to copy. Use shared `design_tokens.DARK` and `CARD_BACKGROUND_CSS`; do not leave independent green backgrounds or large lime/mint washes. Lime remains the brand/key emphasis and mint retains its win semantics. Verify actual native previews and cached-master frames. Existing semantic line breaks, contextual kicker titles and brand/subtitle safe spaces remain mandatory. This replaces the former green-background policy.
