"""Photographic covers keep native pixel gates and bind the actual source bytes."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE=Path(__file__).resolve().parents[1]/'tools/audit_interview_cover.py'
spec=importlib.util.spec_from_file_location('photo_audit',MODULE)
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

class PhotoContract(unittest.TestCase):
    def photo(self):
        return {'cover':{'photo_path':'assets/cover.jpg','photo_source':'https://example.org/event/photo','photo_sha256':'a'*64}}
    def test_offline_contract_needs_no_local_source(self):
        contract,issues=audit.framing_contract(self.photo())
        self.assertFalse(issues);self.assertNotIn('frame_at',contract)
        self.assertEqual(contract['photo_sha256'],'a'*64)
    def test_fake_frame_and_missing_source_hash_rejected(self):
        s=self.photo();s['cover']['frame_at']=0;s['cover'].pop('photo_sha256')
        _,issues=audit.framing_contract(s)
        self.assertTrue(any('frame_at' in i for i in issues))
        self.assertTrue(any('SHA-256' in i for i in issues))
    def test_independent_video_frame_requires_real_provenance(self):
        s=self.photo();s['cover']['generation']='video_frame'
        self.assertTrue(audit.framing_contract(s)[1])
        s['cover']['source_frame']={'url':'https://example.org/video','seconds':468.1,'source_sha256':'b'*64}
        self.assertFalse(audit.framing_contract(s)[1])

    def test_video_contract_unchanged(self):
        self.assertFalse(audit.framing_contract({'cover':{'frame_at':2}})[1])
        self.assertTrue(audit.framing_contract({'cover':{}})[1])
    def test_real_file_mutation_fails(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p=root/'assets/cover.jpg';p.parent.mkdir();Image.new('RGB',(80,80),'blue').save(p)
            s=self.photo();s['cover']['photo_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
            audit.validate_photo_file(s,root)
            p.write_bytes(p.read_bytes()+b'changed')
            with self.assertRaises(ValueError):audit.validate_photo_file(s,root)
    def test_photo_cannot_bypass_pixel_checks(self):
        s=self.photo();contract,_=audit.framing_contract(s)
        issues=audit.validate_result({'contract':contract},s)
        self.assertTrue(any('poster' in i for i in issues));self.assertTrue(any('人脸' in i for i in issues))

if __name__=='__main__':unittest.main()
