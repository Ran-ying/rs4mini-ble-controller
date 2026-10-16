#!/usr/bin/env python3
"""Trace the inherited system_calc calibration path without executing App code."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_command_audit import DERIVED_SHA256
from ronin_settings_trace import BASE, unique_record
from ronin_balance_trace import ordinal_enum

OWNER=BASE+'DJIGimbalRoninBaseAbstraction;'
MODEL='Ldji/midware/data/model/P3/'


def command_slot(operations, wanted):
    registers,found={},None
    for op,text in operations:
        if op.startswith('const-string'):
            reg,value=text.split(', ',1);registers[reg]=value
        elif op in ('const/4','const/16','const'):
            reg,value=text.split(', ',1);registers[reg]=int(value)
        elif op=='new-array':
            dest,size,kind=text.split(', ')
            if kind!='[Ljava/lang/String;' or type(registers.get(size)) is not int:raise ValueError('unsupported source array')
            registers[dest]=[None]*registers[size]
        elif op=='aput-object':
            value,array,index=text.split(', ');target=registers.get(array);offset=registers.get(index)
            if not isinstance(target,list) or type(offset) is not int or not 0<=offset<len(target) or target[offset] is not None or not isinstance(registers.get(value),str):
                raise ValueError('unresolved/duplicate source array slot')
            target[offset]=registers[value]
        elif op=='sput-object' and OWNER+'->RONIN_COMMAND ' in text:
            array=registers.get(text.split(', ')[0])
            if not isinstance(array,list) or not 0<=wanted<len(array):raise ValueError('source array slot missing')
            found=array[wanted]
        elif op=='return-void':pass
        else:raise ValueError('unsupported source array instruction: '+op)
    if not isinstance(found,str):raise ValueError('unresolved source command name')
    return found


def trace(apk,dex_path):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    raw=dex_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=DERIVED_SHA256:raise ValueError('restoration view hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    classes={c.get_name():c for c in DEX(raw).get_classes()}
    selected=[]
    def method(owner,name,descriptor=None):
        matches=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(matches)!=1 or not matches[0].get_code():raise ValueError('missing readable source method')
        selected.append(matches[0]);return matches[0]
    def ops(m):return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    def require(m,token):
        if not any(token in text for _,text in ops(m)):raise ValueError('missing source reference: '+token)
    initializer=method(OWNER,'<clinit>');name=command_slot(ops(initializer),22)
    if name!='system_calc':raise ValueError('system calibration parameter changed')
    with zipfile.ZipFile(str(apk)) as z:resource=z.read('res/DB.json')
    record=unique_record(json.loads(resource),name)
    if (record['index'],record['size'],record['typeID'],record['minValue'],record['maxValue'])!=(36,1,0,0,1):raise ValueError('system calibration metadata changed')
    chain=[];clsname=BASE+'DJIGimbalHG724Abstraction;'
    while clsname.startswith(BASE):
        cls=classes[clsname];chain.append(clsname)
        if clsname!=OWNER and any(m.get_name()=='startGimbalAutoCalibration' for m in cls.get_methods()):raise ValueError('unexpected model calibration override')
        if clsname==OWNER:break
        clsname=cls.get_superclassname()
    if chain!=[BASE+'DJIGimbal'+n+'Abstraction;' for n in ('HG724','HG702','Ronin2','RoninBase')]:raise ValueError('model calibration chain changed')
    start=method(OWNER,'startGimbalAutoCalibration')
    for token in ('DataGimbalSetUserParams;->setInfo(',OWNER+'->RONIN_COMMAND '):require(start,token)
    if ('const/16','v2, 22') not in ops(start) or ('const/4','v2, 1') not in ops(start):raise ValueError('system calibration start changed')
    poll=method(OWNER[:-1]+'$6;','run');require(poll,'DataGimbalGetUserParams;->setInfos(')
    if ('const/16','v3, 22') not in ops(poll):raise ValueError('system calibration polling key changed')
    callback=method(OWNER[:-1]+'$6$1;','onSuccess');require(callback,'CalibrationState;->values()');require(callback,'ParamInfo;->value ')
    stateowner='Ldji/internal/gimbal/CalibrationState;'
    states=ordinal_enum(ops(method(stateowner,'<clinit>')),stateowner)
    if states!=[dict(name=n,ordinal=i) for i,n in enumerate(('DEFAULT','START','FAIL','SUCCESS'))]:raise ValueError('system calibration enum changed')
    method(OWNER[:-1]+'$10;','<clinit>');method(OWNER[:-1]+'$7;','onSuccess')
    method(OWNER,'refreshCalibrationState');method(OWNER,'updateCalibrationPushInfo')
    for model,names in [('DataGimbalSetUserParams',('doPack','start')),('DataGimbalGetUserParams',('doPack','setRecData','start'))]:
        for name in names:method(MODEL+model+';',name)
    methods=[dict(className=m.get_class_name(),method=m.get_name(),descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest()) for m in selected]
    return dict(schemaVersion=1,apkSha256=APK_SHA256,derivedSha256=DERIVED_SHA256,resourceSha256=hashlib.sha256(resource).hexdigest(),
                appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,inheritanceOnlyDoesNotProveFirmwareSupport=True,
                inheritance=chain,parameter=record,states=states,methods=methods,
                sourceFacts=dict(startCommand='04:0F',startValue=1,startPayloadHex='240101',readCommand='04:10',readPayloadHex='24',
                                 sourceArraySlot=22,statusIsEnumOrdinal=True,statusNotClampedToWriteRange=True,
                                 distinctFromAutoTune6AAnd6E=True,horizontalCalibrationIdentityVerified=False,abortCommandVerified=False))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','dex','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.dex);a.output.write_text(json.dumps(r,indent=2)+'\n')
    print('%d system calibration method fingerprints; no App/hardware execution.'%len(r['methods']))

if __name__=='__main__':main()
