# 上海大师赛：实际原源视觉审查

已对六份本地完整官方视频独立重算 SHA256，与 sources.json 一致。核查保持 1080×1440 全铺满、固定中心 cx=0.5、track=false。1920×1080 实际裁切框为 [555,0,1365,1080]，不改模板、字体、品牌或裁切策略。

此表基于原 53 段快照 SHA256 `e40f024c5208240033f1dd09378ae2baeca6fed06212168f632f6b05a0a5779f`；后续按 scene 和完整旁白定位，不只按 index。窗口是剪辑候选，不能与原声段重复堆同一镜头。所有窗口需要音频组逐区间确认英语句界；图像审查不代表无英语。

实际制作了全源每 8 秒、既有原声窗口每 1 秒与 0.25 秒、优先范围每 0.25 秒、新增候选每 0.5 秒对照图。实际查看的是下列 evidence 指定的抽样板，不冒称全源逐帧或完整球路认证。时间标签为采样中心，可能有一帧量化差，最终切点应以真实镜头切换和原音词界对齐。

满屏观感下允许短暂边缘出画；优先选中心动作、持杯、真实表情。最明显可改善宣传片质感的是：2005 真夺冠反应、2014 首战脱险正脸、2017 完整正脸捧杯、2024 冠军点与中央反应、2025 长拥抱。2005 4比0/30比0、2014 半决赛及首冠奖杯等不足以用现有源逐一对应的具体事实，保留短原生信息卡。

## 既有原声窗口的实际取舍

| 快照 index | 源 | 视觉取舍 |
|---|---|---|
| 14 | cup2005 326.8–343 s | 327.68由休息区溶解到全景，327.93已完成发球随挥；328.0起片已失发球启动。328–343适合VO背景中后段，不能标完整回合。原始326.8起包含英语时必须原声保留至句界。比分6比5/30比40，330与332–333近端费德勒左右出画；339.2–341.2纳尔班迪安反破握拳居中。 |
| 20 | final2012 32.08–39.48 s | 32–34德约近端向左切边，34.2–36.95主要动作中心，38秒左右近脸左切；真实救第一个冠军点。 |
| 23 | final2012 76.44–85.64 s | 78秒穆雷远端右边部分出画；79–80结局中心，81部分德约左切脸，82中心脸好，84低角走场清楚；真实扳回第二盘。 |
| 25 | final2012 85.64–111.48 s | 86–88近端穆雷左切，91.7–94.5德约胜后脸中心强，后段部分举手边缘被切；源约111.8开始TennisTV片尾，不得超到片尾。 |
| 29 | mayer2014 361.04–381.96 s | 361–366近脸是梅耶粉红Lotto，部分脸明显切右；367.0抛球到373回合中心表现较好，374–376梅耶背身走开，381费德勒红Nike近脸。不是2014决赛。 |
| 35 | fedal2017 281–305.2 s | 282–285纳达尔走向右边脸/body切大半；285.6–289.2末球主体多数中心，290.1–290.6费德勒脸左出画；292.5–295.1正脸最佳；298.3–299两脸短好，301/303再次边缘切。 |
| 45 | sinner2024 455.96–476 s | 458.25–461.68发球冠军点及结束主体中心；462–467辛纳庆祝脸好，470.5德约脸左出画，471.5两人靠近都在边，473秒短暂同框脸好；不要把整段握手当双脸完整。 |
| 50 | vacherot2025 360–393.84 s | 361秒瓦舍罗脸左边被切，363–368末球主要中心但365.6–366林德克内希左切；369–372/374–376捂脸主体清楚，373/377切脸，383–392拥抱主体居中效果佳。 |

## 按旁白绑定的替换候选

### P04 / 快照 index 10

这一年的决赛，纳尔班迪安原本只是替补入围。

源 `cup2005`：108.25–113.24 s。状态 `conditional_same_match_action`。

