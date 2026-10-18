#!/usr/bin/env python3
"""Static BLE service/packet-manager routing; no App, JNI, SDK or hardware execution."""
import argparse,hashlib,json,re
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_calibration_transport import DB,ENC,MANAGER,branch_target,source_receive_case
BLE='Ldji/midware/ble2/'
SERVICE=BLE+'BluetoothService;'
BLEMAN=BLE+'BleManager;'
CONNECTOR=BLE+'base/BleConnector;'
TRANSMITTER=BLE+'base/BleDataTransmitter;'
P3='Ldji/midware/data/manager/P3/'
MAIN=P3+'DJIPackManager;'
PROC=P3+'DataBaseProcessor;'
SM=P3+'ServiceManager;'
LINK='Ldji/midware/link/DJILinkDaemonService;'
TYPE='Ldji/midware/link/DJILinkType;'
FIELDS={'needCheckEncrypt','enabledSetDataEvent'}


def literal_boolean_writes(operations):
    """Local literal producers only; branches/unknown writes discard previous constants."""
    registers={};result=[]
    for index,(op,text) in enumerate(operations):
        args=text.split(', ')
        if op.startswith(('if-','goto')) or 'switch' in op:registers.clear();continue
        if op in ('const/4','const/16','const'):registers[args[0]]=int(args[1])
        elif op=='iput-boolean' and any('->'+field+' Z' in text for field in FIELDS):
            value=registers.get(args[0]);field=re.search(r'->(\w+) Z$',text)[1]
            if type(value) is not int or value not in (0,1):raise ValueError('unresolved boolean writer '+field)
            result.append(dict(instructionIndex=index,field=field,value=bool(value)))
        elif op in ('move','move/from16','move/16'):
            value=registers.get(args[1]);registers.pop(args[0],None)
            if value is not None:registers[args[0]]=value
        elif op.startswith(('invoke-','iput','sput','aput','return','monitor-','throw','fill-array-data')):pass
        elif args and re.fullmatch(r'v\d+',args[0]):
            registers.pop(args[0],None)
            if 'wide' in op:registers.pop('v'+str(int(args[0][1:])+1),None)
    return result


def link_switch_value(operations,name):
    matches=[]
    for i,(op,text) in enumerate(operations):
        if op!='sget-object' or TYPE+'->'+name+' '+TYPE not in text:continue
        if i+4>=len(operations):raise ValueError('incomplete link switch assignment')
        reg=text.split(', ')[0];invoke,result,literal,store=operations[i+1:i+5]
        if invoke!=('invoke-virtual',reg+', '+TYPE+'->ordinal()I') or result!=('move-result',reg) or literal[0] not in ('const/4','const/16','const') or store[0]!='aput':raise ValueError('unresolved link switch producer')
        producer,value=literal[1].split(', ');args=store[1].split(', ')
        if len(args)!=3 or args[0]!=producer or args[2]!=reg:raise ValueError('link switch register mismatch')
        matches.append(int(value))
    if len(matches)!=1:raise ValueError('missing/duplicate link case')
    return matches[0]


def fresh_ble_receive_case(command_set,command_id,flags,*,prior_old_state):
    """Explicit hypothetical packet bytes/state, not a measured connection."""
    return source_receive_case(command_set,command_id,flags,old_firmware_state=prior_old_state,need_check=True,enabled_event=True)


