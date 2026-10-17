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
    assert len(profiles['methods']) == 26
    assert [(r['baseCommand'],r['name'],r['index'],r['size']) for r in profiles['parameters']] == [('USER_PROFILE','table_choice',0,1),('GIMBAL_WORK_MODE','ronin_gimbal_work_mode',62,1)]
    assert profiles['userProfileUiValues'] == [0,1,2] and profiles['userProfileUiNames'] == ['M1','M2','M3']
    assert [r['value'] for r in profiles['movementProfileSourceEnums']] == [0,1,3,4,5,255]
    assert [r['name'] for r in profiles['workModeSourceEnums']] == ['Free','Flower','Fpv','Center']
    assert profiles['presetGetter'] == dict(businessOffset=2,width=1,rawBleOffsetVerified=False)
    assert profiles['sourceFacts']['hg724SelectedModelUsesNewUiList'] and profiles['sourceFacts']['newProfileSelectorRequiresUserProfile2']
    assert profiles['uiModeArrays'][1]['defaultLanguageValues'] == ['FPV','Custom','3D Roll 360']
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
print('Layer boundaries passed: device modules do not depend on motion; upper layers do not encode/write packets.')
print('Protocol inventory: %d entries; inventoryComplete=false; further advanced development is gated.' % len(manifest['commands']))
