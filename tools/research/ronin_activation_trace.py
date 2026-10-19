#!/usr/bin/env python3
"""Audit COMMON activation source/version fields offline. No DUML or SDK sends."""
import argparse,hashlib,json,re
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS
ROOT='Ldji/midware/data/model/common/DataAbstractGetPushActiveStatus;'
GIMBAL='Ldji/midware/data/model/P3/DataGimbalActiveStatus;'
TYPE=ROOT[:-1]+'$TYPE;'
VERSION=ROOT[:-1]+'$DJIActiveVersion;'
DEVICE='Lcom/dji/activate/active/ActiveDeviceController;'
WEB='Lcom/dji/activate/active/ActiveWebController;'
COMMON='Ldji/midware/data/config/P3/CmdIdCommon$CmdIdType;'
QUERY='Ldji/midware/data/model/common/DataCommonActiveGetVer;'
VERSIONS={'Ver1_0':0,'Ver1_1':1,'Ver1_3':3,'Ver13':51,'OTHER':100}
TYPES={'GetVer':(0,0),'GET':(1,17),'SET':(2,18),'PUSH':(3,19),'FAIL':(4,20),'GetStatus':(5,49),'SetUerData':(6,51),'SetWebData':(6,55),'OTHER':(100,0)}
MISSING=object()


def constructor_types(descriptor):
    if not descriptor.startswith('(') or not descriptor.endswith(')V'):raise ValueError('constructor descriptor required')
    body=descriptor[1:-2];tokens=[];position=0
    while position<len(body):
        if body[position]==' ':position+=1;continue
        match=re.match(r'L[^;\s]+;|I|Z',body[position:])
        if not match:raise ValueError('unsupported constructor parameter type')
        tokens.append(match.group());position+=len(match.group())
    return tokens


def nullable_literal_enums(operations,owner,selected=None,allow_opaque_references=False):
    """Literal tracking only: explicit reference zero is null; unknown is never null."""
    regs={};records={}
    for op,text in operations:
        if op.startswith(('if-','goto')) or 'switch' in op:raise ValueError('conditional enum initializer')
        if op.startswith('const-string') or op=='const-class':
            reg,value=text.split(', ',1);regs[reg]=('string' if op.startswith('const-string') else 'class',value)
        elif op in ('const/4','const/16','const'):
            reg,value=text.split(', ',1);value=int(value)
            if not -2147483648<=value<=2147483647:raise ValueError('literal outside int32')
            regs[reg]=('int',value)
        elif op=='new-instance':
            reg,value=text.split(', ',1);regs[reg]=('object',value)
        elif op in ('move-object','move-object/from16','move-object/16','move','move/from16','move/16'):
            dest,src=text.split(', ');regs[dest]=regs.get(src,MISSING)
        elif op.startswith('invoke-direct') and owner+'-><init>(' in text:
            raw,descriptor=text.split(', '+owner+'-><init>',1);used=re.findall(r'v\d+',raw)
            if ' ... ' in raw:
                if len(used)!=2 or int(used[1][1:])<int(used[0][1:]):raise ValueError('invalid constructor register range')
                used=['v%d'%n for n in range(int(used[0][1:]),int(used[1][1:])+1)]
            if len(used)<2 or regs.get(used[0])!=('object',owner):raise ValueError('constructor receiver unresolved')
            label=regs.get(used[1],MISSING)
            if label is MISSING or label[0]!='string':raise ValueError('enum label unresolved')
            if selected is not None and label[1] not in selected:continue
            types=constructor_types(descriptor)
            if len(used)!=len(types)+1:raise ValueError('constructor arity unresolved')
            values=[];nulls=[];opaque=[]
            for index,(reg,typ) in enumerate(zip(used[1:],types)):
                value=regs.get(reg,MISSING)
                if value is MISSING:
                    if allow_opaque_references and typ.startswith('L') and typ not in ('Ljava/lang/String;','Ljava/lang/Class;'):
                        values.append({'unresolvedReferenceType':typ});opaque.append(index);continue
                    raise ValueError('unresolved literal register '+reg)
                kind,literal=value
                if typ in ('I','Z'):
                    if kind!='int' or (typ=='Z' and literal not in (0,1)):raise ValueError('nonliteral primitive argument')
                    values.append(literal)
                elif typ=='Ljava/lang/String;':
                    if kind!='string':raise ValueError('string argument unresolved')
                    values.append(literal)
                elif typ=='Ljava/lang/Class;' and kind=='class':values.append(literal)
                elif kind=='int' and literal==0:values.append(None);nulls.append(index)
                elif allow_opaque_references and typ not in ('Ljava/lang/String;','Ljava/lang/Class;'):
                    values.append({'unresolvedReferenceType':typ});opaque.append(index)
                else:raise ValueError('reference argument is neither literal class nor explicit null')
            if not values or type(values[0]) is not str or values[0] in records:raise ValueError('missing/duplicate enum label')
            records[values[0]]=dict(descriptor=descriptor,argumentTypes=types,arguments=values,explicitNullArgumentIndexes=nulls,unresolvedReferenceArgumentIndexes=opaque)
        elif op in ('move-result','move-result-object','sget-object','array-length','new-array'):regs[text.split(', ')[0]]=MISSING
        elif op.startswith(('sput-object','invoke-')) or op in ('return-void','aput-object'):pass
        else:raise ValueError('unsupported enum operation '+op)
    return records


