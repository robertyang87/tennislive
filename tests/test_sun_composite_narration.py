import hashlib
import json
import pytest
from tools.package_sun_xinran_story import validate_audio_segments

def test_composite_allows_distinct_runs_but_binds_every_text_and_audio(tmp_path):
 chapters=[{'id':f'S{i:02d}','narration':f'句子{i}'} for i in range(1,9)]
 rows=[]
 for c in chapters:
  p=tmp_path/(c['id']+'.mp3');p.write_bytes(c['id'].encode())
  digest=hashlib.sha256(p.read_bytes()).hexdigest()
  provenance=tmp_path/(c['id']+'.manifest.json')
  provenance.write_text(json.dumps({'chapters':[{'id':c['id'],'narration':c['narration'],'sha256':digest}]}))
  rows.append({'chapter_id':c['id'],'text':c['narration'],'file':p.name,'audio_sha256':digest,'source_manifest_file':provenance.name,'source_manifest_sha256':hashlib.sha256(provenance.read_bytes()).hexdigest()})
 assert len(validate_audio_segments({'audio_segments':rows},{'chapters':chapters},tmp_path))==8
 rows[2]['text']='旧句子'
 with pytest.raises(ValueError,match='text'):validate_audio_segments({'audio_segments':rows},{'chapters':chapters},tmp_path)


def test_component_provenance_must_be_actual_file(tmp_path):
 chapters=[{'id':f'S{i:02d}','narration':'句子'} for i in range(1,9)]
 rows=[]
 for c in chapters:
  p=tmp_path/(c['id']+'.mp3');p.write_bytes(b'audio')
  rows.append({'chapter_id':c['id'],'text':'句子','file':p.name,'audio_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source_manifest_file':'missing.json','source_manifest_sha256':'invented'})
 with pytest.raises(ValueError,match='manifest SHA'):validate_audio_segments({'audio_segments':rows},{'chapters':chapters},tmp_path)
