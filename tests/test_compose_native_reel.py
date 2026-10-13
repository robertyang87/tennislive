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


@pytest.mark.parametrize('new_asset_bytes', [b'actual new movie', b'wrong movie'])
def test_stale_release_response_is_never_accepted_as_new_movie(monkeypatch,new_asset_bytes):
    import hashlib
    expected=hashlib.sha256(b'actual new movie').hexdigest();calls=[]
    class Response:
        def __init__(self,raw):self.raw=raw
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def raise_for_status(self):pass
        def iter_content(self,size):return iter([self.raw])
    def get(url,**kwargs):
        calls.append(url)
        return Response(b'stale previous movie' if len(calls)==1 else b'actual new movie' if len(calls)==2 else new_asset_bytes)
    monkeypatch.setattr(C.requests,'get',get)
    args=('https://github.com/robertyang87/tennislive/releases/download/reel-match-test/match-test.mp4',expected,len(b'actual new movie'),123)
    if new_asset_bytes==b'actual new movie':
        verified=C.verify_remote_release(*args,retry_wait=0)
        assert verified['sha256']==expected and verified['asset_id']==123
        assert verified['published_url']==calls[2] and f'?v={expected[:12]}' in calls[2]
        assert verified['asset_id_verified']
        assert len(calls)==3 and '/releases/assets/123' in calls[1]
    else:
        with pytest.raises(ValueError,match='full-hash verification'):C.verify_remote_release(*args,retry_wait=0)
        assert len(calls)==3


def archive_fixture(tmp_path, monkeypatch):
    head='a'*40;slug='match-test';monkeypatch.setenv('GITHUB_SHA',head)
    spec=tmp_path/'spec.json'
    spec.write_text(json.dumps({'slug':slug,'outro':False,'segments':[{'start':0,'end':1,'narration':'测试。'}]}))
    film=tmp_path/(slug+'.mp4');film.write_bytes(b'original native movie')
    for name,payload in [('render.json','{}'),('audio_review_binding.json','{}'),
                         ('scoreboard_qc.json','{"segments":[]}'),('subtitles.ass','actual captions'),
                         ('voice_00.mp3','actual voice'),('voice_00.words.json','[]')]:
        (tmp_path/name).write_text(payload)
    R.record(spec,tmp_path,film,tmp_path)
    manifest=json.loads((tmp_path/'render_inputs.json').read_text())
    qc={'status':'pass','slug':slug,'spec_sha256':manifest['spec_sha256'],
        'film_sha256':manifest['film_sha256'],'film_bytes':manifest['film_bytes'],
        'ass_sha256':R.sha256_file(tmp_path/'subtitles.ass'),
        'render_inputs_sha256':R.sha256_file(tmp_path/'render_inputs.json')}
    C.write(tmp_path/'qc_attestation.json',qc)
    meta=json.loads((tmp_path/'render.json').read_text())
    meta.update({'cover_narrated':False,'outro_seconds':0})
    meta['qc_attestation_sha256']=R.sha256_file(tmp_path/'qc_attestation.json')
    C.write(tmp_path/'render.json',meta)
    record={'id':123,'run_number':17,'head_sha':head}
    return slug,spec,record,manifest


def test_native_archive_whitelist_keeps_original_pairs_and_excludes_sources_and_secrets(tmp_path,monkeypatch):
    slug,spec,record,_=archive_fixture(tmp_path,monkeypatch)
    private=['source_main.mp4','source.f140.m4a','source_main_conform.mp4',
             'part_00.mp4','cookies.txt','poster.html','_video.mp4','secret.json']
    for name in private:(tmp_path/name).write_bytes(b'never export')
    paths=C.native_archive_paths(slug,tmp_path,record,spec.read_bytes())
    names={p.name for p in paths}
    assert {slug+'.mp4','voice_00.mp3','voice_00.words.json','render_inputs.json','qc_attestation.json','native_input_archive.json'} <= names
    assert not names.intersection(private)
    assert all(p.parent==tmp_path for p in paths)  # in-place; no duplicate media
    monkeypatch.setattr(C.requests,'get',lambda *a,**kw:pytest.fail('Archive must not fetch overwritten canonical Release'))
    record['_native_input_archive']=True
    C.verified_input(slug,tmp_path,record,spec.read_bytes())
    # A present but damaged native archive cannot silently use the old fallback.
    (tmp_path/'voice_00.words.json').write_text('["changed"]')
    with pytest.raises(ValueError,match='actual file differs'):
        C.verified_input(slug,tmp_path,record,spec.read_bytes())


