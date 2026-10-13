# Native render retry audit

Reviewed against `6402c4ae5d07f0985743522e20a80a53bfa5d8b9`.

The current successful render is difficult to reuse after the same slug is rendered again. `match-reel.yml` uploads the movie to the canonical `reel-<slug>` Release, deletes the local movie, deletes actual narration MP3 files during cleanup, and only then uploads its run artifact. The artifact retains the input manifest, subtitles, narration word boundaries and score masks, but no movie or narration MP3. `compose_native_reel.verified_input()` falls back to the canonical Release when the movie is absent. When another render replaces that Release asset, its bytes no longer match the original run's manifest. The helper correctly refuses them, but the original successful movie is unavailable for strict retry.

This is a transport and retention problem. An old failed QC is not permission to publish, and a retained movie is not a replacement for fresh QC or the unique WeChat receipt.

## Implemented change

Render runs now preserve a separate `native-input-<slug>-<run_number>` Actions artifact after actual movie QC and before Release upload or cleanup. It includes only the movie, native render/input/QC metadata, declared render artifacts, score masks, actual narration MP3 and corresponding WordBoundary files. It uses zero ZIP compression and 14-day retention. A generated whitelist excludes source media, intermediate encodes, downloaded cookies, transcript scratch files and rendered HTML with embedded images. It uploads existing paths without copying media. An upload failure stops Release publication and cleanup.

The composition fetcher prefers this explicit artifact belonging to the selected run. It requires a unique unexpired artifact and rejects ambiguous matches. A native archive that exists but is corrupt or expired never triggers the old fallback. Older runs without a native archive keep their existing artifact fallback and exact movie SHA/size checks. No canonical URL response is accepted unless its actual bytes match the original input manifest. Preserving failed-run diagnostic media does not imply a passing QC.

`native_input_archive.json` records the actual run ID, run number, input head and original file hashes, including each real voice/WordBoundary pair. The pre-Release `render.json` remains the original archived version; later canonical URL fields do not rewrite it. The fetched movie and original archive QC must still agree with actual spec, ASS and render-input bytes. Fresh full-movie QC is still mandatory before publishing a composition.

Voice selection uses one shared whitelist for archive creation and readback. Segment narration comes from the original render projection. Cover narration requires agreement between `cover.narration` and actual `render.json.cover_narrated`; outro narration requires agreement between `outro` (enabled by default) and the actual finite `outro_seconds`. Enabled cover/outro voices retain both `voice_cover`/`voice_outro` MP3 and their real WordBoundary files. Either missing half fails. Disabled paths require no files and do not export stale leftovers. Voice files are never selected with a broad glob.

Run artifact discovery reads every API page with 100 artifacts per page. A native archive on a later page must be discovered before considering the legacy fallback; expiration, ambiguity or corruption remains an error.

This adds one compressed-movie-sized upload to a successful render, so it is not a claimed first-run speed gain. It prevents an avoidable full encode when a verified stream is needed for repair. The previous measured native encodes took 440 and 431.6 seconds. The upload cost must be measured on a real subsequent render; do not turn these encode durations into an unsupported net saving.

## Existing optimizations already present

- Main match-reel checkout excludes unrelated `output/`; the request checkout in the composition workflow serves explicit request validation and is not an accidental duplicate full checkout.
- Push installs the main Python dependencies only. It skips ffmpeg, fonts, Chromium and the cutout model.
- Reattest installs the main dependencies and numpy, and also skips heavy rendering setup.
- Reviewed source staging prefers a same-repository source Release, checks every byte against the actual reviewed SHA, and validates an existing source before reusing it.
- Artifact ZIP recompression has already been disabled for compressed media.

## Validation

Tests authenticate the retained original bytes without requesting the canonical URL, and refuse a present archive with changed word marks, missing actual MP3/movie, wrong run, or failed QC. Existing tests still reject changed movie bytes and wrong head. Run selection tests cover legacy fallback, unique native preference, expired native and ambiguous native identities. The actual workflow selector executes against a fixture containing source media, intermediate encodes and cookies; none is exported. Existing failed-run diagnostic source exclusions and cleanup ordering remain checked separately.

Additional tests cover a native archive on the second API page, cover-only/outro-only/both/neither narration, inactive leftover exclusion, and missing MP3 or word marks in each enabled auxiliary voice. The compose/workflow/cache selection completed with 39 passing tests in 5.08 seconds locally.

These are local contract and real stream-copy tests, not a new hosted upload benchmark. The independent full-movie QC and publication fingerprint/receipt gates remain unchanged.

No volume adjustment, new editorial model, historical-film import, WeChat send, or publication gate relaxation is part of this recommendation.
