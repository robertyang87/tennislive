# 《电子司线，真的准吗？》原文摘录

2026-10-30 在会话里直接下载原文、逐字摘录。只收片子里要用的句子。PDF 本身不进仓库，链接在每节开头。

## 1. ITF《Electronic Line-Calling Systems: Evaluation Procedures》Revision 28.1（2026-01）

https://www.itftennis.com/media/15990/elc-evaluation-procedures-v281-jan-2026.pdf（44 页；第 28 版 2025-06 也已下载核对过）

**§2.1 球落地的物理（第 7–8 页）**
> If a ball is dropped vertically, the contact area tends to increase as the bottom of the ball deforms (i.e. it flattens out). In general, the greater its velocity in the vertical direction when it hits the surface (up to a point), the more it deforms and the bigger the maximum contact area … Thus, whether a ball touches a line may be determined by the speed at which it hits the ground … Due to the horizontal motion, the ball slides and/or rolls along the ground, and thus leaves the surface at a different position from that at which it first made contact. The amount of sliding changes from shot to shot, and depends on approach angle, speed, spin, and the court surface type, making it difficult to accurately identify the true initial impact point.

**§2.2 球印不可信（第 8 页）**
> … clay particles not directly touched by the ball may be disturbed by those particles moving due to the ball impact, which will result in a larger mark than the true contact area. On a hard court, however, the threshold pressure required between the ball and surface to leave a mark may not be generated until sometime after initial contact, thus leaving a smaller mark than the true contact area.

**§4 / 附录：分三级**：Gold、Silver、Bronze（Gold 由 JEC 认定，Silver、Bronze 由 ITF 认定）。

**§7.5.1.4 真值怎么测**
> True ball impact location is measured to the nearest millimetre through use of calibrated high-speed video footage.

**§7.5.1.5 测试方式**：至少 5 个场地位置，每处至少 10 球落在离线外沿 100 mm 以内；通常用发球机在 3–5 m 外打。

**A2.2.2 实时系统的反应时间（第 35 页）**
> The time interval between ball bounce and the audible signal must not be significantly longer than that normally required for a Line Umpire's call. An appropriate response time is 0.15 ± 0.05 seconds.

**A2.2.5 精度门槛（第 38–39 页）**
- Gold：离线 100 mm 以内的球，在 ±5 mm 容差下判对率 100%；单条线上平均绝对偏差 ≤ 5 mm；所有落点最大偏差 ≤ 10 mm
- Silver：±25 mm 以内判对率 80%；25–100 mm 之间 95%
- Bronze：±25 mm 以内，沿线方向 75%、横穿线方向 65%；25–100 mm 之间 85%

**A2.1 可靠性**：实时系统漏判或错判不超过每 4 小时 1 次（至少 120 小时运行）。

## 2. Hawk-Eye Innovations《Electronic Line Calling Technology: How it works》（2016）

https://resources.platform.pulselive.com/HawkEye/document/2016/08/15/1e6cdaa4-2b70-4975-b722-7dca82b8e546/ELC_How_it_Works.pdf（3 页）

> Up to ten cameras set up around the court to capture live images.
> 2D (x,y) Vision processing is used to identify the centre of the ball.
> 3D (x,y,z) System triangulates information from each calibrated camera to provide a 3D position of ball.
> 4D (x,y,z,t) Process repeated for each frame so that 3D positions of ball can be combined to produce single trajectory of flight of the ball.
> Bounce Mark Trajectory is then used to calculate exact contact area ball made with court during the bounce phase.

> During ITF testing in 2006 Hawk-Eye passed … Results showed the system to have a mean error of only **2.6mm** when compared to a high speed camera located on the playing surface.

> … testing … Wind (and therefore camera wobble), Bright sunlight …, Shadows …, Dark or overcast conditions, Artificial floodlights
> … high speed video footage (1000fps), similar to that obtained during ITF testing

⚠️ 「3.6 mm」也出自 Hawk-Eye：Cross 2014 引的是 Hawk-Eye 官网「约 3.6 mm」，Mather 2008 引 Fischetti 2007「3 mm 以内」。2.6 mm 是这份 2016 文件写的 2006 年 ITF 测试结果。几个数说的不是同一次测量，片子只用 2.6 mm，字幕带「2006 年测试」。帧率文件里没写系统自己的，1000fps 是测试用的高速相机。

