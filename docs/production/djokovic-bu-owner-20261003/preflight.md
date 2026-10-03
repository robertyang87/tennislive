# Djokovic–Bu Beijing second-round reel preflight

Production spec: `specs/reels/djokovic-bu-beijing-2026-r2.json`. Owner-selected fuller source: https://www.youtube.com/watch?v=U_XusSb_NV4 . Exact source SHA256: `8802c02443e2b6383eb798994b26c060a44f27cce59d78724467ea6aa7b3bf7e`; 95,263,475 bytes, 1920×1080, 50fps, 244.482902 seconds.

The match is October 2, 2026, Beijing ATP500 round 2. Djokovic won 4–6, 7–6(2), 6–2 in 172 minutes. Bu's game-point save shown at source193.32–210.22 occurred while Djokovic was serving at3–0, not after4–0 and not a break. The final-point backhand and complete celebration/handshake end before the TennisTV branded trailer at234.46. Official event reports708/709 and Chinese player interview are recorded in `_facts`.

Full-match stats are Bu then Djokovic. TNNS Match tab W/UE31/20 and40/30 are retained with raw transcript SHA. Second serve13/30=43% vs27/37=73% includes Bu's double fault; do not blend Tennis.com's13/29 variant. Native validators for W/UE evidence, source/crop, match footage, 13 source-bound original-commentary cues and production title/copy/tags pass. Original source foreground review uses ASR cross-checks and explicitly does not claim human listening.

18 segments /26 real native representative frames plus cover and corrected full-canvas stats have been visually reviewed. The card now avoids normal subtitle/topbar overlay. See preview-qc.md for scope; these frames do not certify final TTS alignment or transitions.

Local real Edge TTS failed before obtaining any speech audio because the speech endpoint was unreachable after two native retries. No measured duration is claimed. Production render will run the actual voice-over overrun and digital silence gates before encoding. Native branch render37103801290 uses push=false; all rendering and publication checks must pass before publication.

Global baseline CI on b96491d had five unrelated Yastremska failures plus the removed temporary source-export helper's missing timeout. These are not treated as this reel passing global CI, and no legacy exceptions are added. Exact-head full CI and final produced-film QC remain necessary for normal merge/push.
