"""Static workflow contracts: inspect invoked commands, not filenames used as data.

This is deliberately a small shell recognizer, not a shell interpreter. It handles
workflow command lists, continuations, environment prefixes and Python entrypoints;
heredoc payloads and quoted arguments are never interpreted as shell commands.
"""
from __future__ import annotations

import ast
import re
import shlex
from pathlib import Path


def _heredoc_delimiters(line: str) -> list[str]:
    """Find real unquoted << operators; quoted examples are ordinary data."""
    delimiters = []
    quote = None
    i = 0
    while i < len(line):
        char = line[i]
        if char == "\\" and quote != "'":
            i += 2
            continue
        if quote:
            if char == quote:
                quote = None
            i += 1
            continue
        if char in "\"'":
            quote = char
            i += 1
            continue
        if char == "#" and (i == 0 or line[i - 1].isspace()):
            break
        if line.startswith("<<<", i):
            i += 3  # here-string, no following payload lines
            continue
        if line.startswith("<<", i):
            after = i + 2 + (line[i + 2:i + 3] == "-")
            lexer = shlex.shlex(line[after:], posix=True, punctuation_chars=";&|()<>")
            lexer.whitespace_split = True
            lexer.commenters = "#"
            delimiter = lexer.get_token()
            if not delimiter or all(c in ";&|()<>" for c in delimiter):
                raise ValueError("unsupported heredoc without an exact delimiter")
            delimiters.append(delimiter)
            i = after
            continue
        i += 1
    return delimiters


def shell_commands(run: str) -> list[list[str]]:
    """Return executable command words from the supported workflow shell syntax."""
    commands = []
    heredocs = []
    # Expressions may contain shell-looking operators, but are expanded by Actions.
    run = re.sub(r"\$\{\{.*?\}\}", "GHA_EXPRESSION", str(run), flags=re.S)
    run = run.replace("\\\n", " ")
    for line in run.splitlines():
        if heredocs:
            if line.strip() == heredocs[0]:
                heredocs.pop(0)
            continue
        if line.lstrip().startswith("#"):
            continue
        heredocs.extend(_heredoc_delimiters(line))
        lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        lexer.commenters = "#"
        try:
            words = list(lexer)
        except ValueError:
            # Multiline quoted strings are not standalone shell invocations.
            continue
        segments = [[]]
        for word in words:
            if word and all(c in ";&|()" for c in word):
                segments.append([])
            else:
                segments[-1].append(word)
        for words in segments:
            while words and (words[0] in {"if", "then", "elif", "else", "do", "!", "env", "command", "{"}
                             or re.match(r"^[A-Za-z_]\w*=", words[0])):
                words = words[1:]
            if words:
                commands.append(words)
    return commands


def invoked_programs(run: str) -> list[tuple[str, list[str]]]:
    """Normalize `python script.py`, `python -m module`, and direct programs."""
    programs = []
    for words in shell_commands(run):
        program, args = Path(words[0]).name, words[1:]
        if re.fullmatch(r"python(?:\d+(?:\.\d+)?)?", program):
            while args and args[0] in {"-u", "-B", "-I", "-E", "-s", "-S"}:
                args = args[1:]
            if not args or args[0] in {"-", "-c"}:
                continue
            if args[0] == "-m":
                if len(args) < 2:
                    continue
                program, args = args[1].rsplit(".", 1)[-1] + ".py", args[2:]
            elif not args[0].startswith("-"):
                program, args = Path(args[0]).name, args[1:]
            else:
                continue
        programs.append((program, args))
    return programs


def renders_poster(run: str) -> bool:
    """Checks/probes and references to the renderer do not render a poster."""
    for program, args in invoked_programs(run):
        if program in {"versus_poster", "versus_poster.py"}:
            return True
        if program != "build_match_reel.py":
            continue
        if args and args[0] == "probe":
            continue
        if any(flag in args for flag in ("--dry-run", "--check-narration")):
            continue
        return True
    return False


def _calling_functions(tree: ast.Module, names: set[str]) -> set[str]:
    """Propagate calls only within each module, so unrelated `main`s stay separate."""
    functions = {node.name: node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    reached = set(names)
    while True:
        callers = {name for name, node in functions.items()
                   if any(isinstance(call, ast.Call)
                          and (getattr(call.func, "id", None)
                               or getattr(call.func, "attr", None)) in reached
                          for call in ast.walk(node))}
        expanded = reached | callers
        if expanded == reached:
            return callers
        reached = expanded


def pages_entries(root: Path) -> tuple[set[str], set[str]]:
    """Discover actual Pages callers, including one-film adapters, from source AST."""
    probes = {"drop_dead_copy_button", "wait_for_copy_page", "trigger_pages_build"}
    scripts = {path.name for path in (root / "tools").glob("*.py")
               if _calling_functions(ast.parse(path.read_text(encoding="utf-8")), probes)}
    cli = root / "src/tennislive/cli.py"
    channels = set()
    if cli.exists():
        source = cli.read_text(encoding="utf-8")
        probing = _calling_functions(ast.parse(source), probes)
        channels = {channel for channel, function in re.findall(
            r'args\.channel\s*==\s*"([^\"]+)"[^\n]*\n\s*return\s+(\w+)\(', source)
            if function in probing}
    return scripts, channels


def _option(args: list[str], name: str, default: str) -> str:
    """argparse takes the final occurrence; dynamic values remain conservative."""
    value = default
    for i, arg in enumerate(args):
        if arg.startswith(name + "="):
            value = arg.split("=", 1)[1]
        elif arg == name and i + 1 < len(args):
            value = args[i + 1]
    return value


def pages_calls(run: str, entries: tuple[set[str], set[str]]) -> list[str]:
    scripts, channels = entries
    calls = []
    for program, args in invoked_programs(run):
        if program in scripts:
            # Both stages return before wait_for_copy_page/trigger_pages_build.
            if program == "push_reel.py" and _option(args, "--stage", "push") in {"check", "page"}:
                continue
            calls.append(program)
        elif program in {"tennislive", "tennislive.py"} and len(args) >= 2 and args[0] == "publish" and args[1] in channels:
            calls.append("tennislive publish " + args[1])
    return calls


def effective_env(workflow: dict, job: dict, step: dict) -> dict:
    """GitHub Actions precedence: step overrides job, which overrides workflow."""
    return {**(workflow.get("env") or {}), **(job.get("env") or {}), **(step.get("env") or {})}


def git_user_settings(run: str) -> list[tuple[str, str]]:
    """Compare git config values after shell unquoting, not quote characters."""
    settings = []
    for words in shell_commands(run):
        if words[:2] != ["git", "config"]:
            continue
        for i, word in enumerate(words[2:], start=2):
            if word in {"user.name", "user.email"} and i + 1 < len(words):
                settings.append((word, words[i + 1]))
    return settings


def poster_font_missing(runs: list[str]) -> bool:
    return any(renders_poster(run) for run in runs) and not any(
        "fonts-noto-color-emoji" in command
        for run in runs for command in shell_commands(run))


def git_identity_problems(run: str) -> list[str]:
    expected = {"user.name": "Claude", "user.email": "noreply@anthropic.com"}
    return [f"git config {key} {value!r} 应该是 {expected[key]!r}"
            for key, value in git_user_settings(run) if value != expected[key]]
