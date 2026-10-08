# Forward production checks and frozen historical diagnostics

The 2026-09-30 scope is forward-only: already-published films are not rerendered,
resent, rewritten or newly certified. A green CI result is not a fresh quality
assessment of those films.

## Narrow inventory boundary

`data/production_history_snapshot.json` records diagnosed findings for four
already-sent productions at revision `c850697251969c419168fd1f5ef7d667b21bbcd7`:
Medvedev 24 titles, Khachanov–Auger-Aliassime, Tabilo–Paul and Bu–Cerundolo.

Only the named inventory assertions may treat an exact frozen row as historical.
The test-only `tests/production_history.py` binds the original spec, posting copy,
sent ledger, PushPlus receipt and per-slug text evidence by SHA-256. Referenced
local assets and non-text output artifacts are additionally bound to frozen Git
mode/blob IDs; absent covers and original per-slug probe paths have explicit
absence markers. A new or changed relevant indexed output binary also re-enables
checks, without fetching media. Materialized local asset edits are detected too;
sparse-omitted binaries use the local Git index identity.

These are repository-snapshot identities, not verification of remote URL bytes.
Changed or missing inputs, newly present formerly absent inputs, new output
evidence, a new slug, an unknown rule or a ledger
without the matching `sent` receipt all re-enable the real checks. No production,
render, preflight, QC or publishing code may import this helper.

CI prints historical findings in a separate visible step before aggregate tests:

    python tests/production_history.py

The report distinguishes frozen findings from inputs that must be checked again.
These records are diagnostic context, not publication permission or QA passes.

## Retained findings and limits

Medvedev's raw-title echo assertion was a legacy inventory false positive: its
dedicated sender separates the leading title from the published body. It does
not establish that the published body repeated the title.

The prior read-only final-media audit also identified foreground-English
caption-gap candidates at Rome 286.061–288.200s and 291.121–292.301s, and Brisbane
333.866–337.086s. Sampled final frames lacked commentary captions. Subjective
listening and full semantic coverage remain unproven; this change does not repair
or revalidate those old media intervals.

New production remains hard-gated. In particular, missing Winners/UE means
`waiting_stats` / `not_verified`, even after truthful `unavailable`, `blocked` or
`not_connected` source checks. One trustworthy complete Match-total evidence
source is enough; no unavailable provider must be falsely marked successful.
