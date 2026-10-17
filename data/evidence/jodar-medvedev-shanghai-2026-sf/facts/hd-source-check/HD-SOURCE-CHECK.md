# 同场1080来源补查

**找到TennisTV官方免费1080短集锦，156秒。**

[官方免费页面](https://www.tennistv.com/videos/4593566/shanghai-2026-sf-jodar-medvedev-short-highlights)明确`entitlement:free`和`ATP_MATCH:5014_2026_MS003`，球员J0DZ/MM58。匿名正常entitlement及StreamAMG公开播放API均200；实际HLS主清单有1920×1080两档。

`tennistv-free-source.json`是元数据与媒体URL/全部HLS档位；`tennistv-free-playback.json`与`tennistv-free-hls-master.m3u8`保存原件；`tennistv-free-playback-requests.json`记录请求状态和时间。动态播放URL会过期，正式制作在下载时重新调用既有`official.media_url`即可。没有下载完整影片。

## 较长版本与限制

- TennisTV赛事页列出的同场10分02秒常规集锦、20分02秒extended、全场replay均明确`premium`；只读取公开卡片，没有请求其entitlement或媒体。
- 当前免费short156秒，比原134秒缓存长22秒，仍短于官网Brightcove303秒版。关键画面须源代理看片核实，不能从时长推定全部覆盖。
- 已知赛事官网303秒官方Brightcove版最高720p。
- ATP本场新闻正常请求403，停止，没有换入口绕过。
- 本次仅在上述官方渠道正常返回的页面中未找到约5分钟的免费1080长版，不据此声称全网没有。未请求受阻YouTube。

生产仍由主线程决定：免费156秒1080版，或经用户明确同意的303秒720版。
