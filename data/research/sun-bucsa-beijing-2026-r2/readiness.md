# 孙心然–布克沙制作就绪记录

2026-10-03官方第二轮，6–4、7–5。本文片原名以中网官方为孙心然。来源WTA4586047，原720p206.358333秒，SHA dd3a0d6f24eea364aa7038b7f3adc4441087273ba56c348f0c2461c2feb16c9d。

13段119.7秒制作稿，官方同场央视实拍封面、原生九行统计卡、全部保留原声窗口的真实ASR证据及6条双语字幕已经准备。统计核心WTA，W/UE完整TNNSMatch。实际ASR cross_checked，没有声称人工听完。

原生production_preflight文案、WUE、实际源字节绑定的foreground_audio_gate通过；完整probe1032帧、10张墙，静音区间空。原生dryrun造型、源尾范围和比分回贴问题已修复，唯一硬项为720低于1080：正在等待账号所有者的新片源画质选择。未添加低清白名单，未正式渲染、质检或微信推送。

本地原生check_narration真实尝试：Microsoft Edge语音端点连接失败，无法测得时长。下一步直接原生production render里测真TTS，不启动独立narration runner。

如用户确认720：按精确URL登记授权；将pending稿提升正式路径；原生下载必须选择已核progressive字节，不能HLS重封装后改SHA假装旧审听版本。完整源声末词205.86结束，选段末206.15+0.18溶解=206.33低于206.358。实际转场、字幕、混音、MP4全解码及SHA由成片质检证明。

原片位于/workspace/sun-bucsa-research/sun-bucsa-wta-original-720p.mp4，不进git。未使用DeepSeek、MiniMax。无临时workflow helper，没有pushplus调用。

## 最新封面选择

2026-10-03 用户发来正手追球照片并要求替换抛球照。画面精确对应央视本场图集第3张；采用2048×1367原图，SHA256 `1978ef2aa3d007474d557115a561767222a9b52402a20886e3cdfbdceac5b7b9`。已用原生render_poster实际输出1080×1440预览并查看，脸部、球拍与球可见，标题不遮脸，双脚位于比分板覆盖区域。正式视频尚未渲染，720p片源确认仍待回复。
