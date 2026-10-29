# 《Walkover》walkover-story-2026 自制动画源存档记录

五段动画均在本地以 PIL/numpy 逐帧代码绘制（无 AI 视频、无素材图），
渲染脚本与自检报告在制作目录 `anim/`（render_horse.py / render_notation.py /
render_three.py、anim-A-report.md / anim-B-report.md）。
本地直传 uploads.github.com 被凭据 401 挡住，照 import-sun-cvetkovic 先例
走 runner 工作流 `import-walkover-anim-sources.yml` 建 Release 存档；
本目录 mp4 只是暂存，存档完成后另行提交移除，Release 为唯一正本。

归整口径：存档版视频流与本地生产版 `*-final.mp4` **逐字节一致**
（ffmpeg `-map 0:v -c copy -f hash` 双向核验），只补一条静音 AAC 轨
（anullsrc 48kHz）——source-asr 的 PyAV 解码需要音轨存在；动画无任何
人声，双档转写应为空。规格均为 1080×1440 / 30fps。

| 本地生产版 | 存档 id（tag `source-<id>`） | 时长 | 存档文件 sha256 |
|---|---|---|---|
| horse-final.mp4（赛马起源） | wo26horse01 | 11.0s | 62ed26135d4fc883a0d9b89adcc648ab8af55e9cfb915f04669b9330f31e4c88 |
| notation-final.mp4（签表 W/O＋一分之线＋连胜断片） | wo26notat01 | 17.0s | a901c02b5fc4e6f60c15f29316f4fed4c92480ddd3c2bb262a3e3a99d6403d33 |
| ledger-final.mp4（积分账本） | wo26ledger1 | 11.0s | fb92509ab9ffddbf70e5847151296e31796846e9fbd2d0d9621aea5532fe42ef |
| timeline-final.mp4（获利者时间轴） | wo26timeln1 | 18.0s | 39b595b1050c50f23a7f977f4f480fdca326b78a5edd0802504a9bcba78c3335 |
| sun-process-final.mp4（孙心然进程，备用文案版） | wo26sunpr01 | 13.0s | 96b11f63f3a3b711e7efe32c6d471d7efcbb75ecbd65f58896cdb5e85ac5f3c5 |

存档直链形如：
`https://github.com/robertyang87/tennislive/releases/download/source-wo26horse01/wo26horse01.mp4`

## 延展版（2026-10-30 第二轮）

赛马段旁白在 narration dry-run 的离线装填估算为 34.78s，超过原 11.0s
动画 speed 0.4 拟合上限（27.5s），本地延展重渲为 34.0s（horse-ext.mp4：
加拍「独自领奖」＋排字/点阵停留，走马步态与原版逐帧同构；自检报告
anim-ext-report.md）。照同一路线存档：

| 本地延展版 | 存档 id（tag `source-<id>`） | 时长 | 存档文件 sha256 |
|---|---|---|---|
| horse-ext.mp4（赛马起源延展版） | wo26horse02 | 34.0s | 8009e6f72391f39879a892697ff086f46bd37d16c93cac4c27bd6f7d0809b264 |

视频流与本地 horse-ext.mp4 逐字节一致（流哈希 0a84dd4a26d255f05c4ec282f69760906d30b28310681a49f6df470b6be43f4e 双向核验），只补静音 AAC 轨。存档工作流 import-walkover-anim-ext（run 40931196836，success）。

**时间轴延展版暂缓**：timeline-ext1/2/3（36/36/40s）已在本地生产并自检，
但其案例分组按年份（穆雷+佩内塔／德约2014+格拉诺列斯／克耶高斯+德约2024+收束），
与 spec seg15 旁白的叙事顺序（同站对照→德约2024→克耶高斯→格拉诺列斯→佩内塔→
费德勒反转→收束）不一致，且无费德勒反转段画面；与本文件上方 red_items
原定分组（同站对照／德约2024／克耶高斯＋格拉诺列斯＋佩内塔／费德勒反转＋结论）
亦不一致。旁白为所有者定稿逐字不可重排，故三段暂不存档、不换源，
等主线/所有者裁定（按叙事顺序重渲，或批准旁白重排）。

## 时间轴叙事版（2026-10-30 第三轮）

