#!/usr/bin/env python3
"""Static source navigation/resource evidence; never inflate or execute App views."""
import argparse,hashlib,json,re,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from ronin_save_trace import BANKS
from ronin_static import APK_SHA256
UI='Lcom/dji/ronin/'
VIEW=UI+'home/UIViewManager$ViewIndex;'
JUMP=UI+'widget/RoninJumpTextView;'
MANAGER=UI+'home/UIViewManager;'
HELP=UI+'ui/create/CreateMainJumpEntryView;'
PRODUCT='Ldji/sdksharedlib/hardware/abstractions/product/DJIProductAbstraction;'
PLATFORM='Ldji/midware/component/DJIComponentManager$PlatformType;'
SELECTED=('CreateRoninNew','CreatePanoRonins','CreateTrackRonins','CreatePathDelayRonins')


def switch_assignments(ops,enum):
    result={}
    for i,(op,text) in enumerate(ops):
        if op!='sget-object' or enum+'->' not in text:continue
        reg=text.split(', ')[0];name=text.split('->')[1].split(' ')[0]
        if name!='HG724':continue
        block=ops[i+1:i+5]
        if len(block)!=4 or block[0] != ('invoke-virtual',reg+', '+enum+'->ordinal()I') or block[1][0]!='move-result' or block[2][0] not in ('const/4','const/16','const') or block[3][0]!='aput':raise ValueError('unsupported enum switch assignment')
        index=block[1][1];value_reg,number=block[2][1].split(', ')
        registers=block[3][1].split(', ')
        if registers[0]!=value_reg or registers[2]!=index or name in result:raise ValueError('ambiguous enum switch assignment')
        result[name]=int(number)
    return result


def view_literals(ops,selected=None):
    selected=SELECTED if selected is None else selected
    registers={};result={}
    for op,text in ops:
        if op.startswith('const-string'):
            reg,value=text.split(', ',1);registers[reg]=value
        elif op in ('const','const/4','const/16'):
            reg,value=text.split(', ');registers[reg]=int(value)
        elif op.startswith('invoke-direct') and VIEW+'-><init>(' in text:
            raw=text.split(', '+VIEW)[0];regs=re.findall(r'v\d+',raw)
            if ' ... ' in raw:regs=['v%d'%i for i in range(int(regs[0][1:]),int(regs[-1][1:])+1)]
            fields=[registers.get(r) for r in regs[1:5]]
            if fields[0] in selected:
                if type(fields[0]) is not str or any(type(v) is not int for v in fields[1:]) or fields[0] in result:raise ValueError('unresolved selected view literals')
                result[fields[0]]=dict(ordinal=fields[1],viewId=fields[2],layoutId=fields[3])
        elif op in ('new-instance','sget-object','move-result','move-result-object'):registers[text.split(', ')[0]]=None
        elif op.startswith(('invoke-','sput-object')) or op=='return-void':pass
        else:raise ValueError('unsupported static view prefix '+op)
    return result


def layout_facts(xml):
    root=ET.fromstring(xml);android='{http://schemas.android.com/apk/res/android}'
    return dict(rootClass=root.tag,jumpIds=[e.attrib[android+'id'] for e in root.iter() if e.tag=='com.dji.ronin.widget.RoninJumpTextView' and android+'id' in e.attrib])


