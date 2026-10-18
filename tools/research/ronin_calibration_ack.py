#!/usr/bin/env python3
"""04:08 base-table ACK/business mapping; static parsing only, no vendor or SDK execution."""
import argparse,hashlib,json
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_sensor_calibration import AUTO,ENUM,auto_calibration_response_body
from ronin_subscription_trace import constructor_records
from ronin_program_receive import source_payload_view,delivery_paths,program_policy,RECV,TABLE,GIMBAL,MANAGER,BASE
from ronin_calibration_transport import branch_target
PROC='Ldji/midware/data/manager/P3/DataBaseProcessor;'
CALL=BASE[:-1]+'$3;'
CCODE='Ldji/midware/data/config/P3/Ccode;'
CMDSET='Ldji/midware/data/config/P3/CmdSet;'


def calibration_ack_view(flags,payload):
    """Stateless conditional base-table ACK view, not a live transaction/result cache."""
    view=source_payload_view(flags,payload,needs_ccode=True)
    if not view['isAck']:raise ValueError('ACK response required for calibration ACK view')
    body=bytes.fromhex(view['businessBodyHex']);complete=len(body)>=2
    return dict(view,businessComplete=complete,calibration=auto_calibration_response_body(body) if complete else None,sourceCallbackReportsSuccess=view['returnCode']==0,requestAssociationVerified=False,physicalCompletionVerified=False)


def source_processor_key(command_set,command_id,sequence):
    for value,maximum in ((command_set,255),(command_id,255),(sequence,65535)):
        if type(value) is not int or not 0<=value<=maximum:raise ValueError('explicit uint8 command and uint16 sequence required')
    value=(command_set<<24)|(command_id<<16)|sequence
    return ((value+2**31)%2**32)-2**31


def check_receive_offsets(rows):
    by={offset:(op,text) for offset,op,text in rows}
    expected={242:('const/16','v4, 11'),270:('const/16','v4, 12'),266:('iput','v1, v7, '+RECV+'->ccode I')}
    for offset,pair in expected.items():
        if by.get(offset)!=pair:raise ValueError('return-code/body offset producer changed')
    for off,op,target in ((246,'if-ne',274),(254,'if-eqz',274),(280,'if-lez',302)):
        if by.get(off,('',))[0]!=op or branch_target(off,by[off][1])!=target:raise ValueError('payload extraction branch changed')


