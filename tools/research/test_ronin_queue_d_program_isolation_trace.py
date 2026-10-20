import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ronin_queue_d_program_isolation_trace import (
    BIT_LAYOUT_ESTABLISHED,
    PREFIX_BANKS,
    STATUS_NEEDS_HW,
    STATUS_UNRESOLVED,
    compute_overall,
    compute_substatuses,
    iter_status_combinations,
    scan,
)


class QueueDTests(unittest.TestCase):
    def evidence(self):
        return json.loads(
            (Path(__file__).resolve().parents[2] / 'protocol/research/ronin-queue-d-program-isolation-evidence.json').read_text()
        )

    def test_hash_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            apk = root / 'apk'
            apk.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError, 'APK hash'):
                scan(apk, root)
            apk.write_bytes(b'apk')
            pin = hashlib.sha256(b'bank').hexdigest()
            for bad in PREFIX_BANKS:
                for b in PREFIX_BANKS:
                    (root / ('business-%02d-prefix-code-restored.dex' % b)).write_bytes(
                        b'bad' if b == bad else b'bank'
                    )
                with patch('ronin_queue_d_program_isolation_trace.APK_SHA256', hashlib.sha256(b'apk').hexdigest()), patch(
                    'ronin_queue_d_program_isolation_trace.PREFIX_BANKS', {b: pin for b in PREFIX_BANKS}
                ):
                    with self.assertRaisesRegex(ValueError, 'bank hash'):
                        scan(apk, root)

    def test_every_substatus_combination_affects_overall(self):
        seen = set()
        for bit_ok, cv, cvu, cam, stop, model in iter_status_combinations():
            subs = compute_substatuses(
                bit_layout_established=bit_ok,
                call_values_has_dynamic_boundary=cv,
                call_values_has_unresolved_args=cvu,
                camera_isolation_has_dynamic_boundary=cam,
                stop_semantics_has_dynamic_boundary=stop,
                model_entry_has_dynamic_boundary=model,
            )
            overall = compute_overall(subs)
            seen.add((bit_ok, cv, cvu, cam, stop, model, overall))
            cv_eff = cv and not cvu
            if not bit_ok:
                self.assertEqual(overall, STATUS_UNRESOLVED)
                self.assertEqual(subs['bit_layout'], STATUS_UNRESOLVED)
            else:
                self.assertEqual(subs['bit_layout'], BIT_LAYOUT_ESTABLISHED)
                if cv_eff or cam or stop or model:
                    self.assertEqual(overall, STATUS_NEEDS_HW)
                else:
                    self.assertEqual(overall, STATUS_UNRESOLVED)
            # Facet flags must map 1:1 into substatuses
            self.assertEqual(subs['call_values'], STATUS_NEEDS_HW if cv_eff else STATUS_UNRESOLVED)
            self.assertEqual(subs['camera_isolation'], STATUS_NEEDS_HW if cam else STATUS_UNRESOLVED)
            self.assertEqual(subs['stop_semantics'], STATUS_NEEDS_HW if stop else STATUS_UNRESOLVED)
            self.assertEqual(subs['model_entry'], STATUS_NEEDS_HW if model else STATUS_UNRESOLVED)
        # 2 * 2^5 = 64 combinations
        self.assertEqual(len(seen), 64)
        # Both overall outcomes must appear
        self.assertTrue(any(row[-1] == STATUS_UNRESOLVED for row in seen))
        self.assertTrue(any(row[-1] == STATUS_NEEDS_HW for row in seen))
        # Flipping only model_entry changes overall when bit_layout holds and others false
        a = compute_overall(compute_substatuses(
            bit_layout_established=True,
            call_values_has_dynamic_boundary=False,
            camera_isolation_has_dynamic_boundary=False,
            stop_semantics_has_dynamic_boundary=False,
            model_entry_has_dynamic_boundary=False,
        ))
        b = compute_overall(compute_substatuses(
            bit_layout_established=True,
            call_values_has_dynamic_boundary=False,
            camera_isolation_has_dynamic_boundary=False,
            stop_semantics_has_dynamic_boundary=False,
            model_entry_has_dynamic_boundary=True,
        ))
        self.assertEqual(a, STATUS_UNRESOLVED)
        self.assertEqual(b, STATUS_NEEDS_HW)

    def test_evidence_substatuses_and_no_disproven_claim(self):
        e = self.evidence()
        self.assertEqual(e['substatuses']['bit_layout'], BIT_LAYOUT_ESTABLISHED)
        for key in ('call_values', 'camera_isolation', 'stop_semantics', 'model_entry'):
            self.assertEqual(e['substatuses'][key], STATUS_NEEDS_HW, key)
        self.assertEqual(e['status'], STATUS_NEEDS_HW)
        self.assertEqual(e['status'], compute_overall(e['substatuses']))
        self.assertNotIn('disproven', e['reasonNotClosed'].lower())
        self.assertFalse(e['programExecutionOpened'])
        self.assertFalse(e['pureGimbalProgramPrimitiveOpenable'])
        self.assertTrue(e['missingHg724NamedCallerDoesNotProveNoInheritedEntry'])
        for key in ('25', '37'):
            self.assertTrue(e['infoByteMaps'][key]['bitsResolved'], key)
        self.assertEqual(sorted(b['bitIndex'] for b in e['infoByteMaps']['25']['setters']), [0, 1, 2, 3, 7])
        self.assertEqual(sorted(b['bitIndex'] for b in e['infoByteMaps']['37']['setters']), [0, 1, 2, 3])
        # Deeper traces present
        self.assertTrue(e['createSetterTraces'])
        self.assertTrue(e['dynamicCallValueSites'] or e['constCameraOrPreviewSetterSites'])
        self.assertTrue(e['instanceInitAndReuse'])
        self.assertTrue(e['stopCallChains'])
        self.assertTrue(e['dynamicBoundaries'])
        facets = {b['facet'] for b in e['dynamicBoundaries']}
        self.assertTrue({'call_values', 'camera_isolation', 'stop_semantics', 'model_entry'} <= facets)
        for b in e['dynamicBoundaries']:
            self.assertTrue(b.get('hardwareMeasurementsNeeded'), b['facet'])
        # No overclaim keys from prior schema
        self.assertNotIn('timelapsePackedInfoBytesUnresolvedForCameraIsolation', e)
        self.assertNotIn('Isolation is statically disproven', e.get('reasonNotClosed', ''))

    def test_path_delay_external_device_is_branch_selected_const_set(self):
        """Regression: v3 at setControlExternalDevice is v2(=1) or v1(=0), not constant 0."""
        e = self.evidence()
        rows = [
            r for r in e['createSetterTraces']
            if r['className'] == 'Lcom/dji/ronin/ui/create/tapgo/CreatePathDelayView;'
            and r['method'] == 'sendToDeviceStart' and r['descriptor'] == '(I)V'
            and r['setter'] == 'setControlExternalDevice'
        ]
        self.assertEqual(len(rows), 1)
        arg = rows[0]['arguments'][0]
        self.assertEqual(arg['kind'], 'const_set')
        self.assertEqual(arg['values'], [0, 1])
        for site in e['constCameraOrPreviewSetterSites']:
            self.assertFalse(
                site['className'].endswith('CreatePathDelayView;') and site['method'] == 'sendToDeviceStart'
                and site['setter'] == 'setControlExternalDevice',
                'PathDelay external-device arg must not be listed as a single constant',
            )
        self.assertIn('unresolvedCallValueSites', e)
