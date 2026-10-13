#!/usr/bin/env python3
"""Select reviewed pipeline tests from a real base/head tree diff; uncertainty is full."""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CATALOG = 'tools/production_test_scopes.json'
LINES = ('reel', 'interview', 'explainer', 'news')
PREFIXES = {
    'reel': ('specs/reels/', 'requests/reels/', 'data/reel_publish_ledger/',
             'data/reel_dispatch_queue/'),
    'interview': ('specs/interviews/', 'requests/interviews/', 'data/interview_publish_ledger/'),
    'explainer': ('specs/explainers/', 'requests/explainers/', 'data/explainer_publish_ledger/',
                  'src/tennislive/video/episodes/'),
    'news': ('specs/news/', 'requests/news/'),
}
WORKFLOWS = {
    'match-reel.yml': 'reel', 'compose-native-reel.yml': 'reel',
    'auto-push-reel.yml': 'reel', 'reel-queue-ci.yml': 'reel',
    'interview-clip.yml': 'interview', 'interview-auto-render.yml': 'interview',
    'auto-push-interview.yml': 'interview', 'explainer.yml': 'explainer',
}
FULL_PATHS = {
    '.github/workflows/ci.yml', 'tools/production_test_scopes.py', CATALOG,
    'pyproject.toml', 'pytest.ini', 'tox.ini', 'setup.cfg', 'setup.py',
    'uv.lock', 'poetry.lock', 'requirements.txt',
    'src/tennislive/design_tokens.py', 'src/tennislive/render/webcards.py',
    'src/tennislive/render/cards.py',
}


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)


def load_catalog(root: Path) -> tuple[dict, dict[str, str]]:
    catalog = json.loads((root / CATALOG).read_text())
    if (set(catalog) != {'version', 'always', 'video_shared', 'scopes'}
            or catalog['version'] != 1 or set(catalog['scopes']) != {*LINES, 'other'}):
        raise ValueError('Unrecognized scope catalog schema')
    owners = {}
    trees = {}
    groups = {'always': catalog['always'], 'video_shared': catalog['video_shared'],
              **catalog['scopes']}
    for group, targets in groups.items():
        if not isinstance(targets, list) or not targets or len(set(targets)) != len(targets):
            raise ValueError(f'Invalid/empty/duplicate catalog group: {group}')
        for target in targets:
            if (not isinstance(target, str) or not re.fullmatch(
                    r'tests/test_[a-zA-Z0-9_]+\.py(?:::[^/\r\n]+)?', target)):
                raise ValueError('Unsafe pytest catalog target')
            file, *node = target.split('::')
            if file not in trees:
                trees[file] = ast.parse((root / file).read_text())
            tree = trees[file]
            if node:
                if group != 'always' or len(node) != 1 or node[0] not in {
                        n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}:
                    raise ValueError(f'Missing or invalid always node: {target}')
            else:
                if file in owners:
                    raise ValueError(f'Multiply owned test: {file}')
                owners[file] = group
    inventory = {p.relative_to(root).as_posix() for p in (root / 'tests').glob('test_*.py')}
    if inventory != set(owners):
        raise ValueError('Test inventory differs from reviewed catalog')
    return catalog, owners


def targets_for(catalog: dict, scopes: set[str], extra: set[str] | None = None) -> list[str]:
    targets = set(catalog['always']) | (extra or set())
    if scopes:
        targets.update(catalog['video_shared'])
    for scope in scopes:
        targets.update(catalog['scopes'][scope])
    # A whole file already collects its always nodes; do not collect them twice.
    return sorted(t for t in targets if '::' not in t or t.split('::')[0] not in targets)