## 3. Whitney, Wurnitsch, Hontiveros & Louie (2008), Current Biology 18(20): R947–R949

https://pmc.ncbi.nlm.nih.gov/articles/PMC2652013/

> Of a random set of 4,457 points drawn from the 2007 Wimbledon championship, referees made 83 erroneous judgments. Of these, the majority (84%) were errors in which the ball was reported as being shifted in the direction of the ball's motion.

（这一集不一定用，留作人眼对照的出处。）


## 4. 补充（2026-10-30 自查时加的，均为新闻报道，非一手文件）
- 法网 2026 仍保留人工司线、看红土球印，是四大满贯里唯一的：Sky Sports（2025-09）、Arab News、SuperSport；赛事总监 Mauresmo「The machine is not 100% reliable」见 AP 转载（WTOP / TSN / theScore，2026-06）。Ruud–Fonseca 那一分各家说法不一，不用。
- FoxTenn 自称用贴地高速相机＋激光扫描直接拍落地瞬间，不靠轨迹推算（WTA 官网 2018、Scroll.in 2019，都是厂商口径；相机数、帧率各报道不一）。
- Whitney 2008 原文另两句：「a ball that lands on a line, even a tiny fraction of the line, is still considered in play」；「In the 2007 Wimbledon championship, there were over 140 player challenges, and more than 25% of these resulted in overturned calls」。

## 5. ITF 认证系统名单（2026-10-30 读）
https://www.itftennis.com/en/about-us/tennis-tech/classified-elc-systems/
- Gold：Hawk-Eye Innovations「Hawk-Eye」、Foxtenn「Foxtenn」、Bolt6「Sentinel」——三家的 Review 和 Real-time 都覆盖硬地、草地、红土（室内外）
- Silver：PlayReplay、Zenniz Smart Court
- 原文：「Only Gold Systems are considered for ELC evaluation on clay and grass surfaces」「Continued poor performance can lead to the suspension of classification」
- 所以「法网不用是因为红土上没有认证系统」这种说法不成立：三家金级都有红土实时认证。

## 6. 大满贯用哪家（新闻报道）
- 澳网、美网：2021 年起全场 Hawk-Eye Live（ESPN、SportBusiness、NPR 2022、Tennishead）
- 温网：2025 年起 Hawk-Eye Live（SVG Europe、Sport Resolutions）
- 2026 年没见到任何一家更换系统的公告，但也没找到 2026 年的官方确认

## 7. Mather (2008) Proc. R. Soc. B 275: 1645–1651, doi:10.1098/rspb.2008.0211
所有者 2026-10-30 上传的 Royal Society 原版 PDF（7 页，2008 年制作）。
- 数据：ATP 提供的 **1473 次挑战、246 名球员、15 站 ATP 赛事、2006–2007 年**（不是温网专项）
- > a significant proportion (39.3%) of the challenged line calls turned out to be incorrect according to the Hawk-Eye data
- 摘要：> Both players and line judges are remarkably accurate at judging ball bounce position, with a positional uncertainty of less than 40 mm. Line judges are more reliable than players. Judgements are more difficult for balls bouncing near base and service lines than those bouncing near side and centre lines. There is no evidence for significant errors in localization due to image motion.
- 位置不确定度（模型参数 space constant，单位 mm）：总体 球员 30 / 司线 22；Table 1 底线与发球线 球员 46 / 司线 32；边线 26 / 14；中线 26 / 14。原文：uncertainty for both players and line judges is doubled for base and service lines
- 结论：> The model predicts that 8.2% of all line calls involving balls within 100 mm of a court line will be called incorrectly by line judges
- 球和场地的接触面宽 44 mm（引 Fischetti 2007）
- ⚠️ 和 Whitney 2008 结论相反：Whitney 说错判多数顺着运动方向偏，Mather 说没有证据表明运动造成显著定位误差（中点只偏 14.4 mm，约接触面宽度的三分之一）

