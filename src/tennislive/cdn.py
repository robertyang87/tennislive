"""卡片图和成片走的 CDN 主机名，一个地方定，别再散在八处。

jsDelivr 的 GitHub 代理有好几个入口，指向不同的 CDN 供应商：

| 主机 | 供应商 |
|---|---|
| `cdn.jsdelivr.net` | 负载均衡（Cloudflare / Fastly …），默认入口 |
| `gcore.jsdelivr.net` | Gcore |
| `fastly.jsdelivr.net` | Fastly |
| `testingcf.jsdelivr.net` | 强制 Cloudflare |

内容完全一样（实测同一文件四个主机返回同样的字节数），差别只在从哪个
边缘节点取。账号所有者反馈国内下载慢，选了「换镜像」这条路。

**默认换成 `gcore.jsdelivr.net`**，理由是 Gcore 在香港／日本／新加坡有
节点，是这几家里离内地最近的；`cdn.` 那个入口在 jsDelivr 的国内备案被
撤销之后，内地流量一律绕到境外。

⚠️ **这是推断，不是实测**——沙箱在境外，量不出内地速度，别拿这里的 ttfb
当结论。所以做成环境变量而不是写死：

```bash
TENNISLIVE_JSDELIVR_HOST=fastly.jsdelivr.net   # 换一个再发一条对比
```

在仓库的 Actions variables 里改一个值就能 A/B，不用改代码。想退回原样就
设成 `cdn.jsdelivr.net`。
"""

from __future__ import annotations

import os
import re

DEFAULT_JSDELIVR_HOST = "gcore.jsdelivr.net"


def jsdelivr_host() -> str:
    """当前该用哪个 jsDelivr 入口。每次读环境变量，方便测试里 monkeypatch。"""
    host = (os.environ.get("TENNISLIVE_JSDELIVR_HOST") or "").strip()
    # 只接受 jsDelivr 自己的主机名。写错一个域名会让整封推送的图片指向
    # 不存在的地方，而 PushPlus 那头**不会报错**——微信里就是一片裂图。
    if host.endswith(".jsdelivr.net") and "/" not in host:
        return host
    return DEFAULT_JSDELIVR_HOST


# 钉进 URL 的那串 commit sha 取前 10 位，不是调用方传进来的整整 40 位。
#
# ⚠️ **这不是洁癖，是它真的把一条推送顶过了平台的上限。** 2026-09-14
# `shelton-ncaa-story`（25 页图卡）被 PushPlus 拒收：
#
#     {'code': 999, 'data': '发送内容过大，不能超过2万字'}
#
# 而 `push.html` 本身只有 18704 字符——**是钉版本这一步把它撑到 21404 的**：
# 每张图有三条完整 URL（`src` / `data-src` /「点此打开原图」的 `<a href>`），
# `@main`（5 字符）换成 `@` ＋ 40 位 sha（41 字符）每处多 36，75 处就是 **2700**
# ——和实测 21404 − 18704 一分不差。钉 10 位之后每处只多 6，75 处 450 → 19154，
# 同样对得上（2026-09-14 run 34849158901 的日志）。
#
# 10 位是量出来的：`gcore.jsdelivr.net` 实测 40 / 12 / 10 / 7 位**全部
# HTTP 200**（jsDelivr 按 GitHub 的 ref 解析，短 sha 一样认）。⚠️ **万一短 sha
# 撞车，失败是安全的**：另一个 commit 上没有这个带日期和 slug 的路径 →
# jsDelivr 回 404 → `wait_for_images` 在 POST 之前就拦住了。
ASSET_REVISION_PIN_LEN = 10

_SHA_RE = re.compile(r"[0-9a-fA-F]{7,40}")


def pin_ref(revision: str) -> str:
    """把 commit sha 截到 `ASSET_REVISION_PIN_LEN` 位；不是 sha 的原样返回。

    ⚠️⚠️ **这个截断只许有这一处实现。** 2026-09-14 第一版只改了
    `pushmsg.pin_asset_revision`，而钉 sha **有两处**——`pushplus` 的
    `_pages_image_url` 自己从 `TENNISLIVE_ASSET_REV` 读整整 40 位重拼 URL，
    随后 `_jsdelivr_fallback_delivery` 按**整个 URL 字符串全文替换**，
    于是 `src` / `data-src` / `href` 三处全被换回长的，**把前一处的修改整个
    盖掉**。补发那一趟量出来仍然是 21404 字符——和没改一模一样。
    这正是「一个数写两处必分叉」，而分叉的样子是**改对了的那一半看不出来**。

    `main` 这类分支名不是 sha，原样返回——`jsdelivr_base` 的默认值就是它。
    """
    return revision[:ASSET_REVISION_PIN_LEN] if _SHA_RE.fullmatch(revision or "") else revision


def jsdelivr_base(repository: str, revision: str = "main") -> str:
    """`https://<host>/gh/<owner>/<repo>@<rev>`，末尾不带斜杠。"""
    return f"https://{jsdelivr_host()}/gh/{repository}@{pin_ref(revision)}"


def is_jsdelivr(url: str) -> bool:
    """这条 URL 是不是走 jsDelivr。

    判据按 `.jsdelivr.net` 而不是某个具体主机——换了镜像之后，只认
    `cdn.jsdelivr.net` 的地方会**悄悄放行**：推送前那道「图片可取吗」的
    校验会一张都不校验，然后把一堆没准备好的链接发出去。
    """
    return ".jsdelivr.net/" in url
