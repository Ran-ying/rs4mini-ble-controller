import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ronin_activation_receive import (
    activation_version_ack_view, common_policy, check_common_constructor,
    check_push_order, trace, COMMON, ROOT, PREFIX_BANKS, VERSIONS,
)


class ActivationReceiveTests(unittest.TestCase):
    def test_all_byte_versions_preserve_unknown_and_distinct_known_values(self):
        reverse = {v: n for n, v in VERSIONS.items()}
        for raw in range(256):
            r = activation_version_ack_view(0x80, bytes([0, raw, 0xAA, 0xBB]))
            self.assertEqual(r['versionRaw'], raw)
            self.assertEqual(r['versionName'], reverse.get(raw))
            self.assertEqual(r['versionKnown'], raw in reverse)
            self.assertEqual(r['sourceVersionFallback'], None if raw in reverse else 'OTHER')
            self.assertEqual(r['trailingBodyHex'], 'aabb')
            self.assertEqual(r['businessOffsetInPayload'], 1)
            self.assertFalse(r['activationStateDecoded'])
        self.assertEqual(activation_version_ack_view(128, b'\0\x03')['versionName'], 'Ver1_3')
        self.assertEqual(activation_version_ack_view(128, b'\0\x33')['versionName'], 'Ver13')
        self.assertEqual(activation_version_ack_view(128, b'\0\x64')['versionName'], 'OTHER')

    def test_ack_without_business_is_incomplete_never_version_zero(self):
        r = activation_version_ack_view(128, b'\0')
        self.assertTrue(r['sourceCallbackReportsSuccess'])
        self.assertFalse(r['businessComplete'])
        self.assertIsNone(r['versionRaw'])
        self.assertIsNone(r['versionName'])
        self.assertIsNone(r['sourceVersionFallback'])
        self.assertEqual(r['businessBodyHex'], '')

    def test_nonzero_ccode_never_decodes_version_even_when_body_looks_known(self):
        for ccode in range(1, 256):
            r = activation_version_ack_view(128, bytes([ccode, 1, 2]))
            self.assertFalse(r['sourceCallbackReportsSuccess'])
            self.assertIsNone(r['versionRaw'])
            self.assertIsNone(r['versionName'])
            self.assertIsNone(r['sourceVersionFallback'])
            self.assertEqual(r['businessBodyHex'], '0102')
            self.assertIsNone(r['trailingBodyHex'])

    def test_every_encrypted_mode_rejects_and_ack_required(self):
        for flags in range(256):
            if flags & 7 or not flags & 128:
                with self.assertRaises(ValueError):
                    activation_version_ack_view(flags, b'\0\1')
            else:
                self.assertEqual(activation_version_ack_view(flags, b'\0\1')['versionName'], 'Ver1_1')

    def test_flags_and_payload_validation_and_missing_return_code(self):
        for flags, payload in [(True, b'\0'), (-1, b'\0'), (256, b'\0'), ('128', b'\0'), (128, []), (128, '00'), (128, b'')]:
            with self.assertRaises(ValueError):
                activation_version_ack_view(flags, payload)

    def test_view_has_no_retained_input_or_implicit_state(self):
        data = bytearray([0, 3, 7])
        r = activation_version_ack_view(128, data)
        data[:] = b'\1\0\0'
        self.assertEqual(r['rawPayloadHex'], '000307')
        self.assertEqual(r['versionName'], 'Ver1_3')
        self.assertIsNone(activation_version_ack_view(128, b'\0')['versionName'])
        for flag in ['requestAssociationVerified', 'actualSessionVersionVerified', 'targetDeviceVerified', 'activationStateDecoded']:
            self.assertFalse(r[flag])

    def binding(self):
        return dict(descriptor='(Ljava/lang/String; I I Z Z Ljava/lang/Class;)V',
                    arguments=['ActiveStatus', 20, 50, 0, 1, None], explicitNullArgumentIndexes=[5])

    def test_policy_requires_explicit_null_and_integer_source_literals(self):
        r = common_policy(self.binding())
        self.assertFalse(r['isBlock'])
        self.assertTrue(r['isMix'])
        self.assertIsNone(r['modelClass'])
        for field, value in [('explicitNullArgumentIndexes', []), ('descriptor', '(I)V')]:
            b = self.binding(); b[field] = value
            with self.assertRaises(ValueError):common_policy(b)
        for index, value in [(1, 50), (2, 20), (3, False), (4, True), (5, 'unknown')]:
            b = self.binding(); b['arguments'][index] = value
            with self.assertRaises(ValueError):common_policy(b)

    def constructor(self):
        return [(6, 'const/4', 'v1, 1'),
                (8, 'iput-boolean', 'v1, v0, ' + COMMON + '->isNeedCcode Z'),
                (16, 'iput-boolean', 'v5, v0, ' + COMMON + '->isMix Z'),
                (20, 'iput-boolean', 'v4, v0, ' + COMMON + '->isBlock Z'),
                (24, 'iput-object', 'v6, v0, ' + COMMON + '->cls Ljava/lang/Class;')]

    def test_need_ccode_is_separate_from_enum_block_mix_arguments(self):
        rows = self.constructor(); check_common_constructor(rows)
        for n in range(len(rows)):
            modified = list(rows); off, op, text = rows[n]
            modified[n] = (off, op, text.replace('v1, 1', 'v1, 0') if n == 0 else text.replace('v0, ', 'v9, '))
            with self.assertRaises(ValueError):check_common_constructor(modified)

    def push(self):
        return [(0, 'invoke-virtual', 'v5, v6, ' + ROOT + '->setRecData([B)V'),
                (6, 'if-eqz', 'v6, +10ah'), (10, 'array-length', 'v0, v6'),
                (12, 'const/16', 'v1, 11'), (16, 'if-lt', 'v0, v1, +105h'),
                (24, 'iget', 'v0, v0, Ldji/midware/data/packages/P3/Pack;->cmdType I'),
                (28, 'const/4', 'v1, 1'), (30, 'if-ne', 'v0, v1, +004h')]

    def test_raw_cache_assignment_is_before_all_three_guards(self):
        rows = self.push(); check_push_order(rows)
        for n in range(len(rows)):
            modified = list(rows); off, op, text = rows[n]
            modified[n] = (off + 2, op, text)
            with self.assertRaises(ValueError):check_push_order(modified)

    def test_wrong_apk_rejected_before_optional_parser(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'apk'; p.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError, 'APK hash'):trace(p, Path(t))

    def test_each_of_eight_pinned_banks_checked_before_optional_parser(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t); p = d / 'apk'; p.write_bytes(b'apk')
            pin = hashlib.sha256(b'bank').hexdigest()
            for bad in PREFIX_BANKS:
                for b in PREFIX_BANKS:
                    (d / ('business-%02d-prefix-code-restored.dex' % b)).write_bytes(b'bad' if b == bad else b'bank')
                with patch('ronin_activation_receive.APK_SHA256', hashlib.sha256(b'apk').hexdigest()), patch('ronin_activation_receive.PREFIX_BANKS', {b: pin for b in PREFIX_BANKS}):
                    with self.assertRaisesRegex(ValueError, 'bank hash'):trace(p, d)

    def evidence(self):
        return json.loads((Path(__file__).resolve().parents[2] / 'protocol/research/ronin-activation-receive-evidence.json').read_text())

    def test_source_evidence_keeps_conditional_mapping_and_model_boundaries(self):
        r = self.evidence()
        self.assertEqual(len(r['bankSha256']), 8)
        self.assertEqual(r['baseCommonPolicy']['commandId'], 50)
        self.assertTrue(r['baseCommonPolicy']['needsCcode'])
        self.assertEqual(r['receiveMapping']['ackBusinessRawPayloadOffset'], 1)
        self.assertTrue(r['mixedDelivery']['processorPathEligible'])
        self.assertTrue(r['mixedDelivery']['pushPathEligible'])
        self.assertFalse(r['mixedDelivery']['actualReflectionSuccessVerified'])
        self.assertTrue(r['sourcePushOrder']['assignsRawCacheBeforeNullLengthAndAckGuards'])
        self.assertFalse(r['sourcePushOrder']['everyAckGuaranteedToReachPushModel'])
        for flag in ['hg724EntryEstablished', 'actualSessionVersionVerified', 'targetDeviceVerified', 'appCodeExecuted', 'javaReflectionExecuted', 'sdkSendAdded', 'sdkReceiveAdded', 'wholeProtocolRecovered']:
            self.assertFalse(r[flag])

    def test_direct_callers_not_mistaken_for_gimbal_or_dataflow_proof(self):
        r = self.evidence()
        self.assertEqual(len(r['versionQueryCallers']), 7)
        external = [x for x in r['versionQueryCallers'] if x['className'] != 'Ldji/midware/data/model/common/DataCommonActiveGetVer;']
        self.assertEqual(len(external), 5)
        self.assertFalse(any('GIMBAL' in x['deviceTypeLiterals'] for x in external))
        self.assertFalse(any(x['literalDataflowToQueryVerified'] for x in external))
        self.assertFalse(r['absentGimbalCallerProvesUnsupported'])
