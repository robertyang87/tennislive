---
name: vibetennis-production
description: Produce, QC and publish a "vibetennis" episode — 网球时差's 16:9 Vibe知识-style cinematic 3D science explainer about a tennis perception phenomenon (Three.js holographic scenes, content-anchored captions, synced SFX, ~3 min). Use for new vibetennis episodes, covers, QC, or WeChat (PushPlus) delivery.
---

# vibetennis production

完整流程、目录和 TODO 见 [docs/vibetennis.md](../../docs/vibetennis.md)；栏目定位见
[docs/columns.md](../../docs/columns.md) 的「vibetennis」。这里只列开工清单。

## 所有者口味（2026-10-30，不要用赛场之上的规矩套）

- 16:9 横屏 1920×1080；宏大、有质感、科技/科幻感的 3D 全息场景，不要扁平 2D
- 字幕锚定在被讲的内容旁边（带引线），不压在底部；左上角「网球时差」＋官方图标，片中不出现「VIBE 知识」
- 音效跟画面对齐；没有旁白；时长随内容，约 3 分钟
- 理论要调研透、每个数有出处；镜头编排先写清楚再渲
- 质量标杆：许先森Ai 抖音片 https://v.douyin.com/ZAuwSjlTKhM/

## 开工清单

1. 选题过「妈妈、高中生、上班族都会说『对』」测试；一个现象，一个反直觉转折，一条有出处的证据链
2. 写 `specs/vibetennis/<slug>.json`（`column`/`cover.eyebrow` = `vibetennis`，`film.canvas` = [1920,1080]，
   `editorial.sources` 不能空，`push.auto` = true）和 `.xhs.txt`（第一行完整问题，正文数字与片子一致，末尾问句，tag ≤5）
3. 复制上一集 `tools/vibetennis/episodes/<slug>/` 改场景与镜头表；本地 3D 分段渲 → `overlay.py` → `sfx.py` → `assemble.sh`
4. `r3d/still_hd.js` 渲一张竖版原生帧当封面素材；`tools/vibetennis/cover.py` 出**单独一张** 2160×2880 海报（封面**不进视频**，所有者 2026-10-30）
5. `finalize.py`（母片原样拷入，不重编码）→ `qc.py`（全绿才有凭证）→ 看 `qc_contact.jpg`，最好整片看一遍
6. `release.py`（Release ＋ copy.html）→ `push.py --dry-run` 看标题正文 → 提交（不提交 mp4）→ PR
7. 合并即推（CLAUDE.md「片子做完就合并、就推微信」）；推完用 `tools/push_link.py --slug <slug>` 取消息网页链接发给所有者
