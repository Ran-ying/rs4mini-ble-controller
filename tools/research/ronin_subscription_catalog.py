#!/usr/bin/env python3
"""Pinned named subscription registration and explicit-case body views; never SDK/DUML/vendor execution."""
import argparse,hashlib,json,re,zipfile
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_subscription_trace import constructor_records
from ronin_subscription_payloads import subscription_group_body
from ronin_settings_trace import OWNER,unique_record
from ronin_program_entry import direct_return
IMPL='Ldji/common/gimbal/Ronin2SubscribeIMPL;'
TYPE='Ldji/midware/data/model/P3/DataGimbalSetPushPeripheralStatus$DataType;'
CMD='Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;'
COMPONENT='Ldji/midware/component/DJIComponentManager$GimbalComponentType;'
SWITCH=IMPL[:-1]+'$2;'
SUB='Ldji/midware/data/model/P3/DataGimbalSubscribeParams;'
USER='Ldji/midware/data/model/P3/DataGimbalGetUserParams;'
MOTOR='Ldji/midware/data/model/P3/DataGimbalRoninGetUserParams;'


def registers(text,owner):
    prefix=text.split(', '+owner+'->',1)[0];values=re.findall(r'v\d+',prefix)
    if ' ... ' in prefix:
        if len(values)!=2:raise ValueError('unresolved invoke register range')
        return ['v%d'%i for i in range(int(values[0][1:]),int(values[1][1:])+1)]
    return values


def resolve_base(entry,parameters):
    args=entry['arguments']
    if len(args) not in (3,4,5):raise ValueError('unrecognized BaseCommand constructor')
    push=args[4] if len(args)==5 else USER
    if push not in (USER,MOTOR):raise ValueError('unresolved registered push class')
    result=dict(commandId=16 if push==USER else 50,parameterName=args[2] if len(args)==3 else args[3],channelSource='resource-if-present' if len(args)==3 else 'explicit-base',missingMetadataChannel=0 if len(args)==3 else None)
    result['channel']=unique_record(parameters,args[2])['index'] if len(args)==3 else args[2]
    if type(result['channel']) is not int or not 0<=result['channel']<=255:raise ValueError('source channel outside byte-sized body subset')
    return result


def registrations(instructions,base_commands,types,commands,parameters):
    """Literal/field/enum-return propagation only; retain supported if intervals instead of executing them."""
    values={};pending=None;rows=[];intervals=[]
    for i,row in enumerate(instructions):
        op,text=row['op'],row['text']
        if op.startswith(('if-','goto','packed-switch','sparse-switch')):
            if op!='if-eqz' or i<2 or instructions[i-2]['op']!='invoke-direct' or IMPL+'->isSupportStateSince4Gen()Z' not in instructions[i-2]['text'] or instructions[i-1]['op']!='move-result' or text.split(', ')[0]!=instructions[i-1]['text'] or row.get('target',0)<=row['offset']:raise ValueError('unresolved constructor control flow')
            intervals.append((row['offset'],row['target']));continue
        if op.startswith('const-string'):dest,value=text.split(', ',1);values[dest]=value
        elif op in ('const','const/4','const/16'):dest,value=text.split(', ',1);values[dest]=int(value)
        elif op=='sget-object':
            dest,field=text.split(', ',1);owner,name=field.split('->',1);values[dest]=dict(enum=owner,name=name.split()[0])
        elif op=='iget' and TYPE+'->mId I' in text:
            dest,source,_=text.split(', ',2);enum=values.get(source)
            if not isinstance(enum,dict) or enum.get('enum')!=TYPE or enum.get('name') not in types:raise ValueError('unresolved DataType id')
            values[dest]=types[enum['name']]['arguments'][2]
        elif op.startswith('move-object') or op=='move':dest,source=text.split(', ');values[dest]=values.get(source)
        elif op.startswith('move-result'):values[text]=pending;pending=None
        elif op.startswith('invoke-'):
            pending=None
            if CMD+'->value()I' in text:
                regs=registers(text,CMD);enum=values.get(regs[0]) if len(regs)==1 else None
                if not isinstance(enum,dict) or enum.get('enum')!=CMD or enum.get('name') not in commands:raise ValueError('unresolved source command value')
                pending=commands[enum['name']]['arguments'][2]
            elif IMPL+'->put(' in text:
                regs=registers(text,IMPL);args=[values.get(r) for r in regs[1:]]
                if not args or type(args[0]) is not str or any(r['key']==args[0] for r in rows):raise ValueError('unresolved or duplicate registration key')
                result=dict(key=args[0],sourceCondition='isSupportStateSince4Gen' if any(start<row['offset']<end for start,end in intervals) else None)
                if text.endswith('->put(Ljava/lang/String; I I)V') and len(args)==3 and all(type(x) is int and 0<=x<=255 for x in args[1:]):result.update(commandId=args[1],channel=args[2],channelSource='explicit-direct',baseCommand=None,parameterName=None,missingMetadataChannel=None)
                elif text.endswith('->put(Ljava/lang/String; '+OWNER+')V') and len(args)==2 and isinstance(args[1],dict) and args[1].get('enum')==OWNER and args[1].get('name') in base_commands:
                    result.update(resolve_base(base_commands[args[1]['name']],parameters));result['baseCommand']=args[1]['name']
                else:raise ValueError('unresolved registration arguments or put overload')
                rows.append(result)
        elif op.startswith(('const','new-','sget','iget','aget','move-exception','array-length','add-','sub-','mul-','div-','int-to-','float-to-')):values[text.split(', ')[0]]=None
    return rows


