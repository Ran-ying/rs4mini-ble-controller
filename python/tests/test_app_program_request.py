import asyncio,unittest
import test_controller as fixtures
from test_app_commands import reply
from rs4mini_sdk.app_program_request import program_status_request_spec,program_status_request_reply
class ProgramRequestTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 def incoming(self,r,body=b'\0',flags=128):reply(self.client,r,body,lambda data:data.__setitem__(8,flags))
 async def sent(self,count=1):
  await fixtures.until(lambda:len([f for f in self.client.frames() if f['commandId']==107])==count)
  return [f for f in self.client.frames() if f['commandId']==107][-1]
 async def test_fixed_payload_and_invalid_names(self):
  for name,h in (('track','00020162'),('timelapse','00020137'),('panorama','00020163')):self.assertEqual(program_status_request_spec(name)['payload'].hex(),h)
  for name in (None,98,'delay','TRACK',{}):
   with self.assertRaises(ValueError):program_status_request_spec(name)
 async def test_raw_ack_body_is_not_fresh_state(self):
  m=dict(sender=4,receiver=2,commandSet=4,commandId=107,flags=128,payload=bytes.fromhex('0001620401020304'),raw=b'x')
  r=program_status_request_reply(m,'track');self.assertEqual(r['bodyHex'],'01620401020304');self.assertFalse(r['freshStatusVerified']);self.assertFalse(r['programCorrelationVerified'])
  for flags in (129,-128,384):
   with self.assertRaises(Exception) as raised:program_status_request_reply(dict(m,flags=flags),'track')
   self.assertEqual(raised.exception.code,'RS4MINI_PROTOCOL_ERROR')
 async def test_profile_and_invalid_before_sends(self):
  with self.assertRaises(ValueError):await self.gimbal.appCommands.sendProgramStatusRequest(program='track')
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for spec in (dict(program='delay'),dict(program=98),dict(program='track',timeoutMs=0),dict(program='track',requestType=0)):
   with self.assertRaises((ValueError,TypeError)):await self.gimbal.appCommands.sendProgramStatusRequest(**spec)
  self.assertEqual(self.client.frames(),[])
 async def test_three_requests_ack_only_not_notification_or_cache(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for count,name in enumerate(('track','timelapse','panorama'),1):
   q=asyncio.create_task(self.gimbal.app_commands.send_program_status_request(program=name));r=await self.sent(count);self.assertEqual(r['payload'],program_status_request_spec(name)['payload']);self.assertEqual(r['flags'],64);self.incoming(r,bytes.fromhex('00620402030405'),0);self.assertEqual(len(self.gimbal.experimental.pending),1);before=self.gimbal.appCommands.programStatus;self.incoming(r);result=await q;self.assertEqual(result['requestedProgram'],name);self.assertTrue(result['acknowledged']);self.assertEqual(result['bodyHex'],'');self.assertFalse(result['freshStatusVerified']);self.assertEqual(self.gimbal.appCommands.programStatus,before)
  self.assertEqual(len(self.client.frames()),3)
 async def test_simultaneous_queries_match_sequence(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');a=asyncio.create_task(self.gimbal.appCommands.sendProgramStatusRequest(program='track'));b=asyncio.create_task(self.gimbal.appCommands.sendProgramStatusRequest(program='timelapse'));await self.sent(2);r=self.client.frames();self.incoming(r[1]);self.assertEqual((await b)['requestedProgram'],'timelapse');self.incoming(r[0]);self.assertEqual((await a)['requestedProgram'],'track')
 async def test_bad_ack_and_nack_no_cached_success(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for count,(body,flags,code) in enumerate(((b'\7',128,'RS4MINI_DEVICE_ERROR'),(b'',128,'RS4MINI_PROTOCOL_ERROR'),(b'\0',129,'RS4MINI_PROTOCOL_ERROR')),1):
   q=asyncio.create_task(self.gimbal.appCommands.sendProgramStatusRequest(program='track'));r=await self.sent(count);self.incoming(r,bytes.fromhex('00620401020304'),0);self.incoming(r,body,flags)
   with self.assertRaises(Exception) as raised:await q
   self.assertEqual(raised.exception.code,code);self.assertEqual(self.gimbal.experimental.pending,{})
  self.assertEqual(len(self.client.frames()),3)
 async def test_timeout_late_ack_and_disconnect_no_replay(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');q=asyncio.create_task(self.gimbal.appCommands.sendProgramStatusRequest(program='track',timeoutMs=30));r=await self.sent()
  with self.assertRaises(Exception) as raised:await q
  self.assertEqual(raised.exception.code,'RS4MINI_RESPONSE_TIMEOUT');self.incoming(r);self.assertEqual(self.gimbal.experimental.pending,{})
  q=asyncio.create_task(self.gimbal.appCommands.sendProgramStatusRequest(program='panorama'));await self.sent(2);await self.gimbal.disconnect()
  with self.assertRaises(Exception) as raised:await q
  self.assertEqual(raised.exception.code,'RS4MINI_DISCONNECTED');self.assertEqual(len([f for f in self.client.frames() if f['commandId']==107]),2)
 async def test_task_cancel_clears_pending_no_repeat(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');q=asyncio.create_task(self.gimbal.appCommands.sendProgramStatusRequest(program='track'));await self.sent();q.cancel()
  with self.assertRaises(asyncio.CancelledError):await q
  self.assertEqual(self.gimbal.experimental.pending,{});self.assertEqual(len(self.client.frames()),1)
