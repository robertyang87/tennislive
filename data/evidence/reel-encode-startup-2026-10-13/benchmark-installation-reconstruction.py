"""Reconstructed after measurement: repeats original recorded commands.

The original benchmark was an inline exec_command heredoc, not this file.
Outputs rerun-results.json so the original results.json remains immutable.
"""
import json
import os
from pathlib import Path
import shlex
import statistics
import subprocess
import time
import venv

folder = Path(__file__).resolve().parent
root = Path(os.environ.get('TENNISLIVE_BENCH_REPO', '/workspace/tennislive-probe-speed'))
provenance = json.loads((folder / 'provenance.json').read_text())
venv.EnvBuilder(with_pip=True, system_site_packages=True).create(folder / 'rerun-venv')
python = str(folder / 'rerun-venv/bin/python')
source = next(line for line in provenance['workflow_bootstrap_script_at_measurement'].splitlines()
              if line.strip().startswith('python -c'))
commands = {
    'old_editable': [python, '-m', 'pip', 'install', '-q', '-e', '.[pronunciation]'],
    'new_extra_requirements': [python, *shlex.split(source)[1:]],
}
rows = []
for i in range(4):
    for label, command in commands.items():
        start = time.perf_counter()
        subprocess.run(command, cwd=root, check=True, capture_output=True, text=True)
        elapsed = time.perf_counter() - start
        if i:
            rows.append({'pair': i, 'kind': label, 'elapsed_seconds': elapsed})
        print(i, label, round(elapsed, 3), flush=True)
subprocess.run([python, '-c', 'import pypinyin, tennislive; print(pypinyin.__version__)'],
               cwd=root, check=True, env={**os.environ, 'PYTHONPATH': 'src'})
(folder / 'rerun-results.json').write_text(json.dumps({
    'raw': rows,
    'median_seconds': {label: statistics.median(r['elapsed_seconds'] for r in rows
                                               if r['kind'] == label)
                       for label in commands},
}, indent=2) + '\n')
