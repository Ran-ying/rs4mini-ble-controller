#!/usr/bin/env python3
"""Check module direction and the explicit protocol-completeness gate offline."""
import ast
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
js_root = root / 'node/src'
seen = set()

def visit_js(path):
    path = path.resolve()
    if path in seen:
        return
    seen.add(path)
    assert path.name not in {'controller.js', 'trajectory.js', 'orientation.js', 'experimental.js'}, path
    for target in re.findall(r"(?:from\s+|import\s*)['\"]([^'\"]+)['\"]", path.read_text()):
        if target.startswith('.'):
            visit_js(path.parent / target)

visit_js(js_root / 'device-node.js')
py_root = root / 'python/rs4mini_sdk'
visited = set()

def visit_python(name):
    if name in visited:
        return
    visited.add(name)
    assert name not in {'controller', 'expansion', 'experimental', 'orientation', 'client'}, name
    tree = ast.parse((py_root / (name + '.py')).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level and node.module:
            visit_python(node.module)

visit_python('device')
for name in ['node/src/controller.js', 'node/src/experimental.js',
             'python/rs4mini_sdk/controller.py', 'python/rs4mini_sdk/expansion.py', 'python/rs4mini_sdk/experimental.py']:
    text = (root / name).read_text()
    assert not re.search(r'(?:from\s+[.\w]*protocol\s+import|[\'\"]\./(?:experimental-)?protocol\.js|\._enqueue\(|\.writeAsync\()', text), name
for name in ['RSBleDevice.m', 'RSBleDevice.h', 'RSBleDevice_Internal.h', 'RSDeviceProtocol.h', 'RSControlCore.m']:
    text = (root / 'macos' / name).read_text()
    assert not re.search(r'RSGimbal|RSPositionLoop|RSTrajectoryLoop|RSMotionCore|RSOrientation\(', re.sub(r'//[^\n]*', '', text)), name
text = (root / 'macos/RSGimbal.m').read_text()
assert not re.search(r'RS\w*Frame\(|writeFrame:|writeValue:|RSDecode', text), 'native upper layer bypasses SDK'
manifest = json.loads((root / 'protocol/COMMANDS.json').read_text())
assert manifest['inventoryComplete'] is False
assert manifest['advancedDevelopment']['allowed'] is False
assert len({row['key'] for row in manifest['commands']}) == len(manifest['commands'])
for row in manifest['commands']:
    for source in row['implementation']:
        assert (root / source).is_file(), (row['key'], source)
# An app enum identifies a candidate; it must never silently become target support.
for row in manifest['commands']:
    if row['targetEvidence'] == 'official-app-enum':
        assert row['requestCodec'] in {'unknown', 'not-exposed'} and not row['implementation'], row['key']
    if row['targetEvidence'] == 'app-generic-code':
        assert row['key'] == '04:24' and row['requestCodec'] == 'not-applicable' and row['responseCodec'] == 'candidate-structured'
        assert manifest['userPushSdk']['modelSpecificPathVerified'] is False and manifest['userPushSdk']['targetDeviceVerified'] is False
    if row.get('officialAppEvidence'):
        evidence_path = root / row['officialAppEvidence']
        evidence = json.loads(evidence_path.read_text())
        assert evidence['targetDeviceVerified'] is False
        assert evidence['parameterNamesSafeToInferFromWireIndex'] is False
        for item in evidence['enumEntries']:
            assert item['wireValue'] == (0 <= item['value'] <= 255)
# Offline bytecode-tail hypotheses must not silently become device support.
for row in manifest['commands']:
    if row.get('offlineResearchEvidence'):
        offline = json.loads((root / row['offlineResearchEvidence']).read_text())
        assert offline['targetDeviceVerified'] is False
        assert offline['rs4MiniModelBranchRecovered'] is False
        assert offline['executableImplementationRecovered'] is False
for source in manifest.get('offlineResearchTools', []):
    assert (root / source).is_file(), source
    assert source.startswith('tools/research/'), source
if manifest.get('modelIdentityResearch'):
    model = json.loads((root / manifest['modelIdentityResearch']).read_text())
    assert model['identityLinkedByReadableAppCode'] is True
    assert model['targetDeviceVerified'] is False
    assert model['wireCommandBranchRecovered'] is False
    assert model['parameterResourceSelectionRecovered'] is False
    assert model['parameterNamesSafeToInferFromWireIndex'] is False
if manifest.get('codeRestorationResearch'):
    restored = json.loads((root / manifest['codeRestorationResearch']).read_text())
    assert restored['methodBytesBackedByApk'] is True
    assert restored['selectedStaticCommandPathRecovered'] is True
    assert restored['targetDeviceVerified'] is False
    assert restored['appCodeExecuted'] is False
    assert restored['wholeProtocolRecovered'] is False
    assert restored['parameterNamesSafeToInferFromWireIndex'] is False
if manifest.get('commandMethodAudit'):
    audit = json.loads((root / manifest['commandMethodAudit']).read_text())
    assert audit['appCodeExecuted'] is False and audit['targetDeviceVerified'] is False
    assert audit['inventoryComplete'] is False
    assert audit['classCount'] == len(audit['classes']) == 55
    assert audit['methodCount'] == sum(len(c['methods']) for c in audit['classes']) == 631
    assert audit['derivedSha256'] == restored['derivedSha256']
    for cls in audit['classes']:
        for method in cls['methods']:
            assert re.fullmatch('[0-9a-f]{64}', method['instructionSha256'])
if manifest.get('settingsResearch'):
    settings = json.loads((root / manifest['settingsResearch']).read_text())
    assert settings['derivedSha256'] == restored['derivedSha256']
    assert settings['appCodeExecuted'] is False and settings['targetDeviceVerified'] is False
    assert settings['wholeProtocolRecovered'] is False
    assert settings['parameterNamesSafeToInferFromWireIndex'] is False
    assert {m['method'] for m in settings['methods']} >= {'setMotorEnabled', 'setCustomFollowModeYawEnabled', 'setRonin2CommonUserParam'}
    assert settings['parameters']['CUSTOM_FOLLOW_SETTING']['index'] == 132
    assert settings['parameters']['MOTOR_SPECIAL_CMD']['index'] == 35
if manifest.get('calibrationResearch'):
    calibration = json.loads((root / manifest['calibrationResearch']).read_text())
    assert calibration['derivedSha256'] == restored['derivedSha256']
    assert calibration['appCodeExecuted'] is False and calibration['targetDeviceVerified'] is False
    assert calibration['wholeProtocolRecovered'] is False
    assert calibration['hg724UsesHg702AutoTuneOverride'] is True
    assert calibration['sourceFacts']['requestAcknowledgement'] is False
    assert calibration['sourceFacts']['statusQueryAcknowledgement'] is True
if manifest.get('motorTuningResearch'):
    motor = json.loads((root / manifest['motorTuningResearch']).read_text())
    assert motor['derivedSha256'] == restored['derivedSha256']
    assert motor['appCodeExecuted'] is False and motor['targetDeviceVerified'] is False
    assert motor['wholeProtocolRecovered'] is False and motor['parameterNamesSafeToInferFromWireIndex'] is False
    assert motor['sourceFacts']['namespaceDistinctFromUserParameters'] is True
    assert len(motor['parameters']) == 12 and motor['scalarEncoding']['switchCase'] == 4
if manifest.get('balanceResearch'):
    balance = json.loads((root / manifest['balanceResearch']).read_text())
    assert balance['derivedSha256'] == restored['derivedSha256']
    assert balance['appCodeExecuted'] is False and balance['targetDeviceVerified'] is False
    assert balance['researchToolProvidesSdkInterface'] is False and balance['wholeProtocolRecovered'] is False
    assert [r['maxValue'] for r in balance['matchingResourceRecords']] == [1,255]
    assert balance['sourceFacts']['startValue'] == 64
    assert balance['sourceFacts']['startCommand'] == '04:0F'
if manifest.get('systemCalibrationResearch'):
    system = json.loads((root / manifest['systemCalibrationResearch']).read_text())
    assert system['derivedSha256'] == restored['derivedSha256']
    assert system['appCodeExecuted'] is False and system['targetDeviceVerified'] is False
    assert system['wholeProtocolRecovered'] is False
    assert system['parameter']['name'] == 'system_calc' and system['parameter']['index'] == 36
    assert [r['name'] for r in system['states']] == ['DEFAULT','START','FAIL','SUCCESS']
    assert system['sourceFacts']['horizontalCalibrationIdentityVerified'] is False
    assert system['sourceFacts']['abortCommandVerified'] is False
if manifest.get('codeBankResearch'):
    banks = json.loads((root / manifest['codeBankResearch']).read_text())
    assert banks['appCodeExecuted'] is False and banks['targetDeviceVerified'] is False
    assert banks['wholeProtocolRecovered'] is False and banks['wholeAppRecovered'] is False
    assert len(banks['banks']) == 8 and sum(row['restored'] for row in banks['banks']) == 6
    assert banks['restoredCodeItems'] == sum(row.get('restoredCodeItems',0) for row in banks['banks']) == 49542
    assert banks['banks'][5]['derivedSha256'] == restored['derivedSha256']
    assert [row['segment'] for row in banks['banks'] if not row['restored']] == [1,7]
if manifest.get('controlModeCallerResearch'):
    callers = json.loads((root / manifest['controlModeCallerResearch']).read_text())
    assert callers['appCodeExecuted'] is False and callers['targetDeviceVerified'] is False
    assert callers['wholeProtocolRecovered'] is False and callers['fieldSemanticsFullyAudited'] is False
    assert callers['derivedSha256'] == banks['banks'][3]['derivedSha256']
    assert len(callers['methods']) == 40
if manifest.get('followModeResearch'):
    modes = json.loads((root / manifest['followModeResearch']).read_text())
    assert modes['sdkDerivedSha256'] == restored['derivedSha256']
    assert modes['uiDerivedSha256'] == banks['banks'][3]['derivedSha256']
    assert modes['appCodeExecuted'] is False and modes['targetDeviceVerified'] is False and modes['wholeProtocolRecovered'] is False
    assert len(modes['parameters']) == 6 and len(modes['methods']) == 18
    assert [r['value'] for r in modes['modeEnums']] == [0,1,2,3]
    assert modes['sourceFacts']['axisShifts'] == {'pitch':2,'roll':4,'yaw':6}
    assert modes['sourceFacts']['lowTwoBitsSemanticsVerified'] is False
    assert modes['sourceFacts']['pfPtfFpvPresetsVerified'] is False
if manifest.get('numericParameterResearch'):
    numeric = json.loads((root / manifest['numericParameterResearch']).read_text())
    assert numeric['sdkDerivedSha256'] == restored['derivedSha256']
    assert numeric['uiDerivedSha256'] == banks['banks'][3]['derivedSha256']
    assert numeric['appCodeExecuted'] is False and numeric['targetDeviceVerified'] is False and numeric['wholeProtocolRecovered'] is False
    assert len(numeric['parameters']) == 18 and len(numeric['methods']) == 42
    assert numeric['sourceFacts']['defaultGetterIsCommonUserParams'] is True
    assert numeric['sourceFacts']['researchToolProvidesSdkInterface'] is False
    assert [r['value'] for r in numeric['unsignedTypes']] == [0,1]
    assert numeric['distinctCreatePath']['inputSource']['index'] == 72 and numeric['distinctCreatePath']['inputValue'] == 2
    assert numeric['distinctCreatePath']['sourceCombinesInputAndValueInOneRequest'] is True
if manifest.get('numericParameterSdk',{}).get('implemented'):
    sdk = manifest['numericParameterSdk']
    assert sdk['targetDeviceVerified'] is False and sdk['namedParameterCount'] == 18
    for filename in sdk['files']:assert (root / filename).is_file()
    expected = {(r['domain'],r['parameter'],r['axis']):(r['index'],r['size'],r['minValue'],r['maxValue']) for r in numeric['parameters']}
    def normalize(groups):
        return {(domain,parameter,axis):(indices[i],size,minimum,maximum)
                for domain,rows in groups.items() for parameter,indices,size,minimum,maximum in rows
                for i,axis in enumerate(('pitch','roll','yaw'))}
    tree = ast.parse((root / 'python/rs4mini_sdk/app_tuning.py').read_text())
    py_groups = ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='GROUPS' for t in n.targets)))
    js_text = (root / 'node/src/app-tuning.js').read_text()
    js_literal = re.search(r'const groups=(\{.*?\});',js_text,re.S).group(1)
    js_groups = ast.literal_eval(re.sub(r'\b(follow|rc):',r'"\1":',js_literal))
    native = (root / 'macos/RSControlCore.m').read_text().split('NSArray<NSDictionary *> *RSAppTuningSelection(',1)[1]
    native_literal = re.search(r'NSArray \*groups=(@\{.*?\})\[domain\];',native,re.S).group(1)
    native_groups = json.loads(native_literal.replace('@',''))
    assert normalize(py_groups) == normalize(js_groups) == normalize(native_groups) == expected
