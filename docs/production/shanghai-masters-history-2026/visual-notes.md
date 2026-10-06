# 本期视觉辅助：完全沿用原栏目版式

用户最新要求所有布局与视觉跟原栏目一致。因此第一轮自绘13张的巨大年份、上置标题、花瓣纹理、双数字面板、九节点及自建节点列表全部撤出正式交付，只留在 `graphics/internal-drafts/` 作为内部废弃草案。该目录禁止进入最终成片；原说明已由本文件取代。

正式候选改为16张原生章节/论点卡，全部直接调用仓库 `tools/render_title_card.py:render` 和 `build`，只换 text/kicker，原生版式、字体、四色顶部细杠、底部品牌以及共享深蓝背景均未改。`git diff -- tools/render_title_card.py tools/render_stat_card.py` 为空；没有本期CSS覆盖、额外纹理或新图形模板。完整实际原生JPG是渲染器默认的2160×2880超采样，1080×1440 PNG是同张原图等比例Lanczos缩小，未移动元素或重新排版。辅助HTML仅把内嵌字体payload改为指向同一份本地字体，DOM与样式来自原生build。

## 实际对照证据

已从当前Git HEAD读取并实际查看两张原有正式产物：

- 既有「网球有故事」：`output/2026-09-27/reel/china-open-withdrawals-story-2026/title_card_02.jpg`，复制到 `graphics/comparison/original-story-published.jpg`。它证明原故事片已有居中得意黑两行标题、小框和品牌，不是第一轮自绘布局。该历史产物使用旧墨绿底及旧品牌位置，只作历史版式证据，不恢复其旧配色。
- 现行原生栏目章节卡：`output/2026-10-05/reel/zheng-bouzkova-beijing-2026-r3/title_card_02.jpg`，复制到 `graphics/comparison/original-current-column.jpg`。它已使用共享深蓝底、顶部四色细杠、居中得意黑和底部安全品牌，本期直接沿用同一生成器。
- 三列真实图片对照：`graphics/comparison/layout-comparison.jpg`。已使用view_image查看原有两图、对照图、本期16卡接触表和2005完整预览。
- `graphics/comparison/native-layout-witness.json` 保存Git HEAD、原生渲染器SHA256、未修改证明和两张原有产物路径。

比对的结论是：第一轮仅配色相同，版式不符合最新要求；现行正式候选使用相同生成器，保留原有栏目布局。旧草案不能用于证明合格。

## 原生导入方式

**首选按 `graphics-manifest.json` 中的 title_card/kicker 直接写原生segment，让build_match_reel在成片时现渲。** 本期不设置layout或保持null，原生 `_materialize_title_cards` 按1080×1440画面区渲染并设置full_bleed=True，全部铺满。不得改成band或证据小窗。

各候选包含 `native_segment_template`，seconds与narration仍需按实际生成旁白补齐，模板中占位文字不是可执行spec。每张原生卡已包含标准卡底logo与handle，不要叠加第二个卡底品牌。比赛窗口照常采用原栏目原生角标、字幕和比分回贴。不要再叠自绘花瓣或背景。

16张并非要求全部入片；只选择叙事需要的卡，真实经典回合仍优先完整官方画面。不要把整片做成静态幻灯，或重复、拖长卡片填满时长。章节卡字幕仍按原栏目标准时间轴渲，最后检查实际字幕帧与品牌安全区。

## 对应事实

| 候选 | 原生两行内容 | 事实界限 |
|---|---|---|
| 01 | 1996年／上海首届ATP赛事 | 1998不是元年 |
| 02 | 1998张德培／在上海夺冠 | 早期里程碑 |
| 03 | 2002大师杯／世界来到浦东 | 上海新国际博览中心；不用旗忠资料图 |
| 03b | 两盘领先又被追平／休伊特五盘夺冠 | 2002大师杯，不是Masters 1000 |
| 04 | 第5盘4比0／纳尔班迪安领先 | 第五盘局分、纳尔班迪安视角 |
| 05 | 冠军只差2分／费德勒30比0 | 小框定位第5盘6比5发球；不是赛点 |
| 06 | 纳尔班迪安／逆转费德勒夺冠 | 2005大师杯冠军 |
| 07 | 2009大师赛／亚洲唯一一站 | 全球9站之一，非大师杯改名同一种比赛 |
| 08 | 德约救下／5个冠军点 | 2012决赛 |
| 08b | 发球胜赛局1个／抢七再救4个 | 均为德约救下的冠军点 |
| 09 | 抢七13比11／德约扳回第二盘 | 13-11是抢七分数；正式盘分7-6¹¹ |
| 10 | 费德勒救下／5个赛点 | 2014第二轮、本届首战 |
| 10b | 发球局救2个／抢七再救3个 | 第3盘4-5、15-40本人发球 |
| 11 | 费德勒／上海大师赛首冠 | 2014；2006/2007大师杯冠军另计 |
| 12 | 连续3年取消／三个暂停的秋天 | 2020—2022，不造新闻影像 |
| 13 | 单打96签／12日正赛 | 2023；12日不含资格赛 |

