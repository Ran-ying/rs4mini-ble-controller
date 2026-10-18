#!/usr/bin/env python3
"""Static calibration-view entry/gates; no App/UI/SDK or hardware execution."""
import argparse,hashlib,json,re,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_program_entry import view_literals
from ronin_sensor_calibration import AUTO,PART,PUSH
from ronin_subscription_trace import constructor_records
from ronin_external_device import source_enum
OWNER='Lcom/dji/ronin/ui/configuration/system/ConfigNewSettingsView;'
WRAPPER='Lcom/dji/ronin/ui/configuration/ConfigSystemStatusView;'
TAB='Lcom/dji/ronin/ui/tab/TabViewPagerBaseView;'
SWITCH='Lcom/dji/ronin/ui/entry/DeviceSwitchTextView;'
COMMON='Lcom/dji/ronin/util/CommonUtils;'
UPGRADE='Lcom/dji/upgrade/util/CommonUtils;'
SUPPORTED='Lcom/dji/ronin/util/ISupportedVersion;'
MODEL='Ldji/common/product/Model;'
THRESHOLD='00.02.32.25'
SECOND={'HG702','HG710'}
THIRD={'HG703','HG711','HG720'}
FOURTH={'HG704','HG714','HG724'}
FIFTH={'HG705','HG715'}
OLD={'RONIN2','RONINS','RONINSC'}|SECOND|THIRD


def canonical_version_number(text):
    """Offline canonical unsigned-decimal components only; not arbitrary Java strings."""
    if text is None or text=='':return 0
    if type(text) is not str or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)*',text):raise ValueError('canonical decimal version required')
    value=0
    for part in text.split('.'):
        number=int(part)
        if number>2147483647:raise ValueError('component exceeds Java int32')
        value=((value*256+number+2**63)%2**64)-2**63
    return value


def visibility_case(selected_model,cached_model,*,imu_outcome='not-observed',imu_version=None):
    if any(v is not None and type(v) is not str for v in (selected_model,cached_model)):raise ValueError('explicit model names or None required')
    if imu_outcome not in ('not-observed','success','failure'):raise ValueError('explicit IMU outcome required')
    direct=selected_model in SECOND|THIRD|FOURTH|FIFTH
    advanced=True if direct else None if imu_outcome=='not-observed' else False if imu_outcome=='failure' else canonical_version_number(imu_version)>canonical_version_number(THRESHOLD)
    return dict(normalVisible=cached_model in OLD,advancedVisible=advanced,versionQueryRequired=not direct,selectedModel=selected_model,cachedModel=cached_model,liveVisibilityVerified=False)


def action_case(action,*,motor_enabled):
    if action not in ('normal','advanced') or type(motor_enabled) is not bool:raise ValueError('named action and explicit cached motor boolean required')
    return dict(sourcePart='GYRO' if action=='normal' else 'AUTO',methodGateAllowsStart=motor_enabled,bodyHex=('05' if action=='normal' else '00') if motor_enabled else None,firmwareAcceptanceVerified=False)


def threshold_literal(ops):
    found=[]
    for i,(op,text) in enumerate(ops):
        if op!='sput-wide' or SUPPORTED+'->IMU_VERSION_SUPPORT_ADVANCED_CALIBRATION J' not in text:continue
        if i<3:raise ValueError('missing threshold producer')
        (a,x),(b,y),(c,z)=ops[i-3:i]
        if not a.startswith('const-string') or b!='invoke-static' or COMMON+'->formatVersion(Ljava/lang/String;)J' not in y or c!='move-result-wide':raise ValueError('unresolved threshold producer')
        reg,literal=x.split(', ',1)
        if y.split(', ')[0]!=reg or text.split(', ')[0]!=z:raise ValueError('threshold register mismatch')
        found.append(literal)
    if len(found)!=1:raise ValueError('missing/ambiguous threshold')
    return found[0]