if manifest.get('standaloneSdk',{}).get('implemented'):
    standalone = json.loads((root / manifest['standaloneResearch']).read_text())
    sdk = manifest['standaloneSdk']
    assert standalone['apkSha256'] == numeric['apkSha256']
    assert standalone['sdkDerivedSha256'] == numeric['sdkDerivedSha256'] and standalone['uiDerivedSha256'] == numeric['uiDerivedSha256']
    assert standalone['appCodeExecuted'] is False and standalone['targetDeviceVerified'] is False and standalone['wholeProtocolRecovered'] is False
    assert standalone['conditionalAppModelBranchLinked'] is True and len(standalone['modelMethods']) == 6
    assert standalone['parameters'] == numeric['distinctCreatePath']['parameters']
    assert standalone['inputSource'] == numeric['distinctCreatePath']['inputSource']
    facts = standalone['sourceFacts']
    assert (facts['inputSourceIndex'],facts['inputSourceWidth'],facts['inputSourceValue']) == (72,1,2)
    assert facts['sourceAndValueShareOneRequest'] and facts['callerMustChooseInputSourceExplicitly'] and facts['readDoesNotSelectInputSource']
    assert sdk['namedParameterCount'] == 6 and sdk['explicitInputSource'] == 2 and sdk['sourceAndValueShareOneRequest'] is True and sdk['targetDeviceVerified'] is False
    for filename in sdk['files']:assert (root / filename).is_file()
    expected = {}
    for row in standalone['parameters']:
        parameter = 'smoothing' if row['name'].startswith('gimbal_create_smooth_') else 'speed'
        expected[(parameter,row['name'].rsplit('_',1)[1])] = (row['index'],row['size'],row['minValue'],row['maxValue'])
    def standalone_normalize(groups):
        return {(parameter,axis):(indices[i],2,minimum,maximum) for parameter,indices,minimum,maximum in groups for i,axis in enumerate(('pitch','roll','yaw'))}
    tree = ast.parse((root / 'python/rs4mini_sdk/app_standalone.py').read_text())
    py_groups = ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='GROUPS' for t in n.targets)))
    js_groups = ast.literal_eval(re.search(r'const groups=(\[.*?\]);',(root / 'node/src/app-standalone.js').read_text(),re.S).group(1))
    native = (root / 'macos/RSControlCore.m').read_text().split('NSArray<NSDictionary *> *RSAppStandaloneSelection(',1)[1]
    native_groups = json.loads(re.search(r'NSArray \*groups=(@\[.*?\]);',native,re.S).group(1).replace('@',''))
    assert standalone_normalize(py_groups) == standalone_normalize(js_groups) == standalone_normalize(native_groups) == expected
