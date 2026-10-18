#!/usr/bin/env python3
"""Static balance-menu source conditions and layouts; no UI/App/SDK execution."""
import argparse,hashlib,json,re,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_program_entry import view_literals,VIEW as INDEX
from ronin_calibration_entry import SECOND,THIRD,FOURTH,FIFTH
SWITCH='Lcom/dji/ronin/ui/entry/DeviceSwitchTextView;'
MODEL='Ldji/common/product/Model;'
ENTRY='Lcom/dji/ronin/ui/configuration/setting/BalanceCheckJumpEntryView;'
CHECK='Lcom/dji/ronin/ui/configuration/setting/SettingBalanceCheckView;'
VIDEO='Lcom/dji/ronin/ui/configuration/setting/SettingBalanceAjustView;'
GUIDE='Lcom/dji/ronin/ui/guide/BeginnerGuideManager;'
ADJUST='Lcom/dji/ronin/ui/monitor/state/GimbalAdjustView;'
SELECTED=('ConfigSettingBalanceTestHG701','GimbalAdjustHG701','GimbalVideoAdjustHG701','GimbalVideoAdjustRS3')
NEEDS_TEST={'RONIN2','RONINS','RONINSC','HG720'}|SECOND


def source_route(selected_model):
    """Explicit valid selected-item model only; not live identity or arbitrary mIndex."""
    if type(selected_model) is not str or not selected_model:raise ValueError('explicit source selected-item model required')
    needed=selected_model in NEEDS_TEST
    return dict(sourceSelectedModel=selected_model,needBalanceTest=needed,menuTarget='ConfigSettingBalanceTestHG701' if needed else 'GimbalVideoAdjustRS3',videoTestButtonVisibility=0 if needed else 8,forcedOldCheckAdjustTextVisibility=0 if selected_model=='RONINSC' or selected_model in SECOND|THIRD|FOURTH|FIFTH else 4,actualSelectedModelVerified=False,liveUiVerified=False,firmwareSupportVerified=False)


