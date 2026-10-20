import asyncio,json,unittest
from pathlib import Path
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_tutorial import tutorial_notification

def message(body,flags=0):return dict(sender=4,receiver=2,commandSet=4,commandId=43,flags=flags,payload=bytes(body))
def notify(client,body,sequence=1,flags=0,command=43):reply(client,dict(sequence=sequence,commandId=command),body,lambda b:b.__setitem__(8,flags))
class TutorialTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 async def test_source_vectors_and_unsigned_signed_domains(self):
  rows=json.loads((Path(__file__).resolve().parents[2]/'node/test/fixtures/tutorial-status.json').read_text());self.assertEqual(len(rows),8)
  for v in rows:
   r=tutorial_notification(message(bytes.fromhex(v['bodyHex'])))
   for k,value in v['expected'].items():self.assertEqual(r[k],value,v['name'])
   self.assertFalse(r['physicalCompletionVerified']);self.assertFalse(r['requestAssociationVerified'])
  for step in range(256):
   r=tutorial_notification(message((step,0,0,0,0)));self.assertEqual(r['rawStep'],step);self.assertEqual(r['knownSourceStepName'] is not None,step<11)
  for bit in range(32):
   r=tutorial_notification(message(b'\0'+(1<<bit).to_bytes(4,'little')));self.assertEqual(r['rawCompletionWord'],1<<bit);self.assertEqual(sum(r['sourceFlags'].values()),int(bit<9));self.assertEqual(r['sourceStepStatus']['STEP_FINISH'],bit==30);self.assertEqual(r['sourceStepStatus']['STEP_START'],bit==31)
 async def test_reject_incomplete_invalid_and_encrypted_envelopes(self):
  for n in range(5):self.assertIsNone(tutorial_notification(message(bytes(n))))
  for flags in (128,1,2,3,4,5,6,7,-1,256,True,None):self.assertIsNone(tutorial_notification(message(bytes(5),flags)))
  for key in ('sender','receiver','commandSet','commandId'):self.assertIsNone(tutorial_notification(dict(message(bytes(5)),**{key:0})))
 async def test_tutorial_cannot_complete_pending_query(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.getWorkMode());await fixtures.until(lambda:sent(self.client,16));r=sent(self.client,16);notify(self.client,(0,255,255,255,255),r['sequence']);self.assertFalse(task.done());self.assertTrue(self.gimbal.experimental.pending);reply(self.client,r,(0,62,1,2));await task;self.assertFalse(self.gimbal.experimental.pending);self.assertEqual([f['commandId'] for f in self.client.frames()],[16])
 async def test_tutorial_cannot_supply_joint_feedback_or_complete_move(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.moveTo(pan=5));await fixtures.until(lambda:self.gimbal.activeOperation is not None);owner=self.gimbal.activeOperation;notify(self.client,(255,255,255,255,255));self.assertEqual(self.gimbal.activeOperation,owner);self.assertIsNone(self.gimbal.latestTelemetry);self.assertIsNone(self.gimbal.appCommands.sensorCalibrationStatus);await self.gimbal.stop()
  with self.assertRaises(Exception) as error:await task
  self.assertEqual(error.exception.code,'RS4MINI_MOVE_CANCELLED');self.assertTrue(all(f['commandId']==1 for f in self.client.frames()))
if __name__=='__main__':unittest.main()
