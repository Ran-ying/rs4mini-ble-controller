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
center_sdk = manifest.get('centerInfoSdk',{}).get('implemented',False)
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
        if row['key']=='04:69':
            assert row['requestCodec']=='not-applicable' and row['responseCodec']=='candidate-structured' and manifest['externalDeviceSdk']['passiveOnly'] is True
            assert row['externalDeviceResearch']==manifest['externalDeviceResearch']
        else:
            assert row['key'] in {'04:24','04:57','04:27','04:33','04:38','04:64','04:6B','04:66','04:30','04:2B'} and row['requestCodec'] == ('implemented' if row['key']=='04:6B' else 'not-applicable') and row['responseCodec'] == 'candidate-structured'
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
if manifest.get('savePrefixCallerResearch'):
    save=json.loads((root/manifest['savePrefixCallerResearch']).read_text())
    assert save['apkSha256']==controls['apkSha256'] and save['scannedBanks']==list(range(8)) and len(save['bankSha256'])==8
    for key in ['appCodeExecuted','liveUiExecuted','targetDeviceVerified','wholeProtocolRecovered','wholeAppRecovered','allScannedBodiesRecovered','indirectReflectionResolved','targetModelCallPathEstablished','hg724BusinessEntryEstablished','persistencePathEstablished','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded','saveSettingsOpened','parameterWriteEquatedToPersistence']:
        assert save[key] is False
    tree=ast.parse((root/'tools/research/ronin_prefix_restore.py').read_text())
    pins=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PREFIX_BANKS' for t in n.targets)))
    assert {int(k):v for k,v in save['bankSha256'].items()}==pins=={b['segment']:b['derivedSha256'] for b in save['banks']}
    assert save['externalDirectCallers']==[] and save['externalAllocations']==[] and save['newBanks01And07ReferenceMethods']==[]
    assert len(save['methods'])==4 and all(m['segment']==5 for m in save['methods'])
    assert save['enumRegistration']['wireCommandId']==17 and save['sourceDoPack']['emptyBody'] is True
    assert save['sourceStartPack']['allMentionsPresent'] is True and save['sourceStartPack']['finalTransportEncryptionVerified'] is False
    row=next(row for row in manifest['commands'] if row['key']=='04:11')
    assert row['savePrefixCallerResearch']==manifest['savePrefixCallerResearch'] and row['requestCodec']=='unknown' and not row['implementation']
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
if manifest.get('inventoryPrefixResearch'):
    inv=json.loads((root/manifest['inventoryPrefixResearch']).read_text())
    assert inv['apkSha256']==controls['apkSha256'] and inv['scannedBanks']==list(range(8))
    assert inv['allNonExcludedGimbalEnumsPresentInCommandsJson'] is True
    assert inv['newlyDiscoveredGimbalWireCommands']==[]
    assert inv['inventoryCompleteRemainsFalse'] is True and inv['inventoryCompleteClaimed'] is False
    assert inv['activationOrBindingWriteOpened'] is False and inv['sessionVersionNegotiated'] is False
    assert manifest['inventoryComplete'] is False
    row=next(row for row in manifest['commands'] if row['key']=='unknown:device-management')
    assert row['inventoryPrefixResearch']==manifest['inventoryPrefixResearch']
if manifest.get('programPrefixResearch'):
    prog=json.loads((root/manifest['programPrefixResearch']).read_text())
    assert prog['apkSha256']==controls['apkSha256'] and prog['scannedBanks']==list(range(8))
    assert prog['pureGimbalProgramPrimitiveOpenable'] is False and prog['programExecutionOpened'] is False
    assert prog['cameraFieldsInterleavedWithPanorama'] is True and 'mExposure' in prog['panoramaDoPackFields']
    assert prog['hg724NamedProgramCallers']==[] and prog['newBanks01And07External']==[]
    assert [len(prog['commands'][k]['externalDirectCallers']) for k in ['25','37','62','63']]==[12,3,12,4]
    for key in ['04:25','04:37','04:62','04:63']:
        row=next(row for row in manifest['commands'] if row['key']==key)
        assert row['programPrefixResearch']==manifest['programPrefixResearch'] and not row['implementation']
if manifest.get('motionPrefixResearch'):
    motion=json.loads((root/manifest['motionPrefixResearch']).read_text())
    assert motion['apkSha256']==controls['apkSha256'] and motion['scannedBanks']==list(range(8))
    for flag in ['appCodeExecuted','liveUiExecuted','targetDeviceVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded']:
        assert motion[flag] is False
    assert motion['command0C']['sourceDoPack']['axisOrder']==['yaw','roll','pitch'] and motion['command0C']['sendOpened'] is False
    assert motion['command0C']['replacesExistingVelocity04_01'] is False
    assert motion['command14']['onlyBaseRotateCaller'] is True and motion['command14']['sendOpened'] is False
    assert motion['command4C']['perAxisResetEvidenceFound'] is False and len(motion['command4C']['externalDirectCallers'])==8
    assert motion['hg724OverridesOfRotateOrReset']==[] and motion['perAxisResetStringHits']==[]
    for key in ['04:0C','04:14','04:4C']:
        row=next(row for row in manifest['commands'] if row['key']==key)
        assert row['motionPrefixResearch']==manifest['motionPrefixResearch']
