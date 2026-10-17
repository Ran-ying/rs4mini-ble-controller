#!/usr/bin/env python3
"""Pinned offline angle-class audit and handwritten body vectors; never sends DUML."""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS

MODEL='Ldji/midware/data/model/P3/'
A=MODEL+'DataGimbalAngleControl;'
B=MODEL+'DataGimbalSetAngle;'
C=MODEL+'DataGimbalAbsAngleControl;'
BASE='Ldji/sdksharedlib/hardware/abstractions/gimbal/'
ROOT=BASE+'DJIGimbalAbstraction;'


def integer(value,lo,hi):
    if type(value) is not int or not lo<=value<=hi:raise ValueError('explicit bounded integer required')
    return value


def boolean(value):
    if type(value) is not bool:raise ValueError('explicit boolean required')
    return int(value)


def angle14_body(yaw,roll,pitch,*,absolute,yaw_invalid,roll_invalid,pitch_invalid,overtime):
    """Raw source fields, not degrees, safe limits, firmware completion or an SDK."""
    angles=[integer(v,-32768,32767) for v in (yaw,roll,pitch)]
    flag=sum(boolean(v)<<i for i,v in enumerate((absolute,yaw_invalid,roll_invalid,pitch_invalid)))
    return struct.pack('<hhhBB',*angles,flag,integer(overtime,-2147483648,2147483647)&255)


def angle0a_control_flag(*,permission,reference,absolute,yaw_valid,roll_valid,pitch_valid):
    """Handwritten source arithmetic, including each narrowing byte cast."""
    p,r,a,y,ro,pi=[boolean(v) for v in (permission,reference,absolute,yaw_valid,roll_valid,pitch_valid)]
    mode=(p<<1)|r
    value=(((mode<<6)+a)<<5)&255
    for valid,shift in ((y,4),(ro,3),(pi,2)):
        signed=value if value<128 else value-256
        value=((signed+valid)<<shift)&255
    return value


def source_angle_units(value):
    """Finite float32*10, float-to-int truncation then signed-short narrowing."""
    if type(value) not in (float,int) or not math.isfinite(value):raise ValueError('finite source angle required')
    try:
        single=struct.unpack('<f',struct.pack('<f',value))[0]
        scaled=struct.unpack('<f',struct.pack('<f',single*10))[0]
    except (OverflowError,struct.error):raise ValueError('finite float32 multiplication required')
    if not math.isfinite(scaled):raise ValueError('finite float32 multiplication required')
    number=max(-2147483648,min(2147483647,math.trunc(scaled)))
    return (number+32768)%65536-32768


def source_overtime(value):
    """Finite source double path: clamp .1..25.5 then truncate *10."""
    if type(value) not in (float,int) or not math.isfinite(value):raise ValueError('finite source time required')
    return math.trunc(min(25.5,max(.1,value))*10)