黑衣白头带纳尔班迪安对阵白黑Nike费德勒，第二盘抢七真实回合；介绍其替补身份的同场背景，不假称入围镜头。近端110秒左切部分身体；主体多数帧中心。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/cup2005-intro/sheet_02.jpg`

### P04 / 快照 index 11

面对费德勒，他先输掉两盘，却连扳两盘。

源 `cup2005`：105.6–110.5 s。状态 `conditional_same_match_action`。

真实第二盘抢七，可承载“先输两盘”的概述；此窗口尚不是连扳第三、四盘，请不做逐盘画面对照。纳尔班迪安仍穿黑衣。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/cup2005-intro/sheet_01.jpg`；`work/shanghai-masters-history-2026/visual-review/cup2005-intro/sheet_02.jpg`

### P04 / 快照 index 12

第五盘，他一度四比零领先，费德勒又追回来。甚至带着六比五、三十比零，站上自己的发球胜赛局。

源 `cup2005`：保留原生短卡。状态 `retain_short_native_fact_card`。

4比0与6比5/30比0具有具体阶段，当前已密审窗口327–339实际是6比5/30比40反破点。保留短原生事实卡，不能将该窗口伪标30比0。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/cup2005-index14-dense/sheet_00.jpg`

### P04 / 快照 index 13

冠军只差两分。纳尔班迪安却再次把结局拉了回来。

源 `cup2005`：337.5–341.2 s。状态 `split_fact_then_reaction`。

先保留“冠军只差两分”事实显示；“把结局拉回来”可切到反破6比6及339.2–341.2纳尔班迪安握拳。该情绪不是夺冠庆祝。候选4秒短于整句旁白，不拉长/循环，可按真实TTS句界拆段。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/cup2005-index14-dense/sheet_04.jpg`；`work/shanghai-masters-history-2026/visual-review/cup2005-index14-1s/sheet_01.jpg`

### P04 / 快照 index 15

四小时三十三分钟后，他赢下决胜盘抢七。一个临时得到的参赛机会，成了上海至今难忘的一场决赛。

源 `cup2005`：353.8–357.1 s、378.35–380.1 s、389.0–392.2 s。状态 `recommended_win_reaction_montage`。

真正夺冠后的倒地捂脸、正面含笑致意、举杯，均本场同人；倒地部分手腿切边，378.35后正脸清楚，奖杯窗口以后背为主、杯清楚。三窗口约8.25秒，整句9.884秒尚需短原生事实卡/短延长经核，不硬循环。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/cup2005-win-reaction/sheet_01.jpg`；`work/shanghai-masters-history-2026/visual-review/cup2005-ending/sheet_00.jpg`；`work/shanghai-masters-history-2026/visual-review/cup2005-ending/sheet_04.jpg`；`work/shanghai-masters-history-2026/visual-review/cup2005-ending/sheet_05.jpg`

### P06 / 快照 index 19

二零一二年的决赛，穆雷先拿一盘，第二盘又以五比四领先，准备发球结束比赛。

源 `final2012`：2.0–9.34 s。状态 `conditional_same_score_context`。

真实穆雷第一盘7比5、第二盘5比4、30比0的发球胜赛局回合；德约红衣近端6.25–6.75有短暂左切边，球员多数中心。用于赛事背景，不能承诺全球路。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/final2012-intro/sheet_00.jpg`；`work/shanghai-masters-history-2026/visual-review/final2012-intro/sheet_01.jpg`

### P06 / 快照 index 21

德约科维奇救下一个冠军点，把比赛拖进抢七。可危险没有过去。在那场打了约二十分钟的抢七里，他又救下四个冠军点。

源 `final2012`：40.0–46.0 s、55.0–58.25 s。状态 `recommended_championship_save_context`。

