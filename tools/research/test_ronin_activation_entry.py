import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ronin_activation_entry import (
    source_module_gate, source_push_sn_choice, check_module_default, check_push_sn_choice,
    trace, ROOT, PREFIX_BANKS,
)


class ActivationEntryTests(unittest.TestCase):
    def test_default_module8_does_not_pass_gimbal4_or_center5(self):
        for sender in [4, 5]:
            for format_name in ['sourceV13', 'sourceV14']:
                args = dict(format_name=format_name)
                if format_name == 'sourceV14':args['module_type'] = sender
                r = source_module_gate(8, sender, **args)
                self.assertFalse(r['sourceSenderMatches'])
                self.assertFalse(r['sourceHandlerGatePasses'])
                self.assertFalse(r['replyEnabled'])
                self.assertFalse(r['targetDeviceVerified'])

    def test_all_sender_bytes_require_explicit_matching_source_context(self):
        for sender in range(256):
            r = source_module_gate(8, sender, format_name='sourceV13')
            self.assertEqual(r['sourceHandlerGatePasses'], sender == 8)
            self.assertIsNone(r['sourceModuleMatches'])
        self.assertTrue(source_module_gate(4, 4, format_name='sourceV13')['sourceHandlerGatePasses'])
        self.assertFalse(source_module_gate(4, 4, format_name='sourceV13')['runtimeModuleContextVerified'])

    def test_v14_requires_sender_and_parsed_module_both_match(self):
        for module in range(256):
            for sender in [4, 8]:
                r = source_module_gate(8, sender, format_name='sourceV14', module_type=module)
                self.assertEqual(r['sourceModuleMatches'], module == 8)
                self.assertEqual(r['sourceHandlerGatePasses'], sender == 8 and module == 8)
                self.assertFalse(r['handlerExecuted'])

    def test_gate_rejects_missing_wrong_domain_and_boolean_context(self):
        for expected, sender, args in [(True, 8, dict(format_name='sourceV13')), (8, False, dict(format_name='sourceV13')), (-1, 8, dict(format_name='sourceV13')), (8, 256, dict(format_name='sourceV13')), (8, 8, dict(format_name='Ver13')), (8, 8, dict(format_name='sourceV14')), (8, 8, dict(format_name='sourceV14', module_type=True)), (8, 8, dict(format_name='sourceV13', module_type=8))]:
            with self.assertRaises(ValueError):source_module_gate(expected, sender, **args)

    def test_empty_source_push_cache_populates_from_get_sn(self):
        self.assertEqual(source_push_sn_choice('', 'new'), 'new')
        self.assertEqual(source_push_sn_choice('', ''), '')

    def test_existing_cache_survives_empty_get_but_changes_for_nonempty_different(self):
        self.assertEqual(source_push_sn_choice('old', ''), 'old')
        self.assertEqual(source_push_sn_choice('old', 'new'), 'new')
        self.assertEqual(source_push_sn_choice('old', 'old'), 'old')
        # TextUtils.isEmpty does not trim whitespace.
        self.assertEqual(source_push_sn_choice('old', ' '), ' ')
        for a, b in [(None, 'new'), ('old', None), ([], 'new')]:
            with self.assertRaises(ValueError):source_push_sn_choice(a, b)

    def test_module_default_producer_is_literal8_not_gimbal_or_platform_enum(self):
        rows = [(6, 'const/16', 'v0, 8'), (14, 'iput', 'v0, v3, ' + ROOT + '->module_type_ I')]
        check_module_default(rows)
        for changed in [[(6, 'const/16', 'v0, 4'), rows[1]], [rows[0], (14, 'iput', 'v1, v3, ' + ROOT + '->module_type_ I')]]:
            with self.assertRaises(ValueError):check_module_default(changed)

    def test_cache_branch_offsets_distinguish_write_from_return(self):
        rows = [(20, 'if-nez', 'v1, +010h'), (32, 'if-nez', 'v1, +00ch'), (48, 'if-nez', 'v1, +004h'), (52, 'iput-object', 'v0, v2, ' + ROOT + '->pushSN Ljava/lang/String;'), (56, 'iget-object', 'v0, v2, ' + ROOT + '->pushSN Ljava/lang/String;')]
        check_push_sn_choice(rows)
        changed = list(rows); changed[0] = (20, 'if-nez', 'v1, +012h')
        with self.assertRaises(ValueError):check_push_sn_choice(changed)
        for index in [3, 4]:
            changed = list(rows); off, op, text = changed[index]; changed[index] = (off, op, text.replace('v0,', 'v9,'))
            with self.assertRaises(ValueError):check_push_sn_choice(changed)

    def test_wrong_apk_rejected_before_optional_parser(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'apk'; p.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError, 'APK hash'):trace(p, Path(t))

    def test_all_eight_bank_hashes_rejected_before_optional_parser(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t); p = d / 'apk'; p.write_bytes(b'apk'); pin = hashlib.sha256(b'bank').hexdigest()
            for bad in PREFIX_BANKS:
                for b in PREFIX_BANKS:(d / ('business-%02d-prefix-code-restored.dex' % b)).write_bytes(b'bad' if b == bad else b'bank')
                with patch('ronin_activation_entry.APK_SHA256', hashlib.sha256(b'apk').hexdigest()), patch('ronin_activation_entry.PREFIX_BANKS', {b: pin for b in PREFIX_BANKS}):
                    with self.assertRaisesRegex(ValueError, 'bank hash'):trace(p, d)

    def evidence(self):
        return json.loads((Path(__file__).resolve().parents[2] / 'protocol/research/ronin-activation-entry-evidence.json').read_text())

    def test_nearest_hg724_getter_is_annotated_and_routes_center7(self):
        r = self.evidence()
        self.assertTrue(r['hg724InheritedSerialSourceRouteEstablished'])
        self.assertEqual(r['getterAnnotation'], {'value': 'GimbalSerialNumber'})
        self.assertIn('Ronin2Abstraction', r['nearestSerialGetter']['className'])
        q = r['serialQuerySource']
        self.assertEqual((q['commandSet'], q['commandId'], q['receiverType'], q['receiverId']), (0, 50, 5, 7))
        self.assertEqual(q['packedReceiverByte'], (7 << 5) | 5)
        self.assertEqual(q['initialSourceGetBodyHex'], '11')
        self.assertEqual(q['initialSourceVersion'], 'Ver1_1')
        self.assertEqual(q['callbackUses'], 'getPushSN')
        self.assertFalse(q['freshResultVerified'])
        self.assertFalse(q['sourceRetryPolicyCopiedToSdk'])
        self.assertFalse(q['actualSessionVersionVerified'])

    def test_eight_bank_field_scan_records_one_module_type_write_not_all_mutation_absence(self):
        r = self.evidence()
        self.assertEqual(len(r['bankSha256']), 8)
        self.assertEqual(len(r['activationModuleFieldReferences']), 4)
        self.assertEqual(len(r['directModuleTypeWrites']), 1)
        write = r['directModuleTypeWrites'][0]
        self.assertEqual(write['className'], ROOT)
        self.assertEqual(write['method'], '<init>')
        self.assertFalse(r['sourceDefaultModuleGate']['runtimeNativeOrReflectionMutationRuledOut'])
        self.assertFalse(r['sourceDefaultModuleGate']['firmwareUnsupportedProven'])

    def test_source_route_is_not_registry_hardware_or_activation_implementation(self):
        r = self.evidence()
        for flag in ['actualHg724RegistryVerified', 'targetDeviceVerified', 'javaReflectionExecuted', 'vendorCodeExecuted', 'sdkSendAdded', 'sdkReceiveAdded', 'activationOrBindingImplemented', 'wholeProtocolRecovered']:
            self.assertFalse(r[flag])
        self.assertTrue(r['sourceGetPushSn']['nonemptyCacheMaySurviveEmptyGetSn'])
        self.assertFalse(r['sourceGetPushSn']['sdkCachePolicyAdded'])
