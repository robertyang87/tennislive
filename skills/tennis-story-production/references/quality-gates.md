# Quality gates

Run them in this order. Each one is cheaper than the next, and the point is to fail on the cheap one.

| Gate | Cost | Catches |
|---|---|---|
| `--dry-run` | 0.2 s | Spec shape, window arithmetic, source overrun, licence four-set, hook width, narration that cannot fit |
| `preview_segments_local.py` | 3 s | Picture ↔ line mismatch: the person named is not the person shown, the scoreboard disagrees with the sentence, the window opens on the wrong shot |
| `--check-narration` | ~30 s | Real TTS length per segment, dead air, tokenisation that changes a word's reading |
| Full test suite | ~2 min | Every accumulated wording rule, name table, round naming, and structural contract |
| Render | 5–15 min | Everything that only exists in the product |

The preview gate runs **twice**: once while choosing windows (is this shot any good), once after the copy is final (does this sentence's subject appear in this frame). They catch different things, and the second pass is the one that finds a line sitting on the opponent.

## After the render

Pull the film back and inspect the product, not the log.

- Frames around every window edge — an end card, a focus pull, or a cross-dissolve one frame past the boundary.
- Levels segment by segment. A digitally silent stretch and a correctly quiet one look identical in a waveform thumbnail and identical in a green run.
- Subtitles: on screen, inside the safe area, and matching what is spoken.
- Music: audible under the live sound, gone by the end card, and not competing with the subject's own voice in quote segments.

## Blocking versus retryable

Retryable: network, credentials, a runner that died before any work started.

Blocking, and never overridden: a fabricated or single-sourced absolute claim, a line whose subject is not the person on screen, a screenshot that is not a real page, footage from an unofficial channel, a missing licence field, music above the measured floor, and any deterministic gate that failed.

Missing evidence is a reason to wait. It is never a reason to write around the gap.
