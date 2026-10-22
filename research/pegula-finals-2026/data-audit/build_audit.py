"""Reproduce Pegula's source-bound 2026 season tables; never edit the old pack."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from collections import Counter, defaultdict
import csv, hashlib, html, json, re

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw'
OLD_PACK = Path('/workspace/output/WTA年终之路_2026_七人资料/05_佩古拉/05_佩古拉_事实包.json')
OLD_API = Path('/workspace/wta-finals-2026/source/pegula-api.json')
PID = 316956
TZ = {800: 'Australia/Brisbane', 901: 'Australia/Melbourne', 718: 'Asia/Dubai',
      609: 'America/Los_Angeles', 902: 'America/New_York', 804: 'America/New_York',
      1038: 'Europe/Madrid', 709: 'Europe/Rome', 903: 'Europe/Paris',
      2012: 'Europe/Berlin', 904: 'Europe/London', 1045: 'America/New_York',
      806: 'America/Toronto', 1017: 'America/New_York', 905: 'America/New_York',
      1075: 'Asia/Shanghai'}
BJT = ZoneInfo('Asia/Shanghai')
NOW = datetime.now(timezone.utc).isoformat()


def load(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open('rb') as fh:
        return hashlib.file_digest(fh, 'sha256').hexdigest()


def write(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def csv_write(name, rows, fields):
    with (ROOT / name).open('w', encoding='utf-8-sig', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                         for k, v in row.items()} for row in rows)


def ident(m):
    return int(m['tourn_nbr']), m['round_name'], str((m.get('opponent') or {}).get('id') or 'BYE')


def tokens(score):
    return [(int(a), int(b), int(tb) if tb else None)
            for a, b, tb in re.findall(r'(\d+)-(\d+)(?:\((\d+)\))?', score)]


def normalized_name(text):
    return ' '.join(text.split()).casefold()


old, history, old_history = load(OLD_PACK), load(RAW / 'player-matches.json'), load(OLD_API)
old_events = {e['event_id']: e for e in old['events']}
old_rows = {(m['event_id'], m['round'], normalized_name(m['opponent'])): m for m in old['matches']}
old_index, fresh_index = ({ident(m): m for m in doc['matches']} for doc in (old_history, history))
critical = ['scores', 'winner', 'reason_code', 'points_1', 'points_champ_1', 'points_bonus_1',
            'round_name', 'tourn_round', 's_d_flag', 'qpm_flag', 'rank_1', 'rank_2',
            'seed_1', 'Surface', 'TournamentName', 'StartDate', 'tourn_nbr', 'tourn_year']
raw_diffs, metadata_changes = [], []
for key in old_index.keys() | fresh_index.keys():
    a, b = old_index.get(key), fresh_index.get(key)
    if a is None or b is None:
        raw_diffs.append({'key': key, 'change': 'added' if a is None else 'removed'})
        continue
    for field in critical:
        if a.get(field) != b.get(field):
            raw_diffs.append({'key': key, 'field': field, 'old': a.get(field), 'fresh': b.get(field)})
    changed = [field for field in a.keys() | b.keys() if a.get(field) != b.get(field)]
    if changed:
        metadata_changes.append({'key': key, 'fields': changed})

rows, events, differences, tb_audit, aliases, issues = [], [], [], [], [], []
feeds = {int(eid): load(RAW / f'tournament-{eid}-matches.json')
         for eid in sorted({int(m['tourn_nbr']) for m in history['matches']})}
for raw in history['matches']:
    assert raw['s_d_flag'] == 'S' and raw['qpm_flag'] == 'M'
    assert int(raw['tourn_year']) == 2026
    eid, round_name, opponent_id = ident(raw)
    event = old_events[eid]
    opponent = (raw.get('opponent') or {}).get('fullName', '')
    code = raw['reason_code']
    played = code in ('W', 'R') and bool(opponent)
    result = 'BYE' if code == 'B' else ('W' if raw['winner'] == 1 else 'L')
    score_sets = tokens(raw['scores'])
    player_sets = [(a, b, tb) if raw['winner'] == 1 else (b, a, tb)
                   for a, b, tb in score_sets]
    score = ', '.join(f'{a}-{b}' + (f'({tb})' if tb is not None else '') for a, b, tb in player_sets)
    status = {'W': '正常完赛', 'R': '对手赛中退赛 RET' if result == 'W' else '本人赛中退赛 RET',
              'B': '轮空 BYE', 'D': '对手赛前退出 W/O' if result == 'W' else '本人赛前退出 W/O'}[code]
    if code in ('B', 'D'):
        score = 'BYE' if code == 'B' else 'W/O'
    prior = old_rows[(eid, round_name, normalized_name(opponent))]
    row = {'event_id': eid, 'event': event['event'], 'event_start': raw['tournament']['startDate'],
           'event_end': raw['tournament']['endDate'], 'level': raw['tournament']['level'],
           'surface': raw['tournament']['surface'], 'round': round_name,
           'tourn_round': raw['tourn_round'], 'result': result, 'status': status,
           'reason_code': code, 'count_wl': played, 'opponent_id': None if code == 'B' else int(opponent_id),
           'opponent': opponent, 'opponent_rank': raw['rank_2'] if opponent else None,
           'player_rank': raw['rank_1'], 'seed': raw['seed_1'], 'score_player': score,
           'score_winner': raw['scores'].strip(), 'event_final_points': raw['points_1'],
           'points_champ_1': raw['points_champ_1'], 'points_earned_in_this_match': None,
           'points_note': '本站最终积分；逐站表仅计一次，不能逐场相加。',
           'date': None, 'date_bjt': None, 'date_utc': None, 'start_utc': None,
           'date_start_local': None, 'date_start_bjt': None, 'date_start_utc': None,
           'date_completion_local': None, 'date_completion_bjt': None,
           'completion_bjt_possible_dates': None,
           'start_local': None, 'start_bjt': None, 'timezone': TZ[eid],
           'old_date': prior['date'] or None, 'date_source': None,
           'date_method': 'BYE没有真实比赛日期' if code == 'B' else None,
           'sets': [{'games_pegula': a, 'games_opponent': b, 'tiebreak_loser_points': tb,
                     'tiebreak_loser': ('pegula' if a < b else 'opponent') if tb is not None else None}
                    for a, b, tb in player_sets],
           'player_api_source': 'https://api.wtatennis.com/tennis/players/316956/matches?year=2026&type=S&page=0&pageSize=200&sort=desc',
           'player_api_snapshot': str(RAW / 'player-matches.json')}
    row.update(points=row['event_final_points'], points_rank=raw['points_1'],
               api_source=row['player_api_source'],
               source='https://www.wtatennis.com/players/316956/jessica-pegula/matches',
               score_winner_raw=raw['scores'],
               tournament_points_note=row['points_note'],
               quality='WTA官方逐场；日期由官方赛事MatchTimeStamp转换' if played else 'WTA轮空记录；无真实比赛日')
    row['score_winner'] = (', '.join(f'{a}-{b}' + (f'({tb})' if tb is not None else '')
                                   for a, b, tb in score_sets) if played else score)
    ordinal = {1: '第一轮', 2: '第二轮', 3: '第三轮', 4: '第四轮', 5: '第五轮', 6: '第六轮'}
    row['round_display'] = {'Q': '四分之一决赛', 'S': '半决赛', 'F': '决赛'}.get(
        round_name, ordinal.get(int(raw['tourn_round'] or 0), round_name))
    if played:
        candidates = [m for m in feeds[eid]['matches']
                      if m.get('DrawMatchType') == 'S' and m.get('DrawLevelType') == 'M'
                      and str(PID) in [str(m.get('PlayerIDA')), str(m.get('PlayerIDB'))]]
        matches = [m for m in candidates if opponent_id in [str(m.get('PlayerIDA')), str(m.get('PlayerIDB'))]]
        if not matches:
            matches = [m for m in candidates if normalized_name(opponent) in [
                normalized_name(m.get('PlayerNameFirstA', '') + ' ' + m.get('PlayerNameLastA', '')),
                normalized_name(m.get('PlayerNameFirstB', '') + ' ' + m.get('PlayerNameLastB', ''))]]
            if len(matches) == 1:
                aliases.append({'event_id': eid, 'opponent': opponent, 'history_opponent_id': opponent_id,
                                'tournament_player_ids': [matches[0]['PlayerIDA'], matches[0]['PlayerIDB']],
                                'resolution': 'exact normalized official full name; never fuzzy match'})
        assert len(matches) == 1, (eid, round_name, opponent, len(matches))
        m = matches[0]
        pegula_side = 'A' if str(m['PlayerIDA']) == str(PID) else 'B'
        other_side = 'B' if pegula_side == 'A' else 'A'
        # Code5 is observed only for Jones retiring against sideB Pegula; the
        # history reason R, complete identity and ResultString corroborate it.
        winner_side = {'2': 'A', '3': 'B', '5': 'B'}.get(str(m['Winner']))
        assert str(m['Winner']) != '5' or (code == 'R' and 'Ret' in m['ResultString'])
        official_result = 'W' if winner_side == pegula_side else 'L'
        games = [(int(m[f'ScoreSet{i}{pegula_side}']), int(m[f'ScoreSet{i}{other_side}']))
                 for i in range(1, 6) if str(m.get(f'ScoreSet{i}A') or '').isdigit()
                 and str(m.get(f'ScoreSet{i}B') or '').isdigit()]
        if (official_result != result or games != [(a, b) for a, b, _ in player_sets]
                or m['MatchState'] != 'F' or winner_side is None):
            issues.append({'event_id': eid, 'round': round_name, 'opponent': opponent,
                           'history_result': result, 'feed_result': official_result,
                           'history_sets': player_sets, 'feed_games': games, 'state': m['MatchState']})
        dt = datetime.fromisoformat(m['MatchTimeStamp'])
        local, bjt = dt.astimezone(ZoneInfo(TZ[eid])), dt.astimezone(BJT)
        row.update(date=local.date().isoformat(), date_bjt=bjt.date().isoformat(), date_utc=dt.date().isoformat(),
                   date_start_local=local.date().isoformat(), date_start_bjt=bjt.date().isoformat(),
                   date_start_utc=dt.date().isoformat(), date_basis='official_feed_local_start_calendar_day',
                   start_utc=dt.isoformat(), start_local=local.isoformat(), start_bjt=bjt.isoformat(),
                   date_source=f'https://api.wtatennis.com/tennis/tournaments/{eid}/2026/matches',
                   date_snapshot=str(RAW / f'tournament-{eid}-matches.json'),
                   date_method='Official MatchTimeStamp UTC converted to event local and Asia/Shanghai calendar day; not a European provider date.',
                   match_id=m['MatchID'], match_state=m['MatchState'], winner_code=m['Winner'],
                   start_date_source=f'https://api.wtatennis.com/tennis/tournaments/{eid}/2026/matches',
                   match_feed_source=f'https://api.wtatennis.com/tennis/tournaments/{eid}/2026/matches',
                   match_feed_snapshot=str(RAW / f'tournament-{eid}-matches.json'),
                   feed_round_id=m['RoundID'], feed_score_string=m['ScoreString'],
                   feed_result_string=m['ResultString'], estimated_start_time=m.get('estimatedStartTime'),
                   is_estimated_start_time=m.get('isEstimatedStartTime'),
                   match_time_total=m.get('MatchTimeTotal'), feed_last_updated=m.get('LastUpdated'),
                   calculated_end_utc=None, calculated_end_local=None, calculated_end_bjt=None)
        # LastUpdated can be the following day, or much later; never use it as
        # a match date or an observed final-point timestamp.
        if m.get('MatchTimeTotal') and re.fullmatch(r'\d+:\d+:\d+', m['MatchTimeTotal']):
            hh, mm, ss = map(int, m['MatchTimeTotal'].split(':'))
            end = dt + timedelta(hours=hh, minutes=mm, seconds=ss)
            row.update(calculated_end_utc=end.isoformat(),
                       calculated_end_local=end.astimezone(ZoneInfo(TZ[eid])).isoformat(),
                       calculated_end_bjt=end.astimezone(BJT).isoformat())
        if eid == 1045 and round_name == 'F':
            # The final continued on Monday. Adding net match time to Sunday's
            # feed timestamp would erase the overnight rain suspension.
            news = load(RAW / 'washington-final-news-4553195.json')
            assert 'Monday' in news['body'] and 'suspended on Sunday night' in news['body']
            row.update(date='2026-08-03', date_bjt=None, date_utc=None,
                       date_completion_local='2026-08-03', date_completion_bjt=None,
                       completion_bjt_possible_dates=['2026-08-03', '2026-08-04'],
                       date_basis='official_report_confirmed_completion_day_after_overnight_rain_suspension',
                       completion_source='https://www.wtatennis.com/news/4553195',
                       date_source='https://www.wtatennis.com/news/4553195',
                       date_snapshot=str(RAW / 'washington-final-news-4553195.json'),
                       completion_source_snapshot=str(RAW / 'washington-final-news-4553195.json'),
                       completion_source_quote="Monday ... finish a victory ... rain-delayed final; suspended on Sunday night ... Pegula leading 6-4, 1-2.",
                       date_method='赛报确认周一8/3完赛；官方feed起始/排期当地8/2另存date_start_local。未取得可靠末分或续赛时刻，北京完赛日期保留未知8/3–8/4，不能由发文或LastUpdated时间反推。',
                       calculated_end_utc=None, calculated_end_local=None, calculated_end_bjt=None)
        for i, (a, b, tb) in enumerate(player_sets, 1):
            if {a, b} == {6, 7}:
                official_tb = m.get(f'ScoreTbSet{i}')
                tb_audit.append({'event_id': eid, 'event': event['event'], 'round': round_name,
                                 'opponent': opponent, 'match_id': m['MatchID'], 'set': i,
                                 'games_pegula': a, 'games_opponent': b,
                                 'tiebreak_loser': 'pegula' if a < b else 'opponent',
                                 'history_loser_points': tb, 'feed_ScoreTbSet': official_tb,
                                 'ScoreTbSet_matches_history': str(official_tb) == str(tb),
                                 'feed_ScoreString': m['ScoreString'], 'feed_GrandSlam': m.get('GrandSlam', False),
                                 'source': row['date_source'], 'source_snapshot': row['date_snapshot'],
                                 'rule': '标准括号记抢七输家小分，翻转球员视角时小分值不变；不得直接取GrandSlam ScoreString括号作为输家小分。'})
        for field in ('result', 'score_player', 'opponent_rank', 'player_rank', 'seed'):
            left = prior[field]
            equal = tokens(left) == tokens(score) if field == 'score_player' else left == row[field]
            if not equal:
                differences.append({'kind': 'match_field', 'event_id': eid, 'event': event['event'],
                                    'round': round_name, 'opponent': opponent,
                                    'field': field, 'old': left, 'canonical': row[field]})
        if prior['date'] != row['date']:
            differences.append({'kind': 'match_local_date', 'event_id': eid, 'event': event['event'],
                                'round': round_name, 'opponent': opponent, 'field': 'date',
                                'old': prior['date'], 'canonical': row['date'], 'date_bjt': row['date_bjt'],
                                'source': row['date_source'], 'match_id': m['MatchID']})
    if prior['points'] != raw['points_1']:
        differences.append({'kind': 'event_points', 'event_id': eid, 'round': round_name,
                            'old': prior['points'], 'canonical': raw['points_1']})
    rows.append(row)

rows.sort(key=lambda r: (r['event_start'], int(r['tourn_round'] or 0)))
gross_points = 0
for eid in sorted(feeds, key=lambda i: next(r['event_start'] for r in rows if r['event_id'] == i)):
    erows = [r for r in rows if r['event_id'] == eid]
    played = [r for r in erows if r['count_wl']]
    last = max(played, key=lambda r: int(r['tourn_round']))
    point_values = {r['event_final_points'] for r in erows}
    assert len(point_values) == 1
    points = point_values.pop()
    gross_points += points
    finish = '冠军' if last['round'] == 'F' and last['result'] == 'W' else {
        'F': '亚军', 'S': '4强', 'Q': '8强'}.get(last['round'])
    if finish is None:
        finish = ordinal[int(last['tourn_round'])]
    e = {'event_id': eid, 'event': last['event'], 'start': last['event_start'], 'end': last['event_end'],
         'level': last['level'], 'surface': last['surface'], 'timezone': TZ[eid],
         'entries': len(erows), 'played': len(played), 'wins': sum(r['result'] == 'W' for r in played),
         'losses': sum(r['result'] == 'L' for r in played), 'bye': sum(r['reason_code'] == 'B' for r in erows),
         'ret': sum(r['reason_code'] == 'R' for r in erows), 'wo': sum(r['reason_code'] == 'D' for r in erows),
         'points': points, 'points_champ_1': erows[0]['points_champ_1'],
         'gross_points_cumulative_after_event': gross_points,
         'historic_official_race_rank_after_event': None,
         'points_note': '逐站只计一次；累计为本表已结束赛事总积分，不冒称当周官方Race榜积分/名次。',
         'finish': finish, 'last_round': last['round'], 'last_tourn_round': last['tourn_round'],
         'last_opponent': last['opponent'], 'last_result': last['result'], 'last_score_player': last['score_player'],
         'final_date': last['date'], 'final_date_bjt': last['date_bjt'], 'final_start_utc': last['start_utc'],
         'final_date_basis': last['date_basis'], 'final_date_start_local': last['date_start_local'],
         'final_date_start_bjt': last['date_start_bjt'],
         'final_completion_local': last['date_completion_local'],
         'final_completion_bjt': last['date_completion_bjt'],
         'final_completion_bjt_possible_dates': last['completion_bjt_possible_dates'],
         'final_completion_source': last.get('completion_source'),
         'final_start_local': last['start_local'], 'final_start_bjt': last['start_bjt'],
         'final_calculated_end_local': last['calculated_end_local'],
         'final_calculated_end_bjt': last['calculated_end_bjt'],
         'final_feed_last_updated': last['feed_last_updated'],
         'final_estimated_start_time': last['estimated_start_time'],
         'final_match_id': last['match_id'], 'date_source': last['date_source'],
         'date_snapshot': last['date_snapshot']}
    historical_event = next(m for m in history['matches'] if int(m['tourn_nbr']) == eid)
    e.update(city=historical_event['tournament']['city'], country=historical_event['tournament']['country'],
             prize=historical_event['PrizeWon'], matches=erows,
             last_score=e['last_score_player'], last_status=last['status'],
             source=f'https://www.wtatennis.com/tournaments/{eid}/-/2026',
             draw=old_events[eid].get('draw') or '',
             draw_verification='旧包官方签表链接保留；本次未以该PDF作逐场日期证据')
    for field in ['points', 'wins', 'losses', 'bye', 'wo', 'final_date', 'finish']:
        prior = old_events[eid][field]
        if prior != e[field]:
            differences.append({'kind': 'event_field', 'event_id': eid, 'event': e['event'],
                                'field': field, 'old': prior, 'canonical': e[field], 'source': e['date_source']})
    events.append(e)

played = [r for r in rows if r['count_wl']]
three = [r for r in played if len(r['sets']) == 3 and r['reason_code'] == 'W']
stats = {'entries': len(rows), 'played': len(played), 'wins': sum(r['result'] == 'W' for r in played),
         'losses': sum(r['result'] == 'L' for r in played), 'events': len(events),
         'byes': sum(r['reason_code'] == 'B' for r in rows),
         'retirements': sum(r['reason_code'] == 'R' for r in rows),
         'walkovers': sum(r['reason_code'] == 'D' for r in rows),
         'titles': sum(e['finish'] == '冠军' for e in events),
         'finals': sum(e['finish'] in ['冠军', '亚军'] for e in events),
         'top10_wins': sum(r['result'] == 'W' and r['opponent_rank'] is not None
                          and r['opponent_rank'] <= 10 for r in played),
         'three_set_completed_matches': len(three), 'three_set_wins': sum(r['result'] == 'W' for r in three),
         'three_set_losses': sum(r['result'] == 'L' for r in three),
         'three_set_scope': '仅reason_code=W且确有3盘比分的正常完赛单打，不含RET/BYE/W/O。',
         'three_set_by_event': {e['event']: {'played': sum(r['event_id'] == e['event_id'] for r in three),
                                            'wins': sum(r['event_id'] == e['event_id'] and r['result'] == 'W' for r in three),
                                            'losses': sum(r['event_id'] == e['event_id'] and r['result'] == 'L' for r in three)}
                               for e in events if any(r['event_id'] == e['event_id'] for r in three)},
         'gross_event_points': sum(e['points'] for e in events),
         'surfaces': {s: {'wins': sum(r['result'] == 'W' and r['surface'] == s for r in played),
                          'losses': sum(r['result'] == 'L' and r['surface'] == s for r in played)}
                      for s in sorted({r['surface'] for r in played})}}
race = next(r for r in load(RAW / 'race-2026-10-19-api.json') if r['player']['id'] == PID)
profile = json.loads(html.unescape(re.search(r'data-player-stats="([^"]+)"',
                                           (RAW / 'player-profile.html').read_text())[1]))
profile_summary = profile['ytd']['singles']['winLoss']
race_summary = {'ranking_date': race['rankedAt'], 'rank': race['ranking'], 'points': race['points'],
                'official_tournamentsPlayed_field': race['tournamentsPlayed'], 'actual_history_events': len(events),
                'event_points_sum': stats['gross_event_points'], 'sum_equals_official_race': stats['gross_event_points'] == race['points'],
                'source': 'https://api.wtatennis.com/tennis/players/ranked?page=0&pageSize=100&type=rankSingles&sort=asc&name=&metric=CHAMPSINGLES&at=2026-10-19',
                'source_snapshot': str(RAW / 'race-2026-10-19-api.json'),
                'independent_html_snapshot': str(RAW / 'race-singles.html'),
                'caveat': 'API榜单tournamentsPlayed=18与真实参赛16站是不同字段；现有证据不能确定另外2个计入项身份，不虚构2站或具体零分处罚。16站逐站积分之和5835与此期官方Race完全一致，不能将逐场重复携带的本站积分相加。'}
wuhan = next(r for r in played if r['event_id'] == 1075)
profile_conflict = {'profile_display': profile_summary, 'player_history': f"{stats['wins']} / {stats['losses']}",
                    'before_wuhan': f"{sum(r['result']=='W' for r in played if r['event_id']!=1075)} / {sum(r['result']=='L' for r in played if r['event_id']!=1075)}",
                    'wuhan': wuhan, 'source_snapshot': str(RAW / 'player-profile.html'),
                    'finding': 'profile汇总50/13恰少最后一场武汉正常完赛失利；不能删场或当W/O。具体后台缓存/更新原因未被证据证明。'}
manifest = load(ROOT / 'retrieval-manifest.json')
known = {m['file'] for m in manifest}
for role, path, url in [('old_fact_pack', OLD_PACK, None), ('old_player_api', OLD_API, None),
                        ('official_race_api', RAW / 'race-2026-10-19-api.json', race_summary['source'])]:
    if str(path) not in known:
        manifest.append({'role': role, 'file': str(path), 'url': url, 'sha256': sha(path),
                         'bytes': path.stat().st_size, 'retrieved_at': NOW if url else None})
write('retrieval-manifest.json', manifest)
limitations = [
    '截至本次2026-10-22抓取，最新正式单打记录为武汉10/14负奥斯塔彭科；不把2026赛季或Race视作已经结束，不预写后续赛事。',
    '所有64场实际比赛均有官方MatchState=F；12次BYE没有真实比赛日期，不补造日期。',
    '64场均保存官方MatchTimeStamp对应起始/排期的当地日、北京日及UTC日(date_start_*)；不是逐场独立观测的第一球时刻。date一般取官方开始当地日，华盛顿决赛例外取官方赛报确认的周一8/3完赛日，并显式标date_basis。',
    '华盛顿决赛周日起始、周一完赛；旧包当地8/3正确，不能列为日期错误。未可靠核到续赛/末分钟点，北京实际完赛日保留未知8/3–8/4；不从17:01UTC发文或16:58UTC更新时间推算末分。其他7场日期改动是统一到当地开始日，不保证它们全是实际终场日。',
    'LastUpdated是数据更新时间，不是比赛终场日期；有些记录晚一天更新。calculated_end仅开始时间加官方用时的计算值，不声称观察到末分时间，遇缺用时保留null。',
    '胜者视角history scores与明确A/B盘分逐场交叉验证；Grand Slam ScoreString有不同抢七括号口径，不能直接取其括号替代标准输家小分。',
    race_summary['caveat'], profile_conflict['finding'],
    '资格官宣和宁波/东京是否参赛由独立late-season-audit负责；没有把无比赛记录等同于已核实具体退赛原因。']
canonical = {'schema': 'pegula-season-canonical.v1', 'pid': PID, 'slug': 'pegula',
             'cn': '佩古拉', 'en': 'Jessica Pegula', 'season': 2026, 'generated_at': NOW,
             'scope': '2026年WTA/大满贯正赛单打，截至此次官方API可见最新完场；不含双打/混双/表演赛。',
             'stats': stats, 'race': race_summary, 'matches': rows, 'events': events,
             'profile_aggregate_conflict': profile_conflict, 'limitations': limitations,
             'provenance_manifest': str(ROOT / 'retrieval-manifest.json')}
canonical.update(wl=f"{stats['wins']}–{stats['losses']}", n_played=stats['played'],
                 n_entries=stats['entries'], n_events=stats['events'], race_points=race['points'],
                 top10_wins=stats['top10_wins'],
                 titles=[e['event'] for e in events if e['finish'] == '冠军'], finals=stats['finals'],
                 surfaces={s: f"{v['wins']}–{v['losses']}" for s, v in stats['surfaces'].items()},
                 bjk_matches=[], retrieved_date=NOW[:10],
                 qualification=None, qualification_note='见独立facts/late-season-audit.json，勿沿用未复核的旧官宣时间口径。')
write('canonical.json', canonical)
write('differences.json', {'schema': 'pegula-season-differences.v1', 'generated_at': NOW,
                         'old_fact_pack': str(OLD_PACK), 'old_fact_pack_sha256': sha(OLD_PACK),
                         'critical_old_vs_fresh_player_api': raw_diffs,
                         'noncritical_raw_record_changes': metadata_changes,
                         'normalized_differences': differences,
                         'profile_conflict': profile_conflict, 'race_count_caveat': race_summary,
                         'feed_result_games_state_issues': issues, 'official_id_aliases': aliases})
write('tie-break-audit.json', tb_audit)
write('date-corrections.json', {'date_basis': '官方当地起始/排期日；华盛顿决赛单列已确认实际完成日，保留跨日例外',
                              'all_played_matches': played,
                              'corrections': [d for d in differences if d['kind'] == 'match_local_date'],
                              'event_final_date_corrections': [d for d in differences
                                                               if d['kind'] == 'event_field' and d['field'] == 'final_date']})
match_fields = ['event_id', 'event', 'date', 'date_bjt', 'date_utc', 'date_basis',
                'date_start_local', 'date_start_bjt', 'date_start_utc',
                'date_completion_local', 'date_completion_bjt', 'completion_bjt_possible_dates',
                'round', 'round_display', 'tourn_round', 'result',
                'status', 'reason_code', 'count_wl', 'opponent', 'opponent_rank', 'player_rank', 'seed',
                'score_player', 'sets', 'event_final_points', 'points_earned_in_this_match', 'points_note',
                'start_utc', 'start_local', 'start_bjt', 'timezone', 'estimated_start_time',
                'match_id', 'match_state', 'winner_code', 'match_time_total', 'feed_last_updated',
                'calculated_end_local', 'calculated_end_bjt', 'old_date', 'date_source', 'date_snapshot']
csv_write('matches.csv', rows, match_fields)
csv_write('played-matches.csv', played, match_fields)
csv_write('events.csv', events, [key for key in events[0] if key != 'matches'])
csv_write('three-set-matches.csv', three, match_fields)
checks = {'entry_count_76': len(rows) == 76, 'played_count_64': len(played) == 64,
          'win_loss_50_14': (stats['wins'], stats['losses']) == (50, 14),
          'events_16': len(events) == 16, 'byes_12': stats['byes'] == 12,
          'one_ret_no_walkover': (stats['retirements'], stats['walkovers']) == (1, 0),
          'titles_2_finals_5': (stats['titles'], stats['finals']) == (2, 5),
          'all_64_official_dates': all(r['date'] and r['date_start_local'] and r['date_start_bjt'] for r in played),
          'no_invented_bye_dates': all(r['date'] is None for r in rows if r['reason_code'] == 'B'),
          'no_result_score_state_discrepancy': not issues,
          'old_raw_critical_fields_unchanged': not raw_diffs,
          'all_points_champ_equal_history_points': all(r['event_final_points'] == r['points_champ_1'] for r in rows),
          'gross_points_equal_5835_and_official_race': stats['gross_event_points'] == race['points'] == 5835,
          'all_observed_tiebreak_loser_points_confirmed': all(t['ScoreTbSet_matches_history'] for t in tb_audit),
          'three_set_19_6_25': (stats['three_set_wins'], stats['three_set_losses'], len(three)) == (19, 6, 25),
          'no_duplicate_player_records': len(fresh_index) == len(history['matches'])}
write('validation.json', {'generated_at': NOW, 'checks': checks, 'all_checks_pass': all(checks.values()),
                          'date_corrections': sum(d['kind'] == 'match_local_date' for d in differences),
                          'event_date_corrections': sum(d['kind'] == 'event_field' and d['field'] == 'final_date' for d in differences),
                          'tiebreak_sets_audited': len(tb_audit), 'tiebreak_issues': [t for t in tb_audit if not t['ScoreTbSet_matches_history']],
                          'counts': stats})
print(json.dumps({'stats': stats, 'checks': checks, 'date_changes': [d for d in differences if d['kind']=='match_local_date'],
                  'event_date_changes': [d for d in differences if d['kind']=='event_field' and d['field']=='final_date'],
                  'issues': issues}, ensure_ascii=False, indent=2))