主线裁定：旁白逐字不改，动画按旁白叙事顺序重渲。本地复用六例场景代码
重组＋新写费德勒戴维斯杯反转场景，产 timeline-a/b/c.mp4（38/41/41s，
两轮密帧自检，报告 anim-tlm-report.md）：a＝引子＋迈阿密同站对照
（句0–3，221 字，估长 ≈36.2s）；b＝德约 2024＋克耶高斯＋格拉诺列斯＋
佩内塔（句4–9，238 字，≈39.0s）；c＝费德勒反转＋收束（句10–15，
238 字，≈38.9s）。照同一路线存档（工作流 import-walkover-tlm-sources，
run 40935837484，success）：

| 本地叙事版 | 存档 id（tag `source-<id>`） | 时长 | 存档文件 sha256 |
|---|---|---|---|
| timeline-a.mp4（同站对照） | wo26tmlna01 | 38.0s | 0a3e5e6e024acfe85187fb1b3fb76ef87b6f1e999ae37412f9449e56109f0486 |
| timeline-b.mp4（德约2024＋克耶高斯＋格拉诺列斯＋佩内塔） | wo26tmlnb01 | 41.0s | c627e1d06642be779cc47ce8a648de71947239387d08780003ca2bc90602c49f |
| timeline-c.mp4（费德勒反转＋收束） | wo26tmlnc01 | 41.0s | 3efb6fc4e4cf3169ac1aee2ad6afabd638a0f1c155904dff87b91f83387af256 |

视频流与本地 timeline-a/b/c.mp4 逐字节一致（流哈希双向核验：a 3f5a3b3e…
／b c5519976…／c 595f64af…），只补静音 AAC 轨。年份分组的
timeline-ext1/2/3 就此弃用（本地保留留痕，不存档）；上节「暂缓」结论
由本节 supersede。spec seg15 据此拆为三段换源（旁白逐字未改、仅按
句组连续切分，拼接与原文 diff 逐字一致），speed 拟合 0.99/1.0/1.0。

## 动画 v2 原速版（2026-10-30 第四轮）

render run 40943446442 死在 `reel_source_audio_policy`（2026-10-13 新规：
正常制作不调整原声，任何段 speed≠1 即红）。本片七段动画原靠 speed
拟合旁白（sun 0.64／led 0.43／not ≈0.59／tlb 0.93／hor 0.95／tla·tlc 0.99）。
处置不动旁白与事实：六段按旁白真 TTS 实测时长（run 40939316191）以
1.0 原速重产——拉开拍点/加密度，不慢放、不冻结凑时长，数据逐项与 v1
一致，各段密帧自检报告在制作目录 anim/anim-v2-*-report.md；tla 旁白
35.14s＜源 38.0s，只摘 speed 不换源。照同一路线存档（工作流
import-walkover-v2-sources，run 40948524018，success）：

| 本地 v2 | 存档 id（tag `source-<id>`） | 时长 | 旁白实测 | 存档文件 sha256 |
|---|---|---|---|---|
| sun-process-v2.mp4（孙心然进程） | wo26sunpr02 | 21.5s | 19.49s | 002451b9591171e29b78e895e025709349c44e5f4d5bdac238d361868d0b86d8 |
| horse-v2.mp4（赛马起源） | wo26horse03 | 37.0s | 34.92s | 4d5270f4e32e43b7b2108ff6c7f9325e149f58685aebf7e5438edeede8a5bcb4 |
| notation-v2.mp4（记号/一分之线/连胜断片） | wo26notat02 | 29.0s | 26.95s | d997e918e7b59dcd58938884cc9102e41d91f3dcce0334c6b13b20b98f18282d |
| ledger-v2.mp4（积分账本） | wo26ledger2 | 27.0s | 24.94s | eee4327350245d41ed7d025fab2d4abfd19997d8dcb7f3cc0bc57c8d92446aa2 |
| timeline-b-v2.mp4（时间轴 b） | wo26tmlnb02 | 45.5s | 43.25s | 4b1cb51298f138d17b3f7baa666069b364d7a2c9f6cdd960e4a73b0a024f13a0 |
| timeline-c-v2.mp4（时间轴 c） | wo26tmlnc02 | 43.5s | 41.21s | 1fd27d0b28eddd42261659b77c96b8e41562fbd06588179903a333d1f47236f7 |

视频流与本地 v2 逐字节一致（流哈希双向核验），只补静音 AAC 轨。
spec 同轮换源＋摘除全部 speed（见 spec `_geometry_why` 追记）。
