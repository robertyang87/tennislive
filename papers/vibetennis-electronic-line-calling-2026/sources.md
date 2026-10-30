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

⚠️ 网上流传的「3.6 mm」和这份官方文件对不上，片子用 2.6 mm。帧率文件里没写系统自己的，1000fps 是测试用的高速相机。

## 3. Whitney, Wurnitsch, Hontiveros & Louie (2008), Current Biology 18(20): R947–R949

https://pmc.ncbi.nlm.nih.gov/articles/PMC2652013/

> Of a random set of 4,457 points drawn from the 2007 Wimbledon championship, referees made 83 erroneous judgments. Of these, the majority (84%) were errors in which the ball was reported as being shifted in the direction of the ball's motion.

（这一集不一定用，留作人眼对照的出处。）

## 没读到的
- Cross (2014) The footprint of a tennis ball：researchgate 403，Springer 不在放行名单。「脚印约 10 cm、渲染椭圆约 12.6 cm、偏向判 IN」这些说法**不用**。
- Mather (2008)：royalsocietypublishing.org 不在放行名单。「人眼约 4 cm」**不用**。

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