if manifest.get('gapPrefixResearch'):
    gap=json.loads((root/manifest['gapPrefixResearch']).read_text())
    assert gap['apkSha256']==controls['apkSha256'] and gap['scannedBanks']==list(range(8)) and len(gap['bankSha256'])==8
    for flag in ['appCodeExecuted','liveUiExecuted','targetDeviceVerified','wholeProtocolRecovered','wholeAppRecovered','allScannedBodiesRecovered','indirectReflectionResolved','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded']:
        assert gap[flag] is False
    assert gap['command0D']['hypothesizedClassDefined'] is False and gap['command0D']['enumRegistration']['wireCommandId']==13
    assert gap['command0D']['enumOutsideReferences']==[] and gap['command0D']['sendOpened'] is False
    assert gap['command2C']['externalDirectCallers']==[] and gap['command2C']['sendOpened'] is False
    assert gap['command0A']['onlyDt501UvcExternalCallersInScan'] is True and len(gap['command0A']['externalDirectCallers'])==2
    assert gap['command0A']['sendOpened'] is False and gap['newBanks01And07']['externalDirectCallers']==[]
    for key in ['04:0D','04:2C','04:0A']:
        row=next(row for row in manifest['commands'] if row['key']==key)
        assert row['gapPrefixResearch']==manifest['gapPrefixResearch'] and row['requestCodec']=='unknown' and not row['implementation']
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

if manifest.get('stickResearch'):
    stick=json.loads((root/manifest['stickResearch']).read_text())
    assert stick['appCodeExecuted'] is False and stick['targetDeviceVerified'] is False
    assert stick['wholeProtocolRecovered'] is False and stick['targetLayoutVerified'] is False
    assert stick['sourceSend']['sendEnabledInSdk'] is False
    assert stick['minimumBodyBytes'] == 6 and stick['signedLittleEndian'] is True
    assert len(stick['methods']) == 23 and len(stick['externalCallers']) == 2
    assert manifest['handheldStickSdk']['sendEnabled'] is False
    for key in ('targetDeviceVerified','modelLayoutVerified','axisMappingVerified'):assert manifest['handheldStickSdk'][key] is False
    for path in manifest['handheldStickSdk']['files']:assert (root/path).is_file()

if manifest.get('sourceStatusResearch'):
    source_status=json.loads((root/manifest['sourceStatusResearch']).read_text())
    assert source_status['appCodeExecuted'] is False and source_status['targetDeviceVerified'] is False
    assert source_status['wholeProtocolRecovered'] is False and source_status['targetLayoutVerified'] is False
    assert source_status['sourceComposite']['includesYaw'] is False and source_status['batterySourceDoesNotClamp'] is True
    assert len(source_status['abnormalFields']) == 21 and len(source_status['methods']) == 36
    assert manifest['sourceStatusSdk']['automaticControlEnabled'] is False
    for key in ('targetDeviceVerified','modelLayoutVerified'):assert manifest['sourceStatusSdk'][key] is False
    for path in manifest['sourceStatusSdk']['files']:assert (root/path).is_file()
    expected_fields=[[f['sourceGetter'],f['offset'],f['shift'],f['mask'],f['boolean']] for f in source_status['abnormalFields']]
    js_catalog=re.search(r'const fields=(.*);', (root/'node/src/app-source-status.js').read_text()).group(1)
    assert json.loads(js_catalog) == expected_fields
    py_catalog=ast.literal_eval(re.search(r'FIELDS=(.*)', (root/'python/rs4mini_sdk/app_source_status.py').read_text()).group(1))
    assert [list(row) for row in py_catalog] == expected_fields

    native_status=(root/'macos/RSControlCore.m').read_text().split('NSDictionary *RSDecodeAppSourceStatusNotification(',1)[1]
    native_fields=re.findall(r'@\[@"([^"\n]+)",@(\d+),@(\d+),@(\d+),@(YES|NO)\]',native_status)
    assert [[name,int(offset),int(shift),int(mask),boolean=='YES'] for name,offset,shift,mask,boolean in native_fields] == expected_fields

if manifest.get('tutorialResearch'):
    tutorial=json.loads((root/manifest['tutorialResearch']).read_text())
    assert tutorial['appCodeExecuted'] is False and tutorial['targetDeviceVerified'] is False
    assert tutorial['wholeProtocolRecovered'] is False and tutorial['researchToolProvidesSdkInterface'] is False
    assert tutorial['unknownStepIsCompletionVerified'] is False
    assert tutorial['sourceUnknownEnumFallback'] == 'STEP_FINISH'
    assert tutorial['sourceFinishAndStartSelectBits'] == [30,31]
    assert tutorial['sourceSend']['sendEnabledInSdk'] is False
    assert len(tutorial['methods']) == 28 and tutorial['externalCallers'] == []

if manifest.get('keySupportResearch'):
    keys=json.loads((root/manifest['keySupportResearch']).read_text())
    assert keys['appCodeExecuted'] is False and keys['javaReflectionExecuted'] is False
    assert keys['targetDeviceVerified'] is False and keys['wholeProtocolRecovered'] is False
    assert keys['researchToolProvidesSdkInterface'] is False
    assert len(keys['declaredFields']) == 223 and len(keys['methods']) == 12
    assert sum(k['sourceSupport'] for k in keys['declaredFields']) == 200
    assert sum(k['sourceSupport'] and not k['selectionUnambiguous'] for k in keys['declaredFields']) == 7
    assert keys['sourceRules']['mostSpecificClassPriorityVerified'] is False
    assert keys['abstractionGroupReferences'] == []
    assert {a['action'] for a in keys['selectedActionAnnotations']} == {'Rotate','ResetGimbal'}

