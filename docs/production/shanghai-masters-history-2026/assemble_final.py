"""Assemble this episode from reviewed original windows and native photographs."""
from pathlib import Path
import copy
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
import foreground_audio_gate as gate

BASE = ROOT / 'docs/production/shanghai-masters-history-2026'
draft = json.loads((BASE / 'native-spec.draft.json').read_text())
edl = {r['id']: r for r in json.loads((BASE / 'source-audio-reviewed-edl.json').read_text())['segments']}
photos = json.loads((BASE / 'photo-plan.json').read_text())['photos']
spec = copy.deepcopy(draft)
spec['push'] = {'title': '费德勒与几代大师：上海的白玉兰传奇'}
spec['tts_backend'] = 'edge'
spec['_tts_backend_why'] = 'Native Edge/Yunjian +6%: all44 final body paragraphs plus cover and outro were actually synthesized, measured and source-bound. The merged2005 paragraph was separately remeasured; no character-count duration estimate is used.'
spec['_tennistv_trim'] = 'Fixed1920×1080 center crop[555,0,1365,1080] excludes the source corner watermark. Selected source ends:2005 343.00,2012 106.48 before111.5 end card,2014 381.96,2024 473.40,2025 389.744. Actual source-tail contact sheets reviewed; none of these selected windows includes the Tennis TV brand end card. No2017 original-audio window is selected; its official trophy photograph is used as a photograph. Explicit audio_tail:silence prevents the next unreviewed sentence entering dissolve handles.'
spec['story_photo_motion'] = 'push'
spec['_story_photo_motion_why'] = 'Use the existing native fixed-center 3% photographic push; retain the column typography, colors, full-canvas layout and native title cards.'
spec['segments'] = []
entries = []

def photo(row, filename):
    p = next(x for x in photos if x['file'].endswith(filename))
    row = copy.deepcopy(row)
    for k in ('title_card', 'kicker', 'image', 'image_kind', '_credit', '_original_photo'):
        row.pop(k, None)
    row.update(image=p['file'], image_kind='photo',
               _photo_source=spec['sources'][p['source_name']],
               _credit='Tennis TV / ATP Media; photographer not individually stated',
               _photo_caption_safety='Actually viewed source frame: face and identifying gesture are above the native lower subtitle area. ' + p['caption'],
               _photo_provenance=p)
    return row

def reviewed(row, identifier, *, narration=None, end=None):
    e = edl[identifier]
    assert e['review']['status'] == 'complete' and not e['uncertain_spans']
    out = {k: v for k, v in row.items() if k.startswith('_') and k not in ('_audio_review_status', '_crop_review_status', '_quote_provenance', '_picture_limit', '_quote_skip_why')}
    out.update(source=e['source'], start=e['start'], end=end or e['end'],
               cx=.5, track=False, fit='crop', bed='high', audio_tail='silence',
               _reviewed_edl_id=identifier,
               _crop_tradeoff='Fixed center fills the native canvas. Some wide running or edge gestures leave the crop; this is a historical film, not a claim that every full-width action is visible.')
    if narration:
        assert not e['utterances']
        out['narration'] = narration
        out['_quote_skip_why'] = e['_quote_skip_why']
    elif e['utterances']:
        out['quote'] = [{'at': round(u['start']-e['start'], 4),
                         'end': round(u['end']-e['start'], 4),
                         'text': u['en']+'\n'+u['zh']} for u in e['utterances']]
    else:
        out['_quote_skip_why'] = e['_quote_skip_why']
    entries.append({'index': len(spec['segments']), **{k: e['review'][k] for k in ('transcript_path', 'transcript_sha256')}})
    return out

replacements = {9:'2005-nalbandian-focus.jpg',14:'2005-nalbandian-champion-smile.jpg',
                23:'2012-djokovic-champion-celebration.jpg',25:'2012-murray-postmatch-portrait.jpg',
                27:'2014-federer-r2-relief.jpg',43:'2024-sinner-winner-reaction.jpg',
                47:'2025-vacherot-winner-emotion.jpg',51:'2025-cousins-awards-portrait.jpg'}
