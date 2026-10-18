#!/usr/bin/env python3
"""HG724 handheld factory/key/Setter binding; no reflection, App or hardware execution."""
import argparse,hashlib,json,re
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_stick_trace import MOBILE,SET
from ronin_key_support import KEY,PROPS,normalize_annotations,select_source_keys
LAYER='Ldji/sdksharedlib/hardware/DJISDKCacheHWAbstractionLayer;'
SWITCH=LAYER[:-1]+'$3;'
PLATFORM='Ldji/midware/component/DJIComponentManager$PlatformType;'
ARRAY=SWITCH+'->$SwitchMap$dji$midware$component$DJIComponentManager$PlatformType [I'
CATALOG='Ldji/sdksharedlib/keycatalog/HandheldControllerKeys;'
ROOT='Ldji/sdksharedlib/hardware/abstractions/handheldcontroller/HandheldControllerBaseAbstraction;'
HW='Ldji/sdksharedlib/hardware/abstractions/DJISDKCacheHWAbstraction;'
INIT='(Ljava/lang/String; I Ldji/sdksharedlib/store/DJISDKCacheStoreLayer; Ldji/sdksharedlib/hardware/abstractions/DJISDKCacheHWAbstraction$OnValueChangeListener;)V'
SETTER='Ldji/sdksharedlib/hardware/abstractions/Setter;'
ODD='setIsInternalAndExternalMicroPhonesEnabled'

def platform_cases(operations):
    values={};pending=None;result={}
    for op,text in operations:
        args=text.split(', ')
        if op!='move-result' and not op.startswith('invoke-'):pending=None
        if op.startswith(('if-','goto')) or 'switch' in op:raise ValueError('conditional switch initializer')
        if op=='sget-object':values[args[0]]=('field',args[1])
        elif op.startswith('invoke-'):
            pending=None
            if PLATFORM+'->ordinal()I' in text:
                v=values.get(args[0]);prefix=PLATFORM+'->'
                if not isinstance(v,tuple) or len(v)!=2 or v[0]!='field' or not v[1].startswith(prefix):raise ValueError('unresolved platform enum')
                pending=('ordinal',v[1].split('->')[1].split()[0])
        elif op=='move-result':values[args[0]]=pending;pending=None
        elif op in ('move','move/from16','move/16','move-object','move-object/from16','move-object/16'):
            v=values.get(args[1]);values.pop(args[0],None)
            if v is not None:values[args[0]]=v
        elif op in ('const/4','const/16','const'):values[args[0]]=int(args[1])
        elif op=='new-array':values[args[0]]=('allocated',None)
        elif op=='sput-object':
            if args[1]==ARRAY and values.get(args[0])==('allocated',None):values[args[0]]=('field',ARRAY)
        elif op=='aput' and values.get(args[1])==('field',ARRAY):
            number=values.get(args[0]);ordinal=values.get(args[2])
            if type(number) is not int or not isinstance(ordinal,tuple) or len(ordinal)!=2 or ordinal[0]!='ordinal':raise ValueError('unresolved platform switch assignment '+repr((text,number,ordinal)))
            if ordinal[1] in result:raise ValueError('duplicate platform case')
            result[ordinal[1]]=number
        elif op.startswith(('return','aput','sput')):pass
        elif args and re.fullmatch(r'v\d+',args[0]):
            values.pop(args[0],None)
            if 'wide' in op:values.pop('v'+str(int(args[0][1:])+1),None)
    return result

def factory_choice(platform,cases,targets):
    if type(platform) is not str:raise ValueError('explicit source platform name required')
    target=targets.get(cases.get(platform),46)
    choices={46:None,48:MOBILE,60:'Ldji/sdksharedlib/hardware/abstractions/handheldcontroller/HandheldControllerAbstraction;'}
    if target not in choices:raise ValueError('unreviewed handheld factory target')
    return dict(sourcePlatform=platform,sourcePlatformKnown=platform in cases,selectedClass=choices[target],factoryOffset=target,actualPlatformVerified=False,reflectionSucceededVerified=False)

