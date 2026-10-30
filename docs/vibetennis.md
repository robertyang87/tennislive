# vibetennis 栏目：生产、质检与推送

> 栏目的定位、承诺和为什么要开见 [columns.md「vibetennis」](columns.md)。这份讲**怎么做**。

## 账号所有者对这一栏的口味（2026-10-30，会话原话整理）

和另外三栏**不一样**，别拿赛场之上的规矩套：

| 项 | vibetennis | 另外三栏 |
|---|---|---|
| 画幅 | **16:9 横屏 1920×1080**（「不一定要做竖屏的，做横屏 16:9 的也可以」） | 3:4 竖屏 1080×1440 |
| 视觉 | **宏大、有质感、科技/科幻感**的 3D 全息场景（「画面恢宏，然后又有质感，同时又有这种科技范儿或者是这种科幻的感觉」）；v1 的 2D 扁平版被否掉了（「效果很差呀」） | 官方比赛画面 |
| 字幕 | **跟着内容走**，锚在被讲的东西旁边、带引线（「它的字幕其实不是在最底下的，只是说根据它的内容显示它的文字」） | 底部字幕 |
| 声音 | 音乐 ＋ **跟画面对齐的音效**（「视频里有一些声效也要配合上」）；没有旁白 | 旁白 ＋ 现场声 |
| 时长 | **随内容，约 3 分钟**（「时长不用固定两分钟 40 秒……控制在 3 分钟左右是比较合适的」） | 按栏目 |
| 理论 | 经典研究撑腰，数字要有出处；理论和镜头编排都要先调研清楚 | —— |
| 品牌 | 左上角「网球时差」＋官方图标（`assets/logo/brand/account/icon-transparent-1024.png`），字号与右上角章节角标对齐；**片子里不出现「VIBE 知识」** | 同 |
| 标杆 | 许先森Ai 的抖音片 https://v.douyin.com/ZAuwSjlTKhM/ | —— |

选题沿用 Vibe 知识的爆款公式：人人有过的感受 → 反直觉的转折 → 有出处的硬证据 → 情绪上的和解。

## 目录

```
specs/vibetennis/<slug>.json          spec（栏目、画幅、封面、推送、编辑判断、出处）
specs/vibetennis/<slug>.xhs.txt       发布文案：第一行标题主题，正文，末行 tag（≤5）
assets/vibetennis/<slug>/             封面用的原生高清 3D 渲染帧（竖版 + 16:9）
tools/vibetennis/                     这一栏的共用工具（下面逐个说）
tools/vibetennis/episodes/<slug>/     这一集的 3D 场景、镜头表、叠字、音效脚本（按集存）
output/<日期>/vibetennis/<slug>/      产物：render.json / qc_attestation.json / poster.jpg /
                                      cover_16x9.jpg / qc_contact.jpg / copy.html / pushed.json
data/vibetennis_publish_ledger/       发布账本（和赛场之上同一套 publication_ledger）
```

成片 mp4 **不进 git**（`.gitignore`/100 MB 上限），走 GitHub Release `vibetennis-<slug>`。

## 一集怎么做（第一集 `vibetennis-live-faster-2026` 就是这么做的）

1. **调研**：把论文和一手资料读到能写出每个数（第一集：Brown 1931、Wallach 1939、
   Tyler 1971、Meyer 1985、Regan & Gray 2000、ATP 转播制作手册、华莱士 2006）。
   估算和示意假设要在片尾参考页写明。
2. **镜头表**：`episodes/<slug>/r3d/shots.js`——每个镜头一个 `add(t0, t1, fn)`，按音乐小节
   （`bar(k)`）切；`scene.js` 是场景（全息球场、看台粒子、辉光、颗粒、调色）。
3. **3D 渲染**：在 `r3d/` 下 `npm ci`，起静态服务 `python3 -m http.server 8765`，
   `node cap.js <起帧> <止帧> $VT_WORK/r3d/seg/sN.mp4` 分段渲（headless Chromium + SwiftShader，
   `CHROME_PATH` 指浏览器），每段同时写 `.anchors.json`（3D 点投影到屏幕的坐标）。
