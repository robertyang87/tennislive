---
name: vibetennis-production
description: Produce, QC and publish a "vibetennis" episode — 网球时差's 16:9 Vibe知识-style cinematic 3D science explainer about a tennis perception phenomenon (Three.js holographic scenes, content-anchored captions, synced SFX, ~3 min). Use for new vibetennis episodes, covers, QC, or WeChat (PushPlus) delivery.
---

# vibetennis production

完整流程、目录和 TODO 见 [docs/vibetennis.md](../../docs/vibetennis.md)；栏目定位见
[docs/columns.md](../../docs/columns.md) 的「vibetennis」。这里只列开工清单。

## 栏目使命（账号所有者 2026-10-30，每一集都按它验收）

原话：「作为科普视频，内容一定要**精确且详实**，同时**深入浅出**让普通人都能看得懂，同时用**动画特效**呈现效果抓住观众注意力，能**持续看下去**，并能**引爆共鸣和二次传播**，这是这个 vibetennis 的使命和要求」。

六个要求，每个都落成写 spec、渲染前能逐条检查的做法：

| 要求 | 怎么做到 | 写 spec / 渲之前查什么 |
|---|---|---|
| **精确** | 每个上屏数字都读过原文；搜索摘要和二手报道不算核过。数字有冲突、没有一手来源的，就写模糊（「十来台」「一个数量级」）或者不写。**规则、制度、配置类的事实要核到今年**：一篇报道只说明它发表那一年（来路：BBC 2025「温网没有挑战、不放回放」，到温网 2026 已加视频回看——所有者 2026-10-30 问出来的） | `editorial._claims` 每个数字一行：出处、读没读原文；没读的那一行不许上屏 |
| **详实** | 机制要讲到「为什么」那一层，不停在「是什么」；有反证、有局限的必须摆出来（比如电子司线的「平均误差≠每一球」） | `beats` 里至少有一段讲局限或反证 |
| **深入浅出** | 解释一定要**精准清楚**（所有者同日补：「可以不用生活类比，但解释一定要精准清楚」）：术语出现的那一屏当场用画面解释；机制的每一步因果都要交代，不跳步；宁可多一屏，不为好懂把机制简化到失真；字幕一句只讲一件事。类比不强求，用就得在物理上站得住 | 拿字幕念给不看网球的人听：要反问的那句就重写；再问一句：懂行的人看了会不会说「不是这样的」 |
| **动画特效抓注意力** | 开场 5 秒内出一个反直觉的画面或问题；3D 演示的是机制本身，不是装饰 | 镜头提纲里每一段都写清「这一段的视觉事件是什么」，空着的段落删掉或合并 |
| **持续看下去** | 每一段结尾留一个钩子（「那它准在哪？」「可它也出过事」），把观众推进下一段；答案放在中段，不全压到片尾 | 提纲逐段看：这一段末尾，观众有没有理由继续看 |
| **共鸣和二次传播** | 题目必须是观众今天看球还会碰到的事；片中要有一句能单独截出去转发的话或数字；片尾问观众自己的经历 | 选题过「今天的比赛里还在发生吗」；`xhs.txt` 末尾问句问的是观众的经历 |

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
