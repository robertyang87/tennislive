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
