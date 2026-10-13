# Production quality gates

- Reference sample (human comparison): `fils-cobolli-cincinnati-2026-sf`.
- Visual evidence: human-reviewed and recorded; no model scores are used.
- Unattended freshness window: 20 hours.

Promote only with: complete structured result and winner-perspective score; schema-valid editorial and PushPlus copy; hashed visual evidence for cold open, ending, and cover; 5–10 segments; bilingual broadcast cold open; ending covering the payoff; same-match photo; valid statistics, sources, metadata, duration, and publication fields; and a passing formal spec validator.

Full completion requires five independently verifiable stages: formal spec, completed render, passed QC, successful PushPlus response, and committed `pushed.json`.

Owner update 2026-10-13: ordinary match-reel QC excludes loudness/RMS/peak/threshold-silence and source-gain comparisons. Source audio is preserved at unity. Audio-stream presence and duration, exact actual speech/caption evidence, visual QC and publication identity remain required; the attestation records loudness checks as removed rather than passed.

Temporary credential/API/network/artifact errors are retryable. Fabricated facts, invalid score direction, wrong person, old cover, low confidence, malformed schema, or failed deterministic QC are blocking and must not be overridden.

An evidence-window failure may receive one bounded correction attempt with exact deterministic feedback. The corrected spec must pass the same gates; a second failure remains blocking.
