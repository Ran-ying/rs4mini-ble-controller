#!/usr/bin/env python3
"""Trace balance-test routing and duplicate metadata in the pinned App, offline."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_command_audit import DERIVED_SHA256
from ronin_settings_trace import named_keys, OWNER, BASE
from ronin_model_trace import enum_entry

MANAGER='Ldji/midware/data/manager/P3/DJIGimbalParamInfoManager;'
MODEL='Ldji/midware/data/model/P3/'


def matching_records(records, name):
    """Keep duplicates in source order; never silently apply unique-name lookup."""
    result=[dict(resourceOrdinal=i, **{k:r[k] for k in ('name','index','typeID','size','minValue','maxValue')})
            for i,r in enumerate(records) if r.get('name')==name]
    if not result:
        raise ValueError('missing named balance metadata')
    if any((r['index'],r['typeID'],r['size'])!=(37,0,1) for r in result):
        raise ValueError('balance record layout changed')
    return result


def ordinal_enum(operations, owner):
    registers, entries = {}, []
    for op, text in operations:
        if op.startswith('const-string'):
            reg,value=text.split(', ',1);registers[reg]=value
        elif op in ('const/4','const/16','const'):
            reg,value=text.split(', ',1);registers[reg]=int(value)
        elif op=='invoke-direct' and owner+'-><init>(Ljava/lang/String; I)V' in text:
            regs=re.findall(r'v\d+',text.split(', '+owner)[0])
            if len(regs)!=3:raise ValueError('unsupported ordinal enum constructor')
            label,ordinal=(registers.get(r) for r in regs[1:])
            if not isinstance(label,str) or type(ordinal) is not int:raise ValueError('unresolved ordinal enum')
            entries.append(dict(name=label,ordinal=ordinal))
        elif op in ('new-instance','move-result-object'):
            registers[text.split(', ')[0]]=None
        elif op in ('sput-object','invoke-static','return-void'):
            pass
        else:raise ValueError('unsupported ordinal enum instruction: '+op)
    if len({r['name'] for r in entries})!=len(entries):raise ValueError('duplicate enum name')
    return entries


def trace(apk, dex_path):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:
        raise ValueError('APK hash mismatch')
    raw=dex_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=DERIVED_SHA256:
        raise ValueError('restoration view hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    classes={c.get_name():c for c in DEX(raw).get_classes()}
    def method(owner, name, descriptor=None):
        matches=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or descriptor==m.get_descriptor())]
        if len(matches)!=1 or not matches[0].get_code():
            raise ValueError('expected one readable method: '+owner+name)
        return matches[0]
    def ops(m):return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    def require(m, token):
        if not any(token in s for _,s in ops(m)):raise ValueError('missing source reference: '+token)
    enum=method(OWNER,'<clinit>')
    key=named_keys(ops(enum))['BALANCE_TEST']
    if key!={'name':'balance_test','getter':MODEL+'DataGimbalGetUserParams;'}:
        raise ValueError('balance key route changed')
    with zipfile.ZipFile(str(apk)) as z:resource=z.read('res/DB.json')
    records=matching_records(json.loads(resource),key['name'])
    if [(r['minValue'],r['maxValue']) for r in records]!=[(0,1),(0,255)]:
        raise ValueError('expected both conflicting balance ranges in order')
    chain=[]
    name=BASE+'DJIGimbalHG724Abstraction;'
    while name.startswith(BASE):
        cls=classes[name];chain.append(name)
        if name.endswith(('HG724Abstraction;','HG702Abstraction;')) and any(m.get_name()=='startGimbalBalanceTest' for m in cls.get_methods()):
            raise ValueError('model overrides balance start')
        name=cls.get_superclassname()
    if chain[:3]!=[BASE+'DJIGimbal'+x+'Abstraction;' for x in ('HG724','HG702','Ronin2')]:
        raise ValueError('model inheritance changed')
    start=method(BASE+'DJIGimbalRonin2Abstraction;','startGimbalBalanceTest')
    require(start,OWNER+'->BALANCE_TEST ')
    require(start,'->setRonin2CommonUserParam(')
    if ('const/16','v1, 64') not in ops(start):raise ValueError('balance request value changed')
    setter=method(BASE+'DJIGimbalRonin2Abstraction;','setRonin2CommonUserParam')
    require(setter,'DataGimbalSetUserParams;')
    loader=method(MANAGER,'readToMemory')
    for token in ('V_JsonUtil;->getList(', 'List;->iterator()', 'Iterator;->next()', 'HashMap;->put('):require(loader,token)
    loadrun=method(MANAGER[:-1]+'$1;','run');require(loadrun,'R$raw;->gimbal_param_infos ')
    event=method(BASE+'DJIGimbalRonin2Abstraction;','onEvent3BackgroundThread','(Ldji/midware/data/model/P3/DataGimbalGetUserParams;)V')
    at={};offset=0
    for instruction in event.get_instructions():
        at[offset]=(instruction.get_name(),instruction.get_output());offset+=instruction.get_length()
    expected={0x55c:('and-int/lit16','v2, v11, 192'),0x560:('shr-int/lit8','v2, v2, 6'),
              0x588:('and-int/lit8','v8, v11, 48'),0x59c:('and-int/lit8','v9, v11, 12')}
    if any(at.get(k)!=v for k,v in expected.items()):raise ValueError('balance bit extraction changed')
    for label in ('RollTestResult','PitchTestResult','YawTestResult','BalanceTestStatus'):require(event,label)
    statusowner='Ldji/common/gimbal/BalanceTestStatus;'
    statusinit=method(statusowner,'<clinit>')
    statuses=[enum_entry(ops(statusinit),statusowner,label) for label in ('DEFAULT','TESTING','FINISH','ERROR')]
    if [r['value'] for r in statuses]!=[0,1,2,3]:raise ValueError('balance status values changed')
    resultowner='Ldji/common/gimbal/BalanceTestResult;'
    resultinit=method(resultowner,'<clinit>')
    results=ordinal_enum(ops(resultinit),resultowner)
    if results!=[dict(name=n,ordinal=i) for i,n in enumerate(('PASS','MARGINAL','FAIL','UNKNOWN'))]:raise ValueError('result enum order changed')
    selected=[enum,start,setter,loader,loadrun,event,statusinit,resultinit,method(MANAGER,'read')]
    for model,names in [('DataGimbalSetUserParams',('doPack','start')),('DataGimbalGetUserParams',('doPack','setRecData','start'))]:
        for name in names:selected.append(method(MODEL+model+';',name))
    methods=[dict(className=m.get_class_name(),method=m.get_name(),descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),
                  instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest()) for m in selected]
    return dict(schemaVersion=1,apkSha256=APK_SHA256,derivedSha256=DERIVED_SHA256,resourceSha256=hashlib.sha256(resource).hexdigest(),
                appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,sdkEncapsulationComplete=False,
                inheritance=chain,parameterKey=key,matchingResourceRecords=records,methods=methods,statusEnums=statuses,resultEnums=results,
                sourceFacts=dict(startCommand='04:0F',startValue=64,candidatePayloadHex='250140',readCommand='04:10',candidateReadHex='25',
                                 sourceStartDoesNotCallBalanceAdjust40=True,duplicateNameMap='ordered list iteration inserts by name into HashMap; later successful insertion replaces earlier',
                                 duplicateRangesRequireExplicitHandling=True,resultStatusMask=192,resultStatusShift=6,
                                 resultAxes={'roll':dict(mask=48,shift=4),'pitch':dict(mask=12,shift=2),'yaw':dict(mask=3,shift=0)},
                                 resultEnumeration='two-bit field minus one indexes PASS/MARGINAL/FAIL; zero is invalid, not PASS',
                                 physicalStopAndCompletionUnverified=True))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','dex','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.dex);a.output.write_text(json.dumps(r,indent=2)+'\n')
    print('%d balance metadata records, %d source method fingerprints; no SDK/hardware execution.'%(len(r['matchingResourceRecords']),len(r['methods'])))

if __name__=='__main__':main()
