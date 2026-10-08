# ATP native scoreboard repair, 2026-10-04

Official source cjaHThpISKk SHA256 `2a62a85fb499f153e97fa3074294eb1be476a818aa480291b65b43a3e94484e2`, source box `[98,920,519,1029]`.

Old detector incorrectly counted the spectator dark clothing as board background at 280.5s and 282.5s, reached the entire scan band, and used the spec hint x519. The true native edges are approximately x486 with AD and x436 without points. At 108.5s the native board still has two player names, first-set result 6:4 and AD; the blue active-set cell is withdrawn, so the old blue-required presence check returned None.

The fix requires both two rows of white player-name text and the full-height chromatic navy background at the expected board origin. When this concrete signature holds, board-color scanning also requires green-minus-red >4 and blue-minus-red >8. Dark spectator clothing has green≈red and ends the scan; the native navy and translucent points cell remain. That same verified two-row signature recognizes the set-end board when the blue cell is absent. Other graphics retain the original blue-cell anchor, beyond-hint behavior, width adaptation, yellow-tag shape and gates. No broad crop fallback or gate exception was added.

Six lossless source-crop fixtures are stored in tests/fixtures/atp_scoreboard/beijing2026 with their SHA provenance. Original code: 3 failed, 4 passed. Repaired code and the existing ATP/width-adaptation/geometry-QC/RNA/ITF/WTA tests: 40 passed. Original failure output is /workspace/djokovic-cja-research/atp-before-tests.txt.

Actual source scan+stabilize+FFV1 write_mask was run for 0.2s / five frames at each of six source times. The fixed-atp-mask-samples.json file records each mask SHA and per-frame edge. Wide and ordinary close shots remain x393 / x342–343; dark AD close shot becomes x486 (+2px anti-alias padding), no-points close shot x436 (+2px). Set-end AD mask now exists and narrows with the actual points-cell retract animation (x385→374 at the fps25 sample times). Independent production QC should inspect the actual final-film paste after integration.

Additional actual-source transition scan at 5fps: 99–112s board present 65/65 frames including the no-blue set-end animation; 274–292s present 50/90 frames with tight right edges x432–487 and absent from284s; 309–319s present0/50. These are source detector checks, not final-film approval. See transitions-scan.json.
