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

DEFAULT_JSDELIVR_HOST = "gcore.jsdelivr.net"


def jsdelivr_host() -> str:
    """当前该用哪个 jsDelivr 入口。每次读环境变量，方便测试里 monkeypatch。"""
    host = (os.environ.get("TENNISLIVE_JSDELIVR_HOST") or "").strip()
    # 只接受 jsDelivr 自己的主机名。写错一个域名会让整封推送的图片指向
    # 不存在的地方，而 PushPlus 那头**不会报错**——微信里就是一片裂图。
    if host.endswith(".jsdelivr.net") and "/" not in host:
        return host
    return DEFAULT_JSDELIVR_HOST


def jsdelivr_base(repository: str, revision: str = "main") -> str:
    """`https://<host>/gh/<owner>/<repo>@<rev>`，末尾不带斜杠。"""
    return f"https://{jsdelivr_host()}/gh/{repository}@{revision}"


def is_jsdelivr(url: str) -> bool:
    """这条 URL 是不是走 jsDelivr。

    判据按 `.jsdelivr.net` 而不是某个具体主机——换了镜像之后，只认
    `cdn.jsdelivr.net` 的地方会**悄悄放行**：推送前那道「图片可取吗」的
    校验会一张都不校验，然后把一堆没准备好的链接发出去。
    """
    return ".jsdelivr.net/" in url
