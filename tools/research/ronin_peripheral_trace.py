#!/usr/bin/env python3
"""Pinned full peripheral getter catalog and pure body analysis; no SDK, DUML or vendor execution."""
import argparse,hashlib,json,re,struct
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_subscription_trace import constructor_records
from ronin_program_receive import program_policy,ENUM,RECV,MANAGER,BASE
MODEL='Ldji/midware/data/model/P3/DataGimbalSetPushPeripheralStatus;'
TYPE=MODEL[:-1]+'$DataType;'
BYTES='Ldji/midware/util/BytesUtil;'


def getter_spec(name,descriptor,ops,types):
    """Recognize only manually audited straight-line integer/float/GPS patterns or fixed bool branch."""
    if descriptor=='()V':
        if ops!=[('return-void','')]:raise ValueError('unexpected nonempty void getter')
        return None
    if name=='getGimbalControlStateBad':
        expected=['invoke-direct','move-result','and-int/lit8','const/4','if-ne','const/4','return','const/4','return']
        if [o for o,_ in ops]!=expected or MODEL+'->getControlState()I' not in ops[0][1] or ops[2][1]!='v0, v0, 3' or ops[3][1]!='v1, 2' or ops[4][1]!='v0, v1, +004h' or ops[5][1]!='v0, 1' or ops[7][1]!='v0, 0':raise ValueError('unresolved control-state bool pattern')
        return dict(sourceGetter=name,sourceType='ControlState',sourceId=types['ControlState'],conversion='masked3-equals2')
    if len(ops)<4 or ops[0][0]!='sget-object':raise ValueError('missing source DataType getter binding')
    enum=re.fullmatch(r'(v\d+), '+re.escape(TYPE)+r'->(\w+) '+re.escape(TYPE),ops[0][1])
    if not enum or enum[2] not in types:raise ValueError('unresolved getter enum')
    if ops[1][0]!='invoke-direct' or not re.fullmatch(r'v\d+, '+enum[1]+', '+re.escape(MODEL)+r'->getIntValue\('+re.escape(TYPE)+r'\)I',ops[1][1]) or ops[2][0]!='move-result':raise ValueError('unresolved getter int source')
    value=ops[2][1];tail=ops[3:]
    if descriptor=='()I' and tail==[('return',value)]:conversion='int32'
    elif descriptor=='()F' and len(tail)==4:
        cast,constant,divide,ret=tail
        match=re.fullmatch(r'(v\d+), (1092616192|1120403456)',constant[1])
        if cast!=('int-to-float',value+', '+value) or constant[0]!='const/high16' or not match or divide!=('div-float/2addr',value+', '+match[1]) or ret!=('return',value):raise ValueError('unresolved float scaling order')
        conversion='float32-div'+('10' if match[2]=='1092616192' else '100')
    elif descriptor=='()D' and len(tail)==4:
        constant,divide,cast,ret=tail;match=re.fullmatch(r'(v\d+), 1000000',constant[1])
        if constant[0]!='const' or not match or divide!=('div-int/2addr',value+', '+match[1]) or cast!=('int-to-double',value+', '+value) or ret!=('return-wide',value):raise ValueError('unresolved GPS integer division order')
        conversion='int-div1000000-to-double'
    else:raise ValueError('unsupported getter shape '+name)
    return dict(sourceGetter=name,sourceType=enum[2],sourceId=types[enum[2]],conversion=conversion)


def source_int(payload):
    if not isinstance(payload,(bytes,bytearray)) or len(payload)>=128:raise ValueError('bounded source record required')
    if len(payload) in (1,2):return int.from_bytes(payload,'little',signed=True)
    return int.from_bytes((bytes(payload[:4])+bytes(4))[:4],'little',signed=True)


