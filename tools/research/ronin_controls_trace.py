#!/usr/bin/env python3
"""Audit fine tune, handle and reset source paths; no App or hardware execution."""
import argparse,hashlib,json,re
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_command_audit import DERIVED_SHA256
from ronin_code_banks import UI_BANK_SHA256
from ronin_settings_trace import BASE
from ronin_subscription_trace import constructor_records
from ronin_controls_payloads import HANDLE_FIELDS,fine_tune_payload,handle_patch_payload,hg724_reset_payload
MODEL='Ldji/midware/data/model/P3/'


def handle_getter_context(operations):
    registers={}
    for i,(op,text) in enumerate(operations):
        if op in ('const/4','const/16','const'):
            reg,value=text.split(', ',1);registers[reg]=int(value)
        elif op=='const-class':
            reg,value=text.split(', ',1);registers[reg]=value
        elif op=='new-array':registers[text.split(', ')[0]]=None
        elif op=='invoke-virtual' and MODEL+'DataGimbalGetHandleParams;->get(I I Ljava/lang/Class; [I)' in text:
            args=re.findall(r'v\d+',text.split(', '+MODEL)[0])
            if len(args)!=5 or registers.get(args[3])!='Ljava/lang/Integer;' or registers.get(args[2])!=1:raise ValueError('unsupported handle getter arguments')
            offset=registers.get(args[1]);tail=operations[i+1:]
            if type(offset) is not int or not 0<=offset<8 or len(tail) not in (5,8):raise ValueError('unsupported handle getter context')
            reg=tail[0][1]
            expected=[('move-result-object',reg),('check-cast',reg+', Ljava/lang/Integer;'),('invoke-virtual',reg+', Ljava/lang/Integer;->intValue()I'),('move-result',reg)]
            if tail[:4]!=expected:raise ValueError('handle result transform changed')
            if len(tail)==5:
                if tail[4]!=('return',reg):raise ValueError('handle raw integer changed')
                return offset,False
            andop,andtext=tail[4];parts=andtext.split(', ')
            if andop!='and-int/2addr' or parts[0]!=reg or registers.get(parts[1])!=1:raise ValueError('handle boolean mask changed')
            if tail[5]!=('if-ne',reg+', '+parts[1]+', +003h') or tail[6]!=('return',parts[1]) or tail[7][0]!='return' or registers.get(tail[7][1])!=0:raise ValueError('handle boolean polarity changed')
            return offset,True
        else:raise ValueError('unsupported handle getter prefix '+op)
    raise ValueError('missing handle getter')


def handle_setter_context(operations):
    """Resolve one freshly allocated source setter, not a reusable singleton."""
    owner=MODEL+'DataGimbalSetHandleParams;'
    allocation=[text for op,text in operations if op=='new-instance' and owner in text]
    setters=[text.split('->')[1].split('(')[0] for op,text in operations if op=='invoke-virtual' and owner+'->set' in text]
    allowed={'setDualChannelEnable':('dualChannelMode',0),'setTiltDirection':('tiltDirection',1),'setPanDirection':('panDirection',2)}
    if len(allocation)!=1 or len(setters)!=1 or setters[0] not in allowed:raise ValueError('unsupported handle action setter')
    reg=allocation[0].split(', ')[0]
    if ('invoke-direct',reg+', '+owner+'-><init>()V') not in operations:raise ValueError('missing fresh handle constructor')
    if any('->getInstance(' in text for _,text in operations):raise ValueError('unexpected handle singleton')
    field,offset=allowed[setters[0]]
    return dict(field=field,offset=offset,sourceSetter=setters[0],freshObject=True)


