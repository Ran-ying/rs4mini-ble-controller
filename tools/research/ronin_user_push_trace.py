#!/usr/bin/env python3
"""Audit every fixed-layout user-parameter getter in the pinned App, offline."""
import argparse,hashlib,json,re
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_command_audit import DERIVED_SHA256
OWNER='Ldji/midware/data/model/P3/DataGimbalGetPushUserParams;'


def getter_context(operations):
    registers={}
    for i,(op,text) in enumerate(operations):
        if op in ('const/4','const/16','const'):
            reg,value=text.split(', ',1);registers[reg]=int(value)
        elif op=='const-class':
            reg,value=text.split(', ',1);registers[reg]=value
        elif op=='new-array':registers[text.split(', ')[0]]=None
        elif op=='invoke-virtual' and OWNER+'->get(I I Ljava/lang/Class; [I)' in text:
            args=re.findall(r'v\d+',text.split(', '+OWNER)[0])
            if len(args)!=5 or registers.get(args[3])!='Ljava/lang/Integer;':raise ValueError('unresolved getter arguments')
            offset,size=registers.get(args[1]),registers.get(args[2])
            if type(offset) is not int or offset<0 or size not in (1,2):raise ValueError('unsupported fixed getter context')
            tail=operations[i+1:]
            if len(tail)!=5 or tail[0][0]!='move-result-object':raise ValueError('unsupported getter result')
            reg=tail[0][1]
            expected=[('move-result-object',reg),('check-cast',reg+', Ljava/lang/Integer;'),('invoke-virtual',reg+', Ljava/lang/Integer;->intValue()I'),('move-result',reg),('return',reg)]
            if tail!=expected:raise ValueError('getter transforms raw integer')
            return dict(offset=offset,size=size)
        else:raise ValueError('unsupported getter prefix '+op)
    raise ValueError('missing integer getter')


def trace(apk,dex_path):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    raw=dex_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=DERIVED_SHA256:raise ValueError('restoration view hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    classes={c.get_name():c for c in DEX(raw).get_classes()};methods=[];fields=[]
    def record(m):
        if not m.get_code():raise ValueError('unreadable fixed getter')
        methods.append(dict(className=m.get_class_name(),method=m.get_name(),descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest()))
        return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    for m in classes[OWNER].get_methods():
        if m.get_name().startswith('get') and m.get_name()!='getInstance':fields.append(dict(sourceGetter=m.get_name(),**getter_context(record(m))))
    if len(fields)!=17 or max(r['offset']+r['size'] for r in fields)!=74:raise ValueError('fixed getter inventory changed')
    for name,descriptor,tokens in [('getInt','([B)I',('->fillBytes(','ByteOrder;->LITTLE_ENDIAN ')),('fillBytes','([B I)[B',('->arrayComb([B [B)[B',)),('arrayComb','([B [B)[B',('Ljava/lang/System;->arraycopy(',))]:
        m=next(m for m in classes['Ldji/midware/util/BytesUtil;'].get_methods() if m.get_name()==name and m.get_descriptor()==descriptor)
        operations=record(m)
        if any(not any(token in text for _,text in operations) for token in tokens):raise ValueError('integer helper changed')
        if name=='fillBytes' and operations!=[('array-length','v0, v1'),('sub-int/2addr','v2, v0'),('if-lez','v2, +008h'),('new-array','v2, v2, [B'),('invoke-static','v1, v2, Ldji/midware/util/BytesUtil;->arrayComb([B [B)[B'),('move-result-object','v1'),('return-object','v1')]:raise ValueError('zero extension changed')
        if name=='arrayComb':
            calls=[text for op,text in operations if op=='invoke-static']
            if calls!=['v3, v2, v0, v2, v1, Ljava/lang/System;->arraycopy(Ljava/lang/Object; I Ljava/lang/Object; I I)V','v4, v2, v0, v3, v1, Ljava/lang/System;->arraycopy(Ljava/lang/Object; I Ljava/lang/Object; I I)V']:raise ValueError('zero buffer append order changed')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,derivedSha256=DERIVED_SHA256,appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,
                sourceClass=OWNER,command='04:24',sourceFramingEvidence='protocol/research/ronin-subscription-evidence.json',
                sourceMinimumBytes=74,requestTypeRequired=True,encryptionAllowed=False,fields=fields,methods=methods,
                semantics='Raw unsigned 1/2 byte little-endian integers; source getter names, no units, range or enabled-bit inference.',
                unknownBytesRetained=True,partialPayloadZeroFillAllowed=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('apk','dex','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.dex);a.output.write_text(json.dumps(r,indent=2)+'\n');print('%d getter fields, %d fingerprints; no execution or sends.'%(len(r['fields']),len(r['methods'])))
if __name__=='__main__':main()
