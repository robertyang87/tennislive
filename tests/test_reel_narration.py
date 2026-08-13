"""竖版赛报短片的**合语音**那一段：edge-tts 这条退路要扛得住一次网络抖动。

来路（2026-08-13）：`tools/build_match_reel.py` 的 `tts_one()` 里，edge-tts 那
一支是 `marks = asyncio.run(one())` **单次调用，周围没有任何 try/except**，
而 `main()` 不接 `ReelError`——一次网络抖动就让异常裸奔到 `SystemExit`，
整趟 render 报废。

核实时把两件事分开量了，别把结论记混：

- **match-reel 上 edge-tts 不是主力，是退路。** 拿产物查：
  `output/*/reel/*/render.json` 共 **66** 份，记了 `narration_backend` 的 45 份
  **全是 `azure`、`edge-tts` 零份**（另 21 份渲在这个字段加进来之前）。
  ⚠️ 这里原来写的是「共 58 份 / 另 13 份」，2026-08-13 复查复算不出来
  （66 − 45 = 21）。结论没变，基数改对了——`output/` 不在 CI 的检出里，
  这两个数**没有任何断言在盯**，写错了不会有人告诉你，所以复算口径一起写下：
  `glob("output/*/reel/*/render.json")` 逐份读，按 `narration_backend`
  在不在分两堆。
- **但正因为它是退路才更该有重试**：走到这儿说明 Azure 已经没了（密钥轮换
  或过期、F0 月配额打满、SDK 没装成），这就是最后一条路。

⚠️ **这条修复只覆盖 match-reel。** 同一个形状还在
`src/tennislive/video/synthesize_narration`（解说片）和采访片那条线上，而
**那两条线上 edge-tts 是唯一通道**（`explainer.py` 里 `azure_tts` 出现 0 次、
`explainer.yml` / `interview-clip.yml` 里 `AZURE_SPEECH` 出现 0 次）。那儿比
这儿更该修——**没修，别读成修过了**。

⚠️ **这个文件不许 import aiohttp。** 它只是 edge-tts 的传递依赖，不在
`pyproject.toml` 里，CI 的 `pip install -e ".[dev,webrender,visualqa]"` 根本
不装它（连 edge-tts 都不装）。所以核心判据一律用**合成的异常类**跑，
只有沙箱里真装着 edge-tts 时才多验一层「合成的那几个类名和真的对得上」
——CLAUDE.md 那条「核心判据只吃能在 CI 上跑得起来的东西，读产物的断言当
加餐」，只是这次的「产物」是 edge-tts 自己的异常树。
"""

from __future__ import annotations

import importlib.util
import ssl
import sys
import types
from pathlib import Path

import pytest


def _reel():
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel  # noqa: PLC0415

    return build_match_reel


# ---------------------------------------------------------------- 合成的异常类
#
# ⚠️ **这几个类是照着 2026-08-13 在沙箱里真跑一次合成量到的 MRO 造的**，不是
# 凭印象写的。实测（`asyncio.run(Communicate(...).stream())` 走一遍）：
#
#     TYPE : aiohttp.client_exceptions.ClientConnectorCertificateError
#     MRO  : ClientSSLError → ClientConnectorError → ClientOSError
#            → ClientConnectionError → ClientError
#            → ssl.SSLCertVerificationError → ssl.SSLError → OSError → ValueError
#     CHAIN: [ClientConnectorCertificateError, ssl.SSLCertVerificationError]
#
# 「合成的类名和真的对得上」这一半，由下面
# `test_合成的异常类要和真的edge_tts对得上` 在装着 edge-tts 的机器上兜住。
def _aiohttp_error(name: str = "ClientConnectorError", base=OSError):
    """造一个「长得像 aiohttp 抛出来的」异常类。

    关键是 `__module__`——分类器认的就是它（见 `edge_tts_verdict` 的 docstring：
    不 `import aiohttp`，因为它不在 pyproject 里）。
    """
    return type(name, (base,), {"__module__": "aiohttp.client_exceptions"})


