#!/usr/bin/env python3
"""Audit named follow/RC numeric paths and separate create-input packets offline."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_command_audit import DERIVED_SHA256
from ronin_code_banks import UI_BANK_SHA256
from ronin_settings_trace import BASE,OWNER,named_keys,unique_record
from ronin_model_trace import enum_entry
MODEL='Ldji/midware/data/model/P3/'
SETTING=BASE+'DJIGimbalAbstraction$SettingParamCmd;'


def enum_names(operations,owner):
    registers,result={},{}
    for op,text in operations:
        if op.startswith('const-string'):
            reg,value=text.split(', ',1);registers[reg]=value
        elif op in ('const/4','const/16','const'):
            reg,value=text.split(', ',1);registers[reg]=int(value)
        elif op.startswith('invoke-direct') and owner+'-><init>(Ljava/lang/String; I Ljava/lang/String;)V' in text:
            regs=re.findall(r'v\d+',text.split(', '+owner)[0])
            if len(regs)!=4:raise ValueError('unsupported string-key enum constructor')
            key,value=registers.get(regs[1]),registers.get(regs[3])
            if not isinstance(key,str) or not isinstance(value,str) or key in result:raise ValueError('unresolved/duplicate string-key enum')
            result[key]=value
        elif op in ('new-instance','move-result-object'):registers[text.split(', ')[0]]=None
        elif op.startswith(('sput-object','invoke-static')) or op=='return-void':pass
        else:raise ValueError('unsupported string-key enum instruction: '+op)
    return result


def cache_pairs(operations):
    """Only unconditional adjacent literal/enum/map-put triples before control flow."""
    result={}
    for i,(op,text) in enumerate(operations):
        if op.startswith(('if-','goto')) or 'switch' in op:break
        if not op.startswith('const-string') or i+2>=len(operations):continue
        op2,text2=operations[i+1];op3,text3=operations[i+2]
        if op2!='sget-object' or OWNER+'->' not in text2 or op3!='invoke-interface' or 'Map;->put(' not in text3:continue
        args=re.findall(r'v\d+',text3.split(', Ljava/util/Map;')[0])
        if len(args)!=3 or args[1:]!=[text.split(', ')[0],text2.split(', ')[0]]:continue
        key=text.split(', ',1)[1];value=text2.split(OWNER+'->',1)[1].split(' ')[0]
        if key in result:raise ValueError('duplicate cache-key mapping')
        result[key]=value
    return result


def trace(apk,sdk_path,ui_path):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    raw=sdk_path.read_bytes();uiraw=ui_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=DERIVED_SHA256 or hashlib.sha256(uiraw).hexdigest()!=UI_BANK_SHA256:raise ValueError('pinned restoration hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    sdk={c.get_name():c for c in DEX(raw).get_classes()};ui={c.get_name():c for c in DEX(uiraw).get_classes()};methods={}
    def take(classes,owner,name,descriptor=None):
        choices=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(choices)!=1 or not choices[0].get_code():raise ValueError('expected one readable method '+owner+name)
        m=choices[0];methods[(owner,name,m.get_descriptor())]=dict(bank='sdk' if classes is sdk else 'ui',className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());return m
    def ops(m):return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    def require(m,token):
        if not any(token in text for _,text in ops(m)):raise ValueError('missing source reference '+token)
    keys=named_keys(ops(take(sdk,OWNER,'<clinit>')))
    strings=enum_names(ops(take(sdk,SETTING,'<clinit>')),SETTING)
    mappings=cache_pairs(ops(take(sdk,BASE+'DJIGimbalRonin2Abstraction;','initCommandCapabilityMap')))
    constructor=take(sdk,OWNER,'<init>','(Ljava/lang/String; I Ljava/lang/String;)V')
    if ('const-class','v1, '+MODEL+'DataGimbalGetUserParams;') not in ops(constructor):raise ValueError('default getter class changed')
    require(constructor,'->mPushClazz ')
    with zipfile.ZipFile(str(apk)) as z:resource=z.read('res/DB.json')
    records=json.loads(resource);selected=[]
    chain=[];owner=BASE+'DJIGimbalHG724Abstraction;'
    while owner in sdk and owner.startswith(BASE):
        chain.append(owner);owner=sdk[owner].get_superclassname()
    def resolved_setter(name,descriptor):
        for owner in chain:
            if any(m.get_name()==name and m.get_descriptor()==descriptor for m in sdk[owner].get_methods()):return owner
        raise ValueError('unresolved inherited setter')
    axes=('pitch','roll','yaw')
    groups=[('follow','speed','SMOOTH_TRACK_SPEED',(3,12,2),2,1,1,100),('follow','acceleration','SMOOTH_TRACK_ACCELERATION',(15,16,14),2,1,1,100),
            ('follow','deadZone','SMOOTH_TRACK_DEADBAND',(5,13,4),2,1,0,100),('rc','speed','CONTROLLER_MAX_SPEED',(42,43,41),2,1,0,100),
            ('rc','deadZone','CONTROLLER_DEADBAND',(27,40,26),1,0,0,100),('rc','smoothing','CONTROLLER_SMOOTHING',(9,39,8),2,1,0,30)]
    for domain,parameter,prefix,indices,size,type_id,minimum,maximum in groups:
        for axis,index in zip(axes,indices):
            key=prefix+'_'+axis.upper();entry=keys[key];record=unique_record(records,entry['name'])
            if (record['index'],record['size'],record['typeID'],record['minValue'],record['maxValue'])!=(index,size,type_id,minimum,maximum):raise ValueError('numeric metadata changed '+key)
            if entry['getter'] not in (None,MODEL+'DataGimbalGetUserParams;'):raise ValueError('wrong numeric getter')
            if domain=='rc':
                stem={'speed':'ControllerMaxSpeed','deadZone':'ControllerDeadband','smoothing':'ControllerSmoothing'}[parameter]
                setter=take(sdk,BASE+'DJIGimbalRonin2Abstraction;','set'+stem+'On'+axis.title())
                cache_key=('ControllerMaxSpeed'+axis.title()) if parameter=='speed' else axis.title()+('ControllerDeadband' if parameter=='deadZone' else 'ControllerSmoothingFactor')
                if mappings.get(cache_key)!=key:raise ValueError('numeric cache-key route changed')
                require(setter,cache_key);require(setter,'->setRonin2CommonUserParam(')
            elif axis=='roll':
                stem={'speed':'Speed','acceleration':'Accel','deadZone':'Deadband'}[parameter]
                setter=take(sdk,BASE+'DJIGimbalRonin2Abstraction;','setSmoothTrack'+stem+'Roll')
                require(setter,OWNER+'->'+key+' ')
            else:
                stem={'speed':'Speed','acceleration':'Acceleration','deadZone':'Deadband'}[parameter]
                setter=take(sdk,BASE+'DJIGimbalAircraftAbstraction;','setSmoothTrack'+stem+'On'+axis.title())
                legacy='SMOOTH_TRACK_'+axis.upper()+'_'+{'speed':'SPEED','acceleration':'ACCEL','deadZone':'DEADBAND'}[parameter]
                if strings.get(legacy)!=record['name']:raise ValueError('generic inherited setter string changed')
                require(setter,SETTING+'->'+legacy+' ');require(setter,'->isCustomAdvancedSettingProfile()Z')
            if resolved_setter(setter.get_name(),setter.get_descriptor())!=setter.get_class_name():raise ValueError('numeric method override path changed')
            selected.append(dict(record,domain=domain,parameter=parameter,axis=axis,baseCommand=key,resolvedGetter=MODEL+'DataGimbalGetUserParams;',sourceSetter=setter.get_name(),sourceSetterOwner=setter.get_class_name(),writeCommand='04:0F'))
    take(sdk,BASE+'DJIGimbalAbstraction;','setParam')
    take(sdk,BASE+'DJIGimbalAbstraction;','isCustomAdvancedSettingProfile')
    take(sdk,SETTING,'getCmdString')
    take(sdk,BASE+'DJIGimbalRonin2Abstraction;','setRonin2CommonUserParam')
    typeowner=MODEL+'DataFlycGetParamInfo$TypeId;';typem=take(sdk,typeowner,'<clinit>')
    types=[enum_entry(ops(typem),typeowner,n) for n in ('INT08U','INT16U')]
    if [r['value'] for r in types]!=[0,1]:raise ValueError('unsigned numeric type IDs changed')
    switch=ops(take(sdk,MODEL+'DataGimbalSetUserParams$1;','<clinit>'))
    for name,case in [('INT08U',4),('INT16U',5)]:
        marker=next(i for i,(_,text) in enumerate(switch) if '->'+name+' ' in text)
        if switch[marker+3]!=('const/4','v2, '+str(case)):raise ValueError('numeric packing case changed')
    pack=take(sdk,MODEL+'DataGimbalSetUserParams;','doPack');instructions={};off=0;targets=[]
    for o in pack.get_instructions():instructions[off]=o;off+=o.get_length()
    for off,o in instructions.items():
        if o.get_name()!='packed-switch':continue
        payload=instructions[off+2*o.get_ref_off()]
        for case in (4,5):
            destination=off+2*payload.get_targets()[payload.get_values().index(case)]
            texts=[i.get_output() for pos,i in instructions.items() if destination<=pos<destination+24]
            if not any('->intValue()I' in text for text in texts) or not any('BytesUtil;->getBytes(I)[B' in text for text in texts):raise ValueError('unsigned scalar conversion changed')
            targets.append(dict(switchOffset=off,case=case,target=destination))
    if len(targets)!=4:raise ValueError('both single/array packing paths required')
    byte_method=take(sdk,'Ldji/midware/util/BytesUtil;','getBytes','(I)[B');byte_ops=ops(byte_method)
    for expected in [('and-int/lit16','v0, v5, 255'),('const','v1, 65280'),('and-int/2addr','v1, v5'),('shr-int/lit8','v1, v1, 8'),('const/4','v0, 1'),('aput-byte','v0, v3, v4'),('aput-byte','v1, v3, v0')]:
        if expected not in byte_ops:raise ValueError('little-endian low two bytes changed')
    for model,names in [('DataGimbalSetUserParams',('start',)),('DataGimbalGetUserParams',('doPack','setRecData','start'))]:
        for name in names:take(sdk,MODEL+model+';',name)
    ui_owner='Lcom/dji/ronin/viewModel/CreateVideoViewModel;'
    create=take(ui,ui_owner,'performParamSet','(Ldji/midware/ronin2/Ronin2GimbalParamsManager$BaseCommand; I)V')
    for token in ('->GIMBAL_INPUT_SOURCE ','->setIndexs(','->setValues('):require(create,token)
    if ('const/4','v1, 2') not in ops(create):raise ValueError('create input-source value changed')
    take(ui,ui_owner,'supportProfileStandalone')
    create_records=[unique_record(records,keys['GIMBAL_CREATE_'+kind+'_'+axis.upper()]['name']) for kind in ('SMOOTH','MAX_SPEED') for axis in axes]
    for row,index in zip(create_records,(77,76,78,80,79,81)):
        if (row['index'],row['size'],row['typeID'])!=(index,2,0):raise ValueError('distinct create metadata changed')
    for axis in axes:
        for suffix,key_kind in [('Smooth','SMOOTH'),('Speed','MAX_SPEED')]:
            caller=take(ui,ui_owner,'perform'+axis.title()+suffix+'Set')
            require(caller,'->supportProfileStandalone()Z')
            require(caller,OWNER+'->GIMBAL_CREATE_'+key_kind+'_'+axis.upper()+' ')
    input_record=unique_record(records,keys['GIMBAL_INPUT_SOURCE']['name'])
    if (input_record['index'],input_record['size'],input_record['typeID'])!=(72,1,0):raise ValueError('input-source metadata changed')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,sdkDerivedSha256=DERIVED_SHA256,uiDerivedSha256=UI_BANK_SHA256,
                appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,sourceRangesAreNotMechanicalSafetyLimits=True,
                inheritance=chain,inheritanceOnlyDoesNotProveFirmwareSupport=True,
                parameters=selected,unsignedTypes=types,packingTargets=targets,methods=list(methods.values()),
                distinctCreatePath=dict(parameters=create_records,inputSource=input_record,inputValue=2,sourceCombinesInputAndValueInOneRequest=True,automaticSelectionNotAllowed=True),
                sourceFacts=dict(readCommand='04:10',writeCommand='04:0F',defaultGetterIsCommonUserParams=True,littleEndianLowBytes=True,
                                 inheritedFollowPitchYawHaveCustomAdvancedSettingProfileCheck=True,sourceBoundsDoNotProveActivePreset=True,
                                 researchToolProvidesSdkInterface=False))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','sdk','ui','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.sdk,a.ui);a.output.write_text(json.dumps(r,indent=2)+'\n')
    print('%d ordinary numeric records, %d source methods; create-input pair remains separate; no App executed.'%(len(r['parameters']),len(r['methods'])))

if __name__=='__main__':main()