if manifest.get('registrationResearch'):
    registration=json.loads((root/manifest['registrationResearch']).read_text())
    for flag in ('appCodeExecuted','javaReflectionExecuted','targetDeviceVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','runtimeMethodMapOrderVerified','actualHg724InstantiationVerified','fullRegistryVerified'):
        assert registration[flag] is False
    assert registration['annotatedCatalogFieldCount']==226 and len(registration['methods'])==19
    assert {f['fieldName'] for f in registration['inheritedFields']}=={'CONNECTION','FIRMWARE_VERSION','SERIAL_NUMBER'}
    assert registration['catalogLiteralCollisions']=={}
    assert len(registration['selectedActionDeclarations'])==2
    assert {a['action'] for a in registration['selectedActionDeclarations']}=={'Rotate','ResetGimbal'}
    assert all(a['nearestTargetDeclaration']['className']==a['declaringClass'] for a in registration['selectedActionDeclarations'])

if manifest.get('programResearch'):
    programs=json.loads((root/manifest['programResearch']).read_text())
    for flag in ('appCodeExecuted','targetDeviceVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','targetModelCallPathEstablished','rawBleOffsetsVerified'):
        assert programs[flag] is False
    assert len(programs['methods'])==106 and len(programs['externalDirectCallers'])==60
    assert programs['track']['pointLimit']==10 and programs['track']['stopBodyBytes']==1
    assert programs['delay']['pointLimit']==6 and programs['roninTimelapse']['pointLimit']==5
    assert programs['roninTimelapse']['totalDurationOverwritesFirstPointDurationAtOffset']==2
    assert programs['standaloneStatus']['sourceIsChangedSendsAck'] is True
    assert programs['standaloneStatus']['automaticAckImplementedInSdk'] is False
    assert programs['externalStatus']['requestTypes']=={'StartContinuePush':0,'StopContinuePush':1,'RequestSinglePush':2}
    assert programs['externalStatus']['sourceFirstByteSuccessValues']==[0,1]
    assert programs['externalStatus']['timelapseStatusMask']==7

if manifest.get('programEntryResearch'):
    entry=json.loads((root/manifest['programEntryResearch']).read_text())
    for flag in ('appCodeExecuted','targetDeviceVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','liveUiExecuted','fullModelWorkflowVerified','fullShutterGateReachabilityVerified'):
        assert entry[flag] is False
    assert len(entry['methods'])==22 and len(entry['layouts'])==4
    assert entry['hg724PlatformSwitchCase']==9 and entry['hg724HandleBranch']['value']==1
    assert entry['helpRouteIsShutterCableNotProgram'] is True
    assert entry['selectedClickDirectlyCallsShutterHelper'] is False
    assert entry['componentArgumentIgnoredByHandheldHelper'] is True

if manifest.get('trackWorkflowResearch'):
    workflow=json.loads((root/manifest['trackWorkflowResearch']).read_text())
    for flag in ('appCodeExecuted','liveUiExecuted','targetDeviceVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','fullModelWorkflowVerified','androidInflationExecuted'):
        assert workflow[flag] is False
    assert len(workflow['methods'])==29 and len(workflow['layouts'])==2
    assert workflow['staticSelectedMountChainEstablished'] is True
    track=workflow['track']
    assert track['watchdogMs']==3000 and track['sourceTimedUiUnlockMs']==1200
    for flag in ('uiStateIsPhysicalCompletionVerified','subscriptionStopIsProgramStop','statusHandlerDirectlyChecksCommandId','statusHandlerDirectlyChecksSuccess','statusHandlerDirectlyChecksSequence','completeCameraIsolationVerified'):
        assert track[flag] is False

if manifest.get('programReceiveResearch'):
    receive=json.loads((root/manifest['programReceiveResearch']).read_text())
    for flag in ('appCodeExecuted','targetDeviceVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','javaReflectionExecuted','actualCmdSetExtensionSelectionVerified'):
        assert receive[flag] is False
    assert len(receive['methods'])==37 and len(receive['baseProgramPolicies'])==7
    assert receive['payloadMapping']['ackBusinessOffsetInRawPayload']==1
    assert receive['payloadMapping']['requestBusinessOffsetInRawPayload']==0
    assert receive['mixed6B']['processorAndPushPathsEligible'] is True
    assert receive['eventOrder']['baseMayPostBeforeDerivedFieldsParsed'] is True
    assert receive['extensionLookup']['namespaceMatchesInSixRestoredBanks']==[]
    assert receive['extensionLookup']['dynamicExtensionAbsenceProven'] is False

if manifest.get('programStatusSdk'):
    program=manifest['programStatusSdk']
    assert program['passiveOnly'] and program['requestEnvelopesOnly']
    for flag in ('automaticQuerySubscriptionAckSendEnabled','modelSpecificPathVerified','targetDeviceVerified','programCorrelationVerified','physicalCompletionVerified','sharedSourceStateRetained'):
        assert program[flag] is False
    assert program['sourceSignedLengthHighBitRejected'] is True
    assert program['commandIds']==[56,100,107]
    assert len(json.loads((root/program['fixtures']).read_text()))==5

