# YT_COOKIES_TXT 过期了怎么办

这条是**给账号所有者自己动手的操作手册**：源片全部来自 YouTube，而机房 IP 一律被
YouTube 按机器人挡掉，唯一的通行证就是仓库 Secret `YT_COOKIES_TXT` 里那份登录态
cookie。**它会过期**，过期之后整条源片下载链（赛场之上、赛后开麦、场上采访、
frame-grab、编排器）一起停摆。

⚠️ **过期的表现是骗人的**：滚到眼前的报错写着

    ERROR: Sign in to confirm you're not a bot

读起来像「这个视频要登录才能看」，而它其实是三件事共用的一张脸：

| 真因 | 日志里的记号 | 归谁 |
|---|---|---|
| 这份 cookie 死了 | `The provided YouTube account cookies are no longer valid.`（**WARNING，不是 ERROR**，在几十行里很容易滑过去） | 第 2 步，重导 |
| **这一阵子被限流** | 同上——**yt-dlp 分不出这两者**，见第 0 节 | **等一个钟头再跑一次** |
| 缺 `yt-dlp[default]` | `n challenge solving failed` / `Only images are available` | 查那条工作流的 pip 行，和 cookie 无关 |

CLAUDE.md「别把『我想到的原因都排除了』当成『我想到了所有原因』」记的正是第三行
那次；**第二行是 2026-09-19 才量出来的，之前不在候选里**——见第 0 节。

## 0. ⚠️ 先别急着重导——这句报错**也可能是一阵子的**

2026-09-19 实测的一天，把这一条摆到了最前面：

| 时刻（UTC） | 跑的什么 | 结果 |
|---|---|---|
| 17:20 / 17:31 | probe ×2，**两台不同 runner** | 8 种 player client 全红 |
| 17:44 / 18:48 | **cookies（默认视频）** ×2，隔一小时 | 全红，yt-dlp 打出 `The provided YouTube account cookies are no longer valid.` |
| **23:49** | **cookies（默认视频），同一份 secret 一个字没改** | **绿**——`拿到 probe.webm，1939464 字节` |

四趟全红之后，**什么都没改，五小时后自己好了**。判据不是推的：23:49 那一趟日志里
`带 cookie 试（25 行）` **还是 25 行**（说明 secret 没被动过），而那句
`cookies are no longer valid` 的 WARNING **一次都没出现**。

⚠️ **所以 yt-dlp 那句「你的账号 cookie 失效了」自己也会骗人**：它是 yt-dlp 对
YouTube 拒绝响应的解读，而**「这个机房这一阵子被限流」和「这份 cookie 死了」
在它眼里长得一样**。仓库里「排除了 A 和 B 不等于就是 C」那条记的是同一个形状——
这次多出来的第三个候选是「**等一等**」。

**结论不是「不用管」，是顺序变了：先跑第 1 步隔一个钟头再跑一次；两次都红、
而且中间换过 runner，才轮到第 2 步真去重导。** 重导一份要开无痕、要小心别点退出，
比再跑一趟 51 秒的检查贵得多。

## 1. 先确认真的是它

不要凭报错猜。跑一趟 `match-reel` 的 `mode=cookies`：什么都不产、不提交、不推微信，
**实测 51 秒**，它真去取 3 秒媒体流（`--skip-download` 那种探活是假的，不带 cookie
照样拿得到标题和格式表）。

    Actions → match-reel → Run workflow
      mode = cookies
      slug = cookie-check      （随便填，这个模式不读 spec）
      url  = 留空即可          （留空走内置的那条测试视频）

日志末尾三种结论，各指向不同的活：

| 日志里出现 | 意思 | 怎么办 |
|---|---|---|
| `撞上了机器人验证——cookie 无效或已过期` | cookie 死了**或者**在限流 | **隔一个钟头再跑一次**；还红才走第 2 步 |
| `n challenge 解不了` | 缺 `yt-dlp[default]` / JS 运行时，**和 cookie 无关** | 查那条工作流的 pip 行 |
| `YouTube 下载可用。` | cookie 是好的 | 停手，去查别的 |

## 2. 重新导一份 cookie

⚠️ **整个过程在无痕窗口里做**，这一条不是讲究卫生，是这份 cookie 能活多久的关键：
平时那个窗口继续刷 YouTube 会把会话轮换掉，导出来的那份当场就作废。

1. 开一个**无痕 / 隐私窗口**，登录 youtube.com（用哪个账号都行，普通账号即可，
   不需要会员）
2. 在同一个无痕窗口里新开一个标签页，打开 <https://www.youtube.com/robots.txt>
   ——这一步是为了让导出发生在一个不跑播放页 JS 的页面上，避免导的瞬间会话被刷新
3. 用一个 **Netscape 格式**的 cookies.txt 导出扩展导出 `youtube.com` 这个域
   （Chrome / Edge：「Get cookies.txt LOCALLY」；Firefox：「cookies.txt」）。
   导出来的文件第一行应该是 `# Netscape HTTP Cookie File`，正文是**制表符**分隔
4. ⚠️ **直接关掉那个无痕窗口，不要点退出登录**。点了退出就等于把刚导出的那份会话
   当场作废——导完立刻失效，而表现和「导错了」一模一样

## 3. 更新 Secret

    仓库 Settings → Secrets and variables → Actions → YT_COOKIES_TXT → Update

把整份文件的内容**原样粘进去**（包含第一行那句注释；多行没问题，工作流是
`printf '%s'` 原样落盘的）。⚠️ 别在中间用会把制表符换成空格的编辑器过一手——
换成空格那份文件 yt-dlp 读不了，而它报的仍然是「Sign in to confirm」。

⚠️ **不要把 cookie 内容贴进任何对话、issue、PR 或日志里**：它等价于那个 YouTube
账号的登录凭证。工作流里已经不会打印内容，只打印行数。

## 4. 再跑一遍第 1 步

同一条 `mode=cookies`，看到 `YouTube 下载可用。` 加上一行字节数和时长，才算好了。
它没变绿就别去开 probe——一趟 probe 是 2~7 分钟，而这一趟是 51 秒。

## 多久要做一次

没有定数，Google 那边随时会让会话失效。**判据是产物不是日历**：任何一条线报
`Sign in to confirm you're not a bot`，第一件事是跑第 1 步分因，**第二件事是等一个
钟头再跑一次**（第 0 节那张表），两次都红才动手重导。
