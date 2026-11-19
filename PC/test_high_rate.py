import unittest, numpy as np, struct,zlib
from protocol import encode,Parser,spectrum
from telemetry import parse_rate,parse_telemetry
class HighRate(unittest.TestCase):
 def test_signed24(self):
  raw=np.array([[-524288,0,524287],[-8388608,8388607,-1],[100,-200,300]]*42+[[1,2,3],[4,5,6]],dtype=np.int32)
  self.assertEqual(len(raw),128)
  for fs in [40000,80000]:
   wire=encode(raw,seq=5,fs=fs,first=1234,flags=1,compact=True);self.assertEqual(len(wire),1180)
   p=Parser();out=[]
   for i in range(0,len(wire),7):a,b=p.feed(wire[i:i+7]);out+=a
   self.assertEqual(p.errors,0);self.assertEqual(out[0][1],fs);np.testing.assert_array_equal(out[0][4],raw)
 def test_mixed_formats_and_crc(self):
  raw=np.arange(96).reshape(32,3)-50;p=Parser()
  bad=bytearray(encode(raw,fs=80000,compact=True));bad[30]^=1
  frames,logs=p.feed(encode(raw)+bytes(bad)+b'OK RATE fs=80000\r\n'+encode(raw,fs=80000,compact=True))
  self.assertEqual(len(frames),2);self.assertGreater(p.errors,0);self.assertIn('OK RATE fs=80000',logs)
 def test_high_fft(self):
  fs=80000;n=1024;t=np.arange(n)/fs;x=np.sin(2*np.pi*128*fs/n*t)[:,None]*np.array([[10,20,30]])
  f,a=spectrum(x,fs);self.assertEqual(f[np.argmax(a[:,0])],10000)
  np.testing.assert_allclose(a[128],[10,20,30],rtol=.0001)
  self.assertIsNotNone(parse_rate('RATE current=80000 supported=2500,5000,10000,20000,40000,80000'))
  self.assertIsNotNone(parse_telemetry('FFT valid=1 hz_x100=3900000,3900000,3900000 amp_mg_x100=10,20,30 windows=1 skip=0 age_ms=1 step_max_ms=1'))
if __name__=='__main__':unittest.main()
