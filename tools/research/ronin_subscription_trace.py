#!/usr/bin/env python3
"""Trace subscription bitmaps/endpoints and request-push framing without execution."""
import argparse,hashlib,json,re,zipfile
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_command_audit import DERIVED_SHA256
from ronin_settings_trace import BASE,OWNER,unique_record
from ronin_profiles_trace import preset_read_context
from ronin_subscription_payloads import subscription_group_body,MOVEMENT_PROFILE_NAMES


def constructor_records(operations,owner):
    """Resolve literal enum constructor arguments, never evaluate vendor code."""
    registers={};records={}
    for op,text in operations:
        if op.startswith('const-string') or op=='const-class':
            reg,value=text.split(', ',1);registers[reg]=value
        elif op in ('const/4','const/16','const'):
            reg,value=text.split(', ',1);registers[reg]=int(value)
        elif op.startswith('invoke-direct') and owner+'-><init>(' in text:
            raw=text.split(', '+owner)[0];regs=re.findall(r'v\d+',raw)
            if ' ... ' in raw:regs=['v%d'%i for i in range(int(regs[0][1:]),int(regs[-1][1:])+1)]
            values=[registers.get(r) for r in regs[1:]]
            if not values or not isinstance(values[0],str) or values[0] in records or any(v is None for v in values):raise ValueError('unresolved/duplicate enum constructor')
            records[values[0]]=dict(descriptor=text.split('-><init>',1)[1],arguments=values)
        elif op in ('new-instance','move-result-object','sget-object'):registers[text.split(', ')[0]]=None
        elif op.startswith(('sput-object','invoke-static')) or op=='return-void':pass
        else:raise ValueError('unsupported enum prefix '+op)
    return records


