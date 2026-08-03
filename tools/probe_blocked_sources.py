#!/usr/bin/env python3
"""在 Actions 的出口网络上探那些**沙箱够不到**的源。

沙箱这台机器被挡的几处，各有各的挡法，长得却都像「没有」：

- `atptour.com` —— 全站 403，带浏览器 UA 也一样
- `live-tennis.eu` —— 403，连控制组（阿尔卡拉斯）都搜不到，是被挡不是没有
- `mextenisphoto.pixieset.com` —— 403 + 「Just a moment…」，Cloudflare 人机校验

runner 的出口 IP 不一样，这几处可能通。**通不通本身就是结论**，所以
每一条都要把状态码、Content-Type、字节数打出来——只在成功时出声的检查，
没法证明它真的看过。

    python tools/probe_blocked_sources.py --want "Coleman Wong" --want Brooksby

**探图**（场馆图那条线用）：给 `--url` 就换成自定义目标，给 `--save DIR`
就把取到的图片存下来（工作流会当 artifact 传出来），每张打出真实尺寸。

    python tools/probe_blocked_sources.py --save out/ \\
        --url "https://ktf.kz/_images/photoalbum/366_1749034030_1.jpg"

为什么要这个：场馆图那条线攒了一堆「本环境取不到」，各有各的挡法——
霍巴特官网被 Cloudflare 挡（标题 `CNAME Cross-User Banned`）；
`atptour.com` 全站 403。runner 的出口不一样，**通不通本身就是结论**。

⚠️ 2026-07-31 第一次拿场馆图这条线跑出来的结论，**和我的预期相反，记下来**：
runner 上 `atptour.com`（索引页和赛事页）、霍巴特官网**仍然 403**。
同一次跑里里约那张对照图 200 + 2048x929 取到了，所以不是工具坏了。

所以「换个出口就能过」这个假设**对 403 那两处不成立**：它们是按 UA／
机器人规则挡的，换 IP 没用。**每加一条「本环境取不到」的记录之前，
先用这个工具证一次**——别把「我这儿取不到」直接写成「换个环境就有」。

⚠️⚠️ 2026-08-03：上面这段原来还把 **ktf.kz**（阿拉木图官方相册）列成
「从两个完全不同的网络都到不了」。**那句话是错的，而且错了三天。**
它一直好好地在那儿，问题在证书：

    ktf.kz        只发了叶子证书，**没带中间证书**  → verify error 21
    almatyopen.kz 同一个 IP，发完整链              → verify OK

「服务器少发一张中间证书」和「这台主机连不上」在 urllib 那儿报出来
**一模一样**（`URLError`），我就照着报错写了结论。真正的判据是
`SSLCertVerificationError.verify_code`：20/21 是链不完整，跟可达性无关。

现在 `fetch()` 会自己把 AIA 指的那张中间证书补上再重试一次
（`_aia_completed_context`），**不是关掉校验**——补进来的那张必须自己
能挂到已受信的根上，补完仍然走完整校验（含主机名）。
补上之后 ktf.kz 的 92 本相册全部取得到。
"""

from __future__ import annotations

import argparse
import os
import re
import socket
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

TARGETS = [
    ("ATP 洛斯卡沃斯战报（周四）",
     "https://www.atptour.com/en/news/los-cabos-2026-thursday-report"),
    ("ATP 洛斯卡沃斯赛果页",
     "https://www.atptour.com/en/scores/archive/los-cabos/8996/2026/results"),
    ("ATP 即时排名（live-tennis.eu）",
     "https://live-tennis.eu/en/atp-live-ranking"),
    ("赛事官方图库（pixieset）",
     "https://mextenisphoto.pixieset.com/mifeltenisopen2026/"),
    ("赛事官网八强战报列表",
     "https://www.loscabostennisopen.com/wp-json/wp/v2/posts"
     "?per_page=5&orderby=date&order=desc"),
]


# 「链不完整」的两个 OpenSSL 码。**只有这两个**才值得去补中间证书：
#   20 unable to get local issuer certificate
#   21 unable to verify the first certificate
# 过期（10）、主机名对不上（62）、自签（18）都是**证书本身有问题**，
# 补中间证书救不了，也不该救——那才是真该报出来的东西。
_INCOMPLETE_CHAIN_CODES = frozenset({20, 21})


