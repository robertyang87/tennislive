from pathlib import Path
import hashlib,json,sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import foreground_audio_gate as A


def fixture(tmp_path):
    spec={'slug':'new-match','source_url':'https://example.test/source',
          'segments':[{'start':10.,'end':15.,'quote':[{'at':1.,'end':3.,'text':'What a finish!\n漂亮的收尾！'}]}]}
    source=tmp_path/'source.mp4';source.write_bytes(b'unit-test source identity')
    packet={'source_url':spec['source_url'],'source_sha256':A._sha(source),'method':'asr_then_listened',
            'reviewer':'fixture','reviewed_at':'2026-09-30T23:00:00Z','status':'complete',
            'reviewed_from':10.,'reviewed_to':15.,
            'foreground_english':[{'start':11.,'end':13.,'en':'What a finish!','zh':'漂亮的收尾！'}]}
    transcript=tmp_path/'transcript.json';transcript.write_text(json.dumps(packet))
    review={'schema':A.SCHEMA,'plan_sha256':A.plan_hash(spec),'segments':[
        {'index':0,'transcript_path':'transcript.json','transcript_sha256':A._sha(transcript)}]}
    path=tmp_path/'data/audio_reviews/new-match.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(review))
    return spec,source,transcript,path


def seal(spec, ass):
    film=ass.parent/f"{spec['slug']}.mp4";film.write_bytes(b'synthetic rendered film')
    artifacts={'subtitles.ass':A._sha(ass)}
    offsets=[];cursor=1.;lengths=[]
    for seg in spec['segments']:
        offsets.append(cursor);length=(seg['end']-seg['start'])/float(seg.get('speed') or 1);lengths.append(length);cursor+=length
    A.record_timeline(spec,ass.parent,1.,offsets,lengths)
    binding=ass.parent/'audio_review_binding.json'
    if binding.exists():artifacts[binding.name]=A._sha(binding)
    manifest=ass.parent/'render_inputs.json';manifest.write_text(json.dumps({'film_sha256':A._sha(film),'artifacts':artifacts}))
    (ass.parent/'render.json').write_text(json.dumps({'render_inputs_sha256':A._sha(manifest)}))


def rebind(transcript,path):
    review=json.loads(path.read_text());review['segments'][0]['transcript_sha256']=A._sha(transcript);path.write_text(json.dumps(review))


def test_real_source_identity_and_complete_bilingual_cue_are_required(tmp_path):
    spec,source,_,_=fixture(tmp_path)
    assert len(A.require(spec,root=tmp_path,sources={'':source}))==1
    source.write_bytes(b'different cut')
    with pytest.raises(ValueError,match='源片字节'):A.require(spec,root=tmp_path,sources={'':source})


def test_bare_skip_reason_and_partial_quote_cannot_replace_audio_evidence(tmp_path):
    spec,_,_,path=fixture(tmp_path);path.unlink();spec['segments'][0]['_quote_skip_why']='only crowd'
    with pytest.raises(ValueError,match='waiting_audio_review'):A.require(spec,root=tmp_path)


@pytest.mark.parametrize('mutate',[
    lambda p:p.update(reviewed_to=14),lambda p:p.update(method='asr_only'),
    lambda p:p.update(status='pending'),lambda p:p.update(source_url='https://example.test/other'),
    lambda p:p.update(foreground_english=[]),
    lambda p:p['foreground_english'][0].update(zh=''),
    lambda p:p['foreground_english'][0].update(start=10.2),
    lambda p:p['foreground_english'][0].update(end=15.2),
])
def test_incomplete_or_changed_review_never_passes(tmp_path,mutate):
    spec,_,transcript,path=fixture(tmp_path);packet=json.loads(transcript.read_text());mutate(packet)
    transcript.write_text(json.dumps(packet));rebind(transcript,path)
    with pytest.raises(ValueError):A.require(spec,root=tmp_path)


def test_new_utterance_after_existing_caption_is_not_ignored(tmp_path):
    spec,_,transcript,path=fixture(tmp_path);packet=json.loads(transcript.read_text())
    packet['foreground_english'].append({'start':13.4,'end':14.8,'en':'Another title.','zh':'又一座冠军。'})
    transcript.write_text(json.dumps(packet));rebind(transcript,path)
    with pytest.raises(ValueError,match='缺完整中英字幕'):A.require(spec,root=tmp_path)


