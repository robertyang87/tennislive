# Actual produced film verification

Native render37103801290 completed successfully on2026-10-03. The Release file was independently downloaded into a temporary directory and byte-verified, with an entire-stream ffmpeg error-level decode completing at exit0. The actual original movie is1080×1440,25fps,186.4 seconds and80,121,748 bytes. Video and audio tracks end at186.400000 and186.389333 seconds.

Film SHA256: `b62142669feb6220621e0663bc4c2f9128129193c0564f044639b5372272b192`. Native check_reel_landed reported0 failed checks; its QC attestation binds the current spec, actual ASS, movie and render-input projection.

Release URL: https://github.com/robertyang87/tennislive/releases/download/reel-djokovic-bu-beijing-2026-r2/djokovic-bu-beijing-2026-r2.mp4

All ten actual narration files are shorter than their own segment. The narrowest margin is0.324 seconds at0-based segment15 (match point), with a5.016-second MP3 and5.34-second window. Long rallies keep audible court ambience; narration-free seconds are disclosed warnings, not digital silence.

A720px-wide dialogue review copy was generated with the repository review_copy.py. It is a separate review version; publication uses the verified1080px original. No WeChat send is asserted. Branch render usedpush=false; production merge remains subject to the repository exact-head CI rule.

Temporary source-export and render-dispatch workflows have been removed. No legacy exceptions or unrelated old-film edits were made. Actual movie visual QC is recorded in final-visual-qc.md: all186 one-second representative frames, key full-size frames and7 transitions sampled at subsecond spacing passed. No source human listening is claimed.

The original official JPEG contains a real EOI at offset152915 and24 bytes after it. It fully decodes at1920×1280. CI erroneously required EOI to be the last nonzero bytes; the bounded test correction preserves the original asset bytes and uses full decoder validation for JPEG files with trailing data. Truncated or EOI-missing files must remain rejected. This does not weaken or exempt the five separate published-episode baseline failures.
