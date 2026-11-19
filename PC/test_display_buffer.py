import unittest
import numpy as np
from display_buffer import SampleRing
class RingTest(unittest.TestCase):
 def test_wrap(self):
  r=SampleRing(5);x=np.arange(27).reshape(9,3)
  r.extend(x[:3]);r.extend(x[3:7]);np.testing.assert_array_equal(r.tail(10),x[2:7])
  r.extend(x[7:]);np.testing.assert_array_equal(r.tail(3),x[6:])
 def test_large_clear_copy(self):
  r=SampleRing(5);x=np.arange(30).reshape(10,3);r.extend(x)
  np.testing.assert_array_equal(r.tail(100),x[-5:]);v=r.tail(2);v[:]=0
  np.testing.assert_array_equal(r.tail(2),x[-2:]);r.clear();self.assertEqual(len(r),0)
if __name__=='__main__':unittest.main()