def test_whitespace_narration_needs_no_unsynthesized_voice_and_preserves_real_segment_index(tmp_path,monkeypatch):
    slug,spec,record,_=archive_fixture(tmp_path,monkeypatch)
    value=json.loads(spec.read_text())
    value['segments'].insert(0,{'start':0,'end':1,'narration':' \t\n '})
    spec.write_text(json.dumps(value))
    for suffix in ('.mp3','.words.json'):
        (tmp_path/('voice_00'+suffix)).rename(tmp_path/('voice_01'+suffix))
    R.record(spec,tmp_path,tmp_path/(slug+'.mp4'),tmp_path)
    manifest=json.loads((tmp_path/'render_inputs.json').read_text())
    qc=json.loads((tmp_path/'qc_attestation.json').read_text())
    qc.update({'spec_sha256':manifest['spec_sha256'],
               'render_inputs_sha256':R.sha256_file(tmp_path/'render_inputs.json')})
    C.write(tmp_path/'qc_attestation.json',qc)
    meta=json.loads((tmp_path/'render.json').read_text())
    meta['qc_attestation_sha256']=R.sha256_file(tmp_path/'qc_attestation.json')
    C.write(tmp_path/'render.json',meta)
    selected={path.name for path in C.native_archive_paths(slug,tmp_path,record,spec.read_bytes())}
    assert {'voice_01.mp3','voice_01.words.json'} <= selected
    assert not {'voice_00.mp3','voice_00.words.json'}.intersection(selected)
    record['_native_input_archive']=True
    C.verified_input(slug,tmp_path,record,spec.read_bytes())
    (tmp_path/'voice_01.mp3').unlink()
    with pytest.raises(ValueError):C.verified_input(slug,tmp_path,record,spec.read_bytes())
    record['_native_input_archive']=False
    with pytest.raises(ValueError):C.native_archive_paths(slug,tmp_path,record,spec.read_bytes())


@pytest.mark.parametrize('damage',['missing_pair','failed_qc','wrong_run','missing_movie'])
def test_native_archive_rejects_incomplete_pairs_failed_qc_and_wrong_identity(tmp_path,monkeypatch,damage):
    slug,spec,record,_=archive_fixture(tmp_path,monkeypatch)
    C.native_archive_paths(slug,tmp_path,record,spec.read_bytes())
    record['_native_input_archive']=True
    if damage=='missing_pair':(tmp_path/'voice_00.mp3').unlink()
    elif damage=='missing_movie':(tmp_path/(slug+'.mp4')).unlink()
    elif damage=='wrong_run':record['id']=999
    else:
        p=tmp_path/'qc_attestation.json';v=json.loads(p.read_text());v['status']='fail';C.write(p,v)
    monkeypatch.setattr(C.requests,'get',lambda *a,**kw:pytest.fail('Do not hide a damaged native archive'))
    with pytest.raises(ValueError):C.verified_input(slug,tmp_path,record,spec.read_bytes())


@pytest.mark.parametrize('kind',['native','legacy','expired_native','ambiguous_native'])
def test_selected_run_prefers_unique_native_archive_and_falls_back_only_when_absent(monkeypatch,kind):
    record={'id':123,'run_number':17,'head_sha':'a'*40,'event':'workflow_dispatch',
            'path':'.github/workflows/match-reel.yml','status':'completed','conclusion':'success'}
    legacy={'id':1,'name':'reel-match-test-17','expired':False}
    native={'id':2,'name':'native-input-match-test-17','expired':kind=='expired_native'}
    others=[{'id':3,'name':'native-input-other-test-17','expired':False},
            {'id':4,'name':'native-input-match-test-16','expired':False}]
    artifacts=[legacy,*others]+([] if kind=='legacy' else [native])
    if kind=='ambiguous_native':artifacts.append(dict(native,id=5))
    monkeypatch.setattr(C,'api',lambda path:dict(record) if path=='actions/runs/123' else {'artifacts':artifacts})
    if kind in ('expired_native','ambiguous_native'):
        with pytest.raises(ValueError):C.source_run('match-test','123')
    else:
        selected,artifact=C.source_run('match-test','123')
        assert artifact['id']==(1 if kind=='legacy' else 2)
        assert selected['_native_input_archive']==(kind=='native')


def test_native_archive_on_later_api_page_is_not_hidden_by_legacy_fallback(monkeypatch):
    record={'id':123,'run_number':17,'head_sha':'a'*40,'event':'workflow_dispatch',
            'path':'.github/workflows/match-reel.yml','status':'completed','conclusion':'success'}
    first=[{'id':i,'name':f'unrelated-{i}','expired':False} for i in range(99)]
    first.append({'id':100,'name':'reel-match-test-17','expired':False})
    native={'id':101,'name':'native-input-match-test-17','expired':False}
    calls=[]
    def api(path):
        calls.append(path)
        if path=='actions/runs/123':return dict(record)
        return {'artifacts':first if path.endswith('page=1') else [native]}
    monkeypatch.setattr(C,'api',api)
    _,selected=C.source_run('match-test','123')
    assert selected['id']==101 and any(path.endswith('page=2') for path in calls)