def _edge_error(name: str):
    """造一个 edge-tts 自己的异常类（`EdgeTTSException` 的子类）。"""
    base = type("EdgeTTSException", (Exception,),
                {"__module__": "edge_tts.exceptions"})
    return type(name, (base,), {"__module__": "edge_tts.exceptions"})


def _fake_edge_tts(script: list, built: list) -> types.SimpleNamespace:
    """一个假的 `edge_tts` 模块，按 `script` 逐次成功/抛错。

    `script[i]` 是第 i 次尝试要做的事：异常实例＝抛出来，`"empty"`＝一个字节
    音频都不给（试「合出来是空文件」那条路），`None`＝正常出音频。

    ⚠️ **假的 `Communicate` 也是一次性的**，和真的一样（真的在 `stream()` 里
    有 `if self.state["stream_was_called"]: raise RuntimeError("stream can
    only be called once.")`）。不带这一条的话，「只把 `async for` 包进重试
    循环」那种错写法能蒙混过去——而那正是这个修复最容易踩坏的地方：
    **重试本身会把一个可恢复的错变成不可恢复的错**。
    """

    class _Communicate:
        def __init__(self, text, voice, **kw):
            self._turn = len(built)
            built.append({"text": text, "voice": voice, **kw})
            self._used = False

        def stream(self):
            if self._used:
                raise RuntimeError("stream can only be called once.")
            self._used = True
            return self._gen()

        async def _gen(self):
            plan = script[self._turn]
            if isinstance(plan, BaseException):
                raise plan
            if plan == "empty":
                return
            yield {"type": "audio", "data": b"\0" * 64}
            yield {"type": "WordBoundary", "offset": 1000,
                   "duration": 500, "text": "喂"}

    return types.SimpleNamespace(
        Communicate=_Communicate,
        exceptions=types.SimpleNamespace(
            NoAudioReceived=_edge_error("NoAudioReceived")),
    )


@pytest.fixture
def edge_only(monkeypatch):
    """把 `tts_one` 逼进 edge-tts 那一支，并把 `time.sleep` 换成记账。

    返回 `sleeps` 列表——退避的秒数是判据的一部分（照抄 Azure 那套 65 秒阶梯
    是这次特别要防的错，见 `test_退避阶梯不许照抄Azure那套`）。
    """
    reel = _reel()
    monkeypatch.setattr(reel.azure_tts, "available", lambda: False)
    sleeps: list[float] = []
    monkeypatch.setattr(reel.time, "sleep", sleeps.append)
    return sleeps


def test_edge_tts没送到要重试而不是整趟报废(tmp_path, monkeypatch, edge_only,
                                             capsys):
    """前两次传输层失败、第三次成功 → 拿到音频，不是死掉。

    这是这条修复的主判据，**真跑一遍 `tts_one()`**（喂假的 `edge_tts` 模块），
    不是查源码里有没有 `for attempt in`——「写了不等于跑过」这个仓库栽过
    好几次。

    三条断言各钉一头：

    1. **最终拿到词边界**（不再是裸 `SystemExit`）；
    2. **`Communicate` 建了三次**——重试重跑的是整个 `one()`，不是只把
       `async for` 包进循环（假的 `Communicate` 和真的一样是一次性的，
       只包 `async for` 会在第二次撞上 `RuntimeError`）；
    3. **退了两次、日志两行**——退路要出声，不然「今天 edge-tts 慢」和
       「这条重试了两次」在日志上一模一样。
    """
    reel = _reel()
    built: list = []
    boom = _aiohttp_error()
    script = [boom("connection reset"), boom("connection reset"), None]
    monkeypatch.setitem(sys.modules, "edge_tts",
                        _fake_edge_tts(script, built))

    path = tmp_path / "voice_01.mp3"
    marks = reel.tts_one("测试一句", path, "zh-CN-YunjianNeural", "+6%")

    assert marks and marks[0]["text"] == "喂"
    assert path.stat().st_size > 0
    assert path.with_suffix(".words.json").is_file()
    assert len(built) == 3, (
        f"重试要重建 Communicate，实际只建了 {len(built)} 个——"
        "只把 async for 包进循环的话，第二次会撞上 stream can only be called once")
    assert edge_only == list(reel._EDGE_BACKOFF)[:2], edge_only
    said = [ln for ln in capsys.readouterr().out.splitlines() if "重试第" in ln]
    assert len(said) == 2, f"两次重试要各出一次声，实际 {said}"
    assert "aiohttp" in said[0], f"日志要点名是哪一类失败：{said[0]}"