def read_changes(root: Path, base: str, head: str) -> tuple[str, str, list[tuple[str, str]]]:
    # rev-parse validation also prevents options or unresolved/zero event SHAs.
    before = git(root, 'rev-parse', '--verify', '--end-of-options', base + '^{commit}').decode().strip()
    after = git(root, 'rev-parse', '--verify', '--end-of-options', head + '^{commit}').decode().strip()
    fields = git(root, 'diff', '--name-status', '--no-renames', '-z', before, after, '--').split(b'\0')
    if fields[-1] != b'' or (len(fields) - 1) % 2:
        raise ValueError('Malformed NUL-separated tree diff')
    rows = []
    for i in range(0, len(fields) - 1, 2):
        status, path = fields[i].decode(), fields[i + 1].decode()
        if status not in {'A', 'M', 'D', 'T'}:
            raise ValueError('Unexpected tree diff status')
        clean_path(path)
        rows.append((status, path))
    return before, after, rows


def clean_path(path: str) -> None:
    parts = PurePosixPath(path).parts
    if not parts or path.startswith('/') or '..' in parts or any(c in path for c in '\r\n\0\\'):
        raise ValueError('Unsafe or unrepresentable changed path')


def references(root: Path) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    refs: dict[str, set[str]] = defaultdict(set)
    slugs: dict[str, set[str]] = defaultdict(set)

    def strings(value):
        if isinstance(value, dict):
            for child in value.values():
                yield from strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from strings(child)
        elif isinstance(value, str):
            yield value

    for scope, prefixes in PREFIXES.items():
        for prefix in prefixes:
            if not (prefix.startswith(('specs/', 'requests/')) or prefix.endswith('episodes/')):
                continue
            for path in (root / prefix).glob('*.json'):
                value = json.loads(path.read_text())
                if isinstance(value, dict) and isinstance(value.get('slug'), str):
                    slugs[value['slug']].add(scope)
                for text in strings(value):
                    text = text.removeprefix('./')
                    if text.startswith(('assets/', 'data/evidence/', 'data/audio_reviews/')):
                        clean_path(text)
                        refs[text].add(scope)
    return refs, slugs


def dependency_consumers(root: Path, owners: dict[str, str]) -> dict[str, set[str]]:
    """Overapproximate local import/string consumers without executing source.

    Includes function-local imports and source filenames in contract tests.
    Same-basename path collisions only widen coverage. No inferred
    consumer means unknown/full, not permission to skip the changed source.
    """
    sources = {p.relative_to(root).as_posix(): p for folder in ('tools', 'src', 'tests')
               for p in (root / folder).rglob('*.py')}
    by_stem: dict[str, set[str]] = defaultdict(set)
    modules: dict[str, set[str]] = defaultdict(set)
    for path, file in sources.items():
        pieces = list(PurePosixPath(path).with_suffix('').parts)
        pieces = pieces[1:] if pieces[0] == 'src' else pieces
        if pieces[-1] == '__init__':
            pieces.pop()
        modules['.'.join(pieces)].add(path)
        if path.startswith(('tools/', 'tests/')) and file.stem != '__init__':
            modules[file.stem].add(path)
        if file.stem != '__init__':
            by_stem[file.stem].add(path)
    edges = {}
    for path, file in {**sources, **{p: root / p for p in owners}}.items():
        tree = ast.parse(file.read_text())  # Syntax errors cannot create a partial graph.
        docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                      if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                      and n.body and isinstance(n.body[0], ast.Expr)
                      and isinstance(n.body[0].value, ast.Constant)
                      and isinstance(n.body[0].value.value, str)}
        dependencies = set()
        package = list(PurePosixPath(path).parent.parts)
        package = package[1:] if package and package[0] == 'src' else package
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    dependencies.update(modules.get(name.name, set()))
            elif isinstance(node, ast.ImportFrom):
                prefix = node.module or ''
                if node.level:
                    prefix = '.'.join(package[:len(package) - node.level + 1] + ([prefix] if prefix else []))
                dependencies.update(modules.get(prefix, set()))
                for name in node.names:
                    dependencies.update(modules.get(prefix + '.' + name.name, set()))
            elif isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute)):
                function = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
                if function in {'__import__', 'import_module'} and node.args and isinstance(node.args[0], ast.Constant):
                    dependencies.update(modules.get(node.args[0].value, set()))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                for mentioned in re.findall(r'[a-zA-Z0-9_./-]+\.py\b', node.value):
                    dependencies.update(by_stem.get(PurePosixPath(mentioned).stem, set()))
        edges[path] = dependencies - {path}
    consumers: dict[str, set[str]] = defaultdict(set)
    for test in {*owners, 'tests/conftest.py'} & edges.keys():
        seen = set()
        pending = list(edges[test])
        while pending:
            path = pending.pop()
            if path not in seen:
                seen.add(path)
                pending.extend(edges.get(path, set()) - seen)
        for path in seen:
            consumers[path].add(test)
    return consumers


