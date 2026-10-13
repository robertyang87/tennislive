"""所有 reel spec 默认 `push.auto: true`（2026-10-13 账号所有者：质检通过即推送微信，不用问）。

不开就必须写 `push._no_auto_why`。旧片豁免在 `data/legacy_push_auto_off.json`，只许减不许加。
来路：fritz-pocket-ball-shanghai-2026 合并后 auto-push-reel 绿着跳过（run 38366614433）。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = ROOT / "specs" / "reels"
LEGACY = set(json.loads((ROOT / "data" / "legacy_push_auto_off.json").read_text())["slugs"])


def _missing():
    out = set()
    for p in SPEC_DIR.glob("*.json"):
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        push = d.get("push") or {}
        if push.get("auto") is not True and not push.get("_no_auto_why"):
            out.add(p.stem)
    return out


def test_新片默认开自动推送():
    fresh = _missing() - LEGACY
    assert not fresh, (
        f"这些 reel spec 没写 push.auto=true 也没写 push._no_auto_why：{sorted(fresh)}。"
        "默认要开：质检通过即推送微信。")


def test_豁免表只许减不许加():
    stale = LEGACY - _missing()
    assert not stale, f"这些已经开了自动推送或表过态，从豁免表删掉：{sorted(stale)}"
