# ATP 源片：Tennis TV 单场集锦要订阅，账号所有者拍板不订（2026-08-09）

> 账号所有者：「atp 也要搞定啊」→ 探明 Tennis TV 每场都发官方单场集锦、
> 卡点在订阅 token → 账号所有者：「**我没有会员，太贵了没必要**」。
> 所以 ①订阅那档**永久出局**，ATP 走免费路，方案见下。

## 实测事实

`https://www.tennistv.com/library/match-highlights` 列着蒙特利尔 2026 的
**每一场**单场集锦，slug 规律固定：

    /videos/<id>/montreal-2026-r3-darderi-shang-highlights      ← 商竣程那场也有
    /videos/<id>/montreal-2026-r4-fils-norrie-highlights
    …（R2/R3/R4 二十条全在，当天场次当天上）

- 单场集锦 `data-entitlement="premium"`——**要订阅 token**
- 当日合集（Tuesday Highlights 那类）是 `freemium`——免费注册账号即可
- 页面沙箱直连可达；下载走 streamamg（采访线已验证 yt-dlp 能下）

## 免费路两档（订阅档已被账号所有者否掉，别再提）

| 档 | 要什么 | 覆盖 |
|---|---|---|
| **① ATP Tour YouTube 频道（主路）** | 无 | 大场次有免费单场集锦，覆盖不稳定；runner 上探。和 WTA 的 YouTube 路是同一套下载栈 |
| ② 免费注册 token（可选升级，零费用） | 账号所有者注册一个**免费** Tennis TV 账号、取 JWT 配 `TENNISTV_JWT` secret | 解锁 `freemium` 档的**当日合集**（Tuesday Highlights 那类）——要在合集里按烧死的记分条定位单场，重活但机械可做 |

场上采访不受影响：`fetch_tennistv_video_metadata` 走的公开 entitlement
接口（`data-entitlement="free"` 那批），不要任何 token，赛后开麦照旧。

② 真要配的话：注册免费账号 → F12 → Network 里找
`Authorization: Bearer <一长串>` → 配进 Settings → Secrets → **Actions**
（⚠️ 加到 Codespaces 那栏工作流读不到且不报错）。token 会过期，
探针要把 HTTP 状态和响应体一起报，和「视频下架」区分开。

## 班次口径

ATP 场次的源片解析顺序：**① YouTube 免费单场集锦 → 没有就报「这场没源」
跳过**（②没配之前不参与）。选题优先级照旧（中国球员>顶级>热点）——
ATP 覆盖不稳是源的限制，不是选题规则变了；YouTube 上探得到就做。
