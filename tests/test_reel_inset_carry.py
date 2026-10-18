"""角标 `carry`：同一张角标跨几个硬切镜头连挂，只在第一镜淡入、最后一镜淡出。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import build_match_reel as reel  # noqa: E402

BASE = "[0:v]null[base]"


def _ins(**kw):
    ins = {"corner": "tr", "width": 0.6, "pad": 0.085, "motion": "editorial",
           "show_for": 4.2}
    ins.update(kw)
    return ins


def test_无carry时照旧淡入淡出():
    chain = reel._overlay_chain(BASE, _ins())
    assert "fade=t=in" in chain and "fade=t=out" in chain


def test_carry_start只淡入不淡出():
    chain = reel._overlay_chain(BASE, _ins(carry="start"))
    assert "fade=t=in" in chain
    assert "fade=t=out" not in chain


def test_carry_mid不淡入不淡出且位置不动():
    chain = reel._overlay_chain(BASE, _ins(carry="mid"))
    assert "fade=" not in chain
    assert "if(lt(t" not in chain


def test_carry_end只在show_for处淡出():
    chain = reel._overlay_chain(BASE, _ins(carry="end", show_for=3.0))
    assert "fade=t=in" not in chain
    assert f"fade=t=out:st={3.0 - reel.CARRY_OUT_SECS:.3f}" in chain
