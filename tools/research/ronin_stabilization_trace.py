#!/usr/bin/env python3
"""Trace the angle SDK's stabilization dependency, never a vision/camera SDK."""
import argparse
import hashlib
import json
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_angles_trace import ROOT,MODEL,BASE
from ronin_subscription_trace import constructor_records
from ronin_profiles_trace import relative_target

STATE=MODEL+'DataEyeGetPushStabilizationState;'
PAUSE=MODEL+'DataSingleSendAppStateForStabilization;'
REASON=STATE[:-1]+'$PauseReason;'


def source_state_byte(raw):
    """Source business byte, not a target BLE frame or physical gimbal state."""
    if type(raw) is not int or not 0<=raw<=255:raise ValueError('one explicit source byte required')
    enabled=bool(raw&128)
    paused=not enabled or not bool(raw&64)
    return dict(raw=raw,sourceTurnedOn=enabled,sourcePaused=paused,sourcePauseReasonRaw=raw&63,sourceNeedPause=enabled and not paused)


def wait_flow(operations):
    """Check selected code-unit branch anchors; no execution or general CFG claim."""
    anchors={pc:(op,text) for pc,op,text in operations}
    branch=anchors.get(4)
    if branch!=('if-eqz','v0, +037h') or relative_target(4,branch[1])!=59:raise ValueError('wait false-flag branch changed')
    expected={2:('const/4','v1, 1'),3:('const/4','v2, 0'),32:('const-wide/16','v4, 3'),38:('xor-int/2addr','v2, v1'),73:('xor-int/lit8','v7, v2, 1'),75:('return','v7')}
    if any(anchors.get(pc)!=value for pc,value in expected.items()):raise ValueError('wait constant/inversion changed')
    for token in ('->await(J Ljava/util/concurrent/TimeUnit;)Z','TimeUnit;->SECONDS '):
        if not any(token in text for _,_,text in operations):raise ValueError('missing wait source '+token)
    # Both branches send the same no-callback START; no resume semantics established.
    starts=[pc for pc,op,text in operations if op=='invoke-virtual' and PAUSE+'->start()V' in text]
    if starts!=[27,70]:raise ValueError('wait START send sites changed')
    return dict(timeoutSeconds=3,falseNeedPauseStillSendsStart=True,awaitResultIsInvertedThenReturnInverted=True,startInstructionCodeUnits=starts,sourceReturnsFirmwareMotionCompletion=False,sourceWaitUsesAngleAck=False)


