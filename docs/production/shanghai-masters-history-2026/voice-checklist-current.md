# 上海大师赛历史专题：内部配音质检清单

## 当前重渲版本与证据状态

- 本记录为内部质检清单；无需用户参与审片。没有声称完整实际听核完成。
- 本次产物：run 37416853309；7分13.4秒（433.4秒）；1080×1440；134832565字节。
- 最终 MP4 SHA-256：`95f91fcfd666a915387f572418e9b07a0e372135e28ffaff53df53e3d825fcce`。
- 原生成片 QC 通过；完整解码错误数为 0。技术通过不代表语音发布通过。
- 本次实际 46 份 MP3 与 46 份 words 已保全，文本绑定 46/46 完整。46/46 MP3 SHA 均与旧锁定版不同。**旧 13 个中／高置信指定字位的正确证据全部失效，不能继承到本次音源。**
- 上表 12 点只是优先清单，不能表述为新版本仅剩 12 项。下面 13 个旧正确字位也全部须对当前音源补证；完整音轨仍须实际复核。
- 截至本轮复核，PR #1197 issue comments 与 review comments 均为 0，没有新增人工语音证据。
- 当前待听核，仍为 draft／审片版，未发布、未推送微信。


## 附录：旧 13 个指定字位全部失效

| 段落 | 目标字位 | 旧声学证据 | 本次状态 |
|---|---|---|---|
| 35 | 重新 第2处「重」 | correct/medium | stale / pending-current-audio；MP3 SHA 已变 |
| 48 | 重逢 第1处「重」 | correct/medium | stale / pending-current-audio；MP3 SHA 已变 |
| 5 | 追回 第1处「追」 | correct/medium | stale / pending-current-audio；MP3 SHA 已变 |
| 16 | 五比四 第1处「比」 | correct/high | stale / pending-current-audio；MP3 SHA 已变 |
| 9 | 纳尔班迪安 第1处「纳」 | correct/medium | stale / pending-current-audio；MP3 SHA 已变 |
| 19 | 只差 第1处「差」 | correct/medium | stale / pending-current-audio；MP3 SHA 已变 |
| 36 | 延长 第1处「长」 | correct/high | stale / pending-current-audio；MP3 SHA 已变 |
| 11 | 追回 第1处「追」 | correct/medium | stale / pending-current-audio；MP3 SHA 已变 |
| 11 | 冠军 第1处「冠」 | correct/medium | stale / pending-current-audio；MP3 SHA 已变 |
| 11 | 纳尔班迪安 第1处「纳」 | correct/high | stale / pending-current-audio；MP3 SHA 已变 |
| cover | 传奇 第1处「传」 | correct/medium | stale / pending-current-audio；MP3 SHA 已变 |
| cover | 传奇 第1处「奇」 | correct/medium | stale / pending-current-audio；MP3 SHA 已变 |
| cover | 几代 第1处「几」 | correct/high | stale / pending-current-audio；MP3 SHA 已变 |

旧字位正确只对旧实际MP3生效，不扩展成完整词／句子或发布pass。新的机器补测结论如有，将单独附录；上述未通过状态不由研究计划自动改变。


这份清单聚焦 8 段原音里的 12 个待核点。它不是完整配音听核记录，也不代表可发布。**当前没有已证实错读；uncertain、unreliable、support_only 和 correct/low 均不能记为 pass。**

## 逐项听核

按整段音频播放，保留前后语境。字位秒数只用于定位，不证明声调。每项须记录听核者、实际听核时间、音频 SHA-256、听到的读音与结论。听不清继续待核。