# Generic-program sends are explicit fixed status requests, never execution.
request = manifest['programStatusRequestSdk']
assert request['profile']=='ronin-2.2.2'
assert request['sourceRequestType']==2 and request['sourceRequestTypeName']=='RequestSinglePush'
assert request['allowedProgramCommands']==[98,55,99]
assert request['singleRequestSendEnabled'] is True and request['ackBodyOpaque'] is True
assert request['continuousSubscriptionSendEnabled'] is True
for flag in ('programExecutionSendEnabled','freshStatusVerified','programCorrelationVerified','modelSpecificPathVerified','targetDeviceVerified','physicalCompletionVerified'):
    assert request[flag] is False
for source in request['files']:
    assert (root/source).is_file()

subscription = manifest['programStatusSubscriptionSdk']
assert subscription['profile']=='ronin-2.2.2'
assert subscription['sourceRequestTypes']=={'StartContinuePush':0,'StopContinuePush':1}
assert subscription['allowedProgramCommands']==[98,55,99]
assert subscription['explicitBooleanEnabledRequired'] is True and subscription['ackBodyOpaque'] is True
for flag in ('automaticRefreshEnabled','automaticStopEnabled','replayAfterDisconnectEnabled','programExecutionSendEnabled','remoteSubscriptionStateVerified','notificationStreamVerified','targetDeviceVerified','modelSpecificPathVerified','physicalCompletionVerified'):
    assert subscription[flag] is False
vectors = json.loads((root/subscription['fixtures']).read_text())
assert len(vectors)==6
assert {(v['program'],v['enabled']) for v in vectors} == {(p,e) for p in ('track','timelapse','panorama') for e in (True,False)}
for source in subscription['files']:
    assert (root/source).is_file()

if manifest.get('trackPointResearch'):
    points=json.loads((root/manifest['trackPointResearch']).read_text())
    assert len(points['methods'])==51
    for flag in ('appCodeExecuted','liveUiExecuted','targetDeviceVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','sdkProgramSendAdded'):
        assert points[flag] is False
    assert points['time']['moveSecondsAtProgress']=={'p1':1,'p60':60,'p61':120,'p159':6000}
    assert points['point']['previewArgumentViews']==[['moveTime','stopTime','yaw','pitch',0]]
    assert points['point']['sendToDeviceStartArgumentViews']==[['moveTime','stopTime','yaw','pitch',0],[0,'stopTime','yaw','pitch',0],['moveTime','stopTime','yaw','pitch',0]]
    assert points['point']['existingJointAnglesEquivalentVerified'] is False
    assert points['point']['physicalReferenceFrameVerified'] is False
    assert {n:r['wireId'] for n,r in points['peripheral']['selectedTypes'].items()}=={'PActualPose':34,'RActualPose':35,'YActualPose':36,'PMotorAngle':16,'RMotorAngle':17,'YMotorAngle':18}
    assert points['peripheral']['rawBleOffsetsVerified'] is False
    assert points['preview']['completeCameraIsolationVerified'] is False
    assert points['preview']['physicalStopVerified'] is False

if manifest.get('peripheralSdk'):
    import ast
    sdk=manifest['peripheralSdk'];proof=json.loads((root/manifest['peripheralResearch']).read_text())
    assert len(proof['methods'])==70 and len(proof['catalog']['types'])==46 and len(proof['catalog']['getters'])==43
    assert proof['sourceTagCollisions']==[{'sourceId':21,'sourceTypes':['YGyroOut','PAcceOut']}]
    assert proof['basePolicy']['isBlock'] is False and proof['basePolicy']['isMix'] is False
    assert proof['envelope']['requestBusinessOffsetInRawPayload']==0
    assert proof['envelope']['actualExtensionSelectionVerified'] is False
    for flag in ('appCodeExecuted','targetDeviceVerified','modelLayoutVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface'):
        assert proof[flag] is False
    assert sdk['passiveOnly'] and sdk['sourceTypeCount']==46 and sdk['sourceGetterViewCount']==43
    assert sdk['ambiguousSourceIds']==[21] and sdk['emptyPresentRecordUsesSourceZero'] is True
    for flag in ('sourceCollisionRepaired','sourceGpsDivisionCorrected','missingFieldsSynthesized','automaticSubscriptionAckOrControlEnabled','targetDeviceVerified','modelLayoutVerified','referenceFrameVerified'):
        assert sdk[flag] is False
    js=(root/'node/src/app-peripheral.js').read_text().split('const catalog = ',1)[1].split(';\n',1)[0]
    py=(root/'python/rs4mini_sdk/app_peripheral.py').read_text().split('CATALOG = ',1)[1].split('\n',1)[0]
    native=(root/'macos/RSControlCore.m').read_text().split('static NSDictionary *AppPeripheralCatalog(void)',1)[1].split('JSONObjectWithData:[@',1)[1].split(' dataUsingEncoding:',1)[0]
    assert json.loads(js)==proof['catalog'] and ast.literal_eval(py)==proof['catalog'] and json.loads(json.loads(native))==proof['catalog']
    assert len(json.loads((root/sdk['fixtures']).read_text()))==6

