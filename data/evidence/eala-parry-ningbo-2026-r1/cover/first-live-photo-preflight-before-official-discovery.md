## 抽帧封面渲前预检：官方图是不是已经在了

```
[渲前预检] eala-parry-ningbo-2026-r1 主角 伊埃拉（Alexandra Eala） · Ningbo · 当地 2026-10-19（Asia/Shanghai；日期来源 flashscore dc_1_2w7niT85）
    · ATP Media 照片接口：没跑——WTA 的比赛——ATP Media 只收男子
    · WTA 照片接口：0 张（筛掉 标题不是这一站 2 张、发布早于开赛 91 张）——查空（取回来了，没有对得上的）
    · WTA photo-resources：1 张
    · WTA 赛后稿头图：O4 不查——头图说明只有「姓名, 赛事 年份」（`Zheng Qinwen, US Open 2026`），不写对手、不写日期，上传时刻只有 photo-resources 路径里的日子——点名闸恒过不了（2026-09-27 评审拿掉的那一档）
    · AP 通讯社：0 张——查空（取回来了，没有对得上的）
    · 美网官方图片接口：O4 不查——封顶 1280×720（`f_` 前缀就是顶），横竖都铺不满 1080×1440——机器不写 `_low_res_why`，恒换不上
    · 当地报纸：没跑——这一站在哪个城市、当地哪份报纸没登记（`find_cover_photo._LOCAL_PAPERS`）
    · 赛事官网：没跑——这一站没有登记开着 WP REST 的官网（`cover_channels.EVENT_SITES`）
    · 中文媒体：O4 不查——公众号／当地网站的配图没有图注，时间地点人物自证不了（出处以来源自己的描述为准，不靠看图推断）——bu-majchrzak 那张要拿 dHash 对首轮七篇稿子排资料图（5beecfa6）；换图要人挑
    · 这一趟：查了 1（WTA photo-resources）；查空 2（WTA 照片接口、AP 通讯社）；没跑 3（ATP Media 照片接口、当地报纸每日图集、赛事官网 WordPress 媒体库）；O4 不查 3（WTA 赛后稿头图、美网官方图片接口、中文媒体）
       wta https://photoresources.wtatennis.com/photo-resources/2026/10/19/bb1379b4-3a13-4cb9-95eb-4097c2ee106e/Alexandra
         - 说明／文件名里没有对手「parry」，判不了是不是这一场
         - 说明／文件名里没有赛事「Ningbo」
         - 说明没写日期，元数据只有上传日子 2026-10-19、没有上传时刻——判不了是不是这场开赛之后拍的（前一晚夜场的图过了午夜才传，日子一样），不换
    → 不拦：查成的 3 档里 1 张候选没有一张全过——抽帧照发
```
