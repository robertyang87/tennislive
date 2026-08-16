# ATP 源片：Tennis TV 的**短集锦**是免费的（2026-08-16 更正）

> 账号所有者 2026-08-16：「**ATP 的赛场之上 highlight 可以去 tennistv 找啊**」
> ——给了一条 `.../cincinnati-2026-r2-paul-hurkacz-**short**-highlights`。
> 去量了一遍：**这条路通，而且不要订阅。**

## ⚠️ 这份文档 2026-08-09 那版的结论是错的，错法值得记

那版写着「单场集锦 `data-entitlement="premium"`——要订阅 token」，据此把 ATP
判成「只能靠 ATP Tour YouTube 频道碰运气」。**那句话对它查的那一档是真的，
而它把一档写成了全部**——Tennis TV 的单场集锦分两档，挂在**两个平行的
library 版块**下：

| 版块 | slug | entitlement | 时长 | 抽样 |
|---|---|---|---|---|
| `library/match-highlights` | `<赛事>-<轮次>-<对阵>-highlights` | **premium**（要订阅，账号所有者已否掉） | 全长 | 2/2 |
| **`library/short-highlights`** | 同名带 **`-short-highlights`** | **free** | **2 分半** | **20/20** |

上一版**只查了 `match-highlights` 这一个版块**，而 `library/short-highlights`
从来没被打开过。这正是 CLAUDE.md 里「空结果先自证是真空」「查空一类不等于
查空全部」那条——只不过这次要自证的不是空不空，是**空的范围有多大**；
同一个形状这个仓库已经栽过三次（「查了一场就写成了一类」）。

⚠️ **两档的 slug 差六个字母，页面长得一模一样。** 只有 `data-entitlement`
那一个属性把它们分开——所以**判据是打开页面看那个属性**，不是看标题像不像。

## 实测（2026-08-16，辛辛那提 2026 R1/R2 那一页）

**覆盖**：`match-highlights` 20 场、`short-highlights` 20 场，**一一对应**，
没有一场只有付费档。⚠️ 这是**一页的抽样**（一站两轮），别读成「永远都有」——
做片子之前照旧打开那一页看一眼。

**规格**（20 条全查过 entitlement 和时长）：

    entitlement   20/20 free
    时长          2:28 ~ 2:39（几乎定长 ~155 秒，和 WTA 纯集锦定长 310 秒同一个形状）
    视频          1920×1080 · h264 · **30 fps**        ← ⚠️ 不是 25
    音频          aac
    HLS 档位      1920×1080 / 1280×720 / 640×360 / 483×272

⚠️ **30 fps**：WTA 那条线的源片多是 25，跨源剪辑要按 CLAUDE.md「多源剪辑：
帧率要认领」写 `mixed_fps`。

**解析链**（零 token，`fetch_tennistv_video_metadata` 早就写好了）：

    页面 → data-entry-id → api.tennistv.com/entitlementcheck/v1/videoentitlements/<entry>
         → api.playback.streamamg.com/v1/entry/<entry> → streamamg 的 HLS

⚠️ **manifest 上那个令牌只活 60 秒**（payload `exp - iat = 60`，
`customerId` 是 `anonymous`——可见确实没用到任何登录）。所以
**解析必须在下载那一刻做，不能把解出来的地址钉进 spec**：钉进去就是一条
一分钟后必死的链接，而它失败的样子和「这条片子被下架了」一模一样。
spec 里放**页面地址**（不带令牌，`_reject_signed_source_urls` 放行）。

⚠️ 但 60 秒**不是下载的时限**：实测整条 154 秒、74.6 MB 的片子一趟下完没事，
令牌只管换取那一步。别为此去拆分片下载。

**沙箱下得动**——被挡的是 YouTube，不是 streamamg（CLAUDE.md 早记过这一条）。
所以这条源比 WTA 那条更好在本地走完整条流水线。

## 班次口径（更新）

账号所有者 2026-08-16 定的顺序：「**优先级就是 YouTube 找不到就找
Tennis TV 的 short highlight**」。

1. **ATP Tour / Tennis TV 官方 YouTube 频道**（主路）—— 大场次有免费单场集锦
2. **Tennis TV `library/short-highlights`**（YouTube 没有这一场时）—— 免费、1080p
3. 两条都没有才报「这场没源」跳过

⚠️ **这个顺序和「挑更长更完整的那版」是同一条**，不是妥协：YouTube 那批
单场集锦实测 **2~8 分钟**（Tennis TV 频道那批偏长），而短集锦是**定长 2 分半**
——它是被剪短的那一版。片长在这条线上是内容（「不要砍片长」「我怕故事讲解
不完整」），所以拿得到长的就不要将就短的。

⚠️ 反过来也别读成「短集锦是次品」：ATP 的 YouTube 覆盖**本来就不稳**
（这份文档 2026-08-09 那版整篇讲的就是这件事），而短集锦是**每场都有**的。
它顶上来的不是画质，是**覆盖**——2 分半、1080p，够剪一条「赛场之上」。

**订阅那一档永久出局**（账号所有者：「我没有会员，太贵了没必要」），
`TENNISTV_JWT` 那条可选升级也不必再提——短集锦这一档根本不需要它。

选题优先级照旧（中国球员 > 顶级 > 热点，半决赛级别以上直接做）。

## 怎么扫一天的候选（**先扫 YouTube，缺哪几场再来这儿补**）

    curl -sS -H "User-Agent: tennislive/0.1" https://www.tennistv.com/library/short-highlights \
      | grep -o '/videos/[0-9]*/[a-z0-9-]*short-highlights' | sort -u

逐条打开看 `data-entitlement` 和 `itemprop="duration"`。⚠️ 别按 slug 猜
`-short-highlights` 存不存在——**猜错时页面照样返回 200**（soft-404 这个仓库
栽过），要看属性抠不抠得出来。

## 代码在哪

- 解析：`tennislive.video.official.media_url()` —— **两条线共用这一份**
  （「赛场之上」`build_match_reel`、「赛后开麦」`build_interview_clip`
  各包一层只翻译异常类型）。写两处必分叉，而**分叉的样子是「采访线能下、
  出片线报『注册用户才能看』」**——那正是 2026-08-16 之前的状态
- 判据：`tests/test_match_reel.py` 四条（解析真被调到、播放列表不走 curl、
  缓存键用页面地址、只有一份实现），四条都反向验证过
