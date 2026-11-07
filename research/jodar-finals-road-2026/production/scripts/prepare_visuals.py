import json,zipfile,re,sys,shutil,hashlib
from pathlib import Path
ROOT=Path('/dev/shm/jodar-production/native');BASE=Path('/workspace/jodar-finals-production');SLUG='jodar-finals-road-2026'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'src')]
import build_match_reel as reel
from tennislive.video.transition_cards import render_clip

specfile=ROOT/f'specs/reels/{SLUG}.json';spec=json.load(open(specfile))
bindings={r['segment_id']:r for r in json.load(open(BASE/'research/photos/narration-photo-binding.json'))['bindings']}
z=zipfile.ZipFile('/dev/shm/jodar-production/jodar-tts-bundle.zip');bundle=json.loads(z.read('manifest.json'));entries={r['request']['text']:r for r in bundle['entries']}
clean=lambda t:re.sub(r'[^\w]','',t)
assets=ROOT/f'assets/reel/{SLUG}';voices=Path('/dev/shm/jodar-production/frozen-voices');voices.mkdir(exist_ok=True)
cardtext={'fact-ao':('资格赛突围\n澳网正赛首胜','2026 · 第2轮负门西克'),'fact-wim-r3':('先赢一盘\n负于望月慎太郎','2026 · 温网第3轮'),'fact-us-r1':('美网首轮\n三盘负布云朝克特','2026 赛季'),'fact-paris-r2':('巴黎第2轮\n等待年终资格','2026 · 负于鲁德')}
rows=[];proof=[]
for index,segment in enumerate(spec['segments']):
    if not segment.get('narration'):continue
    ident=segment['_id'];entry=entries[reel.speakable(segment['narration'])];rid=entry['request_id'];marks=json.loads(z.read(f'requests/{rid}/marks.json'))
    length=round(entry['duration_seconds']+.4,3);segment['seconds']=length
    audio=voices/f'{ident}.mp3';wordfile=voices/f'{ident}.words.json';audio.write_bytes(z.read(f'requests/{rid}/audio.mp3'));wordfile.write_bytes(z.read(f'requests/{rid}/marks.json'))
    voiceproof={'id':ident,'segment':index+1,'text':segment['narration'],'spoken':entry['duration_seconds'],'picture':length,'audio':str(audio),'words':str(wordfile),'request_id':rid,'audio_sha256':entry['audio_sha256'],'marks_sha256':entry['marks_sha256']}
    if ident=='race_table':
        source=BASE/'production/race-chart/race-points-qualified.png';shutil.copyfile(source,assets/'race-points-qualified.png');segment['image']=f'assets/reel/{SLUG}/race-points-qualified.png';segment['image_kind']='canvas';segment['subtitle_bottom']=100;segment['_canvas_caption_safety']='Rootverified15row/8qualifiedRace; currentnative bottommargin100 placescaptions at1340 above1394sourcefooter. Actualepisodepixelpreview required.';proof.append(voiceproof);continue
    elements=bindings[ident]['elements'];cuts=[0.]
    if len(elements)>1:
        target=len(clean(reel.speakable(elements[0]['exact_narration_clause'])));total=0
        for j,mark in enumerate(marks):
            total+=len(clean(mark['text']))
            if total>=target:
                cuts.append(round(marks[j+1]['offset']/1e7 if j+1<len(marks) else (mark['offset']+mark['duration'])/1e7,4));break
        if len(cuts)!=2:raise ValueError((ident,target,total))
    cuts.append(length);shots=[]
    for j,element in enumerate(elements):
        if element['kind']=='photograph':
            source=Path(element['local_path']);dest=assets/'photos'/source.name;dest.parent.mkdir(exist_ok=True)
            if not dest.exists():shutil.copyfile(source,dest)
            shots.append({'kind':'photo','path':str(dest),'cx':element['cx'],'cy':element['cy'],'label':element['asset_id'],'static':element['asset_id']=='marrakech-event-2932','semantic_clause':element['exact_narration_clause']})
        else:
            key=element.get('card_id') or Path(element['local_path']).stem;text,kicker=cardtext[key];seconds=cuts[j+1]-cuts[j]+(.28 if j<len(elements)-1 else .56)
            dest=assets/'native-factcards'/f'{key}.mp4';dest.parent.mkdir(exist_ok=True)
            render_clip(text,dest,seconds=seconds,fps=25,kicker=kicker,size=(1080,1440))
            shots.append({'kind':'native_card','path':str(dest),'cx':.5,'cy':.5,'label':key,'static':True,'semantic_clause':element['exact_narration_clause'],'native_component':'tennislive.video.transition_cards.render_clip','title':text,'kicker':kicker})
    mixed=any(s['kind']=='native_card' for s in shots);segment['image']=f'assets/reel/{SLUG}/visual-sequences/{ident}.mp4';segment['image_kind']='canvas' if mixed else 'photo'
    if mixed:
        segment.pop('_photo_source',None);segment.pop('_photo_caption_safety',None);segment['_canvas_caption_safety']='Nativecommontransitioncardcomponent plus exactsameeventprofessionalphoto inputs, synchronized at realwholeutterance WordBoundaryclause; noextraInfoinset orTTSsplit. Actualnativepixelpreview beforeformalrequired.'
    else:
        segment['_photo_source']=elements[0]['source_url'];segment['_photo_caption_safety']='Actualroot/photo fixedsourcecrop identity review, sameevent/photosmatchedtorealvoicephrases. Marrakechoriginal1024x1280crop960x1280→1080x1440=1.125xstaticnoextraZoom, explicitlyapprovedbodyonly; othershighresprofessional. Exactmanifestretainsprovenance, finalnativepixelpreviewrequired.'
    row={'segment':index,'id':ident,'seconds':length,'output':str(assets/'visual-sequences'/f'{ident}.mp4'),'shots':shots,'cuts':cuts};rows.append(row);proof.append({**voiceproof,'actual_phrase_cuts':cuts})
specfile.write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
(BASE/'production/visual-sequence-manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
(BASE/'production/actual-16-voice-manifest.json').write_text(json.dumps({'status':'actual_frozen_inputs_only_not_acoustic_or_film_approval','bundle_sha256':hashlib.sha256(Path('/dev/shm/jodar-production/jodar-tts-bundle.zip').read_bytes()).hexdigest(),'native_request_count':len(entries),'body':proof},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'body_spoken':sum(p['spoken'] for p in proof),'body_picture':sum(p['picture'] for p in proof),'source_picture':sum(s['end']-s['start'] for s in spec['segments'] if s.get('source')),'visual_sequences':len(rows),'requests':len(entries)},ensure_ascii=False))
