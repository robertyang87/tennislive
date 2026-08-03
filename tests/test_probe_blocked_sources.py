"""补中间证书那条路的判据。

背景（CLAUDE.md 里那条「『取不到』有好几种，要让接口自己说是哪一种」）：
阿拉木图的官方相册在 `ktf.kz`，它**只发叶子证书、不带中间证书**。urllib 把这
件事报成 `URLError`——和「这台主机连不上」一模一样，于是我照着报错写了
「从两个完全不同的网络都到不了」，错了三天。

`fetch()` 现在会补一张 AIA 指的中间证书再重试。**这是最容易被写成安全漏洞的
那种修法**，所以判据盯的是「它有没有放松校验」，不是「它能不能取到图」：

1. 只有链不完整（verify_code 20/21）才去补。过期、主机名对不上、自签
   一律照旧失败——那些是证书本身有问题，补中间证书救不了也不该救
2. 补进来的中间证书**必须自己能挂到已受信的根上**，挂不上就不用（fail closed）
3. 不校验的连接只许用来**读**证书，不许拿去传数据

三条都反向验证过。真实世界的对照实验记在这儿，省得下次重跑：

    expired / wrong.host / self-signed / untrusted-root .badssl.com  → 照旧失败，连补都不补
    incomplete-chain.badssl.com  → 补了，但它的中间证书挂不到可信根上 → 拒绝
    ktf.kz                       → 补上（Thawte TLS RSA CA G1 → DigiCert Global Root G2）→ 200
"""

from __future__ import annotations

import ast
import importlib.util
import re
import ssl
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tools" / "probe_blocked_sources.py"


def _load():
    spec = importlib.util.spec_from_file_location("probe_blocked_sources", PROBE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _a_real_certificate_pem() -> str:
    """随便拿一张**能被解析**的证书。

    只用来喂 `load_verify_locations` / `create_default_context`，验的是
    「返回的 context 有没有被调松」，跟这张证书是谁签的无关。
    """
    for cand in (ssl.get_default_verify_paths().cafile,
                 "/etc/ssl/certs/ca-certificates.crt",
                 "/usr/lib/ssl/cert.pem",
                 "/etc/pki/tls/certs/ca-bundle.crt"):
        if cand and Path(cand).exists():
            text = Path(cand).read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
                          text, re.DOTALL)
            if m:
                return m.group(0) + "\n"
    raise AssertionError(
        "这台机器上一张系统证书都找不到——判据的主语没了。"
        "不要把这条测试改成 skip：一条常年跳过的检查和常年红是同一个毛病。")


def _url_error(verify_code: int | None, message: str = "boom"):
    """造一个带 verify_code 的 URLError，跟 urllib 真实抛的形状一样。"""
    if verify_code is None:
        return urllib.error.URLError(OSError(message))
    reason = ssl.SSLCertVerificationError(message)
    reason.verify_code = verify_code
    reason.verify_message = message
    return urllib.error.URLError(reason)


@pytest.mark.parametrize(("code", "should_try"), [
    (20, True),    # unable to get local issuer certificate —— 就是它
    (21, True),    # unable to verify the first certificate
    (10, False),   # 证书过期
    (18, False),   # 自签
    (19, False),   # 自签根在链里
    (62, False),   # 主机名对不上
    (None, False),  # 压根不是证书问题（DNS/连不上）
])
def test_只有链不完整才去补中间证书(monkeypatch, code, should_try):
    """反向验证的那一半在这儿：**过期和主机名对不上不许被绕过去**。

    这是这条修法唯一真正危险的地方——「补一张证书再重试」写宽一点点，
    就变成「证书有毛病就重试到过为止」。
    """
    module = _load()
    tried = []

    def _never_opens(*_args, **_kwargs):
        raise _url_error(code)

    monkeypatch.setattr(module.urllib.request, "urlopen", _never_opens)
    monkeypatch.setattr(module, "_aia_completed_context",
                        lambda host, port=443: tried.append(host))

    status, _detail, body = module.fetch("https://example.invalid/x")

    assert body == b""
    assert bool(tried) is should_try, (
        f"verify_code={code} 时{'应该' if should_try else '不该'}去补中间证书，"
        f"实际 {'补了' if tried else '没补'}")
    if not should_try:
        assert status.startswith("ERR"), "不补的那一支要照旧把失败报出来"


def test_中间证书挂不到已受信的根上就不许采用(monkeypatch, tmp_path):
    """闸①：AIA 只是个线索，取回来的东西还要自己过一遍校验。

    挂不上就返回 None（宁可报「取不到」），**不是**「那就先信着」。
    badssl 的 incomplete-chain 真机上走的正是这一支。
    """
    module = _load()
    pem = _a_real_certificate_pem()
    bundle = tmp_path / "ca.pem"
    bundle.write_text(pem, encoding="utf-8")
    monkeypatch.setenv("SSL_CERT_FILE", str(bundle))

    monkeypatch.setattr(module, "_leaf_cert_der", lambda host, port=443: b"DER")
    monkeypatch.setattr(module, "_aia_ca_issuer_url", lambda der: "http://ca.example/int.crt")

    class _Resp:
        def read(self):
            return pem.encode()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *a, **k: _Resp())

    verdict = {"rc": 1}

    class _Done:
        def __init__(self, rc):
            self.returncode, self.stdout, self.stderr = rc, b"error 20 at 0 depth", b""

    def _fake_run(cmd, **_kwargs):
        if cmd[:2] == ["openssl", "x509"]:
            out = cmd[cmd.index("-out") + 1]
            Path(out).write_text(pem, encoding="utf-8")
            return _Done(0)
        if cmd[:2] == ["openssl", "verify"]:
            return _Done(verdict["rc"])
        return _Done(0)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    assert module._aia_completed_context("h.example") is None, \
        "openssl verify 说这张中间证书挂不上，就不许拿它去建 context"

    # 反过来：挂得上的时候要真的给出 context，而且**一项都没调松**。
    # 少了这一半，上面那条断言可能是「它永远返回 None」——恒真的绿灯。
    verdict["rc"] = 0
    ctx = module._aia_completed_context("h.example")
    assert ctx is not None, "挂得上却不给 context，那这条路等于没修"
    assert ctx.verify_mode == ssl.CERT_REQUIRED, "校验模式被调松了"
    assert ctx.check_hostname is True, "主机名校验被关掉了"


def test_不校验的连接只许用来读证书():
    """闸③是个**位置**判据：只测行为拦不住「有人把它挪去传数据」。

    `_create_unverified_context()` 在这个模块里只该出现一次，而且只能在
    `_leaf_cert_der` 里面——那一步只 `getpeercert()`，一个字节的正文都不读。
    """
    tree = ast.parse(PROBE.read_text(encoding="utf-8"))
    where = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for inner in ast.walk(node):
            if (isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Attribute)
                    and inner.func.attr == "_create_unverified_context"):
                where.append(node.name)
    assert where == ["_leaf_cert_der"], (
        f"不校验的连接出现在 {where or '（一处都没有？那这条判据的主语没了）'}，"
        "只允许 _leaf_cert_der 用它读证书")
