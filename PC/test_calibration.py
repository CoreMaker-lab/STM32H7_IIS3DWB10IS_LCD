import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from calibration import Calibration,parse_calibration

ACTIVE='CAL ACTIVE valid=1 offset_ug=12000,-8000,20000 gain_ppm=1020000,980000,1010000'
CANDIDATE=ACTIVE.replace('ACTIVE','CANDIDATE')
def status(session=0,mask=0,face=-1,solved=0,pending=0):
    return f'CAL STATUS session={session} mask={mask} face={face} samples=0 target=12500 solved={solved} pending={pending}'

class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.now=100.;self.sent=[];self.m=Calibration(self.sent.append,lambda:self.now)
        self.m.connection(True);self.feed('CAL INFO fw=104 rule=2 rows=1 accel=1');self.feed(status())
    def feed(self,line):
        event=parse_calibration(line);self.assertIsNotNone(event);self.m.event(event)
    def ready_to_save(self):
        self.assertTrue(self.m.request('begin'));self.feed('OK CAL BEGIN version=1 capture_ms=5000')
        for i,f in enumerate(('X+','X-','Y+','Y-','Z+','Z-')):
            self.assertTrue(self.m.request('face',i));self.feed(f'OK CAL FACE {f} samples=12500')
            self.assertIsNotNone(self.m.pending)
            self.feed(f'CAL FACE_DONE rc=0 mask={(1<<(i+1))-1} mean_ug=1000000,0,0')
        self.assertTrue(self.m.request('solve'));self.feed(CANDIDATE)
    def test_save_requires_final_and_readback(self):
        self.ready_to_save();self.assertTrue(self.m.request('save'))
        self.feed('OK CAL SAVE pending');self.assertFalse(self.m.success);self.assertTrue(self.m.locked)
        self.feed('CAL SAVE rc=0 sensor_resume=0 seq=17 relearn=1')
        self.assertFalse(self.m.success);self.assertEqual(self.m.pending,'verify')
        self.feed(status());self.feed(ACTIVE)
        self.assertTrue(self.m.success);self.assertFalse(self.m.locked)
    def test_failed_pose_and_cancel_during_capture(self):
        self.m.request('begin');self.feed('OK CAL BEGIN version=1 capture_ms=5000')
        self.m.request('face',0);self.feed('OK CAL FACE X+ samples=12500')
        self.feed('CAL FACE_DONE rc=-1 mask=0 mean_ug=0,0,0')
        self.assertEqual(self.m.mask,0);self.assertIn('未通过',self.m.note)
        self.m.request('face',0);self.assertTrue(self.m.request('cancel'));self.feed('OK CAL CANCEL')
        self.assertFalse(self.m.session)
    def test_timeout_does_not_claim_success(self):
        self.ready_to_save();self.m.request('save');self.feed('OK CAL SAVE pending')
        self.now+=9;self.m.tick();self.assertFalse(self.m.success);self.assertTrue(self.m.locked)
        self.feed(status());self.feed(ACTIVE)
        self.assertFalse(self.m.success);self.assertIn('未确认',self.m.note)
        self.feed('CAL SAVE rc=0 sensor_resume=0 seq=17 relearn=1');self.assertFalse(self.m.success)
    def test_disconnect_recover_session(self):
        self.ready_to_save();self.m.request('save');self.m.connection(False)
        self.assertFalse(self.m.success);self.assertIsNone(self.m.candidate)
        self.m.connection(True);self.feed('CAL INFO fw=104 rule=2 rows=1 accel=1');self.feed(status(session=1,mask=63,solved=1))
        self.assertTrue(self.m.locked);self.assertFalse(self.m.request('save'))
        self.assertTrue(self.m.request('solve'));self.feed(CANDIDATE)
    def test_failed_save_and_mismatched_readback(self):
        self.ready_to_save();self.m.request('save')
        self.feed('CAL SAVE rc=-9 sensor_resume=0 seq=17 relearn=1');self.assertFalse(self.m.success)
        self.feed(status(session=1,mask=63,solved=1));self.assertTrue(self.m.request('save'))
        self.feed('CAL SAVE rc=0 sensor_resume=0 seq=18 relearn=1')
        self.feed(ACTIVE.replace('12000','13000'));self.assertFalse(self.m.success)
        self.assertIn('不一致',self.m.note)
    def test_parser_rejects_bad_input(self):
        for line in [status(mask=64),status(face=6),'xx'+ACTIVE,ACTIVE+' junk',ACTIVE.replace('1020000','99999999'),
                     'CAL FACE_DONE rc=1 mask=0 mean_ug=0,0,0', 'OK CAL FACE X+ samples=40000']:
            self.assertIsNone(parse_calibration(line),line)
    def test_rejected_operation_and_unsupported(self):
        self.m.request('begin');self.feed('ERR CAL busy_or_sensor')
        self.assertFalse(self.m.session);self.assertIsNone(self.m.pending)
        self.feed('ERR COMMAND');self.assertFalse(self.m.known);self.assertFalse(self.m.locked)
    def test_live_values_staleness_and_heartbeat(self):
        self.m.monitor(True);self.assertEqual(self.sent[-1],'CAL MONITOR 1')
        self.feed('OK CAL MONITOR 1')
        self.feed('CAL LIVE mean_ug=-287125,194971,807483 std_ug=1900,2100,2300 stable=1')
        self.assertTrue(self.m.live_fresh());self.assertEqual(self.m.live['mean'][0],-287125)
        self.assertFalse(self.m.session);self.assertFalse(self.m.success)
        self.now+=2.1;self.m.tick();self.assertFalse(self.m.live_fresh())
        self.assertEqual(self.sent[-1],'CAL MONITOR 1')
        self.m.monitor(False);self.assertEqual(self.sent[-1],'CAL MONITOR 0');self.assertIsNone(self.m.live)
        self.assertIsNotNone(parse_calibration(ACTIVE.replace('12000','1200000')))
        self.assertIsNone(parse_calibration(ACTIVE.replace('12000','5000001')))
        self.assertIsNone(parse_calibration('CAL LIVE mean_ug=0,0,0 std_ug=-1,0,0 stable=1'))
    def test_diagnostic_rows_and_single_face_retry(self):
        self.ready_to_save()
        self.feed('CAL ROW face=2 valid=1 raw_ug=1120000,1000000,1870000 residual_ug=123000,0,0 checked=1')
        self.feed('CAL CHECK rc=-3 worst_face=2 worst_axis=0 max_ug=123000 span_ug=2000000,2000000,2000000')
        self.feed('ERR CAL SOLVE rc=-3 mask=63')
        self.assertIn('Y+',self.m.note);self.assertIn('123.00',self.m.note)
        self.assertEqual(self.m.rows[2]['raw'][0],1120000)
        self.assertTrue(self.m.request('face',2));self.assertFalse(self.m.rows[2]['checked']);self.assertIsNone(self.m.check)
        self.feed('OK CAL FACE Y+ samples=12500')
        self.feed('CAL FACE_DONE rc=0 mask=63 mean_ug=1200000,1000000,1870000')
        self.assertEqual(self.m.mask,63);self.assertIn('CAL DATA',self.sent)
        self.assertIsNone(parse_calibration('CAL ROW face=8 valid=1 raw_ug=0,0,0 residual_ug=0,0,0 checked=1'))
    def test_quality_rules_and_actual_main_display(self):
        self.feed('CAL QUALITY rule=2 norm_ug=1000,1000,1000,1000,2700,1000 pair_ug=32000,42000,29000')
        self.feed('CAL CHECK rc=0 worst_face=4 worst_axis=0 max_ug=73750 span_ug=1985182,1996184,1989080')
        self.assertEqual(self.m.quality['pair'][1],42000)
        self.feed('CAL QUALITY rule=2 norm_ug=1000,1000,78000,1000,1000,1000 pair_ug=0,0,0')
        self.feed('CAL CHECK rc=-4 worst_face=2 worst_axis=0 max_ug=400000 span_ug=2000000,2000000,2000000')
        self.assertIn('合量核验未通过',self.m.note)
        self.feed('ACCEL mean_ug=123,-456,1000000 calibrated=1')
        self.assertTrue(self.m.actual_fresh());self.assertTrue(self.m.actual['calibrated'])
        self.now+=2.1;self.assertFalse(self.m.actual_fresh())
        self.assertIsNone(parse_calibration('ACCEL mean_ug=0,0,1000000 calibrated=2'))
    def test_old_firmware_is_visible_and_capture_not_lost(self):
        self.m.connection(False);self.m.connection(True)
        self.feed('MCU CAL V1.1 / PERF V1 / RATE V1.1 / FFT V3')
        self.feed(status(session=1,mask=0))
        self.feed('ERR CAL command')
        self.assertFalse(self.m.link_ready);self.assertIn('V1.1',self.m.version_text())
        self.assertFalse(self.m.request('solve'))
        self.feed('CAL INFO fw=104 rule=2 rows=1 accel=1');self.assertTrue(self.m.link_ready)
        self.assertTrue(self.m.request('face',0));self.feed('OK CAL FACE X+ samples=12500')
        self.feed('CAL FACE_DONE rc=0 mask=1 mean_ug=759326,285421,-142758')
        self.assertEqual(self.m.rows[0]['raw'],(759326,285421,-142758))
    def test_qt_integration(self):
        from PySide6 import QtWidgets
        from app import Window, Receiver
        qapp=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        win=Window();win.timer.stop();w=Receiver('TEST',921600);w.connected=True;w.is_alive=lambda:True;win.worker=w
        w.log(status());w.log('CAL INFO fw=104 rule=2 rows=1 accel=1');win.update_data();self.assertTrue(win.calibration.known)
        w.log('CAL LIVE mean_ug=-287125,194971,807483 std_ug=1900,2100,2300 stable=1');win.update_data()
        self.assertIn('-287.125',win.cal_dialog.live_cards[0].text())
        self.assertIn('静止',win.cal_dialog.live_state.text())
        w.log('ACCEL mean_ug=1000,-2000,1000000 calibrated=1');win.update_data()
        self.assertIn('+1000.000',win.xyz_cards[2].text());self.assertIn('已应用',win.xyz_note.text())
        self.assertTrue(win.calibration.request('begin'))
        w.log('OK CAL BEGIN version=1 capture_ms=5000');win.update_data()
        self.assertFalse(win.learn.isEnabled());self.assertFalse(win.rate_apply.isEnabled());self.assertFalse(win.record.isEnabled())
        self.assertTrue(win.cal_dialog.capture.isEnabled())
        win.calibration.request('face',0);w.log('OK CAL FACE X+ samples=12500');win.update_data()
        self.assertTrue(win.cal_dialog.cancel.isEnabled());self.assertFalse(win.cal_dialog.capture.isEnabled())
        win.calibration.request('cancel');w.log('OK CAL CANCEL');win.update_data()
        self.assertFalse(win.calibration.locked);self.assertTrue(win.record.isEnabled())
        win.worker=None;win.calibration.connection(False);win.close();qapp.processEvents()

if __name__=='__main__':unittest.main()
