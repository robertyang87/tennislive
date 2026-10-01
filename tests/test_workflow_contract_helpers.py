"""Workflow contracts distinguish executed commands from references and inherited settings."""
from pathlib import Path

import pytest

from tools.workflow_contracts import (
    effective_env, git_user_settings, pages_entries, pages_calls, renders_poster, poster_font_missing,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def entries():
    return pages_entries(ROOT)


@pytest.mark.parametrize("run", [
    "python tools/build_match_reel.py render --slug demo",
    "python3 -u tools/build_match_reel.py render --cover-only --slug demo",
    "PYTHONPATH=src python -m tools.build_match_reel render --slug demo",
    "echo ready; python tools/build_match_reel.py render --slug demo",
    "python tools/build_match_reel.py render " + "\\" + "\n  --slug demo",
    "python tools/versus_poster.py --spec demo.json",
])
def test_real_render_commands_need_emoji_fonts(run):
    assert renders_poster(run)


@pytest.mark.parametrize("run", [
    "git add tools/build_match_reel.py",
    "python -c \"from pathlib import Path; print(Path('tools/build_match_reel.py').exists())\"",
    "python - <<'PY'\nassert sha('tools/build_match_reel.py') == expected\nPY",
    "# python tools/build_match_reel.py render --slug demo",
    "echo 'python tools/build_match_reel.py render'",
    "pytest tests/test_match_reel.py",
    "python tools/build_match_reel.py probe --slug demo",
    "python tools/build_match_reel.py render --dry-run --slug demo",
    "python tools/build_match_reel.py render --check-narration --slug demo",
])
def test_checks_and_path_mentions_do_not_render(run):
    assert not renders_poster(run)


@pytest.mark.parametrize("stage", ["check", "page"])
@pytest.mark.parametrize("option", ["--stage {stage}", "--stage={stage}"])
def test_push_reel_local_stages_do_not_need_pages(stage, option, entries):
    run = "python tools/push_reel.py " + option.format(stage=stage)
    assert not pages_calls(run, entries)


@pytest.mark.parametrize("run", [
    "python tools/push_reel.py --stage push",
    "python tools/push_reel.py --outdir output/demo",
    "python tools/push_reel.py --stage $STAGE",
    "python tools/push_reel.py --stage check; python tools/push_reel.py --stage push",
    "tennislive publish pushplus --outdir output/demo",
    "python tools/publish_medvedev24_approved.py verify-public",
    "python3 tools/check_pages_trigger.py",
])
def test_publishing_and_pages_adapters_still_need_permission(run, entries):
    assert pages_calls(run, entries)


def test_nonexecuted_pages_entry_is_not_a_permission_reason(entries):
    run = "git add tools/push_reel.py\npython -m pytest tests/test_push_reel.py"
    assert not pages_calls(run, entries)


def test_pages_discovery_follows_local_adapter_calls(tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "adapter.py").write_text(
        "def verify():\n    wait_for_copy_page(url, title)\n"
        "def main():\n    verify()\n")
    entries = pages_entries(tmp_path)
    assert pages_calls("python tools/adapter.py verify-public", entries)
    assert not pages_calls("echo tools/adapter.py", entries)


def test_env_is_inherited_and_step_overrides_are_respected():
    workflow = {"env": {"GH_TOKEN": "workflow"}}
    job = {"env": {"GITHUB_TOKEN": "job"}}
    assert effective_env(workflow, job, {}) == {"GH_TOKEN": "workflow", "GITHUB_TOKEN": "job"}
    assert effective_env(workflow, job, {"env": {"GITHUB_TOKEN": ""}})["GITHUB_TOKEN"] == ""
    assert not any(effective_env({}, {}, {}).get(k) for k in ("GH_TOKEN", "GITHUB_TOKEN"))


@pytest.mark.parametrize("quote", ["'", '\"', ""])
def test_git_identity_is_about_values_not_shell_quote_style(quote):
    run = f"git config user.name {quote}Claude{quote}\ngit config user.email {quote}noreply@anthropic.com{quote}"
    assert git_user_settings(run) == [("user.name", "Claude"), ("user.email", "noreply@anthropic.com")]


def test_incorrect_git_identity_remains_visible():
    assert git_user_settings("git config user.name tennis live") != [("user.name", "Claude")]
    assert git_user_settings("git config user.email actions@users.noreply.github.com") == [
        ("user.email", "actions@users.noreply.github.com")]
    assert git_user_settings("# git config user.name Claude\necho 'git config user.name Claude'") == []


def test_actual_render_without_emoji_font_is_still_rejected():
    from tools.workflow_contracts import poster_font_missing

    render = "python tools/build_match_reel.py render --slug demo"
    install = "apt_install_cached fonts-noto-cjk fonts-noto-color-emoji"
    assert not poster_font_missing([install, render])
    assert poster_font_missing([render])
    assert poster_font_missing(["# " + install, render])
    assert not poster_font_missing(["git add tools/build_match_reel.py"])


def test_incorrect_identity_is_rejected_regardless_of_quote_style():
    from tools.workflow_contracts import git_identity_problems

    assert not git_identity_problems("git config user.name 'Claude'")
    assert git_identity_problems("git config user.name 'tennislive'")
    assert git_identity_problems("git config user.email 'actions@users.noreply.github.com'")


@pytest.mark.parametrize("run", [
    "{ python tools/push_reel.py --stage push; }",
    "if false; then :; else python tools/push_reel.py --stage push; fi",
    "{ python -m tennislive publish pushplus; }",
    "python -m tennislive publish pushplus",
])
def test_grouped_or_module_pages_invocations_still_require_access(run):
    entries = ({"push_reel.py"}, {"pushplus"})
    assert pages_calls(run, entries)


@pytest.mark.parametrize("run", [
    "{ python tools/build_match_reel.py render --slug demo; }",
    "if false; then :; else python tools/build_match_reel.py render --slug demo; fi",
])
def test_grouped_rendering_still_requires_font(run):
    assert renders_poster(run)
    assert poster_font_missing([run])


@pytest.mark.parametrize("prefix", [
    "echo 'example <<PY'\n",
    "echo \"example <<PY\"\n",
    "cat <<'END-OF-DOC'\nhello\nEND-OF-DOC\n",
    'cat <<"END-OF-DOC"\nhello\nEND-OF-DOC\n',
    "cat <<-EOF\n\thello\n\tEOF\n",
    "cat <<< 'inline text'\n",
])
def test_quoted_examples_and_exact_heredoc_boundaries_cannot_hide_publish(prefix):
    assert pages_calls(prefix + "python tools/push_reel.py --stage push",
                       ({"push_reel.py"}, {"pushplus"}))


def test_real_heredoc_body_is_not_executed_as_shell():
    run = "cat <<'END-OF-DOC'\npython tools/push_reel.py --stage push\nEND-OF-DOC"
    assert not pages_calls(run, ({"push_reel.py"}, {"pushplus"}))