if manifest.get('profilesResearch'):
    profiles = json.loads((root / manifest['profilesResearch']).read_text())
    assert profiles['apkSha256'] == numeric['apkSha256']
    assert profiles['sdkDerivedSha256'] == numeric['sdkDerivedSha256'] and profiles['uiDerivedSha256'] == numeric['uiDerivedSha256']
    assert profiles['appCodeExecuted'] is False and profiles['targetDeviceVerified'] is False and profiles['wholeProtocolRecovered'] is False and profiles['researchToolProvidesSdkInterface'] is False
    assert len(profiles['methods']) == 41
    assert [(r['baseCommand'],r['name'],r['index'],r['size']) for r in profiles['parameters']] == [('USER_PROFILE','table_choice',0,1),('GIMBAL_WORK_MODE','ronin_gimbal_work_mode',62,1)]
    assert profiles['userProfileUiValues'] == [0,1,2] and profiles['userProfileUiNames'] == ['M1','M2','M3']
    assert [r['value'] for r in profiles['movementProfileSourceEnums']] == [0,1,3,4,5,255]
    assert [r['name'] for r in profiles['workModeSourceEnums']] == ['Free','Flower','Fpv','Center']
    assert profiles['presetGetter'] == dict(businessOffset=2,width=1,rawBleOffsetVerified=False)
    assert profiles['sourceFacts']['hg724SelectedModelUsesNewUiList'] and profiles['sourceFacts']['newProfileSelectorRequiresUserProfile2']
    assert profiles['uiModeArrays'][1]['defaultLanguageValues'] == ['FPV','Custom','3D Roll 360']
    assert [(r['baseCommand'],r['index'],r['size'],r['minValue'],r['maxValue']) for r in profiles['modeParameters']]==[('SMOOTH_TRACK_ENABLED_YAW',17,1,0,1),('SMOOTH_TRACK_ENABLED_PITCH',18,1,0,1),('SMOOTH_TRACK_ENABLED_ROLL',19,1,0,1),('FLOWER_SPECIAL_CMD',34,1,0,255)]
    assert profiles['axisModeSourceValues']==dict(ThreeAxis=0,TwoAxis=8,Roll360=16,ThreeDRoll360=24)
    flow=profiles['newModeFlow']
    assert flow['fpvSmoothValues']==[1,1,1] and flow['index2BypassesSmoothSetter'] and flow['uiCustomFlagIsLocalOnly'] and flow['axisModeIsNotMotorControlBit'] and flow['customAxisDisplayLocalOnly']
    for key in ['callbacksChainParameterWrites','atomicTransactionVerified','wireOrderVerified','firmwareRollbackVerified']:assert flow[key] is False

