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
