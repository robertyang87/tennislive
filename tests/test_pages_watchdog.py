"""Pages 部署卡在队里时的看门狗（2026-09-24 普罗佐罗娃那条推送撞上的）。

run 3031（workflow_dispatch）一直 pending、一个 job 都没起，占着 `concurrency: pages`
不放；后面六趟部署全堵在它后面，推送探复制页探了半个多小时。手动取消它之后
下一趟两分钟内上线。
"""
from __future__ import annotations

import datetime as dt

from tennislive.render import pushmsg

NOW = dt.datetime(2026, 9, 24, 16, 22, tzinfo=dt.timezone.utc).timestamp()


def _run(rid, status, minutes_ago):
    born = dt.datetime.fromtimestamp(NOW - minutes_ago * 60, tz=dt.timezone.utc)
    return {"id": rid, "status": status, "created_at": born.isoformat().replace("+00:00", "Z")}


def test_没人在跑_自己pending很久_又没起job_才算卡死():
    runs = [_run(3038, "pending", 1), _run(3031, "pending", 45), _run(3030, "completed", 45)]
    jobs = {3038: 0, 3031: 0}
    assert pushmsg.stuck_pages_runs(runs, jobs.get, now=NOW) == [3031]


def test_前面有人在跑_后面的pending是正常排队_不许动():
    runs = [_run(3031, "pending", 45), _run(3030, "in_progress", 46)]
    assert pushmsg.stuck_pages_runs(runs, lambda rid: 0, now=NOW) == []


def test_起了job的不算卡死_查不到job的不动():
    runs = [_run(1, "queued", 20), _run(2, "pending", 20)]
    jobs = {1: 1, 2: None}
    assert pushmsg.stuck_pages_runs(runs, jobs.get, now=NOW) == []


def test_看门狗等够了才查_之后隔一段再查():
    t = [0.0]
    calls = []
    dog = pushmsg.PagesWatchdog(first=360, every=240, clock=lambda: t[0],
                                unstick=lambda: calls.append(t[0]) or [3031])
    for t[0] in (0, 100, 359):
        dog.tick()
    assert calls == []
    for t[0] in (360, 400, 599, 600):
        dog.tick()
    assert calls == [360, 600] and dog.cancelled == [3031, 3031]


def test_两条探活循环都挂着看门狗():
    """推送复制页的两条路（竖版短片 wait_for_copy_page、其余线 _probe_page）都要有。"""
    import inspect
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import push_reel
    for fn in (push_reel.wait_for_copy_page, pushmsg._probe_page):
        src = inspect.getsource(fn)
        assert "PagesWatchdog()" in src and "watchdog.tick()" in src, fn.__name__