if manifest.get('subscriptionCatalogResearch'):
    catalog=json.loads((root/manifest['subscriptionCatalogResearch']).read_text())
    assert len(catalog['methods'])==24 and len(catalog['registrations'])==152
    assert len({r['key'] for r in catalog['registrations']})==152
    assert catalog['baseCommandCount']==81 and catalog['dbPresentUniqueCommandChannelPairs']==121
    assert len(catalog['aliasGroups'])==17
    assert catalog['metadata']['resourceConditionalKeyCount']==21
    assert catalog['metadata']['resourceConditionalBaseCommandCount']==15
    assert catalog['metadata']['missingReadLeavesJavaDefaultChannel']==0
    assert catalog['metadata']['resourceRuntimeLoadedBeforeEnumInitializationVerified'] is False
    assert catalog['supportPredicate']['conditionalKeys']==['FollowModeSensitivity','GimbalControlState']
    assert catalog['supportPredicate']['hg724UsesDefault'] is True
    assert catalog['supportPredicate']['defaultResult'] is True
    assert catalog['supportPredicate']['runtimeComponentCacheVerified'] is False
    assert catalog['endpoint']['receiverByte']==229 and catalog['endpoint']['ackRequested'] is False
    assert catalog['endpoint']['remoteStopOrLeaseVerified'] is False
    for flag in ('appCodeExecuted','targetDeviceVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','runtimeRegistrationMapConstructed'):
        assert catalog[flag] is False

if manifest.get('parameterSubscriptionSdk'):
    sdk=manifest['parameterSubscriptionSdk'];proof=json.loads((root/manifest['subscriptionCatalogResearch']).read_text())
    projection=[{k:r[k] for k in ('key','commandId','channel','channelSource','sourceCondition')} for r in proof['registrations']]
    js=(root/'node/src/app-parameter-subscription.js').read_text().split('const catalog = ',1)[1].split(';\n',1)[0]
    py=(root/'python/rs4mini_sdk/app_parameter_subscription.py').read_text().split('CATALOG = ',1)[1].split('\n',1)[0]
    native=(root/'macos/RSControlCore.m').read_text().split('static NSArray *AppParameterSubscriptionCatalog(void)',1)[1].split('JSONObjectWithData:[@',1)[1].split(' dataUsingEncoding:',1)[0]
    assert json.loads(js)==projection and ast.literal_eval(py)==projection and json.loads(json.loads(native))==projection
    assert sdk['keyCount']==152 and sdk['receiverByte']==229 and sdk['oneShotOnly'] is True
    for flag in ('automaticRefresh','emptySelectionMeansStop','targetRoutingVerified','notificationStreamVerified','remoteSubscriptionStateVerified','targetDeviceVerified'):
        assert sdk[flag] is False
    init=json.loads((root/manifest['subscriptionInitResearch']).read_text())
    assert init['runtimeInitializationOrderObserved'] is False and init['targetDeviceVerified'] is False
    assert len(init['methods'])==13 and len(init['directCapturedIdWriters'])==3

if manifest.get('externalDeviceResearch'):
    proof=json.loads((root/manifest['externalDeviceResearch']).read_text())
    assert len(proof['methods'])==36 and len(proof['directCallers'])==1
    assert proof['typedMethodDeclarations']==[]
    assert proof['basePolicy']['commandId']==105 and proof['basePolicy']['isBlock'] is False and proof['basePolicy']['isMix'] is True
    assert {r['name']:r['sourceId'] for r in proof['sourceSpeedControlTypes']}=={'CommonStick':1,'RockWheel':2,'Sensor':3,'Other':7}
    assert proof['request']['ackRequested'] is False and proof['request']['doPackAssignsBody'] is False
    assert proof['request']['emptyBodyInActualTransportVerified'] is False
    assert proof['receive']['sourceResetClearsControlType'] is False
    assert proof['receive']['sourceRetainsPreviousFieldsWhenMissing'] is True
    for flag in ('appCodeExecuted','liveUiExecuted','targetDeviceVerified','modelLayoutVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded'):
        assert proof[flag] is False

if manifest.get('externalDeviceSdk'):
    sdk=manifest['externalDeviceSdk'];proof=json.loads((root/manifest['externalDeviceResearch']).read_text())
    types={r['sourceId']:r['name'] for r in proof['sourceSpeedControlTypes']}
    js=(root/'node/src/app-external-device.js').read_text().split('const controlTypes=new Map(',1)[1].split(');',1)[0]
    py=(root/'python/rs4mini_sdk/app_external_device.py').read_text().split('CONTROL_TYPES=',1)[1].split('\n',1)[0]
    native=(root/'macos/RSControlCore.m').read_text().split('NSDictionary *RSDecodeAppExternalDeviceNotification(',1)[1].split('NSDictionary *types=@',1)[1].split(';',1)[0]
    assert dict(ast.literal_eval(js))==types and ast.literal_eval(py)==types
    assert {int(k):v for k,v in re.findall(r'@(\d+):@"(\w+)"',native)}==types
    assert sdk['recordOffset']==0 and sdk['speedControlTag']==2 and sdk['sourceOtherControlType']==7 and sdk['passiveOnly'] is True
    for flag in ('missingFieldsSynthesized','sourceSingletonRetentionEmulated','automaticQuerySubscriptionAckOrControlEnabled','cameraFieldsDecoded','targetDeviceVerified','modelLayoutVerified','unitVerified','referenceFrameVerified'):
        assert sdk[flag] is False
    assert len(json.loads((root/sdk['fixtures']).read_text()))==7

