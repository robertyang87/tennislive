"""让沙箱里的出网请求认得出代理那张证书——**只为把验证搬回本地**。

## 为什么要有它

CLAUDE.md 里「为什么不在本地跑」一直写着两条：YouTube 挡机房 IP，以及
「edge-tts 同理」。**第一条是真的，第二条不是。** 实测下来 edge-tts 在沙箱里
连的是 `speech.platform.bing.com`，报的是

    SSLCertVerificationError: self-signed certificate in certificate chain

——不是被挡，是**这台机器的出网走一个做 TLS 拦截的代理**，而 edge-tts 认的
是 certifi 自带的那份根证书，里面没有代理那张。代理的 CA 就在机器上
（`/root/.ccr/ca-bundle.crt`），挂上去当场就通了。

这件事值多少：`build_match_reel.py --check-narration` 那道闸比的是
「TTS 时长 vs spec 里的段长」，**一个源片字节都不碰**。它跑在 runner 上是因为
合语音要出网——而合语音本来就能在本地合。量出来的账（shang-rublev，
2026-08-05）：那条片子 98 分钟的周期里有**两趟 `mode=narration`**，各自
1 分 37 秒和 1 分 53 秒的 run，加上两次「推 spec → 等 run → 拉日志」的往返。
搬到本地之后是一条命令。

## 它不做什么

- **不碰 site-packages。** certifi 自己那份文件一个字节都不动，合并出来的
  那份写在缓存目录里。改别人装的包会在下一次 `pip install` 时静默消失，
  而消失的样子是「今天怎么又不通了」
- **在 runner 上是个 no-op，而且不出声。** 那儿没有这个 CA 文件，也不需要。
  恒真的告警会把真正该看见的那次淹掉
"""

from __future__ import annotations

import os
import ssl
from pathlib import Path

#: 这台沙箱的代理 CA。换个环境就用 `TENNISLIVE_EXTRA_CA` 指过去。
_WELL_KNOWN = ("/root/.ccr/ca-bundle.crt",)
_CACHE = Path.home() / ".cache" / "tennislive-ca" / "bundle.pem"

_done: str | None = None


def _extra_ca() -> Path | None:
    """代理的 CA 在哪儿。**找不到就是 runner，返回 None。**"""
    explicit = os.environ.get("TENNISLIVE_EXTRA_CA", "").strip()
    if explicit:
        p = Path(explicit).expanduser()
        # 显式指了却不存在，是**配错了**，不是「这台机器没有」——要出声。
        # 悄悄当成 no-op 的话，「配了却没生效」和「本来就没配」长得一模一样。
        if not p.is_file():
            raise FileNotFoundError(f"TENNISLIVE_EXTRA_CA 指向的文件不存在：{p}")
        return p
    for cand in _WELL_KNOWN:
        p = Path(cand)
        # ⚠️ **`Path.is_file()` 会抛，不是只返回 False。** 它只吞
        # ENOENT / ENOTDIR / EBADF / ELOOP 那几类，**不吞 EACCES**——而 runner 上
        # 跑测试的用户根本进不去 `/root`，于是 `os.stat` 抛 PermissionError。
        #
        # 这个探测排在 `main()` 的**第一行**，所以它一抛就是**每一次 CLI 调用
        # 都崩**：整条 match-reel 会死在还没解析参数的时候。CI 当场逮到
        # （run 30971701644，两条 dry-run 测试红在
        # `PermissionError: '/root/.ccr/ca-bundle.crt'`）。
        #
        # 探一个「众所周知的位置」**失败就等于这台机器没有它**，任何 OSError
        # 都一样——这条路只是猜，猜不中是常态。显式配的那条不同：那儿配错了
        # 要报，见上面。
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


def trust_local_proxy_ca(*, verbose: bool = True) -> str | None:
    """把代理的 CA 合进一份根证书里并让本进程用它。返回那份文件的路径。

    在 runner 上（没有那个 CA）返回 `None` 并且**一个字都不打**。

    ⚠️ **必须在 `import edge_tts` 之前调用。** edge-tts 在**模块导入那一刻**就
    `ssl.create_default_context(cafile=certifi.where())` 建好了 `_SSL_CTX`，
    之后再改 `certifi.where` 一点用都没有。两个调用点（`build_match_reel` 和
    `explainer`）的 `import edge_tts` 都在函数体里，所以从 CLI 入口调就够早。
    判据在 `test_挂代理CA要排在导入edge_tts之前`。
    """
    global _done
    if _done is not None:
        return _done or None
    ca = _extra_ca()
    if ca is None:
        _done = ""          # 记住「查过了，这台机器不需要」，别每次都翻磁盘
        return None

    import certifi  # noqa: PLC0415

    base = Path(certifi.where())
    merged = base.read_text(encoding="utf-8") + "\n" + ca.read_text(encoding="utf-8")
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE.write_text(merged, encoding="utf-8")

    # **三处都要设，因为三种客户端各认各的。** requests 认
    # `REQUESTS_CA_BUNDLE`，标准库的 `create_default_context()` 认
    # `SSL_CERT_FILE`，而 edge-tts 显式喂的是 `certifi.where()`。
    # 只设一处的样子是「有的能通有的不通」，比全都不通更难查。
    os.environ["SSL_CERT_FILE"] = str(_CACHE)
    os.environ["REQUESTS_CA_BUNDLE"] = str(_CACHE)
    certifi.where = lambda: str(_CACHE)   # type: ignore[assignment]

    if verbose:
        print(f"[出网] 挂上代理 CA（{ca}）→ {_CACHE}；本地也能合语音了")
    _done = str(_CACHE)
    return _done


def can_verify(host: str = "speech.platform.bing.com") -> tuple[bool, str]:
    """真握一次手，看这台机器现在验不验得过。**查产物，不查信号。**

    「设了环境变量」是信号，「TLS 握得上」才是产物——而这两件事分叉的时候
    （CA 过期、代理换了证书）没有任何东西会报错，只有下一次合语音会炸。
    """
    import socket  # noqa: PLC0415

    ctx = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE"))
    try:
        with socket.create_connection((host, 443), timeout=15) as sock, \
                ctx.wrap_socket(sock, server_hostname=host):
            return True, "握手通过"
    except Exception as exc:      # noqa: BLE0001 - 什么错都要如实报出来
        return False, f"{type(exc).__name__}: {exc}"
