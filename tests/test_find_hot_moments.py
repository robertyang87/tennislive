"""tools/find_hot_moments.py —— 把 check_crowd_rise 的观众声抬升时刻和
probe.json 的 scene_cuts/point_ends 对齐。纯函数，不联网、不碰音视频。

配套：tools/check_crowd_rise.py 新增的 `--json` 输出口，仍然严格不进
render/CI（test_音频那套不许接进出片流程 钉着这条），这份测试不碰它。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _mod():
    sys.path.insert(0, str(Path("tools").resolve()))
    import find_hot_moments  # noqa: PLC0415

    return find_hot_moments


def test_死球和观众声都在附近的排最前():
    m = _mod()
    ranked = m.align(crowd_hits=[10.0, 50.0, 90.0],
                      scene_cuts=[10.3, 90.4], point_ends=[10.1])
    # 10.0s：切点和死球都在 1.5s 窗口内 → score 3；90.0s：只有切点 → score 1；
    # 50.0s：什么都不沾 → score 0
    assert [c["t"] for c in ranked] == [10.0, 90.0, 50.0]
    assert ranked[0]["score"] == 3
    assert ranked[1]["score"] == 1
    assert ranked[2]["score"] == 0


def test_死球权重比场景切点高():
    m = _mod()
    # 两个候选各只沾一种信号，死球那个应该排在前面
    ranked = m.align(crowd_hits=[5.0, 20.0], scene_cuts=[5.2], point_ends=[20.1])
    assert ranked[0]["t"] == 20.0
    assert ranked[0]["score"] == 2
    assert ranked[1]["t"] == 5.0
    assert ranked[1]["score"] == 1


def test_窗口外的信号不算命中():
    m = _mod()
    ranked = m.align(crowd_hits=[10.0], scene_cuts=[13.0], point_ends=[], window=1.5)
    assert ranked[0]["score"] == 0
    # 但最近的那个切点仍然要报出来，供人自己判断要不要放宽窗口
    assert ranked[0]["nearest_scene_cut"] == 13.0
    assert ranked[0]["scene_cut_delta"] == 3.0


def test_没有切点或死球数据不报错只是分数低():
    m = _mod()
    ranked = m.align(crowd_hits=[1.0, 2.0], scene_cuts=[], point_ends=[])
    assert all(c["score"] == 0 for c in ranked)
    assert all(c["nearest_scene_cut"] is None for c in ranked)


def test_命令行拼两份json输出排好序的候选(tmp_path, capsys):
    m = _mod()
    probe = tmp_path / "probe.json"
    probe.write_text(json.dumps({"scene_cuts": [10.3], "point_ends": [10.1]}), encoding="utf-8")
    crowd = tmp_path / "crowd.json"
    crowd.write_text(json.dumps({"hits": [10.0, 50.0]}), encoding="utf-8")

    old_argv = sys.argv
    try:
        sys.argv = ["find_hot_moments.py", "--probe", str(probe), "--crowd", str(crowd), "--json"]
        code = m.main()
    finally:
        sys.argv = old_argv
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out[0]["t"] == 10.0
    assert out[0]["score"] == 3
    assert out[1]["t"] == 50.0