## 8. Cross (2014) The footprint of a tennis ball, Sports Engineering 17: 239–247
所有者 2026-10-30 上传的作者手稿版（19 页 TeX，2014-05-01 生成，无期刊页眉；和正式版可能有排版差异）。
- 摘要：> The Hawk-Eye line calling system in tennis uses a footprint of the ball to determine whether the ball was in or out. However, the footprint itself is not measured. It is the ball trajectory through the air that is measured.
- > The method used to estimate the footprint with the Hawk-Eye system has not been published as far as the author is aware
- 接触时长：Wilson 球 total impact duration 4.72 ± 0.01 ms
- 竖直落地：maximum contact diameter 42 ± 1 mm
- 斜落地实验（水平 21.1 m/s、竖直 6.8 m/s，黑板撒粉）：footprint length 100 ± 1 mm、width 44 ± 1 mm
- Hawk-Eye 转播画面（2014-01-02 布里斯班）：> The footprint shown in the Hawk-Eye system is an ellipse that is typically about 126 mm long and about 45 mm wide for a fast first serve. If the ball slides throughout the bounce, then a 126 mm long footprint implies that the average horizontal speed … is about 28 m/s, approximately as expected.
  ⚠️ 原文没有「椭圆偏大 20–25%」「偏向判 IN」的结论
- 绒毛：> Fibres extending out from the ball contact the court surface about 10 mm before the ball begins to compress … the effect can probably be ignored since it is unlikely to be detected by players or line referees. Nevertheless, there is no requirement in the rules of tennis that the effect should be ignored. If any part of the ball touches a line, then the ball is conventionally assumed to be "in".
- 场地不平：> local variations in the height of the contact surface, even as small as 1 mm, can alter the initial contact point of a ball on the court by up to 3 or 4 mm when the ball is incident at a small angle
- 像素：作者估算——若每台相机以 1920 像素横向覆盖约 12 m，一像素约 6 mm（是假设性估算，不是 Hawk-Eye 的实际参数）
- 对当年 ITF 测试的批评：当年按 2000 fps 高速相机测，作者认为看清落地头 0.1 ms 要 10000 fps 以上。⚠️ 这是 2014 年对当年流程的批评，现行第 28.1 版的测试帧率原文没写，片中不把它说成现状

## 9. Sony：相机与帧率（所有者 2026-10-30 在浏览器读到的原句；会话网络读不到 sony 两站）
- https://community.sony.dk/t5/blogs/blogarticleprintpage/blog-id/Discover_DI_EN/article-id/214?nobounce（页脚注明改编自 https://www.sony.net/SonyInfo/technology/stories/Hawk-Eye/）
> "typically, between eight and twelve cameras running at frame rates of up to 340 frames per second will be recording the game"
- 旁证：Cosmos Magazine 称 Hawk-Eye 官网写其相机 340 fps；RedShark News 同样写 340 fps
- 片中口径：「厂商说明：相机最高 340 帧/秒」——原句是 up to，是上限，不是某场实测
- 由此估算（片中标「按 340 帧/秒估算」）：两帧间隔 1/340 ≈ 2.94 ms；Cross 2014 实测触地 4.72 ms（Wilson 球）→ 触地全程约 1.6 个帧间隔，最多拍到一两帧；200 km/h = 55.6 m/s × 2.94 ms ≈ 16 cm/帧
- ⚠️ 不要引 WUSF/NPR「12 台只用 8 台、4 台备用」——那是 NFL 测首攻的系统

## 10. 2025 温网中央球场误关事故（所有者转来的原句，与 Sky Sports、AOL 的转述一致）
- 俱乐部周日声明（AFP 全文转载）：系统 "deactivated in error"，持续一局；
> "In that time, there were three calls not picked up by live ELC on the affected part of the court. Two of these were called by the chair umpire, who was not made aware that the system had been deactivated"
> "Following the third, the chair umpire stopped the match and consulted with the review official. It was determined that the point should be replayed."
- 俱乐部给 BBC Sport 的声明：
> "Following our review, we have now removed the ability for Hawk-Eye operators to manually deactivate the ball tracking"
- AP，CEO Sally Bolton 周一发布会：
> "the technology was 'inadvertently deactivated' by someone for three points at Centre Court"
- 片中口径：系统被误关一局，其间三个判罚没被系统接住，前两个由主裁自己判，第三个停赛商议后重打；赛后取消了操作员手动关闭的权限。重打结果不写
- 球员：Anastasia Pavlyuchenkova（帕夫柳琴科娃）vs Sonay Kartal（卡尔塔尔，英国）

## 11. BBC Sport：温网控制室（所有者转来的原句；温网官网原文已下线，出处挂 BBC）
> "There is a line-calling hub inside Wimbledon's grounds, where 50 operators use 144 screens to monitor the ball-tracking footage from 12 cameras on each court."

