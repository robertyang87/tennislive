import json
from pathlib import Path
from tools import taste_preflight as T, explainer_preflight as P
from tennislive.video import explainer as E

def test_production_explainer_is_discovered_without_fake_reel():
    kind,path=T.find_spec('sun-xinran-coming-of-age-2026')
    assert kind=='explainer' and path.name.endswith('.production.json')
    assert T.line_of(kind,json.loads(path.read_text()))=='网球有故事'

def test_video_only_exemption_does_not_skip_fact_or_copy_checks():
    rows=dict(P.preflight('sun-xinran-coming-of-age-2026'))
    assert '全称断言' in rows and '假词' in rows and '小红书正文 1000 字' in rows
    assert '每屏要点（无正文字卡，不适用）' in rows
    assert sum(len(b[3]) for b in E._SCRIPTS['sun-xinran-coming-of-age-2026'])==1156
