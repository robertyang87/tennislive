# ATP 源片的钥匙：Tennis TV 单场集锦（2026-08-09 实测）

> 账号所有者：「atp 也要搞定啊」。答案在 2026-08-09 夜里探出来了：
> **Tennis TV 给 ATP 每场都发官方单场集锦**，卡点只在一个订阅 token。

## 实测事实

`https://www.tennistv.com/library/match-highlights` 列着蒙特利尔 2026 的
**每一场**单场集锦，slug 规律固定：

    /videos/<id>/montreal-2026-r3-darderi-shang-highlights      ← 商竣程那场也有
    /videos/<id>/montreal-2026-r4-fils-norrie-highlights
    …（R2/R3/R4 二十条全在，当天场次当天上）

- 单场集锦 `data-entitlement="premium"`——**要订阅 token**
- 当日合集（Tuesday Highlights 那类）是 `freemium`——免费注册账号即可
- 页面沙箱直连可达；下载走 streamamg（采访线已验证 yt-dlp 能下）

## 三档接入方案（从好到兜底）

| 档 | 要什么 | 覆盖 |
|---|---|---|
| **① 订阅 token（推荐）** | 账号所有者登录 tennistv.com 后取 JWT 配成 `TENNISTV_JWT` secret | **每场**单场集锦，ATP 与 WTA 完全对齐，手动转存永久退休 |
| ② 免费注册 token | 免费账号的 JWT | 只有当日合集——要在合集里按记分条定位单场，重活 |
| ③ ATP Tour YouTube 频道 | 无 | 只有大场次有免费单场集锦，覆盖不稳定；runner 上探 |

⚠️ 合规口径：账号所有者本人有付费订阅，自动化的是**他自己账号**的取用，
和现在手动转存是同一件事的自动版。

## token 怎么取（给账号所有者的操作指引）

1. 浏览器登录 tennistv.com（订阅账号）
2. F12 开发者工具 → Network → 刷新页面 → 随便点一个请求，在 Request
   Headers 里找 `Authorization: Bearer <一长串>`（或 Application →
   Cookies 里的会话 token——具体键名等第一次配的时候对着真实请求确认）
3. 把那串配进仓库 Settings → Secrets and variables → **Actions** →
   `TENNISTV_JWT`（⚠️ 加到 Codespaces 那栏工作流读不到且不报错，
   CLAUDE.md 的老坑）
4. 告诉会话一声，跑一遍探针验证能解出 HLS，然后接进 match-reel 的
   源片解析（`media_url()` 那层）

⚠️ token 会过期（周期未知，第一次配了之后量）；过期的表现要和
「视频下架」区分开，探针必须把 HTTP 状态和响应体一起报。

## 接入后的班次口径

ATP 场次不再一律跳过：选题优先级照旧（中国球员>顶级>热点），源片解析
顺序 ①订阅集锦 → ③YouTube 免费集锦 → 没有就报「这场没源」跳过。
`TENNISTV_JWT` 没配之前只有 ③ 那一档可自动尝试。
