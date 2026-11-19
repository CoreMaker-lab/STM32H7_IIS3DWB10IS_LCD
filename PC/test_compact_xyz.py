import os,time,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6 import QtWidgets
from app import Window,Receiver

class CompactXYZTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    def setUp(self):
        self.win=Window();self.win.timer.stop();self.w=Receiver('TEST',921600)
        self.w.connected=True;self.w.is_alive=lambda:True;self.win.worker=self.w
        self.w.log('CAL INFO fw=104 rule=2 rows=1 accel=1')
    def tearDown(self):
        self.win.calibration.connection(False);self.win.worker=None;self.win.close();self.app.processEvents()
    def test_independent_raw_and_corrected_rows(self):
        self.w.log('CAL LIVE mean_ug=-365269,225966,800225 std_ug=1000,1000,1000 stable=1')
        self.w.log('ACCEL mean_ug=0,0,1000000 calibrated=1');self.win.update_data()
        self.assertIn('-365.269',self.win.raw_xyz_cards[0].text())
        self.assertIn('+1000.000',self.win.corrected_xyz_cards[2].text())
        self.assertIn('已应用',self.win.corrected_xyz_state.text())
    def test_uncalibrated_and_stale_not_mislabeled(self):
        self.w.log('CAL LIVE mean_ug=-365269,225966,800225 std_ug=1000,1000,1000 stable=1')
        self.w.log('ACCEL mean_ug=-365269,225966,800225 calibrated=0');self.win.update_data()
        self.assertIn('—',self.win.corrected_xyz_cards[0].text())
        self.assertEqual(self.win.corrected_xyz_state.text(),'尚未校准')
        self.win.calibration.live_stamp-=3;self.win.calibration.actual_stamp-=3;self.win.update_data()
        self.assertIn('—',self.win.raw_xyz_cards[0].text());self.assertIn('超时',self.win.raw_xyz_state.text())
    def test_main_has_no_page_scroll_and_fits_900(self):
        self.win.resize(1280,900);self.win.show();self.app.processEvents()
        self.assertNotIsInstance(self.win.centralWidget(),QtWidgets.QScrollArea)
        self.assertLessEqual(self.win.minimumSizeHint().height(),900)
        bottom=self.win.log.mapTo(self.win.centralWidget(),self.win.log.rect().bottomRight()).y()
        self.assertLess(bottom,self.win.centralWidget().height())

if __name__=='__main__':unittest.main()