def switch_assignments(ops):
    values={};pending=None;result={}
    for op,text in ops:
        if op=='sget-object':
            dest,field=text.split(', ',1);values[dest]=dict(field=field)
        elif op.startswith('invoke-'):
            pending=None
            if COMPONENT+'->ordinal()I' in text:
                regs=registers(text,COMPONENT);field=values.get(regs[0]) if len(regs)==1 else None
                if not isinstance(field,dict) or not field.get('field','').startswith(COMPONENT+'->'):raise ValueError('unresolved component switch field')
                pending=dict(ordinalField=field['field'].split('->')[1].split()[0])
        elif op.startswith('move-result'):values[text]=pending;pending=None
        elif op in ('move','move/from16','move/16') or op.startswith('move-object'):
            dest,source=text.split(', ');values[dest]=values.get(source)
        elif op=='new-array':values[text.split(', ')[0]]=dict(allocatedArray=True)
        elif op=='sput-object':
            source,field=text.split(', ',1)
            if field.startswith(SWITCH+'->$SwitchMap$') and isinstance(values.get(source),dict) and values[source].get('allocatedArray'):values[source]=dict(field=field)
        elif op in ('const','const/4','const/16'):dest,value=text.split(', ',1);values[dest]=int(value)
        elif op=='aput':
            source,array,index=text.split(', ');number=values.get(source);ordinal=values.get(index);target=values.get(array)
            if type(number) is not int or not isinstance(ordinal,dict) or 'ordinalField' not in ordinal or not isinstance(target,dict) or not target.get('field','').startswith(SWITCH+'->$SwitchMap$'):raise ValueError('unresolved component case assignment '+repr((number,ordinal,target)))
            if ordinal['ordinalField'] in result:raise ValueError('duplicate component case')
            result[ordinal['ordinalField']]=number
        elif op.startswith(('const','new-array','array-length','move-exception')):values[text.split(', ')[0]]=None
    return result


