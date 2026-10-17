#!/usr/bin/env python3
"""Audit distinct user-profile, movement-preset and new follow UI paths offline."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_command_audit import DERIVED_SHA256
from ronin_code_banks import UI_BANK_SHA256
from ronin_settings_trace import BASE, OWNER, named_keys, unique_record
from ronin_model_trace import enum_entry


def preset_read_context(operations):
    """Resolve the source getter's explicit offset/width; not a raw BLE offset."""
    registers={}
    for op,text in operations:
        if op in ('const/4','const/16','const'):
            reg,value=text.split(', ',1);registers[reg]=int(value)
        elif op=='const-class':
            reg,value=text.split(', ',1);registers[reg]=value
        elif op=='invoke-virtual' and 'DataGimbalGetPushUserParams;->get(I I Ljava/lang/Class; [I)' in text:
            args=re.findall(r'v\d+',text.split(', Ldji/')[0])
            if len(args)!=5 or registers.get(args[3])!='Ljava/lang/Integer;':raise ValueError('unresolved preset getter arguments')
            offset,width=registers.get(args[1]),registers.get(args[2])
            if (offset,width)!=(2,1):raise ValueError('preset business offset/width changed')
            return dict(businessOffset=offset,width=width,rawBleOffsetVerified=False)
        else:raise ValueError('unsupported preset getter prefix '+op)
    raise ValueError('missing preset getter')


def relative_target(pc,branch_text):
    """DEX branch displacement and PC are code units, not byte offsets."""
    match=re.search(r', ([+-])([0-9a-fA-F]+)h$',branch_text)
    if type(pc) is not int or pc<0 or not match:raise ValueError('unresolved branch displacement')
    return pc+(1 if match[1]=='+' else -1)*int(match[2],16)


def axis_mode_value(name):
    values={'ThreeAxis':0,'TwoAxis':1,'Roll360':2,'ThreeDRoll360':3}
    if type(name) is not str or name not in values:raise ValueError('explicit source axis enum required')
    return values[name]<<3