def test_own_tts_is_chinese_only(tmp_path):
    spec,_,_,_=fixture(tmp_path);spec['segments'][0]['narration']='中文旁白'
    with pytest.raises(ValueError,match='不叠加英文'):A.require(spec,root=tmp_path)
    spec['segments'][0].pop('quote')
    with pytest.raises(ValueError):A.require(spec,root=tmp_path)


def test_final_ass_must_actually_contain_the_reviewed_cue(tmp_path):
    spec,source,_,_=fixture(tmp_path);A.bind_sources(spec,{'':source},tmp_path,root=tmp_path)
    ass=tmp_path/'subtitles.ass'
    ass.write_text('Dialogue: 0,0:00:02.00,0:00:04.00,TL,,0,0,0,,What a finish!\\N漂亮的收尾！\n')
    seal(spec,ass)
    A.verify_final(spec,ass,1.,root=tmp_path)
    ass.write_text('Dialogue: 0,0:00:02.00,0:00:04.00,TL,,0,0,0,,漂亮的收尾！\n')
    with pytest.raises(ValueError):A.verify_final(spec,ass,1.,root=tmp_path)


def test_renderer_keeps_english_score_verifiable_in_final_ass(tmp_path):
    from tools.build_match_reel import explicit_quote_cues
    from tennislive.video.explainer import write_subtitles

    spec,source,transcript,review_path=fixture(tmp_path)
    en='Oh, and Kalinskaya, from 40–15 up…'
    zh='噢，卡林斯卡娅刚才还40–15领先……'
    spec['segments'][0]['quote'][0]['text']=en+'\n'+zh
    packet=json.loads(transcript.read_text())
    packet['foreground_english'][0].update(en=en,zh=zh)
    transcript.write_text(json.dumps(packet))
    review=json.loads(review_path.read_text())
    review['plan_sha256']=A.plan_hash(spec)
    review['segments'][0]['transcript_sha256']=A._sha(transcript)
    review_path.write_text(json.dumps(review))
    A.bind_sources(spec,{'':source},tmp_path,root=tmp_path)
    cues=explicit_quote_cues(tuple(spec['segments'][0]['quote']),span=5.,offset=1.)
    ass=write_subtitles(cues,tmp_path/'subtitles.ass',height=1440,margin_v=1284)
    seal(spec,ass)
    # The unchanged final gate checks the renderer's actual ASS and source binding.
    A.verify_final(spec,ass,1.,root=tmp_path)


def test_final_bilingual_overlap_is_rejected(tmp_path):
    spec,source,_,_=fixture(tmp_path);A.bind_sources(spec,{'':source},tmp_path,root=tmp_path)
    ass=tmp_path/'subtitles.ass';ass.write_text('Dialogue: 0,0:00:02.00,0:00:04.00,TL,,0,0,0,,What a finish!\\N漂亮的收尾！\nDialogue: 0,0:00:03.00,0:00:04.50,TL,,0,0,0,,Another title\\N又一座冠军\n')
    seal(spec,ass)
    with pytest.raises(ValueError,match='四行'):A.verify_final(spec,ass,1.,root=tmp_path)


def test_production_entrypoints_wire_audio_before_render_and_final_qc():
    for name,needle in [('build_match_reel.py','require_audio_review(spec)'),('production_preflight.py','require_audio_review(spec)'),('check_reel_landed.py','verify_final(spec,')]:
        assert needle in (ROOT/'tools'/name).read_text()
    render=(ROOT/'tools/build_match_reel.py').read_text().split('def render(',1)[1]
    assert render.index('require_audio_review(spec)')<render.index('outdir.mkdir')
    assert 'bind_sources(spec, sources, outdir)' in render


def test_real_render_rejects_missing_audio_review_before_output(tmp_path):
    import build_match_reel as reel
    spec={'slug':'brand-new-without-review','source_url':'https://example.test/source',
          'cover':{},'segments':[{'start':0.,'end':5.,'quote':'What a finish!\n漂亮的收尾！'}]}
    out=tmp_path/'must-not-render'
    with pytest.raises(ValueError,match='waiting_audio_review'):
        reel.render(spec,out,voice='fixture',rate='+0%')
    assert not out.exists()


def test_final_chinese_translation_cannot_be_replaced_with_unrelated_text(tmp_path):
    spec,source,_,_=fixture(tmp_path);A.bind_sources(spec,{'':source},tmp_path,root=tmp_path)
    ass=tmp_path/'subtitles.ass'
    ass.write_text('Dialogue: 0,0:00:02.00,0:00:04.00,TL,,0,0,0,,What a finish!\\N完全无关的中文\n')
    seal(spec,ass)
    with pytest.raises(ValueError):A.verify_final(spec,ass,1.,root=tmp_path)


