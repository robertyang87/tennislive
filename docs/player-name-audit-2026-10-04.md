# 球员中文译名全量复查：2026-10-04

范围：当前 ATP/WTA 各 500 个排名快照条目，加排名之外 173 个字典键，共 1173 条。英文重音、大小写及别名键仍分别留账；并非 1173 位互不重复的球员。排名日期仍为 `27 July 2026`，本轮不刷新排名。

两轮累计主显示名修正 101 个条目（第二轮新增 53 个）；其中 Tim Puetz / Tim Pütz 是同一人的两个英文别名。另统一原先分叉的 Python 字典、快照及人工覆盖表，并重建待复核队列。

## 核实程度

| 状态 | 条目数 | 含义 |
| --- | ---: | --- |
| 媒体原文确认 | 443 | 已读取中文正文或视频页面发布简介，并核对球员身份；单一来源不等于媒体唯一共识。 |
| 原生姓名核验 | 36 | 核对中文姓名或日文汉字全名，转为简体；米兰仅有专业网球媒体原文与 WTA 身份交叉核对，Jenny Lim 为本人社交双语署名且无官网反链，两项均标中等置信度。 |
| 来源存在多译 | 36 | 记录已知用名差异；有充分依据的选定库内主名，其余保留现名并继续待核。 |
| 已修正但待进一步核实 | 7 | 包括语义机翻修正、人工音译统一及专业媒体中文名的中等置信度身份核验。国际英文排名只证明身份，不证明中文媒体译名。 |
| 暂定译名保留 | 502 | 未取得足够中文主流媒体或官方依据，不以音译冒充已确认。 |
| 现有人工词典名保留待核 | 149 | 本轮没有拿到足够原文依据，不能仅凭 curated 标签声称权威确认。 |

排名表受控音译/机器译名队列现有 **512 条**，不阻断现有内容流程。另有现名待核、多译及原生全名缺口，完整状态均在逐条账中，不能把队列长度当作全部未核实条目数。

**本轮完成的是全量覆盖的复查和有据修正，不是声称全部球员都已有统一官方中文译名。** 搜索验证码、无结果、链接不可读、同姓或姓名子串误命中，都不算核实成功。未确认的条目明确保留待核。

逐条英文名、原名、现名、来源链接、原文摘录、选择理由、独立来源数量及未解决原生姓名见 [`data/player_name_audit_2026-10-04.json`](../data/player_name_audit_2026-10-04.json)。人工覆盖来源保存在 [`data/player_name_overrides.json`](../data/player_name_overrides.json)。

## 显示名修正

