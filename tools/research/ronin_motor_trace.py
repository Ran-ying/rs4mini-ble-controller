#!/usr/bin/env python3
"""Trace named motor tuning through current-App code, without running it."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_command_audit import DERIVED_SHA256
from ronin_settings_trace import named_keys,unique_record,OWNER
from ronin_model_trace import enum_entry

BASE='Ldji/sdksharedlib/hardware/abstractions/gimbal/'
MODEL='Ldji/midware/data/model/P3/'
GROUPS=(('Stiffness','STIFFNESS','stiffness'),('Strength','STRENGTH','strength'),('GyroFiltering','FILTERING','gyroFiltering'),('PreControl','PRECONTROL','preControl'))


def trace(apk,dex_path):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    raw=dex_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=DERIVED_SHA256:raise ValueError('restored view hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    classes={c.get_name():c for c in DEX(raw).get_classes()}
    enum=next(m for m in classes[OWNER].get_methods() if m.get_name()=='<clinit>')
    keys=named_keys([(o.get_name(),o.get_output()) for o in enum.get_instructions()])
    with zipfile.ZipFile(str(apk)) as z:resource=z.read('res/DB.json')
    records=json.loads(resource)
    selected=[];wanted=set()
    abstraction=classes[BASE+'DJIGimbalRonin2Abstraction;']
    for group,(suffix,prefix,parameter) in enumerate(GROUPS):
        for axis_index,axis in enumerate(('Pitch','Roll','Yaw')):
            method_name='setMotorControl'+suffix+'On'+axis;wanted.add(method_name)
            method=next(m for m in abstraction.get_methods() if m.get_name()==method_name)
            outputs=[o.get_output() for o in method.get_instructions()]
            key=prefix+'_'+axis.upper()
            if not any('BaseCommand;->'+key+' ' in text for text in outputs) or not any('->setRonin2MotorParam(' in text for text in outputs):raise ValueError('motor setter path changed')
            if keys[key]['getter']!=MODEL+'DataGimbalRoninGetUserParams;':raise ValueError('wrong motor getter namespace')
            record=unique_record(records,keys[key]['name'])
            if record['index']!=group*3+axis_index or record['size']!=1 or record['typeID']!=0 or record['minValue']!=(5,1,0,0)[group] or record['maxValue']!=100:raise ValueError('motor metadata changed')
            selected.append(dict(axis=axis.lower(),parameter=parameter,key=key,setter=method_name,record=record))
    for cls in ('DJIGimbalHG724Abstraction;','DJIGimbalHG702Abstraction;'):
        if any(m.get_name() in wanted for m in classes[BASE+cls].get_methods()):raise ValueError('unexpected motor override')
    targets={BASE+'DJIGimbalRonin2Abstraction;':wanted|{'setRonin2MotorParam'},
             MODEL+'DataGimbalRoninSetUserParams;':{'setInfo','doPack','setRecData','start'},
             MODEL+'DataGimbalRoninGetUserParams;':{'doPack','setRecData','start'}}
    targets.update({MODEL+'DataFlycGetParamInfo$TypeId;':{'<clinit>'}, MODEL+'DataGimbalRoninSetUserParams$1;':{'<clinit>'},
                    'Ldji/midware/util/BytesUtil;':{'getBytes'},BASE+'DJIGimbalAbstraction;':{'checkValueValid'}})
    type_method=next(m for m in classes[MODEL+'DataFlycGetParamInfo$TypeId;'].get_methods() if m.get_name()=='<clinit>')
    type_fact=enum_entry([(o.get_name(),o.get_output()) for o in type_method.get_instructions()],MODEL+'DataFlycGetParamInfo$TypeId;','INT08U')
    if type_fact['value']!=0 or type_fact['ordinal']!=0:raise ValueError('source motor scalar type changed')
    switch_method=next(m for m in classes[MODEL+'DataGimbalRoninSetUserParams$1;'].get_methods() if m.get_name()=='<clinit>')
    switch_ops=[(o.get_name(),o.get_output()) for o in switch_method.get_instructions()]
    marker=next(i for i,(op,text) in enumerate(switch_ops) if '->INT08U ' in text)
    if switch_ops[marker+3]!=('const/4','v2, 4') or switch_ops[marker+4]!=('aput','v2, v0, v1'):raise ValueError('INT08U packing case changed')
    pack_method=next(m for m in classes[MODEL+'DataGimbalRoninSetUserParams;'].get_methods() if m.get_name()=='doPack')
    instructions={};offset=0;scalar_targets=[]
    for op in pack_method.get_instructions():instructions[offset]=op;offset+=op.get_length()
    for offset,op in instructions.items():
        if op.get_name()!='packed-switch':continue
        payload=instructions[offset+2*op.get_ref_off()]
        destination=offset+2*payload.get_targets()[payload.get_values().index(4)]
        segment=[o.get_output() for address,o in instructions.items() if destination<=address<destination+24]
        if not any('->intValue()I' in s for s in segment) or not any('BytesUtil;->getBytes(I)[B' in s for s in segment):raise ValueError('motor scalar conversion changed')
        scalar_targets.append(destination)
    if len(scalar_targets)!=2:raise ValueError('both scalar/array motor packing branches must be covered')
    byte_method=next(m for m in classes['Ldji/midware/util/BytesUtil;'].get_methods() if m.get_name()=='getBytes' and m.get_descriptor()=='(I)[B')
    byte_ops=[(o.get_name(),o.get_output()) for o in byte_method.get_instructions()]
    if byte_ops[0]!=('and-int/lit16','v0, v5, 255') or ('const/4','v4, 0') not in byte_ops or ('aput-byte','v0, v3, v4') not in byte_ops:raise ValueError('motor low-byte conversion changed')
    methods=[]
    for name,names in targets.items():
        for m in classes[name].get_methods():
            if m.get_name() not in names or not m.get_code():continue
            if name=='Ldji/midware/util/BytesUtil;' and m.get_descriptor()!='(I)[B':continue
            ops=[o.get_output() for o in m.get_instructions()]
            if m.get_name()=='setRonin2MotorParam' and not any('DataGimbalRoninSetUserParams;' in s for s in ops):raise ValueError('wrong motor write path')
            if m.get_name()=='start' and not any('DataConfig$NEEDACK;->YES ' in s for s in ops):raise ValueError('motor ACK policy changed')
            methods.append(dict(className=name,method=m.get_name(),descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest()))
    return dict(schemaVersion=1,apkSha256=APK_SHA256,derivedSha256=DERIVED_SHA256,resourcePath='res/DB.json',resourceSha256=hashlib.sha256(resource).hexdigest(),
                appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,parameterNamesSafeToInferFromWireIndex=False,
                sourceFacts=dict(writeCommand='04:31',readCommand='04:32',acknowledgementRequested=True,recordWidthsFromNamedMetadata=True,
                                 headerByteNotInterpretedAsWidth=True,namespaceDistinctFromUserParameters=True,sourceRangesAreNotMechanicalSafetyLimits=True),
                scalarEncoding=dict(type=type_fact,switchCase=4,targets=scalar_targets,lowByteFirst=True),parameters=selected,methods=methods)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk',type=Path,required=True);parser.add_argument('--dex',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=trace(args.apk,args.dex);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print('%d named motor records, %d method fingerprints; no vendor code executed.'%(len(report['parameters']),len(report['methods'])))


if __name__=='__main__':main()
