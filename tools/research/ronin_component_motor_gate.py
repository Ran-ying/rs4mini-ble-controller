#!/usr/bin/env python3
"""Static MotorEnabled cache producer for the component-calibration gate; no execution."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_settings_trace import named_keys,unique_record,OWNER
from ronin_calibration_transport import branch_target
RONIN='Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalRonin2Abstraction;'
SUB='Ldji/common/gimbal/Ronin2SubscribeIMPL;'

def source_motor_enabled(value):
    if type(value) is not int or not 0<=value<=255:raise ValueError('explicit uint8 source parameter required')
    return not bool(value&1)

def trace(apk,sdk):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    raw=sdk.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BANKS[5]:raise ValueError('bank hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    cs={c.get_name():c for c in DEX(raw).get_classes()};methods=[]
    def take(owner,name,descriptor=None):
        found=[m for m in cs[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(found)!=1 or not found[0].get_code():raise ValueError('missing gate method')
        m=found[0];methods.append(dict(className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest()));rows=[];off=0
        for i in m.get_instructions():rows.append((off,i.get_name(),i.get_output()));off+=i.get_length()
        return rows
    sub=take(SUB,'<init>');by={o:(p,t) for o,p,t in sub}
    if by[304]!=('const-string/jumbo','v0, MotorEnabled') or OWNER+'->MOTOR_SPECIAL_CMD ' not in by[310][1] or SUB+'->put(' not in by[314][1]:raise ValueError('MotorEnabled registration changed')
    event=take(RONIN,'onEvent3BackgroundThread','(Ldji/midware/data/model/P3/DataGimbalGetUserParams;)V');by={o:(p,t) for o,p,t in event}
    for off,pair in {96:('const/4','v0, 0'),98:('const/4','v1, 1'),884:('and-int/lit8','v2, v11, 1'),892:('move','v2, v1'),896:('move','v2, v0'),906:('const-string/jumbo','v4, MotorEnabled')}.items():
        if by.get(off)!=pair:raise ValueError('source gate boolean producer changed')
    if branch_target(888,by[888][1])!=896 or branch_target(894,by[894][1])!=898:raise ValueError('inverted motor bit branch changed')
    if OWNER+'->MOTOR_SPECIAL_CMD ' not in by[852][1] or 'DJIGimbalParamInfoManager;->read(' not in by[864][1] or '->notifyValueChangeForKeyPath(' not in by[920][1]:raise ValueError('source motor cache publication changed')
    for off,op,text in event:
        if 98<off<920 and text.split(', ')[0] in ('v0','v1') and not op.startswith(('if-','goto','invoke','iput','sput','aput','return')):raise ValueError('gate boolean register overwritten')
    keys=named_keys([(op,t) for _,op,t in take(OWNER,'<clinit>')]);name=keys['MOTOR_SPECIAL_CMD']['name']
    with zipfile.ZipFile(str(apk)) as z:resource=z.read('res/DB.json')
    row=unique_record(json.loads(resource),name)
    if row['name']!='motor_special_cmd' or row['index']!=35 or row['size']!=1:raise ValueError('motor parameter context changed')
    return dict(apkSha256=APK_SHA256,bankSha256=BANKS[5],methods=methods,resourceSha256=hashlib.sha256(resource).hexdigest(),parameter=row,sourceCache=dict(key='MotorEnabled',enabledWhenBit0IsZero=True,producer='DataGimbalGetUserParams event -> parameter manager -> cache publication'),sdkPreflight=dict(freshReadIndex=35,size=1,autoEnableMotors=False,atomicWithFirmwareCalibration=False),actualMotorPhysicalStateVerified=False,hardwareTested=False,vendorCodeExecuted=False)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','sdk','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.sdk);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('3 methods: MotorEnabled source gate from index35 inverse bit0')
if __name__=='__main__':main()
