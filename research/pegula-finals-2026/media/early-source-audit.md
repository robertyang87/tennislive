# 佩古拉2026：早季官方素材准备审计

范围：澳网、迪拜、查尔斯顿、法网、柏林；仅为本集可审提纲备料。未正式渲染，未改共享spec，未进行git fetch/checkout/commit。详尽身份、字节数、SHA256、ffprobe、归档run及候选链接见同目录 `early-source-audit.json`；实际8源的独立清单为 `early-downloaded-sources.json`。

## 已取得的实际原生1080视频

|站点/用途|官方发布者 / YouTube ID|实际尺寸、时长|本地文件（sources/）|
|---|---|---|---|
|澳网半决赛|Australian Open / qMezbjE3Nu4|1920×1080，486.713s|ao-sf.mp4|
|迪拜半决赛|WTA / L7tpXYiUH9c|1920×1080，309.894s|dubai-sf.mp4|
|迪拜决赛|WTA / n8N7tGMhsQA|1920×1080，309.406s|dubai-final.mp4|
|迪拜半决赛本人采访|Dubai Duty Free Tennis Championships / GxUTADaA1MQ|1920×1080，135.697s|dubai-sf-interview.mp4|
|迪拜夺冠本人发言|Dubai Duty Free Tennis Championships / kuICNiB--fE|1920×1080，90.419s|dubai-champion-speech.mp4|
|查尔斯顿决赛|WTA / Zwi_zjefnh0|1920×1080，309.685s|charleston-final.mp4|
|柏林半决赛|WTA / Il6cKvP4qAw|1920×1080，306.434s|复用Sabalenka项目staging/extra/berlin-sf.mp4|
|柏林决赛|WTA / fKfC75_5ZCI|1920×1080，309.267s|berlin-final.mp4|

以上均已取得真实字节并ffprobe，不是网页标称1080。半决赛采访由迪拜赛事官网页面直接嵌入确证；夺冠发言由同名赛事官方频道发布，描述写明2026击败斯维托丽娜夺冠。实际视频抽帧已核佩古拉本人、赛事场地/领奖台/比赛服和相关记分条，未把整条素材当作已通过全程前景审核。六条新归档run全部success，迪拜决赛复用既有Release，柏林SF复用已落地官方源。

## 可进入提纲的事实与画面线索

- **1月29日澳网SF**：3-6、6-7(7)负莱巴金娜，首次澳网四强。源437.4–451.4s为末段比赛/反应候选；438/442s全景、446/450s反应已看。尚未逐帧核起拍与完整解说，不标“已可剪”。
- **2月20–21日迪拜**：半决赛从1-6、1-3落后逆转阿尼西莫娃，1-6、6-4、6-3；决赛6-2、6-4胜斯维托丽娜，赛季首冠、生涯第10冠、第4座WTA1000。SF259.2–283s、F239–259.5s为末分/反应扫描候选。SF262s近端球员触左裁边，不能直接判固定球场中心3:4合格；决赛239–244s较有希望，仍需逐帧和原声句尾审核。WTA4454811写“two days earlier”与官方逐场日期不符，叙事按2/20、2/21，即前一天。
- **4月1–5日查尔斯顿**：前四场**全部三盘**，前三场**先丢一盘**，决赛6-2、6-2胜斯塔罗杜布采娃，卫冕并夺赛季第二冠。官方逐场API已保存并摘录到 `charleston-pegula-match-evidence.json`。WTA4482619特写写“first two”不如实际逐场比分准确；提纲用“四场三盘”。终局267.8–283s虽有真实冠军点/庆祝，**270s固定中心裁切会切掉近端球员，不能直接用作合格完整回合**。
- **5月26日法网R1**：先赢一盘，仍以6-1、3-6、3-6负比勒尔，首轮出局。未取得赛事/巡回赛官方原生1080同场视频及佩古拉本人同次失利采访。WWOS正版源归档因仅限澳洲而失败，未绕过地域限制；不追加广播来源探测。**本集按已定提纲使用事实卡**，不杜撰本人心理、采访或时码。
- **6月20–21日柏林**：SF6-4、6-7(4)、6-0胜萨巴伦卡；F4-6、6-4、3-6负诺斯科娃，亚军。SF256.5–270.95s有真实末分及完整“into another final”解说（此前源绑定双ASR证据已列JSON），但260s近端球员出左裁边；旧集审核不等于本集裁切通过。F254.5–283s为末分/诺斯科娃倒地/握手候选，未过完整原声与逐帧审查。

## 本人原声候选：实际双ASR，尚非正式字幕

实际small.en/medium.en输出均在本目录，SHA与源绑定。这里只认 `asr_cross_checked`，没有声称人工听审。

1. **迪拜SF9.15–18.12s**：她回忆决胜盘1-1时看向教练，并说 **“I'm just happy I'm still even here right now. She was playing some incredible tennis.”**（“我很高兴自己还在比赛里。她打得实在太好了。”）这两句共同核心在13.72–18.12s；前导连接词small识别“and I said”，medium为“I'm saying”，已标未决，不冒称逐字字幕定稿。18.50s才开始下一句，候选末端避开它。
2. **迪拜夺冠20.40–34.45s**：完整回答“很棒的生日礼物”、几小时后飞回家、**“But just super happy to go home with a trophy. It was a great week.”**（“能带着奖杯回家，我特别开心。这一周很棒。”）。双ASR实质意思一致，口头“yeah / it was just”有细小分歧；详见 `interview-candidates.json`。主持人下一问38.42s，候选不含新问题。若压片长，可再精审28.60–34.45s短版。

这两段实际帧已看，人物是真实佩古拉；**人脸中心尚未实测，cx_face保留null**。正式制作阶段仍须完成真实中心measurement、逐词字幕/行宽与边界审核。

## 封面实拍建议

优选 `media/photos/charleston-trophy.jpg`：**5181×3454、12,614,142bytes**，WTA4482273原图，2026-04-05；**Matthew Stockman/Getty Images**。实际全图已目视：佩古拉正脸、睁眼无遮挡，手持查尔斯顿玻璃奖杯，Credit One Charleston Open背景与花景可识别。同目录 `cover-photo-candidates.json`保存原始URL、credit及SHA。迪拜候选仅1024×683，画质不足，不选为HQ封面。未生成或合成照片。

抽帧证据在 `media/contacts/`：每源全画幅contact以及固定球场中心3:4的真实源画面。这里只是素材准备/局部证据，**不代表完整回合、正式字卡叠图或最终成片QC通过**。
