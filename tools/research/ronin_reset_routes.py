#!/usr/bin/env python3
"""Audit generic reset routing without promoting it to target BLE support."""
import argparse,hashlib,json
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_angles_trace import ROOT,MODEL
from ronin_profiles_trace import relative_target
from ronin_subscription_trace import constructor_records

RESET=MODEL+'DataGimbalNewResetAndSetMode;'
SPECIAL=MODEL+'DataSpecialControl;'
OLD=MODEL+'DataOldSpecialControl;'
NEW=MODEL+'DataNewSpecialControl;'
PLATFORMS=('M200','M210','M210RTK')
PRODUCTS=('Pomato','Orange2','M200','M210','M210RTK','Potato')


def source_platform_route(name):
    if type(name) is not str or not name:raise ValueError('explicit source platform label required')
    return 'gimbal-reset-and-mode' if name in PLATFORMS else 'special-control-factory'


def source_product_variant(name):
    if type(name) is not str or not name:raise ValueError('explicit source product label required')
    return 'new-special-control' if name in PRODUCTS else 'old-special-control'


def reset_mode_body(mode,reset):
    if type(mode) is not int or not 0<=mode<=255 or type(reset) is not bool:raise ValueError('explicit source byte and boolean required')
    return bytes((mode,int(reset)))


