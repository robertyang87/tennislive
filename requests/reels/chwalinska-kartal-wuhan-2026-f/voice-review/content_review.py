"""Current final's actual full dual-ASR evidence; no hearing/tone pass claim."""
from pathlib import Path
import argparse,datetime,json,hashlib
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();job=json.loads((out/'job.json').read_text());mapping=json.loads((out/'asr-input-map.json').read_text());asrs={}
assert mapping['source_bundle_sha256']==job['bundle_sha256']
for model in ['small','large-v3-turbo']:
    path=out/f'asr-{model}.json';d=json.loads(path.read_text());assert d['status']=='complete' and d['input_wav_sha256']==mapping['wav_sha256'] and d['bundle_sha256']==job['bundle_sha256'];asrs[model]=d
rows=[]
for binding,position in zip(job['bindings'],mapping['utterances']):
    assert binding['edit_id']==position['edit_id'] and binding['actual_mp3_sha256']==position['mp3_sha256']
    c=next(x for x in job['coverage'] if x['edit_id']==binding['edit_id'])
    transcripts={model:''.join(s['text'] for s in d['segments'] if s['start']<position['end'] and s['end']>position['start']) for model,d in asrs.items()}
    rows.append(dict(edit_id=binding['edit_id'],expected_display=binding['display_text'],expected_actual_speakable=binding['text'],actual_native_tokens=binding['word_boundary_tokens'],all_name_occurrences=c['names'],all_number_occurrences=c['numbers'],all_ascii_occurrences=c['letters'],asr_context=transcripts,content_interpretation='Actual full ASR outputs inspected for recoverable speech content. Segment-overlap context may include neighboring sentences. ASR orthography/normalization never proves the actual syllable tone.'))
findings=[
dict(scope='intro_coordinates',status='content_supported_by_both_asr',detail='Both actual models recover北京时间2026年10月18日晚上、武汉一千赛女单决赛 and the two finalists. Chinese digits vs Arabic digits normalize differently. 地上native token is intact; no ASR omission of the celebration context.'),
dict(scope='first_set_correction',status='actual_context_supported',detail='Displayed长回合 is actual speakable常回合, native常｜回合; small writes常回合理 and large-v3-turbo长回合里. A fresh actual acoustic contrast is target48, not inherited from an older sentence.'),
dict(scope='set_scores_and_break_points',status='finite_content_inspection_complete',detail='Across actual transcripts: 4比1、6比2、0比2、第五个破发点、二平/两平、三平、4比3、4平、3比2、5比2、第三次机会. small has local spellings三边/两瓶/三瓶/四兵; large-v3-turbo restores most score values. Both spellings and raw word times are retained; no tone pass is inferred.'),
dict(scope='保发',status='actual_dual_asr_signal_requires_acoustic_or_owner_review',detail='Both models write爆发 at second_set_context再保发 and last_game_context又保发. Native tokens are actual保发 in both places; no fake token爆发. This is a bounded bao3/bao4 signal only, addressed by one fresh actual full-sentence calibrated comparison per occurrence (targets49,50). It is not a confirmed misread from ASR.'),
dict(scope='last_game_context',status='content_supported_by_both_asr',detail='Both models recover到了她/他的发球胜赛局、卡尔塔尔接连拿到破发点、第三次机会. Native发球｜胜赛｜局 is a split of the full term, not evidence that a different player served.'),
dict(scope='full_stats',status='numbers_supported_by_both_asr',detail='Both actual models recover赫23制胜分/27非受迫失误、卡32制胜分/36非受迫失误、决胜盘最后4局全被赫拿下. 制胜/智盛、受迫/受破/受魄 are raw ASR spellings, not acoustic tone verdicts.'),
dict(scope='outlook_names_and_scope',status='content_supported_by_both_asr_tones_not_proven',detail='Both recover2009年一千赛制引入后、首个巡回赛单打冠军就是一千赛冠军、前三人大坂直美/安德莱斯库/姆博科、赫第四位、新一周首次世界前二十 and the final question. Both use大阪直美 and姆伯科 spellings; native tokens are intact大坂直美/安德莱斯库/姆博科. This is name/content evidence, not proof of every name syllable tone.'),
dict(scope='brand',status='owner_confirmation_reused_for_exact_actual_bytes',detail='The actual complete brand request, MP3 and raw marks match the earlier owner-confirmed complete utterance. See job.owner_confirmation_reuse; historical machine unknowns remain untouched. This is owner-reported hearing, never assistant hearing.'),
dict(scope='nickname',status='not_present_in_actual_requests',detail='No月亮姐 in any actual request; 赫瓦林斯卡 is the displayed and spoken name.')]
result=dict(schema='tennislive.actual-dual-asr-content-review.v1',slug=job['slug'],created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),bundle_sha256=job['bundle_sha256'],input_wav_sha256=mapping['wav_sha256'],utterances=rows,findings=findings,owner_confirmation_reuse=job.get('owner_confirmation_reuse'),assistant_listening_claimed=False,new_utterances_human_listening_claimed=False,tone_pass_claimed=False,naturalness_pass_claimed=False,pronunciation_release_pass_claimed=False)
(out/'content-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('Actual complete dual-ASR content review recorded for',len(rows),'bound utterances')
