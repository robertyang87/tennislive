# 上海大师赛历史专题：语音审计闭环记录

本次核查基于 PR #1197 head `8d870d2219f3cc44921e0ac3dec6b674426034c8`。Issue comments 与 review comments 均为0，没有新增实际听核证据。最新五个 check 中 `test`、`queue-contract`、`read-only-probe` 为 success，`shanghai-audio-evidence` 与 `review-render-dispatch` 为 skipped。跳过不等于语音通过。

新增提交只补了当前音源绑定、旧证据失效、公共参考生成及本地诊断执行记录；未新增已证实错读或完整实际听核通过。公共参考 run 37421031426 为24组通用字词×2take，预期标签不能视为发音认证；安全拆分实际执行且未将生产音频外传。它不关闭下面任一读音项。

## 当前绑定与失效范围

仓库 delivery.md / voice-review.md 当前对应 run 37416853309：433.4秒、1080×1440、134832565 bytes；MP4 SHA256 `95f91fcfd666a915387f572418e9b07a0e372135e28ffaff53df53e3d825fcce`；原生QC pass、完整解码0错误。后续严格原生重渲产物须按实际新文件重新记录，本文不提前认证未来视频。

46份实际MP3及46份words已保全，文本绑定46/46；46/46 MP3 SHA均与历史锁定版不同。旧13个中／高置信指定字位正确证据全部 stale / pending-current-audio；当前优先12项全部 pending。12项只是优先清单，不能写成整片仅剩12项。完整当前旁白及最终混音实际听核仍未完成。

## 最小重点听核清单

下列既有证据是历史追溯信息，音源SHA已变化，均不能直接用于当前音源通过。每项必须对当前实际MP3保留上下文听核，记录核查者、时间、实际音源SHA、字位、听到的读音及结果；听不清继续pending。没有要求用户参与审片。

|段落／目标|目标读音|已有证据与当前状态|通过标准|
|---|---|---|---|
|正文4 伊万尼塞维奇的塞|yī wàn ní **sài** wéi qí|旧 uncertain，score −0.131；当前pending|实际听到sài第四声，完整专名清晰。|
|正文11 追回来的回|zhuī **huí** lái|旧 unreliable，参考组自测失败；当前pending|实际听到huí第二声，连读自然、无吞字。|
|正文11 发球胜赛局的发|**fā qiú** shèng sài jú|旧 not_measured；当前pending|实际听到fā第一声，完整术语清楚。|
|正文11 冠军只差两分的差|guàn jūn zhǐ **chà** liǎng fēn|旧 uncertain，score −0.195；当前pending|实际听到chà第四声，允许规范三声变调。|
|正文16 准备发球的发|zhǔn bèi **fā qiú**|旧 not_measured；当前pending|独立听到本处fā第一声；正文11不能替代。|
|正文35 第一处重新的重|cái **chóng xīn** huí dào sài lì|旧 unreliable，参考组自测失败；当前pending|独立听到第一处chóng第二声；第二处不能替代。|
|正文36 单打的单|**dān dǎ**|旧 correct/low，score 0.242；当前pending|实际听到dān第一声，完整词清楚；low不提升pass。|
|正文43 瓦舍罗的舍|wǎ **shè** luó|旧 support_only；当前pending|独立听到shè第四声，完整专名及排名数字清晰。|
|正文44 瓦舍罗的舍|wǎ **shè** luó|另一音源旧 support_only；当前pending|独立听到本处shè第四声；正文43不能替代。|
|固定片尾 第一处时差的差|shí **chā**|旧 unreliable，参考自测失败；当前pending|实际听到第一处chā第一声。|
|固定片尾 第二处时差的差|shí **chā** guī wǒ|旧 unreliable，正确倾向不能通过；当前pending|独立听到第二处chā第一声。|
|固定片尾 好球的好|**hǎo qiú** guī nǐ|旧 uncertain，score 0.114；当前pending|实际听到hǎo第三声，允许自然半三声，口号自然清楚。|

13个已失效字位为：正文35第二处重新／48重逢／5追回的追／16五比四的比／9纳尔班迪安的纳／19只差的差／36延长的长／11追回的追、冠军的冠、纳尔班迪安的纳／封面传奇的传、奇及几代的几。旧结论只对旧MP3指定字位生效，本次均须补证，不由优先12项覆盖。详见 [冻结清单](voice-checklist-current.md)。

## 仓库能关闭什么、必须实际听什么

仓库及真实产物可以关闭正式文本、实际MP3 SHA与渲染输入绑定、words完整性、字幕原文映射、素材来源、片长尺寸、原生QC和解码等技术要求。静态字典、多音字词表、ASR汉字、WordBoundary均不证明实际声调。

上述12项、旧13个失效字位、其余专名／数字／ATP字母读法及整片停顿和混音必须针对当前实际声音复核。uncertain、unreliable、support_only、correct/low及未测结果不能记pass；公共参考近似也不能代替完整成片实际听核。没有虚构人工听核，完整听核尚未完成。

Edge免费接口当前不支持自定义SSML phoneme，只支持声线及prosody控制；仓库 `pronounce.py` 经 `speakable()` 在喂TTS的文字副本进行限定上下文、字数1:1同音换写，屏幕文字保持原文。新增纠音须有当前原句真实错读及修复后读对的可靠证据；目前没有已证实错读，不猜改。现有声线为 `zh-CN-YunjianNeural`，重合成后须重新保全SHA及当前字位证据。

## draft → ready → 发布的剩余条件

1. 制作侧核清当前全部待核字位，包括优先12项和失效13项；未确认仍pending。若证实错读，按真实证据修复，重合成并重新绑定，不沿用旧SHA通过。
2. 严格按“网球有故事”原生制作规则重渲后的实际最终视频，完成完整语音／混音听核、素材视觉及字幕音轨检查；重点8段包不能替代全片。
3. 将真实核查记录、原生QC、最终MP4及全部音源SHA绑定，并完成最新head必需CI与原生发布包校验，才可由draft进入ready。技术CI成功不代替语音验收。
4. 用户已授权真正质检通过后由制作侧直接推送微信，无需用户审片或再次确认；目前语音条件未满足，仍draft／审片未发布。真正满足上述条件后，按实际发送结果记录发布状态。本文未发送微信。

参考：[当前语音记录](voice-review.md)、[交付记录](delivery.md)、[公共参考执行摘要](voice-evidence/public-reference-37421031426/execution-summary.md)、[Edge官方说明](https://github.com/rany2/edge-tts#custom-ssml)。