40–46抢七穆雷6比4冠军点，55–58为6比5冠军点；主要主体中心，可支撑抢七“再救”的同场叙述。前半发球局1个冠军点可沿用既有原声素材。此9.25秒组合短于11.732秒VO，按句界拆段后保留1+4的短原生统计卡。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/final2012-champ-saves/sheet_00.jpg`；`work/shanghai-masters-history-2026/visual-review/final2012-champ-saves/sheet_02.jpg`；`work/shanghai-masters-history-2026/visual-review/final2012-champ-saves/sheet_03.jpg`

### P06 / 快照 index 22

五次，离结束都只差一分。五次，比赛都没有结束。

源 `final2012`：63.0–68.85 s。状态 `conditional_championship_point_context`。

抢七穆雷10比9冠军点的实战背景，多数主体中心，67.25–67.75近端德约向右短暂切边；不能用一个回合画面声称逐一展示了五个冠军点。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/final2012-champ-saves/sheet_03.jpg`；`work/shanghai-masters-history-2026/visual-review/final2012-champ-saves/sheet_04.jpg`

### P06 / 快照 index 24

第二盘抢七，德约以十三比十一拿下。到了决胜盘，他两次破发，终于把这场决赛赢了下来。

源 `final2012`：78.5–80.2 s、91.7–94.0 s。状态 `split_set_result_and_match_result`。

前窗口为抢七12比11拿下第二盘结尾，后窗口为整场夺冠后正脸，禁止把整场举手画面配成第二盘庆祝；合计短于整句VO，13比11保留短原生比分卡较清楚。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/final2012-index23-dense/sheet_01.jpg`；`work/shanghai-masters-history-2026/visual-review/final2012-index25-dense/sheet_02.jpg`

### P06 / 快照 index 26

上海留下的，不只是一个冠军名字。还有那些明明快到终点，却仍然继续的回合。

源 `final2012`：91.7–94.5 s、108.0–111.2 s。状态 `recommended_real_winner_reaction`。

两处真实夺冠后德约致意，前处正脸好，后处举臂贴边，且接近片源片尾。两窗口合计6秒短于8.66秒VO；可采用一句缩卡/更短剪法，经root调整节奏。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/final2012-index25-dense/sheet_02.jpg`；`work/shanghai-masters-history-2026/visual-review/final2012-index25-1s/sheet_02.jpg`

### P07 / 快照 index 27

两年后，费德勒的上海大师赛首冠，也从一次险境开始。

源 `mayer2014`：449.0–454.0 s。状态 `recommended_same_match_escape`。

费德勒红Nike、黑Nike头带，本场惊险获胜后的致意/握拳正脸中心；只承载这届首冠从首战险境开始的介绍，不能标为决赛夺冠。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/mayer2014-win-walk/sheet_01.jpg`

### P07 / 快照 index 28

本届首战，他在第三盘四比五、十五比四十时，救下两个赛点。进了抢七，又救下三个。

源 `mayer2014`：367.0–376.3 s。状态 `conditional_fourth_match_point`。

近端梅耶粉红Lotto、黑Lotto头带抛球，远端费德勒红Nike救第四赛点；367–373双方主体中心较清楚，后为梅耶背身走开。这里只展示第四赛点的一个实例，2+3统计保留短原生卡，不声称五分逐一完整展示。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/mayer2014-priority/sheet_04.jpg`；`work/shanghai-masters-history-2026/visual-review/mayer2014-priority/sheet_05.jpg`；`work/shanghai-masters-history-2026/visual-review/mayer2014-index29-1s/sheet_01.jpg`

### P07 / 快照 index 30

五次躲过出局，他才继续向前。半决赛击败德约科维奇，决赛再用两盘抢七战胜西蒙。

源 `mayer2014`：449.0–452.0 s。状态 `partial_first_clause_only`。

仅“躲过出局继续向前”可用本场获胜费德勒；后半半决赛德约/决赛西蒙不可用梅耶首战冒充，继续用原生短事实卡或真实2014决赛另源。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/mayer2014-win-walk/sheet_01.jpg`

### P07 / 快照 index 31

从差一点离开，到第一次捧起上海大师赛的奖杯，这一周，结局被改写了。

源 `mayer2014`：保留原生短卡。状态 `retain_2014_trophy_fact_card`。

当前Mayer2014源无2014颁奖，不可用2017杯照片/视频假充2014首冠，保留原生短结局卡。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/mayer2014-overview/sheet_04.jpg`

### P08 / 快照 index 32

二零一七年，费德勒与纳达尔在上海决赛相遇。