if manifest.get('subscriptionResearch'):
    subscription = json.loads((root / manifest['subscriptionResearch']).read_text())
    assert subscription['apkSha256'] == numeric['apkSha256'] and subscription['derivedSha256'] == restored['derivedSha256']
    assert subscription['appCodeExecuted'] is False and subscription['targetDeviceVerified'] is False and subscription['wholeProtocolRecovered'] is False and subscription['researchToolProvidesSdkInterface'] is False
    assert len(subscription['methods']) == 34
    endpoint = subscription['sourceEndpoint']
    assert (endpoint['receiverTypeValue'],endpoint['receiverId'],endpoint['packedReceiverByte']) == (5,7,229)
    assert endpoint['ackRequested'] is False and endpoint['actualTargetRoutingVerified'] is False
    assert [(r['command'],r['channel']) for r in subscription['selectedChannels']] == [(16,0),(50,0)]
    assert subscription['sourceCancellation']['remoteStopOrLeaseDurationVerified'] is False and subscription['sourceCancellation']['refreshSkipsEmptyMap'] is True
    assert subscription['sourceRefreshSeconds'] == 1 and subscription['sourceTemporaryGetLifetimeMs'] == 3000
    preset = subscription['presetRequestPush']
    assert preset['sourcePayloadOffset'] == 2 and preset['width'] == 1 and preset['sourceFramingEstablished'] is True
    assert preset['requestTypeRequired'] is True and preset['encryptionAllowed'] is False and preset['targetDeviceVerified'] is False and preset['activePresetVerified'] is False
    assert [(r['name'],r['value']) for r in subscription['sourceMovementEnums']] == [(r['name'],r['value']) for r in profiles['movementProfileSourceEnums']]
    assert [r['bodyHex'] for r in subscription['offlineBodyVectors']] == ['100001','320001','24090502','']
