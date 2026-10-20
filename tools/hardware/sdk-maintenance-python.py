"""Opt-in direct BLE SDK maintenance checks; never run by default tests/CI."""
import argparse,asyncio,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'python'))
from rs4mini_sdk.device import BleDevice
ACTIONS=('fine-tune','autotune','horizontal','acceleration-echo')

async def run(action):
    if action not in ACTIONS:raise RuntimeError('Unknown maintenance case')
    if os.getenv('RS4MINI_SDK_TEST')!='yes' or os.getenv('RS4MINI_SDK_MAINTENANCE')!=action or not os.getenv('RS4MINI_DEVICE_ID'):
        raise RuntimeError('Explicit test opt-in, selected maintenance case and local device ID required')
    folder=ROOT/'node/captures';folder.mkdir(exist_ok=True)
    capture=folder/('sdk-python-'+action+'-'+str(time.time_ns())+'.jsonl')
    def save(kind,data):
        with capture.open('a') as f:f.write(json.dumps(dict(at=time.time(),kind=kind,data=data),default=lambda x:bytes(x).hex())+'\n')
    g=BleDevice(deviceId=os.environ['RS4MINI_DEVICE_ID']);a=g.appCommands
    summary=dict(port='python',runtime=sys.version.split()[0],action=action,completed=False,physicalObservedByUser=None)
    def status(s):
        save('status',s)
        if s.get('kind') in ('calibration','sensorCalibration'):print('PROGRESS',s.get('state',s.get('sourceStatus')),s.get('percent',s.get('rawProgressValue')),flush=True)
    g.onAppStatus=status;g.onMessage=lambda m:save('raw',m);g.onTelemetry=lambda t:save('telemetry',t)
    try:
        await g.connect(timeoutMs=15000,directConnectTimeoutMs=8000)
        a.useProfile('ronin-2.2.2')
        motor=await a.getMotorSettings(timeoutMs=3000);save('motorPreflight',motor)
        if motor.get('settings',{}).get('enabled') is not True:raise RuntimeError('Motor must already be enabled')
        print('PREPARE_5_SECONDS',action,flush=True);await asyncio.sleep(5)
        if action=='fine-tune':
            results=[]
            for axis in ('pitch','roll'):
                before=await g.getJointAngles(fresh=True)
                plus=await a.sendFineTuneRequest(axis=axis,adjustmentDegrees=1,timeoutMs=5000);save(axis+'Plus',plus)
                await asyncio.sleep(4);after_plus=await g.getJointAngles(fresh=True)
                minus=await a.sendFineTuneRequest(axis=axis,adjustmentDegrees=-1,timeoutMs=5000);save(axis+'Minus',minus)
                await asyncio.sleep(4);after_minus=await g.getJointAngles(fresh=True)
                effect=dict(axis=axis,before=before[axis],afterPlus=after_plus[axis],afterMinus=after_minus[axis],plusStatus=plus['statusCode'],minusStatus=minus['statusCode'])
                effect['directionMatched']=effect['afterPlus']-effect['before']>.2 and effect['afterMinus']-effect['afterPlus']<-.2
                results.append(effect);save('effect',effect);print('EFFECT',json.dumps(effect),flush=True)
            summary['effects']=results;summary['completed']=all(x['directionMatched'] for x in results)
        elif action=='acceleration-echo':
            before=await a.getFollowTuning(parameter='acceleration',timeoutMs=5000)
            levels=await a.getFollowSettings(parameter='acceleration',timeoutMs=5000)
            if len(before['values'])!=3 or any(v['rawValue']!=1 for v in before['values']) or set(levels['settings'].values())!={'low'}:
                raise RuntimeError('Expected authorized baseline1/Low; no writes')
            for axis in ('pitch','roll','yaw'):
                save('accelerationEcho',await a.setFollowTuning(axis=axis,parameter='acceleration',value=1,timeoutMs=5000))
            after=await a.getFollowTuning(parameter='acceleration',timeoutMs=5000)
            final_levels=await a.getFollowSettings(parameter='acceleration',timeoutMs=5000)
            summary['values']=[dict(axis=v['axis'],rawValue=v['rawValue']) for v in after['values']]
            summary['levelsUnchanged']=levels['settings']==final_levels['settings']
            summary['completed']=len(after['values'])==3 and all(v['rawValue']==1 for v in after['values']) and summary['levelsUnchanged']
        elif action=='horizontal':
            save('request',await a.sendComponentCalibrationRequest(sourcePart='AUTO',timeoutMs=5000))
            deadline=time.monotonic()+65
            while time.monotonic()<deadline:
                await asyncio.sleep(.1);s=a.sensorCalibrationStatus
                if s and s.get('sourceStatus') in ('COMPLETE','FAIL'):
                    summary['terminal']=s['sourceStatus'];summary['completed']=s['sourceStatus']=='COMPLETE';break
        else:
            save('motorBefore',await a.getMotorTuning(timeoutMs=5000));save('start',await a.sendAutoTuneRequest(start=True))
            deadline=time.monotonic()+45
            while time.monotonic()<deadline:
                await asyncio.sleep(.1);s=a.calibrationStatus or {}
                if s.get('state') in ('Complete','Failure'):
                    summary['terminal']=s['state'];summary['completed']=s['state']=='Complete';break
            save('motorAfter',await a.getMotorTuning(timeoutMs=5000))
        summary['invalidFrames']=g.decoder.invalidFrames
    except Exception as e:
        save('error',dict(code=getattr(e,'code','ERROR'),message=str(e)));summary['errorCode']=getattr(e,'code','ERROR')
    finally:
        try:await g.close();summary['closed']=g.closed and not g.connected
        except Exception as e:summary['closed']=False;summary['closeErrorCode']=getattr(e,'code','ERROR')
    save('summary',summary);print('SUMMARY',json.dumps(summary),flush=True)
    return 0 if summary['completed'] and summary.get('closed') and not summary.get('errorCode') and summary.get('invalidFrames')==0 else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=ACTIONS)
    sys.exit(asyncio.run(run(parser.parse_args().action)))