def trace(apk,bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    images={}
    for bank,pin in BANKS.items():
        raw=(bank_dir/('business-%02d-code-restored.dex'%bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('bank hash mismatch')
        images[bank]=raw
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    images={b:DEX(raw) for b,raw in images.items()};cs={c.get_name():c for c in images[5].get_classes()};methods={}
    def take(owner,name,descriptor=None):
        found=[m for m in cs[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(found)!=1 or not found[0].get_code():raise ValueError('missing/ambiguous BLE route method '+owner+name)
        m=found[0];methods[(owner,name,m.get_descriptor())]=dict(bank=5,className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());rows=[];offset=0
        for ins in m.get_instructions():rows.append((offset,ins.get_name(),ins.get_output()));offset+=ins.get_length()
        return rows
    def ops(rows):return [(op,text) for _,op,text in rows]
    def require(rows,*tokens):
        for token in tokens:
            if not any(token in text for _,_,text in rows):raise ValueError('missing route reference '+token)
    if cs[MAIN].get_superclassname()!=MANAGER or any(m.get_name()=='parse' for m in cs[MAIN].get_methods()):raise ValueError('main manager parse inheritance changed')
    require(take(SERVICE,'<init>'),MAIN+'->getInstance()',SERVICE+'->packManager '+MAIN)
    require(take(MAIN,'getInstance'),'v2, Main',MAIN+'-><init>(Ljava/lang/String;)V')
    main=take(MAIN,'<init>');require(main,MANAGER+'-><init>()V')
    base=take(MANAGER,'<init>');require(base,ENC+'->getInstance()',MANAGER+'->encryManager '+ENC,MANAGER[:-1]+'$2;-><init>(',MANAGER+'->simpleComsumer ')
    if [r for r in literal_boolean_writes(ops(base)) if r['field']=='needCheckEncrypt'][0]['value'] is not True:raise ValueError('base encryption gate changed')
    if [r for r in literal_boolean_writes(ops(main)) if r['field']=='enabledSetDataEvent'][0]['value'] is not True:raise ValueError('main event gate changed')
    require(take(DB,'<init>','(Z)V'),ENC+'->getInstance()',DB+'->encryManager '+ENC)
    require(take(ENC,'getInstance'),ENC+'->instance '+ENC,ENC+'-><init>()V')
    require(take(SERVICE,'start'),BLEMAN+'->setDataListener('+BLE+'base/BleDataReceiveListener;)V')
    require(take(BLEMAN,'setDataListener'),CONNECTOR+'->setDataListener(')
    require(take(CONNECTOR,'setDataListener'),CONNECTOR+'->mDataListener ')
    require(take(CONNECTOR,'onCharacteristicChanged'),'BluetoothGattCharacteristic;->getValue()[B',CONNECTOR+'->mDataListener ',BLE+'base/BleDataReceiveListener;->onDataReceived([B)V')
    require(take(SERVICE,'onDataReceived'),SERVICE+'->packManager '+MAIN,'v1, 0',MAIN+'->parse([B I I)V')
    require(take(MANAGER,'parse'),'SimpleComsumer;->put(Landroid/os/Message;)V')
    require(take(MANAGER[:-1]+'$2;','invoke'),MANAGER+'->-$$Nest$mparseOne(')
    require(take(MANAGER,'-$$Nest$mparseOne'),MANAGER+'->parseOne()Z')
    take(MANAGER,'parseOne')
    require(take(SERVICE,'onConnect'),TYPE+'->BLE ',LINK+'->setLinkType(')
    switch=take(LINK[:-1]+'$2;','<clinit>');case=link_switch_value(ops(switch),'BLE')
    if case!=3:raise ValueError('reviewed BLE link case changed')
    rows=take(LINK,'setLinkType');by={off:(op,text) for off,op,text in rows}
    if by.get(80)!=('const/4','v3, 3') or by.get(82,('',))[0]!='if-eq' or branch_target(82,by[82][1])!=110 or branch_target(44,by[44][1])!=52:raise ValueError('BLE selection/alive gate changed')
    require(rows,LINK+'->isAlive Z',SERVICE+'->getInstance()',LINK+'->changeTo(')
    require(take(LINK,'changeTo'),SM+'->changeTo(',LINK+'->curServiceInterface ')
    require(take(SM,'changeTo'),SM+'->mInterface ')
    require(take(DB,'submitTask'),PROC+'->sendCmd(')
    require(take(PROC,'sendCmd'),'Handler;->sendMessage(',PROC+'->putPackToSpecialChannelToSend(')
    require(take(PROC[:-1]+'$MyHandler;','handleMessage'),PROC+'->-$$Nest$mrealSendOnePack(')
    require(take(PROC,'-$$Nest$mrealSendOnePack'),PROC+'->realSendOnePack(')
    require(take(PROC,'realSendOnePack'),SM+'->sendmessage(')
    require(take(SM,'sendmessage'),'DJIServiceInterface;->sendmessage(')
    require(take(SERVICE,'sendmessage'),P3+'BlockUtils;->isNeedShieldPack(',SERVICE+'->sendBuffer(')
    require(take(SERVICE,'sendBuffer'),'SendPack;->buffer [B',BLEMAN+'->getMaxDataLength()I',BLEMAN+'->sendData([B)V')
    require(take(BLEMAN,'getMaxDataLength'),CONNECTOR+'->getMaxDataLength()I')
    require(take(BLEMAN,'sendData'),TRANSMITTER+'->sendData([B)V')
    require(take(TRANSMITTER,'sendData'),TRANSMITTER+'->generateReq([B)Z')
    require(take(TRANSMITTER,'generateReq'),TRANSMITTER+'->addRequestToQueue(')
    require(take(TRANSMITTER,'executeQueue'),TRANSMITTER+'->sendNonBlockingWriteRequest(')
    require(take(TRANSMITTER,'sendNonBlockingWriteRequest'),CONNECTOR+'->sendData([B)Z')
    require(take(CONNECTOR,'sendData'),'BluetoothGattCharacteristic;->setValue([B)Z','BluetoothGatt;->writeCharacteristic(')
    require(take(CONNECTOR,'initWriteCharcteristic'),'BluetoothGattCharacteristic;->setWriteType(I)V')
    # Upgrade mode is a source gate, not an SDK feature or actual device state.
    shield=take(P3+'BlockUtils;','isNeedShieldPack');require(shield,TYPE+'->BLE ',BLEMAN+'->isInUpgradeMode()Z')
    writers=[]
    for bank,dex in images.items():
        for c in dex.get_classes():
            for m in c.get_methods():
                if not m.get_code():continue
                operations=[(i.get_name(),i.get_output()) for i in m.get_instructions()]
                if not any(op=='iput-boolean' and any('->'+f+' Z' in text for f in FIELDS) for op,text in operations):continue
                writers.append(dict(bank=bank,className=c.get_name(),method=m.get_name(),descriptor=m.get_descriptor(),writes=literal_boolean_writes(operations),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest()))
    expected={(MANAGER,'needCheckEncrypt',True),(P3+'DJIArPackManager;','needCheckEncrypt',False),(P3+'DJIFlightLogPackManager;','needCheckEncrypt',False),(P3+'DJINotSyncPackManager;','enabledSetDataEvent',True),(MAIN,'enabledSetDataEvent',True)}
    actual={(r['className'],w['field'],w['value']) for r in writers for w in r['writes']}
    if actual!=expected or len(writers)!=5 or any(r['method']!='<init>' for r in writers):raise ValueError('direct policy field writers changed')
    return dict(apkSha256=APK_SHA256,restoredBanks=BANKS,methods=sorted(methods.values(),key=lambda r:(r['className'],r['method'],r['descriptor'])),directPolicyFieldWriters=writers,
        sourceBlePolicy=dict(managerClass=MAIN,parseInheritedFrom=MANAGER,needCheckEncrypt=True,enabledSetDataEvent=True,encryptionSingletonSharedWithDataBase=True,sourceRouteResolved=True,actualSessionStateVerified=False),
        sourceReceiveRoute=['BleConnector.onCharacteristicChanged','mDataListener','BluetoothService.onDataReceived','DJIPackManager.parse inherited','SimpleComsumer queue','DJIPackManagerBase$2.invoke','parseOne'],
        sourceSendRoute=['DataBase.submitTask','DataBaseProcessor queue/realSendOnePack','ServiceManager.mInterface.sendmessage','BluetoothService.sendmessage/sendBuffer','BleManager.sendData','BleDataTransmitter queue','BleConnector.sendData','BluetoothGatt.writeCharacteristic'],
        sourceLinkSelection=dict(linkType='BLE',switchCaseValue=case,requiresAliveDaemon=True,selectedService=SERVICE),
        scope=dict(scannedBanks=sorted(BANKS),unrestoredBanks=[1,7],reflectionOrNativeFieldWritesExcluded=False,appOrJniExecuted=False,liveBleOrHardwareTested=False,peerEncryptionAcceptanceVerified=False),
        remaining=['Static BLE route and constructor policy are resolved, not live firmware/session encryption state.','Callbacks, queue scheduling, actual source gate values and peer acceptance require separate evidence.','Upgrade shield/connection gates can prevent dispatch; this audit is not an end-to-end delivery guarantee.','No JNI encryption implementation, calibration SDK trigger or physical completion/abort proof added.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d route methods, %d direct policy writers; no live device proof'%(len(r['methods']),len(r['directPolicyFieldWriters'])))
if __name__=='__main__':main()
