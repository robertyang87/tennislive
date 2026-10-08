"""Production must run static pronunciation checks with a lightweight dictionary."""
import ast
import re
from pathlib import Path

import pytest
import yaml

from tools.workflow_contracts import invoked_programs, shell_commands

ROOT = Path(__file__).resolve().parents[1]


def _steps(name):
    workflow = yaml.safe_load((ROOT / ".github/workflows" / name).read_text())
    return [step for job in workflow["jobs"].values() for step in job["steps"]]


def _installs_pronunciation(run):
    for command in shell_commands(run):
        if command[:2] != ["pip", "install"]:
            continue
        for argument in command:
            match = re.fullmatch(r"\.\[([^]]+)\]", argument)
            if match and "pronunciation" in match[1].split(","):
                return True
    return False


def _imports_dictionary(run):
    for command in shell_commands(run):
        program, arguments = command[0], command[1:]
        if program not in {"python", "python3"} or "-c" not in arguments:
            continue
        source = arguments[arguments.index("-c") + 1]
        if any(isinstance(node, ast.Import) and
               any(alias.name == "pypinyin" for alias in node.names)
               for node in ast.walk(ast.parse(source))):
            return True
    return False


def test_production_extra_is_only_the_same_pinned_dictionary():
    project = (ROOT / "pyproject.toml").read_text()
    optional = project.split("[project.optional-dependencies]", 1)[1]
    requirements = ast.literal_eval(
        re.search(r"^pronunciation\s*=\s*(\[[^]]+\])", optional, re.M)[1])
    assert requirements == ["pypinyin>=0.50,<0.60"]
    for extra in ("dev", "polyphone"):
        dependencies = ast.literal_eval(
            re.search(rf"^{extra}\s*=\s*(\[[^]]+\])", optional, re.M)[1])
        assert requirements[0] in dependencies


@pytest.mark.parametrize("workflow", [
    "match-reel.yml", "interview-clip.yml", "explainer.yml",
    "preview-reel.yml", "reel-auto-ready.yml", "interview-auto-render.yml",
    "oncourt-interviews.yml",
])
def test_actual_install_and_import_probe_exist_in_each_production_path(workflow):
    installs = [step for step in _steps(workflow)
                if _installs_pronunciation(step.get("run", ""))]
    assert installs, f"{workflow}: pronunciation dictionary not installed"
    assert all(_imports_dictionary(step["run"]) for step in installs), (
        f"{workflow}: missing dictionary must fail before synthesis")
    assert not any(step.get("continue-on-error") for step in installs)


def test_reel_installs_before_dry_run_only_in_modes_that_check_speech():
    steps = _steps("match-reel.yml")
    dependency = next(step for step in steps
                      if _installs_pronunciation(step.get("run", "")))
    modes = set(re.findall(r"inputs\.mode\s*==\s*'([^']+)'", dependency["if"]))
    assert modes == {"render", "cover", "narration", "reattest"}
    consumer = next(step for step in steps if any(
        program.endswith("build_match_reel.py") and "--dry-run" in arguments
        for program, arguments in invoked_programs(step.get("run", ""))))
    assert steps.index(dependency) < steps.index(consumer)


@pytest.mark.parametrize("workflow,selector", [
    ("match-reel.yml", "--spec"), ("interview-clip.yml", "--spec"),
    ("explainer.yml", "--slug"),
])
def test_independent_cli_scans_speech_even_without_interview_takeaway(workflow, selector):
    steps = _steps(workflow)
    dependency = next(step for step in steps
                      if _installs_pronunciation(step.get("run", "")))
    consumers = [(step, arguments) for step in steps
                 for program, arguments in invoked_programs(step.get("run", ""))
                 if program.endswith("check_polyphones.py")]
    assert consumers
    consumer, check = consumers[0]
    assert steps.index(dependency) <= steps.index(consumer)
    assert check and selector in check
    assert "--measure" not in check, "static production check must remain lightweight"


def test_comments_and_echo_cannot_fake_a_real_install_or_probe():
    fake = '# pip install -e ".[pronunciation]"\necho \'pip install -e ".[pronunciation]"\''
    assert not _installs_pronunciation(fake)
    assert not _imports_dictionary('# python -c "import pypinyin"\necho pypinyin')
    assert _installs_pronunciation('pip install -q -e ".[pronunciation]"')
    assert _imports_dictionary('python -c "import pypinyin"')
