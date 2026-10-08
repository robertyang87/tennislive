#!/usr/bin/env python3
"""Build this episode's native evidence cards; the reel spec owns the timeline.

Use the repository's existing card typography and palette, with explicit dates
and verified tournament identities. This tool only prepares still assets.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from render_evidence_card import build_html, render  # noqa: E402

DEST = ROOT / "assets/beatcards/vacherot-shanghai-one-year"

CARDS = {
    "before": {"kind": "timeline", "title": "走到上海之前", "rows": [
        {"when": "2024.06", "what": "世界第110 · 肩伤打断进程"},
        {"when": "2025.06", "what": "世界第267 · 温网资格赛摔伤"},
        {"when": "2025.09", "what": "世界第204 · 再次出发"}],
        "note": "ATP 排名与球员采访 · 各节点排名"},
    "door": {"kind": "facts", "title": "2025 上海 · 入场之前", "rows": [
        {"value": "第9候补", "label": "抵达上海时的资格赛候补位置"},
        {"value": "不足36小时", "label": "开赛前才确定入围", "hi": True}],
        "note": "瓦舍罗赛后自述 · ATP / 上海大师赛"},
    "qualifying1": {"kind": "facts", "title": "2025 上海 · 资格赛第一轮", "rows": [
        {"value": "6-7⁷ 6-4 6-2", "label": "瓦舍罗 胜 巴萨瓦雷迪", "hi": True}],
        "note": "2025 上海大师赛官方资格赛签表"},
    "qualifying2": {"kind": "facts", "title": "2025 上海 · 资格赛第二轮", "rows": [
        {"value": "第二盘 5-5", "label": "抢七小分 · 距淘汰只差2分", "hi": True},
        {"value": "4-6 7-6⁵ 6-4", "label": "瓦舍罗 胜 德拉克斯尔"}],
        "note": "官方签表 · 德拉克斯尔赛后采访"},
    "early-rounds": {"kind": "timeline", "title": "2025 上海 · 正赛第一至三轮", "rows": [
        {"when": "第一轮", "what": "6-3 6-4 · 胜杰雷"},
        {"when": "第二轮", "what": "3-6 6-3 6-4 · 逆转布勃利克"},
        {"when": "第三轮", "what": "6-0 3-1 · 马哈奇退赛"}],
        "note": "2025 上海大师赛官方正赛签表 · 瓦舍罗视角"},
    "fourth-round": {"kind": "facts", "title": "2025 上海 · 第四轮", "rows": [
        {"value": "4-6 7-6¹ 6-4", "label": "逆转格里克斯普尔", "hi": True},
        {"value": "世界第204", "label": "走进大师赛1/4决赛"}],
        "note": "官方签表 · ATP 赛后报道"},
    "nine-wins": {"kind": "facts", "title": "2025 上海 · 从资格赛到冠军", "rows": [
        {"value": "9场全胜", "label": "资格赛2场 + 正赛7场", "hi": True},
        {"value": "6次逆转", "label": "6次先丢首盘，6次赢下比赛"}],
        "note": "官方资格赛 / 正赛签表 · ATP 夺冠统计"},
    "after-title": {"kind": "timeline", "title": "2025—2026 · 突破继续有回声", "rows": [
        {"when": "2025.10", "what": "巴黎大师赛1/4决赛"},
        {"when": "2025年末", "what": "世界第31"},
        {"when": "2026.04", "what": "主场蒙特卡洛大师赛半决赛"}],
        "note": "ATP赛事报道 · 年末排名"},
    "chengdu-tokyo": {"kind": "timeline", "title": "2026 · 首战出局以后", "rows": [
        {"when": "成都", "what": "头号种子 · 首战负哈里斯"},
        {"when": "东京", "what": "逆转西西帕斯 · 再胜菲斯"},
        {"when": "东京", "what": "半决赛负莱赫奇卡"}],
        "note": "2026 成都 / 东京官方签表"},
    "final-turn": {'kind': 'facts', 'title': '2025 上海 · 决赛的反转', 'rows': [{'value': '首盘 4-6', 'label': '表哥抢前点，瓦舍罗落后'}, {'value': '次盘 6-3', 'label': '3-3后把球打深，第8局破发', 'hi': True}, {'value': '决胜盘 6-3', 'label': '开局再次破发，把领先守到终点'}], 'note': '上海大师赛官方决赛赛报 · 瓦舍罗视角'},
    "injury-2026": {"kind": "timeline", "title": "2026 · 又一次停下来", "rows": [
        {"when": "5月", "what": "左脚伤 · 法网第二轮赛前退出"},
        {"when": "6月", "what": "退出温网"},
        {"when": "7月", "what": "停赛近2个月 · 格施塔德复出"}],
        "note": "法网比赛记录 · ATP 复出报道"},
    "return": {"kind": "facts", "title": "2026 上海 · 回到故事开始的地方", "rows": [
        {"value": "第17号种子", "label": "首轮轮空 · 世界前20", "hi": True},
        {"value": "2025 → 2026", "label": "从等一个位置，到以冠军身份回来"}],
        "note": "2026 上海官方签表 · 截至2026.10.07"},
}


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for name, data in CARDS.items():
        config = DEST / f"{name}.json"
        config.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        render(build_html(data), DEST / f"{name}.png")
        print(name, flush=True)


if __name__ == "__main__":
    main()
