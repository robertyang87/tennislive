"""tools/ 下不许定义 Warning 子类——要定义在 tennislive 包里。

pytest-xdist 的主控进程按 ``type(w).__module__`` 重新 import warning 类来反序列化 worker
发回的 warning，而主控的 sys.path 里没有 tools/：类定义在 tools/ 里，worker 一发这条
warning，整场测试会话 INTERNALERROR（PR #1138 CI，run 36421724798）。本地加
``-p no:warnings`` 跑不出来，所以按形状判：扫 tools/*.py 的 AST，不维护白名单。
"""
import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _warning_classes_in_tools():
    found = []
    for path in sorted((ROOT / "tools").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                name = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", "")
                if name.endswith("Warning"):
                    found.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.name}({name})")
    return found


def test_tools下不许定义Warning子类_xdist主控反序列化不了():
    found = _warning_classes_in_tools()
    assert not found, ("这些 Warning 子类定义在 tools/ 里，xdist 主控 import 不到，"
                       "worker 一发就 INTERNALERROR——挪进 src/tennislive/findings.py：\n"
                       + "\n".join(found))


def test_自动spec那条warning的类_主控不带tools也import得到():
    sys.path.insert(0, str(ROOT / "tools"))
    import build_interview_request as req  # noqa: PLC0415
    module = req.UnverifiedAutoSpecFinding.__module__
    assert module.startswith("tennislive."), module
    probe = ("import sys; sys.path[:] = [p for p in sys.path if not p.rstrip('/').endswith('tools')]; "
             f"import importlib; importlib.import_module({module!r})")
    r = subprocess.run([sys.executable, "-c", probe], cwd=ROOT / "src",
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-600:]