def trace(apk,bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    images=[]
    for bank,expected in BANKS.items():
        raw=(bank_dir/('business-%02d-code-restored.dex'%bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('restored bank hash mismatch: %02d'%bank)
        images.append((bank,raw))
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    fingerprints=[];external=[];chain=[];selected={}
    for bank,raw in images:
        classes={c.get_name():c for c in DEX(raw).get_classes()}
        if bank==5:
            owner=BASE+'DJIGimbalHG724Abstraction;'
            while owner in classes and owner.startswith(BASE):
                chain.append(owner);owner=classes[owner].get_superclassname()
            rotate=[owner for owner in chain if any(m.get_name()=='rotate' for m in classes[owner].get_methods())]
            if rotate!=[ROOT]:raise ValueError('rotate inheritance changed')
        for owner,cls in classes.items():
            for m in cls.get_methods():
                if not m.get_code():continue
                ops=[(o.get_name(),o.get_output()) for o in m.get_instructions()]
                if owner not in (A,B) and any(op.startswith('invoke-') and any(x+'->' in text for x in (A,B)) for op,text in ops):
                    external.append(dict(bank=bank,className=owner,method=m.get_name(),descriptor=m.get_descriptor()))
                if bank==5 and (owner in (A,B,C) or (owner==ROOT and m.get_name() in ('rotate','justSendPauseData','getReceiverIdByIndex')) or (owner=='Ldji/midware/util/BytesUtil;' and (m.get_name(),m.get_descriptor()) in [('getBytes','(S)[B'),('getUnsignedBytes','(I)[B')])):
                    fingerprints.append(dict(bank=bank,className=owner,method=m.get_name(),descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest()))
                    selected[(owner,m.get_name(),m.get_descriptor())]=ops
    def take(owner,name,descriptor=None):
        found=[ops for (o,n,d),ops in selected.items() if o==owner and n==name and (descriptor is None or descriptor==d)]
        if len(found)!=1:raise ValueError('ambiguous or missing angle method '+name)
        return found[0]
    def require(ops,token):
        if not any(token in t for _,t in ops):raise ValueError('missing source evidence '+token)
    rotate=take(ROOT,'rotate')
    for token in ('->ABSOLUTE_ANGLE ','->RELATIVE_ANGLE ','->justSendPauseData()V',C+'->start()V','CallbackUtils;->onSuccess(', '4627870829588250624','4591870180066957722','4621819117588971520'):
        require(rotate,token)
    for axis in ('Pitch','Roll','Yaw'):
        require(rotate,C+'->set'+axis+'(S)');require(rotate,C+'->set'+axis+'Invalid(Z)')
    if any(A+'->' in t or B+'->' in t for _,t in rotate):raise ValueError('base rotate now also references 0A')
    require(take(ROOT,'justSendPauseData'),'DataSingleSendAppStateForStabilization$GimbalState;->START ')
    for owner,command in ((A,'AngleControl'),(B,'SetAngle'),(C,'AbsAngleControl')):
        for (o,n,d),ops in selected.items():
            if o==owner and n=='start':
                require(ops,'CmdIdGimbal$CmdIdType;->'+command+' ');require(ops,'DataConfig$NEEDACK;->YES ')
    require(take(C,'doPack'),'v0, 8')
    # Raw doubles are decoded independently rather than inferred from display text.
    doubles=[struct.unpack('<d',struct.pack('<Q',v))[0] for v in (4627870829588250624,4591870180066957722,4621819117588971520)]
    if doubles!=[25.5,.1,10.0]:raise ValueError('source time constants changed')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(k):v for k,v in BANKS.items()},
        appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,
        hg724Inheritance=chain,rotateImplementationOwner=ROOT,
        angle14=dict(bodyBytes=8,axisOrder=['yaw','roll','pitch'],signedLittleEndian16=True,controlModeBit=0,invalidAxisBits=dict(yaw=1,roll=2,pitch=3),timeClamp=[.1,25.5],timeMultiplier=10,absoluteAndRelativeShareCommand=True,sourceRequiresCapabilityChecks=True,sourcePauseState='START',sourceCallsNoCallbackStart=True,sourceReportsSuccessWithoutWaitingForAck=True,firmwareCompletionVerified=False,referenceFrameVerified=False,receiverRoutingVerified=False,capabilityInitializationAudited=False),
        angle0a=dict(twoDistinctClasses=True,externalDirectCallers=external,hg724CallPathEstablished=False,negativeSearchProvesUnsupported=False,monitorUvcExcludedFromScope=True,controlBodyBytes=10,setAngleBodyBytes=10,controlDefaultDeviation=300,setAngleDefaultError=10,setAngleDefaultReference=0,setAngleDefaultPayloadTimeout=2,controlDefaultFlag=angle0a_control_flag(permission=False,reference=False,absolute=False,yaw_valid=True,roll_valid=True,pitch_valid=True),flagArithmeticIsNotConventionalBitmask=True,transportTimeoutIsNotPayloadTimeout=True),
        vectors=[dict(name='14-yaw-only-absolute',bodyHex=angle14_body(123,0,0,absolute=True,yaw_invalid=False,roll_invalid=True,pitch_invalid=True,overtime=10).hex()),dict(name='14-relative-signed',bodyHex=angle14_body(-123,45,-67,absolute=False,yaw_invalid=False,roll_invalid=False,pitch_invalid=False,overtime=255).hex())],
        remaining=['Resolve model capabilities, receiver routing and stabilization pause/resume before exposing current-App angle SDK.', 'Audit response errors, completion, cancellation, release and physical reference frame.', 'No hardware verification; banks 1/7, protected/dynamic paths remain outside scan.'],methods=fingerprints)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();result=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('%d method fingerprints; no vendor execution or BLE.'%len(result['methods']))

if __name__=='__main__':main()
