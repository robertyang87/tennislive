"""tools/read_scoreboard.py —— MiniMax 读记分条（只测不联网半截）。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


def _tool():
    sys.path.insert(0, str(_TOOLS))
    import read_scoreboard as rs  # noqa: PLC0415

    return rs


def test_无key跳过出声(monkeypatch, capsys, tmp_path):
    rs = _tool()
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["read_scoreboard.py", "--dir", str(tmp_path)])
    assert rs.main() == 2
    assert "没配 MINIMAX_API_KEY" in capsys.readouterr().out


def test_没score图跳过出声(monkeypatch, capsys, tmp_path):
    rs = _tool()
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")
    monkeypatch.setattr(sys, "argv", ["read_scoreboard.py", "--dir", str(tmp_path)])
    assert rs.main() == 2
    assert "没有 score_*.jpg" in capsys.readouterr().out


def test_ask剥掉代码围栏(monkeypatch, tmp_path):
    rs = _tool()
    img = tmp_path / "s.jpg"
    img.write_bytes(b"fake-jpeg")

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *e):
            return False

        def read(self):
            return ('{"choices":[{"message":{"content":'
                    '"```json\\n[{\\"t\\": 13.7, \\"score\\": \\"1-2 15-30\\"}]\\n```"}}]}'
                    ).encode()

    captured = {}

    def fake_open(req, timeout):
        captured["url"] = req.full_url
        captured["data"] = __import__("json").loads(req.data)
        return FakeResp()

    monkeypatch.setattr(rs.urllib.request, "urlopen", fake_open)
    rows = rs._ask(img, "sk-test")
    assert rows == [{"t": 13.7, "score": "1-2 15-30"}], "要剥掉 ```json 围栏"
    # 确认 thinking disabled（和 DeepSeek 同一个形状）
    assert captured["data"]["thinking"] == {"type": "disabled"}
    assert captured["data"]["model"] == rs.MODEL
