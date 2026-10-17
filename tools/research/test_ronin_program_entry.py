import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_program_entry import switch_assignments,view_literals,layout_facts,direct_return,trace,VIEW
class ProgramEntryTests(unittest.TestCase):
 def switch(self):return [('sget-object','v1, LE;->HG724 LE;'),('invoke-virtual','v1, LE;->ordinal()I'),('move-result','v1'),('const/16','v2, 9'),('aput','v2, v0, v1')]
 def test_selected_switch_assignment_uses_case_not_ordinal(self):self.assertEqual(switch_assignments(self.switch(),'LE;'),{'HG724':9})
 def test_switch_register_mismatch_rejected(self):
  ops=self.switch();ops[-1]=('aput','v3, v0, v1')
  with self.assertRaises(ValueError):switch_assignments(ops,'LE;')
 def test_duplicate_target_assignment_rejected(self):
  with self.assertRaises(ValueError):switch_assignments(self.switch()*2,'LE;')
 def test_other_model_pattern_is_outside_selected_scope(self):self.assertEqual(switch_assignments([('sget-object','v0, LE;->OTHER LE;')],'LE;'),{})
 def literals(self):return [('const-string/jumbo','v1, CreateTrackRonins'),('const/16','v2, 23'),('const','v3, 2131363675'),('const','v4, 2131558880'),('move-result','v5'),('invoke-direct/range','v0 ... v5, '+VIEW+'-><init>(Ljava/lang/String; I I I I)V')]
 def test_view_four_literals_allow_unresolved_parent_without_guessing(self):self.assertEqual(view_literals(self.literals())['CreateTrackRonins'],dict(ordinal=23,viewId=2131363675,layoutId=2131558880))
 def test_unknown_layout_literal_rejected(self):
  ops=self.literals();ops[3]=('move-result','v4')
  with self.assertRaises(ValueError):view_literals(ops)
 def test_unhandled_branch_not_treated_as_linear_literals(self):
  with self.assertRaises(ValueError):view_literals([('if-eqz','v0, +2h')])
 def test_layout_fact_selects_only_real_jump_widget_ids(self):
  r=layout_facts('<Root xmlns:android="http://schemas.android.com/apk/res/android"><com.dji.ronin.widget.RoninJumpTextView android:id="@7F0A075B"/><TextView android:id="@7F0A0001"/></Root>')
  self.assertEqual(r,dict(rootClass='Root',jumpIds=['@7F0A075B']))
 def test_direct_return_carries_literal_or_class_field(self):
  self.assertEqual(direct_return([('const/4','v1, 1'),('return','v1')]),1)
  self.assertEqual(direct_return([('sget-object','v0, LM;->HG724 LM;'),('return-object','v0')]),'LM;->HG724 LM;')
 def test_non_direct_or_wrong_register_return_rejected(self):
  for ops in ([('const/4','v1, 1'),('return','v2')],[('invoke-static','LM;->call()I'),('move-result','v0')]):
   with self.assertRaises(ValueError):direct_return(ops)
 def test_apk_hash_checked_before_optional_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'wrong')
   with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d))
 def test_bank_hash_checked_before_optional_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'fixture');(Path(d)/'business-03-code-restored.dex').write_bytes(b'wrong')
   with patch('ronin_program_entry.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()):
    with self.assertRaisesRegex(ValueError,'bank hash mismatch'):trace(p,Path(d))
