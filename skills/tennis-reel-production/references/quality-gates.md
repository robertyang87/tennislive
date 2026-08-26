# Production quality gates

- Published benchmark: `fils-cobolli-cincinnati-2026-sf`.
- DeepSeek shadow-score threshold: 80/100.
- MiniMax shadow-score threshold: 85/100.
- Visual confidence threshold: 0.80.
- Unattended freshness window: 20 hours.

Promote only with: complete structured result and winner-perspective score; schema-valid editorial and PushPlus copy; hashed MiniMax evidence for cold open, ending, and cover; 5–10 segments; bilingual broadcast cold open; ending covering the payoff; same-match photo; valid statistics, sources, metadata, duration, and publication fields; and a passing formal spec validator.

Full completion requires five independently verifiable stages: formal spec, completed render, passed QC, successful PushPlus response, and committed `pushed.json`.

Temporary credential/API/network/artifact errors are retryable. Fabricated facts, invalid score direction, wrong person, old cover, low confidence, malformed schema, or failed deterministic QC are blocking and must not be overridden.