if manifest.get('sensorCalibrationResearch'):
    proof=json.loads((root/manifest['sensorCalibrationResearch']).read_text())
    assert len(proof['methods'])==48 and len(proof['directCallers'])==17 and len(proof['externalEnumReferences'])==9
    assert len(proof['typedMethodDeclarations'])==9
    assert [r['commandId'] for r in proof['basePolicies']]==[8,48]
    assert proof['basePolicies'][1]['modelClass']=='Ldji/midware/data/model/P3/DataGimbalGetPushSensorCalibrateStatus;'
    assert {r['name']:r['sourceId'] for r in proof['sensorStates']}=={'COMPLETE':0,'PROCESSING':1,'FAIL':3,'OTHER':9}
    assert {r['name']:r['sourceId'] for r in proof['responseStates']}=={'FAIL':0,'SUCCESS':1,'PROCESSING':2}
    facts=proof['sourceFacts']
    assert facts['pushStartIsInert'] is True and facts['unboundClassAssignedTo30InBaseTable'] is False
    assert facts['pushInheritsChangeDetection'] is True and facts['unboundAlwaysChanged'] is True
    for flag in ('sourceBaseTableActualExtensionVerified','sourceProgressUnitVerified','horizontalCalibrationIdentityVerified','firmwareAbortVerified'):
        assert facts[flag] is False
    for flag in ('appCodeExecuted','liveUiExecuted','targetDeviceVerified','modelLayoutVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded'):
        assert proof[flag] is False

if manifest.get('sensorCalibrationSdk'):
    sdk=manifest['sensorCalibrationSdk'];proof=json.loads((root/manifest['sensorCalibrationResearch']).read_text())
    states={r['sourceId']:r['name'] for r in proof['sensorStates']}
    js=(root/'node/src/app-sensor-calibration.js').read_text().split('const states=new Map(',1)[1].split(');',1)[0]
    py=(root/'python/rs4mini_sdk/app_sensor_calibration.py').read_text().split('STATES=',1)[1].split('\n',1)[0]
    native=(root/'macos/RSControlCore.m').read_text().split('NSDictionary *RSDecodeAppSensorCalibrationNotification(',1)[1].split('NSDictionary *states=@',1)[1].split(';',1)[0]
    assert dict(ast.literal_eval(js))==states and ast.literal_eval(py)==states
    assert {int(k):v for k,v in re.findall(r'@(\d+):@"(\w+)"',native)}==states
    assert sdk['sourceModelClass']==proof['basePolicies'][1]['modelClass'] and sdk['sourceStatusIds']==[0,1,3,9]
    assert sdk['passiveOnly'] is True and sdk['rawProgressUnclamped'] is True
    for flag in ('shortDefaultsSynthesized','sourceDomainsConflated','legacyExperimentalFormatOverwritten','automaticQuerySubscriptionAckOrControlEnabled','requestAssociationVerified','modelLayoutVerified','progressUnitVerified','targetDeviceVerified'):
        assert sdk[flag] is False
    assert len(json.loads((root/sdk['fixtures']).read_text()))==7

if manifest.get('calibrationEntryResearch'):
    proof=json.loads((root/manifest['calibrationEntryResearch']).read_text())
    assert len(proof['methods'])==63 and len(proof['layouts'])==2
    assert proof['sourceActions']['normal']['bodyHex']=='05' and proof['sourceActions']['advanced']['bodyHex']=='00'
    assert proof['sourceActions']['bothRequireCachedMotorEnabled'] is True and proof['sourceActions']['uiSystemCalibrationIsSystemCalc'] is False
    assert proof['hg724ExplicitCase']['normalVisible'] is False and proof['hg724ExplicitCase']['advancedVisible'] is True and proof['hg724ExplicitCase']['versionQueryRequired'] is False
    assert proof['threshold']['literal']=='00.02.32.25' and proof['threshold']['number']==139289 and proof['threshold']['comparison']=='strict-greater-than'
    assert proof['lifecycle']['advancedAckStartsUiTimerMs']==60000 and proof['lifecycle']['transitiveFirmwareStopProven'] is False
    assert proof['lifecycle']['liveIndexOrCacheFreshnessVerified'] is False and proof['scope']['fullActivityReachabilityVerified'] is False
    for flag in ('appCodeExecuted','liveUiExecuted','targetDeviceVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded'):
        assert proof[flag] is False

if manifest.get('tutorialSdk'):
    sdk=manifest['tutorialSdk']
    assert sdk['passiveOnly'] is True
    for flag in ['stepSendExposed','automaticAck','unknownStepIsCompletionVerified','targetDeviceVerified','modelLayoutVerified','requestAssociationVerified','physicalCompletionVerified']:
        assert sdk[flag] is False
    assert (root/sdk['documentation']).is_file()
    tutorial_row=next(row for row in manifest['commands'] if row['key']=='04:2B')
    assert tutorial_row['tutorialResearch']==manifest['tutorialResearch']
    step_row=next(row for row in manifest['commands'] if row['key']=='04:2C')
    assert step_row['requestCodec']=='unknown' and not step_row['implementation']

if manifest.get('balanceAdjustResearch'):
    proof=json.loads((root/manifest['balanceAdjustResearch']).read_text())
    for flag in ['appCodeExecuted','liveUiExecuted','targetDeviceVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded','hg724EntryEstablished']:
        assert proof[flag] is False
    assert len(proof['methods'])==61 and len(proof['directCallers'])==6
    assert proof['sourceReceive']['sameCommandAsRequest'] and proof['sourceReceive']['bitPairsParsedAsDecimalStrings']
    assert proof['sourceEnums']['status']['TEST_FINISHED']==10 and proof['sourceEnums']['status']['TEST_ERROR']==11
    assert proof['sourceUi']['timerMs']==20000 and proof['sourceUi']['detachSendsStop'] is False
    assert proof['sourceRequest']['sendEnabledInSdk'] is False
    row=next(row for row in manifest['commands'] if row['key']=='04:40')
    assert row['balanceAdjustResearch']==manifest['balanceAdjustResearch'] and row['requestCodec']=='unknown' and not row['implementation']

