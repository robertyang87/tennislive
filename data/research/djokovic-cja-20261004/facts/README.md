# 德约科维奇–兹维列夫，本场事实与统计核验

核验于2026-10-04。正式可用事实在 `facts.json`，两列统计在 `stats.ready.json`，完整分盘统计在 `stats-all-periods.json`。本目录没有调用DeepSeek/MiniMax；既有probe草稿含这两条通道输出，只读取其可追溯源摘录与元数据，文案不复用。

## 本场身份与赛果

用户源：https://www.youtube.com/watch?v=cjaHThpISKk 。Tennis TV官方频道，原标题 `Alexander Zverev vs Novak Djokovic BLOCKBUSTER Clash 🍿 | Beijing 2026 Match Highlights`。2026-10-04，北京中网ATP500，男单1/4决赛，硬地。源网页证据`youtube-jina.txt`、探测证据`probe.json`（319.181497秒、1920×1080、25fps）。

ATP原稿：https://www.atptour.com/en/news/zverev-djokovic-beijing-2026-sunday-qf 。`atp-report-jina.txt`保留原稿标题、正文日期October04,2026及Sunday evening。可用坐标「北京时间10月4日晚上，北京中网男单1/4决赛」。不要把Jina页头 `Published Time: Tue,23 Jun2026`当比赛日期，这是抽取的技术元数据，与正文日期冲突。

德约科维奇胜，赢家视角4-6 6-4 6-4；兹维列夫视角6-4 4-6 4-6。无抢七。2小时35分，ATP正文与Flashscore分盘59+41+55分钟一致。第二赛果交叉源 https://www.tennisexplorer.com/beijing/2026/atp-men/ （`tennisexplorer-beijing.html`1156附近）同样是QF、德约4/6/6、兹维列夫6/4/4。

场地court已补核：官方OP https://www.protennislive.com/posting/2026/747/op.pdf ，标题ORDER OF PLAY SUNDAY OCTOBER04,2026，第一列CAPITAL GROUP DIAMOND，第5场Not Before7:00PM，[1]AlexanderZVEREV(GER) vs [6]NovakDJOKOVIC(SRB)。本地证据`beijing-oop.pdf`、`beijing-oop.txt`、原生页面预览`beijing-oop.png`。可用「钻石球场」或「Capital Group Diamond」，19:00是不得早于的排期，不是实际开打。Flashscore df_hh_1的KC=1791112200=11:10UTC/19:10北京是赛程字段，不是已经确认的实际首球时间；不据此计算实际结束。官方正文的「周日晚上」足够写片头。

## 每盘进程与关键比分

依据 https://local-global.flashscore.ninja/2/x/feed/df_mh_1_Wpcpd4Ug （原始`df_mh_1.txt`）。归属a/主=兹维列夫、b/客=德约。下述局面均写为回合发生前比分；原feed行首是该局结束后的比分。feed不含每局终结分，实际局内总分=列出的条数+1。

1. 第一盘德约先发。开局八分，德约在30-40曾到局点，兹维列夫追回平分并在优势分拿到破发点，破发至1-0。此后到5-3各自保发。
2. 第一盘德约3-5发球：第九局十四分，兹维列夫在优势分拿到一个盘点，德约救下后保发至4-5。不要说兹维列夫5-4时拿到这一盘点：当时德约还在3-5发球。
3. 第一盘兹维列夫5-4发球：德约逼出15-40、30-40两个破发点，但兹维列夫连赢最后四分，6-4收下首盘。全盘兹维列夫破发1/2，德约0/2。
4. 第二盘双方一直保发。德约4-4发球的第九局，兹维列夫40-30拿到破发点；德约连赢三分保发到5-4。紧接着兹维列夫4-5发球，德约先连赢两分到0-30，15-40取得盘点兼破发点，并兑现该盘唯一一次破发机会，6-4扳平。
5. 决胜盘德约1-1发球的第三局：兹维列夫在优势分取得破发点，德约救下后保发2-1。其余八局打完到德约5-4，双方仍各守住所有发球局。
6. 决胜盘兹维列夫4-5发球：先到40-30局点，德约追回平分，在优势分取得第一个赛点；兹维列夫救下并再次拿局点，德约又追回平分、拿到第二赛点并兑现。此局十二分（原feed11条+终结分），德约6-4结束比赛。不能写「所有赛点都兑现」或「第一赛点胜」。画面中的终结击球方式须另按本场视频核，不由逐分数据猜。

德约丢掉开场第一个发球局后，其余14个发球局全部保住。兹维列夫的九个连续保发跨越首盘五局和第二盘前四局，结束于第二盘最后一局；不能说首盘九个连续保发。

## 排名、种子、H2H和纪录

https://www.tennisexplorer.com/ranking/atp-men/ 原始`tennisexplorer-rankings.html`153行注明排名日2026-09-28：兹维列夫第2/德国，德约第11/塞尔维亚。本场种子兹维列夫1、德约6，由本场赛事结果/签表交叉核。ATP原文称Zverev top seed和Top-2 win，支持世界前二身份。

