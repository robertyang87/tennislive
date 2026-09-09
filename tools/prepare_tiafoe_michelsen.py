"""One-pass reviewed production: new evidence audit, promote, then normal gates."""
import json
import subprocess
import sys
from pathlib import Path

from build_match_reel import load_spec, validate_spec
from promote_reel_draft import insert_chapter_cards, promote

slug = 'tiafoe-michelsen'
path = Path(f'specs/reels/pending/{slug}.draft.json')
out = Path(f'output/2026-09-09/reel/{slug}')
subprocess.run([sys.executable, 'tools/analyze_reel_visuals.py', '--draft', str(path),
                '--outdir', str(out), '--write'], check=True)
d = json.loads(path.read_text())
assert d['_visual_evidence']['status'] == 'pass', d['_visual_evidence']
# The source has no scoreboard during the chosen winner celebration / embrace.
for seg in [d['segments'][0],d['segments'][-1]]:
    if seg['start'] >= 122:
        seg['score_inset'] = False
        seg['_score_inset_why'] = 'Full-source sheets and score_03 show board disappears after match point, before this window.'
d['segments'][0]['crosses_cut']='完整赛点从发球准备到回合结束及赢家庆祝；源片114.86和121.96切点均属于同一赛点。'
d['segments'][0]['score_inset']=True
d['segments'][0]['score_inset_windows']=[[112.5,121.9]]
d['segments'][0]['_score_inset_why']='score03 confirms board disappears after matchpoint before winner celebration.'
last=d['segments'][-1]
# Preserve the audited payoff and include the complete observed embrace, ending
# at the first source contact frame after the players separate.
assert last['start'] == 112.5 and last['end'] == 127.53, 'Review model boundaries before rendering'
last['end']=154.5
last['score_inset']=True
last['score_inset_windows']=[[112.5,121.9]]
last['_score_inset_why']='score_03: board present120.5s, absent122.5s onward; do not paste shirts or crowd during embrace.'
last['narration']='抢十来到九比六，赛点就在眼前。两个人都已经拼了四个多小时。米切尔森发球，蒂亚福接发，胜负悬在这一分。拿下了！十比六，两盘落后的人，笑到了最后。第三次美网半决赛，蒂亚福是这样一点点挣回来的。再看网前，米切尔森哭了。蒂亚福没有急着走开，把年轻的同胞抱在怀里。第一次大满贯八强，离半决赛只差那么一点。你觉得最大的转折，是第三盘发球胜赛局，还是决胜盘零比三后的追赶？'
last['_reviewed_ending_boundary']='Full source contact_02: embrace continues through152.5s; separated154.5s. Keep complete handshake then stop, no later crowd/career segment. Raw model report retained.'
last['crosses_cut']='Same-match winner reaction into net embrace, ending after separation at154.5s.'
insert_chapter_cards(d)
# Normalize title/stat placeholders before promote's shape/length validation.
path.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
d=load_spec(path)
spec=promote(d)
spec['cover']['topic']='2026 美网 1/4决赛'
spec['topbar']['line1']='2026 美网 1/4决赛'
validate_spec(spec)
formal=Path(f'specs/reels/{slug}.json')
formal.write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
copy='''两盘落后，又两次被逼到悬崖边，蒂亚福是怎么翻回来的？

北京时间9月9日凌晨，美网男单1/4决赛，蒂亚福以5-7、3-6、7-5、6-3、7-6(6)逆转米切尔森，决胜盘抢十10-6。

第三盘，米切尔森5-4发球胜赛没能关门；蒂亚福连拿三局续命。第四盘扳平后，他在决胜盘又从0-3追了回来。

全场总分170-173、制胜分50-55，蒂亚福都落后；但非受迫失误43-61，两人同样破发8次，他用了17个机会，对手用了23个。总分更多，不等于关键机会兑现得更好。

网前漫长的拥抱，是这场美国德比的另一面。一位第三次进入美网半决赛，一位第一次来到大满贯八强。

你觉得，最大的转折是第三盘发球胜赛局，还是决胜盘0-3之后的追赶？

#美网 #蒂亚福 #网球 #赛场之上 #网球时差
'''
Path(f'specs/reels/{slug}.xhs.txt').write_text(copy)
path.unlink()
print('Reviewed formal spec ready; continue standard narration, render and QC gates.')
