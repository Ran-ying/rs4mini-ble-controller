import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ronin_activation_formats import (
    source_sn_text, source_integer_read, get_status_view, v13_push_view, v14_push_view,
    check_push_reads, trace, ROOT, PREFIX_BANKS,
)


class ActivationFormatTests(unittest.TestCase):
    def test_source_sn_keeps_signed_decimal_instead_of_ascii_normalization(self):
        self.assertEqual(source_sn_text(b'Az09\0-\xff\x80'), 'Az09045-1-128')
        for value in range(256):
            expected = chr(value) if 48 <= value <= 57 or 65 <= value <= 90 or 97 <= value <= 122 else str(value if value < 128 else value - 256)
            self.assertEqual(source_sn_text(bytes([value])), expected)
        self.assertEqual(source_sn_text(b''), '')

    def test_source_integer_padding_is_explicit_not_validated_status(self):
        self.assertEqual(source_integer_read(b'\x80', 0, 1), 128)
        self.assertEqual(source_integer_read(b'\xff' * 4 + b'\x01', 0, 5), -1)
        self.assertEqual(source_integer_read(b'\x01', 5, 1), 0)
        self.assertEqual(source_integer_read(b'\x01\x02', 1, 2), 2)
        for start, width in [(True, 1), (0, True), (-1, 1), (0, 0), (0, 33)]:
            with self.assertRaises(ValueError):source_integer_read(b'\0', start, width)

    def get_body(self, version='Ver1_1'):
        head = bytes([0x83]) + (2026).to_bytes(2, 'little') + bytes([10, 19, 12, 34, 56])
        return head + (b'0123456789' if version == 'Ver1_0' else b'\x03Ab9')

    def test_get_is_explicit_version_and_gimbal_business_context(self):
        for version, request, offset, sn in [('Ver1_0', 1, 8, '0123456789'), ('Ver1_1', 17, 9, 'Ab9'), ('Ver1_3', 17, 9, 'Ab9'), ('Ver13', 1, 9, 'Ab9'), ('OTHER', 1, 9, 'Ab9')]:
            r = get_status_view(self.get_body(version) + b'\xde\xad', version)
            self.assertEqual(r['sourceGetRequestValue'], request)
            self.assertEqual(r['snOffset'], offset)
            self.assertEqual(r['sourceSnText'], sn)
            self.assertEqual(r['year'], 2026)
            self.assertEqual([r[n] for n in ['month', 'day', 'hour', 'minute', 'second']], [10, 19, 12, 34, 56])
            self.assertTrue(r['activeBit'])
            self.assertEqual(r['unknownActiveBits'], 0x82)
            self.assertEqual(r['trailingBodyHex'], 'dead')
            self.assertFalse(r['activationValidityVerified'])

    def test_get_truncation_never_uses_source_zero_padding_or_old_cache(self):
        for version in ['Ver1_0', 'Ver1_1']:
            body = self.get_body(version)
            for length in range(len(body)):
                with self.assertRaises(ValueError):get_status_view(body[:length], version)
        for version in ['unknown', 1, None]:
            with self.assertRaises(ValueError):get_status_view(self.get_body(), version)
        for n in range(17, 256):
            with self.assertRaisesRegex(ValueError, 'exceeds16'):get_status_view(bytes(8) + bytes([n]) + bytes(n), 'Ver1_1')

    def test_get_preserves_unvalidated_date_and_all_active_bits(self):
        for raw in range(256):
            body = bytes([raw, 255, 255, 255, 0, 255, 255, 255, 0])
            r = get_status_view(body, 'Ver1_1')
            self.assertEqual(r['activeBit'], bool(raw & 1))
            self.assertEqual(r['unknownActiveBits'], raw & 254)
            self.assertEqual(r['year'], 65535)
            self.assertEqual(r['month'], 255)
            self.assertFalse(r['dateValidityVerified'])
            self.assertEqual(r['snLength'], 0)

    def v13(self, declared=3, tail=b'ABC'):
        return b'\x33' + b'\xfe\xff\xff\xff' + bytes(range(16)) + bytes([7, declared]) + tail

    def test_v13_declared_length_and_copied_bytes_remain_distinct(self):
        for n in range(256):
            body = self.v13(n, b'ABC')
            r = v13_push_view(body)
            self.assertEqual(r['safeCommandType'], -2)
            self.assertEqual(r['nonceHex'], bytes(range(16)).hex())
            self.assertEqual(r['activateModuleCount'], 7)
            self.assertEqual(r['deviceNumberCopiedBytes'], min(n, 3))
            self.assertEqual(r['declaredDeviceNumberComplete'], n <= 3)
            self.assertEqual(r['deviceNumberRawHex'], b'ABC'[:n].hex())
            self.assertEqual(r['trailingBodyHex'], b'ABC'[n:].hex())

    def test_v13_short_or_wrong_marker_rejects_without_default(self):
        body = self.v13()
        for n in range(23):
            with self.assertRaises(ValueError):v13_push_view(body[:n])
        for marker in [0, 3, 19, 54, 255]:
            with self.assertRaises(ValueError):v13_push_view(bytes([marker]) + body[1:])

    def v14(self):
        body = bytearray(143)
        body[0] = 54
        body[1:5] = b'\0\0\0\x80'
        body[5] = 40
        body[6:38] = bytes(range(32))
        body[38:41] = bytes([4, 9, 31])
        body[41:73] = b'B' * 32
        body[73:105] = b'T' * 32
        body[105] = 33
        body[106:138] = b'U' * 32
        body[138:143] = bytes([103, 7, 2, 3, 0])
        return body

    def test_v14_fixed_arrays_do_not_follow_declared_string_lengths(self):
        r = v14_push_view(self.v14() + b'12345tail')
        self.assertEqual(r['safeCommandType'], -2147483648)
        self.assertEqual(r['deviceNumberRawHex'], bytes(range(32)).hex())
        self.assertFalse(r['deviceNumberDeclaredWithinStorage'])
        self.assertTrue(r['boardNumberDeclaredWithinStorage'])
        self.assertFalse(r['userIdDeclaredWithinStorage'])
        self.assertEqual(r['boardNumberRawHex'], (b'B' * 32).hex())
        self.assertEqual(r['timeInfoRawHex'], (b'T' * 32).hex())
        self.assertEqual(r['userIdRawHex'], (b'U' * 32).hex())
        self.assertEqual(r['reservedVerifyRawHex'], b'12345'.hex())
        self.assertEqual(r['trailingBodyHex'], b'tail'.hex())
        self.assertEqual(r['moduleType'], 4)
        self.assertEqual(r['moduleNoActivateCount'], 9)
        self.assertEqual(r['deviceType'], 103)
        self.assertFalse(r['verificationPerformed'])

    def test_v14_reserved_verify_lengths_are_little_endian_and_source_clamped(self):
        for n in [0, 1, 255, 256, 257, 32768, 65535]:
            for verify in [0, 1, 255]:
                body = self.v14(); body[140] = verify; body[141:143] = n.to_bytes(2, 'little')
                r = v14_push_view(body + b'abc')
                self.assertEqual(r['reservedVerifyDeclaredBytes'], n + verify)
                self.assertEqual(r['reservedVerifyCopiedBytes'], min(n + verify, 3))
                self.assertEqual(r['declaredReservedVerifyComplete'], n + verify <= 3)
                self.assertEqual(r['trailingBodyHex'], b'abc'[n + verify:].hex())

    def test_v14_all_byte_length_fields_preserve_declared_values(self):
        fields = {5: 'deviceNumberDeclaredBytes', 40: 'boardNumberDeclaredBytes', 105: 'userIdDeclaredBytes', 140: 'verifyCodeDeclaredBytes'}
        for offset, name in fields.items():
            for n in range(256):
                body = self.v14(); body[offset] = n
                r = v14_push_view(body)
                self.assertEqual(r[name], n)
                self.assertEqual(len(bytes.fromhex(r['deviceNumberRawHex'])), 32)

    def test_v14_short_or_wrong_marker_rejects(self):
        body = self.v14()
        for n in range(143):
            with self.assertRaises(ValueError):v14_push_view(body[:n])
        body[0] = 51
        with self.assertRaises(ValueError):v14_push_view(body)

    def test_views_copy_bytes_and_never_reply_or_verify(self):
        for fn, body in [(v13_push_view, bytearray(self.v13())), (v14_push_view, self.v14())]:
            r = fn(body); original = bytes(body); body[:] = bytes(len(body))
            self.assertEqual(r['rawBusinessHex'], original.hex())
            for flag in ['automaticReplyEnabled', 'senderAndModuleGateVerified', 'targetDeviceVerified', 'activationValidityVerified']:
                self.assertFalse(r[flag])
        for fn in [source_sn_text, v13_push_view, v14_push_view]:
            for bad in [None, [], 'abc']:
                with self.assertRaises(ValueError):fn(bad)

    def test_push_register_check_distinguishes_minimum11_from_byte_read1(self):
        rows = [(12,'const/16','v1, 11'),(28,'const/4','v1, 1'),
                (156,'invoke-virtual','v5, v3, v1, v0, v2, '+ROOT+'->get(I I Ljava/lang/Class; [I)Ljava/lang/Number;'),
                (248,'invoke-virtual','v5, v1, v0, '+ROOT+'->getRevertSn(I I)Ljava/lang/String;'),
                (300,'invoke-virtual','v5, v1, v1, v6, v0, '+ROOT+'->get(I I Ljava/lang/Class; [I)Ljava/lang/Number;'),
                (344,'const/4','v0, 2'),(346,'invoke-virtual','v5, v0, v6, '+ROOT+'->getRevertSn(I I)Ljava/lang/String;'),
                (362,'invoke-static','v6, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z'),
                (368,'move-result','v6'),(370,'sput-boolean','v6, '+ROOT+'->isPushActivated Z')]
        check_push_reads(rows)
        for n in range(len(rows)):
            changed = list(rows); off, op, text = changed[n]; changed[n] = (off + 1, op, text)
            with self.assertRaises(ValueError):check_push_reads(changed)
        with self.assertRaises(ValueError):check_push_reads(rows + [(150,'const/4','v1, 11')])

    def test_wrong_apk_rejected_before_optional_parser(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'apk'; p.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError, 'APK hash'):trace(p, Path(t))

    def test_all_eight_inputs_pinned_even_when_selected_methods_are_bank5(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t); p = d / 'apk'; p.write_bytes(b'apk'); pin = hashlib.sha256(b'bank').hexdigest()
            for bad in PREFIX_BANKS:
                for b in PREFIX_BANKS:(d / ('business-%02d-prefix-code-restored.dex' % b)).write_bytes(b'bad' if b == bad else b'bank')
                with patch('ronin_activation_formats.APK_SHA256', hashlib.sha256(b'apk').hexdigest()), patch('ronin_activation_formats.PREFIX_BANKS', {b: pin for b in PREFIX_BANKS}):
                    with self.assertRaisesRegex(ValueError, 'bank hash'):trace(p, d)

    def test_evidence_preserves_generic_source_and_no_execution_boundaries(self):
        r = json.loads((Path(__file__).resolve().parents[2] / 'protocol/research/ronin-activation-formats-evidence.json').read_text())
        self.assertEqual(r['parsedMethodBanks'], [5])
        self.assertEqual(r['sourcePushQuirks']['dispatchIntegerRequestedBytes'], 1)
        self.assertEqual(r['sourcePushQuirks']['oldPushSnOffset'], 1)
        self.assertEqual(r['v13']['minimumBytes'], 23)
        self.assertEqual(r['v14']['minimumBytes'], 143)
        self.assertTrue(r['sourceSideEffects']['deviceInfoHandlerCallsSetUserInfo'])
        self.assertFalse(r['sourceSideEffects']['sourceHandlersExecuted'])
        for flag in ['sdkSendAdded', 'sdkReceiveAdded', 'targetDeviceVerified', 'hg724EntryEstablished', 'actualSessionVersionVerified', 'activationValidityVerified', 'vendorCodeExecuted', 'wholeProtocolRecovered', 'networkActivationWorkflowComplete']:
            self.assertFalse(r[flag])
