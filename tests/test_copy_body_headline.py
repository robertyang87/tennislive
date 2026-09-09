import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from push_reel import copy_body_only, split_copy

def test_dated_column_title_is_not_in_copy_body():
    title="9.9 赛场之上 | 卫冕冠军阿卡出局"
    body="四小时的较量。\n\n#网球时差"
    source="🎾9.9 赛场之上｜阿尔卡拉斯出局\n\n"+body
    result=copy_body_only(source,title)
    assert split_copy(title+"\n\n"+result)==(title,body)

def test_opening_paragraph_is_preserved():
    assert copy_body_only("9.9 的比赛打到深夜。", "标题")=="9.9 的比赛打到深夜。"
    assert copy_body_only("阿卡没有退。\n\n精彩击球。", "标题")=="阿卡没有退。\n\n精彩击球。"
