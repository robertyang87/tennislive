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


def approved_omission(slug):
    approved = deepcopy(G.APPROVED_WUE_OMISSIONS[slug])
    identity = G._APPROVED_MATCH_IDENTITIES[slug]
    return {
        'slug': slug,
        'cover': {'eyebrow': '赛场之上', 'winner': identity['winner'],
                  'result': identity['result'], 'matchup': [
                      {'name': name, 'name_en': english}
                      for name, english in identity['matchup']]},
        '_match': {'status': 'result_verified', 'date': approved['match_date'],
                   'source': identity['source'], 'source_id': identity['source_id'],
                   'winner': identity['winner'], 'loser': identity['loser'],
                   'participants': deepcopy(identity['participants']),
                   'set_scores_home_away': deepcopy(identity['sets']),
                   'winner_result': identity['result']},
        'stats': {'a': {}, 'b': {}, '_winners_ue_omission': approved},
    }


def test_vacherot_owner_approved_omission_requires_exact_match():
    s = approved_omission('vacherot-urludpfjfq')
    assert G.problem(s) is None
    for section, field, value in [
        (None, 'slug', 'unapproved-vacherot'),
        ('_match', 'date', '2026-10-03'),
        ('_match', 'source', 'official_atp'),
        ('_match', 'source_id', 'other-match'),
        ('_match', 'winner_result', '6-4 6-4'),
        ('cover', 'result', '6-4 6-4'),
    ]:
        bad = deepcopy(s)
        (bad if section is None else bad[section])[field] = value
        assert G.problem(bad)
    bad = deepcopy(s)
    bad['cover']['matchup'].reverse()
    assert G.problem(bad)


@pytest.mark.parametrize('side', ['a', 'b'])
@pytest.mark.parametrize('field', ['winners', 'ue'])
def test_approved_omission_cannot_display_unknown_as_zero(side, field):
    s = approved_omission('vacherot-urludpfjfq')
    s['stats'][side][field] = 0
    assert G.problem(s)


def test_original_five_exact_omission_authorizations_remain_unchanged():
    originals = {
        'zheng-shi-beijing-2026-r1': ('1020_2026_LS070', '7-6(6) 4-6 6-2',
                                    'owner-approved-single-film-omission-2026-10-01'),
        'nishikori-tiafoe-tokyo-2026-r1': ('j3oaqNc6', '6-4 6-4',
                                         'owner-approved-remaining-four-film-omissions-2026-10-01'),
        'shang-baez-beijing-2026-r1': ('0bIo5sEk', '5-7 6-3 7-5',
                                      'owner-approved-remaining-four-film-omissions-2026-10-01'),
        'zverev-norrie-beijing-2026-r1': ('0I8uROz9', '7-6(1) 6-4',
                                        'owner-approved-remaining-four-film-omissions-2026-10-01'),
        'sun-lys-beijing-2026-r1': ('1020_2026_LS082', '6-1 3-0 Ret.',
                                   'owner-approved-remaining-four-film-omissions-2026-10-01'),
    }
    for slug, (source_id, result, authorization) in originals.items():
        entry = G.APPROVED_WUE_OMISSIONS[slug]
        assert entry == {'slug': slug, 'source_id': source_id, 'match_date': '2026-10-01',
                         'winner_result': result, 'fields': ['winners', 'ue'],
                         'decision': 'omit_both_rows_for_this_film_only',
                         'authorization': authorization}
        assert G.problem(approved_omission(slug)) is None