if manifest.get('userPushSdk',{}).get('implemented'):
    push = json.loads((root / manifest['userPushResearch']).read_text())
    assert push['apkSha256'] == numeric['apkSha256'] and push['derivedSha256'] == restored['derivedSha256']
    assert push['appCodeExecuted'] is False and push['targetDeviceVerified'] is False and push['wholeProtocolRecovered'] is False
    assert len(push['fields']) == 17 and len(push['methods']) == 20 and push['sourceMinimumBytes'] == 74
    assert push['partialPayloadZeroFillAllowed'] is False and push['requestTypeRequired'] is True and push['encryptionAllowed'] is False
    assert push['sourceFramingEvidence'] == manifest['subscriptionResearch']
    sdk = manifest['userPushSdk']
    assert sdk['fieldCount'] == 17 and sdk['minimumPayloadBytes'] == 74 and sdk['targetDeviceVerified'] is False and sdk['activePresetVerified'] is False
    for filename in sdk['files']:assert (root / filename).is_file()
    expected = [[r['sourceGetter'],r['offset'],r['size']] for r in push['fields']]
    js_fields = json.loads(re.search(r'const fields=(\[.*?\]);',(root / 'node/src/app-user-parameters.js').read_text(),re.S).group(1))
    tree = ast.parse((root / 'python/rs4mini_sdk/app_user_parameters.py').read_text())
    py_fields = ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FIELDS' for t in n.targets)))
    native = (root / 'macos/RSControlCore.m').read_text().split('NSDictionary *RSDecodeAppUserParameterNotification(',1)[1]
    native_fields = json.loads(re.search(r'NSArray \*fields=(@\[.*?\]);',native,re.S).group(1).replace('@',''))
    assert js_fields == [list(r) for r in py_fields] == native_fields == expected
if manifest.get('controlsResearch'):
    controls = json.loads((root / manifest['controlsResearch']).read_text())
    assert controls['apkSha256'] == numeric['apkSha256'] and controls['derivedSha256'] == restored['derivedSha256'] and controls['uiDerivedSha256'] == numeric['uiDerivedSha256']
    assert controls['appCodeExecuted'] is False and controls['targetDeviceVerified'] is False and controls['wholeProtocolRecovered'] is False and controls['researchToolProvidesSdkInterface'] is False
    assert len(controls['methods']) == 68
    assert controls['fineTune']['axisWireValues'] == dict(ROLL=0,PITCH=2,YAW=4) and controls['fineTune']['sourceCallableAxes'] == ['pitch','roll']
    handle = controls['handle']
    assert [r['offset'] for r in handle['fields']] == list(range(8)) and all(r['size']==1 for r in handle['fields'])
    assert [r['sourceBit0Boolean'] for r in handle['fields']] == [False]*5+[True]*3
    assert handle['constructorByteDefaults'] == [255]*8 and handle['afterPackResetFields'] == handle['writeFieldOrder'][:6]
    assert handle['afterPackRetainedFields'] == handle['writeFieldOrder'][6:] and handle['unspecifiedByteFirmwareSemanticsVerified'] is False
    assert [(a['field'],a['offset'],a['sourceSetter']) for a in handle['sourceActions']] == [('dualChannelMode',0,'setDualChannelEnable'),('tiltDirection',1,'setTiltDirection'),('panDirection',2,'setPanDirection')]
    assert all(a['freshObject'] is True for a in handle['sourceActions'])
    assert [a['readTransform'] for a in handle['sourceActions']] == ['enum-array-index-not-find','raw-equals-one-not-bit0','raw-equals-one-not-bit0']
    assert handle['writeFailureFallback'] == dict(api='DJISDKCache.getValue',comparison='reference-identity-after-Class.cast',directBleReadProven=False,writeAcceptanceProven=False)
    assert handle['writeSuccessParsesReadback'] is False
    assert controls['parameterReset']['sourceBodyHex'] == '010001' and controls['parameterReset']['targetResetScopeVerified'] is False
    assert controls['parameterSave']['directCallerScanBanks'] == ['business05','business03'] and controls['parameterSave']['directCallers'] == [] and controls['parameterSave']['targetModelCallPathEstablished'] is False
    assert controls['offlineVectors'] == dict(pitchNegative='f402',rollPositive='0c00',panDirectionPatch='ffff01ffffffffff')
if manifest.get('handleReadSdk',{}).get('implemented'):
    sdk = manifest['handleReadSdk']
    assert sdk['source'] == manifest['controlsResearch'] and sdk['fieldCount'] == 8 and sdk['targetDeviceVerified'] is False and sdk['modelLayoutVerified'] is False
    for filename in sdk['files']:assert (root / filename).is_file()
    expected = [[r['sourceGetter'],r['offset'],r['sourceBit0Boolean']] for r in controls['handle']['fields']]
    js = json.loads(re.search(r'const fields=(\[.*?\]);',(root / 'node/src/app-handle.js').read_text(),re.S).group(1))
    tree = ast.parse((root / 'python/rs4mini_sdk/app_handle.py').read_text())
    py = ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FIELDS' for t in n.targets)))
    native = (root / 'macos/RSControlCore.m').read_text().split('NSDictionary *RSDecodeAppHandleReply(',1)[1]
    literal = re.search(r'NSArray \*fields=(@\[.*?\]);',native,re.S).group(1).replace('@YES','true').replace('@NO','false').replace('@','')
    assert js == [list(r) for r in py] == json.loads(literal) == expected
