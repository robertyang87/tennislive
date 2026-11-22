from copy import deepcopy
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import interview_source_gate as gate

def spec():
    s={'requested_content_type':'trophy_moment','interview_kind':'赛后捧杯时刻','url':'https://www.youtube.com/watch?v=abc','match':{'id':'m1','event':'成都公开赛','round':'决赛','winner':'A','loser':'B','participants':['A','B']},'source_verification':{'status':'verified','detected_type':'trophy_moment','method':'reviewed_trophy_frames','source_url':'https://www.youtube.com/watch?v=abc','evidence':[{'kind':'viewed_source_frame'}]},'trophy_moment':{'audio_speaker':'broadcast_commentator','player_speech':False,'source_sha256':'a'*64,'match_id':'m1','reviewed_frames':[{'source_second':463,'sha256':'b'*64,'trophy_visible':True,'winner_visible':True}]}}
    return gate.finalize_source_contract(s)

def test_reviewed_trophy_retains_signed_identity():
    s=spec();assert gate.validate_source_contract(s)
    s['trophy_moment']['reviewed_frames'][0]['source_second']=470
    with pytest.raises(gate.SourceContractError,match='SHA|sha|匹配'):gate.validate_source_contract(s)

@pytest.mark.parametrize('field,value',[('player_speech',True),('audio_speaker','player'),('source_sha256',''),('match_id','other'),('reviewed_frames',[])])
def test_incomplete_or_mislabelled_trophy_rejected(field,value):
    s=spec();s['trophy_moment'][field]=value;gate.finalize_source_contract(s)
    with pytest.raises(gate.SourceContractError):gate.validate_source_contract(s)

def test_trophy_does_not_bypass_lead_or_enable_title_discovery():
    s=spec();s['opening']={'kind':'none'}
    assert not gate.verified_no_lead_exception(s)
    assert gate.explicit_title_type('Chengdu Highlights trophy moment')==''
