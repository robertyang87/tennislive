"""User-requested replacements are explicit; unrequested duplicate films stay blocked."""
import importlib.util
import json
import sys
from pathlib import Path


def test_revision_pair_requires_request_and_matching_match(tmp_path):
    sys.path.insert(0, str(Path('tools').resolve()))
    import build_match_reel as reel
    base = {'slug': 'base', 'source_url': 'https://youtu.be/ChIOgR3JpVQ',
            'cover': {'eyebrow': '赛场之上'}}
    revised = {**base, 'slug': 'detail', 'revision_of': 'base',
               '_revision_request': 'User requested a finer replacement.'}
    (tmp_path / 'base.json').write_text(json.dumps(base))
    (tmp_path / 'detail.json').write_text(json.dumps(revised))
    assert reel.duplicate_match_problem(base, tmp_path) is None
    assert reel.duplicate_match_problem(revised, tmp_path) is None
    unrequested = {**revised}
    del unrequested['_revision_request']
    assert reel.duplicate_match_problem(unrequested, tmp_path)
    assert reel.duplicate_match_problem({**base, 'slug': 'third'}, tmp_path)
    assert reel.duplicate_match_problem({**revised, 'revision_of': 'missing'}, tmp_path)