源 `fedal2017`：285.6–289.2 s。状态 `conditional_real_fedal_final`。

真正2017决赛末球，费德勒紫衣近端/纳达尔蓝衣远端主体多数中心，286.6费德勒右侧贴边，289.1举手右边部分手切。窗口短于5.204秒，另接同场场馆或肖像须音频组核，不循环。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/fedal2017-priority/sheet_02.jpg`

### P08 / 快照 index 33

六比四、六比三，费德勒第二次在上海大师赛夺冠。

源 `fedal2017`：320.0–325.3 s。状态 `recommended_2017_trophy`。

真实2017费德勒接杯/持杯正脸，人物与奖杯都在中心，最佳替换本届夺冠说明字卡；本场夺冠杯不可复用2014章节。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/fedal2017-trophy/sheet_00.jpg`

### P08 / 快照 index 34

两个熟悉的名字，把多年的对抗又带到同一张球网两边。而上海，记住了他们共同留下的这一场。

源 `fedal2017`：325.3–330.5 s、298.3–299.0 s、292.5–295.1 s。状态 `recommended_2017_montage`。

持杯到举杯＋两人网前短拥抱＋费德勒正脸胜后反应，避免重复静止Fed杯照；三个窗口总8.5秒略短于9.332秒VO。298.3–299两人脸短暂同时可读，整段握手不能承诺双脸完整。与原声窗口重叠时root应择一使用。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/fedal2017-trophy/sheet_00.jpg`；`work/shanghai-masters-history-2026/visual-review/fedal2017-trophy/sheet_01.jpg`；`work/shanghai-masters-history-2026/visual-review/fedal2017-priority/sheet_06.jpg`；`work/shanghai-masters-history-2026/visual-review/fedal2017-priority/sheet_04.jpg`

### P11 / 快照 index 42

二零二四年，辛纳的对手，是上海四冠王德约科维奇。

源 `sinner2024`：452.0–457.92 s。状态 `recommended_same_match_intro`。

2024决赛实战→辛纳侧背及中央近脸；德约远端452.6–453.1冲右部分越界，属于宣传片真比赛背景，不能宣称完整最后一分。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/sinner2024-priority/sheet_03.jpg`；`work/shanghai-masters-history-2026/visual-review/sinner2024-priority/sheet_04.jpg`

### P11 / 快照 index 43

他以七比六、六比三赢下决赛，第一次捧起这里的奖杯。德约此前在上海大师赛决赛四战全胜，纪录在这一晚改变。

源 `sinner2024`：458.25–461.68 s、462.0–467.5 s、468.25–469.8 s。状态 `recommended_win_and_reactions`。

真实冠军点发球→辛纳胜后举拍/正脸→德约短正脸；同一场纪录变化叙述可用，不把图中的辛纳举拍说成捧杯。球网握手470.5–472.5双人脸多切边，已避开。与index45原声重叠必须择一/拆段。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/sinner2024-priority/sheet_05.jpg`；`work/shanghai-masters-history-2026/visual-review/sinner2024-priority/sheet_06.jpg`；`work/shanghai-masters-history-2026/visual-review/sinner2024-index45-1s/sheet_00.jpg`；`work/shanghai-masters-history-2026/visual-review/sinner2024-index45-1s/sheet_01.jpg`

### P11 / 快照 index 44

同一座球场，开始写下新的冠军名字。

源 `sinner2024`：462.0–466.5 s。状态 `recommended_winner_face`。

真正夺冠后辛纳中央近景，可承载新的冠军名字；这是index43/45的替代窗口，不重复堆同一反应。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/sinner2024-index45-1s/sheet_00.jpg`

### P12 / 快照 index 46

二零二五年，更意外的名字走到了最后。

源 `vacherot2025`：360.0–364.53 s。状态 `conditional_real_2025_introduction`。

