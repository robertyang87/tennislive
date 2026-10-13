"""match-reel 启动缓存的回归判据。"""

from pathlib import Path
import re


WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github/workflows/match-reel.yml"
).read_text(encoding="utf-8")


def _step_block(name: str) -> str:
    """按同级 ``- name`` 边界取一个 workflow step。"""
    lines = WORKFLOW.splitlines()
    start = next(
        i for i, line in enumerate(lines) if line.strip() == f"- name: {name}"
    )
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if (
            len(line) - len(line.lstrip()) == indent
            and line.strip().startswith("- name:")
        ):
            end = i
            break
    return "\n".join(lines[start:end])


def test_apt缓存要能把后补的字体回写():
    """滚动键让 render 补下的字体成为下一趟可恢复的缓存。"""
    block = _step_block("缓存 apt 包（ffmpeg + 字体，绕开镜像抽风）")
    assert "github.run_id" in block
    key = re.search(r"^\s*key:\s*(.+)$", block, re.M)
    restore = re.search(r"^\s*restore-keys:\s*\|\s*\n\s*(.+)$", block, re.M)
    assert key and restore
    prefix = key.group(1).split("${{ github.run_id }}", 1)[0]
    assert restore.group(1).strip() == prefix.strip()


def test_Chromium缓存可启动就不再跑with_deps():
    """真启动成功后早退；失败仍落回原有安装路径。"""
    block = _step_block("装 Chromium")
    smoke = block.index("playwright.chromium.launch")
    fallback = block.index("python -m playwright install --with-deps chromium")
    assert smoke < fallback
    before_fallback = block[:fallback]
    assert "timeout 20 python" in before_fallback
    assert "exit 0" in before_fallback
    assert "raise SystemExit(1)" in before_fallback


def test_mask_cache_is_render_only_atomic_entries_and_saved_only_after_current_qc(tmp_path):
    import os
    import subprocess
    import yaml

    steps = yaml.safe_load(WORKFLOW)['jobs']['reel']['steps']
    restore = next(s for s in steps if s.get('id') == 'scoreboard_mask_cache')
    reset = next(s for s in steps if s.get('name') == '清除上一趟蒙版缓存写入标记')
    render = next(s for s in steps if s.get('name') == 'render — 出成片')
    qc = next(s for s in steps if s.get('name') == '查成片本身合不合格')
    changed = next(s for s in steps if s.get('id') == 'scoreboard_mask_changes')
    save = next(s for s in steps if s.get('name') == '回写完整蒙版缓存（实际成片 QC 通过后）')
    assert steps.index(restore) < steps.index(reset) < steps.index(render) < steps.index(qc) < steps.index(changed) < steps.index(save)
    assert restore['uses'] == 'actions/cache/restore@v4'
    assert save['uses'] == 'actions/cache/save@v4'
    for step in (restore, reset, changed):
        assert step['if'] == "github.event.inputs.mode == 'render'"
    assert save['if'] == "github.event.inputs.mode == 'render' && steps.scoreboard_mask_changes.outputs.changed == 'true'"
    assert not changed.get('continue-on-error') and not qc.get('continue-on-error')
    assert restore['with']['path'] == save['with']['path'] == '~/.cache/tennislive-scoreboard-masks/entries'
    assert render['env']['TENNISLIVE_SCOREBOARD_MASK_CACHE'] == '~/.cache/tennislive-scoreboard-masks'
    key = restore['with']['key']
    assert key.endswith('${{ github.run_id }}-${{ github.run_attempt }}')
    assert '${{ github.event.inputs.slug }}' in key
    assert restore['with']['restore-keys'].strip() == key.split('${{ github.run_id }}')[0]
    assert save['with']['key'] == '${{ steps.scoreboard_mask_cache.outputs.cache-primary-key }}'
    # Execute the real reset/check shell: a restored marker or incomplete
    # staging file must not advertise a complete write in this run.
    cache = tmp_path / '.cache/tennislive-scoreboard-masks'
    cache.mkdir(parents=True)
    (cache / '.dirty').touch()
    (cache / 'partial.tmp').write_bytes(b'incomplete')
    output = tmp_path / 'github-output'
    env = {**os.environ, 'MASK_TEST_ROOT': str(tmp_path), 'GITHUB_OUTPUT': str(output)}
    for script in (reset['run'], changed['run']):
        subprocess.run(['bash', '-e', '-c', script.replace('$HOME', '$MASK_TEST_ROOT')], check=True, env=env)
    assert output.read_text() == 'changed=false\n'
    (cache / '.dirty').touch()  # The helper marks only a committed complete entry.
    output.unlink()
    subprocess.run(['bash', '-e', '-c', changed['run'].replace('$HOME', '$MASK_TEST_ROOT')], check=True, env=env)
    assert output.read_text() == 'changed=true\n'
