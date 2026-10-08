# Copyable publishing-title policy

Effective 2026-10-02 across all columns and pipelines.

- At most 20 Unicode code points in the final copied title. Every digit, Latin letter and punctuation mark counts as one; visual half-width is irrelevant.
- No whitespace, including tabs, non-breaking/full-width spaces, line separators or invisible Unicode format characters.
- Prefer concise wording and dispensable punctuation removal. Preserve numeric set boundaries, score separators, decimals, percentages, question marks and meaningful name punctuation.
- Date, column name and the separator are mandatory parts of the copied title: `10.2赛场之上|孙心然连赢9局过关`. This complete 18-character string includes the prefix. Never remove the prefix to fit. The ordinary display may use spaces; the copyable field cannot.
- A title that still exceeds the budget needs a shorter editorial hook before publishing. Never slice it or remove the required prefix.
- Both primary and alternative copy titles pass the same gate; older archives are not rewritten, but new publication uses current policy.

## Implementation

`src/tennislive/render/copy_title.py` owns normalization and strict final validation. `push_reel.publication_title` and `prepare_copy` cover final reel and interview output in check/page/push. Legacy dated intermediate headline helpers keep their original interface and tests; their visual budget cannot authorize final publication. The shared `split_xhs` / `to_copy_page` outlet covers copyable primary and alternative titles; daily, knowledge, explainer, hotspot and schedule generators preserve date and column while fitting their editorial hooks. Raw publication QA and explainer preflight validate final characters without visual-width exceptions.

The legacy `xhs_title_len` remains only for visual-width uses such as in-frame topic layout and body-line readability. It must not authorize a publishing title.

`data/copy_titles.json` holds explicit publishing-only short hooks keyed by exact slug. The four current match entries match the corrected Sun copy page and pending ATP metadata without changing spec, video, QC, receipt or ledger bytes. Existing explainer topics also have short copy-only hooks where necessary; their in-frame titles remain unchanged.

## Verification

`tests/test_copy_title_policy.py` and `tests/test_final_copy_title_boundary.py` exercise Unicode whitespace, invisible characters, 20/21-character boundaries including ASCII, preserved numeric punctuation, no silent truncation, primary/alternate copy fields, every active explainer and raw QA rejection. Existing pipeline tests cover the generators and public-page version matching.
