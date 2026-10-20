import asyncio,unittest
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_profile_values import profile_value_write,profile_value_reply
class ProfileValueTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 def calls(self):return [('userProfile',0,self.gimbal.app_commands.get_user_profile,self.gimbal.app_commands.send_user_profile_request,dict(sourceProfileValue=2)),('workMode',62,self.gimbal.app_commands.get_work_mode,self.gimbal.app_commands.send_work_mode_request,dict(sourceMode='Center'))]
 def msg(self,b):return dict(sender=4,receiver=2,commandSet=4,commandId=16,flags=128,payload=bytes(b),raw=b'')
 async def test_distinct_source_values_and_no_inferred_movement_names(self):
  for v in range(6):self.assertEqual(profile_value_write('userProfile',v)['payload'],bytes((0,1,v)))
  for mode,v in [('Free',0),('Flower',1),('Fpv',2),('Center',3)]:self.assertEqual(profile_value_write('workMode',mode)['payload'],bytes((62,1,v)))
  p=profile_value_reply(self.msg([0,0,9,5]),'userProfile');self.assertIsNone(p['sourceUiName']);self.assertTrue(p['withinSourceRange']);w=profile_value_reply(self.msg([0,62,9,128]),'workMode');self.assertIsNone(w['sourceMode']);self.assertTrue(w['withinSourceRange'])
 async def test_unknown_raw_and_bad_replies(self):
  for kind,index,*_ in self.calls():
   r=profile_value_reply(self.msg([0,index,9,255]),kind);self.assertEqual(r['rawValue'],255);self.assertFalse(r['withinSourceRange']);self.assertFalse(r['activePresetVerified'])
   for body in [[0,62 if index==0 else 0,9,2],[0,index,9],[7]]:
    with self.assertRaises(Exception):profile_value_reply(self.msg(body),kind)
 async def test_getters_read_exact_indices_including_zero(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for kind,index,read,write,opts in self.calls():
   before=len([f for f in self.client.frames() if f['commandId']==16]);task=asyncio.create_task(read());await fixtures.until(lambda:len([f for f in self.client.frames() if f['commandId']==16])==before+1);r=sent(self.client,16);self.assertEqual(r['payload'],bytes((index,)));reply(self.client,r,[0,index,9,2]);result=await task;self.assertEqual(result['parameter'],kind);self.assertEqual(result['rawValue'],2);self.assertEqual(result['parameters'][0]['headerByte'],9);self.assertFalse(result['activePresetVerified'])
  self.assertTrue(all(f['commandId']==16 for f in self.client.frames()))
 async def test_owned_setters_ack_only_and_no_cross_domain_commands(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for kind,index,read,write,opts in self.calls():
   before=len([f for f in self.client.frames() if f['commandId']==15]);task=asyncio.create_task(write(**opts));await fixtures.until(lambda:len([f for f in self.client.frames() if f['commandId']==15])==before+1);r=sent(self.client,15);self.assertEqual(r['payload'][0],index)
   with self.assertRaises(Exception) as e:await self.gimbal.setVelocity(pan=.1)
   self.assertEqual(e.exception.code,'RS4MINI_BUSY');reply(self.client,r,[0]);result=await task;self.assertEqual(result['parameter'],kind);self.assertEqual(result['requestedRawValue'],2 if kind=='userProfile' else 3);self.assertFalse(result['activePresetVerified']);self.assertFalse(result['persistenceVerified']);self.assertFalse(result['physicalCompletionVerified'])
  self.assertTrue(all(f['commandId'] in (1,15) for f in self.client.frames()));self.assertFalse(hasattr(self.gimbal.appCommands,"userParameterStatus"))
 async def test_profile_and_work_validation_before_any_frame(self):
  with self.assertRaises(ValueError):await self.gimbal.appCommands.sendUserProfileRequest(sourceProfileValue=2)
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for v in [True,-1,6,2.5,float('nan'),float('inf'),10**1000]:
   with self.assertRaises((ValueError,TypeError)):await self.gimbal.appCommands.sendUserProfileRequest(sourceProfileValue=v)
  for v in ['PF','FPV',2,True,{},None]:
   with self.assertRaises((ValueError,TypeError)):await self.gimbal.appCommands.sendWorkModeRequest(sourceMode=v)
  with self.assertRaises(TypeError):await self.gimbal.appCommands.sendWorkModeRequest(sourceMode='Fpv',index=62)
  self.assertEqual(self.client.frames(),[])
 async def test_nack_does_not_trigger_fallback_save_or_retry(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for kind,index,read,write,opts in self.calls():
   before=len([f for f in self.client.frames() if f['commandId']==15]);task=asyncio.create_task(write(**opts));await fixtures.until(lambda:len([f for f in self.client.frames() if f['commandId']==15])==before+1);r=sent(self.client,15);reply(self.client,dict(r,commandId=16),[0]);await asyncio.sleep(0);self.assertFalse(task.done());reply(self.client,r,[7])
   with self.assertRaises(Exception) as e:await task
   self.assertEqual(e.exception.code,'RS4MINI_DEVICE_ERROR');self.assertEqual(len([f for f in self.client.frames() if f['commandId']==15]),before+1)
  self.assertTrue(all(f['commandId'] in (1,15) for f in self.client.frames()))
 async def test_cancel_preamble_postwrite_timeout_no_replay(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for kind,index,read,write,opts in self.calls():
   before=len([f for f in self.client.frames() if f['commandId']==15]);blocked=asyncio.Event();started=asyncio.Event();original=self.client.write_gatt_char;first=True
   async def send(*args,**kwargs):
    nonlocal first
    if first:first=False;started.set();await blocked.wait()
    await original(*args,**kwargs)
   self.client.write_gatt_char=send;task=asyncio.create_task(write(**opts));await started.wait();stopping=asyncio.create_task(self.gimbal.stop());await asyncio.sleep(0);blocked.set();await stopping
   with self.assertRaises(Exception) as e:await task
   self.assertEqual(e.exception.code,'RS4MINI_OPERATION_CANCELLED');self.assertEqual(len([f for f in self.client.frames() if f['commandId']==15]),before);self.client.write_gatt_char=original;task=asyncio.create_task(write(**opts));await fixtures.until(lambda:len([f for f in self.client.frames() if f['commandId']==15])==before+1);await self.gimbal.stop()
   with self.assertRaises(Exception) as e:await task
   self.assertEqual(e.exception.code,'RS4MINI_OPERATION_CANCELLED')
   with self.assertRaises(Exception) as e:await write(**dict(opts,timeoutMs=10))
   self.assertEqual(e.exception.code,'RS4MINI_RESPONSE_TIMEOUT');self.assertEqual(len([f for f in self.client.frames() if f['commandId']==15]),before+2);self.assertFalse(self.gimbal.experimental.pending)
 async def test_disconnect_reconnect_never_repeats_either_request(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for i,(kind,index,read,write,opts) in enumerate(self.calls()):
   self.client=self.clients[-1];task=asyncio.create_task(write(**opts));await fixtures.until(lambda:sent(self.client,15));await self.client.disconnect()
   with self.assertRaises(Exception) as e:await task
   self.assertEqual(e.exception.code,'RS4MINI_DISCONNECTED');await self.gimbal.connect();self.assertEqual(len([f for c in self.clients for f in c.frames() if f['commandId']==15]),i+1)
