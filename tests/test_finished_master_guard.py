"""A finished master must not receive a second subtitle/voice burn."""
import argparse
import ast
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest


@pytest.mark.parametrize("imported,dry_run,blocked", [
    (True, False, True), (True, True, False), (False, False, False),
])
def test_finished_master_render_guard_preserves_validation(monkeypatch, tmp_path,
                                                         imported, dry_run, blocked):
    tree = ast.parse(Path("tools/build_match_reel.py").read_text(encoding="utf-8"))
    main = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "main")

    class ReelError(Exception):
        pass

    class ReachedEditorialCheck(Exception):
        pass

    def editorial_check(*args):
        raise ReachedEditorialCheck

    spec = {"_import": {"kind": "finished_master_inspection"}} if imported else {}
    namespace = {
        "__doc__": "Test actual CLI routing before rendering side effects.",
        "argparse": argparse, "Path": Path, "ReelError": ReelError,
        "localca": SimpleNamespace(trust_local_proxy_ca=lambda: None),
        "load_spec": lambda path: spec, "enforce_spec_wording": editorial_check,
    }
    exec(compile(ast.Module(body=[main], type_ignores=[]), "actual_reel_main", "exec"), namespace)
    out = tmp_path / "render-output"
    argv = ["build_match_reel.py", "render", "--spec", "approved.json", "--outdir", str(out)]
    if dry_run:
        argv.append("--dry-run")
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(ReelError if blocked else ReachedEditorialCheck):
        namespace["main"]()
    assert not out.exists(), "No rendering side effects may happen before this guard"