def _leaf_cert_der(host: str, port: int = 443, timeout: int = 20) -> bytes | None:
    """只把叶子证书读回来（为了看它的 AIA 指到哪儿），**不传任何数据**。

    这一步必须用不校验的连接——校验不过正是我们要修的那件事。它读到的
    东西也不被信任：AIA 只是个**线索**，取回来的中间证书还要自己过一遍
    `openssl verify`（见 `_aia_completed_context`）才会被用上。
    """
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or ""
    try:
        if proxy:
            parsed = urllib.parse.urlsplit(proxy if "//" in proxy else f"//{proxy}")
            sock = socket.create_connection((parsed.hostname, parsed.port or 8080), timeout)
            sock.sendall(f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n"
                         .encode())
            head = b""
            while b"\r\n\r\n" not in head:
                chunk = sock.recv(1024)
                if not chunk:
                    return None
                head += chunk
            if b" 200 " not in head.split(b"\r\n")[0]:
                return None
        else:
            sock = socket.create_connection((host, port), timeout)
        with sock, ssl._create_unverified_context().wrap_socket(
                sock, server_hostname=host) as tls:
            return tls.getpeercert(binary_form=True)
    except Exception:                                         # noqa: BLE001
        return None


def _aia_ca_issuer_url(der: bytes) -> str | None:
    """从叶子证书里读 AIA 的 CA Issuers 地址。走 openssl，不引第三方库。"""
    try:
        out = subprocess.run(
            ["openssl", "x509", "-inform", "DER", "-noout", "-ext", "authorityInfoAccess"],
            input=der, capture_output=True, timeout=20, check=False).stdout.decode("utf-8", "ignore")
    except Exception:                                         # noqa: BLE001
        return None
    m = re.search(r"CA Issuers - URI:(\S+)", out)
    return m.group(1) if m else None


def _aia_completed_context(host: str, port: int = 443) -> ssl.SSLContext | None:
    """服务器漏发中间证书时，自己把 AIA 指的那张补进信任链。

    **这不是「跳过校验」，方向正相反**——浏览器本来就会做这一步（AIA
    chasing），我们只是补上 Python 不做的那一环。两条闸保证它没有放松任何
    东西，缺一不可：

    1. 取回来的中间证书**必须自己能挂到已受信的根上**（`openssl verify`
       拿现有 bundle 验它）。挂不上就返回 None，宁可报「取不到」。
       ——所以它拿到的信任，正是它本来就有的那份，一点没多。
    2. 返回的 context 仍然是 `create_default_context()`：
       `verify_mode=CERT_REQUIRED`、`check_hostname=True`，一项没动。

    openssl 不在就直接返回 None（**fail closed**）：验不了就别用。
    """
    der = _leaf_cert_der(host, port)
    if not der:
        return None
    aia = _aia_ca_issuer_url(der)
    if not aia:
        return None
    try:
        with urllib.request.urlopen(aia, timeout=20) as fh:
            blob = fh.read()
    except Exception:                                         # noqa: BLE001
        return None
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "aia.crt")
        pem = os.path.join(tmp, "aia.pem")
        with open(raw, "wb") as fh:
            fh.write(blob)
        for form in ("DER", "PEM"):
            done = subprocess.run(["openssl", "x509", "-inform", form, "-in", raw,
                                   "-out", pem], capture_output=True,
                                  timeout=20, check=False)
            if done.returncode == 0:
                break
        else:
            return None
        bundle = (os.environ.get("SSL_CERT_FILE")
                  or ssl.get_default_verify_paths().cafile or "")
        if not bundle or not os.path.exists(bundle):
            return None
        # 闸①：这张中间证书自己得是可信的。验不过就不用它。
        checked = subprocess.run(["openssl", "verify", "-CAfile", bundle, pem],
                                 capture_output=True, timeout=20, check=False)
        if checked.returncode != 0:
            print(f"    ⚠️ AIA 取到的中间证书**挂不到已受信的根上**，不采用："
                  f"{checked.stdout.decode('utf-8', 'ignore').strip()[:120]}")
            return None
        with open(pem, encoding="utf-8") as fh:
            extra = fh.read()
    # 闸②：仍然是默认的完整校验，只是多带一张中间证书。
    ctx = ssl.create_default_context(cafile=bundle)
    ctx.load_verify_locations(cadata=extra)
    return ctx


