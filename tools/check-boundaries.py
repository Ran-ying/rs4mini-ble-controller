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
print('Layer boundaries passed: device modules do not depend on motion; upper layers do not encode/write packets.')
print('Protocol inventory: %d entries; inventoryComplete=false; further advanced development is gated.' % len(manifest['commands']))
