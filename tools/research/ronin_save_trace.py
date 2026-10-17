#!/usr/bin/env python3
"""Scan all six pinned restored banks for save references; no vendor execution."""
import argparse,hashlib,json
from pathlib import Path
from ronin_static import APK_SHA256
BANKS={
0:'76002e76e02e1306ad197c4af127975d573999de174e5a9e44cc6f840196f621',
2:'de69497b77de530d0d559646dc6d3fb24569e2ba8ba9502216f3d6c9fd6f3bf8',
3:'bb50b39865520f55e97116ae1903bda3545b01c2fb7e2aba67a979dc264a9854',
4:'2d3ff70fb84eb02ac75949ca6e7d5cc849a7f9ef55029fd168890c6dbccb1d12',
5:'4fdbd74a05df63d72a0feb1c907d9395426ec3cdb5d6aeb45e3836d856d66654',
6:'057f13084cf969ffadcfa2150d1b3ae3ed8a7822c95fb54158781764c9156e2f'}
OWNER='Ldji/midware/data/model/P3/DataGimbalSaveUserParams;'
ENUM='Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;'


def classify_reference(op,text,owner):
    if 'SaveUserParams' not in text:return None
    if OWNER+'->' in text and op.startswith('invoke-'):
        return 'internal-invoke' if owner==OWNER else 'external-direct-invoke'
    if op=='new-instance' and OWNER in text:return 'allocation'
    if op=='const-class' and OWNER in text:return 'class-literal'
    if op.startswith('const-string'):return 'string-literal-not-proven-reflection'
    if ENUM+'->SaveUserParams ' in text:return 'command-enum-reference'
    return 'other-reference'


def scan(apk,bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    # Validate every bank before loading the optional parser or accepting partial results.
    images=[]
    for bank,expected in BANKS.items():
        raw=(bank_dir/('business-%02d-code-restored.dex'%bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('restored bank hash mismatch: %02d'%bank)
        images.append((bank,raw))
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    rows=[];methods=[]
    for bank,raw in images:
        dex=DEX(raw);classes=dex.get_classes();readable=0;total=0;instructions=0
        for cls in classes:
            for method in cls.get_methods():
                total+=1
                if not method.get_code():continue
                readable+=1;references=[];offset=0
                for instruction in method.get_instructions():
                    op,text=instruction.get_name(),instruction.get_output();kind=classify_reference(op,text,cls.get_name())
                    if kind:references.append(dict(kind=kind,instructionByteOffset=offset))
                    offset+=instruction.get_length();instructions+=1
                if references:methods.append(dict(segment=bank,className=cls.get_name(),method=method.get_name(),descriptor=method.get_descriptor(),codeOffset=method.get_code_off(),instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest(),references=references))
        rows.append(dict(segment=bank,derivedSha256=BANKS[bank],classCount=len(classes),methodCount=total,methodWithCodeCount=readable,instructionCount=instructions,stringTableMatches=sorted(set(str(s) for s in dex.get_strings() if 'SaveUserParams' in str(s)))))
        print('bank%02d: %d methods with code, %d instructions'%(bank,readable,instructions),flush=True)
    external=[dict(segment=m['segment'],className=m['className'],method=m['method'],descriptor=m['descriptor']) for m in methods if any(r['kind']=='external-direct-invoke' for r in m['references'])]
    return dict(schemaVersion=1,apkSha256=APK_SHA256,appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,wholeAppRecovered=False,allScannedBodiesRecovered=False,indirectReflectionResolved=False,targetModelCallPathEstablished=False,scannedBanks=list(BANKS),unrestoredBanks=[1,7],scope='instruction references in six pinned restored banks; not whole-App or firmware support proof',banks=rows,externalDirectCallers=external,methods=methods)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=scan(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,indent=2)+'\n');print('%d methods contain save references; %d external direct callers in scan scope'%(len(r['methods']),len(r['externalDirectCallers'])))
if __name__=='__main__':main()
