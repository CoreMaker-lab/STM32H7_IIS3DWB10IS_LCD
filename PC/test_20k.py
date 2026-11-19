import unittest
import numpy as np
from calibration import parse_calibration
from telemetry import parse_rate,parse_telemetry
from protocol import Parser,encode
class Rate20kTests(unittest.TestCase):
 def test_capture_and_peak(self):
  self.assertIsNotNone(parse_calibration('OK CAL FACE Z+ samples=100000'))
  self.assertIsNotNone(parse_calibration('CAL STATUS session=1 mask=0 face=4 samples=99999 target=100000 solved=0 pending=0'))
  self.assertIsNotNone(parse_telemetry('FFT valid=1 hz_x100=820000,980000,100000 amp_mg_x100=100,200,300 windows=1 skip=0 age_ms=0 step_max_ms=1'))
  self.assertEqual(parse_rate('RATE current=20000 supported=2500,5000,10000,20000')[1]['current'],20000)
 def test_full_second_fragmented(self):
  parser=Parser();expected=np.arange(20000*3,dtype=np.int32).reshape(-1,3);wire=b''.join(encode(expected[i:i+32],i//32,20000,i) for i in range(0,len(expected),32));rows=[]
  for i in range(0,len(wire),137):
   packets,_=parser.feed(wire[i:i+137]);rows.extend(p[4] for p in packets)
  np.testing.assert_array_equal(np.vstack(rows),expected);self.assertEqual(parser.errors,0)