4. **叠字**：`overlay.py`（skia）按 `.anchors.json` 把字幕锚到对应物体旁、画引线；字幕起点
   吸附到 `beats.npy` 的音乐拍点；左上角品牌、右上角章节角标也在这里。
5. **音效与混音**：`sfx.py` 全部用 numpy/scipy 合成（不下载素材），按画面事件对齐；
   `assemble.sh` 混音：SFX -18 LUFS、音乐 -16 LUFS，总混 -14 LUFS / -1.5 dBTP，
   另出一版只有音效的（方便换 BGM）。
6. **封面**：`tools/vibetennis/cover.py`——3:4 海报走仓库**同一套 solo 海报模板**
   （`versus_poster`，台头「网球时差 · vibetennis」），按 2 倍像素出 **2160×2880 高清**；
   素材是同一场景**按竖版重新渲染**的原生帧（`r3d/still_hd.js`），不是从 16:9 裁。
   同时出 `cover_16x9.jpg`：16:9 背景帧压暗虚化，海报整张居中。
7. **定稿**：`tools/vibetennis/finalize.py`——成片第一屏是封面帧（停 `film.cover_seconds`
   ＝1.2 秒、静音，和赛场之上同一条约定），再接母片；交付版 H.264 约 8 Mbps、TV 范围 yuv420p。
8. **质检**：`tools/vibetennis/qc.py`（L2，查产物）全绿才写 `qc_attestation.json`。
   它不代替人看一遍整片：`checks.human_full_watch_claimed` 如实写 false。
9. **上传与复制页**：`tools/vibetennis/release.py`——传 Release、回写 `video_url`，
   再调 `push_reel.py --stage page` 写 `copy.html`。
10. **合并即推送**：PR 合进 main，`auto-push-vibetennis.yml` 跑
    `publish_gate.py`（闸）→ 预占账本 → `push.py`（标题＋正文＋海报＋成片＋复制页，
    复用 push_reel 的标题/正文/版式/探活）→ 记 `pushed.json` 和账本。
    推完的消息网页：`python3 tools/push_link.py --slug <slug>`。

本地先看一眼推送长什么样：`python3 tools/vibetennis/push.py --outdir <产物目录> --dry-run`
（只写 `push_preview.html`，不发）。

## 标题和正文

标题规则和别的栏目同一份（`render/copy_title.py`）：`M.D栏目|主题`，整句 ≤20 字、无空白。
`vibetennis` 十个字母，主题只剩 4–5 个字（第一集：`10.30vibetennis|现场更快`），
所以**正文第一行**写完整的问题（`网球为什么现场看比电视上快？`）。正文要**和片子里的数一致**，
估算要说是估算；末尾一个问句当置顶评论；tag ≤5（活动期自动补活动 tag）。

## TODO（没做的，别以为做了）

- **16:9 品牌片尾**：`video/column_outro.py` 的三份母版都是 1080×1440，vibetennis 还没有
  横屏母版，也没在 `column_outro.COLUMNS` 里登记（登记了就得有母版，否则出片报错）。
  第一集以片内收束卡结尾，`film.outro_seconds=0`。
- **BGM 版权**：第一集用的是所有者在会话里选的预览曲 *We Never (Remix)*（来自 vibeknowledge 仓库），
  没核授权；发公开平台前要所有者确认或换曲（只含音效的版本可直接配新 BGM）。
- **3D 渲染还在本地**：没有 GitHub Actions 渲染工作流（SwiftShader 软渲一集要几十分钟）。
- **中文显示名**：栏目名照所有者原话叫 `vibetennis`；要不要改中文名由他定。
- **dashboard**：已登记类型 `vibetennis`，但看板的「渲染/质检」阶段没有对应工作流可盯（渲染在本地）。
