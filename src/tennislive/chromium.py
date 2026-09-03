"""找 Chromium ——全仓库**只有这一份**（review 路线 ⑥ 第一刀，2026-09-03）。

在这之前它有 **12 份**，各自漂移，而漂移的样子是「本地全绿、runner 上报找不到」：

| 哪一份 | 毛病 |
|---|---|
| `render_stat_card` / `render_evidence_card` / `render_beat_card` / `versus_poster` | 写死 `chromium-1194/chrome-linux/chrome`——版本号一换就是死路 |
| `probe_atp_browser_stats` / `probe_venue_photos` | 只认 `chrome-linux`，新版 playwright 的目录叫 **`chrome-linux64`**（`build_interview_clip` 的 docstring 记过这个坑，别处没跟着改） |
| `preview_diagram_local` | 只看 `/opt/pw-browsers`，不看 `PLAYWRIGHT_BROWSERS_PATH` |
| `webcards._chromium_executable` | 不认 headless shell，找不到回 None，调用方各自处理 |

规矩本文件一条：**先问显式配置，再问 playwright 自己，最后按通配 glob——目录名
里不许出现版本号。** 顺序：

1. `CHROMIUM_PATH`（显式配置，配错了就该报）
2. playwright 自报的 `executable_path`（沙箱里它会答一个不存在的版本号，所以要
   `exists()` 再信）
3. `PLAYWRIGHT_BROWSERS_PATH` → `/opt/pw-browsers` → `~/.cache/ms-playwright`，
   每个根下先找完整版 `chromium-*/*/chrome`，再找 `chromium_headless_shell-*/*/headless_shell`
   （渲截图够用，但别当默认）；`/opt/pw-browsers/chromium` 这种包装脚本也认

判据在 tests/test_chromium.py：行为（假目录树两种目录名都认、headless 兜底、
环境变量优先）＋ 出处只有一份（别处不许再写 `pw-browsers` / `executable_path=`）。
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

_FULL = "chromium-*/*/chrome"
_SHELL = "chromium_headless_shell-*/*/headless_shell"
INSTALL_HINT = "装：python -m playwright install chromium"


def _roots() -> list[str]:
    roots = [os.environ.get("PLAYWRIGHT_BROWSERS_PATH"), "/opt/pw-browsers",
             str(Path.home() / ".cache/ms-playwright")]
    out: list[str] = []
    for r in roots:
        if r and r not in out:
            out.append(r)
    return out


def _ask_playwright() -> str | None:
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415

        with sync_playwright() as p:
            exe = p.chromium.executable_path
    except Exception:  # noqa: BLE001 — 没装 / 版本对不上，都退回自己找
        return None
    return exe if exe and Path(exe).is_file() else None


def find_chromium(*, ask_playwright: bool = True) -> str | None:
    """找得到返回可执行文件路径，找不到返回 None（**不抛**——调用方决定怎么报）。"""
    explicit = os.environ.get("CHROMIUM_PATH")
    if explicit and Path(explicit).is_file():
        return explicit
    if ask_playwright and (exe := _ask_playwright()):
        return exe
    for root in _roots():
        for pattern in (_FULL, _SHELL):
            hits = sorted(glob.glob(str(Path(root) / pattern)))
            if hits:
                return hits[-1]
        wrapper = Path(root) / "chromium"
        if wrapper.is_file():
            return str(wrapper)
    return None


def require_chromium(*, ask_playwright: bool = True) -> str:
    """找不到就 `FileNotFoundError`，报错正文带着找过哪儿和怎么装。"""
    exe = find_chromium(ask_playwright=ask_playwright)
    if exe:
        return exe
    raise FileNotFoundError(
        f"找不到 Chromium。{INSTALL_HINT}\n"
        f"（找过 CHROMIUM_PATH、playwright 自报的路径，和 {', '.join(_roots())} 下的 "
        f"{_FULL} / {_SHELL}）")


def launch_chromium(pw, **kwargs):
    """`pw.chromium.launch(**kwargs)`；默认那条路起不来就显式给可执行文件路径。

    每个调用方原来各自写一遍「try 默认 launch，except 试几个写死的路径」——
    现在只在这儿写一遍。找不到的时候抛的是**默认 launch 那个异常**（playwright
    自己的话最准），只是把我们找过哪儿加在 `__notes__` 里。
    """
    try:
        return pw.chromium.launch(**kwargs)
    except Exception as default_error:  # noqa: BLE001
        exe = find_chromium(ask_playwright=False)
        if not exe:
            note = f"找不到 Chromium 的可执行文件（{INSTALL_HINT}）"
            if hasattr(default_error, "add_note"):
                default_error.add_note(note)
            raise default_error
        return pw.chromium.launch(executable_path=exe, **kwargs)
