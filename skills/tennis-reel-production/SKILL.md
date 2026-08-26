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