@pytest.mark.parametrize('enabled',['cover','outro','both','neither'])
def test_native_cover_and_outro_voice_pairs_follow_shared_projection_and_actual_render(tmp_path,monkeypatch,enabled):
    slug,spec,record,_=archive_fixture(tmp_path,monkeypatch)
    value=json.loads(spec.read_text());meta=json.loads((tmp_path/'render.json').read_text())
    value['cover']={'narration':'封面。'} if enabled in ('cover','both') else {}
    value['outro']=enabled in ('outro','both')
    meta['cover_narrated']=bool(value['cover']);meta['outro_seconds']=3.5 if value['outro'] else 0
    spec.write_text(json.dumps(value));C.write(tmp_path/'render.json',meta)
    R.record(spec,tmp_path,tmp_path/(slug+'.mp4'),tmp_path)
    manifest=json.loads((tmp_path/'render_inputs.json').read_text());qc=json.loads((tmp_path/'qc_attestation.json').read_text())
    qc.update({'spec_sha256':manifest['spec_sha256'],'render_inputs_sha256':R.sha256_file(tmp_path/'render_inputs.json')})
    C.write(tmp_path/'qc_attestation.json',qc)
    meta=json.loads((tmp_path/'render.json').read_text());meta['qc_attestation_sha256']=R.sha256_file(tmp_path/'qc_attestation.json');C.write(tmp_path/'render.json',meta)
    extra=[]
    for prefix,active in [('voice_cover',meta['cover_narrated']),('voice_outro',value['outro'])]:
        # Inactive leftover voices must not sneak into the whitelist either.
        for suffix in ('.mp3','.words.json'):
            name=prefix+suffix;(tmp_path/name).write_bytes(b'actual original pair')
            if active:extra.append(name)
    selected={path.name for path in C.native_archive_paths(slug,tmp_path,record,spec.read_bytes())}
    assert set(extra) <= selected
    for prefix,active in [('voice_cover',meta['cover_narrated']),('voice_outro',value['outro'])]:
        assert (prefix+'.mp3' in selected)==active and (prefix+'.words.json' in selected)==active
    record['_native_input_archive']=True
    C.verified_input(slug,tmp_path,record,spec.read_bytes())
    # Both selection and subsequent reads must reject either missing half.
    for name in extra:
        path=tmp_path/name;raw=path.read_bytes();path.unlink()
        with pytest.raises(ValueError):C.verified_input(slug,tmp_path,record,spec.read_bytes())
        record['_native_input_archive']=False
        with pytest.raises(ValueError):C.native_archive_paths(slug,tmp_path,record,spec.read_bytes())
        record['_native_input_archive']=True;path.write_bytes(raw)


def test_native_archive_workflow_precedes_release_and_cleanup_without_continue_on_error(tmp_path,monkeypatch):
    import yaml
    steps=yaml.safe_load((ROOT/'.github/workflows/match-reel.yml').read_text())['jobs']['reel']['steps']
    names=[s.get('name') for s in steps]
    prepare=next(s for s in steps if s.get('id')=='native_archive')
    archive=next(s for s in steps if s.get('name')=='保留本次原生输入（不进 git）')
    assert names.index('查成片本身合不合格') < steps.index(prepare) < steps.index(archive) < names.index('成片发到 Release（不进 git）') < names.index('丢掉不进仓库的中间物')
    assert archive['if']=="github.event.inputs.mode == 'render'"
    assert not archive.get('continue-on-error')
    assert archive['with']['path']=='${{ steps.native_archive.outputs.paths }}'
    assert archive['with']['retention-days']==14
    assert archive['with']['if-no-files-found']=='error'
    assert 'native_archive_paths(' in prepare['run']
    assert 'copy' not in prepare['run'] and '||' not in prepare['run']
    # Execute the actual workflow selector, not a duplicate list of globs.
    slug,spec,record,_=archive_fixture(tmp_path,monkeypatch)
    spec_path=tmp_path/'specs/reels'/f'{slug}.json';spec_path.parent.mkdir(parents=True)
    spec_path.write_bytes(spec.read_bytes())
    (tmp_path/'tools').symlink_to(ROOT/'tools',target_is_directory=True)
    for name in ('source.mp4','cookies.txt','part_00.mp4'):(tmp_path/name).write_bytes(b'excluded')
    output=tmp_path/'github-output.txt'
    result=subprocess.run(['bash','-e','-c',prepare['run']],cwd=tmp_path,
                          env={**os.environ,'PYTHONPATH':str(ROOT/'src'),
                               'NATIVE_SLUG':slug,'NATIVE_OUTDIR':str(tmp_path),
                               'GITHUB_RUN_ID':str(record['id']),'GITHUB_RUN_NUMBER':str(record['run_number']),
                               'GITHUB_SHA':record['head_sha'],'GITHUB_OUTPUT':str(output)},
                          capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    selected=[Path(line).name for line in output.read_text().splitlines()[1:-1]]
    assert 'native_input_archive.json' in selected and slug+'.mp4' in selected
    assert not {'source.mp4','cookies.txt','part_00.mp4'}.intersection(selected)
