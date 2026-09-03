"""合语音——全仓库**只有这一份**（review 路线 ⑥ 第二刀，2026-09-03）。

在这之前有两套：`build_match_reel.tts_one`（Azure 优先，退 edge-tts 带重试和
内容缓存）和 `explainer.synthesize_narration`（只有 edge-tts，一次重试都没有、
不缓存）——采访线的解读卡口播走的是后者。「同一个形状还在
`explainer.synthesize_narration`，没修，别当成修过了」那句注释（下面原样留着）
写了三周，现在兑现：三条线都走这儿。

判据 tests/test_tts.py（缓存 / 错误类型 / 要风格没 Azure 必须报错 / 出处只有
一份——`edge_tts.Communicate(` 不许再出现在三条出片线里）＋
tests/test_reel_narration.py（edge-tts 重试的那一整套，喂假模块真跑）。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from . import azure_tts


class TTSError(RuntimeError):
    """缺省的错误类型；各条线传自己的 `error=` 进来。"""


# ⭐ 2026-08-13：**edge-tts 这条路原来一次重试都没有**（`asyncio.run(one())`
# 单次调用、周围没有任何 try/except），补上。核实时把两件事分开量了：
#
# · **match-reel 上 edge-tts 不是主力，是退路。** 拿产物查，不是推的：
#   `output/*/reel/*/render.json` 共 **66** 份，记了 `narration_backend` 的
#   **45 份全是 `azure`、`edge-tts` 零份**（另 21 份渲在这个字段加进来之前）。
#   ⚠️ 2026-08-13 复查时这里原来写的是「共 58 份 / 另 13 份」——**那个数复算
#   不出来**（66 − 45 = 21，不是 13）。结论那一半（记了的全是 azure、
#   edge-tts 零份）复算得上，只有基数错了。带数字的注释过期或者算错的时候
#   不吭声，所以口径写在这儿：`glob("output/*/reel/*/render.json")` 逐份读，
#   按 `narration_backend` 在不在分两堆。
#   `tts_one` 第一句就是 `if azure_tts.available()`，`match-reel.yml` 三个步骤
#   都注了 AZURE_SPEECH_*、SDK 也真装了。
# · **但正因为它是退路才更该有重试。** 走到这儿说明 Azure 已经没了（密钥轮换
#   或过期、F0 月配额打满、SDK 没装成），**这就是最后一条路**；而 `main()`
#   不接 `ReelError`，一次网络抖动就让异常裸奔到 `SystemExit`，整趟 render
#   报废（这个位置在分段编码之前，所以烧掉的是下载+封面+抠图那几十秒，
#   不是最贵的编码——但整趟要重跑，含约 97 秒的 checkout/apt/pip 准备）。
# · ~~⚠️ **同一个形状还在 `video/explainer.py:synthesize_narration`，而那条线上
#   edge-tts 是唯一通道**……那儿比这儿更该修，只是不在这次的改动范围里——
#   **没修，别当成修过了**。~~ **2026-09-03 兑现了**：解说片和采访线的
#   `synthesize_narration` 现在逐段调这儿的 `tts_one`，重试、缓存、Azure 优先
#   三样一起拿到。⚠️ 那两条线的工作流仍然没配 `AZURE_SPEECH_*`，所以生产上
#   照旧是 edge-tts——变的是「有重试」，不是「换后端」。
#
# ⚠️ **别照抄 `azure_tts._BACKOFF = (5, 15, 45)`。** 那三个数是从一个**实测的
# 具体配额**倒推的（F0 神经语音「20 次请求 / 60 秒」，最后一档 45 秒是为了跨过
# 那个 60 秒窗口，理由写在 `azure_tts.py` 的注释里）。edge-tts 没有这样的公开
# 配额，照搬等于把一个**失去前提的常量**搬过来——「判据要跟着结构走，不是跟着
# 当初那一版的数走」。这儿要盖的只是**一次网络抖动**，两次、合计 8 秒够了；
# 真是「连着几分钟都连不上」，那不是抖动，重试也救不了，早点红比晚点红好。
EDGE_BACKOFF = (2.0, 6.0)

# edge-tts **自己那几个异常**里，哪些是「服务端明确回了个我们不认的东西」。
# `SkewAdjustmentError` 尤其要点名：它正是 403 时钟校正失败之后的产物，见下面
# `edge_tts_verdict` 的 docstring。
_EDGE_FATAL = frozenset({"SkewAdjustmentError", "UnexpectedResponse",
                         "UnknownResponse"})
# 「握上了又断了」「一个字节音频都没收到」——这两类重发是有意义的。
_EDGE_RETRY = frozenset({"WebSocketError", "NoAudioReceived"})


def _exc_chain(exc: BaseException) -> list[BaseException]:
    """异常自己 + 它的 `__cause__` / `__context__` 链，去环。

    ⚠️ **只看最外层那个类是不够的**：2026-08-13 在这台沙箱里真跑了一次合成，
    最外层是 `aiohttp...ClientConnectorCertificateError`，而真正说明「这是
    结构性阻断不是抖动」的 `ssl.SSLCertVerificationError` 挂在 `__cause__` 上。
    """
    seen: set[int] = set()
    chain: list[BaseException] = []
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        chain.append(cur)
        cur = cur.__cause__ or cur.__context__
    return chain


def edge_tts_verdict(exc: BaseException) -> tuple[bool, str]:
    """这次 edge-tts 失败该不该重发。返回 `(要不要重试, 判据)`。

    **按异常类型判，不按错误文本判。** `azure_tts._classify` 走的是子串匹配，
    那是因为 Azure SDK 把一切都压成一句 `cancellation_details` 字符串；
    这条路没有那个限制，类型摆在那儿，没必要退回猜字符串。

    ⚠️ **最容易踩的坑：按 `except edge_tts.exceptions.EdgeTTSException` 写。**
    2026-08-13 实测（这台沙箱，真跑一次 `Communicate(...).stream()`），逃出来的是

        aiohttp.client_exceptions.ClientConnectorCertificateError
        MRO: ClientSSLError → ClientConnectorError → ClientOSError
             → ClientConnectionError → ClientError → ssl.SSLCertVerificationError
             → ssl.SSLError → OSError → ValueError → Exception

    ——**`EdgeTTSException` 的子类一个都没沾**。传输层失败（也就是「没送到」
    那一整类）全部以 aiohttp 的异常出现，按 `EdgeTTSException` 写的分类器
    **恰好漏掉它唯一想接住的那一类**，而且它会绿着通过所有测试。

    ⚠️ **403 不在任何一张表里，是故意的。** edge-tts 语义下 403 不是鉴权拒绝，
    是 `Sec-MS-GEC` 令牌的时钟偏移；库自己在 `stream()` 里
    （`edge_tts/communicate.py`，`DRM.handle_client_response_error` 读响应头
    `Date` 校正 skew）已经重来过一次，外层再试**加不了任何东西**。校正失败时
    它退化成 `SkewAdjustmentError`——那一条在「不重试」那张表里。
    ⚠️ 这一段是**读 edge_tts 源码推的，不是我今天量出来的**：这台沙箱到不了
    WSS 端点（卡在 TLS，见上面的实测），复现不了 403。

    **判据宁可窄，不可宽：只有点名的那几类才重试，其余一律不重试**——
    我们自己的 `TypeError`、装少了包的 `ImportError`，重发三次只是多烧 8 秒，
    外加两行说「被挡回来」的**假话**（这个仓库里「喊错了比不吭声更坏」）。
    代价是万一将来真有一类瞬时错没被盖住会被判成不重试，所以**两个方向都要
    把类名打出来**：日志里会写着它叫什么，而不是让下一个人从「今天怎么又失败
    了」开始猜。

    ⚠️ **aiohttp 是按模块名认的，没有 `import aiohttp`**：它不在
    `pyproject.toml` 里（只是 edge-tts 的传递依赖），而「自己 import 的就自己
    声明」——`certifi` 那条注释就是为这个写的。按名字认还顺带把「edge-tts 哪天
    换掉 aiohttp」变成一次看得见的失败：判据里钉了
    `edge_tts.communicate` 必须真的用着 aiohttp。
    """
    import ssl  # noqa: PLC0415

    chain = _exc_chain(exc)
    name = f"{type(exc).__module__}.{type(exc).__qualname__}"

    # ① 证书链不通：结构性阻断，重试一万次也一样。**必须排在 ② 前面**——
    #    它本身是个 aiohttp 异常，排在后面会被当成「传输层抖了一下」白试两次。
    if any(isinstance(e, ssl.SSLCertVerificationError) for e in chain):
        return False, f"{name}：证书链不通，这是结构性阻断不是抖动"

    kinds = {f"{c.__module__}.{c.__qualname__}"
             for e in chain for c in type(e).__mro__}
    roots = {k.split(".", 1)[0] for k in kinds}
    edge_names = {k.rsplit(".", 1)[-1] for k in kinds if k.startswith("edge_tts.")}

    # ② edge-tts 明确说「这个响应我不认」／「时钟校正也没救回来」。
    hit = sorted(edge_names & _EDGE_FATAL)
    if hit:
        return False, f"{name}：edge-tts 明确拒绝（{'、'.join(hit)}），重发没有意义"
    # ③ 传输层失败——「没送到」那一整类，重发是安全的，也是唯一的出路。
    if "aiohttp" in roots:
        return True, f"{name}：传输层（aiohttp）失败，没送到"
    hit = sorted(edge_names & _EDGE_RETRY)
    if hit:
        return True, f"{name}：{'、'.join(hit)}，没收到音频"
    # ④ 兜一层不依赖 aiohttp 的：socket 断了 / 超时。
    #    ⚠️ `asyncio.TimeoutError` **只有 3.11 起**才是内置的 `TimeoutError`
    #    的别名；3.10 上它是另一个类（`asyncio.exceptions.TimeoutError`），
    #    而 `pyproject` 写的是 `requires-python = ">=3.10"`。只写
    #    `isinstance(e, TimeoutError)` 的话，这条兜底在 3.10 上是**半哑的**，
    #    而它哑掉的样子和「今天没超时」一模一样。按名字补上那一支，
    #    不为此 import asyncio 的异常模块。
    if any(isinstance(e, (TimeoutError, ConnectionError)) for e in chain) \
            or "asyncio.exceptions.TimeoutError" in kinds:
        return True, f"{name}：连接断了或超时，没送到"
    return False, f"{name}：不在已知的「没送到」清单里，不重发"


def tts_content_key(text: str, voice: str, rate: str, pitch: str,
                     style: str, styledegree: str, lead_pause: float) -> str:
    """TTS 内容缓存键：同文同参数 = 同一段音频，可跨趟复用。

    ⚠️ **键按内容算，不按路径/序号算。** 旁白 text 没变、只改封面/字幕/换段
    顺序时，voice 不该重合成——「改了字」和「没改字」只有内容 hash 分得开
    （仓库里「源片键按 URL 算」是同一个形状的教训）。分隔符用 ASCII 的
    Unit Separator（0x1f），防「text 尾 + voice 头」拼出一个跨字段碰撞。
    """
    payload = "\x1f".join([text, voice, rate, pitch, style, styledegree,
                           str(lead_pause)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def tts_one(text: str, path: Path, voice: str, rate: str,
            pitch: str = "+0Hz", style: str = "", styledegree: str = "",
            lead_pause: float = 0.0, *, synth=None,
            error: type[Exception] = TTSError) -> list[dict]:
    """合一条语音，落盘并返回词边界（带内容缓存：同文同参数不重合成）。

    全仓库只有这一份（review 路线 ⑥ 第二刀，2026-09-03）：reel / 解说片 / 采访
    三条线都走它。`synth` 是「缓存外真正合成的那半截」，缺省 `_tts_one_uncached`
    ——调用方要打桩就从这儿递进来（reel 的判据就是这么钉缓存的）；`error` 是
    失败时抛哪一类（各条线各有各的错误类型，报错正文一个字不变）。
    """
    key = tts_content_key(text, voice, rate, pitch, style, styledegree,
                          lead_pause)
    cache_dir = Path(os.environ.get(
        "TENNISLIVE_TTS_CACHE",
        str(Path.home() / ".cache" / "tennislive-tts")))
    cached_mp3 = cache_dir / f"{key}.mp3"
    cached_marks = cache_dir / f"{key}.json"
    if cached_mp3.is_file() and cached_marks.is_file():
        print(f"[TTS] 命中缓存 {key[:10]}（{len(text)} 字），不重合成")
        shutil.copyfile(cached_mp3, path)
        return json.loads(cached_marks.read_text(encoding="utf-8"))
    marks = (synth or _tts_one_uncached)(text, path, voice, rate, pitch, style,
                                         styledegree, lead_pause, error=error)
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, cached_mp3)
        cached_marks.write_text(json.dumps(marks, ensure_ascii=False),
                                encoding="utf-8")
    except OSError:
        # 缓存写失败不该把整条片子带崩——缓存是加速，不是正确性。
        pass
    return marks


def _tts_one_uncached(text: str, path: Path, voice: str, rate: str,
                      pitch: str = "+0Hz", style: str = "", styledegree: str = "",
                      lead_pause: float = 0.0, *,
                      error: type[Exception] = TTSError) -> list[dict]:
    """真正跑合成的那半截（`tts_one` 的缓存外逻辑）。"""
    # **配了 Azure 就走 Azure。** 同一把嗓子（`zh-CN-YunjianNeural`），多出
    # 十个情绪风格和真 `<break>`——两条路 2026-08-04 在 runner 上并排探过
    # （run 30884267406 / 30892017944）。词边界单位已经在 `azure_tts` 里对齐到
    # 100ns，字幕那条线一个字不用改。
    if azure_tts.available():
        print(f"[TTS] Azure（风格 {style or '无'}）")
        return azure_tts.synthesize(
            text, path, voice=voice, rate=rate, pitch=pitch, style=style,
            styledegree=styledegree, lead_pause=lead_pause)
    # ⚠️ **spec 明确要了情绪风格却没有 Azure，必须报错**：悄悄退回 edge-tts
    # 等于发一条和 spec 说的不一样的片子，而且不吭声——这个仓库最常见的那种坏。
    if style or lead_pause:
        raise error(
            f"这一段要 `voice.style={style or '—'}` / `lead_pause="
            f"{lead_pause or '—'}`，而它们**只有 Azure 那条路有**"
            f"（Edge 免费端点对 express-as 和 break 一律拒绝，实测 run "
            f"30884267406）。\n当前不可用：{azure_tts.why_unavailable()}\n"
            "两条出路：把这两个键从 spec 里去掉（退回只调语速音高），"
            "或者配好 AZURE_SPEECH_KEY / AZURE_SPEECH_REGION 再渲。")

    import asyncio

    import edge_tts

    async def one() -> list[dict]:
        marks: list[dict] = []
        with path.open("wb") as fh:
            stream = edge_tts.Communicate(
                text, voice, rate=rate, pitch=pitch,
                boundary="WordBoundary").stream()
            async for chunk in stream:
                if chunk.get("type") == "audio" and chunk.get("data"):
                    fh.write(chunk["data"])
                elif chunk.get("type") in ("WordBoundary", "SentenceBoundary"):
                    marks.append({"offset": chunk.get("offset", 0),
                                  "duration": chunk.get("duration", 0),
                                  "text": chunk.get("text", "")})
        if not path.is_file() or path.stat().st_size == 0:
            # 「连上了、也没报错，可一个字节音频都没有」——这一类重发是有意义的，
            # 所以判在循环**里面**，并且借 edge-tts 自己那个异常，好走同一套分类
            # （`NoAudioReceived` 在 `_EDGE_RETRY` 里）。原来它判在循环外面、
            # 直接 `raise ReelError`，等于把一个可重试的失败钉死成不可重试。
            raise edge_tts.exceptions.NoAudioReceived(
                f"TTS 没出音频：{path.name}")
        return marks

    # ⚠️ **重试要重跑整个 `one()`，不能只把 `async for` 包进循环。**
    # `Communicate.stream()` 有一次性标志（`edge_tts/communicate.py`：
    # `if self.state["stream_was_called"]: raise RuntimeError(
    # "stream can only be called once.")`），第二次直接抛 `RuntimeError`
    # ——**那样重试本身会把一个可恢复的错变成不可恢复的错**，而且它报出来的
    # 样子跟服务端出问题一模一样。每次重来都得新建一个 `Communicate`。
    # `path.open("wb")` 是截断打开，所以上一次失败留下的半截 mp3 会被这一次
    # 盖掉，拼不出一个坏音频。
    marks: list[dict] = []
    for attempt in range(len(EDGE_BACKOFF) + 1):
        try:
            marks = asyncio.run(one())
            break
        except Exception as exc:                       # noqa: BLE001
            retry, why = edge_tts_verdict(exc)
            if not retry or attempt == len(EDGE_BACKOFF):
                # **用尽了也要说清是哪一类**：抖了半天和「这个错重发没意义」，
                # 下一步完全不同。两个方向都出声——只在失败时出声的检查，
                # 没法证明它成功过。
                tail = (f"重试 {attempt} 次仍然没送到"
                        if retry else "判定为不该重发")
                raise error(
                    f"edge-tts 合成失败：{path.name}　「{text[:24]}…」\n"
                    f"判据：{why}｜{tail}") from exc
            pause = EDGE_BACKOFF[attempt]
            print(f"[TTS] edge-tts 没送到（{why}），{pause:.0f}s 后重试第 "
                  f"{attempt + 1}/{len(EDGE_BACKOFF)} 次：「{text[:18]}…」")
            time.sleep(pause)
    path.with_suffix(".words.json").write_text(
        json.dumps(marks, ensure_ascii=False), encoding="utf-8")
    return marks