| 项 | 段落与语境 | 完整目标读音 | 已有证据（上一锁定版） | 通过标准 |
|---|---|---|---|---|
| 1 | 正文 4：「伊万尼塞维奇」 | yī wàn ní **sài** wéi qí | 塞：uncertain，score −0.131 | 实听确认塞为 sài（第四声），完整人名音节清晰；不能仅凭词边界文字通过。 |
| 2 | 正文 11：「费德勒又追回来」 | zhuī **huí** lái | 回：unreliable，参考组自测失败 | 实听确认回为 huí（第二声），完整词连读自然、无吞字。 |
| 3 | 正文 11：「自己的发球胜赛局」 | **fā qiú** shèng sài jú | fā 缺可靠独立单音参考，not_measured | 实听确认发为 fā（第一声），发球胜赛局完整清楚；保留规范术语。 |
| 4 | 正文 11：「冠军只差两分」 | guàn jūn zhǐ **chà** liǎng fēn | 差：uncertain，score −0.195 | 实听确认差为 chà（第四声），允许自然三声变调；不借已退役旧短句结果通过。 |
| 5 | 正文 16：「准备发球结束比赛」 | zhǔn bèi **fā qiú** jié shù bǐ sài | fā 缺可靠独立单音参考，not_measured | 单独实听确认本段发为 fā（第一声）；正文 11 正确不能代替本段。 |
| 6 | 正文 35：第一处「才重新回到赛历」 | cái **chóng xīn** huí dào sài lì | 重：unreliable，参考组自测失败 | 实听确认第一处重为 chóng（第二声）；第二处正确不能代替第一处。 |
| 7 | 正文 36：「回归后的单打签表」 | huí guī hòu de **dān dǎ** qiān biǎo | 单：correct/low，score 0.242；不能作为发布通过 | 实听确认单为 dān（第一声），单打完整清楚；low 不能升级为 pass。 |
| 8 | 正文 43：「排名第二百零四的瓦舍罗」 | wǎ **shè** luó | 舍：support_only；单侧强支持，没有可靠双侧自测 | 实听确认舍为 shè（第四声），完整人名清楚；同时核排名数字的连读。 |
| 9 | 正文 44：「瓦舍罗成为……」 | wǎ **shè** luó | 另一份音频的 support_only | 单独实听确认本处舍为 shè（第四声）；正文 43 正确不能代替本处。 |
| 10 | 固定片尾：第一处「关注网球时差」 | guān zhù wǎng qiú **shí chā** | 差：unreliable，参考组自测失败 | 实听确认第一处时差的差为 chā（第一声）；固定口号仍须核实际音源。 |
| 11 | 固定片尾：第二处「时差归我」 | **shí chā** guī wǒ | 差：unreliable；原始倾向正确但自测失败 | 单独实听确认第二处差为 chā（第一声）；不凭倾向 score 通过。 |
| 12 | 固定片尾：「好球归你」 | **hǎo qiú** guī nǐ | 好：uncertain，score 0.114 | 实听确认好为 hǎo（第三声），允许自然半三声；完整口号清楚自然。 |

## 哪些能够用仓库证据关闭

仓库记录可以证明正式旁白文本、真实音源 SHA、实际音频与渲染输入的绑定，以及音频元数据和词边界记录是否完整。画面铺满、字幕和原声音轨绑定、片长、峰值和素材来源等技术／素材要求，按对应真实产物检查关闭。

同一实际 MP3 与完整文字均未变化时，已有中／高置信声学证据只适用于其指定字位，不扩展为整句、完整专名、数字或全片通过。上一锁定版的 13 项指定字位正确，不关闭上述 12 项。重渲只要 SHA 或文字改变，旧字位定位和旧声学结论都不能用于新音源。

**本交付上述 12 项全部为 pending，必须针对当前实际音源实际听核。仓库文字、ASR、uncertain、unreliable、support_only 或 low 均不能关闭它们。未来即使补强机器声学证据，也不能代替完整成片实际听核；本交付没有宣称听核完成。**

## 从 draft 到可发布的剩余条件

1. 将这 12 个目标逐项实际核清，记录听核者、时间、实际 MP3 SHA、字位位置、听到的读音和结论；任何未确认项仍为 pending。
2. 完整播放最终成片，核所有专名、数字、ATP 字母读法、断句停顿和最终混音；8 段重点听核不能代替全片。
3. 将真实结果绑定最终 MP4 SHA，并更新交付状态；若改配音，须复核新音源、重新绑定并重渲相关版本。
4. 完成当前 PR 必需的 CI 与真实成片质检；被跳过的语音任务不是通过。
