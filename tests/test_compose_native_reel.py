from pathlib import Path
import copy,json,os,subprocess,sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import compose_native_reel as C
import render_inputs as R
from foreground_audio_gate import plan_hash


def recipe_fixture():
    spec={'slug':'match-test','sources':{'main':'https://example.test/source'},'segments':[{'start':1.,'end':3.,'bed':'low','narration':'测试。','subtitle_bottom':306}]}
    video=R.project(spec);video['segments'][0]['bed']='mid'
    audio=R.project(spec);audio['segments'][0]['subtitle_bottom']=360
    vm={'projection':video,'assets':{}};am={'projection':audio,'assets':{}}
    meta={'cover_seconds':1.,'outro_seconds':0.,'film_seconds':3.,'segments_seconds':2.,'narration_voice':'voice','narration_rate':'+6%','narration_backend':'edge','narration_seconds':{'0':1.}}
    binding={'sources':{'main':'a'*64},'timeline':{'cover_seconds':1.,'offsets':[1.],'lengths':[2.]}}
    ab=copy.deepcopy(binding);ab['plan_sha256']=plan_hash(spec)
    return spec,vm,am,meta,copy.deepcopy(meta),binding,ab


def test_split_recipes_allow_only_proven_visual_and_audio_changes(tmp_path):
    values=recipe_fixture();C.verify_recipes(*values,tmp_path)
    # Different current crop cannot be excused by matching only audio plan.
    bad=list(copy.deepcopy(values));bad[0]['segments'][0]['cx']=.6
    with pytest.raises(ValueError,match='video recipe'):C.verify_recipes(*bad,tmp_path)
    # Raising the bed is exactly the unwanted change this path must reject.
    bad=list(copy.deepcopy(values));bad[0]['segments'][0]['bed']='mid'
    with pytest.raises(ValueError,match='audio recipe'):C.verify_recipes(*bad,tmp_path)
    bad=list(copy.deepcopy(values));bad[6]['timeline']['offsets']=[1.1]
    with pytest.raises(ValueError,match='timeline'):C.verify_recipes(*bad,tmp_path)
    bad=list(copy.deepcopy(values));bad[0]['segments'][0]['voice']={'rate':'+9%'}
    with pytest.raises(ValueError):C.verify_recipes(*bad,tmp_path)


def test_actual_native_movie_and_artifact_hashes_cannot_be_redeclared(tmp_path,monkeypatch):
    slug='match-test';head='a'*40;monkeypatch.setenv('GITHUB_SHA',head)
    spec=tmp_path/'spec.json';spec.write_text(json.dumps({'slug':slug,'segments':[]}))
    film=tmp_path/f'{slug}.mp4';film.write_bytes(b'original native bytes')
    (tmp_path/'render.json').write_text('{}')
    (tmp_path/'audio_review_binding.json').write_text('{}')
    (tmp_path/'scoreboard_qc.json').write_text('{"segments":[]}')
    R.record(spec,tmp_path,film,tmp_path)
    C.verified_input(slug,tmp_path,{'head_sha':head},spec.read_bytes())
    film.write_bytes(b'changed movie')
    with pytest.raises(ValueError,match='Actual input movie'):C.verified_input(slug,tmp_path,{'head_sha':head},spec.read_bytes())
    with pytest.raises(ValueError,match='identity'):C.verified_input(slug,tmp_path,{'head_sha':'b'*40},spec.read_bytes())


def test_real_stream_copy_preserves_every_payload_and_timestamp(tmp_path):
    import shutil
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg unavailable')
    video=tmp_path/'video.mp4';audio=tmp_path/'audio.mp4';result=tmp_path/'composed.mp4'
    for path,hz in [(video,440),(audio,880)]:
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=black:s=64x64:r=25:d=1','-f','lavfi','-i',f'sine=frequency={hz}:sample_rate=48000:duration=1','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(path)],check=True)
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(video),'-i',str(audio),'-map','0:v','-map','1:a','-c','copy','-movflags','+faststart',str(result)],check=True)
    assert C.packet_proof(video,result,'v:0')['exact_payload_and_timestamps_match']
    assert C.packet_proof(audio,result,'a:0')['exact_payload_and_timestamps_match']
    with pytest.raises(ValueError,match='packet timestamps'):C.packet_proof(video,result,'a:0')
