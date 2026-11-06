# vibetennis ② 球拍 · 素材清单

每个文件写清：来源、授权、能不能上屏、用在哪。**能上屏**只限公有领域、CC0，或明确允许的授权且画面里没有品牌标志。

| 文件 | 是什么 | 来源 | 授权 | 上屏？ | 用途 |
|---|---|---|---|---|---|
| `US3999756.pdf` | Prince / Howard Head 大拍面专利全文（15 页扫描件，1976-12-28 授权，含 1985 年复审证书） | USPTO 官方下载 `https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/3999756` | 美国专利，公有领域 | ✅ | 专利原件出场、引用原文 |
| `US3999756-drawing-02..05.png` | 专利附图 4 页（Sheet 1–4），灰度 2685×3944 | 同上，`pdftoppm -r 250` 后缩到 1/3 | 公有领域 | ✅ | Sheet 2 的 FIG.5A/5B、6A/6B 把大拍面和「PRIOR ART」旧式拍的区域分布并排画出——3D 甜点区动画照它的轮廓做 |
| `1893-lawn-tennis-player-racket.jpg` | 1893 年《The game of lawn tennis and how to play it》插图：持拍站立的球员，拍头是早期平顶偏方的形状（1280×2115） | Wikimedia Commons「File:The game of lawn tennis and how to play it (1893) (14798604783).jpg」，Internet Archive Book Images 扫描 | 公有领域（1893 年出版） | ✅ | 历史段开头：最早的球拍长什么样；也作 1890 年代拍头形状的建模参考 |
| `US3086777.pdf`、`US3086777-drawing-1..3.png` | 拉科斯特钢拍专利（1961 申请、1963-04-23 授权）：钢管「双梁＋腹板」截面框体、钢丝绕线 | USPTO 官方下载 | 公有领域 | ✅ | 金属拍段：框体截面剖开动画的依据（→ 威尔逊 T2000） |
| `US3752478.pdf`、`US3752478-drawing-2.png` | 挤压铝框专利（Flak / Questor，1973-08-14 授权）：三腔中空铝型材截面，图 4 为「PRIOR ART」对比 | 同上 | 公有领域 | ✅ | 铝拍：三腔截面爆炸拆解 |
| `US3755037.pdf`、`US3755037-drawing-2..3.png` | 纤维增强球拍的制造方法（1973-08-28 授权）：纤维缠绕、充压成型 | 同上 | 公有领域 | ✅ | 碳纤维段：纤维层叠的显微／分层动画参考 |
| `US4061520.pdf`、`US4061520-drawing-2.png` | 复合材料高强度结构的制造方法（1977-12-06 授权）：泡沫芯外裹纤维 | 同上 | 公有领域 | ✅ | 碳纤维段：拍框截面「泡沫芯＋碳纤维壳」 |
| `US4664380.pdf`、`US4664380-drawing-2..4.png` | 库布勒「加厚框体」球拍专利（1987-05-12 授权）：宽体框；Sheet 1 的 Fig.4 是**旧式拍框（PRIOR ART）**受击后的振动衰减曲线 | 同上 | 公有领域 | ✅ | 宽体拍、拍框硬度段：振动曲线可直接做成 3D 波形 |
| `ref/wood-racket-maxply-commons.jpg` | 一支木拍实物照（960px 缩略图） | Wikimedia Commons「File:Dunlop_Maxply.jpg」，作者 Partynia，2024-12-06 | CC BY 4.0 | ❌（拍身有品牌标志） | 只做 3D 木拍建模参考：拍头形状、胶合木条、喉部楔块 |

## 3D 模型
片中所有球拍都按真实尺寸程序化建模（Three.js），不用带品牌的模型；尺寸数据见 `../sources.md`。

## 查过、不收的
- **US 3,909,402**：国际网联历史文件脚注把它标成邓禄普碳钢拍，但 USPTO 原件第 1 页是「Water Purification Device」（净水装置）——对不上，不收、不引（2026-11-05 核）。
- 物理论文原文（Cross 1998/2006/2010 等，作者主页 PDF）只作核对，**不进仓库**（版权归出版方）；链接记在 `../sources.md`。