| 英文名 | 原显示名 | 统一显示名 | 状态 |
| --- | --- | --- | --- |
| Luciano Darderi | 达尔代里 | 达尔德里 | 媒体原文确认 |
| Jakub Mensik | 门西克 | 门希克 | 媒体原文确认 |
| Karen Khachanov | 哈恰诺夫 | 卡恰诺夫 | 媒体原文确认 |
| Alexei Popyrin | 波皮林 | 波普林 | 来源存在多译 |
| Alex Michelsen | 米切尔森 | 米克尔森 | 来源存在多译 |
| Matteo Arnaldi | 阿尔纳尔迪 | 阿纳尔迪 | 媒体原文确认 |
| Mattia Bellucci | 贝卢奇 | 贝鲁奇 | 来源存在多译 |
| Terence Atmane | 阿特马内 | 阿特玛纳 | 来源存在多译 |
| Stephane Robert | 罗贝尔 | 罗伯特 | 媒体原文确认 |
| Roberto Carballes Baena | 卡巴列斯·巴埃纳 | 卡巴雷斯·巴埃纳 | 来源存在多译 |
| Jacob Fearnley | 弗恩利 | 费恩利 | 来源存在多译 |
| Zizou Bergs | 贝尔格斯 | 贝尔赫斯 | 来源存在多译 |
| Dominic Stricker | 施特里克 | 斯特里克 | 来源存在多译 |
| Tim Puetz | 皮茨 | 普茨 | 媒体原文确认 |
| Tim Pütz | 皮茨 | 普茨 | 媒体原文确认 |
| Fabian Marozsan | 马罗赞 | 马洛桑 | 媒体原文确认 |
| Vit Kopriva | 科普日瓦 | 科普里瓦 | 来源存在多译 |
| Dalibor Svrcina | 斯弗尔奇纳 | 斯夫尔奇纳 | 来源存在多译 |
| Nicolas Jarry | 哈里 | 贾里 | 媒体原文确认 |
| Ignacio Buse | 布塞 | 布赛 | 来源存在多译 |
| Emil Ruusuvuori | 鲁苏武里 | 鲁苏沃里 | 媒体原文确认 |
| Anna Danilina | 达尼利娜 | 达尼丽娜 | 媒体原文确认 |
| Lyudmyla Kichenok | 柳德米拉·基琴诺克 | 柳德米拉·奇琴诺克 | 媒体原文确认 |
| Nadiia Kichenok | 娜迪娅·基琴诺克 | 娜迪娅·奇琴诺克 | 媒体原文确认 |
| Nicole Melichar-Martinez | 梅利哈尔-马丁内斯 | 梅里查尔 | 媒体原文确认 |
| Feng Shuo | 冯硕 | 丰硕 | 原生姓名核验 |
| Anastasia Zakharova | 扎哈罗娃 | 扎哈洛娃 | 来源存在多译 |
| Yulia Putintseva | 普汀塞娃 | 普丁塞娃 | 来源存在多译 |
| Sofya Lansere | 兰塞尔 | 兰瑟雷 | 已修正但待进一步核实 |
| Lucia Bronzetti | 布龙泽蒂 | 布朗泽蒂 | 来源存在多译 |
| Marco Trungelliti | 特伦杰利蒂 | 特兰杰里迪 | 来源存在多译 |
| Hugo Dellien | 德利恩 | 乌戈·德里安 | 来源存在多译 |
| Simona Waltert | 瓦尔特特 | 沃尔特特 | 来源存在多译 |
| Nuria Parrizas Diaz | 帕里萨斯·迪亚斯 | 帕里萨斯·迪亚兹 | 媒体原文确认 |
| Ilie Nastase | 纳斯塔塞 | 纳斯塔斯 | 媒体原文确认 |
| Conchita Martinez | 康奇塔·马丁内斯 | 孔奇塔·马丁内斯 | 媒体原文确认 |
| Johanna Larsson | 拉尔松 | 拉尔森 | 媒体原文确认 |
| Kiki Bertens | 贝尔腾斯 | 贝尔滕斯 | 媒体原文确认 |
| Martin Klizan | 克利赞 | 克里赞 | 媒体原文确认 |
| Zachary Svajda | 斯瓦伊达 | 什瓦伊达 | 来源存在多译 |
| Michael Mmoh | 莫 | 迈克尔·莫 | 媒体原文确认 |
| Hayato Matsuoka | 松冈 | 松冈隼 | 原生姓名核验 |
| Yuta Shimizu | 清水 | 清水悠太 | 原生姓名核验 |
| Masamichi Imamura | 今村 | 今村昌伦 | 原生姓名核验 |
| Denis Yevseyev | 叶夫谢耶夫 | 叶夫塞耶夫 | 来源存在多译 |
| Renta Tokuda | 德田 | 德田廉大 | 原生姓名核验 |
| Omar Jasika | 贾西卡 | 雅西卡 | 来源存在多译 |
| Petra Marcinko | 马尔钦科 | 马辛科 | 媒体原文确认 |
| Veronika Erjavec | 埃尔哈维茨 | 埃里亚韦茨 | 来源存在多译 |
| Alina Charaeva | 恰拉耶娃 | 查拉耶娃 | 媒体原文确认 |
| Polina Iatcenko | 亚特琴科 | 伊亚琴科 | 媒体原文确认 |
| Sofia Costoulas | 科斯托拉斯 | 克斯特拉斯 | 媒体原文确认 |
| Carol Young Suh Lee | 李 | 李英洙 | 已修正但待进一步核实 |
| Luisina Giovannini | 乔万尼尼 | 焦万尼尼 | 媒体原文确认 |
| Yeonwoo Ku | 具妍雨 | 具姸玗 | 原生姓名核验 |
| Varvara Lepchenko | 列普琴科 | 勒普琴科 | 媒体原文确认 |
| Julia Avdeeva | 阿夫德耶娃 | 阿夫杰耶娃 | 媒体原文确认 |
| Elena Pridankina | 普里丹基纳 | 普里丹金娜 | 来源存在多译 |
| Elizara Yaneva | 亚涅瓦 | 亚涅娃 | 媒体原文确认 |
| Anastasiia Sobolieva | 索博利耶娃 | 索博列娃 | 媒体原文确认 |
| Whitney Osuigwe | 奥苏伊格韦 | 奥斯维圭 | 媒体原文确认 |
| Guiomar Maristany Zuleta De Reales | 玛丽斯塔尼·祖莱塔·德·雷亚莱斯 | 马里斯塔尼 | 媒体原文确认 |
| Angela Fita Boluda | 菲塔·博鲁达 | 菲塔·波鲁达 | 媒体原文确认 |
| Anouk Koevermans | 科弗曼斯 | 科费尔曼斯 | 媒体原文确认 |
| Francisca Jorge | 豪尔赫 | 若热 | 媒体原文确认 |
| Selena Janicijevic | 亚尼奇耶维奇 | 亚尼契耶维奇 | 媒体原文确认 |
| Vera Zvonareva | 兹沃娜列娃 | 兹沃纳列娃 | 媒体原文确认 |
| Tereza Martincova | 马丁佐娃 | 马丁科娃 | 媒体原文确认 |
| Hanna Chang | 张 | 张汉娜 | 媒体原文确认 |
| Hiromi Abe | 安倍 | 阿部宏美 | 原生姓名核验 |
| Ena Koike | 小池 | 小池爱菜 | 原生姓名核验 |
| Rina Saigo | 西乡 | 西乡里奈 | 原生姓名核验 |
| Yufei Ren | 任 | 任钰菲 | 原生姓名核验 |
| Mimi Xu | 徐 | 徐铭格 | 媒体原文确认 |
| Yuriko Lily Miyazaki | 宫崎 | 宫崎百合子 | 原生姓名核验 |
| Sakura Hosogi | 细木 | 细木咲良 | 原生姓名核验 |
| Momoko Kobori | 小堀 | 小堀桃子 | 原生姓名核验 |
| Yidi Yang | 杨 | 杨一迪 | 原生姓名核验 |
| Varvara Panshina | 盘石那 | 瓦尔瓦拉·潘希娜 | 已修正但待进一步核实 |
| Miho Kuramochi | 仓持 | 仓持美穗 | 原生姓名核验 |
| Eunhye Lee | 李 | 李恩惠 | 已修正但待进一步核实 |
| Natsumi Kawaguchi | 川口 | 川口夏实 | 原生姓名核验 |
| Patcharin Cheapchandej | 廉价昌德 | 帕查琳·齐普昌德 | 已修正但待进一步核实 |
| Jiaqi Wang | 王 | 王佳祺 | 原生姓名核验 |
| Boyoung Jeong | 郑 | 郑宝映 | 原生姓名核验 |
| Misaki Matsuda | 松田 | 松田美咲 | 原生姓名核验 |
| Reina Goto | 后藤 | 五藤玲奈 | 原生姓名核验 |
| Eri Shimizu | 清水 | 清水映里 | 原生姓名核验 |
| Lucie Nguyen Tan | 阮晋勇 | 露西·阮·谭 | 已修正但待进一步核实 |
| Jenny Lim | 林 | 林丽诗 | 原生姓名核验 |
| Mio Mushika | 虫贺 | 虫贺心央 | 原生姓名核验 |
| Astrid Lew Yan Foon | 刘仁宽 | 阿斯特丽德·卢·扬·丰 | 已修正但待进一步核实 |
| Yuno Kitahara | 北原 | 北原结乃 | 原生姓名核验 |
| Yujia Huang | 黄 | 黄裕迦 | 原生姓名核验 |
| Hikaru Sato | 佐藤 | 佐藤光 | 原生姓名核验 |
| Rinko Matsuda | 松田 | 松田铃子 | 原生姓名核验 |
| Lan Mi | 米 | 米兰 | 原生姓名核验 |
| Ikumi Yamazaki | 山崎 | 山崎郁美 | 原生姓名核验 |
| Reese Brantmeier | 布兰特梅尔 | 布兰特迈尔 | 媒体原文确认 |
| Kayo Nishimura | 西村 | 西村佳世 | 原生姓名核验 |
| Chengyiyi Yuan | 元 | 袁程依依 | 原生姓名核验 |

