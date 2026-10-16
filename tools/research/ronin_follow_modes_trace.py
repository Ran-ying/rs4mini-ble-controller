#!/usr/bin/env python3
"""Trace six packed parameter modes across pinned SDK/UI code banks, offline."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_command_audit import DERIVED_SHA256
from ronin_code_banks import UI_BANK_SHA256
from ronin_settings_trace import BASE,OWNER,named_keys,unique_record
from ronin_model_trace import enum_entry

FIELDS=[('setFollowSpeedMode','FOLLOW_SPEED_MODE',65),('setFollowDeadZoneMode','FOLLOW_DEAD_ZONE_MODE',66),
        ('setFollowAcceMode','FOLLOW_ACCE_MODE',71),('setRcSpeedMode','RC_SPEED_MODE',67),
        ('setRcDeadZoneMode','RC_DEAD_ZONE_MODE',68),('setRcSmoothMode','RC_SMOOTH_MODE',69)]
UI='Lcom/dji/ronin/ui/configuration/'
DIALOG=UI+'dialog/ConfigSelectSeekbarDialog;'


def trace(apk,sdk_path,ui_path):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    raw=sdk_path.read_bytes();uiraw=ui_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=DERIVED_SHA256 or hashlib.sha256(uiraw).hexdigest()!=UI_BANK_SHA256:raise ValueError('pinned restored bank hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    sdk={c.get_name():c for c in DEX(raw).get_classes()};ui={c.get_name():c for c in DEX(uiraw).get_classes()};methods=[]
    def take(classes,owner,name,descriptor=None):
        matches=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(matches)!=1 or not matches[0].get_code():raise ValueError('expected readable source method')
        m=matches[0];methods.append(dict(bank='sdk' if classes is sdk else 'ui',className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest()));return m
    def ops(m):return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    enum=take(sdk,OWNER,'<clinit>');keys=named_keys(ops(enum))
    with zipfile.ZipFile(str(apk)) as z:resource=z.read('res/DB.json')
    records=json.loads(resource);parameters=[]
    for method,key,index in FIELDS:
        entry=keys[key];row=unique_record(records,entry['name'])
        if (row['index'],row['size'],row['typeID'],row['minValue'],row['maxValue'])!=(index,1,0,0,255) or entry['getter']!='Ldji/midware/data/model/P3/DataGimbalGetUserParams;':raise ValueError('mode parameter metadata/getter changed')
        operations=ops(take(sdk,BASE+'DJIGimbalRonin2Abstraction;',method))
        if not any(OWNER+'->'+key+' ' in t for _,t in operations) or not any('->setRonin2CommonUserParam(' in t for _,t in operations):raise ValueError('mode setter dispatch changed')
        parameters.append(dict(row,key=key,setter=method))
    for cls in ('DJIGimbalHG724Abstraction;','DJIGimbalHG702Abstraction;'):
        if any(m.get_name() in {r[0] for r in FIELDS} for m in sdk[BASE+cls].get_methods()):raise ValueError('unexpected model-specific mode override')
    take(sdk,BASE+'DJIGimbalRonin2Abstraction;','setRonin2CommonUserParam')
    take(sdk,BASE+'DJIGimbalRonin2Abstraction;','onEvent3BackgroundThread','(Ldji/midware/data/model/P3/DataGimbalGetUserParams;)V')
    owner='Ldji/common/gimbal/DJIGimbalRCControlType;';enum=take(sdk,owner,'<clinit>')
    values=[enum_entry(ops(enum),owner,n) for n in ('Custom','Low','Middle','High')]
    if [r['value'] for r in values]!=[0,1,2,3]:raise ValueError('mode enum values changed')
    update=take(ui,DIALOG,'updateView');instructions={};offset=0
    for o in update.get_instructions():instructions[offset]=(o.get_name(),o.get_output());offset+=o.get_length()
    expected={0x56:('shr-int/lit8','v2, v0, 2'),0x5e:('iput','v2, v6, '+DIALOG+'->pitchType I'),
              0x62:('shr-int/lit8','v2, v0, 6'),0x68:('iput','v2, v6, '+DIALOG+'->yawType I'),
              0x6c:('shr-int/lit8','v0, v0, 4'),0x72:('iput','v0, v6, '+DIALOG+'->rollType I')}
    if any(instructions.get(k)!=v for k,v in expected.items()):raise ValueError('axis mode layout changed')
    take(ui,DIALOG[:-1]+'$2;','onItemChange')
    for name in ('RCControlTypeBinding','RCSpeedTypeBinding'):take(ui,DIALOG[:-1]+'$'+name+';','<clinit>')
    take(ui,UI+'control/ConfigControlMovementView;','initView')
    for axis in ('Pan','Tilt','Roll'):take(ui,UI+'smoothtrack/ConfigSmoothTrack'+axis+'View;','onClick')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,sdkDerivedSha256=DERIVED_SHA256,uiDerivedSha256=UI_BANK_SHA256,
                appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,inheritanceOnlyDoesNotProveFirmwareSupport=True,
                parameters=parameters,modeEnums=values,methods=methods,
                sourceFacts=dict(writeCommand='04:0F',readCommand='04:10',axisShifts=dict(pitch=2,roll=4,yaw=6),axisMask=252,
                                 lowTwoBitsSemanticsVerified=False,pfPtfFpvPresetsVerified=False,physicalUnitsVerified=False))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','sdk','ui','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.sdk,a.ui);a.output.write_text(json.dumps(r,indent=2)+'\n')
    print('%d mode records, %d cross-bank method fingerprints; no App executed.'%(len(r['parameters']),len(r['methods'])))

if __name__=='__main__':main()
