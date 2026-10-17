import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ronin_stabilization_trace import source_state_byte,wait_flow,trace,BANKS,PAUSE

class StabilizationTraceTests(unittest.TestCase):
    def flow(self):
        return [(2,'const/4','v1, 1'),(3,'const/4','v2, 0'),(4,'if-eqz','v0, +037h'),(27,'invoke-virtual','v3, '+PAUSE+'->start()V'),(30,'sget-object','v3, Ljava/util/concurrent/TimeUnit;->SECONDS Ljava/util/concurrent/TimeUnit;'),(32,'const-wide/16','v4, 3'),(34,'invoke-virtual','v0, v4, v5, v3, Ljava/util/concurrent/CountDownLatch;->await(J Ljava/util/concurrent/TimeUnit;)Z'),(38,'xor-int/2addr','v2, v1'),(70,'invoke-virtual','v7, '+PAUSE+'->start()V'),(73,'xor-int/lit8','v7, v2, 1'),(75,'return','v7')]

    def test_all_business_bytes_preserve_reason_and_source_truth_table(self):
        for value in range(256):
            state=source_state_byte(value)
            self.assertEqual(state['raw'],value)
            self.assertEqual(state['sourcePauseReasonRaw'],value%64)
            self.assertEqual(state['sourceTurnedOn'],value>=128)
            self.assertEqual(state['sourcePaused'],value<192)
            self.assertEqual(state['sourceNeedPause'],value>=192)

    def test_disabled_state_is_reported_paused_not_physical_completion(self):
        self.assertEqual(source_state_byte(64),dict(raw=64,sourceTurnedOn=False,sourcePaused=True,sourcePauseReasonRaw=0,sourceNeedPause=False))
        self.assertTrue(source_state_byte(128)['sourcePaused'])
        self.assertFalse(source_state_byte(192)['sourcePaused'])

    def test_one_explicit_byte_required(self):
        for value in (True,-1,256,b'\xc0',None,192.0):
            with self.assertRaises(ValueError):source_state_byte(value)

    def test_code_unit_branch_and_same_start_both_paths(self):
        result=wait_flow(self.flow());self.assertEqual(result['timeoutSeconds'],3)
        self.assertEqual(result['startInstructionCodeUnits'],[27,70]);self.assertTrue(result['falseNeedPauseStillSendsStart'])
        self.assertFalse(result['sourceReturnsFirmwareMotionCompletion'])

    def test_wait_branch_displacement_not_byte_offset(self):
        ops=self.flow();ops[2]=(4,'if-eqz','v0, +06eh')
        with self.assertRaisesRegex(ValueError,'branch'):wait_flow(ops)

    def test_changed_timeout_or_return_inversion_rejected(self):
        for pc,op,text in ((32,'const-wide/16','v4, 4'),(73,'xor-int/lit8','v7, v2, 0')):
            ops=[(i,op,text) if i==pc else (i,o,t) for i,o,t in self.flow()]
            with self.assertRaisesRegex(ValueError,'constant/inversion'):wait_flow(ops)

    def test_missing_second_start_not_assumed_resume(self):
        with self.assertRaisesRegex(ValueError,'START send sites'):wait_flow([row for row in self.flow() if row[0]!=70])

    def test_apk_precheck_before_parser(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d))

    def test_bank_prechecks_before_parser(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'fixture')
            for bank in BANKS:(Path(d)/('business-%02d-code-restored.dex'%bank)).write_bytes(b'wrong')
            with patch('ronin_stabilization_trace.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()):
                with self.assertRaisesRegex(ValueError,'restored bank hash mismatch: 00'):trace(p,Path(d))
