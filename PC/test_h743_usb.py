import os,unittest,queue,time
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from telemetry import parse_telemetry
from detection import parse_detection

FFT='FFT valid=1 hz_x100=244,24658,37109 amp_mg_x100=270,122,252 windows=155 skip=0'
DETECT='DETECT state=0 progress=0 score_x100=0 model=0 blocks=0 NVM=1'
FIFO='FIFO samples/s=2489 level=0 ovr=0 errors=0 UI_fps=30 init=0 LCD=0 tx_drop=5 stream_drop=0 rx_ovf=0'
class H743Tests(unittest.TestCase):
 def test_telemetry(self):
  kind,v=parse_telemetry(FFT);self.assertEqual(kind,'fft');self.assertIsNone(v['age']);self.assertEqual(v['hz'][1],246.58)
  self.assertEqual(parse_telemetry(DETECT),('h7nvm',{'code':1}))
  self.assertEqual(parse_telemetry(FIFO)[1]['rate'],2489)
  self.assertEqual(parse_telemetry('NVM save=0 restart=0 models=1')[1],{'save':0,'restart':0,'models':1})
  self.assertIsNotNone(parse_detection(DETECT))
 def test_real_window_h7_state(self):
  from PySide6 import QtWidgets
  from app import Window,Receiver
  app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
  window=Window();worker=Receiver('COM17',115200);worker.connected=True;worker.is_alive=lambda:True;window.worker=worker
  for line in (FIFO,FFT,DETECT):worker.log(line)
  self.assertTrue(worker.is_h7)
  window.update_mcu_telemetry(worker);window.update_detection(worker);window.update_calibration(worker)
  self.assertIn('2489',window.perf_label.text());self.assertIn('未上报',window.mcu_fft_status.text());self.assertIn('无有效保存记录',window.nvm_label.text())
  self.assertFalse(window.cancel_learn.isEnabled());self.assertFalse(window.cal_button.isEnabled())
  window.show();app.processEvents();window.grab().save('/tmp/h743_previous_ui_preview.png')
  window.worker=None;window.close()
if __name__=='__main__':unittest.main()
