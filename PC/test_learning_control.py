import unittest,time,queue,threading,os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from learning_control import CommandPacer,LearningTransaction,parse_learning

class LearningTests(unittest.TestCase):
    def setUp(self):
        self.now=10.;self.sent=[];self.tx=LearningTransaction(self.sent.append,lambda:self.now)
    def wire(self,cmd='LEARN'):
        self.tx.event(self.now,('sent',cmd,''))
    def test_one_click_queues_only_learn(self):
        self.assertTrue(self.tx.request('LEARN'));self.assertEqual(self.sent,['LEARN'])
        self.assertFalse(self.tx.request('LEARN'));self.assertEqual(self.sent,['LEARN'])
    def test_ack_then_state_no_retry(self):
        self.tx.request('LEARN');self.wire();self.tx.event(self.now,parse_learning('OK LEARN 30S'))
        self.now+=2.1;self.tx.tick(True);self.assertEqual(self.sent,['LEARN'])
        self.tx.observe(self.now,1);self.assertIsNone(self.tx.pending);self.assertIn('已进入',self.tx.note)
    def test_missing_ack_bounded_and_existing_learning_stops_retry(self):
        self.tx.request('LEARN')
        for i in range(3):
            self.wire();self.now+=2.1;self.tx.tick(True)
        self.assertEqual(self.sent,['LEARN']*3);self.assertIsNone(self.tx.pending)
        self.tx.request('LEARN');self.wire();self.tx.observe(self.now,1)
        self.now+=10;self.tx.tick(True);self.assertEqual(len(self.sent),4)
    def test_errors_are_explicit_and_not_retried(self):
        for line in ['ERR LEARN busy','ERR LEARN sensor_not_ready','ERR CAL session_active','ERR BUSY NVM pending']:
            self.tx.request('LEARN');self.wire();self.tx.event(self.now,parse_learning(line))
            self.assertIsNone(self.tx.pending);self.assertIn('拒绝',self.tx.note)
        self.assertEqual(len(self.sent),4)
    def test_stale_telemetry_does_not_confirm_unsent_cancel(self):
        self.tx.request('CANCEL');self.tx.observe(self.now,3);self.assertIsNotNone(self.tx.pending)
        self.wire('CANCEL');self.tx.event(self.now,parse_learning('OK CANCEL'));self.assertIsNone(self.tx.pending)
    def test_accepted_but_state_missing_not_resent(self):
        self.tx.request('LEARN');self.wire();self.tx.event(self.now,parse_learning('OK LEARN 30S'))
        self.now+=5.1;self.tx.tick(True);self.assertEqual(self.sent,['LEARN']);self.assertIn('未确认持续',self.tx.note)
    def test_cancel_removes_unsent_learn_and_query_coalescing(self):
        p=CommandPacer();p.add('LEARN');p.add('CAL STATUS');p.add('CAL STATUS');p.add('CANCEL')
        self.assertEqual(list(p.items),['CAL STATUS','CANCEL'])
    def test_spacing_avoids_receiver_rearm_blackout(self):
        p=CommandPacer();p.add('START');p.add('LEARN');received=[];ready=-1
        for ms in range(200):
            cmd=p.take(ms/1000)
            if cmd is not None:
                self.assertGreaterEqual(ms/1000,ready);received.append(cmd);ready=ms/1000+.05
        self.assertEqual(received,['START','LEARN'])
    def test_ui_reports_rejection_and_starts_upload_only_after_learning_state(self):
        from PySide6 import QtWidgets
        from app import Window,Receiver
        app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        win=Window();win.timer.stop();w=Receiver('TEST',921600);w.connected=True;w.is_alive=lambda:True;win.worker=w
        try:
            win.learning_command('LEARN');self.assertFalse(win.learn.isEnabled())
            self.assertEqual(w.commands.get_nowait()[0],'LEARN');self.assertTrue(w.commands.empty())
            w.learning_event(('sent','LEARN',''));w.log('ERR LEARN busy');win.update_detection(w)
            self.assertIsNone(win.pending_command);self.assertIn('拒绝',win.learning_note.text())
            win.learning_command('LEARN');self.assertEqual(w.commands.get_nowait()[0],'LEARN')
            w.learning_event(('sent','LEARN',''));w.log('OK LEARN 30S');win.update_detection(w)
            self.assertIsNotNone(win.pending_command);self.assertTrue(w.commands.empty())
            w.log('DETECT state=1 progress=10 score_x100=0 model=1 blocks=15');win.update_detection(w)
            self.assertIsNone(win.pending_command);self.assertEqual(w.commands.get_nowait()[0],'START')
            self.assertIn('已进入',win.learning_note.text())
        finally:
            win.calibration.connection(False);win.worker=None;win.close();app.processEvents()
    def test_text_only_ack_is_delivered_without_future_bytes(self):
        from protocol import Parser, MAGIC, encode
        p=Parser();packets,lines=p.feed(b'OK LEARN 30S\r\n')
        self.assertEqual(lines,['OK LEARN 30S']);self.assertEqual(len(packets),0)
        frame=encode([[1,2,3]]*32)
        for length in (1,2,3):
            p=Parser();a,b=p.feed(b'OK CANCEL\r\n'+frame[:length])
            self.assertEqual(b,['OK CANCEL']);self.assertEqual(bytes(p.buf),MAGIC[:length])
            a,b=p.feed(frame[length:]);self.assertEqual(len(a),1);self.assertEqual(p.errors,0)
    def test_receiver_real_write_loop_paces_commands_and_reports_ack(self):
        from app import Receiver
        from unittest.mock import patch
        w=Receiver('TEST',921600);writes=[];buf=bytearray();lock=threading.Lock()
        class FakeSerial:
            def __init__(self,*a,**kw):pass
            @property
            def in_waiting(self):return len(buf)
            def write(self,data):
                now=time.monotonic();writes.append((now,data))
                if data==b'LEARN\n':
                    with lock:buf.extend(b'OK LEARN 30S\r\nDETECT state=1 progress=0 score_x100=0 model=1 blocks=0\r\n')
                return len(data)
            def read(self,n):
                time.sleep(.002)
                with lock:out=bytes(buf[:n]);del buf[:n]
                return out
            def close(self):pass
        with patch('app.serial.Serial',FakeSerial):
            w.commands.put(('CAL MONITOR 1',None));w.commands.put(('LEARN',None));w.start()
            deadline=time.monotonic()+1
            while time.monotonic()<deadline and w.detections.empty():time.sleep(.005)
            w.stop_event.set();w.join(2)
        self.assertFalse(w.is_alive());self.assertFalse(w.detections.empty())
        commands=[(t,b) for t,b in writes if b!=b'STOP\n']
        self.assertEqual(sum(b==b'LEARN\n' for _,b in commands),1)
        for (t,_),(u,_) in zip(commands,commands[1:]):self.assertGreaterEqual(u-t,.075)
        events=[]
        while not w.learning_events.empty():events.append(w.learning_events.get_nowait()[1][0])
        self.assertEqual(events,['sent','ack'])
if __name__=='__main__':unittest.main()