if manifest.get('fineTuneSdk',{}).get('implemented'):
    sdk=manifest['fineTuneSdk']
    assert sdk['targetDeviceVerified'] is False and sdk['stabilizationStateVerified'] is False and sdk['sourceAdjustmentDegrees']==[-2,2]
    assert sdk['axes']==controls['fineTune']['sourceCallableAxes'] and controls['fineTune']['targetAdjustmentEffectVerified'] is False
    assert controls['fineTune']['pauseGateSource']['targetStateVerified'] is False and controls['fineTune']['callbacksDoNotParseActualAngles'] is True
    for filename in sdk['files']:assert (root/filename).is_file()
    expected={name:controls['fineTune']['axisWireValues'][name.upper()] for name in sdk['axes']}
    js=json.loads(re.search(r'const axes=(\{.*?\});',(root/'node/src/app-fine-tune.js').read_text()).group(1))
    tree=ast.parse((root/'python/rs4mini_sdk/app_fine_tune.py').read_text())
    py=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='AXES' for t in n.targets)))
    native=(root/'macos/RSControlCore.m').read_text().split('NSDictionary *RSAppFineTuneSpec(',1)[1]
    objc=json.loads(re.search(r'NSDictionary \*axes=(@\{.*?\});',native).group(1).replace('@',''))
    assert js==py==objc==expected
if manifest.get('handleWriteSdk',{}).get('implemented'):
    sdk=manifest['handleWriteSdk']
    assert sdk['targetDeviceVerified'] is False and sdk['unspecifiedByteSemanticsVerified'] is False and sdk['readbackVerified'] is False and sdk['persistenceVerified'] is False
    assert sdk['source']==manifest['controlsResearch'] and sdk['allowedValues']==[0,1]
    for filename in sdk['files']:assert (root/filename).is_file()
    expected={a['field']:a['offset'] for a in controls['handle']['sourceActions']}
    js=json.loads(re.search(r'const settings=(\{.*?\});',(root/'node/src/app-handle.js').read_text()).group(1))
    tree=ast.parse((root/'python/rs4mini_sdk/app_handle.py').read_text())
    py=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SETTINGS' for t in n.targets)))
    native=(root/'macos/RSControlCore.m').read_text().split('NSDictionary *RSAppHandleWriteSpec(',1)[1]
    objc=json.loads(re.search(r'NSDictionary \*settings=(@\{.*?\});',native).group(1).replace('@',''))
    assert js==py==objc==expected
if manifest.get('factoryResetSdk',{}).get('implemented'):
    sdk=manifest['factoryResetSdk'];evidence=controls['parameterReset']
    assert sdk['sourcePlatform']=='HG724' and sdk['targetDeviceVerified'] is False and sdk['targetResetScopeVerified'] is False and sdk['persistenceVerified'] is False
    assert evidence['successCallbackForwardsOpaqueObject'] is True and evidence['failureCallbackMapsCcode'] is True and evidence['callbackParsesPhysicalCompletion'] is False
    for filename in sdk['files']:assert (root/filename).is_file()
    expected=list(bytes.fromhex(evidence['sourceBodyHex']))
    js=(root/'node/src/app-protocol.js').read_text().split('export function factoryResetSpec(',1)[1]
    assert json.loads(re.search(r'payload:bytes\((\[.*?\])\)',js).group(1))==expected
    py=(root/'python/rs4mini_sdk/app_protocol.py').read_text().split('def factory_reset_spec(',1)[1]
    assert list(ast.literal_eval(re.search(r'payload=bytes\((\(.*?\))\)',py).group(1)))==expected
    native=(root/'macos/RSControlCore.m').read_text().split('NSData *RSAppFactoryResetFrame(',1)[1]
    assert json.loads('['+re.search(r'uint8_t payload\[\]=\{(.*?)\}',native).group(1)+']')==expected
if manifest.get('saveCallerResearch'):
    save=json.loads((root/manifest['saveCallerResearch']).read_text())
    assert save['apkSha256']==controls['apkSha256'] and save['scannedBanks']==[0,2,3,4,5,6] and save['unrestoredBanks']==[1,7]
    for key in ['appCodeExecuted','targetDeviceVerified','wholeProtocolRecovered','wholeAppRecovered','allScannedBodiesRecovered','indirectReflectionResolved','targetModelCallPathEstablished']:assert save[key] is False
    expected={b['segment']:b['derivedSha256'] for b in banks['banks'] if b.get('restored')}
    tree=ast.parse((root/'tools/research/ronin_save_trace.py').read_text())
    pins=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BANKS' for t in n.targets)))
    assert pins=={b['segment']:b['derivedSha256'] for b in save['banks']}==expected
    assert save['externalDirectCallers']==[] and len(save['methods'])==4
    assert all(b['methodCount']>=b['methodWithCodeCount']>0 and b['instructionCount']>0 for b in save['banks'])
    assert not any(r['kind']=='external-direct-invoke' for m in save['methods'] for r in m['references'])