def model_literals(ops):
    return {m.group(1) for op,text in ops if op=='sget-object' for m in [re.search(re.escape(MODEL)+r'->(\w+) '+re.escape(MODEL),text)] if m}


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
    from androguard.core.axml import ARSCParser,AXMLPrinter
    cs=None;references=[]
    token=INDEX+'->GimbalAdjustHG701 '
    for bank,raw in images:
        current={c.get_name():c for c in DEX(raw).get_classes()}
        if bank==3:cs=current
        for owner,c in current.items():
            for m in c.get_methods():
                if not m.get_code():continue
                refs=[dict(opcode=i.get_name(),reference=i.get_output()) for i in m.get_instructions() if token in i.get_output()]
                if refs:references.append(dict(bank=bank,className=owner,method=m.get_name(),descriptor=m.get_descriptor(),references=refs))
    methods={}
    def take(owner,name,descriptor=None):
        ms=[m for m in cs[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(ms)!=1 or not ms[0].get_code():raise ValueError('missing/ambiguous balance entry '+owner+name)
        m=ms[0];methods[(owner,name,m.get_descriptor())]=dict(bank=3,className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest())
        return [(i.get_name(),i.get_output()) for i in m.get_instructions()]
    def require(ops,*tokens):
        for t in tokens:
            if not any(t in text for _,text in ops):raise ValueError('missing balance entry evidence '+t)
    for name,expected in [('is2ndGenDeviceIndex',SECOND),('isThirdGenDeviceIndex',THIRD),('is4thGenDeviceIndex',FOURTH),('is5thGenDeviceIndex',FIFTH)]:
        ops=take(SWITCH,name)
        if model_literals(ops)!=expected:raise ValueError('generation model set changed '+name)
        require(ops,'->mIndex I','->items [','DeviceTextViewItem;->model ')
    need=take(SWITCH,'isNeedBalanceTestDeviceIndex')
    if model_literals(need)!={'RONIN2','RONINS','RONINSC','HG720'}:raise ValueError('old balance-test direct set changed')
    require(need,'->is2ndGenDeviceIndex()Z','v0, v2, +003h','v0, v2, +028h','v0, v2, +01eh','v0, v2, +014h','v0, v1, +00ah')
    require(take(SWITCH,'is2ndOrThirdGenDeviceIndex'),'->is2ndGenDeviceIndex()Z','->isThirdGenDeviceIndex()Z')
    require(take(SWITCH,'supportSince2ndGenDeviceIndex'),'->is2ndOrThirdGenDeviceIndex()Z','->is4thGenDeviceIndex()Z','->is5thGenDeviceIndex()Z')
    require(take(SWITCH,'getModelOfDevice'),'->RONIN2 ','v2, v1, +003h')
    require(take(SWITCH,'checkMatchIndexAndModel'),'->getModelOfDevice(','v0, v1, +004h')
    require(take(ENTRY,'onClick'),'->isNeedBalanceTestDeviceIndex()Z','v2, +00ch','->ConfigSettingBalanceTestHG701 ','->GimbalVideoAdjustRS3 ','->showView(')
    take(ENTRY,'<init>')
    for name in ('onDeviceIndexChanged','onFinishInflate'):
        ops=take(VIDEO,name);require(ops,'->isNeedBalanceTestDeviceIndex()Z','->mBtnJump2BalanceCheck ','->setVisibility(I)V')
        if not any(op=='const/16' and text.endswith(', 8') for op,text in ops):raise ValueError('video test-button GONE changed')
    for name in ('onClick','onAttachedToWindow','onDetachedFromWindow','updateNextVisibility','updateNavBarItemVisibility'):take(VIDEO,name)
    click=take(VIDEO,'onClick');require(click,'->HG724 ','->getMountCameraRSC4()','->getPitchBalanceRSC4()','->getRollBalanceRSC4()','->getYawBalanceRSC4()','->startWebViewActivity(')
    # This is resource/link selection, not camera SDK control or remote fetching.
    for name in ('startWebViewActivity','startVideoPlayActivity'):take(VIDEO,name)
    require(take(CHECK,'onAttachedToWindow'),'->RONINSC ','->supportSince2ndGenDeviceIndex()Z','->mGimbalAdjustTv ','v2, 4','->setVisibility(I)V')
    for name in ('onClick','onFinishInflate','viewBalanceCheckVideoList','updateNextVisibility'):take(CHECK,name)
    require(take(CHECK,'startTestBalance'),'MotorEnabled','StartBalanceTest','CacheHelper;->performAction(')
    guide=take(GUIDE,'next');require(guide,'->isUseNewProfileDevice()Z','->GimbalVideoAdjustRS3 ','->GimbalVideoAdjustHG701 ')
    if any(token in text for _,text in guide):raise ValueError('guide now references adjust view')
    for name in ('exit','onAttachedToWindow'):take(ADJUST,name)
    nav=view_literals(take(INDEX,'<clinit>'),SELECTED)
    if set(nav)!=set(SELECTED):raise ValueError('missing selected view')
    layouts=[]
    with zipfile.ZipFile(apk) as z:
        resources=ARSCParser(z.read('resources.arsc'))
        for name,row in nav.items():
            configs=resources.get_resolved_res_configs(row['layoutId'])
            if len(configs)!=1:raise ValueError('ambiguous selected layout')
            _,path=configs[0];raw=z.read(path);xml=ET.fromstring(AXMLPrinter(raw).get_xml())
            layouts.append(dict(viewName=name,**row,path=path,sha256=hashlib.sha256(raw).hexdigest(),rootClass=xml.tag))
    roots={r['viewName']:r['rootClass'] for r in layouts}
    if roots!={'ConfigSettingBalanceTestHG701':CHECK[1:-1].replace('/','.'),'GimbalAdjustHG701':ADJUST[1:-1].replace('/','.'),'GimbalVideoAdjustHG701':VIDEO[1:-1].replace('/','.'),'GimbalVideoAdjustRS3':VIDEO[1:-1].replace('/','.')}:raise ValueError('selected root class changed')
    if nav['GimbalVideoAdjustHG701']['viewId']!=nav['GimbalVideoAdjustRS3']['viewId'] or nav['GimbalVideoAdjustHG701']['layoutId']!=nav['GimbalVideoAdjustRS3']['layoutId']:raise ValueError('shared video resource changed')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(b):p for b,p in BANKS.items()},appCodeExecuted=False,liveUiExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,sdkSendAdded=False,sdkReceiveAdded=False,hg724Command40PathEstablished=False,hg724Command40UnsupportedProven=False,methods=sorted(methods.values(),key=lambda r:(r['className'],r['method'],r['descriptor'])),layouts=layouts,uniqueLayoutCount=len({r['path'] for r in layouts}),navigation=nav,sourceModels=dict(needBalanceTest=sorted(NEEDS_TEST),second=sorted(SECOND),third=sorted(THIRD),fourth=sorted(FOURTH),fifth=sorted(FIFTH)),explicitHg724SelectedCase=source_route('HG724'),oldAdjustLiteralReferenceMethods=references,sourceConditions=dict(validSelectedItemRequiredForCase=True,indexIsNotDeviceType=True,menuUsesSelectedIndexNotActualFirmware=True,videoViewsShareResource=True,videoHg724BranchesSelectWebHelp=True,forcedOldViewVisibilityDoesNotEstablishNavigation=True),remaining=['Normal menu route for an explicit valid HG724 selected item bypasses the old balance-test page; this does not prove firmware lacks04:40.','Selected model, actual connected model, live navigation and firmware command support remain distinct.','Old adjust view resources and back-navigation references do not establish its entry path.','Banks1/7, reflection, residual stubs and other class loaders remain outside this scan.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d methods; %d view mappings/%d unique layouts; no execution.'%(len(r['methods']),len(r['layouts']),r['uniqueLayoutCount']))
if __name__=='__main__':main()