def enum_literal_prefix(operations,owner):
    ends=[i for i,(op,text) in enumerate(operations) if op.startswith('invoke-static') and any(owner+'->'+name+'()' in text for name in ('$values','values'))]
    if not ends:raise ValueError('enum construction boundary missing')
    end=ends[0]
    if any(op.startswith('invoke-direct') and owner+'-><init>(' in text for op,text in operations[end:]):raise ValueError('constructor after enum construction boundary')
    return operations[:end]


def literal_switch_cases(operations,enum):
    result={}
    for i,(op,text) in enumerate(operations):
        if op!='sget-object' or enum+'->' not in text:continue
        reg=text.split(', ')[0];name=text.split('->',1)[1].split()[0];tail=operations[i+1:i+5]
        if len(tail)!=4 or tail[0]!=('invoke-virtual',reg+', '+enum+'->ordinal()I') or tail[1][0]!='move-result' or tail[2][0] not in ('const/4','const/16','const') or tail[3][0]!='aput':raise ValueError('unresolved enum switch assignment')
        value_reg,number=tail[2][1].split(', ');put=tail[3][1].split(', ')
        if put[0]!=value_reg or put[2]!=tail[1][1] or name in result:raise ValueError('ambiguous enum switch assignment')
        result[name]=int(number)
    return result


def source_type_value(name,version):
    if type(name) is not str or name not in TYPES or type(version) is not str or version not in VERSIONS:raise ValueError('explicit declared type and version names required')
    data,data1=TYPES[name]
    return data1 if data1 and version in ('Ver1_1','Ver1_3') else data


def source_set_layout(version,sn_byte_length):
    if type(version) is not str or version not in VERSIONS or type(sn_byte_length) is not int or not 0<=sn_byte_length<=2147483637:raise ValueError('explicit version and nonnegative Java-safe byte length required')
    old=version=='Ver1_0'
    return dict(sourceVersion=version,typeValue=source_type_value('SET',version),allocatedBytes=19 if old else sn_byte_length+10,snOffset=9 if old else 10,copiedSnBytes=min(sn_byte_length,10 if old else 16),snLengthByteOffset=None if old else 9,snLengthByteValue=None if old else min(sn_byte_length,16),trailingZeroBytes=(10-min(sn_byte_length,10)) if old else sn_byte_length-min(sn_byte_length,16),targetDeviceVerified=False)