def fetch(url: str, timeout: int = 30) -> tuple[str, str, bytes]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            return str(fh.status), fh.headers.get("Content-Type", "?"), fh.read()
    except urllib.error.HTTPError as exc:
        return str(exc.code), exc.headers.get("Content-Type", "?") if exc.headers else "?", b""
    except urllib.error.URLError as exc:
        reason = exc.reason
        code = getattr(reason, "verify_code", None)
        if code not in _INCOMPLETE_CHAIN_CODES:
            return f"ERR {type(exc).__name__}", str(reason)[:90], b""
        # 服务器漏发中间证书。补一张再来一次——**两种结果都要出声**，
        # 否则「补上了」和「本来就通」在日志里长得一样。
        parts = urllib.parse.urlsplit(url)
        print(f"    ⚠️ 证书链不完整（verify_code={code}：{getattr(reason, 'verify_message', '')}）"
              f"——这**不是**到不了，是 {parts.hostname} 少发了中间证书。补 AIA 再试")
        ctx = _aia_completed_context(parts.hostname, parts.port or 443)
        if ctx is None:
            return f"ERR {type(exc).__name__}", "补不上中间证书", b""
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as fh:
                print("    ✅ 补上中间证书之后校验通过（完整校验，含主机名）")
                return str(fh.status), fh.headers.get("Content-Type", "?"), fh.read()
        except urllib.error.HTTPError as exc2:
            return str(exc2.code), "?", b""
        except Exception as exc2:                             # noqa: BLE001
            return f"ERR {type(exc2).__name__}", str(exc2)[:90], b""
    except Exception as exc:  # noqa: BLE001
        return f"ERR {type(exc).__name__}", "?", b""


def _report_image(body: bytes, url: str, save_dir: str) -> None:
    """图片这一档报**真实尺寸**，不是字节数。

    踩过的两个坑都只有解码之后才看得出来：soft-404 会返回 200 + 一张
    错误页（`Content-Type: text/html`），而有些站返回的「图」其实是
    几十字节的占位符。所以取到 body 还要真的解码一次。
    """
    from pathlib import Path

    name = url.split("?")[0].rstrip("/").split("/")[-1] or "image"
    try:
        from io import BytesIO

        from PIL import Image

        im = Image.open(BytesIO(body))
        print(f"    图片 {im.size[0]}x{im.size[1]} {im.format}")
    except Exception as exc:                              # noqa: BLE001
        print(f"    ⚠️ 取到 {len(body)} 字节但**解不出图片**（{type(exc).__name__}）"
              "——多半是 soft-404 或占位符，不是照片")
        return
    if save_dir:
        out = Path(save_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / name).write_bytes(body)
        print(f"    存下 {out / name}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--want", action="append", default=[],
                    help="要在正文里找的词，找到就把上下文打出来")
    ap.add_argument("--url", action="append", default=[],
                    help="自定义目标，可给多次；给了就**不再探默认那五条**")
    ap.add_argument("--save", default="",
                    help="把取到的图片存进这个目录（工作流当 artifact 传出来）")
    args = ap.parse_args()
    wants = args.want or ["Coleman Wong", "Brooksby"]
    targets = [(u, u) for u in args.url] if args.url else TARGETS

    for label, url in targets:
        status, ctype, body = fetch(url)
        print(f"\n=== {label}")
        print(f"    {url}")
        print(f"    {status}  {ctype}  {len(body)} 字节")
        if not body:
            continue
        if "image/" in ctype:
            _report_image(body, url, args.save)
            continue
        text = body.decode("utf-8", "ignore")
        # Cloudflare 的挑战页会返回 200，光看状态码分不出来
        if "Just a moment" in text or "cf-browser-verification" in text:
            print("    ⚠️ Cloudflare 人机校验页——状态码骗人，这不是内容")
            continue
        flat = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", text))
        for want in wants:
            hits = list(re.finditer(re.escape(want), flat, re.I))
            print(f"    「{want}」命中 {len(hits)} 次")
            for m in hits[:3]:
                s = max(0, m.start() - 220)
                print(f"      …{flat[s:m.end() + 220]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
