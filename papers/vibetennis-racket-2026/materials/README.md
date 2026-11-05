# vibetennis ② 球拍 · 素材清单

每个文件写清：来源、授权、能不能上屏、用在哪。**能上屏**只限公有领域、CC0，或明确允许的授权且画面里没有品牌标志。

| 文件 | 是什么 | 来源 | 授权 | 上屏？ | 用途 |
|---|---|---|---|---|---|
| `US3999756.pdf` | Prince / Howard Head 大拍面专利全文（15 页扫描件，1976-12-28 授权，含 1985 年复审证书） | USPTO 官方下载 `https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/3999756` | 美国专利，公有领域 | ✅ | 专利原件出场、引用原文 |
| `US3999756-drawing-02..05.png` | 专利附图 4 页（Sheet 1–4），灰度 2685×3944 | 同上，`pdftoppm -r 250` 后缩到 1/3 | 公有领域 | ✅ | Sheet 2 的 FIG.5A/5B、6A/6B 把大拍面和「PRIOR ART」旧式拍的区域分布并排画出——3D 甜点区动画照它的轮廓做 |
| `ref/wood-racket-maxply-commons.jpg` | 一支木拍实物照（960px 缩略图） | Wikimedia Commons「File:Dunlop_Maxply.jpg」，作者 Partynia，2024-12-06 | CC BY 4.0 | ❌（拍身有品牌标志） | 只做 3D 木拍建模参考：拍头形状、胶合木条、喉部楔块 |

## 3D 模型
片中所有球拍都按真实尺寸程序化建模（Three.js），不用带品牌的模型；尺寸数据见 `../sources.md`。
