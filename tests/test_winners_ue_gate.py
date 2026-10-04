"""Production checks: actual values, evidence column mapping, and genuine absence."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path('tools').resolve()))
import winners_ue_gate as G
import tnns_stats as T


def spec():
    return {
        'cover': {'result': '6-3 7-6(2)', 'matchup': [
            {'name_en': 'Novak Djokovic'}, {'name_en': 'Nuno Borges'}]},
        '_match': {'date': '2026-09-30'},
        'stats': {'a': {'winners': 23, 'ue': 23}, 'b': {'winners': 24, 'ue': 26},
            '_winners_ue_evidence': {'period': 'Match', 'match_date': '2026-09-30',
                'provider': 'TNNS', 'method': 'api',
                'checked_at': '2026-09-30T17:40:34Z', 'source_url': 'https://example.org/match-proof',
                'winner_result': '6-3 7-6(2)', 'matchup': ['Borges', 'Djokovic'],
                'winners': [24, 23], 'ue': [26, 23]}}}


def test_reversed_source_columns_map_to_named_players():
    assert G.problem(spec()) is None
    wrong = spec(); wrong['stats']['a']['winners'] = 24; wrong['stats']['b']['winners'] = 23
    assert '列序填反' in G.problem(wrong)


@pytest.mark.parametrize('value', [None, -1, True, 1.2, '23'])
def test_missing_is_never_zero(value):
    s = spec(); s['stats']['a']['ue'] = value
    assert G.problem(s)


def test_real_zero_is_valid_when_source_verifies_it():
    s = spec(); s['stats']['a']['ue'] = 0; s['stats']['_winners_ue_evidence']['ue'][1] = 0
    assert G.problem(s) is None


@pytest.mark.parametrize('field,value', [
    ('period','Set 1'), ('checked_at','2026-09-30T17:00:00'), ('match_date','2025-09-30'),
    ('winner_result','6-4 7-6(1)'), ('matchup',['Borges','Norrie']), ('ue',[26]),
])
def test_wrong_match_and_partial_evidence_fail(field,value):
    s = spec(); s['stats']['_winners_ue_evidence'][field] = value
    assert G.problem(s)


def absent():
    s=spec(); s['stats']['a']={}; s['stats']['b']={}
    s['stats']['_winners_ue_why']='Five source classes checked; no full-match W/UE.'
    s['stats']['_winners_ue_check']={
        'status':'unavailable','period':'Match','checked_at':'2026-09-30T18:00:00Z',
        'match_date':'2026-09-30','source_url':'https://example.org/absence-proof',
        'matchup':['Borges','Djokovic'],'winner_result':'6-3 7-6(2)',
        'sources':{k:{'status':'unavailable','evidence':'saved response and identified match'}
                   for k in G.SOURCE_CLASSES}}
    s['stats']['_winners_ue_check']['sources']['tnns']['hasExtendedStats']=False
    return s


def test_prose_or_blocked_request_cannot_excuse_omission():
    s=spec(); s['stats']['a']={}; s['stats']['b']={}
    s['stats']['_winners_ue_why']='Flashscore has no fields; cloud browser blocked'
    assert G.problem(s)
    good=absent(); assert "waiting_stats" in G.problem(good)
    for key in G.SOURCE_CLASSES:
        bad=deepcopy(good);bad['stats']['_winners_ue_check']['sources'][key]['status']='blocked'
        assert G.problem(bad)
    for value in (None,True,'false'):
        bad=deepcopy(good);bad['stats']['_winners_ue_check']['sources']['tnns']['hasExtendedStats']=value
        assert G.problem(bad)


def test_partial_pair_rejected_even_with_excuse():
    s=spec();del s['stats']['b']['ue'];s['stats']['_winners_ue_why']='no data'
    assert G.problem(s)


def test_regression_flashscore_only_excuse_fails():
    s=spec()
    del s['stats']['a']['winners'],s['stats']['a']['ue']
    del s['stats']['b']['winners'],s['stats']['b']['ue']
    s['stats']['_winners_ue_why']='Flashscore全场feed没有Winners/UE项，未采用社媒统计'
    assert G.problem(s)
    assert G.problem(spec()) is None


def test_tnns_unknown_not_reported_as_absence(capsys):
    with pytest.raises(SystemExit,match='未明确返回 false'):
        T._report('sample',{'data':{'data':{'Match':[]}}})
    assert '"_winners_ue_why":' not in capsys.readouterr().out


def decoded():
    def block(w,ue):
        return [{'players':['Borges','Djokovic'],'data':[
            {'title':'Winners','values':w},{'title':'Unforced Errors','values':ue}]}]
    return {'data':{'hasExtendedStats':True,'data':{
        'Match':block([24,23],[26,23]),'Set 1':block([10,11],[12,10]),
        'Set 2':block([14,12],[14,13])}}}


def test_tnns_sum_failure_is_hard_before_printable_values(capsys):
    d=decoded();T.validate_totals(d)
    d['data']['data']['Set 2'][0]['data'][0]['values'][0]=13
    with pytest.raises(SystemExit,match='分盘合计'):
        T._report('sample',d)
    assert '粘进' not in capsys.readouterr().out


@pytest.mark.parametrize('kind',['unknown_players','set_missing','set_order','bad_int'])
def test_tnns_validation_rejects_bad_shape(kind):
    d=decoded()
    if kind=='unknown_players':d['data']['data']['Match'][0]['players']=None
    if kind=='set_missing':del d['data']['data']['Set 1']
    if kind=='set_order':d['data']['data']['Set 2'][0]['players'].reverse()
    if kind=='bad_int':d['data']['data']['Match'][0]['data'][1]['values'][0]=False
    with pytest.raises(ValueError):T.validate_totals(d)


def test_human_verification_stops_instead_of_navigation_fallback():
    for body in ('<title>Just a moment...</title>', '正在进行安全验证', 'Verify you are human'):
        with pytest.raises(SystemExit,match='停止此站访问'):T._reject_challenge(body)
    T._reject_challenge('{"all_matches": []}')


def test_gate_wired_to_production_and_qc_entrypoints():
    for file in ('production_preflight.py','taste_preflight.py','render_stat_card.py','check_reel_landed.py','build_match_reel.py'):
        assert 'from winners_ue_gate import' in Path('tools',file).read_text()


def test_prose_source_does_not_authorize_unverified_zero():
    s=spec();del s['stats']['_winners_ue_evidence'];s['stats']['_source']='Flashscore only; Winners/UE not supplied'
    for side in ('a','b'):
        s['stats'][side]={'winners':0,'ue':0}
    assert G.problem(s)
    assert G.problem(spec()) is None


def test_auto_generated_specs_cannot_soften_missing_stats_gate():
    s=absent();s['_production']={'status':'ready_for_render'}
    s['stats']['_winners_ue_check']['sources']['tnns']['status']='blocked'
    assert G.problem(s)


def test_absence_identity_cannot_be_for_a_different_match():
    s=absent();s['stats']['_winners_ue_check']['matchup']=['Zverev','Norrie']
    assert G.problem(s)


def test_production_preflight_stops_before_copy_or_media(tmp_path, monkeypatch):
    import production_preflight as P
    import json
    s=spec();s['stats']['a']={};s['stats']['b']={}
    f=tmp_path/'spec.json';f.write_text(json.dumps(s))
    monkeypatch.setattr(sys,'argv',['preflight','--spec',str(f),'--column','赛场之上'])
    monkeypatch.setattr(P,'check_copy',lambda *a,**k:pytest.fail('must stop before copy/media'))
    with pytest.raises(ValueError,match='缺 Winners/UE'):P.main()


def test_video_render_missing_stats_stops_before_any_output(tmp_path):
    import build_match_reel as R
    s=spec();s['stats']['a']={};s['stats']['b']={}
    out=tmp_path/'no-render'
    with pytest.raises(ValueError,match='缺 Winners/UE'):
        R.render(s,out,voice='test',rate='0%')
    assert not out.exists()


def test_detected_challenge_never_fetches_or_navigates_again(monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace
    calls=[]
    class Page:
        def goto(self,url,**kw):calls.append(('goto',url))
        def wait_for_timeout(self,*a):pass
        def content(self):return '<html>正在进行安全验证</html>'
        def evaluate(self,*a):pytest.fail('challenge must stop before fetch')
    page=Page()
    context=SimpleNamespace(on=lambda *a:None,new_page=lambda:page)
    browser=SimpleNamespace(new_context=lambda **k:context,close=lambda:None)
    pw=SimpleNamespace(chromium=SimpleNamespace(launch=lambda **k:browser))
    fake=SimpleNamespace(sync_playwright=lambda:nullcontext(pw))
    monkeypatch.setitem(sys.modules,'playwright.sync_api',fake)
    with pytest.raises(SystemExit,match='停止此站访问'):
        T._browser_capture(['https://tnnslive.com/','https://tnnslive.com/match/1'],[],
                           in_page={'day':'https://api.tnnslive.com/v1/matches'})
    assert calls==[('goto','https://tnnslive.com/')]


def test_passive_api_challenge_stops_even_with_normal_app_shell(monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace
    calls=[]; handlers={}
    class Page:
        def goto(self,url,**kw):
            calls.append(('goto',url))
            handlers['response'](SimpleNamespace(
                url='https://api.tnnslive.com/v1/matches?web=true',
                text=lambda:'<title>Just a moment...</title>'))
        def wait_for_timeout(self,*a):pass
        def content(self):return '<html>Normal TNNS app shell</html>'
        def evaluate(self,*a):pytest.fail('passive API challenge must stop before fetch')
    page=Page()
    context=SimpleNamespace(on=lambda event,fn:handlers.update({event:fn}),new_page=lambda:page)
    browser=SimpleNamespace(new_context=lambda **k:context,close=lambda:None)
    pw=SimpleNamespace(chromium=SimpleNamespace(launch=lambda **k:browser))
    monkeypatch.setitem(sys.modules,'playwright.sync_api',SimpleNamespace(sync_playwright=lambda:nullcontext(pw)))
    with pytest.raises(SystemExit,match='停止此站访问'):
        T._browser_capture(['https://tnnslive.com/'],[T._DAY_MARK],
                           in_page={'day':'https://api.tnnslive.com/v1/matches?date=2026-09-30'})
    assert calls==[('goto','https://tnnslive.com/')]


@pytest.mark.parametrize('unavailable',[False,True])
def test_canonical_match_date_cannot_be_silently_skipped(unavailable):
    s=absent() if unavailable else spec()
    del s['_match']['date']
    assert G.problem(s)
    s['_match']['start_utc']='2026-09-30T10:00:00Z'
    assert ("waiting_stats" in G.problem(s)) if unavailable else G.problem(s) is None
    field='_winners_ue_check' if unavailable else '_winners_ue_evidence'
    s['stats'][field]['match_date']='2025-09-30'
    assert G.problem(s)


def test_start_timestamp_is_normalized_with_its_declared_timezone():
    s=spec();del s['_match']['date'];s['_match']['start_utc']='2026-10-01T01:00:00+08:00'
    assert G.problem(s) is None
    s['_match']['start_utc']='2026-09-30T10:00:00'
    assert G.problem(s)


@pytest.mark.parametrize('key,value', [
    ('provider', ''), ('provider', True), ('method', 'api_success'),
    ('method', []), ('method', {}),
    ('source_url', 'not-a-source'), ('source_url', 'file:///tmp/foo'),
    ('source_sha256', 'abc'),
])
def test_provenance_requires_real_provider_method_and_locator(key, value):
    s = spec()
    s['stats']['_winners_ue_evidence'][key] = value
    assert G.problem(s)


def test_hash_alone_cannot_locate_a_source():
    s = spec(); evidence = s['stats']['_winners_ue_evidence']
    evidence.pop('source_url'); evidence['source_sha256'] = 'f' * 64
    assert G.problem(s)
    evidence['source_path'] = 'evidence/match-stats.json'
    assert G.problem(s) is None


def test_no_score_or_ambiguous_surnames_cannot_verify_match():
    s = spec(); s['cover'].pop('result'); s['stats']['_winners_ue_evidence'].pop('winner_result')
    assert G.problem(s)
    s = spec(); s['cover']['matchup'] = [{'name_en':'Shuai Zhang'}, {'name_en':'Zhizhen Zhang'}]
    s['stats']['_winners_ue_evidence']['matchup'] = ['Zhang', 'Zhang']
    assert G.problem(s)


def test_stats_card_gate_runs_before_html_browser_or_output(tmp_path, monkeypatch):
    import render_stat_card as R
    s = spec(); s['stats'].pop('_winners_ue_evidence')
    out = tmp_path/'stats.jpg'
    monkeypatch.setattr(R, 'build', lambda *a, **k: pytest.fail('must gate before HTML/media'))
    with pytest.raises(ValueError, match='结构化证据'):
        R.render(s, out)
    assert not out.exists() and not out.with_suffix('.html').exists()


def test_landed_qc_rejects_unverified_statistics_before_media(tmp_path, monkeypatch):
    import check_reel_landed as L
    import json
    film = tmp_path/'sample.mp4'; film.write_bytes(b'synthetic sentinel')
    path = tmp_path/'sample.json'
    s = spec(); s['stats'].pop('_winners_ue_evidence'); path.write_text(json.dumps(s))
    monkeypatch.setattr(sys, 'argv', ['check', '--film', str(film), '--spec', str(path)])
    monkeypatch.setattr(L, 'cover_seconds', lambda *a: pytest.fail('must gate before media'))
    assert L.main() == 1


def test_taste_preflight_cannot_soften_stats_with_auto_flag(tmp_path, monkeypatch):
    import taste_preflight as P
    import json
    path = tmp_path/'sample.json'; s = spec()
    s['stats'].pop('_winners_ue_evidence'); s['_production'] = {'status':'ready_for_render'}
    path.write_text(json.dumps(s))
    monkeypatch.setattr(P, 'find_spec', lambda slug: ('reel', path))
    monkeypatch.setattr(P, 'run_reel_dry_run', lambda p: P.GateResult('dry', 'pass'))
    assert P.main(['--slug', 'sample', '--no-ci-tests']) == 1


@pytest.mark.parametrize('change', ['duplicate', 'reordered_group', 'false_flag'])
def test_tnns_rejects_ambiguous_or_contradictory_row_provenance(change):
    d = decoded()
    if change == 'duplicate':
        d['data']['data']['Match'][0]['data'].append({'title':'Winners','values':[24,23]})
    elif change == 'reordered_group':
        d['data']['data']['Match'].insert(0, {'players':['Djokovic','Borges'],'data':[]})
    else:
        d['data']['hasExtendedStats'] = False
    with pytest.raises(ValueError):
        T.validate_totals(d)


@pytest.mark.parametrize('status', ['unavailable', 'blocked', 'not_connected', 'not_applicable', 'not_checked'])
def test_exhausted_sources_never_waive_required_future_statistics(status):
    s = absent()
    for entry in s['stats']['_winners_ue_check']['sources'].values():
        entry['status'] = status
    assert 'waiting_stats' in G.problem(s)
    # Complete verified numbers do not have to wait for other providers.
    verified = spec()
    verified['stats']['_winners_ue_check'] = s['stats']['_winners_ue_check']
    assert G.problem(verified) is None


def test_match_reel_cannot_evade_required_stats_by_omitting_entire_card():
    s = spec(); s['cover']['eyebrow'] = '赛场之上'; s.pop('stats')
    assert 'waiting_stats' in G.problem(s)


@pytest.mark.parametrize('value', [[], {'cover': []}, {'cover': None}])
def test_malformed_spec_fails_with_a_useful_gate_message(value):
    assert '必须是对象' in G.problem(value)


def yuan_approved():
    return {
        'slug': 'yuan-andreeva-beijing-2026-r2',
        '_match': {
            'status': 'result_verified', 'source': 'flashscore_points',
            'source_id': 't0OdtxKa', 'date': '2026-10-02',
            'winner_result': '3-6 6-0 6-0', 'winner': '米拉·安德烈耶娃',
            'loser': '袁悦', 'participants': ['袁悦', '米拉·安德烈耶娃'],
            'set_scores_home_away': [[6, 3], [0, 6], [0, 6]],
        },
        'cover': {
            'eyebrow': '赛场之上', 'winner': '米拉·安德烈耶娃',
            'result': '3-6 6-0 6-0', 'matchup': [
                {'name': '袁悦', 'name_en': 'Yue Yuan'},
                {'name': '米拉·安德烈耶娃', 'name_en': 'Mirra Andreeva'},
            ],
        },
        'stats': {'a': {}, 'b': {}, '_winners_ue_omission': {
            'slug': 'yuan-andreeva-beijing-2026-r2', 'source_id': 't0OdtxKa',
            'match_date': '2026-10-02', 'winner_result': '3-6 6-0 6-0',
            'fields': ['winners', 'ue'], 'decision': 'omit_both_rows_for_this_film_only',
            'authorization': 'owner-requested-complete-video-after-missing-wue-disclosure-2026-10-02',
        }},
    }


def test_yuan_complete_video_request_allows_only_exact_two_row_omission():
    assert G.problem(yuan_approved()) is None
    s = yuan_approved(); del s['stats']['_winners_ue_omission']
    assert 'waiting_stats' in G.problem(s)
    s = yuan_approved(); s['slug'] = 'yuan-another-match'
    assert G.problem(s)


@pytest.mark.parametrize('key,value', [
    ('status', 'scheduled'), ('source', 'official_wta'), ('source_id', 'other'),
    ('date', '2026-10-01'), ('winner', '袁悦'), ('loser', '米拉·安德烈耶娃'),
    ('winner_result', '6-3 0-6 0-6'),
    ('participants', ['米拉·安德烈耶娃', '袁悦']),
    ('set_scores_home_away', [[3, 6], [6, 0], [6, 0]]),
])
def test_yuan_omission_rejects_changed_match_identity(key, value):
    s = yuan_approved(); s['_match'][key] = value
    assert G.problem(s)


@pytest.mark.parametrize('key', list(G.YUAN_ANDREEVA_OMISSION))
def test_yuan_omission_requires_exact_authorization_record(key):
    s = yuan_approved(); del s['stats']['_winners_ue_omission'][key]
    assert G.problem(s)


@pytest.mark.parametrize('key,value', [
    ('winner', '袁悦'), ('result', '6-3 0-6 0-6'), ('eyebrow', '赛后开麦'),
    ('matchup', [{'name': '米拉·安德烈耶娃', 'name_en': 'Mirra Andreeva'},
                 {'name': '袁悦', 'name_en': 'Yue Yuan'}]),
])
def test_yuan_omission_rejects_changed_cover_or_player_columns(key, value):
    s = yuan_approved(); s['cover'][key] = value
    assert G.problem(s)


@pytest.mark.parametrize('side', ['a', 'b'])
@pytest.mark.parametrize('field', ['winners', 'ue'])
@pytest.mark.parametrize('value', [None, 0, 99])
def test_yuan_omission_never_authorizes_unknown_zero_or_guessed_values(side, field, value):
    s = yuan_approved(); s['stats'][side][field] = value
    assert G.problem(s)


def test_yuan_omission_does_not_claim_complete_statistics_evidence():
    s = yuan_approved(); s['stats']['_winners_ue_evidence'] = {}
    assert G.problem(s)


def test_djokovic_continuation_omission_is_bound_to_exact_match():
    import json
    s=json.loads(Path('specs/reels/zverev-djokovic.json').read_text())
    assert G.problem(s) is None
    for key,value in [('date','2026-10-05'), ('source_id','different-match'), ('winner','兹维列夫')]:
        changed=deepcopy(s);changed['_match'][key]=value
        assert G.problem(changed)
    changed=deepcopy(s);changed['slug']='some-other-film'
    assert G.problem(changed)
    for field in G.FIELDS:
        changed=deepcopy(s);changed['stats']['a'][field]=0
        assert G.problem(changed)
    changed=deepcopy(s);changed['cover']['matchup'].reverse()
    assert G.problem(changed)
