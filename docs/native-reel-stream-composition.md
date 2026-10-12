# 原生赛场之上：保留音轨、修复画面

`tools/compose_native_reel.py`适用于同一期已有两个真实GitHub原生渲染结果、需要组合其中画面与音轨的情况。它复制压缩流，不重新配音或编码；原声响度不随字幕修复改变。普通新片继续使用`match-reel`，不要把它当作任意本地电影导入器。

输入必须是同production分支、同slug的已结束`match-reel.yml`手动运行。工具从GitHub核对原始head、spec、唯一artifact、完整素材及电影SHA，要求当前画面配方除`bed`外完全等于画面输入，当前声音配方完全等于声音输入；字幕位置是声音输入允许的唯一视觉差异。声音参数、旁白、源时间窗、卡片、取景和时间轴变化都会拒绝。

在production分支新增或修改唯一请求文件，例如：

```text
data/reel-compositions/paolini-bejlek-wuhan-2026-r1/request.json
```

```json
{
  "slug": "paolini-bejlek-wuhan-2026-r1",
  "video_run": 38307920960,
  "audio_run": 38305296490
}
```

推送后`compose-native-reel.yml`自动运行；请求路径须与slug相等，字段必须恰好为上述三个。同一次push不能修改两份合成请求。工作流在默认分支登记后也支持手动dispatch相同三个参数。不要在旧请求不变时期待新的合成；应检查实际新run。

缓存只有在MP3字节和WordBoundary内容均与原音频artifact相同才可使用。失败运行没有缓存时，工具可忠实包装该真实原生artifact的MP3与标记，记录`native_run_artifact_pair_repack`及原始run/head/artifact，不把新包装冒称原缓存。还须核验完整旁白与真实原AAC匹配；缺词、错误配对或不匹配直接失败。

合成后逐包比较视频和音频的内容、PTS、DTS与时长，重新生成原生输入清单和声音绑定，重新跑全片`check_reel_landed`。新QC通过后才替换Release，完整GET校验远端SHA与字节，再提交元数据。容器字节SHA可能随ffmpeg版本不同，必须使用实际新片SHA；不能复制旧QC或假定本地SHA等于云端SHA。

这个工作流不合并、不发微信。负责人核验实际新片、原生QC和当前head完整CI后再合并，由既有自动推送链路发送并核验真实回执。端到端起表与回执记录见[微信交付计时](reel-delivery-sla.md)。
