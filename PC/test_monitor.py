import unittest, tempfile, time, os
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np
from protocol import Parser, encode, spectrum
from detection import parse_detection

class MonitorTests(unittest.TestCase):
 def test_mixed_fragmented_telemetry(self):
  raw=np.array([[-524288,0,524287]]*32)
  line=b'DETECT state=1 progress=20 score_x100=123 model=0 blocks=30\r\n'
  frame=encode(raw,12,2500,384)
  p=Parser();packets=[];logs=[]
  for byte in frame+line+frame+b'END\r\n':
   a,b=p.feed(bytes([byte]));packets+=a;logs+=b
  self.assertEqual(len(packets),2);self.assertEqual(p.errors,0)
  d=[parse_detection(x) for x in logs if parse_detection(x)][0]
  self.assertEqual(d.progress,20);self.assertEqual(d.score,1.23)
  np.testing.assert_array_equal(packets[0][4],raw)
 def test_invalid_telemetry(self):
  for s in ['DETECT state=9 progress=0 score_x100=0 model=0 blocks=0','DETECT state=1 progress=101 score_x100=0 model=0 blocks=0','garbageDETECT state=1 progress=0 score_x100=0 model=0 blocks=0']:
   self.assertIsNone(parse_detection(s))
 def test_crc_and_resync(self):
  good=encode([[123,-456,789]]*32);bad=bytearray(good);bad[29]^=1
  p=Parser();out,_=p.feed(bad+good)
  self.assertEqual(len(out),1);self.assertGreater(p.errors,0)
 def test_fft_amplitude(self):
  t=np.arange(5000)/2500;y=np.column_stack([10*np.sin(2*np.pi*50*t)+1000]*3)
  f,a=spectrum(y,2500);self.assertEqual(f[np.argmax(a[:,0])],50);self.assertAlmostEqual(a[:,0].max(),10,places=3)
 def test_serial_csv(self):
  from app import Receiver
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'data.csv';w=Receiver('TEST',921600)
   from unittest.mock import patch
   frame=encode([[1,2,3]]*32)
   class FakeSerial:
    in_waiting=len(frame)
    def __init__(self,*a,**kw):pass
    def write(self,data):return len(data)
    def read(self,n):time.sleep(.002);return frame
    def close(self):pass
   serial_patch=patch('app.serial.Serial',FakeSerial);serial_patch.start();self.addCleanup(serial_patch.stop)
   w.start()
   w.commands.put(('record',str(path)));w.commands.put(('START',None));time.sleep(.25)
   w.stop_event.set();w.join(2)
   self.assertFalse(w.is_alive());self.assertGreater(w.recorded,100)
   self.assertEqual(len(path.read_text(encoding='utf-8-sig').splitlines()),w.recorded+1)
 def test_ui_learning_and_stale(self):
  from PySide6 import QtWidgets
  from app import Window, Receiver
  qapp=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
  win=Window();win.timer.stop();w=Receiver('TEST',921600)
  w.connected=True;w.is_alive=lambda:True;win.worker=w
  win.learning_command('LEARN');self.assertEqual(w.commands.get_nowait()[0],'LEARN');self.assertTrue(w.commands.empty())
  self.assertIsNone(win.last_detection)
  w.learning_event(('sent','LEARN',''))
  w.log('DETECT state=1 progress=20 score_x100=0 model=0 blocks=30');win.update_detection(w)
  self.assertEqual(win.progress.value(),20);self.assertIsNone(win.pending_command);self.assertFalse(win.learn.isEnabled());self.assertEqual(w.commands.get_nowait()[0],'START')
  w.log('DETECT state=5 progress=100 score_x100=820 model=1 blocks=150');win.update_detection(w)
  self.assertIn('异常报警',win.detect_label.text());self.assertIn('8.20',win.score_label.text())
  win.detect_time-=4;win.update_detection(w);self.assertIn('超时',win.detect_label.text());self.assertIn('—',win.score_label.text())
  win.worker=None;win.close();qapp.processEvents()
if __name__=='__main__':unittest.main()
