#!/usr/bin/env python3
"""Trace the conditional HG724 standalone input/value request, without execution."""
import argparse,hashlib,json
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_code_banks import UI_BANK_SHA256
from ronin_command_audit import DERIVED_SHA256
from ronin_numeric_params_trace import trace as numeric_trace


def trace(apk,sdk_path,ui_path):
    # The underlying audit validates the APK and both banks before analysis.
    numeric=numeric_trace(apk,sdk_path,ui_path)
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    ui_raw=ui_path.read_bytes()
    if hashlib.sha256(ui_raw).hexdigest()!=UI_BANK_SHA256:raise ValueError('pinned UI hash mismatch')
    classes={c.get_name():c for c in DEX(ui_raw).get_classes()};methods=[]
    def take(owner,name):
        choices=[m for m in classes[owner].get_methods() if m.get_name()==name]
        if len(choices)!=1 or not choices[0].get_code():raise ValueError('missing standalone model method')
        m=choices[0];methods.append(dict(className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest()));return m
    def require(m,token):
        if not any(token in o.get_output() for o in m.get_instructions()):raise ValueError('missing standalone model reference '+token)
    utils='Lcom/dji/ronin/util/CommonUtils;';upgrade='Lcom/dji/upgrade/util/CommonUtils;'
    chain=[('Lcom/dji/ronin/viewModel/CreateVideoViewModel;','supportProfileStandalone','->isLightDevice('),
           (utils,'isLightDevice','->supportSince2ndGenDevice()Z'),(utils,'supportSince2ndGenDevice','->is4thGenDevice()Z'),
           (utils,'is4thGenDevice','->isHG724()Z'),(utils,'isHG724',upgrade+'->isHG724()Z')]
    for owner,name,token in chain:require(take(owner,name),token)
    model=take(upgrade,'isHG724');require(model,'ModelName');require(model,'CacheHelper;->getProduct(');require(model,'Model;->HG724 ')
    ops=[(o.get_name(),o.get_output()) for o in model.get_instructions()]
    if ('if-ne','v0, v1, +004h') not in ops or ('const/4','v0, 1') not in ops or ('const/4','v0, 0') not in ops:raise ValueError('HG724 product equality branch changed')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,sdkDerivedSha256=DERIVED_SHA256,uiDerivedSha256=UI_BANK_SHA256,
                appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,
                conditionalAppModelBranchLinked=True,modelPredicate='CacheHelper.getProduct(ModelName) equals Model.HG724; not a BLE field or observed target value',
                sourceFacts=dict(writeCommand='04:0F',readCommand='04:10',inputSourceIndex=72,inputSourceValue=2,inputSourceWidth=1,
                                 sourceAndValueShareOneRequest=True,callerMustChooseInputSourceExplicitly=True,readDoesNotSelectInputSource=True),
                parameters=numeric['distinctCreatePath']['parameters'],inputSource=numeric['distinctCreatePath']['inputSource'],
                prerequisiteEvidence='protocol/research/ronin-numeric-params-evidence.json',modelMethods=methods)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','sdk','ui','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.sdk,a.ui);a.output.write_text(json.dumps(r,indent=2)+'\n')
    print('6 standalone records, %d conditional model methods; no App/hardware execution.'%len(r['modelMethods']))

if __name__=='__main__':main()