## 12. Tennisnet：Hawk-Eye Live 的相机与脚误（2020-11-06，WTA 林茨站；所有者在浏览器逐字核过）
https://www.tennisnet.com/en/news/wta-linz-for-the-first-time-hawk-eye-live-at-an-all-women-tournament
> "Twelve high-speed cameras for ball tracking determine whether balls are 'in' or 'out'."
> "An additional six 'Foot Fault' cameras check the base and center line"
> "When he presses a button, the electronic 'Foot Fault' call occurs."
- 脚误：6 台相机盯底线和中线，画面给场外复核官员，由人判断、按按钮触发电子喊声——「机器看、人来判」，不是全自动
- 12 + 6 = 18 出自这一篇原文本身，不需要另找总数出处
- ⚠️ 范围：这是 2020 年林茨站的配置。温网 2025 的脚误流程没有原文，片中写「以 Hawk-Eye Live 的公开介绍为例」
- ACM（cacmb4.acm.org/news/246601）读不到：Cloudflare 522，新站搜不到，不作出处

## 13. 温网 2025 没有挑战、不用回放（BBC Sport 2025-07 事故后续报道；BBC 原站读不到，所有者在三份独立全文转载里逐字对过：Accra Street Journal、MyJoyOnline 的 BBC 原稿存档、Bashk）
> "There are no challenges under the current system and video replays are not used."
- 备用：TNT Sports 赛事期间报道 "There is also not an option for players to challenge calls."
- 主裁介入：见第 10 节事故声明（系统故障时停赛商议、该分重打）

## 14. CNBC：How Sony's Hawk-Eye works at the US Open（2023-09-09 发，09-12 更新；cnbc.com 对会话 403，所有者在浏览器读到的原句）
https://www.cnbc.com/2023/09/09/how-sonys-hawk-eye-works-at-the-us-open.html
> "We have 12 tracking cameras around all the courts. And then we also have six foot-fault cameras."
> "The cameras track the ball at 340 frames per second"
- 「12 台追球 + 6 台脚误」的结构：美网（CNBC）与林茨（Tennisnet）两站原文互证
- ⚠️ 同文写全赛共 204 台相机、17 块场地：17 × 12 = 204，与 17 × 18 = 306 对不上（这是所有者的推算，原文没解释）。片中不写「每块场地 18 台」，不做总数推演
- 脚误怎么判、有没有挑战：CNBC 没写。脚误流程仍只有 Tennisnet 林茨一篇
- 340 fps：Sony 厂商说明（up to）＋ CNBC 美网陈述，两处原文

## 15. Cosmos Magazine：Paul Connolly《Order in the court》（2021-02-10；所有者经 Wayback 快照逐字核过）
> "Hawk-Eye's website says its 'ultra-motion cameras' operate at 340 fps"
- 340 fps 的出处链：Hawk-Eye 官网（经 Cosmos 转述）→ Sony「up to 340」→ CNBC 美网「track the ball at 340 frames per second」
- ⚠️ 同句里「160 km/h 的球两帧间飞 12.3 cm」算错了：44.4 m/s ÷ 340 ≈ 13.1 cm。不引用；片中的 16 cm 是按 200 km/h 自己算的
- ⚠️ 这是挑战时代的文章（每场 10 台、每盘 3 次不成功挑战），只用来坐实 340 的出处，别的不引
- 旁证：它提到 ITF 校验用 2000 fps 高速相机，与 Cross 2014 所述当年 ITF 测试 2000 fps 一致

## 16. 温网官网《The precision operation》（2025-07-03）已下线——出处改挂 BBC，另有两家佐证（所有者 2026-10-30 查）
- 原链接现在 302 跳到新闻首页；页面当年是前端渲染，Wayback 四份快照与葡萄牙国家档案 Arquivo（2025-07-07）正文字数都是 0，接口无存档，Common Crawl 无抓取
- 《每日电讯报》赛事报道：50 人团队、控制室名 "Ball Traffic Control"、每块场地 12 台相机；NZ Herald：50 名操作员、每场 12 台
- 结论：「每块场地 12 台、50 名操作员」= BBC ＋ 电讯报 ＋ NZ Herald 三方一致；「144 块屏幕」只有 BBC
