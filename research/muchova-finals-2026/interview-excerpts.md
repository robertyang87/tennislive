# 穆霍娃2026：赛后采访的经典段落候选

用户追加：**“最好也有一些赛后采访”“节选经典段落”**。本片是人物故事，选2–3段能推进叙事、表达真实情绪的本人原话；不必每站配一段，不用感谢名单填时长。

当前已取得三条本人采访/专题的实际视频：巴特洪堡Winner’s Feature、温网半决赛场上采访、温网决赛本人亚军发言。两条温网采访已通过仓库既有 `download-video.yml` 保存为源片Release；本任务仅准备素材，未渲染、未推送。

## 优先节选

| 优先 | 内容及作用 | 官方原片 | 原片候选窗口 | 当前证据与边界 |
| --- | --- | --- | --- | --- |
| 1 | 温网半决赛赢下高芙后，她仍在发抖、甚至不知道自己在说什么；现场氛围难以形容。放完整赛点和拥抱之后，给她的停顿、笑声留空间。 | [半决赛本人采访](https://www.youtube.com/watch?v=5OOvRkrKDF4) | 47.7–64.1秒；只是候选，最终以句头句尾为准 | 实际视频153.414秒、1920×1080、有音轨；30秒实帧为穆霍娃本人持温网话筒。small.en全片及medium.en目标窗口均完成；两模型支持她实际说kind of shaking和trying to sink it in。不能照标题/新闻文字删改口语。 |
| 2 | 巴特洪堡夺冠后谈“这些好比赛给了我信心”，接温网只隔两天的行程。用本人声音自然连接草地冠军与温网决赛。 | [WTA Winner’s Feature](https://www.wtatennis.com/videos/4528760/this-is-how-i-won-bad-homburg-karolina-muchova-on-a-memorable-week) | 140.8–164.8秒；可以只选141–145.9秒这一完整句 | WTA媒体ID6399808507112；实际文件165.28秒、1920×1080、有音轨。small.en整片及medium.en三个目标窗口转写均完成，核心句义一致；正式剪点和最终字幕仍待核。专题是比赛回顾加本人采访声音，不冒称场上颁奖现场。 |
| 3（短备选） | 她谈“始终努力在场上打得自在”，给多场比赛串联一个本人视角。 | 同上 | 30.0–37.7秒 | small.en与medium.en核心句义一致。若叙事只需一句，可选30.04–33.26秒的完整句；不把后一句劈开。 |

可用译文候选：

- SF：`I don't even know what I'm saying.` → “我甚至不知道自己在说什么了。”两模型均支持随后她说自己仍有些发抖、正在消化这一刻。可选49.25–63.7秒这一完整情绪段，或53.94–61.4秒的较短完整句；最终字幕英文拼写和边界仍验实际成片。
- 草地信心：`Definitely gives me some confidence to have these good matches under the belt.` → “这些高质量的比赛，确实给了我一些信心。”
- 自在感：`I just try to always, you know, feel free on the court.` → “我只是一直努力，让自己在场上打得自在。”

这些是实际ASR支持的编辑候选，**不是已经逐词放行的最终字幕**。完整英文转写、实际音频SHA和候选句边界保留在[evidence](evidence)与[结构化候选](interview-candidates.json)。未声称真人听核。

## 温网亚军：失利中的幽默与尊重（备选）

[本人亚军发言](https://www.youtube.com/watch?v=3I1Dd6XTDNI)，实际251.495秒、1920×1080、有音轨。原片52.2–76.6秒包括她说很难找到语言，称琳达是“前朋友”，观众笑声，然后澄清是开玩笑。若用这段，必须保留玩笑语境；不能只摘“前朋友”制造不和，也不能把诺斯科娃的冠军致辞当她的。

本片更需要情绪峰值和时间线衔接，这一段优先级低于前两项。温网官网还报道她希望继续战斗并再回来争奖杯；small.en与medium.en均在原片231–242.7秒定位此段，但235.18–235.6秒两模型都写成won，而官网发表的是want；不能把“双模型一致”当事实正确。该词和句末中断仍待第三证据或真实听核，整句暂不列为可直接上片。她确实说“I’ll be fighting, I’ll be fighting more”，但也不为绕开争议把句子强拆成碎片。

官方语境证据：[Wimbledon决赛本人反应报道](https://www.wimbledon.com/en_GB/news/wimbledon_2026_karolina_muchova_final_)；[WTA两位捷克球员发言报道](https://www.wtatennis.com/news/4533986/muchova-and-noskova-capture-hearts-with-humor-and-humanity)。WTA正文嵌入同段[Wimbledon官方X短片](https://x.com/Wimbledon/status/2076000535295963181)；官方syndication数据证实发布者Wimbledon、片长36.2秒、有MP4。另有[亲友感谢短片](https://x.com/Wimbledon/status/2076001520638738920)，34.84秒，内容完整但不列为本片首选。

## 多哈：文字已核实，采访视频尚未取得

[WTA夺冠赛报](https://www.wtatennis.com/news/4450588/muchova-reigns-in-doha-for-first-wta-1000-first-title-since-2019)记载本人在颁奖时谈到久违的胜利感：

`It's been a while since I won a tournament. So it's just nice to get that feeling again.`

可译为“我已经很久没有赢过一站比赛了。能再次感受到这一切，真的很好。”这句贴题，但目前仅核到官方文字，**没有取得对应官方发言视频，不能声称已拥有这段原声，也不合成声音冒充她本人。** 可先用旁白转述，接已取得的真实冠军点和捧杯。

已核的WTA多哈X帖：[11.354秒捧杯](https://x.com/WTA/status/2022719051408052453)、[23.466秒冠军瞬间竖片](https://x.com/WTA/status/2022724749906895281)，两者均不是采访。

## 下载与检查记录

- 温网SF： [下载run39631323263](https://github.com/robertyang87/tennislive/actions/runs/39631323263) · [源片归档](https://github.com/robertyang87/tennislive/releases/download/source-5OOvRkrKDF4/5OOvRkrKDF4.mp4)。
- 温网亚军：[下载run39631329468](https://github.com/robertyang87/tennislive/actions/runs/39631329468) · [源片归档](https://github.com/robertyang87/tennislive/releases/download/source-3I1Dd6XTDNI/3I1Dd6XTDNI.mp4)。
- 本地 `sources/videos` 按任务忽略规则保存，不把大视频提交Git。
- 双模型ASR采用实际MP4字节，ffmpeg解为16000Hz单声道float32，再用faster-whisper int8。环境现有PyAV不接受`metadata_errors`参数，因此仅在本次诊断脚本里用ffmpeg解码；未修改仓库产线代码。转写证据明记此方法，不把它写成原生工具完整成功。
- 渲前仍需对保留的每一整句做双模型交叉核对、争议词复核、说话人与画面一致、固定人物中心裁切和实际字幕预览。YouTube频道元数据可进一步落档；当前有同日真实iframe、归档标题、官方报道/官方X同段及实际本人画面交叉佐证。

## 本轮结论

优先的两段已完成实际视频下载、基础探测、本人实帧核对及small.en/medium.en交叉转写：**巴特洪堡带着信心去温网**与**温网半决赛后仍在发抖**。可据此做提纲选择，正式上片前仍核最终字幕、完整句边界、固定人物裁切和成片混音。

已读完温网亚军视频转写：她表达当时的失望、亲友支持、继续争取奖杯；未在这条发言里诊断伤病。7月发言不能作为之后几个月未拿大分的原因证据。