def direct_return(ops):
    if len(ops)<2:raise ValueError('incomplete switch return')
    (op,text),(ret,reg)=ops[:2]
    if op in ('const/4','const/16','const') and ret=='return' and text.split(', ')[0]==reg:return int(text.split(', ')[1])
    if op=='sget-object' and ret=='return-object' and text.split(', ')[0]==reg:return text.split(', ',1)[1]
    raise ValueError('non-direct switch return requires separate audit')


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
    classes={bank:{c.get_name():c for c in DEX(raw).get_classes()} for bank,raw in images.items()};methods={}
    def take(bank,owner,name,descriptor=None):
        choices=[m for m in classes[bank][owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(choices)!=1 or not choices[0].get_code():raise ValueError('missing or ambiguous entry method '+name)
        m=choices[0];methods[(bank,owner,name,m.get_descriptor())]=dict(bank=bank,className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());return m
    def ops(m):return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    def require(m,*tokens):
        for token in tokens:
            if not any(token in text for _,text in ops(m)):raise ValueError('missing entry source token '+token)
    def selected_return(m,case):
        instructions={};offset=0
        for o in m.get_instructions():instructions[offset]=o;offset+=o.get_length()
        found=[]
        for pos,o in instructions.items():
            if o.get_name()!='packed-switch':continue
            payload=instructions[pos+2*o.get_ref_off()]
            if case not in payload.get_values():continue
            target=pos+2*payload.get_targets()[payload.get_values().index(case)]
            first=instructions[target];second=instructions[target+first.get_length()]
            found.append(dict(switchByteOffset=pos,case=case,targetByteOffset=target,value=direct_return([(first.get_name(),first.get_output()),(second.get_name(),second.get_output())])))
        if len(found)!=1:raise ValueError('ambiguous source switch case')
        return found[0]
    mapping=switch_assignments(ops(take(5,PRODUCT[:-1]+'$2;','<clinit>')),PLATFORM)
    case=mapping['HG724'];handle=selected_return(take(5,PRODUCT,'isHandle'),case);model=selected_return(take(5,PRODUCT,'getModel'),case)
    if handle['value']!=1 or model['value']!='Ldji/common/product/Model;->HG724 Ldji/common/product/Model;':raise ValueError('HG724 platform classification changed')
    require(take(5,PRODUCT,'updateProduct'),'IsHandleDevice','->isHandle(','->notifyValueChangeForKey(')
    common=take(3,UI+'util/CommonUtils;','isHandheldDevice');require(common,'IsHandleDevice','->getProduct(','->toBool(')
    # This source helper reads cache; its component argument is not a model query.
    require(take(3,MANAGER,'showMainView'),'->isHandheldDevice(','->MainRoninNew ')
    take(3,MANAGER,'showView','(Lcom/dji/ronin/home/UIViewManager$ViewIndex;)V')
    require(take(3,MANAGER,'showView','(I I I)V'),'->inflate(')
    for name in ('init','onClick','checkCreateIsWorking','checkIsValuableForCreate','isCreateModeView','showSubView','showNext'):
        take(3,JUMP,name)
    require(take(3,JUMP,'init'),'->findByViewId(')
    require(take(3,JUMP,'showNext'),'->showView(')
    gate=take(3,JUMP,'checkIsValuableForCreate');require(gate,'->isGimbalConnected()','MotorEnabled','->isConnectShutter()')
    # Presence of this helper is not proof that onClick invokes it.
    if any('->checkIsValuableForCreate(' in text for _,text in ops(take(3,JUMP,'onClick'))):raise ValueError('selected click path changed')
    view_map=view_literals(ops(take(3,VIEW,'<clinit>')))
    if set(view_map)!=set(SELECTED):raise ValueError('selected view literals missing')
    take(3,VIEW,'<init>');take(3,VIEW,'findByViewId');take(3,VIEW,'getViewId')
    help_map=switch_assignments(ops(take(3,HELP[:-1]+'$1;','<clinit>')),'Ldji/common/product/Model;')
    # String-return blocks are retained as fingerprints; direct_return only models int/field returns.
    require(take(3,HELP,'getProductParamForCableCapabilityUrl'),'rs-4-mini')
    require(take(3,HELP,'lambda$initView$1'),'ShutterCableCapabilityActivity;','product_name','->getProductParamForCableCapabilityUrl()')
    layouts=[]
    with zipfile.ZipFile(str(apk)) as archive:
        resources=ARSCParser(archive.read('resources.arsc'))
        for name,row in view_map.items():
            configs=resources.get_resolved_res_configs(row['layoutId'])
            if len(configs)!=1:raise ValueError('layout configuration ambiguity')
            _,path=configs[0];raw=archive.read(path);fact=layout_facts(AXMLPrinter(raw).get_xml())
            layouts.append(dict(viewName=name,**row,path=path,sha256=hashlib.sha256(raw).hexdigest(),**fact))
    main=next(l for l in layouts if l['viewName']=='CreateRoninNew')
    for row in layouts:
        if row['viewName']!='CreateRoninNew' and '@%08X'%row['viewId'] not in main['jumpIds']:raise ValueError('program jump id absent from selected menu layout')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(k):BANKS[k] for k in images},appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,liveUiExecuted=False,fullModelWorkflowVerified=False,
        scope='Conditional product-cache source classification and selected menu/resource/navigation declarations; no Android execution',hg724PlatformSwitchCase=case,hg724HandleBranch=handle,hg724ModelBranch=model,handheldHelperReadsCacheKey='IsHandleDevice',componentArgumentIgnoredByHandheldHelper=True,
        helpHg724Case=help_map['HG724'],helpRouteIsShutterCableNotProgram=True,helperHasShutterCheck=True,selectedClickDirectlyCallsShutterHelper=False,fullShutterGateReachabilityVerified=False,
        layouts=layouts,methods=list(methods.values()),remaining=['Actual platform/monitor discovery and cache freshness are unverified.', 'showMainView MainRoninNew is not itself proof that its create menu is mounted for a live target.', 'Resource ids/classes and generic navigation do not prove all click guards or callback registration paths.', 'Program byte routing/units, camera separation, firmware acceptance/cancellation and hardware effects still require audit.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d method fingerprints, %d layouts; conditional HG724 classification only, no execution.'%(len(r['methods']),len(r['layouts'])))
if __name__=='__main__':main()
