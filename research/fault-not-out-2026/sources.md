# fault-not-out-2026 源片检索记录

2026-10-15。沙箱连不上 YouTube，检索放在临时工作流（已删）里用 `yt-dlp ytsearch` 跑，查询词见 `queries.txt`（第二轮覆盖了第一轮）。
入选的全部是官方频道，经 `download-video.yml` 存进 Release `source-<id>`，两档英文转写在 `data/source_asr/<id>/`。
电子司线、司线的单词喊声两档整片转写收不到，另用 `asr_probe.py`（2 秒小窗、medium.en、带提示词）补探，窗口见 `probe_windows.txt`；短窗口补转写在 `asr_clips/`。

| 键 | 视频 | 频道 | 用途 |
|---|---|---|---|
| bu | PYnZo-nL6Hk「Bublik Foot Fault Confusion in Beijing」 | Tennis TV | 中点延长线脚误、布勃利克原话 |
| ao | VwN4Bm3liL0「HILARIOUS Moment Line System Malfunctions! / AO 2025」 | Australian Open | 冷开场：电子司线连喊脚误 |
| ky | o1Ad7ZL7AuU「Nick Kyrgios and umpire James Keothavong have comical exchange / Wimbledon 2018」 | Wimbledon | 司线判脚误、击球后才能喊 |
| md | FhSymjai5hM「Foot Fault: Yes Or No? Controversy In Medvedev vs Zverev / Nitto ATP Finals 2021」 | Tennis TV | 二发脚误、视频回放、梅德韦杰夫原话 |
| rb | I_vN3qoxO8Q「Rublev's double fault his breaking point / AO 2018」 | Australian Open | 双误 |
| wb | GeMppP-gRKc 大坂直美 vs 穆霍娃加长集锦，温网 2026 | Wimbledon | 讲解底片（与 let-not-net-2026 同一条，取的是两档转写都无人声的窗口） |

下了没用：VDy_CN9nNtY（迪拜 2023 德约对梅德韦杰夫中点脚误，和布勃利克那段重复）；LRRPRo71sWY、LHsOkBl1wRE（温网 2019 奥斯塔彭科发球砸中搭档／对手，远景里人太小、居中 3:4 裁切会把发球方裁出画外）；gOm92AFduf4（温网 2025 盘点上的砸人，是回合不是发球）；S5IgXi2HASE（佩古拉 2024 美网 let 后双误，要靠解说才讲得清）；oGq7ylNr9cA、owzOf0vgX5w（只有 720p）；-ymjJrEkWII（集锦里找不到挥空发球）。
2009 美网小威脚误、1999 澳网库尔尼科娃：只有非官方转载，用字卡 + 旁白。

## 封面

Commons 司线类 40 余张多为站立盯线、没有判罚动作；AP 经 16 个会员站 WordPress 媒体库按说明全文搜（`cover_search.py` 最后一版），判罚手势的只有两张：2011 澳网司线伸臂（2000×1106，说明写的是判出界）和 2025 法网第一轮司线坐着伸臂判罚（3200×2133，入选，`assets/reel/faultout/fault-cover-linejudge.jpg`）。
