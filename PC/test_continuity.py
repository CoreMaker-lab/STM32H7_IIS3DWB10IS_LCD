import unittest
from continuity import Continuity
class TestContinuity(unittest.TestCase):
    def test_wrap_and_normal(self):
        c=Continuity();self.assertIsNone(c.feed(0xffffffff,80000,0xffffff80,0,128))
        self.assertIsNone(c.feed(0,80000,0,0,128));self.assertEqual(c.events,0)
    def test_independent_causes(self):
        c=Continuity();c.feed(10,80000,1000,0,128)
        e=c.feed(12,80000,1256,0,128)
        self.assertEqual(e['reasons'],['seq','index']);self.assertEqual(e['seq_delta'],1);self.assertEqual(e['index_delta'],128)
        self.assertEqual(c.feed(13,80000,1384,1,128)['reasons'],['flags'])
        self.assertEqual(c.feed(14,40000,1512,0,128)['reasons'],['rate'])
        self.assertEqual(c.events,3)
    def test_first_flag_explicit(self):
        c=Continuity();e=c.feed(0,80000,0,1,128)
        self.assertIsNone(e['previous']);self.assertEqual(e['reasons'],['flags'])
if __name__=='__main__':unittest.main()