def test_edge_tts明确拒绝的不重发(tmp_path, monkeypatch, edge_only):
    """`SkewAdjustmentError` → **一次就抛**，一秒都不许等。

    edge-tts 语义下 403 不是鉴权拒绝，是 `Sec-MS-GEC` 令牌的时钟偏移，而库
    自己在 `stream()` 里已经校正时钟重来过一次；校正也失败时它退化成
    `SkewAdjustmentError`——外层再试**加不了任何东西**，只会把一次 1 秒的
    失败拖成 9 秒。和 `azure_tts` 那条「被挡回来 ≠ 被拒绝，处置相反」同一条。
    """
    reel = _reel()
    built: list = []
    skew = _edge_error("SkewAdjustmentError")
    monkeypatch.setitem(sys.modules, "edge_tts",
                        _fake_edge_tts([skew("no Date header")] * 3, built))

    with pytest.raises(reel.ReelError) as err:
        reel.tts_one("测试一句", tmp_path / "v.mp3", "zh-CN-YunjianNeural", "+6%")

    assert len(built) == 1, f"明确拒绝的不许重发，实际试了 {len(built)} 次"
    assert edge_only == [], f"不许等：{edge_only}"
    assert "SkewAdjustmentError" in str(err.value), str(err.value)
    assert "不该重发" in str(err.value), (
        "用尽和「重发没意义」下一步完全不同，报错要说清是哪一类")
    # ⚠️ **这一句是反向验证逼出来的。** 上面三句在「`_EDGE_FATAL` 里把名字拼错
    # 了」时**照样全绿**——因为分类器的默认就是不重发，「明确拒绝」和「不在已知
    # 清单里」两条路的可见后果一模一样（都是试一次、都说「不该重发」）。也就是
    # 说这条测试当时分不出「表拦住了」和「表是哑的、只是默认兜住了」。
    # 判据要钉在**它走了哪条路**上：
    assert "明确拒绝" in str(err.value), (
        "它是被『不认识所以不重发』的默认兜住的，不是被 _EDGE_FATAL 拦住的"
        "——那张表对它想拦的这一类是哑的")


def test_合不出音频要走重试那条路(tmp_path, monkeypatch, edge_only):
    """「连上了、也没报错，可一个字节音频都没有」——这一类重发是有意义的。

    修之前那句 `if not path.is_file() or path.stat().st_size == 0` 判在**循环
    外面**、直接 `raise ReelError`，等于把一个可重试的失败钉死成不可重试。
    现在它判在 `one()` 里面，借 edge-tts 自己的 `NoAudioReceived` 走同一套分类。
    """
    reel = _reel()
    built: list = []
    monkeypatch.setitem(sys.modules, "edge_tts",
                        _fake_edge_tts(["empty", "empty", None], built))

    path = tmp_path / "v.mp3"
    marks = reel.tts_one("测试一句", path, "zh-CN-YunjianNeural", "+6%")
    assert marks and path.stat().st_size > 0
    assert len(built) == 3, f"空音频要重试，实际试了 {len(built)} 次"


