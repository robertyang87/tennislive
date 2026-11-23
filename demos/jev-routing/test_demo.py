import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('jev_demo',Path(__file__).with_name('demo.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class DemoTest(unittest.TestCase):
    def test_no_label_leakage_or_mutation(self):
        item={'title':'Tennis highlights','baseline':'interview','expected_column':'interview'}
        before=copy.deepcopy(item)
        self.assertEqual(m.build_request(item)['state'],{'title':'Tennis highlights'})
        self.assertEqual(item,before)

    def test_offline_and_missing_key_do_not_connect(self):
        with patch.object(m.urllib.request,'build_opener') as connect:
            self.assertEqual(m.run_one({'title':'tennis'},'',False)['status'],'prepared_not_called')
            self.assertEqual(m.run_one({'title':'tennis'},'',True)['status'],'missing_api_key')
            connect.assert_not_called()

    def test_response_validation(self):
        data={'model':'jev-test','usage':{'input_tokens':2,'output_tokens':1},'answers':{}}
        for name,criteria in [('column',m.COLUMNS),('evidence',{'explicit_text','insufficient'})]:
            labels=sorted(criteria)
            data['answers'][name]={'type':'choice','choice':labels[0],'confidence':1.,'probabilities':{v:float(v==labels[0]) for v in labels}}
        self.assertIs(m.validate(data),data)
        for invalid in (float('nan'),float('inf'),-1,True,'1'):
            bad=copy.deepcopy(data);bad['answers']['column']['confidence']=invalid
            with self.assertRaises(ValueError):m.validate(bad)

    def test_html_escapes_input(self):
        r=m.run_one({'id':'x','title':'<script>alert(1)</script>','sample_type':'synthetic'},'',False)
        text=m.report({'summary':m.summarize([r]),'records':[r],'created_at':'test','repository_commit':'test'})
        self.assertNotIn('<script>alert(1)</script>',text)
        self.assertIn('&lt;script&gt;',text)

if __name__=='__main__':unittest.main()