def snapshot(keys,rows,*,metadata_case=None,state_since4gen=None):
    """Pure business body only. Explicit cases required; neither source map initialization nor remote replacement is assumed."""
    if not isinstance(keys,(list,tuple)) or not keys or any(type(k) is not str for k in keys):raise ValueError('nonempty named keys required')
    if metadata_case not in (None,'db-present','missing') or state_since4gen is not None and type(state_since4gen) is not bool:raise ValueError('explicit supported source cases required')
    index={r['key']:r for r in rows};selected=sorted(set(keys));groups={}
    for key in selected:
        if key not in index:raise ValueError('unknown source key')
        row=index[key]
        if row['sourceCondition']:
            if state_since4gen is not True:raise ValueError('selected key requires explicit true source support case')
        channel=row['channel']
        if row['channelSource']=='resource-if-present':
            if metadata_case is None:raise ValueError('selected key requires explicit metadata case')
            if metadata_case=='missing':channel=row['missingMetadataChannel']
        groups.setdefault(row['commandId'],set()).add(channel)
    body=b''.join(subscription_group_body(command,sorted(channels)) for command,channels in sorted(groups.items()))
    return dict(selectedKeys=selected,groups=[dict(commandId=c,channels=sorted(ch)) for c,ch in sorted(groups.items())],bodyHex=body.hex(),remoteReplacementVerified=False,remoteStopVerified=False)


