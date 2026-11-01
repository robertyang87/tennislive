# Production quality gates

- Published benchmark: `fils-cobolli-cincinnati-2026-sf`.
- Editorial review benchmark threshold: 80/100.
- Visual review benchmark threshold: 85/100.
- Visual decision confidence: at least 0.80.
- Freshness window for an unattended candidate: at most 20 hours.

## Promotion gates

Require a complete structured result; schema-valid Editorial review editorial and PushPlus copy; hashed Visual review evidence for cold open, ending, and cover; five to ten segments; a bilingual broadcast cold open; an ending covering the payoff; same-match photo; valid statistics, sources, metadata, duration, and publication fields; and a passing formal spec validator.

## Completion proof

Call a run fully successful only when five separate artifacts are verifiable: formal spec, completed render, passed QC, successful PushPlus response, and committed `pushed.json`. An editorial response, green probe, or successful render alone is insufficient.

## Failure policy

Classify missing credentials, temporary API/network errors, or unavailable artifacts as retryable. Classify fabricated facts, invalid score direction, wrong person, old cover, low-confidence evidence, malformed schema, or failed deterministic QC as blocking. Do not automatically publish or override a blocking failure.

