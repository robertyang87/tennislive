from pathlib import Path
from bs4 import BeautifulSoup
import json,hashlib,datetime,re,unicodedata,sys
r=Path('/dev/shm/alcaraz-finals-production/research/audio-race-qc/race-chart-0728');facts_path=Path('/workspace/finals-update-research/facts/race-top15-2026-11-09T0728.json');f=json.loads(facts_path.read_text());src=Path(f['source_race_html']);official=src.parent/'singles.html';n=Path('/dev/shm/shelton-paris-production/native');sys.path.insert(0,str(n/'src'))
from tennislive.zh import player_zh

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(s):return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',s) if not unicodedata.combining(c)).lower().split())
assert sha(src)==f['source_race_sha256']
facts_by_name={norm(row['name']):row for row in f['top15']};assert len(facts_by_name)==15
# Deliberately map Chinese names by normalized EN identity, never by rank/index.
name_to_display={norm(row['name']):row['display_name'] for row in f['top15']}
actual=[];raw_soup=BeautifulSoup(src.read_text(),'html.parser');rank16=None
for tr in raw_soup.select('tr'):
 rk=tr.find('td',class_='rk',recursive=False);pn=tr.find('td',class_='pn',recursive=False)
 if not rk or not pn or not rk.get_text(strip=True).isdigit():continue
 rank=int(rk.get_text(strip=True));raw_name=pn.get_text(' ',strip=True);name=re.sub(r'^[✓✗]\s*','',raw_name);tds=tr.find_all('td',recursive=False)
 if rank==16:rank16={'rank':rank,'name':name,'points':int(tds[5].get_text(strip=True))}
 if rank>15:continue
 key=norm(name);fr=facts_by_name[key];points=int(tds[5].get_text(strip=True));qualified=raw_name.startswith('✓');assert (rank,points,qualified)==(fr['rank'],fr['points'],fr['qualified'])
 status='qualified' if qualified else 'withdrawn' if key==norm('Jannik Sinner') else 'not_qualified'
 actual.append({'rank':rank,'player':name,'normalized_identity':key,'player_zh':name_to_display[key],'native_library_name_zh':player_zh(fr['name']),'points':points,'points_type':'season Race, not rolling52week ranking','status':status,'status_zh':'已晋级' if qualified else '已退赛' if status=='withdrawn' else '未入围','highlight':qualified,'focus':key==norm('Carlos Alcaraz'),'points_evidence':[f['points_source']],'qualification_evidence':[f['official_qualification_source']] if qualified else [],'source_row':tr.get_text(' ',strip=True)})
actual.sort(key=lambda x:x['rank']);assert len(actual)==15 and [x['rank'] for x in actual]==list(range(1,16));assert actual[10]['player']=='Taylor Fritz' and actual[10]['points']==3085;assert actual[14]['player']=='Alejandro Davidovich Fokina' and actual[14]['player_zh']=='福基纳' and actual[14]['points']==2510
assert rank16['name']=='Jakub Menšík' and rank16['points']==2500 and all(norm(x['player'])!=norm('Jakub Menšík') for x in actual)
# Independently inspect the actual eight official profile cards, accent-normalizing Rafael Jodar.
os=BeautifulSoup(official.read_text(),'html.parser');cards=[{'name':a.get_text(' ',strip=True),'profile_url':'https://www.nittoatpfinals.com'+a['href']} for a in os.select('a.player-card[href*="/en/players/singles/"]')];assert len(cards)==8
assert {norm(x['name']) for x in cards}=={norm(x['player']) for x in actual if x['highlight']}
assert sum(x['highlight'] for x in actual)==8 and sum(x['focus'] for x in actual)==1 and actual[1]['status']=='withdrawn' and not actual[1]['highlight']
d={'schema':'tennislive.race-snapshot.v1','as_of':f['as_of_utc'],'as_of_basis':'NormalGET exact2026-11-09T07:28:02.497439Z live-seasonRace checkpoint; afterParis and includescurrent lower-ranked updates. Not labelledParis-onlyfreeze.','capture_time':f['as_of_utc'],'table_title_zh':'2026 ATP年终资格积分榜','date_label_zh':'11月9日赛季积分截点','ranking_is_official_current_page':False,'points_provider':'Live-Tennis independent current liveRace exact07:28UTC snapshot, notofficialrollingranking.','qualification_provider':'OfficialNittoATPFinals actualeightcurrent singlesprofilecards','qualified_active_count':8,'remaining_active_places':0,'focus_player':'Carlos Alcaraz','focus_name_zh':'阿尔卡拉斯','focus_qualification_label_zh':'已晋级','withdrawal_note_zh':'辛纳位列第2，但已退赛，不参加本届年终。','sources':{'live_race':f['points_source'],'official_qualification':f['official_qualification_source']},'rows':actual,'source_binding':{'canonical_fact_path':str(facts_path),'canonical_fact_sha256':sha(facts_path),'source_html_path':str(src),'source_html_sha256':sha(src),'official_roster_html_path':str(official),'official_roster_html_sha256':sha(official),'actual_official_eight_profile_cards':cards,'name_mapping':'ENidentity→Chinese display via currentfacts_by_name; native name record also retained. Never index/rank-based lookup.','excluded_rank16':rank16,'independent_html_15row_comparison':True,'compared_at':datetime.datetime.now(datetime.timezone.utc).isoformat()},'notes':['Top9/Alcaraz6100#3/Shelton5170#4/eightactivequalifiers unchanged since06:04.','TaylorFritz now3085; rank15DavidovichFokina2510 replacesMensik2500 nowrank16.','福基纳 row uses root-authorized shortdisplay alias of native达维多维奇·福基纳.','ThisisAlcarazunrenderedinput update only; frozen13body/cover/outro texts and anyactualpublishedSheltonfilm unchanged.','Race rank is not a tournament seed; snapshot is date-limited, lowerpoints may laterchange.']}
p=r/'data-canonical.json';p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'path':str(p),'sha256':sha(p),'as_of':d['as_of'],'lastrow':actual[-1]},ensure_ascii=False))