if manifest.get('balanceEntryResearch'):
    proof=json.loads((root/manifest['balanceEntryResearch']).read_text())
    for flag in ['appCodeExecuted','liveUiExecuted','targetDeviceVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded','hg724Command40PathEstablished','hg724Command40UnsupportedProven']:
        assert proof[flag] is False
    assert len(proof['methods'])==30 and len(proof['layouts'])==4 and proof['uniqueLayoutCount']==3
    case=proof['explicitHg724SelectedCase']
    assert case['needBalanceTest'] is False and case['menuTarget']=='GimbalVideoAdjustRS3' and case['videoTestButtonVisibility']==8
    assert case['forcedOldCheckAdjustTextVisibility']==0 and case['firmwareSupportVerified'] is False
    assert len(proof['oldAdjustLiteralReferenceMethods'])==3
    row=next(row for row in manifest['commands'] if row['key']=='04:40')
    assert row['balanceEntryResearch']==manifest['balanceEntryResearch'] and not row['implementation']

if manifest.get('codeSlotResearch'):
    proof=json.loads((root/manifest['codeSlotResearch']).read_text())
    for flag in ['appCodeExecuted','liveUiExecuted','targetDeviceVerified','wholeAppRecovered','wholeProtocolRecovered','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded','existingSixRestoredDexViewsChanged']:
        assert proof[flag] is False
    assert proof['namedMetadataStillUnresolvedBanks']==[1,7] and proof['additionalBackupSlotsAudited']==3137
    prior=json.loads((root/manifest['codeBankResearch']).read_text())
    prior_rows={r['segment']:r for r in prior['banks']}
    for bank,count in zip(proof['banks'],[2623,514]):
        assert bank['matchedBackupCodeItems']==count and bank['allBackupSlotsMatched'] and bank['methodOwnerIndicesConsistent']
        assert bank['currentAndBackupFootprintsMatch'] and bank['destinationsNonOverlapping']
        for flag in ['namedMetadataRestored','stringOrderIndependentlyCorroborated','typeIdentityRecovered','prototypeIdentityRecovered','parseableDexProduced']:
            assert bank[flag] is False
        old=prior_rows[bank['segment']]
        assert old['bankSha256']==bank['bankSha256'] and old['backupRecords']==count and old['restored'] is False

if manifest.get('prefixRestorationResearch'):
    proof=json.loads((root/manifest['prefixRestorationResearch']).read_text())
    for flag in ['appCodeExecuted','liveUiExecuted','nativeLibraryExecuted','targetDeviceVerified','wholeAppRecovered','wholeProtocolRecovered','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded','previousSixFilesModified','legacyCallerEvidenceScopeAutomaticallyExpanded']:
        assert proof[flag] is False
    assert proof['namedDexViewsRecovered']==8 and proof['restoredBackupCodeItems']==52679
    assert len(proof['banks'])==8
    for bank in proof['banks']:
        assert bank['sourceProtectedContainerAdler32Matched'] and bank['sourceHeaderSha1MatchesProtectedContainer'] is False
        if bank['segment'] not in (1,7):assert bank['legacySemanticBytes112ToOriginalSizeMatch'] is True
    independent=json.loads((root/manifest['prefixIndependentValidation']).read_text())
    assert independent['allPrefixesMatched'] and independent['totalBytesCompared']==1048576
    assert [b['decryptedPrefixSha256'] for b in independent['banks']]==[b['decryptedPrefixSha256'] for b in proof['banks']]
    calls=json.loads((root/manifest['prefixNewCallers']).read_text())
    assert len(calls['directCallerMethods'])==19 and [b['gimbalDirectInvocations'] for b in calls['banks']]==[60,0]
    for flag in ['appCodeExecuted','targetDeviceVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded','modelPathsVerified','cameraApisAdded','activationCommandsAdded']:
        assert calls[flag] is False

    current=manifest['currentNamedDexResearch']
    assert current['evidence']==manifest['prefixRestorationResearch'] and current['banks']==list(range(8))
    assert current['namedViews']==8 and current['backupCodeItemsMatched']==52679 and current['historicalSixBankEvidenceUnchanged'] is True
    assert current['fullAppRecovered'] is False and current['wholeProtocolRecovered'] is False and current['targetDeviceVerified'] is False

if manifest.get('activationResearch'):
    proof=json.loads((root/manifest['activationResearch']).read_text())
    for flag in ['appCodeExecuted','liveUiExecuted','targetDeviceVerified','wholeProtocolRecovered','wholeAppRecovered','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded','hg724EntryEstablished','bleRouteVerified','activationPersistenceVerified','actualSessionVersionVerified','networkVsDeviceWorkflowFullyAudited']:
        assert proof[flag] is False
    assert len(proof['methods'])==56 and proof['commonEnumScope']==['ActiveStatus']
    assert proof['command']['commandSet']==0 and proof['command']['commandId']==50
    assert proof['command']['enumBinding']['arguments']==['ActiveStatus',20,50,0,1,None]
    assert proof['command']['enumBinding']['explicitNullArgumentIndexes']==[5]
    assert proof['commandSetSourceBinding']['unresolvedReferenceArgumentIndexes']==[3]
    assert proof['typeValuesByVersion']['Ver1_3']['SET']==18 and proof['typeValuesByVersion']['Ver13']['SET']==2
    assert proof['sourceVersionQuery']['bodyHex']=='00' and proof['sourceVersionQuery']['sourceResendPolicyCopiedToSdk'] is False
    assert proof['sourceResponse']['wireOffsetsIndependentlyVerified'] is False
    row=next(row for row in manifest['commands'] if row['key']=='00:32')
    assert row['activationResearch']==manifest['activationResearch'] and row['requestCodec']==('implemented' if center_sdk else 'unknown') and (center_sdk or not row['implementation'])