def trace(apk,sdk):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    raw=sdk.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BANKS[5]:raise ValueError('restored bank hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    dex=DEX(raw);cm=dex.get_class_manager();cs={c.get_name():c for c in dex.get_classes()};methods={}
    def take(owner,name,descriptor=None):
        ms=[m for m in cs[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(ms)!=1 or not ms[0].get_code():raise ValueError('missing/ambiguous binding method '+name)
        m=ms[0];methods[(owner,name,m.get_descriptor())]=dict(className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());return m
    def ops(m):return [(i.get_name(),i.get_output()) for i in m.get_instructions()]
    def require(m,*tokens):
        rows=ops(m)
        for token in tokens:
            if not any(token in text for _,text in rows):raise ValueError('missing binding reference '+token)
    def annotation(a):return dict(typeName=dex.get_cm_type(a.get_type_idx()),elements={dex.get_cm_string(e.get_name_idx()):value(e.get_value()) for e in a.get_elements()})
    def value(v):
        r=v.get_value();t=v.get_value_type()
        return [value(x) for x in r.get_values()] if t==0x1c else annotation(r) if t==0x1d else r
    def aset(offset):return [annotation(x.get_annotation_item().get_annotation()) for x in cm.get_annotation_set_item(offset).get_annotation_off_item()]
    def directory(owner):return cm.get_annotations_directory_item(cs[owner].get_annotations_off())
    cases=platform_cases(ops(take(SWITCH,'<clinit>')))
    factory=take(LAYER,'addHandheldControllerAbstraction');encoded={};off=0
    for i in factory.get_instructions():encoded[off]=i;off+=i.get_length()
    switches=[(o,i) for o,i in encoded.items() if i.get_name()=='packed-switch']
    if len(switches)!=1:raise ValueError('one handheld factory switch required')
    position,ins=switches[0];payload=encoded[position+2*ins.get_ref_off()];targets={k:position+2*t for k,t in zip(payload.get_values(),payload.get_targets())}
    if position!=40 or set(targets.values())!={46,48,60} or cases.get('HG724')!=25:raise ValueError('reviewed handheld factory branch changed')
    require(factory,'getPlatformType()',ARRAY,'v2, 1',MOBILE,'->addAbstraction(')
    if encoded[46].get_name()!='return-void' or encoded[48].get_output()!='v0, '+MOBILE:raise ValueError('factory case meaning changed')
    selected=factory_choice('HG724',cases,targets)
    if selected['selectedClass']!=MOBILE:raise ValueError('HG724 no longer selects Mobile handheld')
    require(take(LAYER,'updateHandheldController'),'->removeAbstraction(','->addHandheldControllerAbstraction()V')
    require(take(LAYER,'onEvent3BackgroundThread','('+PLATFORM+')V'),'->updateHandheldController()V')
    add=take(LAYER,'addAbstraction','(I Ljava/lang/String; Ljava/lang/Class;)V');require(add,'Class;->newInstance()','v0, v1','v0, v7, +03ch',HW+'->init(')
    chain=[];owner=MOBILE
    while owner in cs:
        if owner in chain:raise ValueError('cyclic handheld chain')
        chain.append(owner);owner=cs[owner].get_superclassname()
    if ROOT not in chain or HW not in chain:raise ValueError('handheld superclass chain changed')
    for owner in chain:
        for m in cs[owner].get_methods():
            if m.get_name() in ('init','initializeComponentCharacteristics') and m.get_code():take(owner,m.get_name(),m.get_descriptor())
    require(take(ROOT,'initializeComponentCharacteristics'),CATALOG,'Object;->getClass()',ROOT+'->addCharacteristics(')
    require(take(HW,'init',INIT),'->initializeAllCharacteristics()V','->createMethodMap()V')
    take(HW,'createMethodMap');take(HW,'addCharacteristics','(Ljava/lang/Class; Ljava/lang/Class;)V')
    defaults_annotation=next(annotation(a) for a in cs[KEY]._get_annotation_type_ids() if dex.get_cm_type(a.get_type_idx())=='Ldalvik/annotation/AnnotationDefault;')
    defaults={k:defaults_annotation['elements']['value']['elements'].get(k) for k in PROPS}
    field_rows={r.get_field_idx():r.get_annotations_off() for r in directory(CATALOG).get_field_annotations()};fields=[]
    for field in cs[CATALOG].get_fields():
        literal=field.get_init_value();literal=literal.get_value() if literal is not None else None
        if literal!='StickGimbalControlEnabled':continue
        annotations=aset(field_rows[field.get_field_idx()]);entries,invalid=normalize_annotations(annotations,defaults)
        if invalid:raise ValueError('invalid handheld key annotations')
        selection=select_source_keys(entries,MOBILE,set(chain))
        fields.append(dict(fieldName=field.get_name(),literalKeyName=literal,rawAnnotations=annotations,entries=entries,selection=selection))
    if len(fields)!=1 or not fields[0]['selection']['sourceSupport'] or not fields[0]['selection']['selectionUnambiguous']:raise ValueError('source key support changed')
    setter=take(MOBILE,ODD);index=setter.get_method_idx();bindings=[]
    for row in directory(MOBILE).get_method_annotations():
        if row.get_method_idx()==index:bindings.extend(a for a in aset(row.get_annotations_off()) if a['typeName']==SETTER)
    if bindings!=[dict(typeName=SETTER,elements=dict(value='StickGimbalControlEnabled'))]:raise ValueError('actual Setter key changed')
    require(setter,SET+'->getInstance()',SET+'->setHandheldStickControlEnabled(Z)',SET+'->start(')
    for name in ('onSuccess','onFailure'):take(MOBILE[:-1]+'$3;',name)
    for name in ('<init>','doPack','setHandheldStickControlEnabled','start'):take(SET,name)
    return dict(apkSha256=APK_SHA256,bankSha256=BANKS[5],methods=sorted(methods.values(),key=lambda r:(r['className'],r['method'],r['descriptor'])),platformCases=cases,factoryTargets={str(k):v for k,v in targets.items()},hg724Factory=selected,selectedClassChain=chain,keyFields=fields,setter=dict(methodName=ODD,annotationKey='StickGimbalControlEnabled',declaringClass=MOBILE,sourceCommand='04:58',sourceBooleanBody=True,methodNameDoesNotDefineMicrophoneSemantics=True),factoryArgument=dict(count=1,ordinaryLoopFirstIndex=0,argumentOneIsNotReceiverId=True),scope=dict(parsedBanks=[5],unrestoredBanks=[1,7],sourceHg724FactoryAndSetterPathEstablished=True,actualPlatformVerified=False,reflectionExecuted=False,reflectionAndMethodInvocationSucceededVerified=False,hardwareTested=False,vendorCodeExecuted=False,sdkSendAdded=False),remaining=['PlatformType HG724 is a conditional source case, not live model identity.','Factory reflection, key/method registration and actual invocation were not executed.','No current device58 acceptance, meaning, persistence, ACK extras or57 request association are proven.','Raw key types array is retained; method-name mismatch does not introduce microphone control.'])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','sdk','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.sdk);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d methods; HG724 conditional handheld factory/Setter path established'%len(r['methods']))
if __name__=='__main__':main()
