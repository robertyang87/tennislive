"""原生 Edge 传输回归：不覆盖新端点，代理真正传到合成请求。"""
from __future__ import annotations

import sys
import types

import pytest

from tennislive.video import tts


@pytest.mark.parametrize("endpoint", [
    "wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1?TrustedClientToken=token",
    "wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v2?key=future",
    "wss://custom.example/tts?key=explicit",
])
def test_only_migrate_known_stock_endpoint(monkeypatch, endpoint):
    package = types.ModuleType("edge_tts")
    package.__path__ = []
    communicate = types.ModuleType("edge_tts.communicate")
    constants = types.ModuleType("edge_tts.constants")
    communicate.WSS_URL = constants.WSS_URL = endpoint
    constants.TRUSTED_CLIENT_TOKEN = "token"
    package.communicate, package.constants = communicate, constants
    for name, module in [("edge_tts", package),
                         ("edge_tts.communicate", communicate),
                         ("edge_tts.constants", constants)]:
        monkeypatch.setitem(sys.modules, name, module)
    tts._point_edge_tts_at_live_host()
    expected = (
        "wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1"
        "?Ocp-Apim-Subscription-Key=token"
        if "speech.platform.bing.com" in endpoint else endpoint
    )
    assert communicate.WSS_URL == constants.WSS_URL == expected


@pytest.mark.parametrize("variable", ["HTTPS_PROXY", "https_proxy", None])
def test_native_edge_request_uses_configured_proxy(tmp_path, monkeypatch, variable):
    calls = []

    class Communicate:
        def __init__(self, text, voice, **kwargs):
            calls.append((text, voice, kwargs))

        async def stream(self):
            yield {"type": "audio", "data": b"mock audio"}
            yield {"type": "WordBoundary", "text": "测试", "offset": 0,
                   "duration": 1000}

    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(
        Communicate=Communicate))
    monkeypatch.setattr(tts.azure_tts, "available", lambda: False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("https_proxy", raising=False)
    if variable:
        monkeypatch.setenv(variable, "http://proxy.example:8080")
    audio = tmp_path / "probe.mp3"
    marks = tts._tts_one_uncached("测试", audio, "voice", "+6%", "+0Hz")
    expected = {"rate": "+6%", "pitch": "+0Hz", "boundary": "WordBoundary"}
    if variable:
        expected["proxy"] = "http://proxy.example:8080"
    assert calls == [("测试", "voice", expected)]
    assert audio.read_bytes() == b"mock audio"
    assert marks == [{"text": "测试", "offset": 0, "duration": 1000}]
