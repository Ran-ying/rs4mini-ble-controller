import asyncio,json,struct,unittest
from pathlib import Path
import test_controller as fixtures
from rs4mini_sdk.app_center_info import center_info_spec,center_info_reply
from rs4mini_sdk.protocol import frame,crc16
VECTORS=json.loads((Path(__file__).resolve().parents[2]/'node/test/fixtures/center-info.json').read_text())
PAYLOAD=bytes.fromhex(VECTORS[0]['payloadHex'])
def msg(payload=PAYLOAD,**patch):return dict(dict(sender=229,receiver=2,commandSet=0,commandId=50,flags=128,payload=payload,raw=b'x'),**patch)
class CenterInfoTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 def incoming(self,r,payload=PAYLOAD,**patch):
  raw=bytearray(frame(patch.get('sequence',r['sequence']),patch.get('commandSet',0),patch.get('commandId',50),payload,flags=patch.get('flags',128)))
  raw[4],raw[5]=patch.get('sender',229),patch.get('receiver',2);struct.pack_into('<H',raw,len(raw)-2,crc16(raw[:-2]));self.client.notify(None,raw)
 async def request(self,count=1):
  await fixtures.until(lambda:len([r for r in self.client.frames() if r['commandSet']==0 and r['commandId']==50])==count)
  return [r for r in self.client.frames() if r['commandSet']==0 and r['commandId']==50][-1]
 async def test_shared_contracts_and_versions(self):
  for row in VECTORS:
   m=msg(bytes.fromhex(row['payloadHex']))
   if 'error' in row:
    with self.assertRaises(Exception) as raised:center_info_reply(m,row['sourceVersion'])
    self.assertEqual(raised.exception.code,row['error'])
   else:
    r=center_info_reply(m,row['sourceVersion']);self.assertEqual(r['sourceSerialNumber'],row['sourceSerialNumber']);self.assertEqual(r['serialNumberRawHex'],row['serialNumberRawHex']);self.assertEqual(r['dateRaw']['year'],2026);self.assertFalse(r['activationValidityVerified'])
  for v,b in [('Ver1_0',1),('Ver1_1',17),('Ver1_3',17),('Ver13',1)]:self.assertEqual(center_info_spec(v)['payload'],bytes([b]))
  for v in [None,1,True,'OTHER','Ver14',{}]:
   with self.assertRaises(ValueError):center_info_spec(v)
 async def test_flags_envelope_and_snapshot(self):
  for flags in range(256):
   if flags&128 and not flags&7:self.assertTrue(center_info_reply(msg(flags=flags),'Ver1_1')['acknowledged'])
   else:
    with self.assertRaises(Exception) as raised:center_info_reply(msg(flags=flags),'Ver1_1')
    self.assertEqual(raised.exception.code,'RS4MINI_PROTOCOL_ERROR')
  for patch in [dict(sender=4),dict(sender=5),dict(receiver=4),dict(commandSet=4),dict(commandId=1),dict(flags=True),dict(flags=256),dict(flags=-1),dict(payload=[])]:
   m=msg();m.update(patch)
   with self.assertRaises(Exception):center_info_reply(m,'Ver1_1')
  p=bytearray(PAYLOAD);r=center_info_reply(msg(p),'Ver1_1');p[:]=bytes(len(p));self.assertEqual(r['message']['payload'],PAYLOAD)
 async def test_profile_and_argument_validation_before_send(self):
  with self.assertRaises(ValueError):await self.gimbal.appCommands.getCenterActivationInfo(sourceVersion='Ver1_1')
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for options in [{},{'sourceVersion':'OTHER'},{'sourceVersion':'Ver1_1','timeoutMs':0},{'sourceVersion':'Ver1_1','receiver':229}]:
   with self.assertRaises((TypeError,ValueError)):await self.gimbal.appCommands.getCenterActivationInfo(**options)
  with self.assertRaises(ValueError):await self.gimbal.experimental._query_payload_command('bad',(4,50),b'\x11',30,receiver=229)
  self.assertEqual(self.client.frames(),[])
 async def test_center_target_and_all_correlation_dimensions(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');q=asyncio.create_task(self.gimbal.app_commands.get_center_activation_info(sourceVersion='Ver1_1'));r=await self.request();self.assertEqual(r['receiver'],229);self.assertEqual(r['payload'],b'\x11');self.assertEqual(r['flags'],64)
  for patch in [dict(sender=4),dict(sender=5),dict(receiver=4),dict(sequence=r['sequence']+1),dict(commandSet=4),dict(commandId=1),dict(flags=0)]:self.incoming(r,**patch);self.assertEqual(len(self.gimbal.experimental.pending),1)
  self.incoming(r);result=await q;self.assertEqual(result['sourceSerialNumber'],'A45-1');self.assertEqual(len(self.client.frames()),1);self.assertIsNone(self.gimbal.latestTelemetry)
 async def test_concurrent_query_targets_keep_separate_pending(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');q=asyncio.create_task(self.gimbal.appCommands.getCenterActivationInfo(sourceVersion='Ver1_1'));other=asyncio.create_task(self.gimbal.appCommands.getMotorTuning(axis='pitch',parameter='stiffness'));a=await self.request();await fixtures.until(lambda:any(f['commandSet']==4 and f['commandId']==50 for f in self.client.frames()));b=next(f for f in self.client.frames() if f['commandSet']==4 and f['commandId']==50);self.incoming(a);await q;self.assertEqual(len(self.gimbal.experimental.pending),1);self.incoming(b,b'\0\0\x01\x0a',commandSet=4,commandId=50,sender=4);self.assertEqual((await other)['values'][0]['rawValue'],10)
 async def test_bad_ack_never_returns_previous_success(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');q=asyncio.create_task(self.gimbal.appCommands.getCenterActivationInfo(sourceVersion='Ver1_1'));self.incoming(await self.request());await q
  for count,(body,flags,code) in enumerate([(b'\0',128,'RS4MINI_PROTOCOL_ERROR'),(b'\7',128,'RS4MINI_DEVICE_ERROR'),(PAYLOAD,129,'RS4MINI_PROTOCOL_ERROR')],2):
   q=asyncio.create_task(self.gimbal.appCommands.getCenterActivationInfo(sourceVersion='Ver1_1'));self.incoming(await self.request(count),body,flags=flags)
   with self.assertRaises(Exception) as raised:await q
   self.assertEqual(raised.exception.code,code);self.assertEqual(self.gimbal.experimental.pending,{})
  self.assertEqual(len(self.client.frames()),4)
 async def test_timeout_late_response_disconnect_no_replay(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');q=asyncio.create_task(self.gimbal.appCommands.getCenterActivationInfo(sourceVersion='Ver1_1',timeoutMs=30));r=await self.request()
  with self.assertRaises(Exception) as raised:await q
  self.assertEqual(raised.exception.code,'RS4MINI_RESPONSE_TIMEOUT');self.incoming(r);self.assertEqual(self.gimbal.experimental.pending,{})
  q=asyncio.create_task(self.gimbal.appCommands.getCenterActivationInfo(sourceVersion='Ver1_1'));await self.request(2);await self.gimbal.disconnect()
  with self.assertRaises(Exception) as raised:await q
  self.assertEqual(raised.exception.code,'RS4MINI_DISCONNECTED')
 async def test_task_cancel_and_profile_busy(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');q=asyncio.create_task(self.gimbal.appCommands.getCenterActivationInfo(sourceVersion='Ver1_1'));r=await self.request()
  with self.assertRaises(Exception) as raised:self.gimbal.appCommands.useProfile('ronin-2.2.2')
  self.assertEqual(raised.exception.code,'RS4MINI_BUSY');q.cancel()
  with self.assertRaises(asyncio.CancelledError):await q
  self.incoming(r);self.assertEqual(self.gimbal.experimental.pending,{});self.assertEqual(len(self.client.frames()),1)
