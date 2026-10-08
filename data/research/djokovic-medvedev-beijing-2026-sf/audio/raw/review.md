# Audio review — LgRD3TLoxr0

Method: independent faster-whisper small.en + medium.en ASR, cross-checked with source captions. No human-listening claim.

Source SHA-256: 80179ed4439aecc24c30cf410a2a237c93eee11299d38537f1d0289786ed24d5

One unstable source utterance at 130.64–133.94 remains unresolved and is outside all selected windows.

24.72–26.64  Oh, he's found that line again.
噢，他又打中了这条边线。

27.48–31.04  Couple of outrageous forehands up the line from Daniil Medvedev.
梅德韦杰夫连续打出两记惊人的正手直线。

42.18–45.26  This time the pressure does tell.
这一次，压力终于起了作用。

45.38–46.14  It's been coming.
此前就已经有这个苗头了。

89.40–92.70  Oh well, that could have been pretty nasty.
噢，刚才那一下可能会相当危险。

92.74–94.90  But what a response from Novak Djokovic.
但诺瓦克·德约科维奇的回应太精彩了。

123.12–125.14  It's just brilliant from Medvedev.
梅德韦杰夫这一球太精彩了。

125.26–126.77  Just bided his time there.
他一直耐心等待出手机会。

161.98–165.50  A ridiculously physical opening set of tennis.
首盘的体能消耗大得惊人。

191.26–193.90  Oh, just out of his reach.
噢，刚好超出了他的触球范围。

194.80–198.80  And Djokovic continues to play the big point so well today.
而德约科维奇今天在关键分上继续打得非常出色。

218.82–221.10  That's brilliant from both again.
两人又共同打出了一段精彩对抗。

228.66–232.92  One of the few players that would actually prefer that drive volley on his backhand wing.
他是少数更喜欢用反手打这种抽击截击的球员之一。

236.26–244.14  Yeah! Yeah! Yeah! Yeah! Yeah! Yeah!
呀！呀！呀！呀！呀！呀！

256.38–258.02  That's just amazing depth.
这球的落点深度真是惊人。

259.24–261.12  The shot beforehand from Djokovic.
说的是德约科维奇前一拍的击球。

267.18–270.78  But this time he does find a way through.
但这一次，他终于找到了突破口。

309.36–311.50  Oh, he just went straight back at him.
噢，他直接朝对手打了回去。

311.62–314.14  Djokovic collapses to the ground in a heap.
德约科维奇一下倒在了地上。

335.16–338.02  Oh, it's magnificent from Medvedev.
噢，梅德韦杰夫这一球太精彩了。

343.90–345.44  Can you believe it?
你能相信吗？

345.54–348.62  Just a flurry of errors from Medvedev.
梅德韦杰夫突然连续出现失误。

352.24–355.26  That's a brilliant combination from Djokovic.
德约科维奇这一组击球组合太精彩了。

356.20–357.84  Well, can you believe it?
这结局，你能相信吗？

360.60–366.06  After the most extraordinary level in this match, it has ended on a Medvedev default.
这场比赛打出了极其非凡的水准，却以梅德韦杰夫被判失格结束。

369.90–379.90  Well, no real protest from Daniil Medvedev, but it's hard to argue with the decision from Mohamed Lahyani and the the ATP supervisor there.
梅德韦杰夫并没有真正提出抗议；很难反驳拉希亚尼和现场ATP监督作出的判罚。

## Important method limits

Extracted full AV1 source to signed 16-bit 16kHz mono WAV using ffmpeg.
faster-whisper small.en full-source VAD and no-VAD local windows; medium.en independent no-VAD local windows; separate medium.en VAD checks of narration and ASR noise gaps. Raw word timestamps and probabilities retained.
Source captions are automatic, so player and chair name aliases corrected deterministically; non-name wording follows source captions except the first 24-second line, independently recovered clearly by medium.en.
Word timing has limited resolution; sentence bounds include conservative padding and reflect source-absolute seconds. Some first-word ASR bounds start at a local-window edge and are rejected in favor of aligned supporting runs.
234–245 contains nonlexical court vocalizations. Source captions render three as yeah; both independent no-VAD models render six Yeah tokens. Their six lexical shout candidates are retained conservatively in one contiguous bilingual cue, covering the union of medium and small time extents. Ahh-only candidates are classified as nonlexical grunts. The note does not claim exact acoustic utterance counting by a listener.
No-VAD small generates repeated noise phrases in non-commentary gaps. At 149–161, 180–190, 339.22–343.8 and 273–309, source captions are empty and medium VAD returns zero detected speech; these noise-only hypotheses are explicitly not adopted as original words. At 76.58–87, medium VAD returns only Ugh, a nonlexical exertion sound.
46.28–76.58 planned Chinese narration window: both medium VAD subwindows have duration_after_vad=0, and full small VAD/source captions contain no foreground English. Low-confidence no-VAD Oh my God hypotheses are rejected; raw evidence is retained.