def test_attenuated_mute_does_not_waive_original_audio_review(tmp_path):
    spec,_,_,path=fixture(tmp_path);spec['segments'][0]['mute']=True;path.unlink()
    with pytest.raises(ValueError,match='waiting_audio_review'):A.require(spec,root=tmp_path)


def test_additional_source_audio_cannot_reuse_old_review(tmp_path):
    spec,_,_,_=fixture(tmp_path);before=A.plan_hash(spec);spec['source_audio']='unreviewed.m4a'
    assert A.plan_hash(spec)!=before
    with pytest.raises(ValueError,match='额外音轨'):A.require(spec,root=tmp_path)


@pytest.mark.parametrize('narration',['中文旁白','   '])
def test_all_retained_source_windows_need_review_even_with_tts_or_whitespace(tmp_path,narration):
    spec,_,_,path=fixture(tmp_path);spec['segments'][0]['narration']=narration;spec['segments'][0].pop('quote');path.unlink()
    with pytest.raises(ValueError,match='waiting_audio_review'):A.require(spec,root=tmp_path)


def test_original_english_in_tts_tail_cannot_be_skipped(tmp_path):
    spec,_,_,path=fixture(tmp_path);spec['segments'][0]['narration']='中文旁白';spec['segments'][0].pop('quote')
    review=json.loads(path.read_text());review['plan_sha256']=A.plan_hash(spec);path.write_text(json.dumps(review))
    with pytest.raises(ValueError,match='话尾之后'):A.require(spec,root=tmp_path)


@pytest.mark.parametrize('text',['中文旁白\\NThis is an extra translation','This is an extra translation','中文旁白 This is an extra English translation'])
def test_english_after_chinese_or_separate_overlay_is_not_cn_only(tmp_path,text):
    spec,source,transcript,path=fixture(tmp_path);spec['segments'][0]['narration']='中文旁白';spec['segments'][0].pop('quote')
    packet=json.loads(transcript.read_text());packet.update(foreground_english=[],no_foreground_english_reason='Synthetic fixture is crowd noise only')
    transcript.write_text(json.dumps(packet));rebind(transcript,path)
    review=json.loads(path.read_text());review['plan_sha256']=A.plan_hash(spec);path.write_text(json.dumps(review))
    A.bind_sources(spec,{'':source},tmp_path,root=tmp_path)
    ass=tmp_path/'subtitles.ass';ass.write_text(f'Dialogue: 0,0:00:02.00,0:00:04.00,TL,,0,0,0,,{text}\n');seal(spec,ass)
    with pytest.raises(ValueError,match='额外英文'):A.verify_final(spec,ass,1.,root=tmp_path)


def test_editing_ass_after_render_cannot_obtain_audio_qc_pass(tmp_path):
    spec,source,_,_=fixture(tmp_path);A.bind_sources(spec,{'':source},tmp_path,root=tmp_path)
    ass=tmp_path/'subtitles.ass';ass.write_text('Dialogue: 0,0:00:02.00,0:00:04.00,TL,,0,0,0,,漂亮的收尾！\n');seal(spec,ass)
    ass.write_text('Dialogue: 0,0:00:02.00,0:00:04.00,TL,,0,0,0,,What a finish!\\N漂亮的收尾！\n')
    with pytest.raises(ValueError,match='只改字幕旁文件'):A.verify_final(spec,ass,1.,root=tmp_path)


def test_changed_cover_offset_cannot_reinterpret_sealed_subtitles(tmp_path):
    spec,source,_,_=fixture(tmp_path);A.bind_sources(spec,{'':source},tmp_path,root=tmp_path)
    ass=tmp_path/'subtitles.ass';ass.write_text('Dialogue: 0,0:00:02.00,0:00:04.00,TL,,0,0,0,,What a finish!\\N漂亮的收尾！\n');seal(spec,ass)
    with pytest.raises(ValueError,match='渲染时使用'):A.verify_final(spec,ass,.5,root=tmp_path)


def test_native_dissolve_keeps_nominal_offsets_and_records_real_subtitle_loop():
    import build_match_reel as reel
    graph=reel.dissolve_filtergraph([1.2,5.,4.],.18)
    assert 'offset=1.200' in graph and 'offset=6.200' in graph
    text=(ROOT/'tools/build_match_reel.py').read_text()
    assert 'audio_cue_offsets.append(offset)' in text
    assert 'record_timeline(spec, outdir, cover_secs, audio_cue_offsets, [seg.length for seg in segments])' in text
