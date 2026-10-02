# Copyable publishing-title policy

Effective 2026-10-02 across all columns and pipelines.

- At most 20 Unicode code points in the final copied title. Every digit, Latin letter and punctuation mark counts as one; visual half-width is irrelevant.
- No whitespace, including tabs, non-breaking/full-width spaces, line separators or invisible Unicode format characters.
- Prefer concise wording and dispensable punctuation removal. Preserve numeric set boundaries, score separators, decimals, percentages, question marks and meaningful name punctuation.
- The copyable title does not automatically carry notification-only date/column/emoji prefixes. The existing body, column metadata and in-frame typography are not rewritten.
- A title that still exceeds the budget must be rewritten before publishing. Never slice it or silently omit words to force a pass.
- Both primary and alternative copy titles pass the same gate; older archives are not rewritten, but new publication uses current policy.

## Implementation

`src/tennislive/render/copy_title.py` owns normalization and strict final validation. `push_reel.publication_title` and `prepare_copy` cover final reel and interview output in check/page/push. Legacy dated intermediate headline helpers keep their original interface and tests; their visual budget cannot authorize final publication. The shared `split_xhs` / `to_copy_page` outlet covers copyable primary and alternative titles; daily, knowledge, explainer, hotspot and schedule generators produce concise titles. Raw publication QA and explainer preflight validate final characters without visual-width exceptions.

The legacy `xhs_title_len` remains only for visual-width uses such as in-frame topic layout and body-line readability. It must not authorize a publishing title.

## Verification

`tests/test_copy_title_policy.py` and `tests/test_final_copy_title_boundary.py` exercise Unicode whitespace, invisible characters, 20/21-character boundaries including ASCII, preserved numeric punctuation, no silent truncation, primary/alternate copy fields, every active explainer and raw QA rejection. Existing pipeline tests cover the generators and public-page version matching.
