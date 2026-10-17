import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_reset_routes import source_platform_route,source_product_variant,reset_mode_body,branch_routes,trace,BANKS

class ResetRouteTests(unittest.TestCase):
    def branches(self):return [(4,'if-eqz','v0, +05fh'),(20,'if-nez','v1, +031h'),(28,'if-nez','v1, +029h'),(36,'if-eqz','v0, +003h'),(38,'goto','+1fh')]

    def test_three_exact_platform_labels_take_mode_path(self):
        for name in ('M200','M210','M210RTK'):self.assertEqual(source_platform_route(name),'gimbal-reset-and-mode')
        for name in ('HG724','Orange2','m200','M200 '):self.assertEqual(source_platform_route(name),'special-control-factory')

    def test_product_selector_is_separate_from_platform(self):
        self.assertEqual(source_platform_route('Orange2'),'special-control-factory')
        self.assertEqual(source_product_variant('Orange2'),'new-special-control')
        for name in ('Pomato','M200','M210','M210RTK','Potato'):self.assertEqual(source_product_variant(name),'new-special-control')
        self.assertEqual(source_product_variant('HG724'),'old-special-control')

    def test_labels_are_not_wire_enums_or_truthy_numbers(self):
        for fn in (source_platform_route,source_product_variant):
            for value in ('',103,True,None):
                with self.assertRaises(ValueError):fn(value)

    def test_mode_reset_body_preserves_mode_and_boolean(self):
        self.assertEqual(reset_mode_body(254,True).hex(),'fe01')
        self.assertEqual(reset_mode_body(254,False).hex(),'fe00')
        self.assertEqual(reset_mode_body(0,True).hex(),'0001')
        self.assertEqual(reset_mode_body(255,False).hex(),'ff00')

    def test_body_does_not_accept_axis_enum_or_coerced_boolean(self):
        for mode,reset in ((True,True),(-1,True),(256,True),(254,1),(254,'yaw')):
            with self.assertRaises(ValueError):reset_mode_body(mode,reset)

    def test_code_unit_branch_targets(self):
        self.assertEqual(branch_routes(self.branches()),dict(pauseFailureReturnsAtCodeUnit=99,matchedPlatformPathCodeUnit=69,otherPlatformPathCodeUnit=39))

    def test_changed_platform_branch_rejected(self):
        for pc,op,text in ((20,'if-nez','v1, +062h'),(38,'goto','+20h')):
            ops=[(i,op,text) if i==pc else (i,o,t) for i,o,t in self.branches()]
            with self.assertRaises(ValueError):branch_routes(ops)

    def test_apk_precheck_before_parser(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d))

    def test_bank_prechecks_before_parser(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'fixture')
            for bank in BANKS:(Path(d)/('business-%02d-code-restored.dex'%bank)).write_bytes(b'wrong')
            with patch('ronin_reset_routes.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()):
                with self.assertRaisesRegex(ValueError,'restored bank hash mismatch: 00'):trace(p,Path(d))