没有为适配统计图填入不存在的技术数据或虚构球员头像。已读取render_stat_card的固定统计模板，本期这些历史和关键分说明不能伪装成ACE/双误/一发等赛后技术统计，所以全部用既有title_card。事实来源编号同本期facts-and-sources.json，各图见graphics-manifest.json。

重建命令：`python assets/reel/shanghai-masters-history-2026/graphics/build_graphics.py`。运行时稀疏检出缺少原品牌bitmap，脚本读取 `HEAD:assets/logo/brand/icon-512.png` 原Git blob落在本期目录，只改运行时资源路径，未替换logo图案或改全局文件。

## 用户选定封面最终复核

封面保持用户选择的两行“白玉兰下的传奇”／“一座城与几代网坛大师”，小题“上海大师赛 · 从大师杯到大师1000”，未改词。已从最新cover-plan.json调用 `tools/versus_poster.py:build_poster(layout="solo")` 重渲到 `assets/reel/shanghai-masters-history-2026/cover-preview.jpg`；cover-plan与native-spec.draft.json的cover完全一致。没有修改全局样式。

最新素材为官方4K实图 `qizhong-rolex-aerial-4k.jpg`，真实3840×2160，居中裁窗为[1110,0,2730,2160]，即1620×2160，再等比例缩到1080×1440；不是放大1920图。原模板hero为background-size:cover、background-position:50% 50%，无黑边、信箱或模糊垫层。实际view_image已查看：旗忠花瓣、观众席与中央球场可读，顶栏与标题区沿用原生solo母版。

原品牌logo已恢复并正常显示，图像完整解码；实际位置为x70、y61.5、52×52。品牌文字x136、y44，副标题x136、y92，均与大字分离。hook为字符串，storytitle恰好两个div、没有列表方括号；两行均94px，标题y790—1023，横向overflow为0。未叠新底部标签或比分板。

`same_line_as_printed`原生判断为true：封面旁白就是这两句印字，因此原生pipeline不会再重复排一组封面字幕。后续成片仍须抽帧检查切入第一段字幕与品牌的实际时轴，静图不替代全片字幕质检。

旧 `work/shanghai-masters-history-2026/preview/poster.jpg` 尚是1920来源与缺logo版本，与最新封面最大像素差245；已通知root刷新该缓存，本代理按文件所有权没有改work目录。先前1920版本的缓存一致性核验不适用于当前4K版。最终审核以最新 `cover-preview.jpg`、`cover-preview-audit.json` 与其source/logo/cover-plan SHA256为准。四列原生母版对照 `graphics/comparison/layout-with-cover-comparison.jpg` 已更新为4K带原logo封面。


## 六份完整官方视频的实际裁切审查

已收到并独立重算六源 SHA256，全部与 sources.json 相符；固定中心 3:4 全画布抽样对照与实际查看证据见 visual-footage-review.json / .md。每个候选绑定原53段快照 scene、完整旁白和 index；不直接改 spec。重点可用同场表情、持杯、拥抱替代长说明卡；允许满屏中心裁切导致短暂左右越界，逐条诚实记录，没有把抽样冒称完整球路通过。2005反破段的真实分数是6比5/30比40；2014近端粉红Lotto/黑Lotto头带是梅耶，远端红Nike/黑Nike头带是费德勒；2017持杯不可用作2014首冠。全部新增VO窗口由音频组再核，无声结论不从画面推断。


## 旗忠内景裁图来源更正

`qizhong-interior-portrait.jpg` 的真实母图是 `qizhong-2026-resource.jpg`。Root 与视觉组已通过实际图像匹配并查看确认；来源为赛事官网 2026 年发布的资源文章，署名 **Jade Gao / AFP via Getty Images**。该图只说明场馆，不宣称拍摄年代，也不标作 2019 现场或疫情期间空场。此前把这一裁图归为 `srm19jb_1745.jpg` 的信息已更正。独立原图 `srm19jb_1745.jpg` 自身仍是官方明确标注的 2019 上海大师赛内景，信息保留。

最终照片提交白名单见 `final-photo-files.json`；按实际最终 spec 的图片与封面引用列出，排除 `graphics/`、`graphics/internal-drafts/` 及其他未入片参考图片。
