#!/usr/bin/env python3
"""Audit abnormal/battery source notifications offline, without SDK sends."""
import argparse,hashlib,json,re
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_subscription_trace import constructor_records
MODEL='Ldji/midware/data/model/P3/'
ABNORMAL=MODEL+'DataGimbalGetPushAbnormalStatus;'
BATTERY=MODEL+'DataGimbalPushBatteryInfo;'


def field_context(operations,owner,boolean):
    registers={}
    for i,(op,text) in enumerate(operations):
        if op in ('const/4','const/16','const'):
            reg,value=text.split(', ',1);registers[reg]=int(value)
        elif op=='const-class':
            reg,value=text.split(', ',1);registers[reg]=value
        elif op=='new-array':registers[text.split(', ')[0]]=None
        elif op=='invoke-virtual' and owner+'->get(I I Ljava/lang/Class; [I)' in text:
            regs=re.findall(r'v\d+',text.split(', '+owner)[0])
            if len(regs)!=5 or registers.get(regs[3])!='Ljava/lang/Integer;' or registers.get(regs[2])!=1:raise ValueError('unresolved one-byte Integer getter')
            offset=registers.get(regs[1]);tail=operations[i+1:]
            if type(offset) is not int or offset<0 or len(tail)<5 or tail[0][0]!='move-result-object':raise ValueError('invalid getter result')
            reg=tail[0][1]
            if tail[:4]!=[('move-result-object',reg),('check-cast',reg+', Ljava/lang/Integer;'),('invoke-virtual',reg+', Ljava/lang/Integer;->intValue()I'),('move-result',reg)]:raise ValueError('getter result conversion changed')
            tail=tail[4:];shift=0;mask=255
            if tail[0][0] in ('shr-int/2addr','shr-int/lit8'):
                op,text=tail.pop(0);args=text.split(', ')
                if args[0]!=reg:raise ValueError('unresolved shift destination')
                shift=registers.get(args[1]) if op=='shr-int/2addr' else int(args[2])
                if type(shift) is not int or not 0<=shift<=7:raise ValueError('unresolved source shift')
            if tail[0][0]=='and-int/2addr':
                args=tail.pop(0)[1].split(', ')
                if args[0]!=reg or type(registers.get(args[1])) is not int:raise ValueError('unresolved source mask')
                mask=registers[args[1]]
            if not 0<=mask<=255:raise ValueError('unsupported source mask')
            if not boolean:
                if tail!=[('return',reg)]:raise ValueError('unexpected numeric getter suffix')
            else:
                if len(tail)!=3 or tail[0][0]!='if-ne' or tail[1][0]!='return' or tail[2][0]!='return':raise ValueError('unsupported boolean getter suffix')
                args=tail[0][1].split(', ')
                if args[0]!=reg or args[2]!='+003h' or registers.get(args[1])!=1 or tail[1][1]!=args[1] or registers.get(tail[2][1])!=0 or mask!=1:raise ValueError('boolean getter is not masked-equals-one')
            return dict(offset=offset,size=1,shift=shift,mask=mask,boolean=boolean)
        else:raise ValueError('unsupported getter prefix '+op)
    raise ValueError('missing fixed getter')


def source_values(body,fields):
    required=max(row['offset']+1 for row in fields)
    if not isinstance(body,(bytes,bytearray)) or len(body)<required:raise ValueError('complete known source body required')
    return {row['sourceGetter']:bool((body[row['offset']]>>row['shift'])&row['mask']) if row['boolean'] else (body[row['offset']]>>row['shift'])&row['mask'] for row in fields}