def handle_fallback_comparison(operations):
    """Accept pinned reference comparison, never label it value equality."""
    tokens=[text for _,text in operations]
    if not any('->getData()Ljava/lang/Object;' in t for t in tokens) or not any('Ljava/lang/Class;->cast(' in t for t in tokens):raise ValueError('missing fallback cast/data')
    if ('if-ne','v0, v3, +00bh') not in operations or any('->equals(' in t for t in tokens):raise ValueError('fallback reference comparison changed')
    if ('if-eqz','v3, +022h') not in operations or not any('->RESULT_FAILED ' in t for t in tokens):raise ValueError('fallback failure branches changed')
    if not any('->onSuccess(Ljava/lang/Object;)V' in t for t in tokens) or not any('->onFails(' in t for t in tokens):raise ValueError('fallback callback changed')
    return 'reference-identity-after-Class.cast'


def trace(apk,sdk_path,ui_path):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    raw=sdk_path.read_bytes();uiraw=ui_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=DERIVED_SHA256 or hashlib.sha256(uiraw).hexdigest()!=UI_BANK_SHA256:raise ValueError('pinned restoration hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    sdk={c.get_name():c for c in DEX(raw).get_classes()};ui={c.get_name():c for c in DEX(uiraw).get_classes()};methods={}
    def ops(m):return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    def record(m,bank='sdk'):
        if not m.get_code():raise ValueError('unreadable controls method')
        methods[(m.get_class_name(),m.get_name(),m.get_descriptor())]=dict(bank=bank,className=m.get_class_name(),method=m.get_name(),descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());return m
    def take(owner,name,descriptor=None):
        candidates=[m for m in sdk[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(candidates)!=1:raise ValueError('ambiguous controls method '+owner+name)
        return record(candidates[0])
    def require(m,*tokens):
        operations=ops(m)
        for token in tokens:
            if not any(token in text for _,text in operations):raise ValueError('missing controls source reference '+token)
    chain=[];owner=BASE+'DJIGimbalHG724Abstraction;'
    while owner in sdk and owner.startswith(BASE):chain.append(owner);owner=sdk[owner].get_superclassname()
    resolved=[]
    for name in ('fineTuneGimbalPitchInDegrees','fineTuneGimbalRollInDegrees','loadFactorySettings','getGimbalControllerMode','setGimbalControllerMode','getPitchOrRollInverseControlEnabled','getYawInverseControlEnabled','setPitchOrRollInverseControlEnabled','setYawInverseControlEnabled'):
        owner=next(o for o in chain if any(m.get_name()==name for m in sdk[o].get_methods()));m=take(owner,name);resolved.append(dict(method=name,owner=owner,descriptor=m.get_descriptor()))
    command_owner='Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;'
    command_entries=constructor_records(ops(take(command_owner,'<clinit>')),command_owner)
    for name,value in [('RollFinetune',7),('GetHandleParams',54),('SetHandleParams',53),('ResetUserParams',19),('SaveUserParams',17)]:
        if command_entries[name]['arguments'][2]!=value:raise ValueError('controls command ID changed')
    fine=MODEL+'DataGimbalRollFinetune;';get=MODEL+'DataGimbalGetHandleParams;';put=MODEL+'DataGimbalSetHandleParams;';reset=MODEL+'DataGimbalResetUserParams;';save=MODEL+'DataGimbalSaveUserParams;'
    axis_owner=fine[:-1]+'$FineTuneAxis;';axis_records=constructor_records(ops(take(axis_owner,'<clinit>')),axis_owner)
    axis_values={key:axis_records[key]['arguments'][2] for key in ('ROLL','PITCH','YAW')}
    if axis_values!={'ROLL':0,'PITCH':2,'YAW':4}:raise ValueError('fine axis wire values changed')
    require(take(fine,'doPack'),'->mData B','->mAxis I')
    take(fine,'setFineTuneAxis');take(fine,'setFineTuneValue')
    for axis in ('Pitch','Roll'):
        m=take(BASE+'DJIGimbalAbstraction;','fineTuneGimbal'+axis+'InDegrees')
        require(m,'1073741824','-1073741824','1092616192','->setFineTuneValue(B)','FineTuneAxis;->'+axis.upper()+' ')
        if not any(op=='float-to-int' for op,_ in ops(m)):raise ValueError('fine delta truncation changed')
        if axis=='Roll' and any('->tryToPauseTheStabilizationIfNecessary(' in text for _,text in ops(m)):raise ValueError('fine Roll pause invocation changed')
    pause_ctor=take(BASE+'DJIGimbalAbstraction;','<init>')
    require(pause_ctor,'v0, 0','->needPauseStabilization Z')
    pause_event=take(BASE+'DJIGimbalAbstraction;','onEvent3BackgroundThread','(Ldji/midware/data/model/P3/DataEyeGetPushStabilizationState;)V')
    require(pause_event,'->getStateIsTurnOn()Z','->getStateIsPaused()Z','->needPauseStabilization Z')
    require(take(BASE+'DJIGimbalAbstraction;','tryToPauseTheStabilizationIfNecessary'),'DataSingleSendAppStateForStabilization;','->setGimbalState(')
    for callback in ('8','9'):
        owner=BASE+'DJIGimbalAbstraction$'+callback+';'
        require(take(owner,'onSuccess'),'->onSuccess(Ljava/lang/Object;)V')
        require(take(owner,'onFailure'),'->onFails(')
    getter_rows=[]
    for name,expected,boolean in HANDLE_FIELDS:
        offset,bit=handle_getter_context(ops(take(get,name)))
        if (offset,bit)!=(expected,boolean):raise ValueError('handle getter catalog changed')
        getter_rows.append(dict(sourceGetter=name,offset=offset,size=1,sourceBit0Boolean=bit))
    if ops(take(get,'doPack'))!=[('return-void','')]:raise ValueError('handle read body changed')
    fields=['mJoystickDualChannelEnable','mTiltDirection','mPanDirection','mProfile','mPitchFree','mZoom2Speed','mRotationFocusEnable','mCellphoneSensorDisable']
    body=ops(take(put,'doPack'));ordered=[text.split('->',1)[1].split(' ')[0] for op,text in body if op=='iget' and put+'->' in text]
    if ordered!=fields:raise ValueError('handle write field order changed')
    constants={};slots=[];field=None
    for op,text in body:
        if op in ('const/4','const/16'):
            reg,value=text.split(', ',1);constants[reg]=int(value)
        elif op=='iget' and put+'->' in text:field=text.split('->',1)[1].split(' ')[0]
        elif op=='aput-byte':
            args=text.split(', ');slots.append((field,constants.get(args[2])))
    if slots!=list(zip(fields,range(8))):raise ValueError('handle byte destinations changed')
    require(take(put,'<init>'),'v0, 255')
    constructor_fields=[text.split('->',1)[1].split(' ')[0] for op,text in ops(take(put,'<init>')) if op=='iput']
    reset_fields=[text.split('->',1)[1].split(' ')[0] for op,text in ops(take(put,'reset')) if op=='iput']
    if constructor_fields!=fields or reset_fields!=fields[:6]:raise ValueError('handle default/reset behavior changed')
    for method in (take(put,'<init>'),take(put,'reset')):
        if any(not text.startswith('v0, v1, ') for op,text in ops(method) if op=='iput'):raise ValueError('handle default value register changed')
    setters=['setDualChannelEnable','setTiltDirection','setPanDirection','setProfile','setPitchFree','setZoom2Speed','setRotationFocusEnable','setCellphoneSensorDisable']
    for name,field in zip(setters,fields):require(take(put,name),'->'+field+' I')
    mode_owner='Ldji/common/handheldcontroller/ControllerMode;';modes=constructor_records(ops(take(mode_owner,'<clinit>')),mode_owner)
    if {key:modes[key]['arguments'][2] for key in modes}!={'ONE_AXIS':0,'TWO_AXIS':1,'UNKNOWN':255}:raise ValueError('controller enum changed')
    handheld=BASE+'DJIGimbalHandheldAbstraction;'
    actions=[]
    for method,callback,getcallback,key,getter in [
        ('setGimbalControllerMode','1','2','ControllerMode','getDualChannelEnable'),
        ('setPitchOrRollInverseControlEnabled','7','8','PitchInvertedControlEnabled','getTiltDirection'),
        ('setYawInverseControlEnabled','5','6','YawInvertedControlEnabled','getPanDirection')]:
        context=handle_setter_context(ops(take(handheld,method)))
        require(take(handheld,method),'DJIGimbalHandheldAbstraction$'+callback+';-><init>(')
        if method=='setGimbalControllerMode':require(take(handheld,method),'ControllerMode;->value()I')
        putcallback=handheld[:-1]+'$'+callback+';'
        failure=take(putcallback,'onFailure');success=take(putcallback,'onSuccess')
        require(failure,key,'->-$$Nest$mgetGimbalSettingValue(')
        require(success,'->onSuccess(Ljava/lang/Object;)V')
        if any('DataGimbalGetHandleParams;->' in t for _,t in ops(failure)+ops(success)):raise ValueError('write callback directly queries handle')
        readcallback=handheld[:-1]+'$'+getcallback+';'
        readsuccess=take(readcallback,'onSuccess');require(readsuccess,'->'+getter+'()I')
        require(take(readcallback,'onFailure'),'->onFails(')
        readops=ops(readsuccess)
        if context['field']=='dualChannelMode':
            require(readsuccess,'ControllerMode;->values()')
            if not any(op=='aget-object' for op,_ in readops):raise ValueError('controller mode ordinal lookup changed')
            semantics='enum-array-index-not-find'
        else:
            if ('const/4','v1, 1') not in readops or ('if-ne','v3, v1, +003h') not in readops:raise ValueError('handle direction is not equality-one')
            if any(op.startswith('and-int') for op,_ in readops):raise ValueError('direction unexpectedly uses bit mask')
            semantics='raw-equals-one-not-bit0'
        actions.append(dict(sourceMethod=method,cacheKey=key,getter=getter,readTransform=semantics,**context))
    require(take('Ldji/common/handheldcontroller/ControllerMode;','value'),'->value I')
    require(take(handheld,'-$$Nest$mgetGimbalSettingValue'),'->getGimbalSettingValue(')
    fallback=take(handheld,'getGimbalSettingValue')
    require(fallback,'DJISDKCache;->getValue(','DJISDKCacheKey$Builder;->paramKey(')
    if any('DataGimbalGetHandleParams;->' in t for _,t in ops(fallback)):raise ValueError('cache helper directly sends handle query')
    fallbackowner=handheld[:-1]+'$10;'
    comparison=handle_fallback_comparison(ops(take(fallbackowner,'onSuccess')))
    require(take(fallbackowner,'onFails'),'->onFails(')
    for owner,key in [(fine,'RollFinetune'),(get,'GetHandleParams'),(put,'SetHandleParams'),(reset,'ResetUserParams'),(save,'SaveUserParams')]:
        require(take(owner,'start'),'DeviceType;->GIMBAL ','NEEDACK;->YES ','CmdIdGimbal$CmdIdType;->'+key+' ')
    reset_pack=take(reset,'doPack');require(reset_pack,'PlatformType;->HG724 ','v0, 3','v0, v2, [B')
    reset_ops=ops(reset_pack);expected_tail=[('const/4','v0, 3'),('new-array','v0, v0, [B'),('iput-object','v0, v3, '+reset+'->_sendData [B'),('iget-object','v0, v3, '+reset+'->_sendData [B'),('const/4','v1, 1'),('aput-byte','v1, v0, v2'),('iget-object','v0, v3, '+reset+'->_sendData [B'),('aput-byte','v2, v0, v1'),('iget-object','v0, v3, '+reset+'->_sendData [B'),('const/4','v2, 2'),('aput-byte','v1, v0, v2'),('return-void','')]
    if reset_ops[-12:]!=expected_tail:raise ValueError('reset special payload changed')
    instructions=list(reset_pack.get_instructions());pcs=[];pc=0
    for instruction in instructions:pcs.append(pc);pc+=instruction.get_length()//2
    model_index=next(i for i,(_,text) in enumerate(reset_ops) if 'PlatformType;->HG724 ' in text)
    branch_op,branch_text=reset_ops[model_index+1]
    if branch_op!='if-eq' or branch_text!='v0, v1, +010h' or pcs[model_index+1]+16!=pcs[-12]:raise ValueError('HG724 reset branch does not select special payload')
    reset_callback=BASE+'DJIGimbalAbstraction$13;'
    callback_interface='Ldji/sdksharedlib/hardware/abstractions/DJISDKCacheHWAbstraction$InnerCallback;'
    success_ops=ops(take(reset_callback,'onSuccess'))
    if success_ops!=[('iget-object','v0, v1, '+reset_callback+'->val$callback '+callback_interface),('invoke-interface','v0, v2, '+callback_interface+'->onSuccess(Ljava/lang/Object;)V'),('return-void','')]:raise ValueError('factory reset success no longer forwards opaque object')
    fail=take(reset_callback,'onFailure');require(fail,'DJIError;->getDJIError(','->onFails(')
    if len([op for op,_ in ops(fail) if op.startswith('invoke-')])!=2:raise ValueError('reset failure has extra work')
    if ops(take(save,'doPack'))!=[('return-void','')]:raise ValueError('save body changed')
    direct_save=[]
    for bank,classes in [('sdk',sdk),('ui',ui)]:
        for owner,c in classes.items():
            if owner==save:continue
            for m in c.get_methods():
                if m.get_code() and any(save+'->' in text for _,text in ops(m)):
                    record(m,bank);direct_save.append(dict(bank=bank,className=owner,method=m.get_name()))
    return dict(schemaVersion=1,apkSha256=APK_SHA256,derivedSha256=DERIVED_SHA256,uiDerivedSha256=UI_BANK_SHA256,appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,
                hg724Inheritance=chain,effectiveMethods=resolved,fineTune=dict(command='04:07',axisWireValues=axis_values,sourceCallableAxes=['pitch','roll'],sourceAdjustmentDegrees=[-2,2],conversion='float32 multiply10, truncate-to-int, low signed byte; physical effect/cumulative semantics unverified',targetAdjustmentEffectVerified=False,callbacksDoNotParseActualAngles=True,pauseStabilizationGateNotFirmwareVerified=True,pauseGateSource=dict(defaultValue=False,eventClass='DataEyeGetPushStabilizationState',requiresPauseWhen='turnedOn and notPaused',fineRollDoesNotAutomaticallyInvokePause=True,targetStateVerified=False)),
                handle=dict(readCommand='04:36',writeCommand='04:35',readBodyHex='',fields=getter_rows,writeFieldOrder=fields,constructorByteDefaults=[255]*8,afterPackResetFields=reset_fields,afterPackRetainedFields=fields[6:],unspecifiedByteFirmwareSemanticsVerified=False,sourceActions=actions,writeFailureFallback=dict(api='DJISDKCache.getValue',comparison=comparison,directBleReadProven=False,writeAcceptanceProven=False),writeSuccessParsesReadback=False),
                parameterReset=dict(command='04:13',sourceCondition='PlatformType.HG724 (not GimbalComponentType ordinal)',sourceBodyHex=hg724_reset_payload('HG724').hex(),targetResetScopeVerified=False,successCallbackForwardsOpaqueObject=True,failureCallbackMapsCcode=True,callbackParsesPhysicalCompletion=False),
                parameterSave=dict(command='04:11',sourceBodyHex='',directCallerScanBanks=['business05','business03'],directCallers=direct_save,targetModelCallPathEstablished=False),
                offlineVectors=dict(pitchNegative= fine_tune_payload('pitch',-1.29).hex(),rollPositive=fine_tune_payload('roll',1.29).hex(),panDirectionPatch=handle_patch_payload(panDirection=1).hex()),methods=list(methods.values()))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('apk','sdk','ui','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.sdk,a.ui);a.output.write_text(json.dumps(r,indent=2)+'\n');print('%d controls method fingerprints; source only, no sends.'%len(r['methods']))
if __name__=='__main__':main()
