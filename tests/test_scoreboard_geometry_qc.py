import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _landed():
    path = ROOT / 'tools' / 'check_reel_landed.py'
    module_spec = importlib.util.spec_from_file_location('score_landed', path)
    landed = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(landed)
    return landed


def test_missing_or_changed_mask_blocks_qc(tmp_path):
    landed = _landed()

    def digest(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    def write(p, value):
        p.write_text(json.dumps(value))
        return p

    spec = {'layout': 'band', 'topbar': {'line1': '2026 美网 1/4决赛'},
            'segments': [{'score_inset': True}]}
    sp = write(tmp_path / 'spec.json', spec)
    film = tmp_path / 'video.mp4'
    folder = tmp_path / 'score_masks'
    folder.mkdir()
    mask = folder / 'segment-01.mkv'
    mask.write_bytes(b'verified mask bytes')
    proof = {'status': 'pass', 'spec_sha256': digest(sp),
             'segments': [{'segment': 0, 'mask': str(mask), 'mask_sha256': digest(mask),
                           'max_extra_source_px': 4, 'gap_bridge_frames': 0,
                           'frames': 30, 'present_frames': 30}]}
    audit = write(tmp_path / 'scoreboard_qc.json', proof)
    write(tmp_path / 'render.json', {'scoreboard_qc_sha256': digest(audit)})
    assert landed.scoreboard_geometry_problem(film, sp, spec) is None
    mask.write_bytes(b'different mask')
    assert 'hash' in landed.scoreboard_geometry_problem(film, sp, spec)
    audit.unlink()
    assert '缺失' in landed.scoreboard_geometry_problem(film, sp, spec)


# render 渲完之后 check_reel_landed 从来不在老的产物目录上重跑；这三条渲在各自那家
# 逐帧蒙版落地（ATP 7122b28f 12:01Z / 金杯 40a68f3b 16:51Z，都是 2026-09-24）之前，
# 本来就没有逐帧证据，已发的不重渲。**只许减不许加**——新渲的片子一律要带证据。
_PRE_MASK_RENDERS = frozenset({
    "bu-zheng-hangzhou-2026-r1",          # 52a47f9b 11:54Z
    "zhang-cocciaretto-bjk-cup-2026-qf",  # 8d07e8c4 14:46Z
    "zheng-paolini-bjk-cup-2026-qf",      # b1c39ef1 15:23Z
})


def test_全出血回贴过板的成片也要带逐帧证据(tmp_path):
    """2026-09-27 全库返工盘点：全出血的「赛场之上」从 9-24 起每一条都走逐帧蒙版
    （ATP / WTA / 金杯 / 拉沃尔杯），QC 这一层原来**只查美网带式**。德约那条
    （0f82e4cf）的形状——60/60 帧没检出、静静退回最宽兜底——要是换个样子回来，
    唯一的产物痕迹就是证据不在、或者某一段一帧板都没有。"""
    landed = _landed()

    def digest(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    spec = {'topbar': {'line1': '2026 ATP250 杭州 第二轮'}, 'scorebox': [98, 920, 519, 1029],
            'segments': [{'score_inset': True}, {'score_inset': False}, {'score_inset': True}]}
    sp = tmp_path / 'spec.json'
    sp.write_text(json.dumps(spec))
    film = tmp_path / 'x.mp4'
    assert landed.scoreboard_evidence_expected(spec)
    assert '缺失' in landed.scoreboard_geometry_problem(film, sp, spec)

    masks = tmp_path / 'score_masks'
    masks.mkdir()
    records = []
    for i in (0, 2):
        m = masks / f'segment-{i + 1:02d}.mkv'
        m.write_bytes(f'mask {i}'.encode())
        records.append({'segment': i, 'frames': 120, 'present_frames': 90, 'board_edges': [300, 320],
                        'right': 324, 'mask': str(m), 'mask_sha256': digest(m)})

    def seal(proof):
        audit = tmp_path / 'scoreboard_qc.json'
        audit.write_text(json.dumps(proof))
        (tmp_path / 'render.json').write_text(json.dumps({'scoreboard_qc_sha256': digest(audit)}))

    seal({'status': 'pass', 'profile': 'atp-tour-v1', 'segments': records})
    assert landed.scoreboard_geometry_problem(film, sp, spec) is None
    seal({'status': 'pass', 'profile': 'atp-tour-v1', 'segments': records[:1]})
    assert '覆盖' in landed.scoreboard_geometry_problem(film, sp, spec)
    blind = [dict(records[0]), records[1]]
    blind[0]['present_frames'] = 0
    seal({'status': 'pass', 'profile': 'atp-tour-v1', 'segments': blind})
    assert '第 1 段 0/120' in landed.scoreboard_geometry_problem(film, sp, spec)

    # 没开回贴的、美网以外的带式老路：没有逐帧证据要查（main 会打印「跳过」）
    assert not landed.scoreboard_evidence_expected({'segments': [{'score_inset': False}]})
    assert not landed.scoreboard_evidence_expected(
        {'layout': 'band', 'topbar': {'line1': '2026 戴维斯杯'}, 'segments': [{'score_inset': True}]})

    # 加餐：产物在的时候（本地沙箱）把仓库里每一条全出血回贴成片都量一遍。
    # CI 的稀疏检出不含蒙版（.mkv），那一段自动不跑——上面的合成判据照跑。
    latest = {}
    for meta in sorted((ROOT / 'output').glob('*/reel/*/render.json')):
        latest[meta.parent.name] = meta.parent
    checked, missing = 0, []
    for slug, outdir in sorted(latest.items()):
        spec_path = ROOT / 'specs' / 'reels' / f'{slug}.json'
        if not spec_path.is_file():
            continue
        real = json.loads(spec_path.read_text(encoding='utf-8'))
        if real.get('layout') == 'band' or not landed.scoreboard_evidence_expected(real):
            continue
        if slug in _PRE_MASK_RENDERS:
            assert landed.scoreboard_geometry_problem(outdir / f'{slug}.mp4', spec_path, real), (
                f'{slug} 已经带逐帧证据了——从 _PRE_MASK_RENDERS 里删掉（只许减不许加）')
            continue
        if not list((outdir / 'score_masks').glob('*.mkv')):
            missing.append(slug)
            continue
        checked += 1
        problem = landed.scoreboard_geometry_problem(outdir / f'{slug}.mp4', spec_path, real)
        assert problem is None, (slug, problem)
    if checked:
        assert checked >= 20 and not missing, (checked, missing)