def trace(apk,sdk):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    raw=sdk.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BANKS[5]:raise ValueError('restored bank hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    cs={c.get_name():c for c in DEX(raw).get_classes()};methods={}
    def take(owner,name,descriptor=None):
        found=[m for m in cs[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(found)!=1 or not found[0].get_code():raise ValueError('missing/ambiguous calibration ACK method '+owner+name)
        m=found[0];methods[(owner,name,m.get_descriptor())]=dict(bank=5,className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());rows=[];offset=0
        for i in m.get_instructions():rows.append((offset,i.get_name(),i.get_output()));offset+=i.get_length()
        return rows
    def ops(rows):return [(op,text) for _,op,text in rows]
    def require(rows,*tokens):
        for token in tokens:
            if not any(token in text for _,_,text in rows):raise ValueError('missing calibration ACK reference '+token)
    records=constructor_records(ops(take(ENUM,'<clinit>')),ENUM);policy=program_policy(records['AutoCalibration'])
    if policy!=dict(name='AutoCalibration',commandId=8,isBlock=False,isMix=True,modelClass=AUTO):raise ValueError('base calibration binding changed')
    if ops(take(ENUM,'isNeedCcode'))!=[('const/4','v0, 1'),('return','v0')]:raise ValueError('base gimbal ccode rule changed')
    require(take(GIMBAL,'getCurCmdIdValues'),ENUM+'->values()')
    for name in ('isNeedCcode','isMix','isBlock'):require(take(TABLE,name),'CmdIdInterface;->'+name+'(')
    require(take(RECV,'isNeedCcode'),CMDSET+'->cmdIdClass()',TABLE+'->isNeedCcode(I)Z')
    receive=take(RECV,'setBuffer');check_receive_offsets(receive);require(receive,'->cmdType I','->data [B','v5, v5, 7')
    code=constructor_records(ops(take(CCODE,'<clinit>')),CCODE)
    if code['OK']['arguments'][2]!=0 or code['SUCCEED']['arguments'][2]!=1:raise ValueError('callback return-code enums changed')
    call=take(CALL,'call','()Ljava/lang/Integer;');require(call,CCODE+'->OK ',CCODE+'->SUCCEED ',CMDSET+'->CAMERA ',BASE+'->setRecData([B)V',BASE+'->setRecPack(',BASE+'->-$$Nest$mcallbackSuccess(',BASE+'->-$$Nest$mcallBackFailure(')
    by={offset:(op,text) for offset,op,text in call}
    if by[48][0]!='if-nez' or branch_target(48,by[48][1])!=184 or by[72][0]!='if-ne' or branch_target(72,by[72][1])!=102:raise ValueError('GIMBAL success/failure callback branch changed')
    require(take(BASE,'sendPackResult'),BASE+'->setRecvPack(',CALL+'-><init>(')
    if ops(take(BASE,'setRecData'))!=[('iput-object','v1, v0, '+BASE+'->_recData [B'),('return-void','')]:raise ValueError('business data setter changed')
    for name in ('getType','getStatus'):require(take(AUTO,name),AUTO+'->get(I I Ljava/lang/Class; [I)')
    require(take(BASE,'setPushRecPack'),'Pack;->data [B',BASE+'->setPushRecData([B)V')
    require(take(MANAGER,'setMsg'),TABLE+'->isMix(I)Z',TABLE+'->isBlock(I)Z',PROC+'->setMsg(',BASE+'->setPushRecPack(')
    key=ops(take(PROC,'getKey'))
    expected=[('iget','v0, v3, Ldji/midware/data/packages/P3/Pack;->cmdSet I'),('shl-int/lit8','v0, v0, 24'),('iget','v1, v3, Ldji/midware/data/packages/P3/Pack;->cmdId I'),('shl-int/lit8','v1, v1, 16'),('or-int/2addr','v0, v1'),('iget','v3, v3, Ldji/midware/data/packages/P3/Pack;->seq I'),('or-int/2addr','v3, v0'),('return','v3')]
    if key!=expected:raise ValueError('source processor correlation key changed')
    require(take(PROC,'setMsg'),PROC+'->getKey(','ConcurrentHashMap;->containsKey(','v2, 12','Handler;->sendMessage(')
    # Reflection-loaded command-table alternatives remain separately scoped.
    require(take(CMDSET,'getExtraCmdSetInterface'),'->forName(','->newInstance()')
    require(take(CMDSET,'<init>','(Ljava/lang/String; I I Ldji/midware/data/config/P3/DJICmdSetBase;)V'),'->getExtraCmdSetInterface(','->cls ')
    return dict(apkSha256=APK_SHA256,bankSha256=BANKS[5],methods=sorted(methods.values(),key=lambda r:(r['className'],r['method'],r['descriptor'])),baseCommandPolicy=policy,
        mapping=dict(ackCcodeInRawPayload=0,ackBusinessPartInRawPayload=1,ackBusinessStatusInRawPayload=2,requestBusinessPartInRawPayload=0,requestBusinessStatusInRawPayload=1,baseNeedsCcode=True,emptyBusinessDoesNotAssignNewSourceData=True),
        callback=dict(gimbalSuccessReturnCode=0,cameraOnlyAlternateSuccess=1,businessSuccessStatus=1,successCallbackDoesNotCheckBusinessStatus=True,failureCallbackAlsoStoresBusinessData=True),
        mixedPaths=delivery_paths(is_block=False,is_mix=True),sourceProcessor=dict(keyFields=['cmdSet','cmdId','sequence'],ackBitInKey=False,endpointsInKey=False,matchingMapEntryOnlyQueuesHandlerMessage12=True,fullTransactionBehaviorVerified=False),
        scope=dict(parsedBanks=[5],unrestoredBanks=[1,7],actualExtensionSelectionVerified=False,vendorCodeExecuted=False,hardwareTested=False,sdkInterfaceAdded=False,physicalCompletionVerified=False),
        remaining=['Base-table wire mapping is established; reflection-loaded alternatives and actual target frames remain unverified.','Do not copy weaker source key matching: SDK still requires session, ACK bit, endpoints, command and sequence.','Return-code success, complete business bytes and source SUCCESS are distinct; none proves current physical completion.','Short/empty business view is explicitly incomplete, not the source fallback PROCESSING or a fresh cached result.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','sdk','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.sdk);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d ACK methods; base-table 04:08 mapping only'%len(r['methods']))
if __name__=='__main__':main()
