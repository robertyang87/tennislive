# 自动字幕的空档：rybakina-fernandez-ningbo-2026-f-speech

阈值 2 秒；空档 **2** 处。

第一份是 ASR（medium），第二份 ASR 是 `small`（多语模型）。**它什么都没听出来，不等于这几秒没人说话**——ASR 空词不能证明静音：可能没人说话、不是英语或该语言识别失败，需结合语言窗、VAD 和原声核对。

## 29.0–32.3 秒（片内，3.3 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=34）

- 键：`34.6-37.9`
- 第二份 ASR（small）：`Then I would like to say`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：字幕时间轴自动销账：VAD 测到 0.554s 人声，第二份 ASR（small）听到「Then I would like to say」——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 85.3–89.2 秒（片内，3.9 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=90）

- 键：`90.9-94.8`
- 第二份 ASR（small）：`Then`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：裁定：掌声＋场馆音乐床空档，无窗内台词。依据：当前网格 VAD 人声 0.000s；small/medium/medium.en 三份独立 ASR 在窗内均无词；AudioSet AST 本窗 Music 0.546、Crowd 0.135、Speech 0.031（讲话对照窗 Speech 0.897）。第二 ASR 唯一的「Then」是她 94.76 秒续讲首词「And」的边界误听（多语 medium 同处把续讲听成「然后当然」可互证），非窗内漏词。本空档同时按保守声音事件标注保留原声并烧成对 cue（见 caption_gap_annotations 与其证据文件）。

