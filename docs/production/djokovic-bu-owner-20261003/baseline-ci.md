# Djokovic–Bu preflight and existing CI baseline

Read-only inspection, 2026-10-03. No old episode, test, workflow, or GitHub ref was modified.

## New Djokovic–Bu episode

The inspected 18-segment spec passed native production preflight, spec validation, Winners/UE, fixed-center crop, match-footage style, and source-bound foreground-audio gates. Native taste dry-run passed for this episode. The full taste command ran 17 taste CI tests and classified failures in other episodes separately; its exit code is not proof of a green repository CI.

Inspected spec SHA-256: c16e2ec6faddf82f8d5d4f688f00a71efa2910a8236b5e567b563852a3de63de.
Source SHA-256: 8802c02443e2b6383eb798994b26c060a44f27cce59d78724467ea6aa7b3bf7e.
Audio plan: e5b8ce5838af540484c0eb61764fe61ef20efcf256f5ed331fe2b2a45b2b307e.
Source: U_XusSb_NV4, 1920×1080, actual media50fps, 244.482902 seconds; native probe normalizes its inspection cadence to25fps.
The full-canvas statistics card was included in the inspected spec.

Warnings are not measured narration-duration attestations: some long clips have substantial time after estimated narration; the native render must validate actual synthesized speech. I did not run an independent actual-TTS narration check or listen to source audio. Evidence method remains honest ASR cross-checking. Native render run 37103801290 was started by root and is outside these completed preflight results.

Saved native taste output: preflight-native-taste.json.

## Existing five Yastremska baseline defects

Immutable latest-main inspection: e500357a6030c5520d49d3373abee6878d6d3e46.
All five offending fields/probe conditions remained present there.

Actual completed CI evidence:
https://github.com/robertyang87/tennislive/actions/runs/37102029332
Job:
https://github.com/robertyang87/tennislive/actions/runs/37102029332/job/111143341365
Commit b96491d378ebacf29649630fe025db4aec0ee13a.
Result: 6 failed, 5369 passed, 192 skipped, 54 warnings, 357.40 seconds.
Five failures concern unchanged Yastremska stock content. The sixth concerns the new source-export workflow launch job's missing timeout, separately owned by root. Earlier run 37101649418 was cancelled and is not a complete failure report.

| Exact test | Actual Yastremska condition | Smallest legitimate repair; publication implication |
|---|---|---|
| tests/test_match_reel.py::test_源片自己烧了记分条时字幕要让开 | subtitle_top=860 lacks a concrete _subtitle_top_why collision assessment. | Inspect the exact published film and actual source geometry before writing an honest assessment. A documentation-only fix can use native reattestation only when rendered inputs remain byte-identical. No independent old-film visual pass is asserted here. |
| tests/test_match_reel.py::test_真字段表要盖住每条spec里出现过的字段 | Unsupported root scoreboard_profile=wta_left is absent from the real-field registry and has no runtime consumer. | Removing the unused field changes the bound native render-input projection; native rerender is required under current binding rules. Merely registering a no-op field is not a genuine implementation fix. |
| tests/test_reel_editorial.py::test_钩子不许复述赛果条和顶栏印着的东西 | Cover/editorial hook “首盘救下2个盘点\\n月亮姐第二轮告负” repeats the topbar's 第二轮. | Changing only 第二轮 to 两盘 would remove the round echo while retaining the supported event. Both mirrored hooks must agree. This changes actual rendered cover text and necessarily requires a new native render and exact-film QC. |
| tests/test_reel_editorial.py::test_赛场之上要么有狠数据要么说清为什么没有 | _hit_data and _no_hit_data_why both absent despite existing genuine TNNS figures. | Add an evidence-backed _hit_data annotation, using already sourced W47/6, UE24/11 and breaks5/10 vs1/1. Do not claim data are unavailable. Annotation-only reattestation is permissible only if projection is unchanged. |
| tests/test_probe_board.py::test_标定框和全库spec用的框对得上 | Spec scorebox [90,870,516,984] does not match actual stored custom scan [72,872,481,983] or standard scan [90,870,550,980] within native tolerance. | Rescan the genuine identical source at the existing exact box and preserve real frames/results. A probe-only repair can leave rendered inputs unchanged. If actual geometry instead requires a new crop, that would require rerender. Do not fabricate scan metadata or widen tolerances. |

The source/probe URL is https://www.youtube.com/watch?v=12BOGT88OnQ.
The true statistics source is TNNS Match 75051478, with existing raw evidence at docs/production/chwalinska-owner-20261002/tnns-stats.txt.
The probe actually scanned 1,550 frames at 5 fps. The genuine custom scan differs by 18 px at x0; the standard scan differs by 4 px at y1. Native tolerance is x0±4 and y0/y1±2; x1 is ignored. Existing published scoreboard QC is not a substitute for the required matching custom probe.

## Published episode boundary

Yastremska was already sent at 2026-10-02T08:21:26Z, publish run 36983382818.
Receipt: https://www.pushplus.plus/shortMessage/efcda97681d3426f98709ce8f82b6585
Native render: https://github.com/robertyang87/tennislive/actions/runs/36982776082
Published film: https://github.com/robertyang87/tennislive/releases/download/reel-yastremska-chwalinska/yastremska-chwalinska.mp4
Existing native metadata reports SHA-256 557784652b0aea2adae9daeead955444ec93ef00cbb325e8a700da6a58f05ce3, 89,750,864 bytes, 180.52 seconds. Those old film bytes were not independently downloaded and revalidated in this inspection.

Its actual bound render_inputs.json contains both scoreboard_profile=wta_left and the existing hook. Consequently, all five tests cannot legitimately become green while preserving all old rendering inputs: the hook defect alone requires an old episode rerender. No metadata-only reattestation may claim those rendered inputs stayed unchanged after that fix.

Do not amend the historical freeze, add a legacy exception, weaken a test, or modify the old published episode merely to pass this new video's CI. Current scope is a finished new movie plus exact-file QC; the existing published-episode repair is a separate production decision. No old repair was performed.


Latest pre-artifact-documentation CI: commit5026b399ce776daef47de8b93173d71eb078c448, run37104055227, job111149090626. Actual result6 failed/5369 passed/192 skipped in453.06 seconds. Five failures remain the unchanged published Yastremska conditions listed above. The sixth is a distinct JPEG trailer false positive on the new official Djokovic photograph, which already contains a real EOI marker and fully decodes. The bounded validator correction retains the original asset bytes and requires full decode whenever trailing data are present; negative cases keep rejecting truncated JPEGs. This is not an exception for the five old-episode failures.