ATP官方H2H本场之前德约9-5，本场之后10-5，因此是官方巡回赛第15次交手。Flashscore18场11-7混入三场表演赛：Adria Tour德约胜、World Tennis League兹维列夫胜、Boodles Challenge兹维列夫胜。详`flashscore-h2h.json`。禁止复用草稿「18次」「11-7」。

ATP本场原文：39岁的德约在北京累计32胜0负；这是公开赛年代男子单打在一个巡回赛赛事开局的最长连胜，超过纳达尔法网开局31连胜。不是「本赛季32连胜」，也不是「已赢得第七个中网冠军」。目前六冠，本场把冲击第七冠的机会保留下来。

半决赛10月5日周一，对梅德韦杰夫。ATP原文：梅德韦杰夫7-6(4) 6-3胜塞伦多洛，到本场前已经连胜七场；双方官方H2H德约10-5领先。北京赢球是德约本赛季第二次战胜世界前二，之前在澳网半决赛胜辛纳；年满39岁后战胜前3的人，在ATP排名时代（1973起）他是Rosewall、Connors之后第三人。上述支线只在需要时用，不挤压本场进程。

## 统计来源与缺口

Flashscore原始 https://local-global.flashscore.ninja/2/x/feed/df_st_1_Wpcpd4Ug ：全场17项，分盘各16项。`stats.ready.json`两列a=兹维列夫、b=德约。全场、分盘ACE/双误/一二发得分分子分母/破发点/总分/各类局数的整数和已逐项自证。全场85-95共180分，首盘35-35，次盘23-28，决胜盘27-32。按用户口味全场总分差仅可作为正文背景，不作封面钩子。第三方统计不能写「ATP官方统计」。

德约一发得分率19/25=76%、16/20=80%、18/20=90%；发球总得分23/35=66%、21/27=78%、22/28=79%。该趋势成立，但不能用它单独断言对手心理、身体衰退或某技战术因果。

官方完整统计未取得：直接ATP原稿/官网access denied，Jina官方results/rankings转到Cloudflare验证页；可达本场原稿不含技术统计整表/W/UE。仅这项是获取受阻，不代表赛事没有官方统计。

TNNS已真实执行只读工作流 https://github.com/robertyang87/tennislive/actions/runs/37209909119 ，按Zverev,Djokovic及2026-10-04认到数字id75051396、hasExtendedStats=true。但脚本硬闸发现winners分盘合计[47,29]与全场[33,42]不一致，明确输出「不要复制这些数字」，因此不得将任一组加入成片。日志`tnns-run.log`。不能写「TNNS没有W/UE」，要写「TNNS有扩展统计，但本场全场与分盘数据冲突，本次不引用」。未拿到可靠W/UE，准确留空。

Match Charting Project https://www.tennisabstract.com/charting/ 索引当前18320条，`tools/mcp_stats.py find --who Djokovic --year 2026`只返回11场，未列本场北京QF，原始结果`mcp-find.txt`。此为志愿者标注，亦不是官方统计。

## 赛后引语证据边界

既有probe-run.log（run37208304068）和pending的_tactical_research存有ATP全文读取18段后的两段摘录，其中德约原话开头：
“I had a terrible start. Two double faults at the beginning. It was quite cold and honestly, I didn’t feel warmed up, but my fault,” Djokovic said.
摘录后半说首盘中段开始找到发球和serve plus one节奏。该引语追溯到同一ATP原稿，记录sha256在既有draft中。但本次可达Jina正文仅为较早的“More to follow”版本，不含引语；如制作要把整段译成引用卡，需保留这是既有probe读到的原文摘录的事实，不声称本次直接全文复读18段或人工听审。引用旁白宜短译「开局很糟，前面两次双误。天冷，我还没热起来，这是我的问题」；不得假称来自我们听到的原声。

## 15:24UTC 制胜分/UE补核

新增ESPN比赛中心成功定位competition183465，双方statistics=[]，core statsSource=none、双方statistics端点404；比赛身份/CapitalGroupDiamond可额外交叉核，W/UE取不到。中网官方英文10月4日四强赛报728不含本场W/UE；中文当前新闻仍为10月3日回顾。官方ATP liveUI503、候选Hawkeye403、候选单场PDF404，未获得官方统计，不将候选matchID当已核实身份。完整精确URL及结果见`winners-ue-followup-sources.json`。

第二次TNNS只读刷新 https://github.com/robertyang87/tennislive/actions/runs/37212675476 在15:22:45UTC仍报告相同矛盾：本场75051396、hasExtendedStats=true，winners分盘合计[47,29]与全场[33,42]冲突。gh临时凭据过期后，已通过GitHubconnector恢复完整原始job111466853566日志并保存`tnns-refresh-run.log`。不引用任一组数值。没有对局部集锦回合计数冒充全场。