def source_conversion(value,conversion):
    if type(value) is not int or not -2**31<=value<2**31:raise ValueError('source signed int32 required')
    if conversion=='int32':return value
    if conversion=='masked3-equals2':return value&3==2
    if conversion=='int-div1000000-to-double':return float((abs(value)//1000000)*(-1 if value<0 else 1))
    if conversion in ('float32-div10','float32-div100'):
        f=lambda n:struct.unpack('<f',struct.pack('<f',n))[0]
        return f(f(value)/int(conversion.split('div')[1]))
    raise ValueError('unrecognized source conversion')


def peripheral_body(body,catalog):
    if not isinstance(body,(bytes,bytearray)) or not body:raise ValueError('source flag required')
    result=dict(rawFlag=body[0],sourceRecordBranchSelected=body[0]==1,records=[],bodyHex=body.hex())
    if body[0]!=1:return result
    offset=1
    while offset<len(body):
        if len(body)-offset<2:raise ValueError('truncated peripheral header')
        tag,length=body[offset:offset+2];end=offset+2+length
        if length>=128 or end>len(body):raise ValueError('source signed length or truncated record')
        payload=body[offset+2:end];signed=tag if tag<128 else tag-256
        types=[r['name'] for r in catalog['types'] if r['sourceId']==signed]
        getters=[r for r in catalog['getters'] if r['sourceId']==signed]
        value=source_int(payload) if getters else None
        views=[dict(sourceType=r['sourceType'],sourceGetter=r['sourceGetter'],conversion=r['conversion'],value=source_conversion(value,r['conversion'])) for r in getters]
        result['records'].append(dict(rawTag=tag,sourceSignedTag=signed,length=length,payloadHex=payload.hex(),sourceTypes=types,ambiguous=len(types)>1,sourceInt32=value,sourceViews=views));offset=end
    return result


def trace(apk,bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    raw=(bank_dir/'business-05-code-restored.dex').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BANKS[5]:raise ValueError('restored bank hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    classes={c.get_name():c for c in DEX(raw).get_classes()};methods={}
    def take(owner,name,descriptor=None):
        found=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(found)!=1 or not found[0].get_code():raise ValueError('missing or ambiguous peripheral source '+name)
        m=found[0];methods[(owner,name,m.get_descriptor())]=dict(className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());return [(i.get_name(),i.get_output()) for i in m.get_instructions()]
    def require(ops,*tokens):
        for token in tokens:
            if not any(token in text for _,text in ops):raise ValueError('missing peripheral source token '+token)
    enums=constructor_records(take(TYPE,'<clinit>'),TYPE);take(TYPE,'<init>')
    types=[dict(name=n,ordinal=r['arguments'][1],sourceId=r['arguments'][2]) for n,r in enums.items()]
    ids={r['name']:r['sourceId'] for r in types};getters=[];empty=[]
    for m in classes[MODEL].get_methods():
        if not m.get_name().startswith('get') or m.get_descriptor() not in ('()I','()F','()D','()Z','()V'):continue
        spec=getter_spec(m.get_name(),m.get_descriptor(),take(MODEL,m.get_name(),m.get_descriptor()),ids)
        if spec:getters.append(spec)
        else:empty.append(m.get_name())
    if len(types)!=46 or len(getters)!=43 or empty!=['getPMotorCurrent','getRMotorCurrent','getYMototBattery']:raise ValueError('source getter coverage changed')
    collisions=[dict(sourceId=i,sourceTypes=[r['name'] for r in types if r['sourceId']==i]) for i in sorted(set(ids.values())) if sum(r['sourceId']==i for r in types)>1]
    if collisions!=[dict(sourceId=21,sourceTypes=['YGyroOut','PAcceOut'])]:raise ValueError('source tag collision changed')
    policy=program_policy(constructor_records(take(ENUM,'<clinit>'),ENUM)['SetPushPeripheralStatus'])
    if policy!=dict(name='SetPushPeripheralStatus',commandId=102,isBlock=False,isMix=False,modelClass=MODEL):raise ValueError('base peripheral policy changed')
    if classes[MODEL].get_superclassname()!=BASE or any(m.get_name() in ('setPushRecPack','setRecData','isChanged') for m in classes[MODEL].get_methods()):raise ValueError('source receive override path changed')
    for name in ('<init>','getIntValue','getData','getDataByType','doPack','start','setPushRecData'):take(MODEL,name)
    for name,descriptor in [('getSignedInt','(B)S'),('getShort','([B)S'),('getInt','([B)I'),('getLong','([B)J'),('fillBytes','([B I)[B'),('arrayComb','([B [B)[B')]:take(BYTES,name,descriptor)
    require(take(BYTES,'fillBytes','([B I)[B'),'->arrayComb([B [B)[B')
    require(take(BYTES,'arrayComb','([B [B)[B'),'Ljava/lang/System;->arraycopy(')
    if take(BYTES,'getSignedInt','(B)S')!=[('int-to-short','v0, v0'),('return','v0')]:raise ValueError('signed byte getter changed')
    for name,descriptor in [('getShort','([B)S'),('getInt','([B)I'),('getLong','([B)J')]:require(take(BYTES,name,descriptor),'ByteOrder;->LITTLE_ENDIAN ')
    require(take(MODEL,'getIntValue'),'v2, 1','v2, 2','v2, 8','Ljava/lang/Short;','Ljava/lang/Long;','->intValue()I')
    pushed=take(MODEL,'setPushRecData')
    if pushed[0][0]!='invoke-super' or BASE+'->setPushRecData([B)V' not in pushed[0][1]:raise ValueError('source parent/event order changed')
    require(pushed,'mPushDataMap','Ljava/lang/System;->arraycopy(')
    if sum(op=='aget-byte' for op,_ in pushed)!=3:raise ValueError('source signed record reads changed')
    for name in ('setPushRecPack','setPushRecData','setRecData','isChanged'):take(BASE,name)
    take(RECV,'setBuffer');take(RECV,'isNeedCcode');take(MANAGER,'setMsg')
    if take(ENUM,'isNeedCcode')!=[('const/4','v0, 1'),('return','v0')]:raise ValueError('base ccode rule changed')
    catalog=dict(types=types,getters=getters)
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256=BANKS[5],appCodeExecuted=False,targetDeviceVerified=False,modelLayoutVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,methods=list(methods.values()),catalog=catalog,emptySourceGetters=empty,typesWithoutNumericGetter=[r['name'] for r in types if not any(g['sourceType']==r['name'] for g in getters)],sourceTagCollisions=collisions,basePolicy=policy,
        envelope=dict(priorBasePathEvidence='protocol/research/ronin-program-receive-evidence.json',requestBusinessOffsetInRawPayload=0,ackBusinessOffsetInRawPayload=1,baseNeedsCcode=True,requestSourceFlag=1,actualExtensionSelectionVerified=False,targetRawBleLayoutVerified=False),
        integerReading=dict(oneByteSigned=True,twoByteSignedLittleEndian=True,otherWidths='zero-pad tail if shorter than four; first four little-endian signed bits otherwise; long intValue equals low32',zeroLengthPresentRecordSourceValue=0,missingRecordIsNotZeroInOfflineView=True,sourceSignedLengthHighBitRejected=True),
        semantics=dict(sourceMapRetainsOtherRecords=True,sourceBaseCanPostBeforeDerivedParsing=True,offlineViewKeepsDuplicatesUnknownAndCollisionCandidates=True,sourceGpsIntegerDivisionBeforeDouble=True,sourceCollisionNotRepaired=True,physicalReferenceFrameVerified=False))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d source fingerprints; %d types, %d getter views.'%(len(r['methods']),len(r['catalog']['types']),len(r['catalog']['getters'])))
if __name__=='__main__':main()
