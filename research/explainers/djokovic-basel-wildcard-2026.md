# 德约巴塞尔外卡：制作与事实核验

核验日期：2026-10-29。栏目：网球有故事；题型：规则／新闻事件（other），不是人物生涯叙事。

## 一句话主线

排名决定是否达到录取条件；常规报名决定是否进入录取及递补队列；外卡解决临时参赛；种子按排种子时适用的最新排名安排。德约本次为临时A+外卡，仍列四号种子。

## 证据与边界

| 陈述 | 证据 | 边界 |
|---|---|---|
| 德约持外卡且列4号种子 | [赛事10月26日公告](https://www.swissindoorsbasel.ch/en/tournament/tournament-news/articles/2026-10-26_Djokovic-joins-the-fray-on-Wednesday.php) | 文中英文ranked 11th指向Race语境，德文明确为Race。影片不将其误写为ATP世界排名；不混用官宣时与抽签时的每周排名。 |
| 常规正赛提前28天截止，须正式报名，递补先在报名队列中进行 | [2026 ATP规则 §7.03 A.1、§7.04 A.1](https://www.itftennis.com/media/15604/atp-2026-rulebook.pdf)；[ATP第七章3月修订版](https://www.atptour.com/-/media/files/rulebook/2026/2026-rulebook-chapter-7_the-competition_31mar26.pdf) | 10月26日向前28天为9月28日；按通则推算，非声称看过球员私人报名记录；不是大满贯42天。 |
| 六王赛延期后临时谈妥巴塞尔 | [路透社10月14日延期报道](https://www.reuters.com/sports/tennis/six-kings-slam-tournament-saudi-arabia-postponed-december-2026-10-14/)；[Watson/CH Media采访赛事总监](https://www.watson.ch/sport/novak-djokovic/709075666-so-kam-es-zum-deal-zwischen-den-swiss-indoors-und-novak-djokovic) | 具体经过归属于该采访报道，不虚构德约本人直接引语。时间线标题使用10月16日“赛事官宣”，其本人官网17日跟进，不能合写为17日首次官宣。 |
| 德约参赛争取积分与都灵资格 | [球员官网10月17日](https://novakdjokovic.com/en/news/tennis/novak-is-returning-to-basel-after-15-years/)；[赛事10月16日](https://www.swissindoorsbasel.ch/en/tournament/tournament-news/articles/202610-16_Novak-Djokovic-crowns-the-Swiss-Indoors.php) | 不承诺拿到某轮积分就必进总决赛，不猜出场费。 |
| 本次为额外A+外卡，不占本土三张 | 上述赛事总监采访；[Blick对管理方的10月16日报道](https://www.blick.ch/sport/tennis/tennis-hammer-novak-djokovic-kommt-nach-basel/q0jeqjm)；ATP §7.12 A.2 | 不将“绝对巨星”当成规则的完整资格定义，不说任意当前前30自动能用。 |
| 本土三张正赛外卡给瓦林卡、基姆、施特里克 | [赛事10月19日名单](https://www.swissindoorsbasel.ch/en/tournament/tournament-news/articles/202610-19_Wild-Cards-fuer-die-Swiss-Indoors-Basel-2026.php) | 德约额外外卡在既定签表内，32签不变33签；未用额外卡则给下一位合资格报名球员，不能说对递补完全无影响。 |
| 外卡可以成为种子 | ATP §7.12 A.1、§7.14 A.1 | 外卡是参赛路径，种子是排名安排；不宣称外卡保证好签。 |

## 视觉方案与开工清单

- A3：本人点题的当周新闻引出报名／外卡／排种子规则。无需复制一整场比赛复盘。
- B2：封面“德约为何还要外卡？”；口播先点名问题，开头立即给出4号种子反差。
- B10：10段，从当下身份矛盾一路推进到临时加赛、本土名额、预留名额边界和种子，逐一兑现观众追问。
- 规则时间线、对照、人物图文均复用transition_cards共用动效；字体、深蓝背景、3:4、品牌片尾沿用原线。
- 图片复用现存已核实的本届10月28日首轮ATP Media/Getty原图：作为本次参赛身份解读，未冒称拍摄于10月16日签约现场。采用本条问题封面，不复用原比赛封面的标题和比分包装。
- C5适用范围为人物／关系叙事长片；此片为规则事件解说。已在对话展示逐段提纲并持续制作。
- 已执行taste_preflight --line 网球有故事（工具目前只加载reel/interview spec，按清单自查）；本线实际闸为explainer_preflight与check_polyphones。不得把工具不支持误报成内容未过审。
- 实际成片、逐屏原生画面、实际配音与发布链在完成后补记，不提前写通过。

## 原生制作入口

`src/tennislive/video/episodes/djokovic-basel-wildcard-2026.json` 为本片内容真相，沿现有packaged episode格式接入原生explainer注册表、渲染、预检、发布；没有另起平行剪辑器。
