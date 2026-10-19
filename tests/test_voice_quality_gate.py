"""Actual-input approval coverage and invalidation, using synthetic test bytes only."""
import hashlib
import json
from pathlib import Path
import zipfile
import pytest
import voice_quality_gate as gate


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def episode(tmp_path):
    root = tmp_path
    out = root / 'output' / 'test-episode'
    out.mkdir(parents=True)
    spec = root / 'specs/reels/test-episode.json'
    spec.parent.mkdir(parents=True)
    write(spec, {'slug': out.name, 'segments': [{'narration': '冠军。'}]})
    film = out / 'test-episode.mp4'
    film.write_bytes(b'synthetic-test-film')
    bundle = root / 'actual-bundle.zip'
    entries = []
    with zipfile.ZipFile(bundle, 'w') as z:
        for index in range(2):
            req = {'text': f'冠军{index}。', 'voice': 'test-voice', 'rate': '+6%',
                   'pitch': '+0Hz', 'style': '', 'styledegree': '',
                   'lead_pause': 0.0, 'backend': 'edge'}
            fields = ['text', 'voice', 'rate', 'pitch', 'style', 'styledegree', 'lead_pause']
            req['cache_key'] = hashlib.sha256('\x1f'.join(str(req[k]) for k in fields).encode()).hexdigest()[:32]
            rid = gate._sha(gate._canonical(req))
            audio = f'synthetic-audio-{index}'.encode()
            marks = json.dumps([{'text': req['text'], 'offset': 0, 'duration': 100}]).encode()
            z.writestr(f'requests/{rid}/audio.mp3', audio)
            z.writestr(f'requests/{rid}/marks.json', marks)
            entries.append({'request_id': rid, 'request': req,
                            'audio_sha256': gate._sha(audio), 'marks_sha256': gate._sha(marks)})
            folder = out if index == 0 else out / '_tkvoice_test'
            folder.mkdir(exist_ok=True)
            (folder / f'voice_{index:02d}.mp3').write_bytes(audio)
            (folder / f'voice_{index:02d}.words.json').write_bytes(marks)
        z.writestr('manifest.json', json.dumps({'schema': 'tennislive.frozen-tts-bundle.v1',
                    'artifact_kind': 'native_tts_inputs', 'quality_approval': False,
                    'entries': entries}))
    manifest = {'spec_sha256': digest(spec), 'film_sha256': digest(film),
                'film_bytes': film.stat().st_size, 'artifacts': {}}
    write(out / 'render_inputs.json', manifest)
    render = {'film_sha256': digest(film), 'render_inputs_sha256': digest(out/'render_inputs.json'),
              'tts_bundle': {'bundle_sha256': digest(bundle), 'request_count': 2}}
    write(out / 'render.json', render)
    gate.capture_inventory(out, spec=spec, bundle=bundle, root=root)
    manifest['artifacts'][gate.INVENTORY] = digest(out/gate.INVENTORY)
    write(out/'render_inputs.json', manifest)
    render['render_inputs_sha256'] = digest(out/'render_inputs.json')
    write(out/'render.json', render)
    gate.prepare(out, root=root)
    return root, out, bundle, spec


def approve(episode):
    root, out, _, _ = episode
    review = json.loads((out/gate.REVIEW).read_text())
    inventory = json.loads((out/gate.INVENTORY).read_text())
    hashes = {e['id']: e['audio_sha256'] for e in inventory['entries']}
    for row in review['entries']:
        for scope in ['phonetics', 'prosody']:
            row[scope].update(status='pass', method='full_audio_listening',
                             reviewer='Synthetic fixture reviewer', reviewed_at='2026-10-19T15:00:00Z',
                             whole_audio=True, audio_sha256=hashes[row['id']],
                             observations='Fixture declaration only, never production approval.')
    review['film_review'].update(status='pass', method='full_audio_listening',
                               reviewer='Synthetic fixture reviewer', reviewed_at='2026-10-19T15:00:00Z',
                               whole_narration_and_seams=True,
                               film_sha256=review['identity']['film_sha256'],
                               observations='Fixture whole-mix declaration only.')
    write(out/gate.REVIEW, review)
    return review


