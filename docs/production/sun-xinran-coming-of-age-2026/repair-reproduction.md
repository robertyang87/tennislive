# 修复生产证据与复现边界

当前交付为 v2，SHA256 `861eae3d2cf1a8b4f6932b258e00d54308abec3eeafc7ada5599c0d829ce1272`、85,039,635 bytes；旧 v1 保留且未改。以下基础流程记录 v1 的原始画布修复，后接 v2 修订。

输入 master 必须是 SHA256 `509cca3263c96588d7726604e5b44b067d803a83867018fcc31dd85558a4bdd4`、58,737,253 bytes。此证据仅复用真实锁定 master，不代表原始素材工程恢复。

`repair-scenes.json` 是实际渲染的32段最终边界，单位为原 master 正文秒，覆盖0至228.84秒；所有边界落在25fps网格。段落最初由5fps图墙及原片cut检测辅助定位，最终固化为此清单。`repair_body_replay.py` 使用相同裁切、key、叠图及编码参数，只把生产时的cut检测/近邻映射替换为读取固化清单，并加输入SHA检查，避免重新运行检测改变边界。复现时使用新工作目录，不能覆盖已冻结交付文件；已有repair-parts必须来自相同输入/几何，否则先移走再渲染。

本次环境：ffmpeg 6.1.1-3ubuntu5，Pillow 12.3.0。把上述原 master 放在脚本同目录，名为“孙心然成长历程_审片版_1080x1440.mp4”，运行repair_body_replay.py，得到repair-body-silent.mp4。裁切坐标是原片像素，bounds按(x,y,width,height)保存；宽镜头比分板分别从原生左侧区域独立回贴。所有fill均固定中心，没有人物追踪。源字幕/品牌为原生像素key叠加；源分辨率、已烧录文字和固定中心边缘损失不能凭本次修复恢复。

封面脚本make_sun_cover.py是实际制作代码，需要同目录cover/sun-usopen-trophy.jpg、cover/NotoSansCJKsc-Bold.otf及original4.jpg。官方独立摄影来源/照片SHA见review-master-manifest.json；字体为官方Noto CJK SC Bold。original4.jpg只是原片4秒画面用于复用品牌时钟，不是封面照片来源；可由原master提取，其像素复编码变化可能影响最终封面SHA。不同库、字体或encoder build也可能导致输出字节不同，不能用“复现了画面流程”宣称输出同一SHA。

最终拼装使用：封面以25fps H.264 yuv420p、CRF21、1.2秒、12800视频timebase编码为cover-silent.mp4；与repair-body-silent.mp4按顺序concat-copy；原master作为第二输入加itsoffset 1.2，映射concat视频和原master音频，两个流都copy，movflags +faststart。原、新AAC各10,728包size/hash一致，PTS舍入情况见manifest。

这里仅登记生产参数和实际抽查证据，未重新渲染已交付冻结影片。v1冻结SHA是`741a40cffaf08bf3d9738c321716752eb27263124fe1434a410f52d8bec5da25`。没有完成全片听核，没有升级发布通过；旧CI和这些脚本的存在均不能替代新master的原生交付校验与实际听音。

## v2：去掉额外贴比分板并柔化接缝

先由原master生成基础repair-parts（repair_body_replay.py）；再运行repair_no_pasted_score_v2.py，wide的10段不再split比分层和overlay，非wide段复用基础编码，输出repair-parts-no-pasted-score-v2。最后运行soften_transitions_v2.py，cover-silent.mp4和32段依原长逐段处理：接缝前0.12秒对下一段首帧从0到0.5透明权重融合，接缝后0.12秒对上一段尾帧从0.5降到0；相邻端帧clone形成0.24秒溶解，未引入黑帧、未删时间。

33段长度逐项检查并concat-copy，原master音轨仍itsoffset1.2后packet-copy。输出独立文件“孙心然成长历程_全屏修复审片版_v2_柔和转场去贴比分_1080x1440.mp4”；原v1不覆盖。v2全解码exit0、video230.04秒、container230.041333秒、10728音包size/hash全部一致；32段中点图墙、7个接缝各6帧及最终封面首帧已实际视觉查看。内部源镜头原有切换没有全体重新剪辑，这不是完整连续人工审片或真实完整听核通过。
