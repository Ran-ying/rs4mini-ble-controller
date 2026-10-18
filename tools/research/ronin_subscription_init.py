#!/usr/bin/env python3
"""Static parameter-loader/enum capture audit; never starts vendor threads or imports SDK."""
import argparse,hashlib,json
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_subscription_catalog import IMPL,OWNER
MANAGER='Ldji/midware/data/manager/P3/DJIGimbalParamInfoManager;'


def captured_channels(rows,available_metadata_names):
    """Explicit per-name read-availability model only, not a scheduler or Java VM."""
    if not isinstance(available_metadata_names,(set,frozenset)) or any(type(v) is not str for v in available_metadata_names):raise ValueError('explicit available metadata-name set required')
    return {r['key']:(r['channel'] if r['channelSource']!='resource-if-present' or r['parameterName'] in available_metadata_names else r['missingMetadataChannel']) for r in rows}


def trace(apk,bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    images=[]
    for bank,pin in BANKS.items():
        raw=(bank_dir/('business-%02d-code-restored.dex'%bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('restored bank hash mismatch')
        images.append((bank,raw))
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    references=[];writers=[];classes=None
    for bank,raw in images:
        dex=DEX(raw)
        if bank==5:classes={c.get_name():c for c in dex.get_classes()}
        for c in dex.get_classes():
            for m in c.get_methods():
                if not m.get_code():continue
                refs=[];writes=[]
                for op in m.get_instructions():
                    name,text=op.get_name(),op.get_output()
                    if name.startswith('invoke-') and any(MANAGER+'->'+v+'(' in text for v in ('setContext','getInstance','init')):refs.append(text.split(', '+MANAGER+'->',1)[-1])
                    if name.startswith('iput') and OWNER+'->mId I' in text:writes.append(name)
                if refs or writes:
                    row=dict(bank=bank,className=c.get_name(),method=m.get_name(),descriptor=m.get_descriptor(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest())
                    if refs:references.append(dict(row,targets=refs))
                    if writes:writers.append(dict(row,writeCount=len(writes)))
    methods=[]
    def take(owner,name,descriptor=None):
        found=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(found)!=1 or not found[0].get_code():raise ValueError('missing/ambiguous loader method '+name)
        m=found[0];row=dict(className=owner,method=name,descriptor=m.get_descriptor(),accessFlags=m.get_access_flags(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest())
        if not any(r['className']==owner and r['method']==name and r['descriptor']==row['descriptor'] for r in methods):methods.append(row)
        return [(i.get_name(),i.get_output()) for i in m.get_instructions()]
    def require(ops,*tokens):
        for token in tokens:
            if not any(token in text for _,text in ops):raise ValueError('missing loader source token '+token)
    require(take(MANAGER,'<clinit>'),'Ljava/util/HashMap;-><init>()V','->infos Ljava/util/HashMap;')
    require(take(MANAGER,'<init>'),MANAGER+'->init()V')
    init=take(MANAGER,'init');require(init,'Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;)V','Ljava/lang/Thread;->start()V')
    require(take(MANAGER,'getInstance'),MANAGER+'-><init>()V')
    require(take(MANAGER,'setContext'),MANAGER+'->context ',MANAGER+'->getInstance()')
    run=take(MANAGER[:-1]+'$1;','run');require(run,'R$raw;->gimbal_param_infos ','->rawfileGetContent(','->-$$Nest$mreadToMemory(')
    require(take(MANAGER,'-$$Nest$mreadToMemory'),MANAGER+'->readToMemory(')
    read=take(MANAGER,'read');require(read,'->infos Ljava/util/HashMap;','Ljava/util/HashMap;->get(')
    load=take(MANAGER,'readToMemory');require(load,'V_JsonUtil;->getList(','Ljava/util/HashMap;->put(')
    for owner,name in ((MANAGER,'init'),(MANAGER,'getInstance'),(MANAGER,'setContext'),(MANAGER,'read'),(MANAGER,'readToMemory')):
        selected=take(owner,name)
        if any('->join(' in t or '->await(' in t or '->get()Ljava/lang/Object;' in t for _,t in selected):raise ValueError('selected loader now has completion wait')
    ctor=take(OWNER,'<init>','(Ljava/lang/String; I Ljava/lang/String;)V');require(ctor,MANAGER+'->read(','->index I','->mId I')
    if [op for op,_ in ctor].count('if-eqz')!=1:raise ValueError('source read-if-present constructor changed')
    getter=take(OWNER,'getId')
    if getter!=[('iget','v0, v1, '+OWNER+'->mId I'),('return','v0')]:raise ValueError('getter no longer returns captured field directly')
    take(OWNER,'<clinit>');take(IMPL,'<init>')
    if len(writers)!=3 or any(w['className']!=OWNER or w['method']!='<init>' for w in writers):raise ValueError('new direct post-constructor id writer requires audit')
    if any(r['accessFlags']&0x20 for r in methods if r['className']==MANAGER and r['method'] in ('init','getInstance','setContext','read','readToMemory')):raise ValueError('selected method-level synchronization changed')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(b):p for b,p in BANKS.items()},appCodeExecuted=False,threadsStarted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,runtimeInitializationOrderObserved=False,methods=methods,directLoaderCallers=references,directCapturedIdWriters=writers,
        sourceFacts=dict(managerInfosStartsEmpty=True,setContextStartsOrGetsLoader=True,loaderThreadStartsAsynchronously=True,resource='gimbal_param_infos / res/DB.json',recordsPublishedIndividually=True,selectedMethodsHaveNoJoinAwaitOrMethodSynchronization=True,baseConstructorReadsMetadataOnce=True,getIdDoesNotReReadMetadata=True,visibleIdWritersOnlyThreeConstructors=True,completionBeforeBaseEnumInitializationProven=False,globalExternalBarrierAbsenceProven=False),
        scope=dict(restoredBanks=sorted(BANKS),unrestoredBanks=[1,7],reflectionOrOtherClassLoadersRuledOut=False),
        sdkDesign=dict(useExplicitPinnedDbPresentBranchInsteadOfEmulatingUninitializedZeroFallback=True,vendorAppCacheNotRequiredForIndependentSdk=True,targetRoutingStillUnverified=True,remoteStopOrLeaseStillUnverified=True),
        remaining=['Selected methods show asynchronous loading and no local completion wait; other global barriers or actual scheduling are not proven absent.','Do not infer a live race, captured zeros or target device failure from this static audit.','Independent SDK may deliberately encode the pinned metadata-present/HG724 source branch without depending on vendor initialization; keep target/route/stream flags false.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d loader/capture fingerprints, %d direct constructor id writers; no threads executed.'%(len(r['methods']),len(r['directCapturedIdWriters'])))
if __name__=='__main__':main()