def branch_routes(operations):
    anchors={pc:(op,text) for pc,op,text in operations}
    expected={4:('if-eqz','v0, +05fh',99),20:('if-nez','v1, +031h',69),28:('if-nez','v1, +029h',69),36:('if-eqz','v0, +003h',39)}
    for pc,(op,text,target) in expected.items():
        if anchors.get(pc)!=(op,text) or relative_target(pc,text)!=target:raise ValueError('reset platform branch changed')
    if anchors.get(38)!=('goto','+1fh'):raise ValueError('third matched platform target changed')
    return dict(pauseFailureReturnsAtCodeUnit=99,matchedPlatformPathCodeUnit=69,otherPlatformPathCodeUnit=39)


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
    classes=None;ui=None;callers=[];fingerprints={}
    for bank,raw in images:
        current={c.get_name():c for c in DEX(raw).get_classes()}
        if bank==5:classes=current
        if bank==3:ui=current
        for owner,cls in current.items():
            if owner==RESET:continue
            for m in cls.get_methods():
                if not m.get_code():continue
                refs=[o.get_output().split('->',1)[1].split('(',1)[0] for o in m.get_instructions() if o.get_name().startswith('invoke-') and RESET+'->' in o.get_output()]
                if refs:callers.append(dict(bank=bank,className=owner,method=m.get_name(),descriptor=m.get_descriptor(),targetMethods=refs))
    def take(owner,name,descriptor=None):
        source=ui if owner.startswith('Lcom/') else classes
        ms=[m for m in source[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(ms)!=1 or not ms[0].get_code():raise ValueError('missing or ambiguous reset method '+owner+name)
        m=ms[0];fingerprints[(owner,name,m.get_descriptor())]=dict(bank=3 if source is ui else 5,className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest())
        ops=[];pc=0
        for o in m.get_instructions():ops.append((pc,o.get_name(),o.get_output()));pc+=o.get_length()//2
        return ops
    def require(ops,token):
        if not any(token in text for _,_,text in ops):raise ValueError('missing reset evidence '+token)
    reset=take(ROOT,'resetGimbal');branches=branch_routes(reset)
    for name in PLATFORMS:require(reset,'PlatformType;->'+name+' ')
    factory=take(SPECIAL,'getInstance');require(factory,'->useNewControl()Z');require(factory,NEW+'->getInstance()');require(factory,OLD+'->getInstance()')
    selector=take(SPECIAL,'useNewControl')
    selected=[text.split('->',1)[1].split(' ')[0] for _,op,text in selector if op=='sget-object' and 'ProductType;->' in text]
    if tuple(selected)!=PRODUCTS:raise ValueError('product selector changed')
    for owner in (OLD,NEW):
        for name in ('<init>','_reset','doPack'):take(owner,name)
        action=take(owner,'resetGimbal','()'+owner);require(action,'->_reset()V');require(action,'->mGimbalByte B')
        take(owner,'start','(J)V')
    require(take(OLD,'sendPack'),'CmdSet;->SPECIAL ');require(take(OLD,'sendPack'),'CmdIdSpecial$CmdIdType;->Control ')
    require(take(NEW,'start','(Ldji/midware/interfaces/DJIDataCallBack;)V'),'CmdIdSpecial$CmdIdType;->NewControl ')
    take(NEW,'doCommonPack');take(NEW,'setWorkView')
    for name in ('<init>','doPack','setReset'):take(RESET,name)
    for desc in ('()V','(Ldji/midware/interfaces/DJIDataCallBack;)V'):require(take(RESET,'start',desc),'CmdIdGimbal$CmdIdType;->ResetAndSetMode ')
    ui_paths=[]
    for owner,name in [('Lcom/dji/ronin/ui/create/CreateUtils;','recenterGimbal'),('Lcom/dji/ronin/widget/RoninBackInTextView$1;','onClick'),('Lcom/dji/ronin/ui/configuration/setting/SettingRoninsGeneralView;','onClick')]:
        ops=take(owner,name)
        for token in ('MotorEnabled',RESET+'->setGimbalMode(',RESET+'->setReset(Z)',RESET+'->start(Ldji/midware/interfaces/DJIDataCallBack;)V','DataGimbalControl$MODE;->OTHER '):require(ops,token)
        if any('->tryToPauseTheStabilizationIfNecessary(' in text or '->justSendPauseData(' in text for _,_,text in ops):raise ValueError('direct UI recenter now invokes stabilization dependency')
        ui_paths.append(dict(className=owner,method=name,bodyHex='fe01',connectionAndMotorChecksPresent=True,selectedMethodCallsStabilization=False,hg724UiReachabilityVerified=False))
    mode=MODEL+'DataGimbalControl$MODE;'
    modes=constructor_records([(op,text) for _,op,text in take(mode,'<clinit>')],mode)
    mode_values={k:v['arguments'][2] for k,v in modes.items()}
    if mode_values['OTHER']!=254:raise ValueError('default mode byte changed')
    command='Ldji/midware/data/config/P3/CmdIdSpecial$CmdIdType;'
    commands=constructor_records([(op,text) for _,op,text in take(command,'<clinit>')],command)
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(k):v for k,v in BANKS.items()},appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,
        genericResetBranches=dict(branches,matchingSourcePlatformNames=list(PLATFORMS),matchingPath='DataGimbalNewResetAndSetMode',otherPath='DataSpecialControl factory',otherPathReportsSuccessImmediately=True,hg724NameIsNotMatchedPlatform=True,livePlatformVerified=False),
        factory=dict(matchingSourceProductNames=list(PRODUCTS),matchingVariant=NEW,otherVariant=OLD,liveProductVerified=False,productTypeIsNotGimbalType=True),
        gimbalBody=dict(defaultModeName='OTHER',defaultModeValue=254,resetIsBoolean=True,defaultModeResetTrueHex=reset_mode_body(254,True).hex(),modeSourceEnums=mode_values,otherModesDeviceVerified=False),
        specialCommands={k:commands[k]['arguments'][2] for k in ('Control','NewControl')},
        oldSpecial=dict(bodyBytes=10,bodyContainsOtherSubsystemFields=True,resetLeavesFlycModeFieldUntouched=True,startLongUsesHandler=True,receiverRoutingVerified=False),
        newSpecial=dict(bodyContainsOtherSubsystemFields=True,completeBodyAudit=False),
        targetClaims=dict(inheritedMethodIsDirectBleWorkflow=False,specialControlTargetSupportVerified=False,recenterImplementationChanged=False,sourceDefaultMatchesHistoricalFe01Bytes=True,matchingBytesProveSameWorkflow=False),
        directUiRecenterPaths=ui_paths,externalResetClassCallers=callers,methods=list(fingerprints.values()),remaining=['Audit actual HG724 App action entry and model/platform/product mapping independently.', 'Do not emit mixed camera/flight special bodies or replace verified FE01 based on generic inheritance.', 'ACK/physical completion/cancel, persistence and direct-BLE routing remain unverified.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d method fingerprints; %d direct reset-class callers; no BLE/vendor execution.'%(len(r['methods']),len(r['externalResetClassCallers'])))

if __name__=='__main__':main()
