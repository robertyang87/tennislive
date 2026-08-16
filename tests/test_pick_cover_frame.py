"""tools/pick_cover_frame.py —— MiniMax 视觉按「情绪对不对题」挑封面帧。

只测**不联网**的部分：高清闸拒低清帧并出声、全低清非零退出、无密钥时不静默、
请求 payload 的 schema（多图 image_url + thinking disabled）。真调 MiniMax 不测。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


def _tool():
    sys.path.insert(0, str(_TOOLS))
    import pick_cover_frame as pcf  # noqa: PLC0415

    return pcf


def _img(path: Path, w: int, h: int) -> Path:
    from PIL import Image  # noqa: PLC0415
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (w, h), (120, 160, 200)).save(path)
    return path


def test_hd_gate拒掉短边不够高清的帧(tmp_path):
    pcf = _tool()
    ok = _img(tmp_path / "hd.jpg", 1080, 1440)        # 竖版海报尺寸，过闸
    small = _img(tmp_path / "small.jpg", 640, 480)    # 短边 480，拒
    tiny = _img(tmp_path / "tiny.jpg", 200, 200)      # 拒

    keep, drop = pcf.hd_gate([ok, small, tiny])
    assert keep == [ok]
    assert [(p.name, why) for p, why in drop] == [
        ("small.jpg", "短边 480px 不够高清（要 ≥ 1080）"),
        ("tiny.jpg", "短边 200px 不够高清（要 ≥ 1080）"),
    ]


def test_hd_gate读不出尺寸也不静默放过(tmp_path):
    pcf = _tool()
    bogus = tmp_path / "not_an_image.jpg"
    bogus.write_text("这不是一张图", encoding="utf-8")
    keep, drop = pcf.hd_gate([bogus])
    assert keep == []
    assert len(drop) == 1 and drop[0][1].startswith("读不出尺寸")


def test_main全低清非零退出并说去拿真实照片(tmp_path, capsys):
    pcf = _tool()
    small = _img(tmp_path / "small.jpg", 640, 480)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-dummy")
    monkeypatch.setattr(sys, "argv", [
        "pick_cover_frame.py", "--frames", str(small),
        "--angle", "逆转：决胜盘二比五落后连救五赛点"])
    rc = pcf.main()
    assert rc == 3
    out = capsys.readouterr().out
    assert "去拿真实照片" in out and "短边 480px" in out, (
        "全低清必须非零退出并明说去拿真实照片，不许静默挑一张软的")


def test_main无密钥跳过并出声(tmp_path, capsys):
    pcf = _tool()
    hd = _img(tmp_path / "hd.jpg", 1080, 1440)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", [
        "pick_cover_frame.py", "--frames", str(hd), "--angle", "逆转"])
    rc = pcf.main()
    assert rc == 2
    assert "没配 MINIMAX_API_KEY" in capsys.readouterr().out


def test_pick请求schema钉死多图与thinking_disabled(tmp_path, monkeypatch):
    pcf = _tool()
    a = _img(tmp_path / "a.jpg", 1080, 1440)
    b = _img(tmp_path / "b.jpg", 1080, 1440)
    captured = {}

    class _FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            import json
            return json.dumps({"choices": [{"message": {"content": "2"}}]}).encode()

    def fake_open(req, timeout):
        captured["url"] = req.full_url
        captured["data"] = __import__("json").loads(req.data)
        captured["timeout"] = timeout
        return _FakeResp()

    monkeypatch.setattr(pcf.urllib.request, "urlopen", fake_open)
    idx = pcf.pick([a, b], "逆转：扛住那一刻", "sk-test")

    assert idx == 1
    assert captured["url"] == pcf.ENDPOINT
    payload = captured["data"]
    assert payload["model"] == pcf.MODEL
    assert payload["thinking"] == {"type": "disabled"}
    content = payload["messages"][0]["content"]
    assert content[0]["type"] == "text"
    assert "逆转：扛住那一刻" in content[0]["text"]
    imgs = [c for c in content if c["type"] == "image_url"]
    assert len(imgs) == 2, "候选帧要作为多图 image_url 一次喂进去"
    for c in imgs:
        assert c["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_pick答不出合法序号返回None不猜(monkeypatch, tmp_path):
    pcf = _tool()
    a = _img(tmp_path / "a.jpg", 1080, 1440)

    class _FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return '{"choices": [{"message": {"content": "都不错"}}]}'.encode()

    monkeypatch.setattr(pcf.urllib.request, "urlopen",
                        lambda req, timeout: _FakeResp())
    assert pcf.pick([a], "夺冠：捧杯", "sk-test") is None
