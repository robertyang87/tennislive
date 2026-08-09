"""复制页的置顶评论：末屏那一问要自动备好，发完顺手粘上去。

来路是 `docs/short-video-benchmark-strategy.md` 行动清单 B-2：末屏一问是
这类短片换评论区的唯一抓手，而问出去之后没人接第一句，评论区就是冷的。
复制页多一格「置顶评论」，把「第 0 条评论」也备好。

抽取必须是机械的、判据要窄：只认**最后一个带旁白的段**里**落在收尾**的
连续问句串。中段的设问是行文不是留给读者的问题，不抽；「评论区聊聊。」
这类邀请句是空话，不带。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from push_reel import pin_comment  # noqa: E402


def _spec(narration: str) -> dict:
    return {"cover": {"eyebrow": "赛场之上"},
            "segments": [{"narration": "第一段只是铺垫。"},
                         {"narration": narration}]}


def test_末屏一问要抽成置顶评论():
    got = pin_comment(_spec("六比四收下。所以——她的下一站，你看好吗？"))
    assert got == "所以——她的下一站，你看好吗？"


def test_连抛两问整串都要():
    """鹰眼那条本来就连抛两问，那是写稿的选择，不是重复——整串都进评论。"""
    got = pin_comment(_spec("比分定格。谁来接这一棒？还要等多久？"))
    assert got == "谁来接这一棒？还要等多久？"


def test_问句后面的邀请句不带进评论():
    """「评论区聊聊。」是邀请不是问题——图文线本来就禁这类空话。"""
    got = pin_comment(_spec("你觉得法网什么时候也会换电子司线？评论区聊聊。"))
    assert got == "你觉得法网什么时候也会换电子司线？"


def test_问句不在收尾就不算():
    """中段的设问是行文。只认落在最后两句里的问句串，宁可空着也不抽错。"""
    assert pin_comment(_spec("她能赢吗？没人知道。答案在第三盘。比分说明了一切。")) == ""


def test_没有旁白段或没有问句要返回空串():
    assert pin_comment({"cover": {"eyebrow": "赛场之上"}}) == ""
    assert pin_comment(_spec("六比四。比赛结束。")) == ""


def test_复制页要带上置顶评论而且两种情况都出声(tmp_path):
    """真跑一遍 `--stage page`——「写了」不等于「跑过」。

    两个方向：有问句 → 页面带评论格、日志说抽到了；没问句 → 页面不留空框、
    日志说没抽到。只验一头的话，抽取整个坏掉（恒返回空）也照样绿。
    """
    outdir = tmp_path / "output" / "2026-08-09" / "reel" / "demo"
    outdir.mkdir(parents=True)
    copy = tmp_path / "demo.xhs.txt"
    copy.write_text("标题这句\n\n正文第一行", encoding="utf-8")
    (tmp_path / "demo.json").write_text(json.dumps(_spec(
        "赛点落地。这样的逆转，你上一次看到是哪一场？"), ensure_ascii=False),
        encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(Path("tools/push_reel.py").resolve()),
         "--stage", "page", "--outdir", str(outdir),
         "--matchup", "伊埃拉 vs 本西奇", "--score", "2:0",
         "--copy", str(copy)],
        check=True, capture_output=True, text=True)
    page = (outdir / "copy.html").read_text(encoding="utf-8")
    assert "复制评论" in page
    assert "这样的逆转，你上一次看到是哪一场？" in page
    assert "已抽出末屏一问" in done.stdout

    (tmp_path / "demo.json").write_text(json.dumps(
        _spec("六比四。比赛结束。"), ensure_ascii=False), encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(Path("tools/push_reel.py").resolve()),
         "--stage", "page", "--outdir", str(outdir),
         "--matchup", "伊埃拉 vs 本西奇", "--score", "2:0",
         "--copy", str(copy)],
        check=True, capture_output=True, text=True)
    page = (outdir / "copy.html").read_text(encoding="utf-8")
    assert "复制评论" not in page, "没有评论就不该留个空框加一个复制不出东西的按钮"
    assert "没抽到收尾问句" in done.stdout, "空着却不出声，和「抽取坏了」长得一样"