if manifest.get('axisModeSdk',{}).get('implemented'):
    sdk=manifest['axisModeSdk']
    assert sdk['index']==34 and sdk['size']==1 and sdk['targetDeviceVerified'] is False and sdk['activePresetVerified'] is False and sdk['otherBitsPreservationVerified'] is False
    assert profiles['axisModeSourceRead']==dict(shift=3,mask=3,packedMask=24)
    for filename in sdk['files']:assert (root/filename).is_file()
    expected=profiles['axisModeSourceValues']
    js=json.loads(re.search(r'const modes=(\{.*?\});',(root/'node/src/app-axis-mode.js').read_text()).group(1))
    tree=ast.parse((root/'python/rs4mini_sdk/app_axis_mode.py').read_text())
    py=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MODES' for t in n.targets)))
    native=(root/'macos/RSControlCore.m').read_text().split('NSDictionary *RSAppAxisModeSpec(',1)[1]
    objc=json.loads(re.search(r'NSDictionary \*modes=(@\{.*?\});',native).group(1).replace('@',''))
    assert js==py==objc==expected
if manifest.get('smoothTrackSdk',{}).get('implemented'):
    sdk=manifest['smoothTrackSdk']
    for key in ['targetDeviceVerified','modelLayoutVerified','activePresetVerified','atomicApplicationVerified']:assert sdk[key] is False
    source=profiles['ordinarySmoothTrack'];assert source['readTransform']=='raw-equals-one' and source['sourceOtherValuesBecomeFalse'] is True and source['appWritesViaParameterArrays'] is True and source['perAxisSdkSetterEstablished'] is False
    for filename in sdk['files']:assert (root/filename).is_file()
    expected={r['baseCommand'].rsplit('_',1)[1].lower():r['index'] for r in profiles['modeParameters'] if r['baseCommand'].startswith('SMOOTH_TRACK_ENABLED_')}
    js=json.loads(re.search(r'const axes=(\{.*?\});',(root/'node/src/app-smooth-track.js').read_text()).group(1))
    tree=ast.parse((root/'python/rs4mini_sdk/app_smooth_track.py').read_text())
    py=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='AXES' for t in n.targets)))
    native=(root/'macos/RSControlCore.m').read_text().split('NSArray *RSAppSmoothTrackSelection(',1)[1]
    objc=json.loads(re.search(r'NSDictionary \*axes=(@\{.*?\});',native).group(1).replace('@',''))
    assert js==py==objc==expected==dict(yaw=17,pitch=18,roll=19)
if manifest.get('profileValueSdk',{}).get('implemented'):
    sdk=manifest['profileValueSdk']
    for key in ['targetDeviceVerified','modelLayoutVerified','activePresetVerified','persistenceVerified']:assert sdk[key] is False
    source=profiles['profileValueSourceRead'];assert source['userProfileRawInteger'] and source['workModeMatchesEnumValue'] and source['unknownWorkModeFallbackVerified'] is False and source['activePresetMappingVerified'] is False
    for filename in sdk['files']:assert (root/filename).is_file()
    kinds={'USER_PROFILE':'userProfile','GIMBAL_WORK_MODE':'workMode'}
    expected={kinds[r['baseCommand']]:dict(index=r['index'],size=r['size'],min=r['minValue'],max=r['maxValue']) for r in profiles['parameters']}
    js=(root/'node/src/app-profile-values.js').read_text()
    assert json.loads(re.search(r'const parameters=(\{.*?\});',js).group(1))==expected
    tree=ast.parse((root/'python/rs4mini_sdk/app_profile_values.py').read_text())
    py={t.id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) for t in n.targets if isinstance(t,ast.Name)}
    native=(root/'macos/RSControlCore.m').read_text().split('static NSDictionary *ProfileValueCatalog(void)',1)[1]
    objc=json.loads(re.search(r'NSDictionary \*catalog=(@\{.*?\});',native).group(1).replace('@',''))
    assert py['PARAMETERS']==objc==expected
    modes={r['name']:r['value'] for r in profiles['workModeSourceEnums']}
    objc_modes=(root/'macos/RSControlCore.m').read_text().split('NSDictionary *RSAppProfileValueSpec(',1)[1]
    assert json.loads(re.search(r'const workModes=(\{.*?\});',js).group(1))==py['WORK_MODES']==json.loads(re.search(r'NSDictionary \*modes=(@\{.*?\});',objc_modes).group(1).replace('@',''))==modes