def trace(apk,sdk_path,ui_path):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    sdk_raw=sdk_path.read_bytes();ui_raw=ui_path.read_bytes()
    if hashlib.sha256(sdk_raw).hexdigest()!=DERIVED_SHA256 or hashlib.sha256(ui_raw).hexdigest()!=UI_BANK_SHA256:raise ValueError('pinned restoration hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    from androguard.core.axml import ARSCParser
    sdk={c.get_name():c for c in DEX(sdk_raw).get_classes()};ui={c.get_name():c for c in DEX(ui_raw).get_classes()};methods={}
    def take(classes,owner,name,descriptor=None):
        choices=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(choices)!=1 or not choices[0].get_code():raise ValueError('expected readable profile method '+owner+name)
        m=choices[0];methods[(owner,name,m.get_descriptor())]=dict(bank='sdk' if classes is sdk else 'ui',className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());return m
    def ops(m):return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    def require(m,token):
        if not any(token in text for _,text in ops(m)):raise ValueError('missing profile reference '+token)
    keys=named_keys(ops(take(sdk,OWNER,'<clinit>')))
    with zipfile.ZipFile(str(apk)) as z:
        records=json.loads(z.read('res/DB.json'));resources=ARSCParser(z.read('resources.arsc'))
    selected=[]
    for key,index,name,maximum in [('USER_PROFILE',0,'table_choice',5),('GIMBAL_WORK_MODE',62,'ronin_gimbal_work_mode',128)]:
        entry=keys[key];record=unique_record(records,entry['name'])
        if entry['name']!=name or (record['index'],record['size'],record['minValue'],record['maxValue'])!=(index,1,0,maximum):raise ValueError('profile parameter metadata changed')
        if entry['getter']!='Ldji/midware/data/model/P3/DataGimbalGetUserParams;':raise ValueError('profile getter changed')
        selected.append(dict(record,baseCommand=key))
    chain=[];owner=BASE+'DJIGimbalHG724Abstraction;'
    while owner in sdk and owner.startswith(BASE):chain.append(owner);owner=sdk[owner].get_superclassname()
    ronin=BASE+'DJIGimbalRonin2Abstraction;'
    for name,key in [('setUserProfile','USER_PROFILE'),('setGimbalWorkMode','GIMBAL_WORK_MODE')]:
        m=take(sdk,ronin,name);require(m,OWNER+'->'+key+' ');require(m,'->setRonin2CommonUserParam(')
        resolved=next(o for o in chain if any(x.get_name()==name and x.get_descriptor()==m.get_descriptor() for x in sdk[o].get_methods()))
        if resolved!=ronin:raise ValueError('profile setter override changed')
    common=take(sdk,ronin,'setRonin2CommonUserParam');require(common,'->checkValueValid(');require(common,'DataGimbalSetUserParams;->setInfo(')
    event=take(sdk,ronin,'onEvent3BackgroundThread','(Ldji/midware/data/model/P3/DataGimbalGetUserParams;)V')
    for token in ('->USER_PROFILE ','UserProfile','->GIMBAL_WORK_MODE ','GimbalWorkMode'):require(event,token)
    event_ops=ops(event);start=next(i for i,(_,text) in enumerate(event_ops) if '->FLOWER_SPECIAL_CMD ' in text)
    if event_ops[start+8:start+12]!=[('const/4','v3, 3'),('shr-int/2addr','v2, v3'),('and-int/2addr','v2, v3'),('aget-object','v11, v11, v2')]:raise ValueError('axis source read shift/mask changed')

    for axis in ('YAW','PITCH','ROLL'):
        start=next(i for i,(_,text) in enumerate(event_ops) if '->SMOOTH_TRACK_ENABLED_'+axis+' ' in text)
        if event_ops[start+8:start+13]!=[('if-ne','v11, v1, +004h'),('move','v11, v1'),('goto','+2h'),('move','v11, v0'),('invoke-static','v11, Ljava/lang/Boolean;->valueOf(Z)Ljava/lang/Boolean;')]:raise ValueError('ordinary smooth read comparison changed')
        for reg,value in [('v0',0),('v1',1)]:
            writes=[(op,text) for op,text in event_ops[:start] if op.startswith(('const','move','iget','sget','aget','new')) and text.split(',')[0]==reg]
            if not writes or writes[-1]!=('const/4',reg+', '+str(value)):raise ValueError('smooth boolean constants unresolved')
    modes='Ldji/common/gimbal/DJIGimbalRonin2WorkMode;';movement='Ldji/common/gimbal/MovementSettingsProfile;'
    work_enum=ops(take(sdk,modes,'<clinit>'));movement_enum=ops(take(sdk,movement,'<clinit>'))
    work=[enum_entry(work_enum,modes,n) for n in ('Free','Flower','Fpv','Center')]
    presets=[enum_entry(movement_enum,movement,n) for n in ('CUSTOM_1','CUSTOM_2','FAST','MEDIUM','SLOW','UNKNOWN')]
    if [r['value'] for r in work]!=[0,1,2,3] or [r['value'] for r in presets]!=[0,1,3,4,5,255]:raise ValueError('profile enums changed')
    business=preset_read_context(ops(take(sdk,'Ldji/midware/data/model/P3/DataGimbalGetPushUserParams;','getPresetID')))
    custom=take(sdk,BASE+'DJIGimbalAbstraction;','isCustomAdvancedSettingProfile')
    for token in ('->getPresetID(','->CUSTOM_1 ','->CUSTOM_2 '):require(custom,token)
    view='Lcom/dji/ronin/ui/configuration/ConfigUserProfileView;';utils='Lcom/dji/ronin/util/CommonUtils;'
    for name in ('setUserProfileMode','updateUserProfile','onClick'):
        m=take(ui,view,name);require(m,'UserProfile' if name!='onClick' else '->setUserProfileMode(')
    update=take(ui,view,'updateUserProfile')
    for token in ('->mUserProfileM1 ','->mUserProfileM2 ','->mUserProfileM3 '):require(update,token)
    buttons=ops(take(ui,view,'onClick'))
    if [text for op,text in buttons if op=='const/4']!=['v1, 2','v1, 1','v1, 0']:raise ValueError('profile button values changed')
    choice=take(ui,view,'lambda$initView$0');require(choice,'->isUseNewProfileDevice()Z');require(choice,'->setTrackModeHG711(I)V');require(choice,'->setTrackMode(I)V')
    new_mode=take(ui,view,'setTrackModeHG711');require(new_mode,'IsCustomFollowMode');require(new_mode,'->setNewUserProfileCustomMode()V')
    for axis in ('YAW','PITCH','ROLL'):require(new_mode,'->SMOOTH_TRACK_ENABLED_'+axis+' ')
    require(take(ui,view,'setNewUserProfileCustomMode'),'IsCustomFollowMode')
    show=take(ui,view,'updateTrackModeShow');require(show,'->isUseNewProfileDevice()Z')
    if ('const/4','v3, 2') not in ops(show) or ('if-eq','v0, v3, +008h') not in ops(show):raise ValueError('new profile selector gate changed')
    require(take(ui,view,'updateView'),'->updateTrackModeViewHG711()V')
    require(take(ui,view,'updateTrackModeViewHG711'),'CustomFollowModeYawEnabled')
    require(take(ui,view,'setTrackMode'),'->SMOOTH_TRACK_ENABLED_YAW ')
    init=take(ui,view,'initView');require(init,'->isUseNewProfileDeviceIndex()Z')
    for rid in (2130903042,2130903043):
        if not any(text.endswith(', '+str(rid)) for op,text in ops(init) if op=='const'):raise ValueError('profile list resource changed')
    switch='Lcom/dji/ronin/ui/entry/DeviceSwitchTextView;'
    require(take(ui,switch,'isUseNewProfileDeviceIndex'),'->is4thGenDeviceIndex()Z')
    require(take(ui,switch,'is4thGenDeviceIndex'),'Model;->HG724 ')
    for name,token in [('isUseNewProfileDevice','->is4thGenDevice()Z'),('is4thGenDevice','->isHG724()Z'),('isHG724','Lcom/dji/upgrade/util/CommonUtils;->isHG724()Z')]:require(take(ui,utils,name),token)
    model=take(ui,'Lcom/dji/upgrade/util/CommonUtils;','isHG724');require(model,'ModelName');require(model,'Model;->HG724 ')
    mode_parameters=[]
    for key,index,name,maximum in [('SMOOTH_TRACK_ENABLED_YAW',17,'yaw_smooth_track',1),('SMOOTH_TRACK_ENABLED_PITCH',18,'pitch_smooth_track',1),('SMOOTH_TRACK_ENABLED_ROLL',19,'roll_smooth_track',1),('FLOWER_SPECIAL_CMD',34,'flower_special_cmd',255)]:
        entry=keys[key];record=unique_record(records,entry['name'])
        if entry['name']!=name or (record['index'],record['size'],record['typeID'],record['minValue'],record['maxValue'])!=(index,1,0,0,maximum):raise ValueError('new mode parameter changed')
        if entry['getter']!='Ldji/midware/data/model/P3/DataGimbalGetUserParams;':raise ValueError('new mode getter changed')
        mode_parameters.append(dict(record,baseCommand=key))
    axis_owner='Ldji/common/gimbal/DJIGimbalRonin2AxisMode;'
    axis_enums=[enum_entry(ops(take(sdk,axis_owner,'<clinit>')),axis_owner,name) for name in ('ThreeAxis','TwoAxis','Roll360','ThreeDRoll360')]
    if [r['value'] for r in axis_enums]!=[0,1,2,3]:raise ValueError('axis enums changed')
    axis_set=take(sdk,ronin,'setGimbalAxisMode');require(axis_set,'->FLOWER_SPECIAL_CMD ')
    if ('shl-int/lit8','v2, v2, 3') not in ops(axis_set):raise ValueError('axis mode shift changed')
    require(axis_set,'->setRonin2CommonUserParam(')
    if next(o for o in chain if any(m.get_name()=='setGimbalAxisMode' for m in sdk[o].get_methods()))!=ronin:raise ValueError('axis setter override changed')
    custom_set=take(sdk,ronin,'setCustomFollowModeEnabled');require(custom_set,'->CUSTOM_FOLLOW_SETTING ')
    if ('or-int/lit8','v2, v0, 1') not in ops(custom_set) or ('and-int/lit8','v2, v0, -2') not in ops(custom_set):raise ValueError('custom bit RMW changed')
    ui_axis=take(ui,view,'setGimbalAxisMode')
    for token in ('->ThreeDRoll360 ','->ThreeAxis ','CacheHelper;->setValue('):require(ui_axis,token)
    require(take(ui,view,'exitCustomModeForHG720'),'->isHG720(')
    if ops(take(ui,view,'setIsCustomMode'))!=[('iput-boolean','v1, v0, '+view+'->mIsCustomMode Z'),('return-void','')]:raise ValueError('UI custom flag now has device side effects')
    require(take(ui,view,'updateAxisModeShow'),'->setVisibility(')
    branch_points=[];pc=0
    for instruction in choice.get_instructions():
        op,text=instruction.get_name(),instruction.get_output()
        if op.startswith('if-') or op.startswith('goto'):
            # Goto has no register prefix; normalize only for displacement parsing.
            target=relative_target(pc,text if ',' in text else 'goto, '+text)
            branch_points.append(dict(pc=pc,operation=op,target=target))
        pc+=instruction.get_length()//2
    if dict(pc=0x34,operation='if-ne',target=0x48) not in branch_points or dict(pc=0x47,operation='goto',target=0x6c) not in branch_points:raise ValueError('new list index2 no longer bypasses smooth setter')
    new_ops=ops(new_mode)
    for op,text in [('if-nez','v10, +01ch'),('if-ne','v10, v5, +005h'),('if-eq','v10, v5, +00ah')]:
        if (op,text) not in new_ops:raise ValueError('new mode index0/1 control flow changed')
    if [text for op,text in new_ops if op=='aput-object' and ', v1,' in text]!=['v6, v1, v4','v6, v1, v5','v6, v1, v7']:raise ValueError('FPV source values not uniform')
    if ('const/4','v5, 1') not in new_ops or not any('v5, Ljava/lang/Integer;->valueOf(I)' in text for _,text in new_ops):raise ValueError('FPV source integer one changed')
    for suffix,names in [('10',('onSuccess','onFailure','lambda$onFailure$0')),('13',('onSuccess','onFails'))]:
        for name in names:
            callback=take(ui,view[:-1]+'$'+suffix+';',name)
            if any('DataGimbalSetUserParams;->' in text or 'CacheHelper;->set' in text for _,text in ops(callback)):raise ValueError('mode callback now chains parameter writes')
    custom_view='Lcom/dji/ronin/ui/configuration/ConfigGimbalModeSetView;'
    display=take(ui,custom_view,'setAxisStatus')
    calls=[text for op,text in ops(display) if op.startswith('invoke-')]
    if len(calls)!=6 or any('Landroid/widget/ImageView;->setVisibility(I)V' not in text for text in calls):raise ValueError('custom axis display now has other side effects')
    clicked=take(ui,custom_view,'setClicked')
    allowed=('Ljava/lang/StringBuilder;->','ConfigLog;->logWriteD(')
    if any(not any(token in text for token in allowed) for op,text in ops(clicked) if op.startswith('invoke-')):raise ValueError('custom clicked flag now calls another component')
    require(clicked,'->mIsClicked Z')
    # Record localized UI labels as facts, not invented enum translations.
    labels=[]
    for resource_id in (2131952876,2131952878,2131952880,2131952882):
        values=sorted(set(str(value) for _,value in resources.get_resolved_res_configs(resource_id)))
        if not values:raise ValueError('missing profile UI labels')
        labels.append(dict(resourceId=hex(resource_id),values=values))
    arrays=[]
    for rid,expected in [(2130903042,['Pan & Tilt follow','Pan follow','FPV','Custom','3D Roll 360']),
                         (2130903043,['FPV','Custom','3D Roll 360'])]:
        resolved=resources.get_resolved_res_configs(rid)
        if len(resolved)!=1 or not isinstance(resolved[0][1],list):raise ValueError('unexpected profile array structure')
        values=[value for config,value in resolved[0][1] if not config.get_qualifier()]
        if values!=expected:raise ValueError('profile array order changed')
        arrays.append(dict(resourceId=hex(rid),defaultLanguageValues=values))
    return dict(schemaVersion=1,apkSha256=APK_SHA256,sdkDerivedSha256=DERIVED_SHA256,uiDerivedSha256=UI_BANK_SHA256,
                appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,
                parameters=selected,modeParameters=mode_parameters,ordinarySmoothTrack=dict(readTransform='raw-equals-one',sourceOtherValuesBecomeFalse=True,appWritesViaParameterArrays=True,perAxisSdkSetterEstablished=False),axisModeSourceEnums=axis_enums,axisModeSourceRead=dict(shift=3,mask=3,packedMask=24),axisModeSourceValues={r['name']:axis_mode_value(r['name']) for r in axis_enums},newModeFlow=dict(fpvSmoothValues=[1,1,1],customFollowFlagReadModifyWrite=True,index2BypassesSmoothSetter=True,uiCustomFlagIsLocalOnly=True,customAxisDisplayLocalOnly=True,callbacksChainParameterWrites=False,atomicTransactionVerified=False,wireOrderVerified=False,firmwareRollbackVerified=False,axisModeIsNotMotorControlBit=True),hg724Inheritance=chain,userProfileUiValues=[0,1,2],userProfileUiNames=['M1','M2','M3'],
                workModeSourceEnums=work,movementProfileSourceEnums=presets,presetGetter=business,uiLabels=labels,uiModeArrays=arrays,
                sourceFacts=dict(userProfileIsNotMovementPreset=True,workModeIsNotPfPtfEnum=True,
                                 hg724ConditionalNewProfileBranch=True,newBranchCallsSetTrackModeHG711=True,
                                 hg724SelectedModelUsesNewUiList=True,newProfileSelectorRequiresUserProfile2=True,
                                 legacyThreeAxisMaskPathNotAutomaticallyHg724=True,sourceCodeDoesNotProveFirmwareSupport=True),
                remaining=['Audit parameter push subscription and raw packet framing before applying getPresetID offset2.',
                           'Audit full mode prerequisites, all source fields and action/cancellation semantics before SDK mode encapsulation.',
                           'SDK interfaces and physical acceptance/effects/persistence remain unverified for these new profile findings.'],methods=list(methods.values()))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','sdk','ui','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();result=trace(a.apk,a.sdk,a.ui);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('%d profile/model method fingerprints; no firmware or BLE execution.'%len(result['methods']))

if __name__=='__main__':main()
