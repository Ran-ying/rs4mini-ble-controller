"""Explicit real-device SDK test; no GUI, motion or maintenance trigger."""
import asyncio,json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'python'))
from rs4mini_sdk.device import BleDevice
async def main():
 if '--help' in sys.argv:
  print('RS4MINI_SDK_TEST=yes RS4MINI_DEVICE_ID=<local ID> python tools/hardware/sdk-python.py');return
 if os.getenv('RS4MINI_SDK_TEST')!='yes' or not os.getenv('RS4MINI_DEVICE_ID'):raise RuntimeError('Explicit SDK test opt-in and local device ID required')
 g=BleDevice(deviceId=os.environ['RS4MINI_DEVICE_ID']);a=g.appCommands;rows=[]
 async def check(name,fn):
  start=time.monotonic()
  try:
   r=await fn();rows.append(dict(name=name,ok=True,elapsedMs=round((time.monotonic()-start)*1000),value=r));return r
  except Exception as e:rows.append(dict(name=name,ok=False,elapsedMs=round((time.monotonic()-start)*1000),code=getattr(e,'code','ERROR')))
 async def reading(fn):
  r=await fn();return {k:r[k] for k in ['rawValue','mode','sourceMode','sourceProfile','sourceWorkMode','inputSource','values','settings'] if k in r}
 try:
  await g.connect(timeoutMs=15000,directConnectTimeoutMs=8000);rows.append(dict(name='connect',ok=g.connected));rows.append(dict(name='deviceLayerOnly',ok=not hasattr(g,'moveTo')))
  await check('attitude',lambda:g.getAttitude(fresh=True,timeoutMs=3000));await check('joints',lambda:g.getJointAngles(fresh=True,timeoutMs=3000));a.useProfile('ronin-2.2.2')
  for name in ['getFollowSensitivity','getMotorSettings','getCustomFollowSettings','getAxisMode','getUserProfile','getWorkMode','getSmoothTrackAxes','getFollowTuning','getRcTuning','getStandaloneTuning']:
   await check(name,lambda name=name:reading(lambda:getattr(a,name)(timeoutMs=3000)))
  if os.getenv('RS4MINI_SDK_WRITEBACK')=='yes':
   baseline=next((r.get('value',{}).get('rawValue') for r in rows if r['name']=='getFollowSensitivity'),None)
   async def write_same():
    if baseline not in (0,1):raise RuntimeError('No valid baseline')
    r=await a.setFollowSensitivity(mode=baseline,timeoutMs=3000);return dict(statusCode=r['statusCode'],acknowledged=r['acknowledged'],requestedMode=baseline)
   async def readback():
    r=await a.getFollowSensitivity(timeoutMs=3000)
    if r['rawValue']!=baseline:raise RuntimeError('Readback mismatch')
    return dict(rawValue=r['rawValue'])
   await check('sensitivity.sameValueWrite',write_same);await check('sensitivity.sameValueReadback',readback)
  for name,fn in [('follow.speed',lambda:a.getFollowSettings(parameter='speed',timeoutMs=3000)),('rc.speed',lambda:a.getRcSettings(parameter='speed',timeoutMs=3000)),('motor.single',lambda:a.getMotorTuning(axis='pitch',parameter='stiffness',timeoutMs=3000)),('motor.bulk',lambda:a.getMotorTuning(timeoutMs=3000)),('handle',lambda:a.getHandleSettings(timeoutMs=3000)),('calibration.query',lambda:a.queryCalibrationStatus(timeoutMs=3000))]:
   await check(name,lambda fn=fn:reading(fn))
  async def degree():
   r=await g.requestDegreeInfo(timeoutMs=3000);return dict(payloadHex=bytes(r.get('payload',r.get('message',{}).get('payload',[]))).hex())
  await check('degreeInfo',degree);await check('stop',g.stop);rows.append(dict(name='decoder',ok=g.decoder.invalidFrames==0 and g.decoder.discardedBytes==0,value=dict(invalidFrames=g.decoder.invalidFrames,discardedBytes=g.decoder.discardedBytes)))
 except Exception as e:rows.append(dict(name='session',ok=False,code=getattr(e,'code','ERROR')))
 finally:
  async def close():
   await g.close();return dict(connected=g.connected,closed=g.closed)
  await check('close',close)
 print(json.dumps(dict(port='python',runtime=sys.version.split()[0],entry='BleDevice',rows=rows),indent=2));sys.exit(1 if any(not r['ok'] for r in rows) else 0)
asyncio.run(main())