if manifest.get('commandReferenceResearch'):
    refs=json.loads((root/manifest['commandReferenceResearch']).read_text())
    assert refs['apkSha256']==controls['apkSha256'] and refs['gimbalCommandSet']==4
    for key in ['appCodeExecuted','targetDeviceVerified','wholeProtocolRecovered','wholeAppRecovered','allScannedBodiesRecovered','indirectDispatchResolved','literalResolutionComplete','literalCandidatesProveSend','researchToolProvidesSdkInterface']:assert refs[key] is False
    assert refs['scannedBanks']==[0,2,3,4,5,6] and refs['unrestoredBanks']==[1,7]
    assert {b['segment']:b['derivedSha256'] for b in refs['banks']}=={b['segment']:b['derivedSha256'] for b in banks['banks'] if b.get('restored')}
    original=json.loads((root/'protocol/research/ronin-2.2.2-evidence.json').read_text())
    assert {(c['name'],c['ordinal'],c['commandId']) for c in refs['commands']}=={(c['name'],c['ordinal'],c['value']) for c in original['enumEntries'] if c['scope']=='non-camera-candidate'}
    assert len(refs['commands'])==40 and len({c['commandId'] for c in refs['commands']})==39 and len(refs['methods'])==50
    for c in refs['commands']:
        assert all(0<=i<len(refs['methods']) and any(x['name']==c['name'] and x['kind']=='external-enum-reference' for x in refs['methods'][i]['enumReferences']) for i in c['externalReferenceMethodIndexes'])
    onoff=refs['onOff'];assert onoff['commandId']==13 and onoff['enumOrdinal']==5 and onoff['hasExplicitClassArgument'] is False
    for key in ['hypothesizedClassDefinitionBanks','externalEnumMethodIndexes','literalCandidateMethodIndexes']:assert onoff[key]==[]
    assert onoff['payloadRecovered'] is False and onoff['hg724CallPathEstablished'] is False
print('Layer boundaries passed: device modules do not depend on motion; upper layers do not encode/write packets.')
print('Protocol inventory: %d entries; inventoryComplete=false; further advanced development is gated.' % len(manifest['commands']))

if manifest.get('angleResearch'):
    angles=json.loads((root/manifest['angleResearch']).read_text())
    assert angles['appCodeExecuted'] is False and angles['targetDeviceVerified'] is False
    assert angles['wholeProtocolRecovered'] is False and angles['researchToolProvidesSdkInterface'] is False
    assert angles['angle14']['sourceReportsSuccessWithoutWaitingForAck'] is True
    assert angles['angle14']['capabilityInitializationAudited'] is False
    assert angles['angle0a']['hg724CallPathEstablished'] is False
    assert angles['angle0a']['negativeSearchProvesUnsupported'] is False
    assert len(angles['methods']) == 48
    assert not any('angles_trace' in (root/p).read_text() for p in ('node/src/device.js','python/rs4mini_sdk/device.py','macos/RSBleDevice.m'))

if manifest.get('angleContextResearch'):
    context=json.loads((root/manifest['angleContextResearch']).read_text())
    assert context['appCodeExecuted'] is False and context['targetDeviceVerified'] is False
    assert context['wholeProtocolRecovered'] is False and context['researchToolProvidesSdkInterface'] is False
    assert context['sourcePolicyIsMechanicalSafeRange'] is False
    assert context['routing']['bleAddressVerified'] is False
    assert context['pause']['sourceCommandValues'] == {'AppState':98,'Stabilization':96}
    assert context['pause']['sourceReceiverTypeValue'] == 17
    assert context['pause']['requiredForDirectBleVerified'] is False and context['pause']['resumeProtocolVerified'] is False
    assert context['pause']['cameraControlAdded'] is False
    assert len(context['methods']) == 29

if manifest.get('stabilizationDependencyResearch'):
    stabilization=json.loads((root/manifest['stabilizationDependencyResearch']).read_text())
    assert stabilization['appCodeExecuted'] is False and stabilization['targetDeviceVerified'] is False
    assert stabilization['wholeProtocolRecovered'] is False and stabilization['researchToolProvidesSdkInterface'] is False
    assert stabilization['sourceBusinessByte']['rawBleOffsetVerified'] is False
    assert stabilization['sourceBusinessByte']['disabledReturnsPaused'] is True
    assert stabilization['sourceEvent']['angleCompletionVerified'] is False
    assert stabilization['waitFlow']['sourceWaitUsesAngleAck'] is False
    assert stabilization['sourceInterruption']['selectedAwaitExceptionTableAudited'] is True
    assert len(stabilization['methods']) == 16 and len(stabilization['callSites']) == 6

if manifest.get('resetRouteResearch'):
    reset_routes=json.loads((root/manifest['resetRouteResearch']).read_text())
    assert reset_routes['appCodeExecuted'] is False and reset_routes['targetDeviceVerified'] is False
    assert reset_routes['wholeProtocolRecovered'] is False and reset_routes['researchToolProvidesSdkInterface'] is False
    assert reset_routes['genericResetBranches']['livePlatformVerified'] is False
    assert reset_routes['factory']['liveProductVerified'] is False
    assert reset_routes['gimbalBody']['defaultModeResetTrueHex'] == 'fe01'
    assert reset_routes['targetClaims']['specialControlTargetSupportVerified'] is False
    assert reset_routes['targetClaims']['recenterImplementationChanged'] is False
    assert len(reset_routes['directUiRecenterPaths']) == 3
    assert len(reset_routes['methods']) == 27 and len(reset_routes['externalResetClassCallers']) == 8
