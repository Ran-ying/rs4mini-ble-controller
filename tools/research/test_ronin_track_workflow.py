import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_track_workflow import direct_calls,selected_elements,trace
from ronin_program_entry import view_literals,VIEW
class TrackWorkflowTests(unittest.TestCase):
 def test_call_like_string_is_not_an_invocation_guard(self):self.assertEqual(direct_calls([('const-string/jumbo','v0, LX;->getCmdId()I')]),[])
 def test_direct_guard_call_is_retained_with_descriptor(self):self.assertEqual(direct_calls([('invoke-virtual','v0, LX;->getCmdId()I')]),[dict(className='LX;',method='getCmdId',descriptor='()I')])
 def test_range_bridge_preserves_owner_and_arguments(self):
  r=direct_calls([('invoke-static/range','v1 ... v6, LX;->-$$Nest$mrun(LX; I Ljava/lang/Object;)V')])
  self.assertEqual(r[0]['method'],'-$$Nest$mrun');self.assertEqual(r[0]['descriptor'],'(LX; I Ljava/lang/Object;)V')
 def test_unresolved_invoke_not_silently_ignored(self):
  with self.assertRaises(ValueError):direct_calls([('invoke-custom','v0, unresolved')])
 def test_real_entry_subclass_id_is_preserved(self):
  r=selected_elements('<Root xmlns:android="http://schemas.android.com/apk/res/android"><com.dji.ronin.ui.entry.RoninCreateJumpTextView android:id="@7F0A0313"/></Root>')
  self.assertEqual(r['elements'],[dict(className='com.dji.ronin.ui.entry.RoninCreateJumpTextView',id='@7F0A0313')])
 def test_unidentified_parent_entry_is_not_given_child_id(self):
  r=selected_elements('<Root><com.dji.ronin.ui.create.CreateMainJumpEntryView/></Root>');self.assertIsNone(r['elements'][0]['id'])
 def test_other_jump_widgets_do_not_prove_mount(self):self.assertEqual(selected_elements('<Root><com.dji.ronin.widget.RoninJumpTextView/></Root>')['elements'],[])
 def literal_ops(self):return [('const-string/jumbo','v1, MainRoninNew'),('const/16','v2, 15'),('const','v3, 2131363446'),('const','v4, 2131558933'),('move-result','v5'),('invoke-direct/range','v0 ... v5, '+VIEW+'-><init>(Ljava/lang/String; I I I I)V')]
 def test_explicit_main_selection_does_not_mutate_default(self):
  self.assertEqual(view_literals(self.literal_ops(),selected=('MainRoninNew',))['MainRoninNew']['layoutId'],2131558933);self.assertEqual(view_literals(self.literal_ops()),{})
 def test_explicit_empty_selection_is_empty(self):self.assertEqual(view_literals(self.literal_ops(),selected=()),{})
 def test_bad_xml_is_rejected(self):
  with self.assertRaises(Exception):selected_elements('<Root>')
 def test_apk_hash_checked_before_optional_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'wrong')
   with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d))
 def test_bank_hash_checked_before_optional_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'fixture');(Path(d)/'business-03-code-restored.dex').write_bytes(b'wrong')
   with patch('ronin_program_entry.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()):
    with self.assertRaisesRegex(ValueError,'bank hash mismatch'):trace(p,Path(d))