## 选择及同步规则

- 先核对原生中文/汉字姓名和本人身份。外国球员按已核实的国内官方及主流媒体用名选本库主名；同一机构的多篇稿件不会记成多个独立媒体。
- 多译不因单篇稿件发布日期较新就机械替换。例如阿特玛纳/阿特马纳、普茨/其他变体保留来源记录；新证支持的主名已对齐，其他真实媒体变体继续留账。
- 六位此前只显示姓的 CHN 球员（任钰菲、杨一迪、王佳祺、黄裕迦、米兰、袁程依依）已核对 WTA 完整姓名和国籍，并同步中国球员识别的两张名单。
- 原生姓名仍待核的 Lea Ma、Victoria Hu、Sanhui Shin，以及巴西球员 Pedro Sakamoto 的完整中文显示名继续留账；Gabriela Ce 的单字显示也进入缺口名单。不能由拼音或族裔猜汉字及国籍。
- Jenny Lim 的林丽诗来自本人双语社交署名，置信度中等，仍缺官网反链；李英洙及李恩惠为专业媒体用名，继续标已修正待进一步核实。李恩惠的同名 WTA 身份分别记录，不合并两个账号。
- 七项错配证据已撤销并保留拒绝记录，五项补充正确球员新证；Aidan Mayo 与 Dick Norman 仍未核实。英文排名、英文赛果与官方 API 只算身份交叉证据，不计中文译名原文来源。
- 12 份未发布稿件已按英文身份修正中文名；另修正两个现行内容生成器的 29 个显示字符串，覆盖旁白、SVG 图、说明卡和故事正文。
- 历史内容队列覆盖 42 个文件：原 18 文件的 19 个身份绑定字段，另 24 文件的 184 个文本字段或行（208 次旧名出现，其中 117 次是应保留的来源/注释证据）。活动源码已修正的条目分别标记，历史输出及发布凭证未伪造为已重渲，见 [`data/player_name_content_review_queue_2026-10-04.json`](../data/player_name_content_review_queue_2026-10-04.json)。真正拼错的巴图什科娃继续待修，不作规范变体。
- 更新工具与实际查询入口共享重音和撇号归一规则。旧 CNTV 来源按央视官方域名识别；人工校订的暂定译名优先于无来源字典，并继续进入复核队列。

