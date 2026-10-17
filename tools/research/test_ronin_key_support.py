import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_key_support import select_source_keys,normalize_annotations,trace,KEY,COMPLEX
class KeySupportTests(unittest.TestCase):
 def resolve(self,rows,target='Child'):return select_source_keys(rows,target,{'Child','Parent','Root'})
 def test_included_parent_matches_child(self):self.assertEqual(self.resolve([dict(includedAbstractions=['Parent'])])['registrationCandidateIndexes'],[0])
 def test_default_matches_non_null_target(self):self.assertTrue(self.resolve([{}])['sourceSupport'])
 def test_exact_excluded_target_blocks_default(self):
  r=self.resolve([dict(excludedAbstractions=['Child'])]);self.assertFalse(r['sourceSupport']);self.assertEqual(r['getKeyCandidateIndexes'],[0]);self.assertEqual(r['registrationCandidateIndexes'],[])
 def test_parent_exclusion_is_not_inherited_set_contains(self):self.assertTrue(self.resolve([dict(excludedAbstractions=['Parent'])])['sourceSupport'])
 def test_exclusion_removes_exact_included_map_key(self):self.assertFalse(self.resolve([dict(includedAbstractions=['Parent'],excludedAbstractions=['Parent'])])['sourceSupport'])
 def test_last_default_wins(self):self.assertEqual(self.resolve([{},{}])['registrationCandidateIndexes'],[1])
 def test_duplicate_include_retains_first(self):
  r=self.resolve([dict(includedAbstractions=['Parent']),dict(includedAbstractions=['Parent'])]);self.assertEqual(r['registrationCandidateIndexes'],[0]);self.assertEqual(r['duplicateIncludedClasses'],['Parent'])
 def test_multiple_ancestor_matches_keep_ambiguity_not_most_specific(self):
  r=self.resolve([dict(includedAbstractions=['Root']),dict(includedAbstractions=['Child'])]);self.assertEqual(r['registrationCandidateIndexes'],[0,1]);self.assertFalse(r['selectionUnambiguous'])
 def test_class_map_match_overrides_default(self):self.assertEqual(self.resolve([{},dict(includedAbstractions=['Parent'])])['registrationCandidateIndexes'],[1])
 def test_null_class_never_supported(self):
  r=self.resolve([{}],None);self.assertFalse(r['sourceSupport']);self.assertEqual(r['getKeyCandidateIndexes'],[])
 def test_key_and_complex_are_invalid_together_in_source(self):
  self.assertEqual(normalize_annotations([dict(typeName=KEY),dict(typeName=COMPLEX)],{}),([],'both-key-and-complex-invalid-in-source'))
 def test_nested_complex_order_and_source_defaults(self):
  defaults=dict(accessType=None,includedAbstractions=[],excludedAbstractions=[],type='Object',types=[])
  rows,error=normalize_annotations([dict(typeName=COMPLEX,elements=dict(value=[dict(typeName=KEY,elements=dict(accessType=3,includedAbstractions=['Parent'])),dict(typeName=KEY,elements=dict(accessType=6))]))],defaults)
  self.assertIsNone(error);self.assertEqual([r['accessType'] for r in rows],[3,6]);self.assertEqual(rows[1]['includedAbstractions'],[])
 def test_apk_hash_checked_before_optional_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'wrong')
   with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d)/'sdk')
 def test_sdk_hash_checked_before_optional_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'fixture');q=Path(d)/'sdk';q.write_bytes(b'wrong')
   with patch('ronin_key_support.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()):
    with self.assertRaisesRegex(ValueError,'SDK hash mismatch'):trace(p,q)
