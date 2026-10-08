# Actual final film — visual QC

Result: **PASS for the inspected visual scope. No visual release blocker found.**

Reviewed actual retrieved native render:
`/tmp/review-copy-0y0_sfkv/djokovic-bu-beijing-2026-r2.mp4`

- Native run: `37103801290`.
- Actual file probe: H.264, 1080 × 1440, 25 fps; AAC; 186.400 seconds.
- SHA-256 supplied and independently checked by the parent: `b62142669feb6220621e0663bc4c2f9128129193c0564f044639b5372272b192`.
- Render metadata: repository `output/2026-10-03/reel/djokovic-bu-beijing-2026-r2/render.json`.
- This review uses the final MP4, rather than the earlier segment previews.

## Inspection scope and evidence

Actually viewed all 10 contact sheets covering 186 decoded frames sampled at 1 frame/second across the whole film, plus the full-resolution keyframes listed in `samples.json`. Also viewed all seven transition contact sheets, each sampling offsets −0.16, −0.08, 0, +0.08, +0.16 and +0.32 seconds around a main transition. All artifacts are in this directory.

The inspected transitions are 1.20, 5.10, 12.90, 136.00, 148.00, 169.04 and 182.54 seconds. Their observed dissolves/fades have no unexplained black/white flash, stray frame or unrelated source end card in these samples. The dark green interval at the start of the brand outro is its deliberate animation background.

This is sampled visual inspection, including denser checks at the identified risk points, not a claim that every video frame was manually viewed. Audio was **not listened to** in this review. Original English ASR verification and full-stream decoding are separate checks performed by the parent/team.

## Findings

| Actual film interval | Observed visual result |
|---|---|
| 0.00–1.20 s, cover | Official same-event maroon-shirt Djokovic celebration photo is sharp; raised fist and face are clear. Hook uses “德约3盘逆转小布”. Final score and 2:52 duration are legible. No claim that the still captures this exact last point is introduced. |
| 1.20–5.10 s, cold open | Djokovic close-up with “31 and 0 now for Djokovic.” and its Chinese translation fits inside the canvas; the brief net shot follows. Transition from the still is coherent. |
| 5.10–12.90 s, first title card | “172分钟 才赢下的胜利” and “先丢一盘 再连扳两盘” are readable, along with the own-account credit. No text overflow. |
| 34.00–42.15 s, long bilingual quote | Long English sentence wraps to two lines above the Chinese line; all three lines fit within the picture. Neither side is clipped. The source score panel disappears when the source itself withdraws it. |
| 110.25–116.30 and 131.50–136.00 s, later bilingual quotes | “It's a lightning quick start from Novak Djokovic.” and “How has he won that point?” with Chinese translations are readable. Captions stay above the preserved score panel. |
| 136.00–148.00 s, full-canvas statistics | Full-frame card is visible without an ordinary match topbar or subtitle overlay. Left Bu: second-serve points won 43% (13/30); right Djokovic: 73% (27/37). Player identities, final score, other rows and labels remain readable. Earlier preview obstruction is absent in the actual film. |
| 148.00–153.34 s, final point | Statistics dissolve into Djokovic's service motion. The serve, subsequent baseline two-handed backhand, Bu's chase and Djokovic's walk toward the net are present. “反手打向空当” describes the visible backhand. Score panel shows Djokovic 5–2, 40–15 before completion. Point payoff is not cut off. |
| 153.34–169.04 s, celebration and handshake | Team reaction, Djokovic close-up/fist celebration, both players meeting at the net and the handshake are present in order. Both heads and the net contact are visible in the handshake keyframe. The Tennis TV source QR/branded tail is absent. |
| 169.04–182.54 s, closing title card | “胜负之外 每球必争” and “德约的坚持 小布的挑战” are clear. Narration captions and the audience question “你最想为哪一分鼓掌？” are readable. The final caption finishes before the card ends. |
| 182.54–186.40 s, own-brand outro | Own “网球时差” animation fills the canvas with no match topbar. Final frame at 186.32 s contains the complete logo, “时差归我，好球归你” and @网球时差 · TENNISJETLAG. The brand payoff is present before the file ends. |

The fixed centered 3:4 crop is consistent throughout. In some wide rallies, a player or ball temporarily reaches/exits a lateral crop edge; this is the expected tradeoff of the locked crop policy, not a new change or a discovered implementation failure. No crop revision is requested.

## Artifacts

- `wall-01.jpg` … `wall-10.jpg`: complete film scan.
- `samples.json` and named full-resolution keyframe JPEGs: risk-point evidence.
- `transition-samples.json` and `transition-wall-1.jpg` … `transition-wall-7.jpg`: dense main-transition evidence.

Repository/specification files were not modified by this review.
