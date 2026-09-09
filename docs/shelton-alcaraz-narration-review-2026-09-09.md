# Shelton–Alcaraz narration alignment repair — 2026-09-09

The published cut passed technical QC but failed editorial alignment. The prior audit claiming that adding “随后” resolved the mismatch was wrong.

Confirmed defects in the previous film:
- Film 10.61–17.67: first-set tiebreak still underway while narration announced the first set had ended.
- Film 31.21–34.67: third-set score 2–0 while narration announced both middle sets already won.
- Film 72.94–77.56: third-set footage under fourth-set result narration.
- Film 114.31–116.74: the first tiebreak point under match-point narration; true match-point footage starts at source 122.17.
- Full-match five-point aggregate was spoken before the final tiebreak finished.
- Copy source included its own dated headline; the publisher prepended another title, moving the first headline into the copyable body.

Repair uses official same-match Set 1/2/3/4 videos, each with its original native scoreboard, alongside the original YouTube cold open, fifth-set tiebreak, match point, handshake and celebration. All four added sources were downloaded and visually inspected. Source URLs and hashes, exact windows, narration and evidence are in the spec's _narration_alignment. Spoken references to previous sets are explicitly retrospective and start after the preceding footage has concluded. No current-set result is announced before the point finishes. Full-match statistics remain after the win. Edge speech was synthesized and measured in every voiced segment; all fit.

Scoreboard geometry masks for all four added windows were actually generated locally. Set 2 excludes the post-board US Open transition from detection. Set 4 ends after the winning point and before an unresolved overlay boundary; the next shot starts at 46 seconds after the board has withdrawn. No maximum-width fallback was introduced.

Future editorial review:
1. Record source, actual set, games/points, server and point outcome for each voiced shot.
2. Match spoken scope to shot scope; a report's true fact is not evidence of the pictured rally.
3. Current results must follow the visible point; past-set recaps must name the prior set clearly.
4. Distinguish first tiebreak point, set point and match point.
5. Review final ASS timing against rendered frames, not just spec text or contact-sheet labels.
6. Do not describe this manual editorial check as a general semantic guarantee from technical QC.

Copy generation now strips standalone dated column headlines before prepending the canonical title. Body paragraphs remain intact. Existing PushPlus receipt is retained; editing a stable video URL does not imply a new phone delivery.

## Delivered render and final inspection

- Run: https://github.com/robertyang87/tennislive/actions/runs/34338063258 — success.
- Film: 189.089 seconds; 104,978,943 bytes.
- Film SHA256: 6b028c3a1a72f1eb4fd77b30ed7899728fbb8f066288772aaa4a2e41cf7b515b.
- Spec SHA256: e59f6c257199e2f10cfb9616f796108d1dcf6ad8aeac4cd629a77878b8f609c9.
- ASS SHA256: 25d6fc5adbff3b3b23b6d0f1b8eb71c4f4ec790f77b6fb37934440ea020b8542.
- Downloaded the updated Release file and verified its exact hash and byte count against the landed QC attestation.
- Read the final ASS and inspected actual rendered frames at film 19, 43, 46, 67.5, 70, 89, 108.5, 122.5, 133, 135.5, 145.5, 178.5 seconds. Checked first-set 6–5 set point; second-set 5–1 receiving set point; third-set 5–3 serving set point; fourth-set 3–1 rally and post-set result; opening tiebreak point; silent 9–7 match point; post-point result, net exchange, and final full-canvas statistics.
- All five source hashes in the rendered scoreboard audit match the source files inspected locally.
- Final fourth-set narration removes redundant serve ownership, retaining the comeback stakes; measured duration 10.656 seconds within the 24.5-second shot.
- Public copy page was fetched after publication: the body starts directly with its first paragraph, with no repeated dated headline.
- Prior successful PushPlus receipt remains unchanged. This is an updated stable video resource, not evidence of a second WeChat delivery.

This is a source-timeline audit plus targeted inspection of the rendered film, not a claim of exhaustive automated semantic recognition.