def trace(apk,bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    images=[]
    for bank,pin in BANKS.items():
        raw=(bank_dir/('business-%02d-code-restored.dex'%bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('restored bank hash mismatch: %02d'%bank)
        images.append((bank,raw))
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    fingerprints={};callers=[];classes=None
    names=('tryToPauseTheStabilizationIfNecessary','justSendPauseData')
    for bank,raw in images:
        dex=DEX(raw);current={c.get_name():c for c in dex.get_classes()}
        if bank==5:classes=current;sdk_dex=dex
        for owner,cls in current.items():
            for m in cls.get_methods():
                if not m.get_code():continue
                refs=[dict(kind='direct-invoke',target=next((name for name in names if '->'+name+'(' in o.get_output()),'state-class-method')) for o in m.get_instructions() if o.get_name().startswith('invoke-') and (any('->'+name+'(' in o.get_output() for name in names) or (STATE+'->' in o.get_output() and owner!=STATE))]
                if refs:callers.append(dict(bank=bank,className=owner,method=m.get_name(),descriptor=m.get_descriptor(),references=refs))
    def take(owner,name,descriptor=None):
        found=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(found)!=1 or not found[0].get_code():raise ValueError('missing or ambiguous stabilization method '+owner+name)
        m=found[0];fingerprints[(owner,name,m.get_descriptor())]=dict(className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest())
        pc=0;ops=[]
        for o in m.get_instructions():ops.append((pc,o.get_name(),o.get_output()));pc+=o.get_length()//2
        return ops
    def require(ops,token):
        if not any(token in text for _,_,text in ops):raise ValueError('missing stabilization evidence '+token)
    take(ROOT,'<init>');take(ROOT,'rotate');take(ROOT,'justSendPauseData')
    event=take(ROOT,'onEvent3BackgroundThread','('+STATE+')V')
    for token in ('->getStateIsTurnOn()Z','->getStateIsPaused()Z','->needPauseStabilization Z','CountDownLatch;->countDown()V'):require(event,token)
    wait=take(ROOT,'tryToPauseTheStabilizationIfNecessary');flow=wait_flow(wait)
    require(wait,'->CANNOT_PAUSE_STABILIZATION ');require(wait,'Ljava/util/List;->remove(')
    require(wait,'Ljava/lang/InterruptedException;->printStackTrace()V')
    wait_method=next(m for m in classes[ROOT].get_methods() if m.get_name()=='tryToPauseTheStabilizationIfNecessary')
    code=wait_method.get_code();handler_list=code.get_handlers();handlers={h.get_off()-handler_list.get_off():h for h in handler_list.get_list()};exception_ranges=[]
    for item in code.get_tries():
        h=handlers[item.get_handler_off()]
        exception_ranges.append(dict(startCodeUnit=item.get_start_addr(),endCodeUnit=item.get_start_addr()+item.get_insn_count(),handlers=[dict(typeName=sdk_dex.get_cm_type(pair.get_type_idx()),targetCodeUnit=pair.get_addr()) for pair in h.get_handlers()],catchAllCodeUnit=h.get_catch_all_addr() if h.get_size()<=0 else None))
    if not any(r['startCodeUnit']<=34<r['endCodeUnit'] and dict(typeName='Ljava/lang/InterruptedException;',targetCodeUnit=40) in r['handlers'] for r in exception_ranges):raise ValueError('await interruption handler changed')
    reset=take(ROOT,'resetGimbal');require(reset,'->tryToPauseTheStabilizationIfNecessary(')
    require(reset,'DataGimbalNewResetAndSetMode;->setReset(Z)')
    chain=[];owner=BASE+'DJIGimbalHG724Abstraction;'
    while owner in classes and owner.startswith(BASE):chain.append(owner);owner=classes[owner].get_superclassname()
    reset_owners=[o for o in chain if any(m.get_name()=='resetGimbal' for m in classes[o].get_methods())]
    if reset_owners!=[ROOT]:raise ValueError('reset inheritance changed')
    for name in ('doPack','getStateIsTurnOn','getStateIsPaused','getPauseReason'):take(STATE,name)
    require(take(STATE,'getStateIsTurnOn'),'v0, v0, 128')
    require(take(STATE,'getStateIsPaused'),'v0, v0, 64')
    require(take(STATE,'getPauseReason'),'v0, v0, 63')
    take(PAUSE,'<init>');take(PAUSE,'doPack');take(PAUSE,'start','()V')
    reason_ops=[(op,text) for _,op,text in take(REASON,'<clinit>')]
    reasons=constructor_records(reason_ops,REASON)
    require(take(REASON,'find'),'->OTHER ')
    enum='Ldji/midware/data/config/P3/CmdIdEYE$CmdIdType;'
    entries=constructor_records([(op,text) for _,op,text in take(enum,'<clinit>')],enum)
    dispatch=[dict(name=k,arguments=v['arguments']) for k,v in entries.items() if any(STATE in str(a) for a in v['arguments'])]
    if len(dispatch)!=1:raise ValueError('unresolved stabilization dispatch')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(k):v for k,v in BANKS.items()},appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,
        scope='offline dependency research; no camera or vision runtime capability',sourceBusinessByte=dict(offset=0,width=1,turnedOnMask=128,notPausedWhenEnabledMask=64,pauseReasonMask=63,disabledReturnsPaused=True,rawBleOffsetVerified=False),
        pauseReasons={k:v['arguments'][2] for k,v in reasons.items()},dispatch=dispatch,waitFlow=flow,
        sourceEvent=dict(needPauseWhen='turnedOn and notPaused',waitersReleasedWhen='turnedOff or paused',waitersAreNotSequenceCorrelated=True,angleCompletionVerified=False),
        sourceInterruption=dict(handlerPrintsException=True,returnCanSucceedWithoutPausedEvent=True,selectedAwaitExceptionTableAudited=True,exceptionRanges=exception_ranges),
        sourceReset=dict(implementationOwner=ROOT,platformBranchAudited=False,usesPauseWait=True,notAngleCompletionNotification=True),callSites=callers,methods=list(fingerprints.values()),
        remaining=['Source stabilization state is not gimbal angle completion, cancellation or firmware stop.', 'No target BLE framing/address or direct-BLE dependency applicability established.', 'No resume request established in these selected routines; not a whole-App absence proof.', 'Banks1/7, residual stubs and dynamic paths remain outside scan.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d method fingerprints, %d caller methods; no SDK/vision/BLE execution.'%(len(r['methods']),len(r['callSites'])))

if __name__=='__main__':main()
