"""`tools/identify_player_frame.py` 的参数校验。

⚠️ **这个工具依赖 insightface/onnxruntime，故意没进 `pyproject.toml`**（见工具
自己的 docstring：接不接是要花 CI 装依赖的时间换「自动挡住选错人」，这个取舍
留给账号所有者定）。所以这儿**不测分类准不准**——那件事 2026-08-07 用
`zhang-sabalenka` 这条片子的 26 张已知答案候选帧手动验证过（26/26 全对，
两张余量只有 0.05~0.06 的边缘案例也判对），结果记在工具的 docstring 里，
不在这份能跑的测试里重复一遍（重复了也验证不了什么，模型权重不在仓库里）。

真正测的是**参数校验那几条路**——它们在 `main()` 里排在 `_load_embedder()`
之前，不需要装 insightface 就能触发，而且 CI 上**没装 insightface 是常态**，
「没装依赖时报错清楚」这条路径反而是 CI 上唯一真的会被走到的路。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import identify_player_frame as ipf  # noqa: E402


def _run(argv: list[str]) -> None:
    old = sys.argv
    sys.argv = ["identify_player_frame.py", *argv]
    try:
        ipf.main()
    finally:
        sys.argv = old


def test_ref格式不对要报错(tmp_path: Path):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\x00")
    with pytest.raises(SystemExit, match="姓名=图片路径"):
        _run(["--ref", "张帅没有等号", str(img)])


def test_至少要两个ref(tmp_path: Path):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\x00")
    with pytest.raises(SystemExit, match="至少给两个"):
        _run(["--ref", f"张帅={img}", str(img)])


def test_参考图不存在要报错(tmp_path: Path):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\x00")
    with pytest.raises(SystemExit, match="参考图不存在"):
        _run(["--ref", "张帅=不存在的路径.jpg", "--ref", f"萨巴伦卡={img}", str(img)])


def test_候选帧不存在要报错(tmp_path: Path):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\x00")
    with pytest.raises(SystemExit, match="候选帧不存在"):
        _run(["--ref", f"张帅={img}", "--ref", f"萨巴伦卡={img}", "不存在的候选.jpg"])


def test_没装依赖要报清楚而不是裸ImportError(monkeypatch: pytest.MonkeyPatch):
    """⚠️ CI 上没装 insightface，这条路**必然**被走到。

    第一版如果直接 `from insightface.app import FaceAnalysis` 摆在文件顶层，
    整个模块在没装依赖的机器上 import 就崩，连参数校验都用不了；现在延迟到
    `_load_embedder()` 里，且包成一句说得清楚的话（缺什么包、能装成什么样）。
    """
    import builtins

    real_import = builtins.__import__

    def blocked(name, *a, **k):
        if name in ("insightface", "insightface.app", "cv2"):
            raise ImportError(f"simulated: no module named {name!r}")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", blocked)
    with pytest.raises(SystemExit, match="insightface"):
        ipf._load_embedder()
