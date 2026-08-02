"""`tools/gh_runs.py`：把 GitHub MCP 那坨返回体挑成几行能看的。

这个脚本存在的理由本身就是一条判据：沙箱 `curl` 到 `api.github.com` 是 403，
只有 MCP 通；而 MCP 的 `actions_list` 三条 run 就 400 KB，只能落文件再挑字段。
于是每次查 CI 都要现搓同一段 python——2026-08-02 一天搓了五遍。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


gh = _load("gh_runs")


def _write(tmp_path: Path, payload: dict) -> str:
    path = tmp_path / "payload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_两种返回体都认(tmp_path, capsys):
    """今天两种都用到了：列 run 的和列 job 的。只认一种等于漏一半。"""
    runs = _write(tmp_path, {"workflow_runs": [
        {"id": 1, "head_sha": "abcdef1234", "head_branch": "main", "event": "push",
         "status": "completed", "conclusion": "success",
         "created_at": "2026-08-02T10:00:00Z", "updated_at": "2026-08-02T10:02:30Z"},
    ]})
    assert gh.main([runs]) == 0
    out = capsys.readouterr().out
    assert "abcdef12" in out and "completed/success" in out
    assert "2:30" in out, "用时没算出来"

    jobs = _write(tmp_path, {"jobs": {"jobs": [
        {"id": 9, "name": "explainer", "status": "completed", "conclusion": "success",
         "started_at": "2026-08-02T09:47:10Z", "completed_at": "2026-08-02T09:55:56Z",
         "steps": [{"number": 12, "name": "PushPlus 推送到微信",
                    "status": "completed", "conclusion": "success",
                    "started_at": "2026-08-02T09:50:43Z",
                    "completed_at": "2026-08-02T09:55:54Z"}]},
    ]}})
    assert gh.main([jobs, "--steps"]) == 0
    out = capsys.readouterr().out
    # 「第 12 步 success 才算已推送」是这条线上反复要查的那一件事
    assert "PushPlus 推送到微信" in out and "12." in out


def test_喂错文件要出声不许当成没有(tmp_path, capsys):
    """空结果先自证是真空。

    喂错文件和「真的一条 run 都没有」长得一模一样——所以要把顶层键报出来，
    并且**退出码非零**。悄悄打印零条是这个仓库反复栽的那个坑。
    """
    path = _write(tmp_path, {"message": "Not Found"})
    assert gh.main([path]) == 2
    err = capsys.readouterr().err
    assert "message" in err, "没把顶层键报出来，看不出是喂错了文件"


def test_截断了要说一声(tmp_path, capsys):
    """静默截断读起来像「一共就这些」——那正是拿它判 CI 时最会骗人的地方。"""
    payload = {"workflow_runs": [
        {"id": i, "head_sha": f"{i:040x}", "head_branch": "main", "event": "push",
         "status": "completed", "conclusion": "success",
         "created_at": "2026-08-02T10:00:00Z", "updated_at": "2026-08-02T10:01:00Z"}
        for i in range(7)
    ]}
    assert gh.main([_write(tmp_path, payload), "--limit", "2"]) == 0
    out = capsys.readouterr().out
    assert "另有 5 条未显示" in out


def test_缺时刻不许编一个用时(tmp_path, capsys):
    """还在跑的 run 没有 updated_at 的对应物，算出 0:00 会读成「秒开秒完」。

    ⚠️ 断言要写 `用时 0:00` 不能只写 `0:00`——时间戳 `10:00:00Z` 里就含着
    `0:00`，裸串会命中它。判据宁可窄不可宽，这个仓库里的老账。
    """
    payload = {"workflow_runs": [
        {"id": 1, "head_sha": "abc", "head_branch": "main", "event": "push",
         "status": "in_progress", "conclusion": None,
         "created_at": "2026-08-02T10:00:00Z"},
    ]}
    assert gh.main([_write(tmp_path, payload)]) == 0
    out = capsys.readouterr().out
    assert "用时 —" in out and "用时 0:00" not in out


@pytest.mark.parametrize("flag,expect", [("--branch", 0), ("--sha", 0)])
def test_过滤条件对不上时不报错只是空(tmp_path, capsys, flag, expect):
    payload = {"workflow_runs": [
        {"id": 1, "head_sha": "abcdef", "head_branch": "main", "event": "push",
         "status": "completed", "conclusion": "success",
         "created_at": "2026-08-02T10:00:00Z", "updated_at": "2026-08-02T10:01:00Z"},
    ]}
    assert gh.main([_write(tmp_path, payload), flag, "nope"]) == expect
    assert "0/1 条" in capsys.readouterr().out