if manifest.get('activationReceiveResearch'):
    proof=json.loads((root/manifest['activationReceiveResearch']).read_text())
    assert len(proof['methods'])==39 and len(proof['bankSha256'])==8
    assert proof['baseCommonPolicy']==dict(commandSet=0,commandId=50,isBlock=False,isMix=True,modelClass=None,explicitNullClass=True,needsCcode=True,needsCcodeDerivedFromConstructor=True)
    assert proof['receiveMapping']['ackBusinessRawPayloadOffset']==1
    assert proof['mixedDelivery']['processorPathEligible'] and proof['mixedDelivery']['pushPathEligible']
    assert proof['sourcePushOrder']['assignsRawCacheBeforeNullLengthAndAckGuards'] is True
    assert proof['sourcePushOrder']['everyAckGuaranteedToReachPushModel'] is False
    for flag in ['hg724EntryEstablished','actualSessionVersionVerified','targetDeviceVerified','appCodeExecuted','javaReflectionExecuted','sdkSendAdded','sdkReceiveAdded','wholeProtocolRecovered']:
        assert proof[flag] is False
    assert len(proof['versionQueryCallers'])==7
    row=next(row for row in manifest['commands'] if row['key']=='00:32')
    assert row['activationReceiveResearch']==manifest['activationReceiveResearch'] and row['responseCodec']==('candidate-structured' if center_sdk else 'unknown') and (center_sdk or not row['implementation'])

if manifest.get('activationFormatsResearch'):
    proof=json.loads((root/manifest['activationFormatsResearch']).read_text())
    assert len(proof['methods'])==34 and proof['parsedMethodBanks']==[5] and len(proof['bankSha256'])==8
    assert proof['sourcePushQuirks']['dispatchIntegerRequestedBytes']==1 and proof['sourcePushQuirks']['oldPushSnOffset']==1
    assert proof['sourcePushQuirks']['newPushActivatedFieldDirectlyStoresTextIsEmpty'] is True
    assert proof['v13']['minimumBytes']==23 and proof['v14']['minimumBytes']==143
    assert proof['sourceSideEffects']['deviceInfoHandlerCallsSetUserInfo'] is True
    assert proof['sourceSideEffects']['sourceHandlersExecuted'] is False and proof['sourceSideEffects']['automaticReplyAdded'] is False
    for flag in ['sdkSendAdded','sdkReceiveAdded','targetDeviceVerified','hg724EntryEstablished','actualSessionVersionVerified','activationValidityVerified','vendorCodeExecuted','wholeProtocolRecovered','networkActivationWorkflowComplete']:
        assert proof[flag] is False
    row=next(row for row in manifest['commands'] if row['key']=='00:32')
    assert row['activationFormatsResearch']==manifest['activationFormatsResearch'] and row['requestCodec']==('implemented' if center_sdk else 'unknown') and (center_sdk or not row['implementation'])

if manifest.get('activationEntryResearch'):
    proof=json.loads((root/manifest['activationEntryResearch']).read_text())
    assert len(proof['methods'])==17 and len(proof['bankSha256'])==8
    assert proof['hg724InheritedSerialSourceRouteEstablished'] is True
    assert proof['getterAnnotation']==dict(value='GimbalSerialNumber')
    query=proof['serialQuerySource']
    assert (query['commandSet'],query['commandId'],query['receiverType'],query['receiverId'],query['packedReceiverByte'])==(0,50,5,7,229)
    assert query['initialSourceGetBodyHex']=='11' and query['actualSessionVersionVerified'] is False and query['freshResultVerified'] is False
    assert len(proof['activationModuleFieldReferences'])==4 and len(proof['directModuleTypeWrites'])==1
    assert proof['sourceDefaultModuleGate']['expectedModuleType']==8 and proof['sourceDefaultModuleGate']['firmwareUnsupportedProven'] is False
    for flag in ['actualHg724RegistryVerified','targetDeviceVerified','javaReflectionExecuted','vendorCodeExecuted','sdkSendAdded','sdkReceiveAdded','activationOrBindingImplemented','wholeProtocolRecovered']:
        assert proof[flag] is False
    row=next(row for row in manifest['commands'] if row['key']=='00:32')
    assert row['activationEntryResearch']==manifest['activationEntryResearch'] and row['targetEvidence']=='app-code-path' and (center_sdk or not row['implementation'])

if center_sdk:
    sdk=manifest['centerInfoSdk']
    assert sdk['explicitVersionRequired'] and sdk['getOnly']
    assert (sdk['commandSet'],sdk['commandId'],sdk['receiverByte'])==(0,50,229)
    for flag in ['sourceCacheFallbackEnabled','automaticRetryEnabled','versionNegotiationEnabled','activationWriteEnabled','targetDeviceVerified','modelLayoutVerified','actualSessionVersionVerified','activationValidityVerified']:
        assert sdk[flag] is False
    assert (root/sdk['fixtures']).is_file() and (root/sdk['documentation']).is_file()
