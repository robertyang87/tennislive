"""WTA 官方头像的后缀（tools/fetch_official_headshot.py）。

2026-09-22：这个 blob 上 `.jpg` 和 `.png` 两种后缀都有货，**没有规律**——
布兹科娃 320983 是 `.jpg`，卡尔塔尔 329918 只有 `.png`。原来只拼 `.jpg`，
于是后者一律报 `404 The specified blob does not exist`，**而那句话和
「这个人没有官方头像」长得一模一样**（CLAUDE.md「空结果 ≠ 不存在」），
`bartunkova-charaeva` 那条 spec 的 `_no_stats_why` 就是据此写的。
"""
from __future__ import annotations

import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import fetch_official_headshot as F  # noqa: E402

# 一张真 PNG（多色，过得了「不是占位剪影」那道颜色数判据）。
_PNG = None


def _real_png_bytes() -> bytes:
    global _PNG
    if _PNG is None:
        from io import BytesIO
        from random import Random

        from PIL import Image
        rnd = Random(0)
        im = Image.new("RGB", (40, 40))
        im.putdata([(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
                    for _ in range(40 * 40)])
        buf = BytesIO()
        im.save(buf, format="PNG")
        _PNG = buf.getvalue()
    return _PNG


def _patch(monkeypatch, available: set[str], pid: int = 329918):
    """只让 `available` 里的后缀 200，其余 404，并记下真实请求顺序。"""
    tried: list[str] = []

    def fake_get(url: str, timeout: int = 30) -> bytes:
        tried.append(url)
        ext = url.rsplit(".", 1)[-1]
        if ext not in available:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)  # type: ignore[arg-type]
        return _real_png_bytes()

    monkeypatch.setattr(F, "_get", fake_get)
    monkeypatch.setattr(F, "wta_player_id", lambda name: pid)
    return tried


def test_只有png的球员也要抓得到(tmp_path, monkeypatch):
    """卡尔塔尔那一类：`.jpg` 404、`.png` 有——不许把它报成「没有头像」。"""
    tried = _patch(monkeypatch, {"png"})
    dest = F.fetch_wta("Sonay Kartal", tmp_path)
    assert dest.name == "wta-329918.png"
    assert dest.read_bytes() == _real_png_bytes()
    # 判据钉在「两个后缀都真的请求过」，不是钉在「最后拿到了」——
    # 只试一个后缀也可能碰巧拿到，那样这条测试就是假绿的。
    assert [u.rsplit("/", 1)[-1] for u in tried] == ["329918.jpg", "329918.png"]


def test_有jpg的球员不再多打一次png(tmp_path, monkeypatch):
    """布兹科娃那一类：第一个后缀就中，不该白挨一次 404。"""
    tried = _patch(monkeypatch, {"jpg", "png"}, pid=320983)
    dest = F.fetch_wta("Marie Bouzkova", tmp_path)
    assert dest.name == "wta-320983.jpg"
    assert [u.rsplit("/", 1)[-1] for u in tried] == ["320983.jpg"]


def test_两个后缀都没有才算真的没有(tmp_path, monkeypatch):
    """恰拉耶娃那一类才是真空——报错要把两条试过的地址都打出来，
    让下一个人看得见「查过」而不是「没查」。"""
    tried = _patch(monkeypatch, set(), pid=329198)
    with pytest.raises(SystemExit) as e:
        F.fetch_wta("Vlada Charaeva", tmp_path)
    msg = str(e.value)
    assert "329198.jpg" in msg and "329198.png" in msg
    assert len(tried) == 2


def test_缓存两个后缀都要认(tmp_path, monkeypatch):
    """已经存成 `.png` 的，下次不许因为只找 `.jpg` 而重下一遍。"""
    (tmp_path / "wta-329918.png").write_bytes(_real_png_bytes())

    def boom(url: str, timeout: int = 30) -> bytes:
        raise AssertionError(f"命中缓存时不该联网：{url}")

    monkeypatch.setattr(F, "_get", boom)
    monkeypatch.setattr(F, "wta_player_id", lambda name: 329918)
    assert F.fetch_wta("Sonay Kartal", tmp_path).name == "wta-329918.png"
