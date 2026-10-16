#!/usr/bin/env python3
"""Fingerprint the HG702 calibration override and status codec, never execute it."""
import argparse
import hashlib
import json
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_command_audit import DERIVED_SHA256
from ronin_model_trace import enum_entry

MODEL = 'Ldji/midware/data/model/P3/'
ABSTRACTION = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/'
TARGETS = {
    ABSTRACTION+'DJIGimbalRonin2Abstraction;': {'startAutoTune'},
    ABSTRACTION+'DJIGimbalHG702Abstraction;': {'startAutoTune', 'onEvent3BackgroundThread'},
    ABSTRACTION+'DJIGimbalHG724Abstraction;': {'<init>'},
    MODEL+'DataGimbalCalibrate;': {'doPack','setStartCalbrate','start'},
    MODEL+'DataGimbalGetPushCalibrationStatus;': {'setPushRecData','start','getCalibratePercent','getCalibrateStatus'},
    MODEL+'DataGimbalGetPushCalibrationStatus$CalibrationStatus;': {'<clinit>','find','<init>'},
    'Ldji/midware/data/config/P3/DataConfig$NEEDACK;': {'<clinit>'},
    'Ldji/midware/data/packages/P3/SendPack;': {'doPack'},
}


def require_reference(operations, token):
    if not any(token in text for _, text in operations):
        raise ValueError('missing expected source reference: '+token)


def trace(apk, dex_path):
    if hashlib.sha256(apk.read_bytes()).hexdigest() != APK_SHA256:
        raise ValueError('pinned APK hash mismatch')
    raw=dex_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DERIVED_SHA256:
        raise ValueError('pinned restoration view hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    classes={c.get_name():c for c in DEX(raw).get_classes()}
    hg724=classes[ABSTRACTION+'DJIGimbalHG724Abstraction;']
    if hg724.get_superclassname()!=ABSTRACTION+'DJIGimbalHG702Abstraction;' or any(m.get_name()=='startAutoTune' for m in hg724.get_methods()):
        raise ValueError('unexpected HG724 override/inheritance')
    methods=[]
    for name,wanted in TARGETS.items():
        for method in classes[name].get_methods():
            if method.get_name() not in wanted or not method.get_code():continue
            if method.get_name()=='onEvent3BackgroundThread' and 'DataGimbalGetPushCalibrationStatus;' not in method.get_descriptor():continue
            ops=[(o.get_name(),o.get_output()) for o in method.get_instructions()]
            if name.endswith('DataGimbalCalibrate;') and method.get_name()=='start':
                require_reference(ops,'DataConfig$NEEDACK;->NO ')
                require_reference(ops,'CmdIdGimbal$CmdIdType;->SetCalibration ')
            if name.endswith('DataGimbalGetPushCalibrationStatus;') and method.get_name()=='start':
                require_reference(ops,'DataConfig$NEEDACK;->YES ')
                require_reference(ops,'CmdIdGimbal$CmdIdType;->GetPushCalibration ')
            if name.endswith('DJIGimbalHG702Abstraction;') and method.get_name()=='startAutoTune':
                require_reference(ops,'DataGimbalCalibrate;->setStartCalbrate(Z)V')
            methods.append(dict(className=name,method=method.get_name(),descriptor=method.get_descriptor(),
                                codeOffset=method.get_code_off(),instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest()))
    enums={}
    for name,labels in [(MODEL+'DataGimbalGetPushCalibrationStatus$CalibrationStatus;',['UnStart','Processing','Complete','Failure','UnKnown']),
                        ('Ldji/midware/data/config/P3/DataConfig$NEEDACK;',['NO','YES'])]:
        initializer=next(m for m in classes[name].get_methods() if m.get_name()=='<clinit>')
        ops=[(o.get_name(),o.get_output()) for o in initializer.get_instructions()]
        enums[name]=[enum_entry(ops,name,label) for label in labels]
    return dict(schemaVersion=1,apkSha256=APK_SHA256,derivedSha256=DERIVED_SHA256,
                appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,
                hg724UsesHg702AutoTuneOverride=True,methods=methods,enums=enums,
                sourceFacts=dict(requestCommand='04:6A',requestPayloads={'false':'000100','true':'000101'},
                    requestAcknowledgement=False,statusCommand='04:6E',statusQueryPayload='',statusQueryAcknowledgement=True,
                    notificationLayout='tag + size + value records; first tag 0 or 1; tag0 values status/percent',
                    sourceLengthIsSignedByte=True,acceptedRecordSizes=[0,127],
                    sendSuccessIsNotFirmwareCompletion=True,stopEffectNotHardwareVerified=True))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk',type=Path,required=True)
    parser.add_argument('--dex',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=trace(args.apk,args.dex)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print('%d method fingerprints; HG702 no-ACK override and enum constants inspected without execution.'%len(report['methods']))


if __name__=='__main__':main()
