#!/usr/bin/env python3
"""Restore all structurally corroborated banks of the pinned APK, offline only."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from ronin_static import APK_SHA256, maps_in, recover
from ronin_code_restore import backup_table, restore_image


def restore_banks(apk, output):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:
        raise ValueError('APK hash mismatch')
    with zipfile.ZipFile(str(apk)) as archive:data=archive.read('classes.dex')
    maps=maps_in(data)
    if len(maps)!=8:raise ValueError('unexpected hidden map count')
    output.mkdir(parents=True,exist_ok=True)
    metadata=recover(data,output)
    report=[]
    for record in metadata:
        index=record['index'];base=maps[index]['base']
        limit=maps[index+1]['base'] if index+1<len(maps) else len(data)
        name=('classes%s.dex.dgc2'%('' if index==0 else index+1)).encode('ascii')
        bank=backup_table(data,base,limit,name)
        row=dict(segment=index,backupName=name.decode('ascii'),bankSha256=bank['bankSha256'],
                 backupRecords=len(bank['rows']),originalSize=bank['originalSize'],structurallyReadable=record['structurallyReadable'])
        if not record['structurallyReadable']:
            row['restored']=False;row['remaining']='metadata lacks corroborating unchanged string-id suffix; code slots not restored'
        else:
            image,records=restore_image((output/record['file']).read_bytes(),bank)
            filename='business-%02d-code-restored.dex'%index
            (output/filename).write_bytes(image)
            row.update(restored=True,restoredCodeItems=len(records),derivedFile=filename,derivedSha256=hashlib.sha256(image).hexdigest())
            # Full slot audit stays ignored, separate from concise source evidence.
            (output/('bank-%02d-slots.json'%index)).write_text(json.dumps(records,indent=2)+'\n')
        report.append(row)
    result=dict(schemaVersion=1,apkSha256=APK_SHA256,appCodeExecuted=False,targetDeviceVerified=False,
                wholeProtocolRecovered=False,wholeAppRecovered=False,banks=report,
                restoredCodeItems=sum(r.get('restoredCodeItems',0) for r in report))
    (output/'code-banks.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


UI_BANK_SHA256='bb50b39865520f55e97116ae1903bda3545b01c2fb7e2aba67a979dc264a9854'
CONTROL_MODE_KEYS=('FollowSpeedMode','FollowDeadZoneMode','FollowAcceMode','RcSpeedMode','RcDeadZoneMode','RcSmoothMode')


def inspect_control_modes(image_path):
    raw=image_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=UI_BANK_SHA256:raise ValueError('pinned UI bank hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    matches=[]
    for cls in DEX(raw).get_classes():
        for method in cls.get_methods():
            if not method.get_code():continue
            references=set()
            for instruction in method.get_instructions():
                references.update(key for key in CONTROL_MODE_KEYS if key in instruction.get_output())
            if not references:continue
            matches.append(dict(className=cls.get_name(),method=method.get_name(),descriptor=method.get_descriptor(),
                                codeOffset=method.get_code_off(),instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest(),
                                referencedModeKeys=sorted(references)))
    return dict(schemaVersion=1,apkSha256=APK_SHA256,derivedSha256=UI_BANK_SHA256,segment=3,
                appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,
                fieldSemanticsFullyAudited=False,methods=matches)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apk',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--inspect-control-modes',action='store_true',help='Optional Androguard metadata-only caller fingerprints')
    a=p.parse_args();r=restore_banks(a.apk,a.output)
    if a.inspect_control_modes:
        refs=inspect_control_modes(a.output/'business-03-code-restored.dex')
        (a.output/'control-mode-references.json').write_text(json.dumps(refs,indent=2)+'\n')
    print('%d banks restored, %d exact code items; other banks remain explicitly incomplete; no App executed.'%(sum(row['restored'] for row in r['banks']),r['restoredCodeItems']))

if __name__=='__main__':main()
