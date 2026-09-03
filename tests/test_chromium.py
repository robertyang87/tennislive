"""找 Chromium 只有一份出处（review 路线 ⑥ 第一刀，`src/tennislive/chromium.py`）。

在这之前它有 12 份，各自漂移，漂移的样子是「本地全绿、runner 上报找不到」：
四份写死 `chromium-1194`、两份只认旧目录名 `chrome-linux`。判据分两头——
行为（假目录树真去找）和出处（别处不许再写 `pw-browsers` / `executable_path=`）。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tennislive import chromium as ch  # noqa: E402


def _tree(tmp_path: Path, rel: str) -> Path:
    exe = tmp_path / rel
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text("#!/bin/sh\n")
    return exe


@pytest.mark.parametrize("layout", ["chrome-linux", "chrome-linux64"])
def test_新旧两种目录名都认_环境变量的根优先(layout, tmp_path, monkeypatch):
    """新版 playwright 把可执行文件挪进了 `chrome-linux64`；只认旧名字的那几份
    在 runner 上装好了也报找不到。`PLAYWRIGHT_BROWSERS_PATH` 排在 /opt/pw-browsers
    前面——喂一个假根，它必须选假根里的那份，而不是这台机器上真的那份。"""
    monkeypatch.delenv("CHROMIUM_PATH", raising=False)
    exe = _tree(tmp_path, f"chromium-1234/{layout}/chrome")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
    assert ch.find_chromium(ask_playwright=False) == str(exe)


def test_完整版优先_没有才退到headless_shell_再没有回None(tmp_path, monkeypatch):
    monkeypatch.delenv("CHROMIUM_PATH", raising=False)
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
    monkeypatch.setattr(ch, "_roots", lambda: [str(tmp_path)])
    assert ch.find_chromium(ask_playwright=False) is None
    with pytest.raises(FileNotFoundError, match="playwright install chromium"):
        ch.require_chromium(ask_playwright=False)
    shell = _tree(tmp_path, "chromium_headless_shell-1234/chrome-linux/headless_shell")
    assert ch.find_chromium(ask_playwright=False) == str(shell)
    full = _tree(tmp_path, "chromium-1234/chrome-linux64/chrome")
    assert ch.find_chromium(ask_playwright=False) == str(full)


def test_CHROMIUM_PATH显式配置排第一_配了不存在的就当没配(tmp_path, monkeypatch):
    full = _tree(tmp_path, "chromium-1/chrome-linux/chrome")
    monkeypatch.setattr(ch, "_roots", lambda: [str(tmp_path)])
    explicit = _tree(tmp_path, "mine/chrome")
    monkeypatch.setenv("CHROMIUM_PATH", str(explicit))
    assert ch.find_chromium(ask_playwright=False) == str(explicit)
    monkeypatch.setenv("CHROMIUM_PATH", str(tmp_path / "nope"))
    assert ch.find_chromium(ask_playwright=False) == str(full)


def test_launch默认那条路起不来才显式给路径(tmp_path, monkeypatch):
    calls = []

    class FakeChromium:
        def launch(self, **kw):
            calls.append(kw)
            if "executable_path" not in kw:
                raise RuntimeError("Executable doesn't exist")
            return "browser"

    class FakePW:
        chromium = FakeChromium()

    exe = _tree(tmp_path, "chromium-9/chrome-linux/chrome")
    monkeypatch.delenv("CHROMIUM_PATH", raising=False)
    monkeypatch.setattr(ch, "_roots", lambda: [str(tmp_path)])
    assert ch.launch_chromium(FakePW(), args=["--no-sandbox"]) == "browser"
    assert calls == [{"args": ["--no-sandbox"]},
                     {"executable_path": str(exe), "args": ["--no-sandbox"]}]
    # 哪儿都找不到：抛的是默认 launch 那个异常（playwright 自己的话最准）
    monkeypatch.setattr(ch, "_roots", lambda: [str(tmp_path / "empty")])
    with pytest.raises(RuntimeError, match="Executable"):
        ch.launch_chromium(FakePW())


def test_这台机器上真的找得到chromium():
    """查产物不查信号：路径存在还不够，得真能跑起来报出版本号。缺 Chromium 时
    这条要红，不许 skip——封面走 HTML 渲染，没有它出不了片。"""
    import subprocess

    exe = Path(ch.require_chromium())
    out = subprocess.run([str(exe), "--version"], capture_output=True, text=True,
                         timeout=60).stdout
    assert "Chromium" in out or "Chrome" in out, f"跑不出版本号：{out!r}"


def _py_files():
    yield from sorted((ROOT / "tools").glob("*.py"))
    yield from sorted((ROOT / "src" / "tennislive").rglob("*.py"))


def _docstring_spans(tree: ast.Module) -> set[int]:
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                d = body[0]
                lines.update(range(d.lineno, (d.end_lineno or d.lineno) + 1))
    return lines


def test_找Chromium的出处只有一份():
    """别处不许再自己找：字符串常量里不许出现 `pw-browsers` / `chromium-1194` /
    `chrome-linux`（docstring 里记坑不算——那是教训的存放处），
    `.chromium.launch(executable_path="…")` 的值不许是字面量。传一个从共享模块
    拿来的变量是合规的（outro_page 就是这么接的）。
    写两处必分叉——而分叉的样子是「其中一份还认着 chromium-1194」。"""
    markers = ("pw-browsers", "chromium-1194", "chrome-linux")
    offenders = []
    for path in _py_files():
        if path.name == "chromium.py" and path.parent.name == "tennislive":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        doc = _docstring_spans(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and any(m in node.value for m in markers) and node.lineno not in doc:
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} 字符串里自己写了浏览器路径")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "launch" \
                    and isinstance(node.func.value, ast.Attribute) \
                    and node.func.value.attr == "chromium" \
                    and any(k.arg == "executable_path" and isinstance(k.value, ast.Constant)
                            for k in node.keywords):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} executable_path 写死了")
    assert not offenders, "\n".join(offenders)
