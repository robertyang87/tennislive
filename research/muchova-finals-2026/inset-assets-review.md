# 穆霍娃赛事信息角标｜资产与有限预览

生成9张右上信息条，映射见 `requests/stories/muchova-finals-2026/inset-assets.json`。未修改候选或正式runtime spec。

- 澳网第四轮、法网第三轮、温网决赛、美网第三轮，都采用她止步轮次与穆霍娃视角整场盘分。
- 多哈决赛、迈阿密1/4决赛、斯图加特决赛、巴特洪堡决赛，分别按实际比赛日标注。
- 额外补温网半决赛第一次出现画面的信息条；原候选尚无该贴图。
- 巴特洪堡把退赛说明从非法的score字符串移到可见topic“草地首冠·对手退赛”，score保持“6-1 1-0”。未改事实。
- 温网半决赛小分存在官方字段冲突，只标已经一致核实的“6-2 1-6 7-6”，不填抢十精确小分。

全部图片采用现有 `render_story_info_band.render_label`，透明底、右缘短轨、右对齐、SmileySans-Oblique文字与TL Score比分字体；`label_fields_problem`和`png_corner_label_problem`逐张返回无问题。首次信息条默认8秒（原生淡入/淡出会占少量边界时间），若镜头不足8秒须延续或延长，不能仅改资产宣称已显示8秒。

## 有限视觉检查

已目检9张贴图本身，文字未截断、日期/比赛/双方/结果都可读。另用8条现有源片在所选起点后0.8、4、7秒各取1帧，生成24张有限预览，采用当前原生1080×1440中心裁切、原生品牌角标坐标与原生信息条宽度/边距，信息条顶部下限为151px。合成只包含画面、品牌与信息条，没有最终ASS字幕、动效或完整连续视频。

样张索引与哈希：`evidence/inset-placement-samples.json`；总表：`contact-sheets/inset-placement/all-placement-samples.jpg`。这些样张中信息条未压人物眼口，也未与左上品牌碰撞；澳网亮天空处仍靠现有描边阴影维持文字识别，最终片需在实际像素再次检查。

法网因当轮主源仍在补，只验资产，不声称已验人物避让。北京/武汉如后续从事实卡改为真实视频，仍需按实际选定轮次补首次赛事贴图；混双与金杯待明确素材/镜头后再定，不臆造高光的标签。

这份记录不授予整片QC或发布通过。最终runtime合并、采访人物中心、字幕、运动全过程遮挡和第7秒仍可见须在正式原生预览及成片中验。

### 补交：证据展示版与混双/金杯角标

- 五张官方积分竖图已派生为 `evidence-{miami-390,stuttgart-325,bad-homburg-500,wimbledon-1300,total-4735}-canvas.png`。统一 1500×1400，原生 DARK background `#080e1d`；1024×1280 原图从 `(238,60)` 起原像素贴入，不裁、不缩、不改色、不改文字。保存后回读，五张原图区域逐像素差均为零。源/派生 SHA256 与坐标详见 `inset-assets.json` 的 `evidence_canvas_assets`。
- 新增 `context-uso_mixed_final.png`、`context-bjk_cup_final.png`；原生 render_label 字段和右轨静态闸通过。混双抢十完整写为 `event: 6-3 1-6 [10-6]`，避免伪装成普通第三盘比分。
- 静态总表 `contact-sheets/evidence-canvas-assets.jpg` 已目视检查：原图边缘完整、留边正确，角标无截字。最终缩放/字幕/动效仍须主线程检查，不以资产检查代替成片验收。