def trace(apk,bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    raw=(bank_dir/'business-05-code-restored.dex').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BANKS[5]:raise ValueError('restored bank hash mismatch')
    with zipfile.ZipFile(str(apk)) as z:resource=z.read('res/DB.json');parameters=json.loads(resource)
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    classes={c.get_name():c for c in DEX(raw).get_classes()};methods={}
    def take(owner,name,descriptor=None):
        found=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(found)!=1 or not found[0].get_code():raise ValueError('missing/ambiguous subscription catalog method '+name)
        m=found[0];methods[(owner,name,m.get_descriptor())]=dict(className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());return m
    def ops(m):return [(i.get_name(),i.get_output()) for i in m.get_instructions()]
    def require(m,*tokens):
        for token in tokens:
            if not any(token in text for _,text in ops(m)):raise ValueError('missing catalog source token '+token)
    bases=constructor_records(ops(take(OWNER,'<clinit>')),OWNER);types=constructor_records(ops(take(TYPE,'<clinit>')),TYPE);commands=constructor_records(ops(take(CMD,'<clinit>')),CMD)
    require(take(TYPE,'<init>'),'->mId I')
    require(take(CMD,'value'),'->data I')
    for descriptor in ('(Ljava/lang/String; I I)V','(Ljava/lang/String; I I Z Ljava/lang/Class;)V','(Ljava/lang/String; I I Z Z Ljava/lang/Class;)V'):take(CMD,'<init>',descriptor)
    for descriptor in ('(Ljava/lang/String; I Ljava/lang/String;)V','(Ljava/lang/String; I I Ljava/lang/String;)V','(Ljava/lang/String; I I Ljava/lang/String; Ljava/lang/Class;)V'):take(OWNER,'<init>',descriptor)
    require(take(OWNER,'<init>','(Ljava/lang/String; I Ljava/lang/String;)V'),'DJIGimbalParamInfoManager;->read(','->index I','->mId I')
    for name in ('getId','getPushClazz'):take(OWNER,name)
    ctor=take(IMPL,'<init>');instructions=[];position=0
    for instruction in ctor.get_instructions():
        row=dict(op=instruction.get_name(),text=instruction.get_output(),offset=position)
        if row['op'].startswith(('if-','goto')):row['target']=position+2*instruction.get_ref_off()
        instructions.append(row);position+=instruction.get_length()
    rows=registrations(instructions,bases,types,commands,parameters)
    if len(rows)!=152 or sum(r['channelSource']=='resource-if-present' for r in rows)!=21 or sum(r['sourceCondition'] is not None for r in rows)!=2:raise ValueError('selected registration coverage changed')
    require(take(IMPL,'put','(Ljava/lang/String; '+OWNER+')V'),'->getPushClazz()','->getId()','->GetUserParams ','->RoninGetParams ')
    require(take(IMPL,'put','(Ljava/lang/String; I I)V'),'Landroid/util/Pair;-><init>(','Map;->put(')
    support=take(IMPL,'isSupportStateSince4Gen');case_fields=switch_assignments(ops(take(SWITCH,'<clinit>')))
    encoded={};position=0
    for instruction in support.get_instructions():encoded[position]=instruction;position+=instruction.get_length()
    switches=[(p,i) for p,i in encoded.items() if i.get_name()=='packed-switch']
    if len(switches)!=1:raise ValueError('one support switch required')
    position,instruction=switches[0];payload=encoded[position+2*instruction.get_ref_off()];outcomes={}
    for case,target in zip(payload.get_values(),payload.get_targets()):
        start=position+2*target;items=[(i.get_name(),i.get_output()) for p,i in encoded.items() if p>=start];outcomes[case]=direct_return(items)
    default=direct_return([(i.get_name(),i.get_output()) for p,i in encoded.items() if p>=position+instruction.get_length()])
    if default!=1 or set(outcomes.values())!={0} or len(outcomes)!=11:raise ValueError('support default/cases changed')
    if set(case_fields.values())!=set(outcomes):raise ValueError('support field coverage changed')
    declared={f.get_name() for f in classes[COMPONENT].get_fields()}
    if not set(case_fields).issubset(declared) or 'HG724' not in declared:raise ValueError('component declarations changed')
    for name in ('doPack','mergeList','start','subscribeCmdChannel','unsubscribeCmdChannel','hasChannelSubscribed'):take(SUB,name)
    require(take(SUB,'start'),'DeviceType;->CENTER ','v0, 7','NEEDACK;->NO ')
    pairs={}
    for row in rows:pairs.setdefault((row['commandId'],row['channel']),[]).append(row['key'])
    aliases=[dict(commandId=c,channel=i,keys=keys) for (c,i),keys in sorted(pairs.items()) if len(keys)>1]
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256=BANKS[5],resource=dict(path='res/DB.json',sha256=hashlib.sha256(resource).hexdigest()),appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,runtimeRegistrationMapConstructed=False,methods=list(methods.values()),baseCommandCount=len(bases),registrations=rows,uniqueNamedKeys=len(rows),dbPresentUniqueCommandChannelPairs=len(pairs),aliasGroups=aliases,
        supportPredicate=dict(method='isSupportStateSince4Gen',falseComponentFields=sorted(case_fields),defaultResult=True,hg724UsesDefault='HG724' not in case_fields,unknownOrMissingComponentBehaviorVerified=False,conditionalKeys=[r['key'] for r in rows if r['sourceCondition']],runtimeComponentCacheVerified=False),
        metadata=dict(resourceConditionalKeyCount=21,resourceConditionalBaseCommandCount=len({r['baseCommand'] for r in rows if r['channelSource']=='resource-if-present'}),missingReadLeavesJavaDefaultChannel=0,resourceRuntimeLoadedBeforeEnumInitializationVerified=False,metadataConditionalNamesNotSilentlyResolved=True),
        endpoint=dict(receiverByte=229,ackRequested=False,sourceRefreshSeconds=1,remoteStopOrLeaseVerified=False),
        exampleSnapshots=[snapshot(['UserProfile','PitchMotorControlStiffness','PeripheralPosYaw'],rows),snapshot(['ControllerMaxSpeedYaw'],rows,metadata_case='db-present'),snapshot(['ControllerMaxSpeedYaw'],rows,metadata_case='missing'),snapshot(['PeripheralGyroOutYaw','PeripheralGyroAccePitch'],rows)],
        remaining=['Actual resource load order and component cache, target route/lease and remote replacement/stop remain unverified.','Selected literal/source-metadata catalog is not 152 target features or all firmware commands.','No SDK send allowlist or persistent subscription manager added.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d fingerprints; %d named registrations, explicit metadata/support cases.'%(len(r['methods']),len(r['registrations'])))
if __name__=='__main__':main()