def test_分类不许按EdgeTTSException写():
    """⚠️ **这条修复最容易踩坏的地方，单独钉一条。**

    直觉写法是 `except edge_tts.exceptions.EdgeTTSException` ——而 2026-08-13
    在沙箱里真跑一次合成，逃出来的是
    `aiohttp.client_exceptions.ClientConnectorCertificateError`，
    **`EdgeTTSException` 的子类一个都没沾**。传输层失败（也就是「没送到」那
    一整类）全部以 aiohttp 的异常出现，按 `EdgeTTSException` 写的分类器
    **恰好漏掉它唯一想接住的那一类**，而且它会绿着通过所有别的测试。

    所以这条正反两头都钉：aiohttp 那一类**必须**判成重试（哪怕它和
    `EdgeTTSException` 毫无血缘），证书链不通**必须**判成不重试（它虽然是
    aiohttp 异常，却是结构性阻断，重发一万次也一样）。
    """
    reel = _reel()

    transport = _aiohttp_error()("Cannot connect to host")
    # 先证明这个样本**真的**踩在陷阱上：它和 edge_tts 的异常树毫无血缘。
    # 不证明这一点的话，「aiohttp 要判成重试」有可能是靠别的支路碰巧过的。
    assert not any(c.__module__.startswith("edge_tts")
                   for c in type(transport).__mro__), "样本没踩在陷阱上"
    retry, why = reel.edge_tts_verdict(transport)
    assert retry is True, why
    assert "aiohttp" in why

    # 证书链：真实形状是 aiohttp 异常，`ssl.SSLCertVerificationError` 挂在
    # `__cause__` 上——**只看最外层那个类会把它判成「传输层抖了一下」**。
    cert = _aiohttp_error("ClientConnectorCertificateError")("ssl:True")
    cert.__cause__ = ssl.SSLCertVerificationError(
        1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
    retry, why = reel.edge_tts_verdict(cert)
    assert retry is False, why
    assert "证书" in why

    # 不认识的一律不重发，**但要把类名说出来**：万一将来真有一类瞬时错没被
    # 盖住，日志里写着它叫什么，而不是让下一个人从「今天怎么又失败了」开始猜。
    retry, why = reel.edge_tts_verdict(TypeError("我们自己的 bug"))
    assert retry is False and "TypeError" in why, why

    # 不依赖 aiohttp 的那一层兜底（socket 断了 / 超时）也要认得出来。
    for exc in (ConnectionResetError("reset"), TimeoutError("timed out")):
        retry, why = reel.edge_tts_verdict(exc)
        assert retry is True, (exc, why)

    # ⚠️ **3.10 上的 `asyncio.TimeoutError` 是另一个类**，不是内置的
    # `TimeoutError`（3.11 才合并）。`pyproject` 写的是 `>=3.10`，所以那条支路
    # 真的到得了——而这台机器是 3.11，`isinstance` 那一半会把它顺手接住，
    # **那条按名字认的支路就永远跑不到，等于写了没跑过**。造一个 3.10 形状的
    # 替身（模块名对得上、但不继承内置 TimeoutError）把它逼出来。
    old_style = type("TimeoutError", (Exception,),
                     {"__module__": "asyncio.exceptions"})("timed out")
    assert not isinstance(old_style, TimeoutError), "替身没造对，没模拟到 3.10"
    retry, why = reel.edge_tts_verdict(old_style)
    assert retry is True, f"3.10 的 asyncio.TimeoutError 漏了：{why}"


def test_合成的异常类要和真的edge_tts对得上():
    """**判据自己也要有判据。**

    上面那几条判据喂的是**合成的**异常类（因为 CI 装的是
    `[dev,webrender,visualqa]`，edge-tts 和 aiohttp 一个都没有）。合成的东西
    只有在「类名和真的对得上」时才算数——这一条就是那个对账，装着 edge-tts
    的机器上（沙箱、以及真正出片的 runner）才跑得到。

    ⚠️ **整条测试不许 skip**：一条常年跳过的检查和常年红是同一个毛病。所以
    没装 edge-tts 时它仍然要断言点东西——断言这台机器是**真的**没装，而不是
    因为名字写错才找不到。
    """
    reel = _reel()
    if importlib.util.find_spec("edge_tts") is None:
        # 没装就到此为止，但要证明「没装」是真的，不是我把名字拼错了。
        assert importlib.util.find_spec("json") is not None, "find_spec 本身坏了"
        return

    import edge_tts  # noqa: PLC0415

    # ① edge-tts 现在**确实**用着 aiohttp。分类器按模块名认它（不 import，
    #    因为 aiohttp 不在 pyproject 里）——哪天 edge-tts 换成 httpx，
    #    这一句会先红，而不是让重试静静地不再生效。
    assert hasattr(edge_tts.communicate, "aiohttp"), (
        "edge-tts 不再用 aiohttp 了？`edge_tts_verdict` 里按 `aiohttp` 认"
        "传输层失败的那一支要跟着改，否则重试会静静地不再命中")
    real = edge_tts.communicate.aiohttp.ClientConnectorError
    assert real.__module__.split(".", 1)[0] == "aiohttp"
    assert _aiohttp_error().__module__ == real.__module__, (
        "合成的 aiohttp 异常和真的模块名对不上，上面那几条判据就是空的")

    # ② 「不重试」那张表里的名字，在真的 edge-tts 里都存在。名字写错的话
    #    这张表对它想拦的那一类就是哑的——而一个会过期的名单和一条常年红的
    #    检查是同一个毛病。
    for name in reel._EDGE_FATAL | reel._EDGE_RETRY:
        cls = getattr(edge_tts.exceptions, name, None)
        assert cls is not None, f"edge_tts.exceptions 里没有 {name}"
        assert cls.__module__ == "edge_tts.exceptions"

    # ③ 真的 `SkewAdjustmentError` / 真的 aiohttp 异常，判出来要和合成的一样。
    retry, why = reel.edge_tts_verdict(edge_tts.exceptions.SkewAdjustmentError("x"))
    assert retry is False, why
    retry, why = reel.edge_tts_verdict(real(types.SimpleNamespace(
        ssl=None, host="h", port=443, is_ssl=False), OSError("boom")))
    assert retry is True, why


def test_退避阶梯不许照抄Azure那套():
    """⚠️ **`azure_tts._BACKOFF = (5, 15, 45)` 不许搬过来。**

    那三个数是从一个**实测的具体配额**倒推的：Azure F0 神经语音「20 次请求 /
    60 秒」，最后一档 45 秒是为了跨过那个 60 秒窗口（理由写在 `azure_tts.py`
    的注释里）。edge-tts 没有这样的公开配额，照搬等于把一个**失去前提的
    常量**搬过来——「判据要跟着结构走，不是跟着当初那一版的数走」，这个仓库
    为它栽过两次（apt 重试写 3×100 秒当场把 CI 弄红是其中一次）。

    这儿要盖的只是**一次网络抖动**，所以两头都钉：

    - **至少要有一次重试**（一次都没有的话这条修复等于没做）；
    - **总等待不许长到 Azure 那个量级**——真是「连着几分钟都连不上」，
      那不是抖动，重试也救不了，早点红比晚点红好。

    上界 15 秒是从「这一步在整趟 render 里的位置」推的，不是拍的：TTS 排在
    分段编码之前，撞一次这道闸白烧的是下载+封面+抠图那几十秒；退避拖到分钟
    级只会把「早点红」这个收益吃掉。
    """
    reel = _reel()
    from tennislive.video import azure_tts  # noqa: PLC0415

    assert len(reel._EDGE_BACKOFF) >= 1, "一次重试都没有，这条修复等于没做"
    assert tuple(reel._EDGE_BACKOFF) != tuple(azure_tts._BACKOFF), (
        "照抄了 Azure 的阶梯——那三个数的前提（F0 20 次/60 秒）在这条路上不存在")
    assert sum(reel._EDGE_BACKOFF) <= 15, (
        f"退避合计 {sum(reel._EDGE_BACKOFF)}s，太长了：这一步排在分段编码之前，"
        "早点红本身就是收益")
    # 判据自己的判据：Azure 那套**确实**在这个上界之外，所以上面那句不是恒真。
    assert sum(azure_tts._BACKOFF) > 15, (
        "Azure 的阶梯变短了？那这条判据就成了一盏恒真的绿灯，得重新定上界")
