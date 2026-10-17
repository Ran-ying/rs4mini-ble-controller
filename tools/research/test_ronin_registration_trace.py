import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_registration_trace import nearest_declaration,literal_collisions,trace

class RegistrationTraceTests(unittest.TestCase):
 def fixture(self):
  return {'Child':dict(superclass='Parent',methods=[]),'Parent':dict(superclass='Object',methods=[dict(method='run',descriptor='()V',accessFlags=1)])}
 def test_inherited_declaration_is_found(self):self.assertEqual(nearest_declaration(self.fixture(),'Child','run','()V')['className'],'Parent')
 def test_nearest_override_wins(self):
  cs=self.fixture();cs['Child']['methods']=[dict(method='run',descriptor='()V',accessFlags=1)]
  self.assertEqual(nearest_declaration(cs,'Child','run','()V')['className'],'Child')
 def test_descriptor_not_just_method_name(self):
  cs=self.fixture();cs['Child']['methods']=[dict(method='run',descriptor='(I)V',accessFlags=1)]
  self.assertEqual(nearest_declaration(cs,'Child','run','()V')['className'],'Parent')
 def test_missing_declaration_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'unresolved'):nearest_declaration(self.fixture(),'Child','other','()V')
 def test_cycle_is_rejected(self):
  cs=self.fixture();cs['Parent']['superclass']='Child'
  with self.assertRaisesRegex(ValueError,'cyclic'):nearest_declaration(cs,'Child','missing','()V')
 def test_duplicate_exact_declarations_rejected(self):
  cs=self.fixture();cs['Parent']['methods']*=2
  with self.assertRaisesRegex(ValueError,'duplicate'):nearest_declaration(cs,'Child','run','()V')
 def test_same_literal_different_fields_preserves_collision(self):
  rows=[dict(declaringClass='Child',fieldName='A',literalKeyName='Same'),dict(declaringClass='Parent',fieldName='B',literalKeyName='Same')]
  self.assertEqual(literal_collisions(rows),{'Same':['Child->A','Parent->B']})
 def test_distinct_literals_not_field_names_determine_collision(self):
  rows=[dict(declaringClass=c,fieldName='A',literalKeyName=c) for c in ('Child','Parent')]
  self.assertEqual(literal_collisions(rows),{})
 def test_unresolved_literal_is_not_silently_ignored(self):
  with self.assertRaisesRegex(ValueError,'unresolved'):literal_collisions([dict(declaringClass='A',fieldName='B',literalKeyName=None)])
 def test_apk_hash_checked_before_optional_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'wrong')
   with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d)/'sdk')
 def test_sdk_hash_checked_before_optional_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'fixture');q=Path(d)/'sdk';q.write_bytes(b'wrong')
   with patch('ronin_key_support.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()):
    with self.assertRaisesRegex(ValueError,'SDK hash mismatch'):trace(p,q)
