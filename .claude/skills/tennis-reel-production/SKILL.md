---
name: tennis-reel-production
description: Produce and audit the Chinese tennis short-video series “赛场之上” with fact-bound editorial copy and time-coded visual evidence. Use when designing, generating, benchmarking, validating, or repairing the automated tennis reel pipeline, its spec, cold open, ending payoff, cover, QC, PushPlus copy, or publication gates.
---

# Tennis Reel Production

Treat this skill as the production contract shared by the production assistant, deterministic renderer, QC, and publisher. Do not compensate for missing evidence by guessing.

## Execution policy

The current production assistant writes editorial copy and reviews footage directly. No external model provider, model API, model credential, or separate model call is required. Provider availability must never block this workflow. Preserve all factual, visual-evidence, subtitle, rendering, QC, and publication gates. This repository copy supersedes the older cloud copy for production, as explicitly authorized by the owner on 2026-11-01.

## Run the workflow

1. Establish a structured match fact packet before writing or inspecting anything. Derive winner-perspective score once and preserve source URLs, event, round, court, rankings, countries, and timestamps.
2. Load `references/editorial.md` for editorial and PushPlus copy. Write using only verified facts. Require schema-valid JSON and reject unsupported claims.
3. Probe the complete source video. Select contact sheets evenly across its full duration and preserve their hashes. For a title-run recap, also source actual footage from earlier rounds; follow the title-run rules in `references/visual-evidence.md`.
4. Load `references/visual-evidence.md` for cold-open, ending, and cover review. Require time-coded visual evidence and confidence; never accept a bare pass/fail answer.
5. Apply `references/quality-gates.md`. Promote a pending draft only when every hard gate passes. A retryable infrastructure failure may wait; a deterministic content failure must stop.
6. Render from the promoted spec, run deterministic QC, then publish through PushPlus and record `pushed.json`. Never treat a successful workflow shell as proof that these stages completed.

## Keep responsibilities separate

- Let the current production assistant decide wording and story structure, not footage windows or factual truth.
- Let the current production assistant classify visible moments and people, not overwrite the structured result.
- Let deterministic code own score direction, timing bounds, schema validation, freshness, rendering, QC, and publication state.
- Require the ending to replay or fully cover the cold-open payoff so the result is not revealed only at the start.
- Require the cover to be demonstrably from the same match. If the evidence cannot establish that, wait or fail rather than substitute an old portrait.

## Benchmark before trusting changes

Use the published reference named in `references/quality-gates.md` as a shadow benchmark. Compare structure and evidence, never copy its players, numbers, conclusions, or timecodes into another match. Run the benchmark without dispatching render, sending PushPlus, or writing publication state.

Approve a workflow or prompt change only when both review scores meet their thresholds and the generated shadow candidate also passes the normal production validator.

## Report outcomes

For success, cite evidence for spec, render, QC, PushPlus, and `pushed.json`. For failure, report only the earliest blocking stage and its run/commit. Do not mask an upstream failure with downstream symptoms.

