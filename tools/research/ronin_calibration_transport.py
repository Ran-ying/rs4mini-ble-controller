#!/usr/bin/env python3
"""Pinned calibration packet/conditional encryption audit; no SDK or vendor execution."""
import argparse,hashlib,json,re
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_sensor_calibration import AUTO
from ronin_subscription_trace import constructor_records
DB='Ldji/midware/data/manager/P3/DataBase;'
ENC='Ldji/midware/data/manager/P3/DJIEncryManager;'
MANAGER='Ldji/midware/data/manager/P3/DJIPackManagerBase;'
PACK='Ldji/midware/data/packages/P3/Pack;'
SEND='Ldji/midware/data/packages/P3/SendPack;'
CONFIG='Ldji/midware/data/config/P3/'
PARSE_SHA='776b32b742970dbc45dfd9130ca113ab2bb089d82a57019093a000cae35cd775'


def uint8(value):
    if type(value) is not int or not 0<=value<=255:raise ValueError('explicit uint8 required')
    return value


def source_need_encrypt(command_set,command_id):
    """Offline source predicate; not firmware support or automatic negotiation."""
    uint8(command_set);uint8(command_id)
    return command_set!=0 and not (command_set==2 and command_id in (16,17,112,113))


def source_send_case(command_set,command_id,*,old_firmware_state):
    if type(old_firmware_state) is not bool:raise ValueError('explicit source session boolean required')
    need=source_need_encrypt(command_set,command_id)
    return dict(sourceNeedEncrypt=need,sourceWouldEncrypt=not old_firmware_state and need,deviceModeVerified=False)


def source_receive_case(command_set,command_id,flags,*,old_firmware_state,need_check,enabled_event):
    """command_set/id are bytes at predicate entry, possibly ciphertext; never decrypted here."""
    uint8(flags);source_need_encrypt(command_set,command_id)
    if any(type(v) is not bool for v in (old_firmware_state,need_check,enabled_event)):raise ValueError('explicit source booleans required')
    state=old_firmware_state;decrypt=False
    if need_check:
        if enabled_event and flags&7==3:state=False;decrypt=True
        elif source_need_encrypt(command_set,command_id):state=True
    return dict(sourceOldFirmwareState=state,sourceWouldCallNativeDecrypt=decrypt,deviceModeVerified=False)


def branch_target(offset,text):
    match=re.search(r'([+-])([0-9a-f]+)h$',text)
    if not match:raise ValueError('explicit code-unit branch displacement required')
    return offset+(1 if match[1]=='+' else -1)*2*int(match[2],16)


def check_need_branches(rows):
    by={offset:(op,text) for offset,op,text in rows}
    for offset,op,target in ((44,'if-eq',116),(60,'if-ne',112),(76,'if-ne',116),(84,'if-eq',116),(92,'if-eq',116),(100,'if-eq',116),(108,'if-eq',116)):
        if offset not in by or by[offset][0]!=op or branch_target(offset,by[offset][1])!=target:raise ValueError('encryption predicate branch changed')
    for offset,pair in {112:('const/4','v3, 1'),114:('return','v3'),116:('const/4','v3, 0'),118:('return','v3')}.items():
        if by.get(offset)!=pair:raise ValueError('encryption predicate return changed')


def command_set_values(operations,wanted):
    registers={};result={};owner=CONFIG+'CmdSet;'
    for op,text in operations:
        args=text.split(', ')
        if op.startswith(('if-','goto')) or 'switch' in op:
            if set(result)==set(wanted):break
            raise ValueError('conditional command-set constructor')
        if op.startswith('const-string'):registers[args[0]]=args[1]
        elif op in ('const/4','const/16','const'):registers[args[0]]=int(args[1])
        elif op.startswith('invoke-direct') and owner+'-><init>(' in text:
            raw=text.split(', '+owner)[0];regs=re.findall(r'v\d+',raw)
            if ' ... ' in raw:regs=['v%d'%i for i in range(int(regs[0][1:]),int(regs[-1][1:])+1)]
            if len(regs)<4:raise ValueError('unsupported command-set constructor')
            label=registers.get(regs[1]);value=registers.get(regs[3])
            if label in wanted:
                if len(regs)!=5:raise ValueError('unsupported selected command-set constructor')
                if label in result or type(value) is not int:raise ValueError('unresolved/duplicate command-set value')
                result[label]=value
        elif op.startswith(('invoke-','sput','return')):pass
        elif args and re.fullmatch(r'v\d+',args[0]):registers.pop(args[0],None)
    if set(result)!=set(wanted):raise ValueError('missing command-set values')
    return result