def trace(apk,bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    images=[]
    for bank,pin in PREFIX_BANKS.items():
        raw=(bank_dir/('business-%02d-prefix-code-restored.dex'%bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('prefix bank hash mismatch: %02d'%bank)
        images.append((bank,raw))
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    classes={};methods={};callers=[];versions=[]
    def take(bank,owner,name,descriptor=None):
        ms=[m for m in classes[bank][owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(ms)!=1 or not ms[0].get_code():raise ValueError('missing/ambiguous activation method '+owner+name)
        m=ms[0];methods[(bank,owner,name,m.get_descriptor())]=dict(bank=bank,className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest())
        return [(i.get_name(),i.get_output()) for i in m.get_instructions()]
    def require(ops,*tokens):
        for token in tokens:
            if not any(token in text for _,text in ops):raise ValueError('missing activation evidence '+token)
    for bank,raw in images:
        current={c.get_name():c for c in DEX(raw).get_classes()}
        if bank in (1,5):classes[bank]=current
        for owner,c in current.items():
            for m in c.get_methods():
                if not m.get_code():continue
                refs=[];version_refs=[]
                for i in m.get_instructions():
                    if not i.get_name().startswith('invoke-'):continue
                    target=re.search(r'(L[^\s,]+;)->([^\s(]+)\(',i.get_output())
                    if not target:continue
                    target_owner,target_method=target.groups()
                    if target_owner==GIMBAL or (target_owner==DEVICE and target_method=='activeGimbal'):refs.append(dict(className=target_owner,method=target_method))
                    if target_method=='setVersion' and target_owner in (ROOT,GIMBAL):version_refs.append(dict(className=target_owner,method=target_method))
                if refs:callers.append(dict(bank=bank,className=owner,method=m.get_name(),descriptor=m.get_descriptor(),references=refs))
                if version_refs:versions.append(dict(bank=bank,className=owner,method=m.get_name(),descriptor=m.get_descriptor(),references=version_refs))
                if (refs or version_refs) and owner not in (ROOT,GIMBAL):
                    if bank not in classes:classes[bank]=current
                    take(bank,owner,m.get_name(),m.get_descriptor())
    enums=nullable_literal_enums(take(5,COMMON,'<clinit>'),COMMON,selected={'ActiveStatus'});binding=enums['ActiveStatus']
    if binding['arguments']!=['ActiveStatus',20,50,0,1,None] or binding['explicitNullArgumentIndexes']!=[5]:raise ValueError('COMMON ActiveStatus binding changed')
    cmdset='Ldji/midware/data/config/P3/CmdSet;';sets=nullable_literal_enums(enum_literal_prefix(take(5,cmdset,'<clinit>'),cmdset),cmdset,selected={'COMMON'},allow_opaque_references=True)
    if sets['COMMON']['arguments'][2]!=0:raise ValueError('COMMON command set changed')
    for owner in (COMMON,cmdset):
        for m in classes[5][owner].get_methods():
            if m.get_name() in ('<init>','value'):take(5,owner,m.get_name(),m.get_descriptor())
    types=nullable_literal_enums(take(5,TYPE,'<clinit>'),TYPE);vers=nullable_literal_enums(take(5,VERSION,'<clinit>'),VERSION)
    if {n:r['arguments'][2] for n,r in vers.items()}!=VERSIONS:raise ValueError('activation version values changed')
    if {n:tuple(r['arguments'][2:]+([0] if len(r['arguments'])==3 else [])) for n,r in types.items()}!=TYPES:raise ValueError('activation type values changed')
    for owner in (TYPE,VERSION):
        for m in classes[5][owner].get_methods():
            if m.get_name() in ('<init>','value','find'):take(5,owner,m.get_name(),m.get_descriptor())
    version_switch=literal_switch_cases(take(5,ROOT[:-1]+'$2;','<clinit>'),VERSION)
    if version_switch!={'Ver1_0':1,'Ver1_1':2,'Ver1_3':3}:raise ValueError('activation version switch changed')
    require(take(5,TYPE,'value','('+VERSION+')I'),'->data1 I','->ordinal()I','v3, v1, +00ch','v3, v1, +006h','v3, v1, +003h')
    for name in ('<init>','doPack','start','getVer','setDevice'):take(5,QUERY,name)
    query_switch=literal_switch_cases(take(5,QUERY[:-1]+'$1;','<clinit>'),'Ldji/midware/data/config/P3/DeviceType;')
    require(take(5,QUERY,'doPack'),TYPE+'->GetVer ',TYPE+'->value()I')
    require(take(5,QUERY,'setRecData'),GIMBAL+'->getInstance()',GIMBAL+'->setVersion(',VERSION+'->find(I)')
    require(take(5,QUERY,'start'),COMMON+'->ActiveStatus ','->timeOut I','->repeatTimes I','v1, 1000','v1, 2')
    require(take(5,GIMBAL,'getInstance'),'->Ver1_1 ','->setVersion(')
    require(take(5,GIMBAL,'start'),'->APP ','->GIMBAL ','->REQUEST ','->YES ','->NO ','CmdSet;->COMMON ',COMMON+'->ActiveStatus ')
    for name in ('<init>','<clinit>'):take(5,GIMBAL,name)
    for name in ('<init>','doPack','getActiveStatus','getYear','getMonth','getDay','getHour','getMin','getSecond','getSN','getTime','setPushRecData','getVersion','setVersion','setType','setActiveStatus','setSN','getRevertSn','getInvertSn'):
        take(5,ROOT,name)
    pack=take(5,ROOT,'doPack');require(pack,'->GET ','->SET ','->FAIL ','->Ver1_0 ','v1, 19','v1, 11','v2, 16','System;->arraycopy(')
    require(take(1,DEVICE,'activeGimbal'),'->SET ','->setActiveStatus(Z)','->setSN(','->setYear(','->setMonth(','->setDay(','->setHour(','->setMin(','->setSecond(','->start(')
    require(take(1,WEB,'<init>'),'OkHttpClient$Builder;->build()',GIMBAL+'->getInstance()')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(b):p for b,p in PREFIX_BANKS.items()},appCodeExecuted=False,liveUiExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,wholeAppRecovered=False,researchToolProvidesSdkInterface=False,sdkSendAdded=False,sdkReceiveAdded=False,hg724EntryEstablished=False,bleRouteVerified=False,activationPersistenceVerified=False,methods=sorted(methods.values(),key=lambda r:(r['bank'],r['className'],r['method'],r['descriptor'])),commonEnumEntryCount=len(enums),commonEnumScope=['ActiveStatus'],commandSetSourceBinding=sets['COMMON'],command=dict(commandSet=0,commandId=50,name='COMMON ActiveStatus',enumBinding=binding,receiverSource='GIMBAL',requestSource='APP',ackRequested=True,sourceEncryptNo=True,finalTransportEncryptionVerified=False,pushClassBindingInCommonEnum=None),sourceVersions=vers,sourceTypes=types,sourceVersionSwitch=version_switch,sourceVersionQuery=dict(bodyHex='00',sourceTimeoutMs=1000,sourceRepeatTimes=2,deviceTypeSwitch=query_switch,updatesSingletonVersionInSource=True,wireResponseOffsetVerified=False,sourceResendPolicyCopiedToSdk=False),typeValuesByVersion={v:{n:source_type_value(n,v) for n in TYPES} for v in VERSIONS},sourceGimbalSingletonInitialVersion='Ver1_1',actualSessionVersionVerified=False,sourceSetLayouts={v:[source_set_layout(v,n) for n in [0,10,16,17]] for v in VERSIONS},sourceResponse=dict(businessActiveBit=dict(offset=0,width=1,mask=1),yearOffset=1,yearWidth=2,snOld=dict(offset=8,bytes=10,batteryReceiverUsesInvertVariant=True),snOther=dict(lengthOffset=8,stringOffset=9,maxLength=16,oversizeSourceFallback='empty string'),wireOffsetsIndependentlyVerified=False,ackAndPushBusinessBodiesUnified=False,version13And14PushHandlersFullyAudited=False),directGimbalCallers=callers,versionSetterCallers=versions,networkVsDeviceWorkflowFullyAudited=False,remaining=['COMMON00:32 is a generic source candidate, not an HG724 BLE activation contract.','Singleton initial version does not prove current version; Ver1_3 and Ver13 are different source enums.','Source getter offsets are business-body offsets; do not assume BLE return-code stripping or notification layout.','SET/FAIL, server validation, binding and persistence are not exposed in SDK; no activation is sent.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d methods; COMMON00:32/versioned activation source only; no sends.'%len(r['methods']))
if __name__=='__main__':main()
