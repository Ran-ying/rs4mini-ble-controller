#!/usr/bin/env python3
"""Static menu mount and track UI callbacks; never executes vendor/UI/BLE code."""
import argparse,hashlib,json,re,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from ronin_program_entry import trace as entry_trace,view_literals,VIEW,HELP,JUMP,UI

TRACK=UI+'ui/create/track/CreateTrackView;'
SUB=UI+'ui/entry/RoninCreateJumpTextView;'
ANDROID='{http://schemas.android.com/apk/res/android}'


def direct_calls(ops):
    result=[]
    for op,text in ops:
        if not op.startswith('invoke-'):continue
        match=re.search(r'(L[^;]+;)->([^ (]+)(\(.*)$',text)
        if not match:raise ValueError('unresolved direct source invoke')
        result.append(dict(className=match[1],method=match[2],descriptor=match[3]))
    return result


def selected_elements(xml):
    root=ET.fromstring(xml)
    names={'com.dji.ronin.ui.create.CreateMainJumpEntryView','com.dji.ronin.ui.entry.RoninCreateJumpTextView'}
    return dict(rootClass=root.tag,elements=[dict(className=e.tag,id=e.attrib.get(ANDROID+'id')) for e in root.iter() if e.tag in names])


def trace(apk,bank_dir):
    # Validates APK/bank03/05 before importing any optional parser.
    entry=entry_trace(apk,bank_dir)
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    from androguard.core.axml import ARSCParser,AXMLPrinter
    classes={c.get_name():c for c in DEX((bank_dir/'business-03-code-restored.dex').read_bytes()).get_classes()};methods={}
    def take(owner,name,descriptor=None):
        found=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(found)!=1 or not found[0].get_code():raise ValueError('missing or ambiguous workflow method '+name)
        m=found[0];methods[(owner,name,m.get_descriptor())]=dict(className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    def require(ops,token):
        if not any(token in text for _,text in ops):raise ValueError('missing workflow source token '+token)
    main=view_literals(take(VIEW,'<clinit>'),selected=('MainRoninNew',))['MainRoninNew']
    init=take(HELP,'initView');require(init,'2131558843');require(init,'2131362579');require(init,'->inflate(')
    require(take(HELP,'onFinishInflate'),'->initView()V')
    require(take(HELP,'onAttachedToWindow'),'->updateVisibility()V')
    take(HELP,'updateVisibility');require(take(HELP,'lambda$initView$0'),JUMP+'->onClick(')
    if classes[SUB].get_superclassname()!=JUMP:raise ValueError('create jump superclass changed')
    take(SUB,'<init>');sub=take(SUB,'onClick');require(sub,'SMART_SHOOTING ')
    if not any(op.startswith('invoke-super') and JUMP+'->onClick(' in text for op,text in sub):raise ValueError('entry no longer delegates click to parent')
    layouts=[]
    with zipfile.ZipFile(str(apk)) as z:
        resources=ARSCParser(z.read('resources.arsc'))
        for name,rid in (('MainRoninNew',main['layoutId']),('CreateMainJumpEntryChild',2131558843)):
            configs=resources.get_resolved_res_configs(rid)
            if len(configs)!=1:raise ValueError('mount layout configuration ambiguity')
            _,path=configs[0];raw=z.read(path)
            layouts.append(dict(name=name,resourceId=rid,path=path,sha256=hashlib.sha256(raw).hexdigest(),**selected_elements(AXMLPrinter(raw).get_xml())))
    if layouts[0]['elements']!=[dict(className='com.dji.ronin.ui.create.CreateMainJumpEntryView',id=None)]:raise ValueError('main entry mount changed')
    menu=next(l for l in entry['layouts'] if l['viewName']=='CreateRoninNew')
    expected=dict(className='com.dji.ronin.ui.entry.RoninCreateJumpTextView',id='@%08X'%menu['viewId'])
    if layouts[1]['elements']!=[expected]:raise ValueError('child menu id binding changed')
    for name in ('previewToggle','sendToDeviceStart','sendToDeviceStop','startRecord','stopRecord','checkGimbalStateStart','checkGimbalStateStop','onEvent3MainThread','onAttachedToWindow','onDetachedFromWindow','openPushEnable','closePushEnable'):
        take(TRACK,name)
    for number in (12,13):
        owner=TRACK[:-1]+'$%d;'%number
        require(take(owner,'onSuccess'),'AssistUIHandler;->post(');take(owner,'onFailure')
        require(take(TRACK[:-1]+'$%d$1;'%number,'run'),'CreateUtils$Status;->'+('PREVIEWING' if number==12 else 'IDLE')+' ')
    require(take(TRACK[:-1]+'$1;','handleMessage'),'v0, 1200')
    take(TRACK,'-$$Nest$fputmStatus');take(TRACK,'-$$Nest$mupdateUI')
    preview=take(TRACK,'previewToggle');require(preview,'->setRecordOrPreview(');require(preview,'->setStartOrStop(')
    require(take(TRACK,'startRecord'),'CameraAction;->START_RECORD ')
    require(take(TRACK,'checkGimbalStateStart'),'RequestType;->StartContinuePush ')
    require(take(TRACK,'checkGimbalStateStop'),'RequestType;->StopContinuePush ')
    event=take(TRACK,'onEvent3MainThread');calls=direct_calls(event)
    for token in ('->getTrackStatus()I','->mPrevGimbalStatus I','CameraAction;->STOP_RECORD ','v1, 255','v1, 3000'):require(event,token)
    forbidden={'getCmdId','isSuccess','getSeq','getSequence'}
    if any(c['method'] in forbidden for c in calls):raise ValueError('selected status guard behavior changed')
    return dict(schemaVersion=1,apkSha256=entry['apkSha256'],bankSha256=entry['bankSha256'],appCodeExecuted=False,liveUiExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,fullModelWorkflowVerified=False,
        scope='Selected static resource mount and track UI callback/status source declarations; no runtime initialization or physical effects',priorEntryEvidence='protocol/research/ronin-program-entry-evidence.json',priorProgramEvidence='protocol/research/ronin-program-evidence.json',mainViewLiteral=main,layouts=layouts,methods=list(methods.values()),
        conditionalMountChain=['IsHandleDevice cache true and preceding Ronin2 route false','showMainView selects MainRoninNew','main resource mounts CreateMainJumpEntryView','onFinishInflate calls initView and inflates child resource','child subclass id matches CreateRoninNew viewId','subclass click logs then invokes parent click','parent generic route opens selected create menu'],staticSelectedMountChainEstablished=True,androidInflationExecuted=False,
        track=dict(command='04:62',previewSourceValue=1,startPhase=0,stopPhase=1,sourcePreviewAckPostsUiState='PREVIEWING',sourceStopAckPostsUiState='IDLE',uiStateIsPhysicalCompletionVerified=False,sourceSubscriptionCommand='04:6B',subscriptionTag='62',subscriptionStopIsProgramStop=False,statusHandlerDirectCalls=calls,statusHandlerDirectlyChecksCommandId=False,statusHandlerDirectlyChecksSuccess=False,statusHandlerDirectlyChecksSequence=False,statusHandlerMayReadRetainedSingletonTrackFields=True,watchdogMs=3000,watchdogAction='re-request StartContinuePush, not motor stop',sourceTimedUiUnlockMs=1200,sourceRecordingHasCameraBranch=True,completeCameraIsolationVerified=False),
        remaining=['Static mount is conditional on product cache/platform and does not prove live target firmware support.', 'Selected UI callbacks can change state from ACK or stale shared status; do not copy them as SDK completion or cancellation.', 'Program units/reference frame, raw BLE receive path, sender/receiver addressing, target acceptance and physical stop remain unverified.', 'Camera/recording branches and all indirect callbacks are not fully isolated; no SDK program send or advanced feature added.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d workflow fingerprints, %d mount layouts; no UI or sends.'%(len(r['methods']),len(r['layouts'])))
if __name__=='__main__':main()
