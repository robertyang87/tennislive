# 伊埃拉—施晗，武汉2026首轮事实包

Winner-first：施晗4-6 6-3 6-3伊埃拉。WTA1075/2026 LS060；Flashscore GUnW9n8D。官方排名日2026-10-12：伊埃拉19/13号种子，施晗217/资格赛。第一分北京时间10月12日21:06:28，旁白只用“晚上”。官方2:27:58，封面按原生分钟截断2:27（不四舍五入，精确官方秒仍保留）。

剧情骨架见 `facts/facts-packet.json`，逐局源比分见 `facts/raw/wta-games-derived.json`。

- 首盘前八局全保发；伊埃拉4-4救2BP保5-4，再在施晗发球局从0-40连拿5分破发6-4。对手三个是局点，不能写盘点。
- 第二盘前六局全保发，3-3后施晗破发—保发—破发连赢3局，6-3扳平。
- 决胜盘首局施晗救2BP保发；次局第三个BP破伊埃拉，再保发3-0。跨盘连赢六局，三次破发三次保发。
- 伊埃拉0-3再救BP保1-3，之后继续保发追2-4、3-5，但施晗最后三发球局同样全保，第一赛点收比赛。
- 施晗资格赛胜斯特恩斯2-6 7-5 6-4、拉希莫娃7-6(2)6-1，官方视频说明她来武汉前未胜Top100，如今三天三胜Top100。该历史说法由WTA发表，不声称穷尽职业比赛自行验全史。

全场Stats.a必须是伊埃拉，Stats.b施晗：制胜分20/31，UE37/33；官方其他共享字段已与Flashscore交叉核。WTA接口没有W/UE，所以这两项归Flashscore。

**数据限制**：官方PBP188分的pointWinner计87/101，官方全场stats与Flashscore同为88/100；7处AD→deuce pointWinner字段与比分变化矛盾。逐局终态和破发点状态全核对，不用错误pointWinner来声称最长连分或总分。

**素材身份**：用户精确ID T9TfTnVgHNY，runner下载题名与比赛一致，306.851701秒、1920×1080/25fps、45935631字节、SHA256 daa20031f91396c2806716021e43fd913cd0e9a17f057e149e7b82f62710b6f8。noembed relay同ID同题名author WTA/@WTA，加WTA官网footer自链提供官方帐号佐证；未虚称直接YT channel-ID/发布时间验证。WTA官方同场Brightcove6406703039112网页标364秒，是不同长度的备选素材，发表2026-10-12T15:58Z不等于YouTube发表。

技术球路、人物动作、关键分画面完整覆盖仍由actual source视觉/原声角色核，不从逐分数据编。

补充场地：10/12官方OOP历史daysection中，伊埃拉vs施晗位于“Dongfeng Voyah Center Court”（中央球场），下一段才是“Court 1”。API CourtID=1是内部ID，不等同打印的Court1。raw与切片位置见court-name-extraction.json。
