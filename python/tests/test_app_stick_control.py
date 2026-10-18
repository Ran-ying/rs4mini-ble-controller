import asyncio,json,unittest
from pathlib import Path
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_handheld_stick import handheld_stick_control_payload,handheld_stick_control_reply

def message(payload,flags=128):return dict(sender=4,receiver=2,commandSet=4,commandId=88,flags=flags,payload=bytes(payload),raw=b'')
class StickControlTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 async def test_shared_contracts_and_boolean_domain(self):
  rows=json.loads((Path(__file__).resolve().parents[2]/'node/test/fixtures/handheld-stick-control.json').read_text());self.assertEqual(len(rows),3)
  for v in rows:
   r=handheld_stick_control_reply(message(bytes.fromhex(v['payloadHex'])),v['enabled']);self.assertEqual(handheld_stick_control_payload(v['enabled']),bytes((int(v['enabled']),)))
   for k,value in v['expected'].items():self.assertEqual(r[k],value)
   for key in ('deviceVerified','physicalCompletionVerified','readbackVerified','persistenceVerified','notificationAssociationVerified'):self.assertFalse(r[key])
  for value in (None,0,1,'true',{},[]):
   with self.assertRaises(ValueError):handheld_stick_control_payload(value)
  for flags in range(129,136):
   with self.assertRaises(Exception) as error:handheld_stick_control_reply(message((0,),flags),True)
   self.assertEqual(error.exception.code,'RS4MINI_PROTOCOL_ERROR')
 async def test_profile_and_arguments_before_writes(self):
  with self.assertRaises(ValueError):await self.gimbal.appCommands.sendHandheldStickControlRequest(enabled=True)
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for options in ({},{'enabled':1},{'enabled':'false'},{'enabled':None},{'enabled':False,'timeoutMs':0},{'enabled':True,'timeoutMs':True},{'enabled':True,'persist':True}):
   with self.assertRaises((TypeError,ValueError)):await self.gimbal.appCommands.sendHandheldStickControlRequest(**options)
  self.assertEqual(self.client.frames(),[])
 async def test_owned_request_and_opaque_ack_leave_source_cache(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');reply(self.client,dict(sequence=1,commandId=87),bytes(6),lambda b:b.__setitem__(8,0));cache=self.gimbal.appCommands.handheldStickStatus;task=asyncio.create_task(self.gimbal.appCommands.send_handheld_stick_control_request(enabled=True));await fixtures.until(lambda:sent(self.client,88));request=sent(self.client,88);self.assertEqual(request['payload'],b'\1');self.assertEqual(request['flags'],64)
  with self.assertRaises(Exception) as error:await self.gimbal.setVelocity(pan=.1)
  self.assertEqual(error.exception.code,'RS4MINI_BUSY')
  reply(self.client,dict(request,sequence=request['sequence']+1),(0,));reply(self.client,request,(0,),lambda b:b.__setitem__(8,0));reply(self.client,request,(0,),lambda b:b.__setitem__(4,5));self.assertTrue(self.gimbal.experimental.pending);reply(self.client,request,(0,255,1,2));r=await task;self.assertTrue(r['requestedEnabled']);self.assertEqual(r['bodyHex'],'ff0102');self.assertEqual(self.gimbal.appCommands.handheldStickStatus,cache);self.assertIsNone(self.gimbal.latestTelemetry);self.assertFalse(self.gimbal.experimental.pending)
 async def test_push_does_not_complete_request_or_get_overwritten(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.sendHandheldStickControlRequest(enabled=False));await fixtures.until(lambda:sent(self.client,88));request=sent(self.client,88);reply(self.client,dict(request,commandId=87),(0,0,0,0,2,0),lambda b:b.__setitem__(8,0));cache=self.gimbal.appCommands.handheldStickStatus;self.assertTrue(cache['sourceStickControlEnabled']);self.assertFalse(task.done());reply(self.client,request,(0,));self.assertFalse((await task)['requestedEnabled']);self.assertEqual(self.gimbal.appCommands.handheldStickStatus,cache)
 async def test_ack_errors_clear_transaction(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for payload,flags,code in [((7,),128,'RS4MINI_DEVICE_ERROR'),((),128,'RS4MINI_PROTOCOL_ERROR'),((0,),131,'RS4MINI_PROTOCOL_ERROR')]:
   count=len([f for f in self.client.frames() if f['commandId']==88]);task=asyncio.create_task(self.gimbal.appCommands.sendHandheldStickControlRequest(enabled=False));await fixtures.until(lambda:len([f for f in self.client.frames() if f['commandId']==88])>count);reply(self.client,sent(self.client,88),payload,lambda b:b.__setitem__(8,flags))
   with self.assertRaises(Exception) as error:await task
   self.assertEqual(error.exception.code,code);self.assertFalse(self.gimbal.experimental.pending);self.assertIsNone(self.gimbal.appCommands.handheldStickStatus)
 async def test_cancel_preamble_sends_no_request(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');blocked=asyncio.Event();started=asyncio.Event();original=self.client.write_gatt_char;first=True
  async def write(*args,**kwargs):
   nonlocal first
   if first:first=False;started.set();await blocked.wait()
   await original(*args,**kwargs)
  self.client.write_gatt_char=write;task=asyncio.create_task(self.gimbal.appCommands.sendHandheldStickControlRequest(enabled=True));await started.wait();stopping=asyncio.create_task(self.gimbal.stop());await asyncio.sleep(0);blocked.set();await stopping
  with self.assertRaises(Exception) as error:await task
  self.assertEqual(error.exception.code,'RS4MINI_OPERATION_CANCELLED');self.assertIsNone(sent(self.client,88))
 async def test_cancel_sent_request_and_ignore_late_ack(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.sendHandheldStickControlRequest(enabled=True));await fixtures.until(lambda:sent(self.client,88));request=sent(self.client,88);await self.gimbal.stop()
  with self.assertRaises(Exception) as error:await task
  self.assertEqual(error.exception.code,'RS4MINI_OPERATION_CANCELLED');reply(self.client,request,(0,));self.assertEqual(len([f for f in self.client.frames() if f['commandId']==88]),1);self.assertIsNone(self.gimbal.appCommands.handheldStickStatus)
 async def test_timeout_no_retry_or_inverse(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  with self.assertRaises(Exception) as error:await self.gimbal.appCommands.sendHandheldStickControlRequest(enabled=False,timeoutMs=10)
  self.assertEqual(error.exception.code,'RS4MINI_RESPONSE_TIMEOUT');self.assertEqual(len([f for f in self.client.frames() if f['commandId']==88]),1);self.assertFalse(self.gimbal.experimental.pending)
if __name__=='__main__':unittest.main()