def model_predicate(ops):
    if [o for o,_ in ops]!=['const-string/jumbo','invoke-static','move-result-object','sget-object','if-ne','const/4','return','const/4','return']:raise ValueError('unresolved ModelName predicate shape')
    if not ops[0][1].endswith(', ModelName') or 'CacheHelper;->getProduct(Ljava/lang/String;)' not in ops[1][1] or not ops[5][1].endswith(', 1') or not ops[7][1].endswith(', 0'):raise ValueError('source predicate is not cache equality')
    match=re.search(re.escape(MODEL)+r'->(\w+) '+re.escape(MODEL),ops[3][1])
    if not match:raise ValueError('unresolved model field')
    return match[1]


def trace(apk,bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    images={}
    for bank in (3,5):
        raw=(bank_dir/('business-%02d-code-restored.dex'%bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=BANKS[bank]:raise ValueError('restored bank hash mismatch')
        images[bank]=raw
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    from androguard.core.axml import ARSCParser,AXMLPrinter
    classes={b:{c.get_name():c for c in DEX(raw).get_classes()} for b,raw in images.items()};methods={}
    def take(bank,owner,name,descriptor=None):
        ms=[m for m in classes[bank][owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(ms)!=1 or not ms[0].get_code():raise ValueError('missing/ambiguous entry method '+name)
        m=ms[0];methods[(bank,owner,name,m.get_descriptor())]=dict(bank=bank,className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    def require(ops,*tokens):
        for token in tokens:
            if not any(token in t for _,t in ops):raise ValueError('missing entry source token '+token)
    init=take(3,OWNER,'<clinit>');require(init,PART+'->GYRO ',PART+'->AUTO ','->CALIBRATION_PART_NORMAL ','->CALIBRATION_PART_ADVANCED ')
    for name,field in (('startCalibration','CALIBRATION_PART_NORMAL'),('startAdvancedCalibration','CALIBRATION_PART_ADVANCED')):
        ops=take(3,OWNER,name);require(ops,AUTO+'-><init>()V',OWNER+'->'+field+' ',AUTO+'->setCalType(',AUTO+'->start(')
        if any('DataGimbalSetUserParams' in t for _,t in ops):raise ValueError('UI route now uses parameter transaction')
    for name,target in (('systemCalibration','startCalibration'),('advancedCalibration','startAdvancedCalibration')):
        ops=take(3,OWNER,name);require(ops,'MotorEnabled','CacheHelper;->getGimbal(','CacheHelper;->toBool(',OWNER+'->'+target+'()V','Toast;->show()V')
        if not any(o=='if-nez' for o,_ in ops):raise ValueError('motor gate branch changed')
    require(take(3,OWNER[:-1]+'$11;','onClick'),OWNER+'->-$$Nest$msystemCalibration(')
    require(take(3,OWNER[:-1]+'$13;','onClick'),OWNER+'->-$$Nest$madvancedCalibration(')
    for name in ('showConfirmDialog','onClick','-$$Nest$msystemCalibration','-$$Nest$madvancedCalibration'):take(3,OWNER,name)
    require(take(3,OWNER,'updateSystemConfigItems'),COMMON+'->isOldSupportDevices()Z','->mSystemCalibrateTv ','v1, 8','v1, 0')
    require(take(3,OWNER,'updateFunctionVisibility'),SWITCH+'->supportSince3rdGenDeviceIndex()Z',SWITCH+'->is2ndGenDeviceIndex()Z','VersionSupportUtils;->checkIMUVersion(')
    groups={}
    for name,expected in (('is2ndGenDeviceIndex',SECOND),('isThirdGenDeviceIndex',THIRD),('is4thGenDeviceIndex',FOURTH),('is5thGenDeviceIndex',FIFTH)):
        ops=take(3,SWITCH,name);require(ops,'->mIndex I','->items [','DeviceTextViewItem;->model ')
        names={m[1] for o,t in ops if o=='sget-object' for m in [re.search(re.escape(MODEL)+r'->(\w+) '+re.escape(MODEL),t)] if m}
        if names!=expected:raise ValueError('device-index generation set changed')
        groups[name]=sorted(names)
    require(take(3,SWITCH,'supportSince3rdGenDeviceIndex'),'->isThirdGenDeviceIndex()Z','->is4thGenDeviceIndex()Z','->is5thGenDeviceIndex()Z')
    require(take(3,COMMON,'isOldSupportDevices'),'->isRonin2(','->isRoninS(','->isHG701(','->is2ndGenDevice()Z','->isThirdGenDevice()Z')
    require(take(3,COMMON,'is2ndGenDevice'),'->isHG702(','->isHG710(')
    require(take(3,COMMON,'isThirdGenDevice'),'->isHG703(','->isHG711(','->isHG720(')
    models={}
    for name in ('isRonin2','isRoninS','isHG701','isHG702','isHG710','isHG703','isHG711','isHG720'):
        require(take(3,COMMON,name),UPGRADE+'->'+name+'(')
        models[name]=model_predicate(take(3,UPGRADE,name))
    if set(models.values())!=OLD:raise ValueError('old-device cache set changed')
    literal=threshold_literal(take(3,SUPPORTED,'<clinit>'))
    if literal!=THRESHOLD or SUPPORTED not in classes[3][OWNER].get_interfaces():raise ValueError('threshold field/interface changed')
    version_ops=take(3,COMMON,'formatVersion');require(version_ops,'v4, 10','v4, 256','Integer;->parseInt(')
    if not all(any(o==expected for o,_ in version_ops) for expected in ('mul-long/2addr','add-long/2addr')):raise ValueError('source version fold changed')
    support=take(3,OWNER,'supportAdvancedCali');require(support,'->IMU_VERSION_SUPPORT_ADVANCED_CALIBRATION J')
    if not any(o=='if-lez' for o,_ in support):raise ValueError('strict version threshold changed')
    cb=OWNER[:-1]+'$2;'
    require(take(3,cb,'lambda$onVersionGetSuccess$0'),'->-$$Nest$msupportAdvancedCali(','->setVisibility(I)V')
    require(take(3,cb,'lambda$onVersionGetFail$1'),'v1, 8','->setVisibility(I)V')
    for name in ('onVersionGetSuccess','onVersionGetFail'):require(take(3,cb,name),OWNER+'->post(Ljava/lang/Runnable;)Z')
    take(3,'Lcom/dji/ronin/util/VersionSupportUtils;','checkIMUVersion')
    if take(3,OWNER[:-1]+'$16;','onSuccess')!=[('return-void','')]:raise ValueError('normal ACK callback changed')
    require(take(3,OWNER[:-1]+'$17;','onSuccess'),OWNER+'->-$$Nest$msetTimer(')
    require(take(3,OWNER,'setTimer'),'v0, 60000','Observable;->timer(')
    timeout=take(3,OWNER[:-1]+'$18;','onNext','(Ljava/lang/Long;)V');require(timeout,'->-$$Nest$mdisposeTimer(','->-$$Nest$mdismissProgressDialog(','->-$$Nest$mshowConfirmIconDlg(')
    if any('midware/data/model/' in t for o,t in timeout if o.startswith('invoke-')):raise ValueError('timeout now directly invokes protocol model')
    for name in ('disposeTimer','dismissProgressDialog','onAttachedToWindow','onDetachedFromWindow'):take(3,OWNER,name)
    sensor=take(3,OWNER,'onEvent3MainThread','('+PUSH+')V');require(sensor,'->mAdvancedCalibrating Z',PUSH+'->getProgress()I',', %','->disposeTimer()V')
    take(3,OWNER,'onEvent3MainThread','('+AUTO+')V')
    require(take(3,TAB,'<init>'),'ArrayList;-><init>()V','->mViewList ')
    require(take(3,TAB,'onFinishInflate'),TAB+'->initData()V',TAB+'->initView()V')
    require(take(3,TAB,'initView'),'RoninCommonVpAdapter;-><init>','ViewPager;->setAdapter(')
    require(take(3,WRAPPER,'initData'),OWNER+'-><init>(Landroid/content/Context;)V','List;->add(')
    entries=view_literals(take(3,'Lcom/dji/ronin/home/UIViewManager$ViewIndex;','<clinit>'),('SystemStatus',))
    inner=take(3,OWNER,'initView');require(inner,'v0, 2131558515',OWNER+'->inflate(')
    with zipfile.ZipFile(str(apk)) as archive:
        resources=ARSCParser(archive.read('resources.arsc'));layouts=[]
        for label,layout_id in (('SystemStatus',entries['SystemStatus']['layoutId']),('SettingsInner',2131558515)):
            configs=resources.get_resolved_res_configs(layout_id)
            if len(configs)!=1:raise ValueError('layout ambiguity')
            _,path=configs[0];raw=archive.read(path);xml=ET.fromstring(AXMLPrinter(raw).get_xml());layouts.append(dict(name=label,layoutId=layout_id,path=path,sha256=hashlib.sha256(raw).hexdigest(),rootClass=xml.tag))
        if layouts[0]['rootClass']!='com.dji.ronin.ui.configuration.ConfigSystemStatusView':raise ValueError('system status root changed')
    parts=source_enum(constructor_records(take(5,PART,'<clinit>'),PART))
    packed=take(5,AUTO,'doPack');require(packed,'->_sendData [B','->mCalType ',PART+'->value I')
    if not any(o=='int-to-byte' for o,_ in packed):raise ValueError('source calibration part packing changed')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(b):BANKS[b] for b in (3,5)},appCodeExecuted=False,liveUiExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,sdkSendAdded=False,sdkReceiveAdded=False,methods=sorted(methods.values(),key=lambda m:(m['bank'],m['className'],m['method'],m['descriptor'])),layouts=layouts,navigation=entries,
        sourceParts={r['name']:r['sourceId'] for r in parts},generationModels=groups,oldCacheModelPredicates=models,threshold=dict(declaringInterface=SUPPORTED,literal=literal,number=canonical_version_number(literal),comparison='strict-greater-than',canonicalOfflineParserOnly=True),
        sourceActions=dict(normal=dict(viewMethod='systemCalibration',startMethod='startCalibration',part='GYRO',bodyHex='05'),advanced=dict(viewMethod='advancedCalibration',startMethod='startAdvancedCalibration',part='AUTO',bodyHex='00'),bothRequireCachedMotorEnabled=True,uiSystemCalibrationIsSystemCalc=False),
        hg724ExplicitCase=visibility_case('HG724','HG724'),lifecycle=dict(selectedUiIndexAndCachedModelAreIndependent=True,liveIndexOrCacheFreshnessVerified=False,imuVersionCallbackPostedAsynchronously=True,callbackOrderingOrRaceAbsenceVerified=False,advancedAckStartsUiTimerMs=60000,normalAckCallbackIsEmpty=True,timeoutDirectlyInvokesFirmwareStop=False,transitiveFirmwareStopProven=False,processingSetsLocalAdvancedFlag=True,sourceUiProgressRenderedWithPercentSuffix=True,requestSequenceAssociationVerified=False),
        scope=dict(parsedBanks=[3,5],unrestoredBanks=[1,7],fullActivityReachabilityVerified=False,mountOrVisibilityDoesNotProveFirmwareSupport=True),remaining=['HG724 selected-item/model-cache source case is conditional, not live device identity or capability.','Visibility and direct method MotorEnabled gates are distinct; hidden normal action is not proof firmware lacks GYRO.','Async version callbacks and source local progress flag are not a per-request firmware transaction.','No actual UI, address routing, physical effects or firmware cancellation were tested.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d methods, %d layouts; conditional model/UI gates only'%(len(r['methods']),len(r['layouts'])))
if __name__=='__main__':main()