raw = {19:'final2012-first-championship-point',22:'final2012-second-set-point',
       24:'final2012-match-and-handshake',28:'mayer2014-fourth-match-point',
       44:'sinner2024-champion-call'}
for i,row in enumerate(draft['segments']):
    if i in (12,13,34,49):
        continue
    if i==11:
        merged = row['narration'] + draft['segments'][12]['narration']
        row = reviewed(row,'cup2005-vo-effects',narration=merged)
        row['_picture_scope'] = 'Actual fifth-set 6-5/30-40 counterbreak footage; narration first recalls the prior 30-0 lead. This is illustrative later action, not the service opening or championship celebration.'
        row.pop('_voice_basis',None)
    elif i==48:
        spec['segments'].append(reviewed(draft['segments'][49],'vacherot2025-final-point-call'))
        spec['segments'][-1]['point_end_ok'] = 'Actually viewed the 381.90s end frame: both finalists are reaching hands at the net. Final point ended at368.60; the guessed382.32 score transition is a later camera change, not live play.'
        row = reviewed(row,'vacherot2025-hug-vo',narration=row['narration'],end=round(381.9+row['seconds'],3))
        row['_picture_scope'] = 'Actual on-court embrace after this final; no awards photo substituted for the embrace.'
        row['point_end_ok'] = 'Actually viewed389.744s end frame: the cousins are embracing in close-up, long after the final point. The guessed390.48 score transition is not a live point.'
    elif i in raw:
        row = reviewed(row,raw[i])
        if i==24:
            row['point_end_ok'] = 'Actually viewed106.48s end frame: Djokovic raises both arms after winning the match. The final point ended before90s; guessed107.52 score transition is a camera change during celebration.'
        if i==44:
            row['point_end_ok'] = 'Window is already post-point winner reaction and approach to the net; no live rally is cut.'
            row['_picture_scope'] = 'Post-title Sinner reaction and complete championship commentary, not a claim of full championship-point footage.'
    elif i in replacements:
        row = photo(row,replacements[i])
    elif i==26:
        row=copy.deepcopy(row)
        row['title_card']='2014上海大师赛\n首战救下5个赛点'
    if row.get('image', '').endswith('qizhong-interior-portrait.jpg'):
        row = copy.deepcopy(row)
        row['_photo_source'] = 'https://en.rolexshanghaimasters.com/en/media/news/shanghai-2026-atp-masters-1000-history-draw-schedule'
        row['_original_photo'] = 'assets/reel/shanghai-masters-history-2026/qizhong-2026-resource.jpg'
        row['_credit'] = 'Jade Gao / AFP via Getty Images'
        row['_photo_caption_safety'] = 'Actually viewed full-canvas stadium interior: the roof and playing court are above the lower subtitle area. Official page published2026; capture date not claimed. It illustrates the venue, not cancellation-year conditions or2019 attendance.'
    if row.get('source'):
        row['crosses_cut'] = 'Retained original same-event highlight camera changes between these named competitors and their reactions; narration/comments remain about this same match. No different-year or different-round action is inserted.'
    spec['segments'].append(row)

spec['_draft_assembly'] = {'status':'review_cut_ready', 'original_audio':'Only whole-window source-bound asr_cross_checked packets are selected; no claim of human listening.',
                           'omitted_uncertain':'2017 championship commentary omitted rather than inventing its words. Original 2005 final point is not presented as a complete visible rally.',
                           'voice':'Actual native Edge/Yunjian +6% cache; publication listening items remain in voice-review.md.'}
final = ROOT / 'specs/reels/shanghai-masters-history-2026.json'
final.parent.mkdir(parents=True,exist_ok=True)
final.write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
review={'schema':gate.SCHEMA,'plan_sha256':gate.plan_hash(spec),'segments':entries}
ledger = ROOT / 'data/audio_reviews/shanghai-masters-history-2026.json'
ledger.parent.mkdir(parents=True,exist_ok=True)
ledger.write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
print('Selected',len(spec['segments']),'native segments and',len(entries),'reviewed original audio windows')
print('Audio gate cues',len(gate.require(spec)))
