# 成片与本次修改

用户最新要求：多视频、少字卡；不显示左下角来源；只讲LED事件；传达遗憾与未来期待。

最终本地成片 144.04 秒，1080×1440、25fps，67,774,002 bytes，SHA256 `0f39ec038475310d0d2b4ebbd0d7d78deb19ecac9ad719b9f31b310f79b6ee62`。正文136.251秒，真实源视频92.290秒，约67.74%；4个短证据页共43.961秒。片头与片尾不算视频占比。仅保留比分前后、广告规则、孙本人解释四处图卡。

采用官方WTA高清源、Tennis Channel罗马原片、正规转播平台Sky Sport自有公开高清。Sky情绪段是首盘结束后擦脸，不剪成LED事故当下反应；德文原声保留17词完整句并准确译成中文，罗马裁判21词，高芙10词。每来源摘录低于25词。普通回合仅承载规则说明，短标识“本场其他回合”可见；未拿它们冒充原分/重打。

全片 `check_reel_landed.py` 0项不合格。所有源窗口实际SHA绑定，10条外语字幕cue实际ASS匹配；安静窗口保留原生球场音并有独立ASR交叉证据。没有用mute推断解说不存在，没有虚报人工听审。56条烧录字幕与人物、图卡安全区经40张真帧独立检查。相关目标测试86 passed，旁白逐段实测均装得下，taste/dry-run通过。

来源文字按用户要求从左下角移除；研究来源、PDF条款及音频证据保留在仓库。研究非官方185秒事故录像与慢放用于核高芙回合末已抬手，不把“丢分后才首次申诉”当事实。原始事故官方发布完整片尚未取得；材料缺口仅留内部。

GitHub正式云端流程现已完成：`match-reel` run [37372143319](https://github.com/robertyang87/tennislive/actions/runs/37372143319) success，使用实际官方归档源并完成渲染、最终QC、Release上传和23个产物文件提交。正式Release成片144.04秒、1080×1440、25fps、67,677,730bytes，SHA256 `5a74a1bc4d0b930399c2fc1d3954697dd02fa8db4afbad361575bc899e516944`。正式ASS与本地已审版本逐字节一致；所有选段、源SHA、旁白时长和字幕时轴一致。海报JPEG与编码环境造成正式成片字节不同，因此另行下载正式文件做质检，不用本地旧hash代替。

正式成片URL：https://github.com/robertyang87/tennislive/releases/download/reel-sun-gauff-led-replay-story-2026/sun-gauff-led-replay-story-2026.mp4

根制作方把正式metadata放在实际下载成片旁，重新运行 `check_reel_landed.py`，0项不合格。独立质检重新抽查37张正式云片真帧，覆盖16段、封面片尾及10条原声双语cue，结论通过；见 [cloud-final-independent-qc.md](cloud-final-independent-qc.md)。方法与未做人工听审的边界保持真实。

正式render之前当前496树的全量测试：5677 passed、234 skipped、0 failed，488.81秒。234正常跳过项包含本机未安装的人脸模型；没有修改测试或闸门消掉失败。正式云runner有人脸模型，原流程检查正常完成。

正式产物提交088f之后，两趟PR检查原本提示“This workflow is awaiting approval from a maintainer in #1191”，jobs为0。确认其只新增正式产物、不修改workflow后，正常通过Actions审批API批准运行，没有改安全规则。正式云片已公开存在；PR合并、Pages复制页及微信推送继续按当前头检查和发布账本完成。正式发出与否以持久账本的sent状态和PushPlus流水号为准，不把工作流已启动算成已发送。
