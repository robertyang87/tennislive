# 德约科维奇—梅德韦杰夫：Winners/UE 取证

比赛：2026-10-05，中网男单半决赛。终局：德约科维奇7-5、5-3领先，梅德韦杰夫DQ。TNNS ID75051388。

正常打开TNNS比赛页面，并在同一正常浏览器会话调用公开stats API取得原始压缩响应。未绕过403或安全验证。元数据API的seo直接对应两人、日期、赛事与半决赛；match_card终局写Defaulted，比分[[7,5],[5,3]]，并与ATP官方签表及Flashscore独立终局吻合。

[原始stats API](https://api.tnnslive.com/v1/web?id=75051388&mode=match_info&submode=stats&web=true) 返回hasExtendedStats=true。直接Match与Set1/Set2组未列W/UE，但同一完整响应中的DJO by court、MED by court分别提供每名选手完整Left/Right场侧计数。统计球员身份通过元数据players.abbreviation（DJO=Novak Djokovic、MED=Daniil Medvedev）核对，而不是通过显示顺序猜测。

| 球员 | Winners左右侧 | Winners全场合计 | UE左右侧 | UE全场合计 |
|---|---:|---:|---:|---:|
| 德约科维奇 | 9+12 | 21 | 10+17 | 27 |
| 梅德韦杰夫 | 12+14 | 26 | 20+17 | 37 |

这是对全场完整场侧分区的透明求和，没有把缺失当0、分盘当全场，也没有宣称API直接列出了Match W/UE行。全场完整性另用双方各13组可加计数自证：Ace、双误、一发进球分子分母、一发得分分子分母、二发进球分子分母、二发得分分子分母、破发点救下分子分母、一发接发得分分子分母、二发接发得分分子分母、破发点兑现分子分母、发球总分分子分母、接发总分分子分母、全场得分分子分母。共26组左右相加都与同源Match值完全一致。逐项算式在winners-ue-derivation.json中。

其中德约总分左右侧45+45=90，分母80+86=166；梅总35+41=76，同样分母166。德约发球分29+25=54，梅总20+19=39；Ace3/4、双误6/3、破发点救下16/18与6/10也全部对应。本场W/UE截至取消资格时全部记录的回合口径。

TNNS梅总一发得分26/44，可由左右12/18+14/26验证，且26+13=39与全场发球得分一致；Flashscore旧值28/44与发球总39冲突，采用TNNS26/44，并保留原Flashscore响应以示差异。

文件：tnns-raw-stats.json及tnns-decoded-stats.json；tnns-raw-meta.json及tnns-decoded-meta.json；winners-ue-derivation.json。各文件SHA256记录在source-manifest.json。stats原始SHA256：1ca3e75cc804f8fb296711e3ea22d7aa7f35787dd28fe0fe1b4b9516f85a3ce3。