def trace(apk,bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    images=[]
    for bank,pin in BANKS.items():
        raw=(bank_dir/('business-%02d-code-restored.dex'%bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('restored bank hash mismatch: %02d'%bank)
        images.append((bank,raw))
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    classes=None;callers=[];fingerprints={}
    for bank,raw in images:
        current={c.get_name():c for c in DEX(raw).get_classes()}
        if bank==5:classes=current
        for owner,cls in current.items():
            if owner in (ABNORMAL,BATTERY):continue
            for m in cls.get_methods():
                if not m.get_code():continue
                refs=[dict(sourceClass=target,method=o.get_output().split('->',1)[1].split('(',1)[0]) for o in m.get_instructions() if o.get_name().startswith('invoke-') for target in (ABNORMAL,BATTERY) if target+'->' in o.get_output()]
                if refs:callers.append(dict(bank=bank,className=owner,method=m.get_name(),descriptor=m.get_descriptor(),references=refs))
    def take(owner,name,descriptor=None):
        ms=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(ms)!=1 or not ms[0].get_code():raise ValueError('missing or ambiguous status method '+name)
        m=ms[0];fingerprints[(owner,name,m.get_descriptor())]=dict(className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    def require(ops,token):
        if not any(token in text for _,text in ops):raise ValueError('missing status evidence '+token)
    fields=[]
    for m in classes[ABNORMAL].get_methods():
        if m.get_name() in ('<clinit>','<init>','getInstance','doPack','isGimbalLocked'):continue
        fields.append(dict(sourceGetter=m.get_name(),**field_context(take(ABNORMAL,m.get_name()),ABNORMAL,m.get_descriptor()=='()Z')))
    if len(fields)!=21 or max(r['offset'] for r in fields)!=4:raise ValueError('abnormal getter inventory changed')
    lock=take(ABNORMAL,'isGimbalLocked')
    require(lock,'->isRollLocked()Z');require(lock,'->isPitchLocked()Z')
    if any('->isYawLocked()Z' in text for _,text in lock):raise ValueError('source composite now includes yaw')
    battery=field_context(take(BATTERY,'getCapacityPercentage'),BATTERY,False)
    if battery!=dict(offset=0,size=1,shift=0,mask=255,boolean=False):raise ValueError('battery getter changed')
    for owner in (ABNORMAL,BATTERY):
        for name in ('<init>','doPack'):take(owner,name)
        if classes[owner].get_superclassname()!='Ldji/midware/data/manager/P3/DataBase;' or any(m.get_name() in ('get','setRecData','setPushRecData','setPushRecPack') for m in classes[owner].get_methods()):raise ValueError('source model body path changed')
    base='Ldji/midware/data/manager/P3/DataBase;'
    for name in ('setPushRecPack','setPushRecData','setRecData'):take(base,name)
    require(take(base,'get','(I I Ljava/lang/Class; [I)Ljava/lang/Number;'),'BytesUtil;->getInt([B)I')
    for name,desc in [('getInt','([B)I'),('fillBytes','([B I)[B'),('arrayComb','([B [B)[B')]:take('Ldji/midware/util/BytesUtil;',name,desc)
    require(take('Ldji/midware/util/BytesUtil;','getInt','([B)I'),'ByteOrder;->LITTLE_ENDIAN ')
    take('Ldji/midware/data/packages/P3/RecvPack;','setBuffer')
    enum='Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;';entries=constructor_records(take(enum,'<clinit>'),enum)
    binding={k:entries[k]['arguments'] for k in ('GetPushAbnormalStatus','RobinPushBattery')}
    if binding['GetPushAbnormalStatus'][2]!=39 or binding['GetPushAbnormalStatus'][-1]!=ABNORMAL or binding['RobinPushBattery'][2]!=51 or binding['RobinPushBattery'][-1]!=BATTERY:raise ValueError('status command binding changed')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(k):v for k,v in BANKS.items()},appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,
        abnormalFields=fields,abnormalMinimumBodyBytes=5,sourceComposite=dict(isGimbalLocked='isRollLocked or isPitchLocked',includesYaw=False),batteryField=battery,sourceIntegerIsUnsignedByte=True,batterySourceDoesNotClamp=True,rawRequestBodyFramingEstablished=True,targetLayoutVerified=False,commandEnumArguments=binding,
        externalCallers=callers,methods=list(fingerprints.values()),remaining=['Model-specific bit meaning, current target notifications and firmware compatibility remain unverified.', 'Do not turn candidate lock/sleep/upgrading/pano flags into automatic motion or completion decisions.', 'Keep04:33 source battery distinct from0D:02 other-model battery and preserve255.', 'Banks1/7, residual stubs and dynamic paths remain outside scan.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d status fingerprints; %d caller methods; no sends.'%(len(r['methods']),len(r['externalCallers'])))

if __name__=='__main__':main()