def trace(apk,dex_path):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    raw=dex_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=DERIVED_SHA256:raise ValueError('restoration view hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    classes={c.get_name():c for c in DEX(raw).get_classes()};methods={}
    def take(owner,name,descriptor=None):
        choices=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(choices)!=1 or not choices[0].get_code():raise ValueError('expected readable subscription method '+owner+name)
        m=choices[0];methods[(owner,name,m.get_descriptor())]=dict(className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());return m
    def ops(m):return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    def require(m,*tokens):
        values=ops(m)
        for token in tokens:
            if not any(token in text for _,text in values):raise ValueError('missing subscription reference '+token)
    sub='Ldji/midware/data/model/P3/DataGimbalSubscribeParams;';impl='Ldji/common/gimbal/Ronin2SubscribeIMPL;'
    base='Ldji/midware/data/manager/P3/DataBase;';recv='Ldji/midware/data/packages/P3/RecvPack;'
    device='Ldji/midware/data/config/P3/DeviceType;';cmd='Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;'
    device_entries=constructor_records(ops(take(device,'<clinit>')),device)
    if [device_entries[k]['arguments'][2] for k in ('APP','CENTER')]!=[2,5]:raise ValueError('subscription endpoint enums changed')
    cmd_entries=constructor_records(ops(take(cmd,'<clinit>')),cmd)
    for key,value in [('SubscribeGimbalParams',18),('GetUserParams',16),('RoninGetParams',50),('GetPushUserParams',36)]:
        if cmd_entries[key]['arguments'][2]!=value:raise ValueError('subscription command enum changed')
    if cmd_entries['GetPushUserParams']['arguments'][-1]!='Ldji/midware/data/model/P3/DataGimbalGetPushUserParams;':raise ValueError('preset push dispatch class changed')
    movement='Ldji/common/gimbal/MovementSettingsProfile;'
    movement_entries=constructor_records(ops(take(movement,'<clinit>')),movement)
    names={row['arguments'][2]:key for key,row in movement_entries.items() if key!='UNKNOWN'}
    if names!=MOVEMENT_PROFILE_NAMES:raise ValueError('offline preset enum mapping differs from source')
    entries=constructor_records(ops(take(OWNER,'<clinit>')),OWNER)
    for descriptor in ('(Ljava/lang/String; I Ljava/lang/String;)V','(Ljava/lang/String; I I Ljava/lang/String;)V','(Ljava/lang/String; I I Ljava/lang/String; Ljava/lang/Class;)V'):
        m=take(OWNER,'<init>',descriptor);require(m,'->mId I','->mPushClazz ')
        if descriptor=='(Ljava/lang/String; I Ljava/lang/String;)V':require(m,'DJIGimbalParamInfoManager;->read(','ParamInfo;->index I')
    take(OWNER,'getId');take(OWNER,'getPushClazz')
    with zipfile.ZipFile(str(apk)) as z:parameters=json.loads(z.read('res/DB.json'))
    selected=[]
    for key in ('USER_PROFILE','STIFFNESS_PITCH'):
        entry=entries[key];args=entry['arguments']
        if len(args)==3:
            record=unique_record(parameters,args[2]);channel=record['index'];group=16
        elif len(args)==5:
            channel=args[2];record=dict(name=args[3])
            getters={'Ldji/midware/data/model/P3/DataGimbalGetUserParams;':16,'Ldji/midware/data/model/P3/DataGimbalRoninGetUserParams;':50}
            if args[4] not in getters:raise ValueError('unknown subscription getter class')
            group=getters[args[4]]
        else:raise ValueError('unexpected selected channel constructor')
        selected.append(dict(baseCommand=key,parameterName=record['name'],command=group,channel=channel,sourceArguments=args))
    if [(r['command'],r['channel']) for r in selected]!=[(16,0),(50,0)]:raise ValueError('selected subscription channel mapping changed')
    start=take(sub,'start');require(start,'DeviceType;->CENTER ','v0, 7','NEEDACK;->NO ','->SubscribeGimbalParams ','->start(Ldji/midware/data/packages/P3/SendPack;)V')
    merge=take(sub,'mergeList');require(merge,'v0, v0, 8','v4, v4, 1','v5, v1, 8')
    pack=take(sub,'doPack');require(pack,'v6, v6, -1','->mergeList(','->entrySet()')
    subscribe=take(sub,'subscribeCmdChannel');require(subscribe,'Ljava/util/List;->set(','Ljava/util/List;->add(')
    unsubscribe=take(sub,'unsubscribeCmdChannel');require(unsubscribe,'Ljava/util/List;->remove(','Ljava/util/Map;->remove(')
    take(sub,'hasChannelSubscribed')
    init=take(impl,'<init>');require(init,'UserProfile','->USER_PROFILE ','STIFFNESS_PITCH','->scheduleAtFixedRate(','v6, 1','TimeUnit;->SECONDS ')
    route=take(impl,'put','(Ljava/lang/String; Ldji/midware/ronin2/Ronin2GimbalParamsManager$BaseCommand;)V');require(route,'->getPushClazz()','->GetUserParams ','->RoninGetParams ','->getId()')
    take(impl,'put','(Ljava/lang/String; I I)V')
    tick=take(impl,'lambda$new$0');require(tick,'->isRemoteOK()Z','->isConnected()Z','->hasChannelSubscribed()Z','->start(')
    require(take(impl,'callGetValue'),'v1, 3000','->sendMessageDelayed(')
    for name in ('registerPushValue','unregisterPushValue','destroy'):take(impl,name)
    handler=take('Ldji/common/gimbal/Ronin2SubscribeIMPL$InnerHandler;','handleMessage');require(handler,'->subscribeCmdChannel(','->unsubscribeCmdChannel(','v1, v1, -1')
    ronin=take(BASE+'DJIGimbalRonin2Abstraction;','<init>')
    require(ronin,'Ronin2SubscribeIMPL;-><init>()V','->mSubscribeController ')
    chain=[];owner=BASE+'DJIGimbalHG724Abstraction;'
    while owner in classes and owner.startswith(BASE):chain.append(owner);owner=classes[owner].get_superclassname()
    writers=[]
    for owner in chain:
        for m in classes[owner].get_methods():
            if m.get_code() and any(o.get_name()=='iput-object' and '->mSubscribeController ' in o.get_output() for o in m.get_instructions()):writers.append(owner+'->'+m.get_name()+m.get_descriptor())
    if writers!=[BASE+'DJIGimbalRonin2Abstraction;-><init>()V']:raise ValueError('target inheritance subscription assignment changed')
    receive=take(recv,'setBuffer');require(receive,'->cmdType I','v4, 11','v4, 12','->ccode I','Ljava/lang/System;->arraycopy(')
    require(take(recv,'isNeedCcode'),'->isNeedCcode(I)Z')
    require(take('Ldji/midware/data/packages/P3/SendPack;','doPack'),'->receiverId I','->receiverType I','->isNeedAck I')
    require(take(base,'setPushRecPack'),'Pack;->data [B','->setPushRecData([B)V')
    require(take(base,'setPushRecData'),'->setRecData([B)V')
    if ops(take(base,'setRecData'))!=[('iput-object','v1, v0, '+base+'->_recData [B'),('return-void','')]:raise ValueError('base data assignment changed')
    require(take(base,'get','(I I Ljava/lang/Class; [I)Ljava/lang/Number;'),'->_recData [B','BytesUtil;->readBytes(')
    camera='Ldji/midware/data/model/base/DJICameraDataBase;';model='Ldji/midware/data/model/P3/DataGimbalGetPushUserParams;'
    for owner in (camera,model):
        if any(m.get_name() in ('get','setRecData','setPushRecData','setPushRecPack') for m in classes[owner].get_methods()):raise ValueError('push model data override changed')
    take(camera,'<init>');preset=preset_read_context(ops(take(model,'getPresetID')))
    return dict(schemaVersion=1,apkSha256=APK_SHA256,derivedSha256=DERIVED_SHA256,appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,
                sourceEndpoint=dict(receiverType='CENTER',receiverTypeValue=5,receiverId=7,packedReceiverByte=229,ackRequested=False,command='04:12',actualTargetRoutingVerified=False),
                subscriptionFormat=dict(groupHeader=['commandByte','highestChannelIndex'],bitmap='LSB-first; ceil((highestChannel+1)/8) bytes',multipleGroupOrder='HashMap iteration; no stable order guaranteed',emptyGroupOmitted=True),
                selectedChannels=selected,sourceMovementEnums=[dict(name=k,value=v['arguments'][2]) for k,v in movement_entries.items()],targetInheritanceControllerAssignments=writers,sourceRefreshSeconds=1,sourceTemporaryGetLifetimeMs=3000,
                sourceCancellation=dict(localReferenceCounted=True,trailingZeroChannelsTrimmed=True,lastGroupRemoved=True,refreshSkipsEmptyMap=True,remoteStopOrLeaseDurationVerified=False),
                presetRequestPush=dict(command='04:24',requestTypeRequired=True,encryptionAllowed=False,sourcePayloadOffset=preset['businessOffset'],width=1,sourceFramingEstablished=True,targetDeviceVerified=False,activePresetVerified=False,ackPayloadOffsetNotInterchangeable=True),
                offlineBodyVectors=[dict(command=c,channels=ch,bodyHex=subscription_group_body(c,ch).hex()) for c,ch in [(16,[0]),(50,[0]),(36,[0,2,9]),(36,[])]],
                remaining=['Verify target routing, refresh/lease and remote stop before exposing a persistent SDK subscription.',
                           '04:24 fixed-layout preset is distinct from subscribed 04:10 parameter records; no active target profile proof.',
                           'Audit all remaining registered key/channel semantics and target traffic.'],methods=list(methods.values()))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','dex','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.dex);a.output.write_text(json.dumps(r,indent=2)+'\n');print('%d method fingerprints, subscription/push source only; no sends.'%len(r['methods']))

if __name__=='__main__':main()