## 验证

```sh
python tools/update_player_names.py --check
python tools/audit_player_name_alignment.py
pytest -q tests/test_player_names.py tests/test_names.py tests/test_player_name_alignment.py
```

覆盖率为 ATP 500/500、WTA 500/500；跨三表、真实 `player_zh()` 与下一次禁止网络翻译的模拟同步均应一致，来源元数据也不能漂移。同步工作流同时执行这些检查。全库测试结果另记在本次 PR，环境及基线问题与改动回归分开报告。

第一轮全库实跑：5319 passed、69 failed、11 errors、285 skipped。两项由规范译名变更触发的旧测试预期已修复（按实际 resolver 断言；历史旧规范名仅在指定存量文本兼容），另加反向检查确保新文本仍拦错名。其余 67 个失败和 11 个错误在固定原始提交 `698332220c3f02c2c6ce5149aecbc598acfaa67c` 的独立基线再次复现；包含此环境缺少 Chromium、未下载的大型历史产物以及原有内容校验问题。全库尚非全绿，不能用局部译名测试代替该事实。

第二轮姓名、原生汉字、采访晋级、三表审计及历史文本反向检查 **66 passed**，内容姓名扫描另 **1 passed**；更广入口回归结果在本次 PR 补充。跨三表和模拟下次同步检查 **0 errors / 0 metadata warnings**。

补充核对：Alina Charaeva 的既有机器音译“恰拉耶娃”改为“查拉耶娃”。WTA 官方 2026-10-03 中网赛果确认其以 3-6、6-4、6-3 击败莱巴金娜；中新网当场报道与央视 2025-08-23 美网资格赛报道均用“查拉耶娃”。来源和英文身份已写入逐条审计。

活动内容生成器修正后另跑解说及故事渲染相关模块：**113 passed / 4 failed**，四项均属于前述已独立复现的既有渲染/样式问题，没有新增失败。