def resource_consumers(root: Path, owners: dict[str, str], scopes: set[str]) -> set[str]:
    """Keep cross-line spec inventory checks at their original function nodes."""
    result = set()
    for file in owners:
        tree = ast.parse((root / file).read_text())

        def reads_family(node):
            literals = [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            for scope in scopes:
                folder = {'reel': 'reels', 'interview': 'interviews', 'explainer': 'explainers', 'news': 'news'}[scope]
                if ('specs' in literals and folder in literals) or any(
                        f'specs/{folder}' in s for s in literals):
                    return True
                if scope == 'explainer' and any('video/episodes' in s for s in literals):
                    return True
            return False

        top = ast.Module(body=[n for n in tree.body if not isinstance(
            n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))], type_ignores=[])
        if reads_family(top):
            result.add(file)
            continue
        for node in tree.body:
            if reads_family(node):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                    result.add(file + '::' + node.name)
                else:
                    # Fixtures/helpers/classes may feed many tests in the file.
                    result.add(file)
    return result


def select(root: Path, rows: list[tuple[str, str]], catalog: dict, owners: dict[str, str]) -> dict:
    def full(reason):
        return {'mode': 'full', 'scopes': list(LINES) + ['other'], 'reason': reason, 'targets': ['tests']}

    if not rows:
        return full('Empty diff cannot establish a narrower scope')
    scopes: set[str] = set()
    explanations = {}
    refs = slugs = consumers = None
    source_changed = False
    for status, path in rows:
        clean_path(path)
        if (path in FULL_PATHS or path.startswith('tests/') or path.endswith('/__init__.py')
                or path.startswith(('assets/fonts/', 'assets/brand/', 'requirements'))):
            return full(f'Test-selection/environment/shared foundation changed: {path}')
        matched = {line for line, prefixes in PREFIXES.items() if path.startswith(prefixes)
                   and path.endswith(('.json', '.jsonl', '.txt'))}
        parts = PurePosixPath(path).parts
        if path.startswith('output/'):
            aliases = {'reel': 'reel', 'interviews': 'interview', 'interview': 'interview',
                       'explainer': 'explainer', 'explainers': 'explainer', 'news': 'news'}
            matched.update(aliases[p] for p in parts[1:3] if p in aliases)
        if path.startswith('.github/workflows/') and PurePosixPath(path).name in WORKFLOWS:
            matched.add(WORKFLOWS[PurePosixPath(path).name])
        if matched:
            scopes.update(matched)
            explanations[path] = sorted(matched)
            continue
        if path in {'README.md', 'CLAUDE.md'} or (path.startswith('docs/') and path.endswith('.md')):
            explanations[path] = ['always']
            continue
        if path.startswith(('assets/', 'data/')):
            # Existing assets can have non-video users. Only newly added,
            # explicitly referenced cover media can take a narrower route.
            if path.startswith('assets/') and (status != 'A' or Path(path).suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp'}):
                return full(f'Existing/shared or non-photo asset changed: {path}')
            if refs is None:
                refs, slugs = references(root)
            matched.update(refs.get(path, set()))
            if path.startswith(('data/evidence/', 'data/audio_reviews/', 'data/narration_checks/')):
                for part in parts[2:]:
                    matched.update(slugs.get(part, set()))
                    matched.update(slugs.get(Path(part).stem, set()))
            if matched:
                scopes.update(matched)
                explanations[path] = sorted(matched)
                continue
        if path.startswith(('tools/', 'src/')) and path.endswith('.py'):
            if status in {'D', 'T'}:
                return full(f'Deleted/retyped source needs base consumers: {path}')
            if consumers is None:
                consumers = dependency_consumers(root, owners)
            # The selector's own case table mentions product source paths as
            # test inputs, not as non-video product consumers. Run that table
            # for source changes without turning it into an ownership edge.
            affected = consumers.get(path, set()) - {'tests/test_production_test_scopes.py'}
            if 'tests/conftest.py' in affected:
                return full(f'Source affects repository-wide test fixtures: {path}')
            groups = {owners[file] for file in affected}
            if not groups or 'other' in groups:
                return full(f'Unknown or non-video source consumers: {path}')
            matched = groups & set(LINES)
            if groups & {'always', 'video_shared'}:
                matched.update(LINES)
            if matched:
                scopes.update(matched)
                explanations[path] = sorted(matched)
                source_changed = True
                continue
        return full(f'Unclassified changed path: {path}')
    extra = resource_consumers(root, owners, scopes) if scopes else set()
    if source_changed:
        extra.add('tests/test_production_test_scopes.py')
    targets = targets_for(catalog, scopes, extra)
    return {'mode': 'scoped', 'scopes': sorted(scopes), 'reason': explanations,
            'targets': targets, 'resource_consumer_targets': sorted(extra)}


def plan(root: Path, base: str, head: str, *, force_full: bool = False) -> dict:
    report = {'schema': 'tennislive.production-test-scope.v1', 'base': base, 'head': head,
              'changed_paths': [], 'catalog_sha256': None}
    try:
        import hashlib
        catalog, owners = load_catalog(root)
        report['catalog_sha256'] = hashlib.sha256((root / CATALOG).read_bytes()).hexdigest()
        if force_full:
            chosen = {'mode': 'full', 'scopes': list(LINES) + ['other'],
                      'reason': 'Manual/scheduled full regression', 'targets': ['tests']}
        else:
            before, after, rows = read_changes(root, base, head)
            report.update(base=before, head=after, changed_paths=[{'status': s, 'path': p} for s, p in rows])
            current = git(root, 'rev-parse', 'HEAD').decode().strip()
            dirty = git(root, 'status', '--porcelain', '--untracked-files=normal', '--',
                        'tools', 'src', 'tests', 'specs', 'requests', 'assets', 'data', '.github/workflows')
            if current != after or dirty:
                raise ValueError('Working inputs differ from the requested committed head')
            chosen = select(root, rows, catalog, owners)
        report.update(chosen)
    except (OSError, ValueError, SyntaxError, TypeError, KeyError, subprocess.CalledProcessError) as exc:
        report.update(mode='full', scopes=list(LINES) + ['other'], targets=['tests'],
                      reason=f'Cannot establish reviewed scope ({type(exc).__name__}); full fallback')
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default='')
    ap.add_argument('--head', default='HEAD')
    ap.add_argument('--full', action='store_true')
    ap.add_argument('--outdir', type=Path, required=True)
    args = ap.parse_args()
    report = plan(ROOT, args.base, args.head, force_full=args.full)
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / 'plan.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    (args.outdir / 'pytest-args.txt').write_text('\n'.join(report['targets']) + '\n')
    print(f"Test scope: {report['mode']}; lines={','.join(report['scopes']) or 'global'}; targets={len(report['targets'])}")


if __name__ == '__main__':
    main()
