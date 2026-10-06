# 修复生产证据与复现边界

输入 master 必须是 SHA256 `509cca3263c96588d7726604e5b44b067d803a83867018fcc31dd85558a4bdd4`、58,737,253 bytes。此证据仅复用真实锁定 master，不代表原始素材工程恢复。

`repair-scenes.json` 是实际渲染的32段最终边界，单位为原 master 正文秒，覆盖0至228.84秒；所有边界落在25fps网格。段落最初由5fps图墙及原片cut检测辅助定位，最终固化为此清单。`repair_body_replay.py` 使用相同裁切、key、叠图及编码参数，只把生产时的cut检测/近邻映射替换为读取固化清单，并加输入SHA检查，避免重新运行检测改变边界。复现时使用新工作目录，不能覆盖已冻结交付文件；已有repair-parts必须来自相同输入/几何，否则先移走再渲染。

本次环境：ffmpeg 6.1.1-3ubuntu5，Pillow 12.3.0。把上述原 master 放在脚本同目录，名为“孙心然成长历程_审片版_1080x1440.mp4”，运行repair_body_replay.py，得到repair-body-silent.mp4。裁切坐标是原片像素，bounds按(x,y,width,height)保存；宽镜头比分板分别从原生左侧区域独立回贴。所有fill均固定中心，没有人物追踪。源字幕/品牌为原生像素key叠加；源分辨率、已烧录文字和固定中心边缘损失不能凭本次修复恢复。

封面脚本make_sun_cover.py是实际制作代码，需要同目录cover/sun-usopen-trophy.jpg、cover/NotoSansCJKsc-Bold.otf及original4.jpg。官方独立摄影来源/照片SHA见review-master-manifest.json；字体为官方Noto CJK SC Bold。original4.jpg只是原片4秒画面用于复用品牌时钟，不是封面照片来源；可由原master提取，其像素复编码变化可能影响最终封面SHA。不同库、字体或encoder build也可能导致输出字节不同，不能用“复现了画面流程”宣称输出同一SHA。

最终拼装使用：封面以25fps H.264 yuv420p、CRF21、1.2秒、12800视频timebase编码为cover-silent.mp4；与repair-body-silent.mp4按顺序concat-copy；原master作为第二输入加itsoffset 1.2，映射concat视频和原master音频，两个流都copy，movflags +faststart。原、新AAC各10,728包size/hash一致，PTS舍入情况见manifest。

这里仅登记生产参数和实际抽查证据，未重新渲染已交付冻结影片。最终冻结SHA仍是`741a40cffaf08bf3d9738c321716752eb27263124fe1434a410f52d8bec5da25`。没有完成全片听核，没有升级发布通过；旧CI和这些脚本的存在均不能替代新master的原生交付校验与实际听音。
