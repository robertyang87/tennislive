import hashlib
import importlib.util
import json
from pathlib import Path


def test_missing_or_changed_mask_blocks_qc(tmp_path):
    path=Path(__file__).resolve().parents[1] / 'tools' / 'check_reel_landed.py'
    module_spec=importlib.util.spec_from_file_location('score_landed',path)
    landed=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(landed)
    def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
    def write(p,value):p.write_text(json.dumps(value));return p
    spec={'layout':'band','topbar':{'line1':'2026 美网 1/4决赛'},'segments':[{'score_inset':True}]}
    sp=write(tmp_path/'spec.json',spec);film=tmp_path/'video.mp4'
    folder=tmp_path/'score_masks';folder.mkdir();mask=folder/'segment-01.mkv';mask.write_bytes(b'verified mask bytes')
    proof={'status':'pass','spec_sha256':digest(sp),'segments':[{'segment':0,'mask':str(mask),'mask_sha256':digest(mask),'max_extra_source_px':4,'gap_bridge_frames':0,'frames':30,'present_frames':30}]}
    audit=write(tmp_path/'scoreboard_qc.json',proof)
    write(tmp_path/'render.json',{'scoreboard_qc_sha256':digest(audit)})
    assert landed.scoreboard_geometry_problem(film,sp,spec) is None
    mask.write_bytes(b'different mask')
    assert 'hash' in landed.scoreboard_geometry_problem(film,sp,spec)
    audit.unlink()
    assert '缺失' in landed.scoreboard_geometry_problem(film,sp,spec)