def trace(apk,bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    images={}
    for bank,expected in BANKS.items():
        raw=(bank_dir/('business-%02d-code-restored.dex'%bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('restored bank hash mismatch')
        images[bank]=raw
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    images={b:DEX(raw) for b,raw in images.items()};classes={c.get_name():c for c in images[5].get_classes()};methods={}
    def take(owner,name,descriptor=None):
        found=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(found)!=1 or not found[0].get_code():raise ValueError('missing/ambiguous transport method '+owner+name)
        m=found[0];row=dict(bank=5,className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());methods[(owner,name,m.get_descriptor())]=row
        rows=[];offset=0
        for ins in m.get_instructions():rows.append((offset,ins.get_name(),ins.get_output()));offset+=ins.get_length()
        return rows
    def ops(rows):return [(op,text) for _,op,text in rows]
    def require(rows,*tokens):
        for token in tokens:
            if not any(token in text for _,_,text in rows):raise ValueError('missing transport reference '+token)
    enums={}
    for suffix,names in [('DeviceType',{'APP':2,'GIMBAL':4}),('DataConfig$CMDTYPE',{'REQUEST':0}),('DataConfig$NEEDACK',{'YES':2}),('DataConfig$EncryptType',{'NO':0,'SIMPLE':3}),('CmdSet',{'COMMON':0,'CAMERA':2,'GIMBAL':4})]:
        owner=CONFIG+suffix+';';rows=ops(take(owner,'<clinit>'))
        if suffix=='CmdSet':values=command_set_values(rows,names)
        else:
            records=constructor_records(rows,owner);values={name:records[name]['arguments'][2] for name in names}
        if values!=names:raise ValueError('transport enum values changed')
        enums[suffix]=values
    if classes[AUTO].get_superclassname()!=DB:raise ValueError('calibration superclass changed')
    for name in ('<init>','doPack','start'):
        rows=take(AUTO,name);require(rows,*(('->getSendData()[B',SEND+'-><init>()V',AUTO+'->start(Ldji/midware/data/packages/P3/SendPack;') if name=='start' else ()))
        if name=='start':require(rows,'DeviceType;->APP ','DeviceType;->GIMBAL ','CMDTYPE;->REQUEST ','NEEDACK;->YES ','EncryptType;->NO ')
        if any('->setReceiverId(' in text for _,_,text in rows):raise ValueError('calibration now overrides address')
    ctor=take(DB,'<init>','()V');require(ctor,DB+'-><init>(Z)V')
    ctor=take(DB,'<init>','(Z)V');require(ctor,'v1, -1','v1, v3, '+DB+'->receiverID I','v1, v3, '+DB+'->senderID I')
    root=take(PACK,'<init>');require(root,'Ljava/lang/Object;-><init>()V')
    child=take(SEND,'<init>');require(child,PACK+'-><init>()V')
    if not any(f.get_name()=='receiverId' and f.get_descriptor()=='I' for f in classes[PACK].get_fields()):raise ValueError('receiverId field changed')
    if any('->receiverId ' in text or '->senderId ' in text for _,_,text in root+child):raise ValueError('pack endpoint IDs no longer Java-zero defaults')
    take(DB,'getSendData');take(DB,'setReceiverId','(I)Ldji/midware/data/manager/P3/DataBase;')
    for name,desc in [('preprocessPack',None),('start','(Ldji/midware/data/packages/P3/SendPack; Ldji/midware/interfaces/DJIDataCallBack; Z)V')]:
        rows=take(DB,name,desc);require(rows,'->receiverID I','v1, -1','v0, v1, +004h','->receiverId I','->getSendData()[B',SEND+'->doPack()V',ENC+'->isOldFirmware()Z',ENC+'->isNeedEncrypt([B)Z',ENC+'->simpleEncrypt([B I)[B','EncryptType;->SIMPLE ',SEND+'->reCrc()V')
    take(DB,'start','(Ldji/midware/data/packages/P3/SendPack; Ldji/midware/interfaces/DJIDataCallBack;)V')
    packed=take(SEND,'doPack');require(packed,'->receiverId I','->receiverType I','->senderId I','v6, 5','->cmdType I','->isNeedAck I','->encryptType I')
    for pair in [('shl-int/2addr','v1, v6'),('or-int/2addr','v1, v7'),('shl-int/lit8','v6, v7, 5')]:
        if pair not in ops(packed):raise ValueError('packet endpoint/flag packing changed')
    require(take(ENC,'<init>'),'v0, 1','v0, v1, '+ENC+'->isOldFirmware Z')
    need=take(ENC,'isNeedEncrypt');check_need_branches(need);require(need,'->COMMON ','->CAMERA ','v0, 16','v0, 17','v0, 112','v0, 113')
    require(take(ENC,'isEncryptData'),'v0, 8','v2, v2, 7','v0, 3')
    require(take(ENC,'encryptData'),'v0, 8','v1, v1, 3')
    for name in ('simpleEncrypt','simpleDecrypt'):require(take(ENC,name),'v0, v0, -11','v2, 9','GroudStation;->native_rcDataDeal([B I)[B')
    take(ENC,'isOldFirmware');take(ENC,'setIsOldFirmware')
    take(MANAGER,'<init>');parse=take(MANAGER,'parseOne');by={off:(op,text) for off,op,text in parse}
    if methods[(MANAGER,'parseOne','()Z')]['instructionSha256']!=PARSE_SHA:raise ValueError('reviewed receive method changed')
    for off,value in ((4,'v1, 0'),(72,'v4, 1')):
        if by.get(off)!=('const/4',value):raise ValueError('receive boolean producer changed')
    for off,target in ((180,276),(184,250),(200,250),(262,276)):
        if branch_target(off,by[off][1])!=target:raise ValueError('receive gate target changed')
    require(parse,'->needCheckEncrypt Z','->enabledSetDataEvent Z','v0, v1, '+ENC+'->setIsOldFirmware(Z)V','v0, v4, '+ENC+'->setIsOldFirmware(Z)V','->simpleDecrypt([B I)[B')
    callers=[]
    for bank,dex in images.items():
        for c in dex.get_classes():
            for m in c.get_methods():
                if not m.get_code():continue
                count=sum(ins.get_name().startswith('invoke-') and ENC+'->setIsOldFirmware(Z)V' in ins.get_output() for ins in m.get_instructions())
                if count:callers.append(dict(bank=bank,className=c.get_name(),method=m.get_name(),descriptor=m.get_descriptor(),invokeCount=count,instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest()))
    if len(callers)!=1 or callers[0]['className']!=MANAGER or callers[0]['method']!='parseOne' or callers[0]['invokeCount']!=2:raise ValueError('direct setter callers changed')
    return dict(apkSha256=APK_SHA256,restoredBanks=BANKS,methods=sorted(methods.values(),key=lambda r:(r['className'],r['method'],r['descriptor'])),enumValues=enums,
        freshCalibration=dict(commandSet=4,commandId=8,senderType=2,receiverType=4,packReceiverIdDefault=0,packSenderIdDefault=0,dataBaseReceiverOverrideDefault=-1,preConditionalFlags=64,sourceNeedsEncrypt=True,defaultSourceOldFirmwareState=True),
        conditionalSend=dict(oldTrue='skip encryption',oldFalse='GIMBAL requires native transform then SIMPLE flag3 and CRC rewrite',commonExcluded=True),
        conditionalReceive=dict(outerGate='needCheckEncrypt',decryptGate='enabledSetDataEvent and flags low3 ==3',disabledEventStillRunsPredicate=True,simpleFlag=3,simpleSetsOldFirmware=False,otherwisePredicateTrueSetsOldFirmware=True,nativeTransformRange='offset9 through length-3 inclusive; includes command set/id',sequenceSource='bytes6..7'),
        directSetterCallers=callers,scope=dict(scannedBanks=sorted(BANKS),unrestoredBanks=[1,7],vendorCodeExecuted=False,hardwareTested=False,actualBleManagerPolicyVerified=False,cryptoAlgorithmImplemented=False),
        remaining=['Source oldFirmware is mutable session policy, not measured firmware age or model identity.','Fresh-object/default source path does not prove actual BLE manager switches or peer encryption acceptance.','JNI transform implementation, live exchange and physical calibration completion/cancellation remain unverified.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d transport methods; conditional session policy only'%len(r['methods']))
if __name__=='__main__':main()