瓦舍罗白米色Lotto、白帽，脸在361秒瞬间移到左边被切，但362后回来；363转入真实冠军点，主要中心。可作人物介绍，不伪称资格赛画面。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/vacherot2025-index50-1s/sheet_00.jpg`

### P12 / 快照 index 47

赛前世界排名第二百零四的瓦舍罗，从资格赛一路来到决赛。球网对面，竟是他的表兄林德克内希。

源 `vacherot2025`：350.0–354.8 s、355.0–359.6 s。状态 `conditional_2025_final_background`。

2025真实决赛角度与瓦舍罗背身，接表兄林德克内希近端青绿上衣的实战；中心主体多数可读，359.5绿衣近端向左越界。只作为本场背景，不能标成资格赛晋级镜头。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/vacherot2025-priority/sheet_00.jpg`；`work/shanghai-masters-history-2026/visual-review/vacherot2025-priority/sheet_01.jpg`；`work/shanghai-masters-history-2026/visual-review/vacherot2025-index50-1s/sheet_00.jpg`

### P12 / 快照 index 48

先输一盘，再连赢两盘。瓦舍罗成为大师一千赛史上，排名最低的冠军。

源 `vacherot2025`：363.0–368.45 s、369.3–371.9 s。状态 `recommended_final_point_and_reaction`。

真实2025冠军点→瓦舍罗捂脸蹲下；365.6–366近端林德克内希左切，关键结局仍有中心可读动作，369.3后捂脸主体中心。先输盘为概述，不能把第三盘画面当第一盘。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/vacherot2025-priority/sheet_05.jpg`；`work/shanghai-masters-history-2026/visual-review/vacherot2025-priority/sheet_06.jpg`；`work/shanghai-masters-history-2026/visual-review/vacherot2025-index50-dense/sheet_04.jpg`

### P12 / 快照 index 49

两个亲人争过同一座奖杯，又在赛后相拥。上海，也留下了属于他们的这一页。

源 `vacherot2025`：383.0–390.85 s。状态 `recommended_real_cousins_hug`。

实际赛后相拥，拥抱主体和瓦舍罗侧脸中心强，林德克内希脸被拥抱自然遮挡；并非双人正面肖像，适合高潮情绪画面。与原声index50择一或切分，避免整段重复。

实际查看证据：`work/shanghai-masters-history-2026/visual-review/vacherot2025-priority/sheet_11.jpg`；`work/shanghai-masters-history-2026/visual-review/vacherot2025-priority/sheet_12.jpg`；`work/shanghai-masters-history-2026/visual-review/vacherot2025-priority/sheet_13.jpg`

## 共用限制

- 固定中心全铺满优先。横向球路/双人分立自然会切边；有瞬间越界不否决整源，选实际中心动作与脸部反应，旁白不说完整末球复盘。
- 所有比赛原生计分牌位于左下，被中心crop切部分姓名/比分。最终必须用栏目既有计分牌补丁方式，核真值；不要自创比分牌模板。
- 2005有原源4:3归档左右黑柱；中心crop消除黑柱，但历史画质仍较低，不能宣称原生历史4K。
- 本审查不是音频通行证，也不是最终成片logo/字幕/品牌总检；最终export应由root按原栏目要求核。

完整窗口、原53段旁白、实际六源sha及证据路径见同目录 `visual-footage-review.json`。未修改 native spec 或全局代码。

实际查看后的六源优秀中心取景缩略图：`work/shanghai-masters-history-2026/visual-review/reviewed-highlight-crops.jpg`。该图仅内部审查证据，未作为成片自创布局。

## 最后补审：2017两分之间准备段

280.5–281.2仍为上一分末段全景，费德勒近端向右跑，球仍在近端右侧，不得把整个280.5–284.0误称死球准备。约281.33硬切纳达尔蓝衣走动；281.33–285.50没有抛球发球，285.6才切下一分全景。281.34–284.73以0.65速度约5.215秒能覆盖5.204秒VO且不进入下一分，但282.3后脸贴右边、283–284.73大半脸持续出框，人物质感较弱。更好的中心镜头选择是只留281.34–282.20短段中央走动后接已验证2017官方照片，由root按旁白句界切。音频组由root反馈safe280.5–288.4、289.48后英文未确认，此处不独立宣称无英语。实际证据priority sheet00/01。
