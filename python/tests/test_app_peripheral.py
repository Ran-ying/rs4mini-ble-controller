import json,pathlib,unittest,asyncio
import test_controller as fixtures
from test_app_commands import reply
from rs4mini_sdk.app_peripheral import peripheral_notification
VECTORS=json.loads((pathlib.Path(__file__).resolve().parents[2]/'node/test/fixtures/peripheral-status.json').read_text())
def message(body):return dict(sender=4,receiver=2,commandSet=4,commandId=102,flags=0,payload=bytes.fromhex(body))
class PeripheralTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 def incoming(self,body,sequence=5,command=102,flags=0):reply(self.client,dict(sequence=sequence,commandSet=4,commandId=command),bytes.fromhex(body),lambda b:b.__setitem__(8,flags))
 async def test_all_shared_source_getter_contracts(self):
  for v in VECTORS:
   result=peripheral_notification(message(v['bodyHex']))
   for k,value in v['expected'].items():self.assertEqual(result[k],value,v['name'])
  self.assertEqual(sum(len(r['sourceViews']) for r in peripheral_notification(message(VECTORS[0]['bodyHex']))['records']),43)
 async def test_wrong_envelope_and_invalid_records_rejected(self):
  m=message('0122020a00')
  for patch in (dict(sender=36),dict(receiver=4),dict(commandSet=0),dict(commandId=107),dict(flags=128),dict(flags=1),dict(flags=-128),dict(flags=256),dict(flags=False),dict(payload=None)):self.assertIsNone(peripheral_notification(dict(m,**patch)))
  for body in ('','0122','01220200','012280'+'00'*128):self.assertIsNone(peripheral_notification(message(body)))
 async def test_every_source_length_and_missing_record(self):
  for n in range(128):
   m=message('');m['payload']=bytes([1,0,n])+bytes([255])*n;self.assertEqual(peripheral_notification(m)['records'][0]['sourceInt32'],0 if n==0 else 16777215 if n==3 else -1)
  self.assertEqual(peripheral_notification(message('01'))['records'],[])
 async def test_source_gate_copies_observer_and_cache_isolation(self):
  self.incoming('0122020a00');self.assertIsNone(self.gimbal.app_commands.peripheral_status);self.gimbal.appCommands.useProfile('ronin-2.2.2')
  def observer(s):
   if s['kind']=='peripheral':s['records'][0]['sourceViews'][0]['value']=999;raise RuntimeError('observer')
  self.gimbal.onAppStatus=observer;self.incoming('0122020a00');snapshot=self.gimbal.appCommands.peripheralStatus;self.assertEqual(snapshot['records'][0]['sourceViews'][0]['value'],1);snapshot['records'][0]['sourceTypes'].append('wrong');self.assertEqual(len(self.gimbal.appCommands.peripheralStatus['records'][0]['sourceTypes']),1);self.assertIsNone(self.gimbal.latestTelemetry);self.assertIsNone(self.gimbal.appCommands.programStatus);self.assertEqual(self.client.frames(),[])
 async def test_notification_does_not_complete_pending_query(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');q=asyncio.create_task(self.gimbal.appCommands.getFollowSensitivity());await fixtures.until(lambda:any(f['commandId']==16 for f in self.client.frames()));r=next(f for f in self.client.frames() if f['commandId']==16);self.incoming('0122020a00',r['sequence'],flags=64);self.assertEqual(len(self.gimbal.experimental.pending),1);self.assertFalse(q.done());self.assertEqual(len(self.client.frames()),1);self.incoming('00960100',r['sequence'],16,128);self.assertEqual((await q)['mode'],0)
 async def test_bad_frame_retains_snapshot_and_nonrecord_flag_opaque(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');self.incoming('0122020a00');before=self.gimbal.appCommands.peripheralStatus;self.incoming('0122021400220200');self.assertEqual(self.gimbal.appCommands.peripheralStatus,before);self.incoming('002280');self.assertEqual(self.gimbal.appCommands.peripheralStatus['records'],[]);self.assertEqual(self.client.frames(),[])
 async def test_lifecycle_clears_without_subscription(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');self.incoming('0122020a00');self.gimbal.appCommands.useProfile('ronin-2.2.2');self.assertIsNone(self.gimbal.appCommands.peripheralStatus);self.incoming('0122020a00');self.gimbal.experimental.useProfile('rs3');self.assertIsNone(self.gimbal.appCommands.peripheralStatus);self.gimbal.appCommands.useProfile('ronin-2.2.2');self.incoming('0122020a00');await self.gimbal.disconnect();self.assertIsNone(self.gimbal.appCommands.peripheralStatus)
