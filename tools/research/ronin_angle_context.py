#!/usr/bin/env python3
"""Audit angle capability overrides and packet context without vendor execution."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_command_audit import DERIVED_SHA256
from ronin_angles_trace import BASE,ROOT,MODEL,C
from ronin_model_trace import enum_entry
from ronin_subscription_trace import constructor_records

CAP='Ldji/common/gimbal/CapabilityKey;'
AXES={'ADJUST_PITCH','ADJUST_ROLL','ADJUST_YAW'}
PAUSE=MODEL+'DataSingleSendAppStateForStabilization;'
DB='Ldji/midware/data/manager/P3/DataBase;'
PACK='Ldji/midware/data/packages/P3/SendPack;'


def axis_updates(operations):
    """Recognize literal capability declarations, not a general bytecode evaluator."""
    registers={};pending=None;result=[]
    for op,text in operations:
        if op.startswith(('if-','goto')) or 'switch' in op:raise ValueError('conditional capability declaration')
        args=text.split(', ')
        if op in ('const/4','const/16','const'):
            registers[args[0]]=int(args[1]);pending=None
        elif op=='sget-object':
            match=re.fullmatch(r'v\d+, '+re.escape(CAP)+r'->(\w+) '+re.escape(CAP),text)
            registers[args[0]]=match.group(1) if match else None;pending=None
        elif op in ('move','move-object','move/from16','move-object/from16'):
            registers[args[0]]=registers.get(args[1]);pending=None
        elif op=='move-result-object':
            registers[args[0]]=pending;pending=None
        elif op.startswith('invoke-'):
            if 'Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;' in text:
                pending=registers.get(args[0])
            else:
                values=[registers.get(x) for x in args[:-1]]
                if '->addMinMaxToCapability('+CAP+' Ljava/lang/Number; Ljava/lang/Number;)V' in text and len(values)==4 and values[1] in AXES:
                    if any(type(v) is not int for v in values[2:]):raise ValueError('unresolved angle range')
                    result.append(dict(key=values[1],supported=True,minimum=values[2],maximum=values[3]))
                elif '->addIsSupportedToCapability('+CAP+' Z)V' in text and len(values)==3 and values[1] in AXES:
                    if values[2] not in (0,1) or type(values[2]) is not int:raise ValueError('unresolved support flag')
                    result.append(dict(key=values[1],supported=bool(values[2]),minimum=0,maximum=0))
                pending=None
        elif op.startswith(('return','iput','sput','aput')) or op=='nop':pending=None
        else:
            # Unknown destination cannot retain a previous literal, including wide writes.
            dest=re.match(r'v(\d+)',text)
            if dest:
                registers['v'+dest.group(1)]=None
                if 'wide' in op:registers['v'+str(int(dest.group(1))+1)]=None
            pending=None
    return result


def protocol_gimbal_id(index):
    if type(index) is not int or not -2147483648<=index<=2147483647:raise ValueError('source int index required')
    return 2 if index==1 else 0


def trace(apk,sdk):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    raw=sdk.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=DERIVED_SHA256:raise ValueError('SDK hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    classes={c.get_name():c for c in DEX(raw).get_classes()};methods={}
    def take(owner,name,descriptor=None):
        found=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or descriptor==m.get_descriptor())]
        if len(found)!=1 or not found[0].get_code():raise ValueError('missing or ambiguous context method '+owner+name)
        m=found[0];methods[(owner,name,m.get_descriptor())]=dict(className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest())
        return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    def require(ops,token):
        if not any(token in text for _,text in ops):raise ValueError('missing angle context '+token)
    chain=[];owner=BASE+'DJIGimbalHG724Abstraction;'
    while owner in classes and owner.startswith(BASE):chain.append(owner);owner=classes[owner].get_superclassname()
    overrides=[];effective={}
    for owner in reversed(chain):
        if not any(m.get_name()=='initGimbalCapability' for m in classes[owner].get_methods()):continue
        ops=take(owner,'initGimbalCapability')
        if owner!=ROOT:require(ops,'->initGimbalCapability()V')
        updates=axis_updates(ops)
        for update in updates:effective[update['key']]=dict(update,declaredBy=owner)
        overrides.append(dict(className=owner,axisUpdates=updates))
    expected={'ADJUST_PITCH':(-90,90),'ADJUST_YAW':(-180,180),'ADJUST_ROLL':(-30,30)}
    if {k:(v['minimum'],v['maximum']) for k,v in effective.items()}!=expected or not all(v['supported'] for v in effective.values()):raise ValueError('effective angle capabilities changed')
    helper=take(ROOT,'addMinMaxToCapability','('+CAP+' Ljava/lang/Number; Ljava/lang/Number;)V')
    if ('const/4','v1, 1') not in helper:raise ValueError('minmax support flag changed')
    for token in ('DJIParamMinMaxCapability;-><init>(Z Ljava/lang/Number; Ljava/lang/Number;)V','Ljava/util/Map;->put('):require(helper,token)
    take(ROOT,'addIsSupportedToCapability');take(ROOT,'addDefaultToCapability');take(ROOT,'init');take(ROOT,'getReceiverIdByIndex');take(ROOT,'justSendPauseData');take(ROOT,'rotate')
    mapping=take('Ldji/midware/util/DoubleCameraSupportUtil;','getGimbalIdInProtocol')
    if mapping!=[('const/4','v0, 1'),('if-eq','v1, v0, +004h'),('const/4','v1, 0'),('return','v1'),('const/4','v1, 2'),('return','v1')]:raise ValueError('gimbal index mapping changed')
    setter=take(DB,'setReceiverId','(I)Ldji/midware/data/manager/P3/DataBase;');require(setter,'->receiverID I')
    for desc in ('('+PACK+')V','('+PACK+' Ldji/midware/interfaces/DJIDataCallBack;)V','('+PACK+' Ldji/midware/interfaces/DJIDataCallBack; Z)V'):
        take(DB,'start',desc)
    preprocess=take(DB,'preprocessPack');require(preprocess,PACK+'->receiverId I')
    take(PACK,'doPack');take(C,'start','()V')
    init=take(PAUSE,'<init>')
    for subtype in ('GimbalState','CameraState'):require(init,PAUSE[:-1]+'$'+subtype+';->NORMAL ')
    take(PAUSE,'doPack')
    start=take(PAUSE,'start','()V');callback=take(PAUSE,'start','(Ldji/midware/interfaces/DJIDataCallBack;)V')
    for token in ('->SINGLE ','v1, 7','->EYE ','CmdIdEYE$CmdIdType;->AppState '):require(start,token)
    require(callback,'CmdIdEYE$CmdIdType;->Stabilization ')
    gimbal=PAUSE[:-1]+'$GimbalState;';camera=PAUSE[:-1]+'$CameraState;'
    state=enum_entry(take(gimbal,'<clinit>'),gimbal,'START');normal=enum_entry(take(camera,'<clinit>'),camera,'NORMAL')
    if (state['value'],normal['value'])!=(1,0):raise ValueError('pause enum values changed')
    eye='Ldji/midware/data/config/P3/CmdIdEYE$CmdIdType;'
    eye_entries=constructor_records(take(eye,'<clinit>'),eye)
    eye_commands={name:eye_entries[name]['arguments'][2] for name in ('AppState','Stabilization')}
    device='Ldji/midware/data/config/P3/DeviceType;'
    single=constructor_records(take(device,'<clinit>'),device)['SINGLE']['arguments'][2]
    return dict(schemaVersion=1,apkSha256=APK_SHA256,sdkSha256=DERIVED_SHA256,appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,
        hg724Inheritance=chain,capabilityDeclarations=overrides,effectiveSourceCapabilities=effective,sourcePolicyIsMechanicalSafeRange=False,dynamicCapabilityChangesExcluded=False,
        routing=dict(sourceIndexOneMapsToId=2,sourceOtherIntIndexesMapToId=0,sourceStoredIdOverridesPackUnlessMinusOne=True,bleAddressVerified=False,deviceIndexVerified=False,encryptionPathAudited=False),
        pause=dict(sourceReceiverType='SINGLE',sourceReceiverTypeValue=single,sourceReceiverId=7,sourceCommandValues=eye_commands,sourceCommandSet='EYE',noCallbackCommand='AppState',callbackCommand='Stabilization',overloadsAreDifferentCommands=True,sourceGimbalStartValue=state['value'],sourceDefaultCameraValue=normal['value'],sourceNoCallbackBodyHex='0100',physicalPauseVerified=False,requiredForDirectBleVerified=False,resumeProtocolVerified=False,cameraControlAdded=False),
        remaining=['Verify live device index/address, reference frame and physical acceptance.', 'Determine direct-BLE applicability of separate EYE/SINGLE dependency without adding excluded camera APIs.', 'Audit acknowledgement errors, firmware completion, cancellation and release before current-App angle SDK.'],methods=list(methods.values()))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','sdk','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();result=trace(a.apk,a.sdk);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('%d context method fingerprints; no SDK/BLE execution.'%len(result['methods']))

if __name__=='__main__':main()