def test_prepare_pending_and_check_never_writes_approval(episode):
    root, out, _, _ = episode
    before = (out/gate.REVIEW).read_bytes()
    assert gate.main(['--check','--outdir',str(out),'--root',str(root)]) == 1
    assert (out/gate.REVIEW).read_bytes() == before
    with pytest.raises(gate.VoiceQualityError, match='already exists'):
        gate.prepare(out, root=root)


def test_complete_review_can_use_sealed_inventory_after_native_cleanup(episode):
    root, out, bundle, _ = episode
    approve(episode)
    bundle.unlink()
    for p in list(out.rglob('voice_*.mp3')) + list(out.rglob('voice_*.words.json')):
        p.unlink()
    assert gate.require_publish(out, root=root)['film_sha256']


def test_one_sample_cannot_approve_all_utterances(episode):
    root, out, _, _ = episode
    review = approve(episode)
    review['entries'] = review['entries'][:1]
    write(out/gate.REVIEW, review)
    with pytest.raises(gate.VoiceQualityError, match='every actual'):
        gate.require_publish(out, root=root)


@pytest.mark.parametrize('scope,method', [('phonetics','asr'),('prosody','asr'),('prosody','word_marks')])
def test_recognition_or_marks_are_not_full_listening(episode, scope, method):
    root, out, _, _ = episode
    review = approve(episode)
    review['entries'][0][scope]['method'] = method
    write(out/gate.REVIEW, review)
    with pytest.raises(gate.VoiceQualityError, match='pending'):
        gate.require_publish(out, root=root)


@pytest.mark.parametrize('target', ['audio','words','spec','render','inventory','film'])
def test_changed_bound_input_invalidates_review(episode, target):
    root, out, _, spec = episode
    approve(episode)
    paths = {'audio':out/'voice_00.mp3','words':out/'voice_00.words.json',
             'spec':spec,'render':out/'render.json','inventory':out/gate.INVENTORY,
             'film':out/f'{out.name}.mp4'}
    p = paths[target]
    if p.suffix == '.json':
        value = json.loads(p.read_text())
        if isinstance(value, list):
            value[0]['text'] = 'changed words'
        else:
            value['_changed'] = True
        write(p,value)
    else:
        p.write_bytes(p.read_bytes()+b'changed')
    with pytest.raises(gate.VoiceQualityError):
        gate.require_publish(out, root=root)


def test_new_native_segment_outside_review_is_rejected(episode):
    root,out,_,_=episode
    approve(episode)
    (out/'voice_99.mp3').write_bytes(b'unreviewed-new-utterance')
    with pytest.raises(gate.VoiceQualityError,match='appeared'):
        gate.require_publish(out,root=root)


def test_hash_binding_alone_does_not_approve_actual_film_mix(episode):
    root,out,_,_=episode
    review=approve(episode)
    review.pop('film_review')
    write(out/gate.REVIEW,review)
    with pytest.raises(gate.VoiceQualityError,match='film narration'):
        gate.require_publish(out,root=root)


def test_temporary_source_mp4_does_not_masquerade_as_formal_movie(episode):
    root,out,_,_=episode
    approve(episode)
    (out/'_segment_source.mp4').write_bytes(b'temporary-source')
    assert gate.require_publish(out,root=root)


@pytest.mark.parametrize('pause',[float('nan'),float('inf'),float('-inf')])
def test_nonfinite_pause_is_rejected(episode,pause):
    _,out,_,_=episode
    request=json.loads((out/gate.INVENTORY).read_text())['entries'][0]['request']
    request['lead_pause']=pause
    with pytest.raises(gate.VoiceQualityError,match='lead_pause'):
        gate._request(request)
